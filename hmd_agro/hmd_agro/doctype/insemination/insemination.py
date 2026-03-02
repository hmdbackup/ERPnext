# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


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
        """Only VACHE/GENISSE can be inseminated"""
        if self.animal:
            categorie = frappe.db.get_value("Animal", self.animal, "categorie")
            if categorie not in ["VACHE", "GENISSE"]:
                frappe.throw("ERR-IA-01: Seules les vaches et génisses peuvent être inséminées.")
    
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
            animal.date_velage_prevue = frappe.utils.add_days(self.date_ia, 280)
            animal.date_tarissement = frappe.utils.add_days(animal.date_velage_prevue, -60)
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

    def update_lactation_count(self):
        """Update nb_inseminations on linked lactation"""
        if self.lactation:
            count = frappe.db.count("Insemination", {
                "lactation": self.lactation
            })
            frappe.db.set_value("Lactation", self.lactation, "nb_inseminations", count)
    
    def decrement_semence_stock(self):
        """Decrement semence stock for the taureau and type used"""
        if self.taureau:
            filters = {"taureau": self.taureau, "quantite_restante": [">", 0]}
            if self.type_semence:
                filters["type_semence"] = self.type_semence
            semence = frappe.get_list("Semence",
                filters=filters,
                fields=["name", "quantite_restante"],
                order_by="date_reception asc",
                limit=1
            )
            if semence:
                frappe.db.set_value("Semence", semence[0].name,
                    "quantite_restante", semence[0].quantite_restante - 1)
            else:
                frappe.msgprint(
                    f"Attention: Aucun stock de semence disponible pour le taureau {self.taureau}.",
                    indicator="orange",
                    alert=True
                )

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
        """Restore +1 dose to the most recent semence batch for this taureau and type"""
        if self.taureau:
            filters = {"taureau": self.taureau}
            if self.type_semence:
                filters["type_semence"] = self.type_semence
            semence = frappe.get_list("Semence",
                filters=filters,
                fields=["name", "quantite_restante", "quantite_recue"],
                order_by="date_reception desc",
                limit=1
            )
            if semence and semence[0].quantite_restante < semence[0].quantite_recue:
                frappe.db.set_value("Semence", semence[0].name,
                    "quantite_restante", semence[0].quantite_restante + 1)