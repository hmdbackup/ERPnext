# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import re


def is_valid_identification_tn(value):
    """Check if identification_tn is valid: 10 digits"""
    if not value:
        return True
    return bool(re.match(r'^\d{10}$', value))

class Animal(Document):
    def validate(self):
        self.set_nom_metier()
        self.set_sexe_from_categorie()
        self.validate_mere_obligatoire()
        self.validate_dates()
        self.set_default_gestation()
        self.validate_identification_tn()
        self.validate_and_format_identification_fr()
        self.protect_status_fields()
        self.protect_reproduction_fields()

    def set_nom_metier(self):
        """N° travail: last 4 digits of identification_fr if it exists, otherwise of
        identification_tn. identification_fr may be the short farm work number (4 digits)
        or a full national ID — take its last 4 digits either way."""
        if self.identification_fr and re.match(r'^\d{1,10}$', self.identification_fr):
            self.nom_metier = self.identification_fr[-4:]
        elif self.identification_tn and re.match(r'^\d{10}$', self.identification_tn):
            self.nom_metier = self.identification_tn[-4:]
        else:
            self.nom_metier = ""

    def set_sexe_from_categorie(self):
        """CF-ANI-01 / CF-ANI-02: Auto-set sexe from categorie"""
        femelles = ["VACHE", "GENISSE", "VELLE"]
        males = ["VEAU", "TAURILLON"]

        if self.categorie in femelles:
            self.sexe = "F"
        elif self.categorie in males:
            self.sexe = "M"

    def validate_mere_obligatoire(self):
        """CF-ANI-03: Validate mother based on origin"""
        if not self.est_achat and not self.id_mere:
            frappe.throw(" La mère est obligatoire pour un animal né sur place.")

        if self.est_achat and not self.id_mere_externe:
            frappe.throw(" La mère externe est obligatoire pour un animal acheté.")

    def validate_dates(self):
        """Validate date coherence"""
        from frappe.utils import getdate
        if self.date_naissance and getdate(self.date_naissance) > getdate(frappe.utils.today()):
            frappe.throw("La date de naissance ne peut pas être dans le futur.")
        if self.est_achat and not self.date_entree:
            frappe.throw("La date d'entrée est obligatoire pour un animal acheté.")
        if self.est_achat and self.date_entree and self.date_naissance:
            if getdate(self.date_entree) < getdate(self.date_naissance):
                frappe.throw("La date d'entrée ne peut pas être avant la date de naissance.")
        if self.statut in ("VENDU", "MORT", "REFORME") and not self.date_sortie:
            frappe.throw("La date de sortie est obligatoire pour un animal vendu, mort ou réformé.")

    def validate_identification_tn(self):
        """ERR-01: Identification TN must be 10 digits"""
        if self.identification_tn and not is_valid_identification_tn(self.identification_tn):
            frappe.throw("L'identification TN doit être 10 chiffres (ex: 1234567890).")

    def set_default_gestation(self):
        """Default etat_gestation = VIDE for females"""
        if self.sexe == "F" and not self.etat_gestation:
            self.etat_gestation = "VIDE"
    
    def validate_and_format_identification_fr(self):
        """French ID: digits only, 1 to 10 (the farm records the short work number, not the
        full 10-digit national ID, so do not force 10 digits)."""
        if self.identification_fr:
            if not re.match(r'^\d{1,10}$', self.identification_fr):
                frappe.throw("L'identification FR doit être numérique (1 à 10 chiffres).")

    def protect_status_fields(self):
        """Prevent manual changes to etat_gestation and etat_lactation"""
        if self.is_new() or self.flags.ignore_validate:
            return
        db_doc = self.get_doc_before_save()
        if not db_doc:
            return
        old_gest = db_doc.etat_gestation or ""
        new_gest = self.etat_gestation or ""
        # Allow default initialization (empty → VIDE) but block other manual changes
        if new_gest != old_gest and not (old_gest == "" and new_gest == "VIDE"):
            frappe.throw("L'état de gestation est géré automatiquement par Insémination et Vêlage.")
        if (self.etat_lactation or "") != (db_doc.etat_lactation or ""):
            frappe.throw("L'état de lactation est géré automatiquement par Lactation.")

    def protect_reproduction_fields(self):
        if self.is_new() or self.flags.ignore_validate:
            return
        db_doc = self.get_doc_before_save()
        if not db_doc:
            return
        protected = [
            "id_ia_fecondante",
            "date_velage_prevue",
            "date_premier_velage",
            "date_tarissement",
            "id_velage_naissance",
            "attente_lait_active",
            "date_fin_attente_lait"
        ]
        for field in protected:
            new_val = str(self.get(field) or "")
            old_val = str(db_doc.get(field) or "")
            if new_val != old_val:
                frappe.throw(
                    f"Le champ '{self.meta.get_field(field).label}' ne peut être modifié manuellement."
                )
    
    def before_rename(self, old_name, new_name, merge=False):
        """Validate new name format on rename"""
        if not re.match(r'^\d{10}$', new_name):
            frappe.throw("L'identification TN doit être 10 chiffres (ex: 1234567890).")

    def after_rename(self, old_name, new_name, merge=False):
        """Update nom_metier after document is renamed"""
        # Check if animal has identification_fr — use that for nom_metier
        id_fr = frappe.db.get_value("Animal", new_name, "identification_fr")
        if id_fr and re.match(r'^\d{1,10}$', id_fr):
            nom_metier = id_fr[-4:]
        elif re.match(r'^\d{10}$', new_name):
            nom_metier = new_name[-4:]
        else:
            nom_metier = ""
        
        frappe.db.set_value("Animal", new_name, "nom_metier", nom_metier, update_modified=False)


    
    def before_save(self):
        pass

    def on_update(self):
        self._close_active_records_on_exit()
        self._update_lot_counts()
        self._track_lot_change()

    def _track_lot_change(self):
        """Audit log: insert an Allotement History row whenever id_lot changes.
        Captures all sources — manual edits, bulk updates, imports, API calls."""
        if not self.has_value_changed("id_lot"):
            return
        prev = self.get_doc_before_save()
        from_lot = prev.id_lot if prev else None
        if (from_lot or "") == (self.id_lot or ""):
            return
        frappe.get_doc({
            "doctype": "Allotement History",
            "animal": self.name,
            "from_lot": from_lot or None,
            "to_lot": self.id_lot or None,
            "moved_by": frappe.session.user,
            "source": getattr(self.flags, "lot_change_source", "MANUAL"),
        }).insert(ignore_permissions=True)

    def on_trash(self):
        self._update_lot_counts(is_delete=True)

    def _close_active_records_on_exit(self):
        """RG04: Auto-close all active records when animal leaves (VENDU/MORT/REFORME)"""
        if not self.has_value_changed("statut"):
            return
        if self.statut not in ("VENDU", "MORT", "REFORME"):
            return

        from frappe.utils import today

        # 1. Close EN_COURS lactation → INTERROMPUE
        lactation = frappe.db.get_value("Lactation", {
            "animal": self.name,
            "statut": "EN_COURS"
        }, "name")
        if lactation:
            # Calculate jours_lactation before closing
            date_debut = frappe.db.get_value("Lactation", lactation, "date_debut")
            jours = 0
            if date_debut:
                from frappe.utils import date_diff
                jours = date_diff(today(), date_debut)
            frappe.db.set_value("Lactation", lactation, {
                "statut": "INTERROMPUE",
                "date_tarissement": today(),
                "jours_lactation": jours
            })
            frappe.db.set_value("Animal", self.name, "etat_lactation", "")

        # 2. Close EN_ATTENTE insemination → ECHOUEE (triggers update_animal_on_resultat which resets gestation)
        pending_ia = frappe.db.get_value("Insemination", {
            "animal": self.name,
            "resultat": "EN_ATTENTE"
        }, "name")
        if pending_ia:
            ia_doc = frappe.get_doc("Insemination", pending_ia)
            ia_doc.resultat = "ECHOUEE"
            ia_doc.flags.ignore_validate = True
            ia_doc.save()

        # 3. If GESTANTE but no pending IA handled above, reset gestation directly
        if not pending_ia and self.etat_gestation == "GESTANTE":
            frappe.db.set_value("Animal", self.name, {
                "etat_gestation": "VIDE",
                "id_ia_fecondante": None,
                "date_velage_prevue": None,
                "date_tarissement": None,
            })

        # 4. Close all open alertes for this animal
        open_alerts = frappe.get_all("Alerte", filters={
            "animal": self.name,
            "statut": ["in", ["NOUVELLE", "CONFIRMEE", "GESTANTE_PROBABLE"]]
        }, pluck="name")
        for alert in open_alerts:
            frappe.db.set_value("Alerte", alert, {
                "statut": "NON_CONFIRMEE",
                "date_traitement": today()
            })

    def _update_lot_counts(self, is_delete=False):
        """Update nb_animaux on current and previous lot"""
        from hmd_agro.hmd_agro.doctype.lot.lot import update_lot_animal_count

        # On delete, exclude this animal from the count (it's still in DB during on_trash)
        exclude = self.name if is_delete else None

        # Update current lot
        if self.id_lot:
            update_lot_animal_count(self.id_lot, exclude_animal=exclude)

        # If lot changed, also update the old lot
        if not is_delete:
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.id_lot and old_doc.id_lot != self.id_lot:
                update_lot_animal_count(old_doc.id_lot)



@frappe.whitelist()
def check_active_records(animal):
    """Check if animal has any active records that would be affected by status change"""
    has_lactation = frappe.db.exists("Lactation", {"animal": animal, "statut": "EN_COURS"})
    has_ia = frappe.db.exists("Insemination", {"animal": animal, "resultat": "EN_ATTENTE"})
    etat_gestation = frappe.db.get_value("Animal", animal, "etat_gestation")
    is_gestante = etat_gestation == "GESTANTE"
    nb_alertes = frappe.db.count("Alerte", {
        "animal": animal,
        "statut": ["in", ["NOUVELLE", "CONFIRMEE", "GESTANTE_PROBABLE"]]
    })

    has_active = bool(has_lactation or has_ia or is_gestante or nb_alertes > 0)

    return {
        "has_active": has_active,
        "lactation": bool(has_lactation),
        "insemination": bool(has_ia),
        "gestation": is_gestante,
        "alertes": nb_alertes
    }


@frappe.whitelist()
def get_reproduction_dashboard(animal):
    """Get all reproduction data for the animal dashboard"""
    
    # Current lactation
    current_lactation = frappe.db.get_value("Lactation", {
        "animal": animal,
        "statut": "EN_COURS"
    }, ["name", "numero_lactation", "date_debut", "jours_lactation", "nb_inseminations"], as_dict=True)

    # Live DIM calculation for current lactation
    if current_lactation and current_lactation.date_debut:
        from frappe.utils import date_diff, today as today_fn
        current_lactation.jours_lactation = date_diff(today_fn(), current_lactation.date_debut)

    # All lactations summary with production
    lactations = frappe.db.get_all("Lactation",
        filters={"animal": animal},
        fields=["name", "numero_lactation", "date_debut", "date_tarissement", "statut",
                "nb_inseminations", "jours_lactation", "production_totale", "lactation_305j"],
        order_by="numero_lactation desc"
    )

    # Live DIM for active lactations + velage dates for IVV
    velages = frappe.db.get_all("Velage",
        filters={"animal": animal},
        fields=["date_velage"],
        order_by="date_velage asc"
    )
    velage_dates = [v.date_velage for v in velages]

    for lac in lactations:
        if lac.statut == "EN_COURS" and lac.date_debut:
            from frappe.utils import date_diff, today as today_fn
            lac.jours_lactation = date_diff(today_fn(), lac.date_debut)

    # Calculate IVV for each lactation (based on velage dates)
    ivv_list = []
    for i in range(1, len(velage_dates)):
        from frappe.utils import date_diff
        ivv = date_diff(velage_dates[i], velage_dates[i - 1])
        ivv_list.append(ivv)

    # Age au premier velage
    animal_data = frappe.db.get_value("Animal", animal,
        ["date_naissance", "date_premier_velage"], as_dict=True)
    age_premier_velage = None
    if animal_data and animal_data.date_naissance and animal_data.date_premier_velage:
        from frappe.utils import date_diff
        age_premier_velage = round(date_diff(animal_data.date_premier_velage, animal_data.date_naissance) / 30, 1)

    # Production lifetime
    production_totale_vie = sum(lac.production_totale or 0 for lac in lactations)

    # Pending insemination
    pending_ia = frappe.db.get_value("Insemination", {
        "animal": animal,
        "resultat": "EN_ATTENTE"
    }, ["name", "date_ia", "taureau"], as_dict=True)
    
    # Last insemination result
    last_ia = frappe.db.get_value("Insemination", {
        "animal": animal,
        "resultat": ["!=", "EN_ATTENTE"]
    }, ["name", "date_ia", "resultat", "taureau"], as_dict=True, order_by="creation desc")
    
    # Total inseminations
    total_ia = frappe.db.count("Insemination", {"animal": animal})
    
    return {
        "current_lactation": current_lactation,
        "lactations": lactations,
        "pending_ia": pending_ia,
        "last_ia": last_ia,
        "total_ia": total_ia,
        "ivv_list": ivv_list,
        "age_premier_velage": age_premier_velage,
        "production_totale_vie": round(production_totale_vie, 1)
    }


@frappe.whitelist()
def get_multi_lactation_chart_data(animal):
    """Get traite data grouped by DIM for each lactation, for overlay chart"""
    from frappe.utils import date_diff

    lactations = frappe.db.get_all("Lactation",
        filters={"animal": animal},
        fields=["name", "numero_lactation", "date_debut"],
        order_by="numero_lactation asc"
    )

    datasets = []
    for lac in lactations:
        if not lac.date_debut:
            datasets.append({"name": f"L{lac.numero_lactation}", "values": {}})
            continue

        traites = frappe.db.get_all("Traite",
            filters={"lactation": lac.name},
            fields=["date_traite", "quantite_litres"],
            order_by="date_traite asc"
        )
        # Aggregate by DIM (date_traite - date_debut), sum all sessions per day
        day_map = {}
        for t in traites:
            if t.date_traite:
                dim = date_diff(t.date_traite, lac.date_debut)
                day_map[dim] = day_map.get(dim, 0) + (t.quantite_litres or 0)

        datasets.append({
            "name": f"L{lac.numero_lactation}",
            "values": day_map
        })

    return datasets