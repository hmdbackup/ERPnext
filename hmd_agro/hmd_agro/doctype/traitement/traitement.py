# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today, add_days

from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_WAREHOUSE as WAREHOUSE


class Traitement(Document):
    def validate(self):
        self.validate_animal_active()
        self.validate_date_traitement()
        self.lock_identity_fields()
        self.validate_type_has_medicaments()
        self.calculate_attente_dates()

    def after_insert(self):
        self.decrement_medicament_stock()
        self.update_animal_attente_lait()

    def on_trash(self):
        self.restore_medicament_stock()
        self.update_animal_attente_lait(clear=True)

    def validate_animal_active(self):
        """RG19: Animal must be ACTIF for treatment"""
        if self.animal:
            statut = frappe.db.get_value("Animal", self.animal, "statut")
            if statut != "ACTIF":
                frappe.throw("RG19: L'animal doit être ACTIF pour recevoir un traitement.")

    def validate_date_traitement(self):
        """Date traitement cannot be in the future"""
        if self.date_traitement and getdate(self.date_traitement) > getdate(today()):
            frappe.throw("La date de traitement ne peut pas être dans le futur.")

    def lock_identity_fields(self):
        """Prevent editing animal after creation"""
        if self.is_new() or self.flags.ignore_validate:
            return
        db_doc = self.get_doc_before_save()
        if not db_doc:
            return

        if str(self.animal or "") != str(db_doc.animal or ""):
            frappe.throw(
                "Le champ 'Animal' ne peut pas être modifié après création. "
                "Supprimez ce traitement et créez-en un nouveau."
            )

    def validate_type_has_medicaments(self):
        """CF-TRT-02: TRAITEMENT_MEDICAL must have medicaments"""
        if self.type_traitement == "TRAITEMENT_MEDICAL":
            if not self.medicaments or len(self.medicaments) == 0:
                frappe.throw(
                    "Un traitement médical doit contenir au moins un médicament."
                )

    def calculate_attente_dates(self):
        """RC-TMD-01: Calculate date_fin_attente_lait for each medicament row"""
        if self.type_traitement != "TRAITEMENT_MEDICAL" or not self.medicaments:
            return
        for row in self.medicaments:
            if row.delai_attente_lait and self.date_traitement:
                row.date_fin_attente_lait = add_days(
                    self.date_traitement, row.delai_attente_lait
                )

    def decrement_medicament_stock(self):
        """RG20: post one Material Issue per medicament row (Stock Module only,
        post-Phase C). Qty consumed = `row.qty_consumed` (ST5-11). Pre-ST5-11
        the qty was hardcoded to 1, regardless of the medical `dose` field —
        a vet administering 50ml of a 100ml flacon decremented 1 "unit" of
        stock, which was wrong. Now `qty_consumed` is a separate field on
        Traitement Medicale (default 1, optional) and represents the stock
        unit count (e.g. 0.5 for half a flacon). `dose` stays the medical
        metadata. Default 1 preserves backward-compat for old rows.

        With Item.allow_negative_stock=1 on MED-*, the issue always succeeds
        even when Bin is at/below 0 — production stance: a recorded Traitement
        represents a real event that already happened. A soft msgprint warns
        when Bin is depleted; the native reorder Material Request (ST5-08)
        fires preventively at reorder_level."""
        if self.type_traitement != "TRAITEMENT_MEDICAL" or not self.medicaments:
            return
        from hmd_agro.hmd_agro.utils.stock_utils import create_stock_movement
        for row in self.medicaments:
            if not row.medicament:
                continue
            qty = float(row.qty_consumed or 1)
            if qty <= 0:
                continue
            item = frappe.db.get_value("Medicament", row.medicament, "item")
            if not item:
                frappe.msgprint(
                    f"Médicament {row.medicament} non lié à un Item ERPNext — "
                    f"écriture stock ignorée. Lancer medicament_migration.",
                    indicator="orange", alert=True,
                )
                continue
            bin_qty = frappe.db.get_value(
                "Bin",
                {"item_code": item, "warehouse": WAREHOUSE},
                "actual_qty",
            ) or 0
            if bin_qty <= 0:
                frappe.msgprint(
                    f"Attention: stock système épuisé pour {row.medicament} "
                    f"(Bin={bin_qty}). Mouvement enregistré en négatif — "
                    f"pensez à saisir une Purchase Receipt pour rattraper.",
                    indicator="orange", alert=True,
                )
            create_stock_movement(item, qty, "Material Issue",
                WAREHOUSE,
                f"Traitement {self.name}", self.date_traitement)

    def restore_medicament_stock(self):
        """Compensating Material Receipt per medicament row on Traitement
        delete. ST5-11: restores `row.qty_consumed` (default 1) to mirror the
        original decrement exactly."""
        if self.type_traitement != "TRAITEMENT_MEDICAL" or not self.medicaments:
            return
        from hmd_agro.hmd_agro.utils.stock_utils import create_stock_movement
        for row in self.medicaments:
            if not row.medicament:
                continue
            qty = float(row.qty_consumed or 1)
            if qty <= 0:
                continue
            item = frappe.db.get_value("Medicament", row.medicament, "item")
            if not item:
                continue
            create_stock_movement(item, qty, "Material Receipt",
                WAREHOUSE,
                f"Restore Traitement {self.name} delete", self.date_traitement)

    def update_animal_attente_lait(self, clear=False):
        """Update Animal milk withdrawal flag based on all treatments"""
        if not self.animal:
            return

        if clear:
            # Recalculate from all OTHER traitements for this animal
            max_date = frappe.db.sql("""
                SELECT MAX(tm.date_fin_attente_lait)
                FROM `tabTraitement Medicale` tm
                JOIN `tabTraitement` t ON t.name = tm.parent
                WHERE t.animal = %s
                  AND t.name != %s
                  AND tm.date_fin_attente_lait >= %s
            """, (self.animal, self.name, today()))
        else:
            # Recalculate from ALL traitements for this animal
            max_date = frappe.db.sql("""
                SELECT MAX(tm.date_fin_attente_lait)
                FROM `tabTraitement Medicale` tm
                JOIN `tabTraitement` t ON t.name = tm.parent
                WHERE t.animal = %s
                  AND tm.date_fin_attente_lait >= %s
            """, (self.animal, today()))

        max_date = max_date[0][0] if max_date and max_date[0][0] else None

        if max_date:
            frappe.db.set_value("Animal", self.animal, {
                "attente_lait_active": 1,
                "date_fin_attente_lait": max_date
            })
        else:
            frappe.db.set_value("Animal", self.animal, {
                "attente_lait_active": 0,
                "date_fin_attente_lait": None
            })


@frappe.whitelist()
def refresh_attente_lait():
    """Clear expired milk withdrawal flags daily"""
    expired = frappe.get_all("Animal", filters={
        "attente_lait_active": 1,
        "date_fin_attente_lait": ["<", today()]
    }, pluck="name")
    for animal in expired:
        frappe.db.set_value("Animal", animal, {
            "attente_lait_active": 0,
            "date_fin_attente_lait": None
        })
    if expired:
        frappe.db.commit()


@frappe.whitelist()
def create_bulk_traitement(animaux, date_traitement, type_traitement, praticien="", observations="", medicaments=None):
    """Create individual Traitement docs for multiple animals"""
    import json
    if isinstance(animaux, str):
        animaux = json.loads(animaux)
    if isinstance(medicaments, str):
        medicaments = json.loads(medicaments)

    created = 0
    errors = []

    for animal in animaux:
        try:
            doc = frappe.get_doc({
                "doctype": "Traitement",
                "animal": animal,
                "date_traitement": date_traitement,
                "type_traitement": type_traitement,
                "praticien": praticien,
                "observations": observations,
                "medicaments": [
                    {
                        "medicament": m.get("medicament"),
                        "dose": m.get("dose"),
                        "unite_dose": m.get("unite_dose"),
                        "voie_administration": m.get("voie_administration")
                    }
                    for m in (medicaments or [])
                ] if type_traitement == "TRAITEMENT_MEDICAL" else []
            })
            doc.insert()
            created += 1
        except Exception as e:
            nom = frappe.db.get_value("Animal", animal, "nom_metier") or animal
            errors.append({"animal": nom, "error": str(e)})

    frappe.db.commit()
    return {"created": created, "errors": errors}
