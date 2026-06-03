# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_WAREHOUSE as WAREHOUSE


class Insemination(Document):
    def validate(self):
        self.validate_animal_eligible()
        self.validate_no_pending_ia()
        self.validate_date_ia()
        self.validate_resultat_transition()
        self.lock_identity_fields()
        self.set_lactation()
        self.set_numero_ia()

    def lock_identity_fields(self):
        """Prevent editing animal/taureau always. date_ia editable only when EN_ATTENTE."""
        if self.is_new() or self.flags.ignore_validate:
            return
        db_doc = self.get_doc_before_save()
        if not db_doc:
            return

        # animal and taureau: always locked
        always_locked = {"animal": "Animal", "taureau": "Taureau"}
        for field, label in always_locked.items():
            if str(self.get(field) or "") != str(db_doc.get(field) or ""):
                frappe.throw(
                    f"Le champ '{label}' ne peut pas être modifié après création. "
                    f"Supprimez cette insémination et créez-en une nouvelle."
                )

        # date_ia: editable only when EN_ATTENTE
        if str(self.date_ia or "") != str(db_doc.date_ia or ""):
            if db_doc.resultat != "EN_ATTENTE":
                frappe.throw(
                    "La date IA ne peut plus être modifiée une fois le résultat confirmé. "
                    "Supprimez cette insémination et créez-en une nouvelle."
                )

    def validate_resultat_transition(self):
        """Enforce one-way state transitions for resultat"""
        if self.is_new() or self.flags.ignore_validate:
            return
        if not self.has_value_changed("resultat"):
            return

        old = self.get_doc_before_save()
        if not old:
            return

        old_val = old.resultat
        new_val = self.resultat

        allowed = {
            "EN_ATTENTE": ["REUSSIE", "ECHOUEE"],
            "REUSSIE": ["ECHOUEE"],
            "ECHOUEE": [],
        }

        if new_val not in allowed.get(old_val, []):
            frappe.throw(
                f"Transition non autorisée: {old_val} → {new_val}. "
                f"Transitions possibles depuis {old_val}: {', '.join(allowed.get(old_val, [])) or 'aucune (état final)'}."
            )

        # REUSSIE → ECHOUEE: block if a Velage depends on this IA
        if old_val == "REUSSIE" and new_val == "ECHOUEE":
            velage = frappe.db.exists("Velage", {"insemination": self.name})
            if velage:
                frappe.throw(
                    f"Impossible de marquer cette IA comme échouée: un vêlage ({velage}) en dépend. "
                    f"Supprimez d'abord le vêlage."
                )
        
        
    
    def on_update(self):
        self.update_animal_on_resultat()
        self.update_lactation_count()
    
    def validate_animal_eligible(self):
        """Only VACHE/GENISSE can be inseminated, and not if already GESTANTE"""
        if self.animal:
            categorie, etat_gestation = frappe.db.get_value(
                "Animal", self.animal, ["categorie", "etat_gestation"]
            )
            if categorie not in ["VACHE", "GENISSE"]:
                frappe.throw("ERR-IA-01: Seules les vaches et génisses peuvent être inséminées.")
            if self.is_new() and etat_gestation == "GESTANTE":
                frappe.throw("ERR-IA-06: Cet animal est déjà gestant. Insémination impossible.")
    
    def validate_date_ia(self):
        """Date IA cannot be in the future and must respect chronology"""
        from frappe.utils import getdate, today
        if self.date_ia and getdate(self.date_ia) > getdate(today()):
            frappe.throw("ERR-IA-02: La date d'insémination ne peut pas être dans le futur.")

        # Chronology checks: run on new docs AND when date_ia is edited
        if not self.is_new() and not self.has_value_changed("date_ia"):
            return

        # IA must be after animal's birth date
        if self.animal and self.date_ia:
            date_naissance = frappe.db.get_value("Animal", self.animal, "date_naissance")
            if date_naissance and getdate(self.date_ia) <= getdate(date_naissance):
                frappe.throw("ERR-IA-03: La date d'insémination doit être après la date de naissance de l'animal.")

        # IA must be after last velage date for this animal
        if self.animal and self.date_ia:
            last_velage_date = frappe.db.get_value(
                "Velage", {"animal": self.animal}, "date_velage",
                order_by="date_velage desc"
            )
            if last_velage_date and getdate(self.date_ia) < getdate(last_velage_date):
                frappe.throw(
                    f"ERR-IA-04: La date d'insémination doit être après le dernier vêlage ({last_velage_date})."
                )


    def validate_no_pending_ia(self):
        """Prevent creating a new IA if one is already pending for this animal"""
        if self.animal:
            existing = frappe.db.exists("Insemination", {
                "animal": self.animal,
                "resultat": "EN_ATTENTE",
                "name": ["!=", self.name or ""]
            })
            if existing:
                frappe.throw(f"L'animal {self.animal} a déjà une insémination en attente ({existing}).")

    
    def set_lactation(self):
        """Auto-link to animal's active lactation (VACHE only, GENISSE has none)"""
        if self.animal:
            lactation = frappe.db.get_value("Lactation", {
                "animal": self.animal,
                "statut": "EN_COURS"
            }, "name")
            if lactation:
                self.lactation = lactation

    def set_numero_ia(self):
        """Auto-set numero_ia based on previous IAs"""
        if self.animal and self.is_new():
            if self.lactation:
                # VACHE: count IAs in this lactation
                count = frappe.db.count("Insemination", {
                    "lactation": self.lactation
                })
            else:
                # GENISSE: count all IAs for this animal
                count = frappe.db.count("Insemination", {
                    "animal": self.animal
                })
            self.numero_ia = count + 1

    def update_animal_on_resultat(self):
        """When IA result changes, update Animal and Alerts"""
        if not self.has_value_changed("resultat"):
            return

        if self.resultat == "REUSSIE" and self.animal:
            animal = frappe.get_doc("Animal", self.animal)
            animal.id_ia_fecondante = self.name
            periode_velage = get_config("periode_velage_jours", default=280)
            animal.date_velage_prevue = frappe.utils.add_days(self.date_ia, periode_velage)
            tarissement_window = get_config("tarissement_window_jours", default=60)
            animal.date_tarissement = frappe.utils.add_days(animal.date_velage_prevue, -tarissement_window)
            animal.etat_gestation = "GESTANTE"
            animal.flags.ignore_validate = True
            animal.save()

            display_name = animal.nom_metier or self.animal
            frappe.msgprint(
                f"Animal {display_name} mis à jour: Gestation confirmée, vêlage prévu le {animal.date_velage_prevue}"
            )

        elif self.resultat == "ECHOUEE" and self.animal:
            animal = frappe.get_doc("Animal", self.animal)
            if animal.id_ia_fecondante == self.name:
                animal.id_ia_fecondante = None
                animal.date_velage_prevue = None
                animal.date_tarissement = None
                animal.etat_gestation = "VIDE"
                animal.flags.ignore_validate = True
                animal.save()
                
                display_name = animal.nom_metier or self.animal
                frappe.msgprint(f"Animal {display_name}: IA échouée, gestation annulée.")
            
            # Close any open verification alerts for this IA
            open_alerts = frappe.get_all("Alerte", filters={
                "insemination": self.name,
                "statut": "NOUVELLE"
            }, pluck="name")
            for alert in open_alerts:
                frappe.db.set_value("Alerte", alert, {
                    "statut": "NON_CONFIRMEE",
                    "date_traitement": frappe.utils.today()
                })

            # Close tarissement/velage alerts (linked by animal, not IA)
            if animal.id_ia_fecondante is None:
                self._close_gestation_alerts()

    def update_lactation_count(self):
        """Update nb_inseminations on linked lactation"""
        if self.lactation:
            count = frappe.db.count("Insemination", {
                "lactation": self.lactation
            })
            frappe.db.set_value("Lactation", self.lactation, "nb_inseminations", count)
    
    def decrement_semence_stock(self):
        """Post a Material Issue (-1 paillette) for the picked Semence batch.

        Batch picker (post-Phase C, Bin-based):
          1. List all Semence records for (taureau, type_semence) FIFO oldest first
          2. Prefer batches with Bin.actual_qty > 0 (live stock)
          3. Fall back to the oldest batch if all are depleted — the real
             Insémination still gets recorded against the correct taureau even
             when the system's stock count is stale. The Bin will go negative
             (Item.allow_negative_stock=1), surfacing the discrepancy via the
             native reorder Material Request and via the soft msgprint below."""
        if getattr(self.flags, "skip_semence_decrement", False):
            return  # historical bulk import: do not write to the stock ledger
        if not self.taureau:
            return
        from hmd_agro.hmd_agro.utils.stock_utils import create_stock_movement
        # Check whether ANY batch exists for (taureau, type) — if not, the
        # Semence master is missing and the operator needs to add receptions
        # first. Separate from "all batches depleted" so the message is precise.
        any_batch = self._pick_semence_batch(prefer_with_stock=False)
        if not any_batch:
            frappe.msgprint(
                f"Aucune Semence enregistrée pour taureau={self.taureau}, "
                f"type={self.type_semence or 'tous'}. Enregistrer une "
                f"livraison Semence avant l'IA.",
                indicator="red", alert=True,
            )
            return
        s = self._pick_semence_batch(prefer_with_stock=True)
        if not s:
            # All batches exist but are at qty=0. v15 enforces batch-level
            # negative stock independent of Item.allow_negative_stock, so
            # refusing here is the only honest option. Operator must post
            # a Purchase Receipt before the IA can be recorded.
            frappe.msgprint(
                f"Stock épuisé sur TOUS les batches du taureau {self.taureau} "
                f"({self.type_semence or 'tous types'}). Enregistrer une "
                f"Purchase Receipt avant l'IA — ERPNext v15 n'autorise pas "
                f"un batch en négatif.",
                indicator="red", alert=True,
            )
            return
        if not s.item:
            frappe.msgprint(
                f"Semence {s.name} non liée à un Item ERPNext — écriture "
                f"stock ignorée. Lancer semence_migration.",
                indicator="orange", alert=True,
            )
            return
        create_stock_movement(s.item, 1, "Material Issue",
            WAREHOUSE,
            f"Insemination {self.name} (batch {s.name})",
            self.date_ia, uom="Paillette", batch_no=s.name)

    def _pick_semence_batch(self, prefer_with_stock):
        """Resolve which Semence record (= Batch) to charge. Returns a dict
        with name, item, qty (Batch.batch_qty) or None.

        Custom picker (not native Bundle auto-pick) because Insemination.semence
        must be resolved BEFORE the Stock Entry is created — native FIFO via
        Serial-and-Batch Bundle picks the batch DURING SE submit, too late to
        populate the form's semence link (which carries fournisseur, date_-
        reception and other metadata the user sees on the IA record).

        Modes:
          prefer_with_stock=True  (decrement):  FIFO oldest-first AMONG batches
                                                with batch_qty > 0; returns
                                                None if none qualify. Required
                                                because v15 ERPNext enforces
                                                batch-level negative stock
                                                independently of Item.allow_-
                                                negative_stock (see Serial-
                                                and-Batch Bundle validation) —
                                                a depleted batch can't be
                                                consumed even with the Item
                                                flag, so we refuse cleanly.
          prefer_with_stock=False (restore):    most-recent batch overall
                                                (adding stock — always succeeds).

        Per-batch qty source: `tabBatch.batch_qty` (auto-maintained by ERPNext
        when Stock Entries with `batch_no` submit). In v15 this is the canonical
        per-batch value — `tabBin` is per (item, warehouse) only, no batch_no
        column anymore (batch tracking moved to Serial-and-Batch Bundle)."""
        conditions = ["s.taureau = %s"]
        params = [self.taureau]
        if self.type_semence:
            conditions.append("s.type_semence = %s")
            params.append(self.type_semence)
        order = "ASC" if prefer_with_stock else "DESC"
        rows = frappe.db.sql(f"""
            SELECT s.name, s.item, COALESCE(bat.batch_qty, 0) AS qty
            FROM `tabSemence` s
            LEFT JOIN `tabBatch` bat ON bat.name = s.name
            WHERE {" AND ".join(conditions)}
            ORDER BY s.date_reception {order}
        """, params, as_dict=True)
        if not rows:
            return None
        if prefer_with_stock:
            for r in rows:
                if (r.qty or 0) > 0:
                    return r
            return None  # all batches depleted — caller surfaces error
        return rows[0]

    def close_chaleur_alerts(self):
        """Close any open chaleur alerts when IA is created"""
        open_alerts = frappe.get_all("Alerte", filters={
            "animal": self.animal,
            "type_alerte": ["in", ["CHALEUR_GENISSE", "CHALEUR_POST_VELAGE"]],
            "statut": ["in", ["NOUVELLE", "CONFIRMEE"]]
        }, pluck="name")
        for alert in open_alerts:
            frappe.db.set_value("Alerte", alert, {
                "statut": "TRAITEE",
                "date_traitement": frappe.utils.today()
            })

    def _close_gestation_alerts(self):
        """Close tarissement/velage alerts when animal is no longer gestante"""
        open_alerts = frappe.get_all("Alerte", filters={
            "animal": self.animal,
            "type_alerte": ["in", ["TARISSEMENT", "VELAGE_IMMINENT"]],
            "statut": "NOUVELLE"
        }, pluck="name")
        for alert in open_alerts:
            frappe.db.set_value("Alerte", alert, {
                "statut": "NON_CONFIRMEE",
                "date_traitement": frappe.utils.today()
            })

    def after_insert(self):
        self.decrement_semence_stock()
        self.close_chaleur_alerts()

    def on_trash(self):
        """Safe delete: block if Velage depends, restore animal state, restore semence"""
        # Block if a Velage depends on this IA
        velage = frappe.db.exists("Velage", {"insemination": self.name})
        if velage:
            frappe.throw(
                f"Impossible de supprimer cette insémination: un vêlage ({velage}) en dépend. "
                f"Supprimez d'abord le vêlage."
            )

        # If REUSSIE: restore animal to VIDE
        if self.resultat == "REUSSIE" and self.animal:
            animal = frappe.get_doc("Animal", self.animal)
            if animal.id_ia_fecondante == self.name:
                animal.id_ia_fecondante = None
                animal.date_velage_prevue = None
                animal.date_tarissement = None
                animal.etat_gestation = "VIDE"
                animal.flags.ignore_validate = True
                animal.save()
                self._close_gestation_alerts()

        # Delete all alerts linked to this IA (auto-generated, no reason to keep orphaned)
        linked_alerts = frappe.get_all("Alerte", filters={
            "insemination": self.name
        }, pluck="name")
        for alert in linked_alerts:
            frappe.delete_doc("Alerte", alert, force=True)

        # Restore semence stock
        self.restore_semence_stock()

        # Update lactation IA count
        if self.lactation:
            count = frappe.db.count("Insemination", {
                "lactation": self.lactation,
                "name": ["!=", self.name]
            })
            frappe.db.set_value("Lactation", self.lactation, "nb_inseminations", count)

    def restore_semence_stock(self):
        """Compensating Material Receipt (+1 paillette) into the most recent
        Semence batch on Insémination delete. The "most recent" pick is an
        approximation — FIFO is irreversible by design, but matching the
        latest batch is a reasonable proxy. Bin enforces no upper-bound check
        (no quantite_recue ceiling) — the receipt just adds to the batch."""
        if not self.taureau:
            return
        from hmd_agro.hmd_agro.utils.stock_utils import create_stock_movement
        s = self._pick_semence_batch(prefer_with_stock=False)
        if not s or not s.item:
            return
        create_stock_movement(s.item, 1, "Material Receipt",
            WAREHOUSE,
            f"Restore Insemination {self.name} delete (batch {s.name})",
            None, uom="Paillette", batch_no=s.name)