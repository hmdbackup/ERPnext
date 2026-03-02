# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import re

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
        """Set nom_metier as last 4 digits of identification_tn"""
        if self.identification_tn and re.match(r'^\d{10}$', self.identification_tn):
            self.nom_metier = self.identification_tn[-4:]
        elif self.identification_tn and re.match(r'^TEMP-\d{2}$', self.identification_tn, re.IGNORECASE):
            self.nom_metier = self.identification_tn
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
        if self.est_achat and self.date_entree and self.date_naissance:
            if getdate(self.date_entree) < getdate(self.date_naissance):
                frappe.throw("La date d'entrée ne peut pas être avant la date de naissance.")

    def validate_identification_tn(self):
        """ERR-01: Identification TN must be TEMP-XX or 10 digits"""
        if self.identification_tn:
            is_temp = re.match(r'^TEMP-\d{2}$', self.identification_tn, re.IGNORECASE)
            is_10_digits = re.match(r'^\d{10}$', self.identification_tn)
            
            if not is_temp and not is_10_digits:
                frappe.throw("L'identification TN doit être au format TEMP-XX (ex: TEMP-01) ou 10 chiffres (ex: 1234567890).")

    def set_default_gestation(self):
        """Default etat_gestation = VIDE for females"""
        if self.sexe == "F" and not self.etat_gestation:
            self.etat_gestation = "VIDE"
    
    def validate_and_format_identification_fr(self):
        """Validate and format French ID: FR + 10 digits → FR 12 3456 7890"""
        if self.identification_fr:
            # Remove spaces for validation
            clean_id = self.identification_fr.replace(" ", "").upper()
            
            if not re.match(r'^FR\d{10}$', clean_id):
                frappe.throw("L'identification FR doit être au format FR + 10 chiffres (ex: FR1234567890).")
            
            # Format: FR 12 3456 7890
            self.identification_fr = f"{clean_id[:2]} {clean_id[2:4]} {clean_id[4:8]} {clean_id[8:12]}"

    def protect_status_fields(self):
        """Prevent manual changes to etat_gestation and etat_lactation"""
        if self.is_new() or self.flags.ignore_validate:
            return
        db_doc = self.get_doc_before_save()
        if not db_doc:
            return
        if self.etat_gestation != db_doc.etat_gestation:
            frappe.throw("L'état de gestation est géré automatiquement par Insémination et Vêlage.")
        if self.etat_lactation != db_doc.etat_lactation:
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
            "id_velage_naissance"
        ]
        for field in protected:
            if self.get(field) != db_doc.get(field):
                frappe.throw(
                    f"Le champ '{self.meta.get_field(field).label}' ne peut être modifié manuellement."
                )
    
    def before_rename(self, old_name, new_name, merge=False):
        """Validate new name format on rename"""
        is_temp = re.match(r'^TEMP-\d{2}$', new_name, re.IGNORECASE)
        is_10_digits = re.match(r'^\d{10}$', new_name)
        
        if not is_temp and not is_10_digits:
            frappe.throw("L'identification TN doit être au format TEMP-XX (ex: TEMP-01) ou 10 chiffres (ex: 1234567890).")

    def after_rename(self, old_name, new_name, merge=False):
        """Update nom_metier after document is renamed"""
        if re.match(r'^\d{10}$', new_name):
            nom_metier = new_name[-4:]
        elif re.match(r'^TEMP-\d{2}$', new_name, re.IGNORECASE):
            nom_metier = new_name
        else:
            nom_metier = ""
        
        frappe.db.set_value("Animal", new_name, "nom_metier", nom_metier, update_modified=False)


    
    def before_save(self):
        pass

    def on_update(self):
        self._update_lot_counts()

    def on_trash(self):
        self._update_lot_counts(is_delete=True)

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
def get_reproduction_dashboard(animal):
    """Get all reproduction data for the animal dashboard"""
    
    # Current lactation
    current_lactation = frappe.db.get_value("Lactation", {
        "animal": animal,
        "statut": "EN_COURS"
    }, ["name", "numero_lactation", "date_debut", "jours_lactation", "nb_inseminations"], as_dict=True)
    
    # All lactations summary
    lactations = frappe.db.get_all("Lactation", 
        filters={"animal": animal},
        fields=["name", "numero_lactation", "date_debut", "date_fin", "statut", "nb_inseminations", "jours_lactation"],
        order_by="numero_lactation desc"
    )
    
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
        "total_ia": total_ia
    }