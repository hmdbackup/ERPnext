# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt
# i can edit
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today

from hmd_agro.hmd_agro.utils.config import get_config


class Velage(Document):
    def validate(self):
        self.lock_identity_fields()
        self.validate_animal_gestante()
        self.validate_date_velage()
        self.validate_veaux()
        self.auto_link_insemination()
        self.clear_veau2_if_single()

    def lock_identity_fields(self):
        """Prevent editing animal and date_velage after creation"""
        if self.is_new() or self.flags.ignore_validate:
            return
        db_doc = self.get_doc_before_save()
        if not db_doc:
            return
        locked = {"animal": "Animal (mère)", "date_velage": "Date"}
        for field, label in locked.items():
            if str(self.get(field) or "") != str(db_doc.get(field) or ""):
                frappe.throw(
                    f"Le champ '{label}' ne peut pas être modifié après création. "
                    f"Supprimez ce vêlage et créez-en un nouveau."
                )

    def after_insert(self):
        self.create_calves()
        self.create_lactation()
        self.update_mother()
        self.close_open_alerts()

    def validate_animal_gestante(self):
        """CF-VEL-01 & CF-VEL-02: Only check gestation on creation"""
        if self.animal:
            categorie, sexe, etat = frappe.db.get_value(
                "Animal", self.animal, ["categorie", "sexe", "etat_gestation"]
            )
            if sexe != "F" or categorie not in ["VACHE", "GENISSE"]:
                frappe.throw("ERR-VEL-01: Seules les vaches et génisses peuvent vêler.")
            if self.is_new() and etat != "GESTANTE":
                frappe.throw("ERR-VEL-02: L'animal n'est pas gestante.")

    def validate_date_velage(self):
        if self.date_velage and getdate(self.date_velage) > getdate(today()):
            frappe.throw("ERR-VEL-03: La date de vêlage ne peut pas être dans le futur.")

        if not self.is_new():
            return

        # Velage must be after animal's birth date
        if self.animal and self.date_velage:
            date_naissance = frappe.db.get_value("Animal", self.animal, "date_naissance")
            if date_naissance and getdate(self.date_velage) <= getdate(date_naissance):
                frappe.throw("ERR-VEL-04: La date de vêlage doit être après la date de naissance de l'animal.")

        # Velage must be after linked insemination date (by at least 250 days)
        if self.insemination and self.date_velage:
            date_ia = frappe.db.get_value("Insemination", self.insemination, "date_ia")
            if date_ia:
                from frappe.utils import date_diff
                jours = date_diff(getdate(self.date_velage), getdate(date_ia))
                if jours < 250:
                    frappe.throw(
                        f"ERR-VEL-05: La date de vêlage doit être au moins 250 jours après l'insémination "
                        f"({date_ia}). Écart actuel: {jours} jours."
                    )

    def validate_veaux(self):
        """CF-VEL-06/07: Validate calf data"""
        if not self.sexe_veau1:
            frappe.throw("ERR-VEL-06: Le sexe du veau 1 est obligatoire.")

        if self.nombre_veaux == "2" and not self.sexe_veau2:
            frappe.throw("ERR-VEL-07: Le sexe du veau 2 est obligatoire pour des jumeaux.")

        # Validate identification format (reuses Animal's validation)
        from hmd_agro.hmd_agro.doctype.animal.animal import is_valid_identification_tn
        for field, label in [("identification_veau1", "Veau 1"), ("identification_veau2", "Veau 2")]:
            val = self.get(field)
            if val and not is_valid_identification_tn(val):
                frappe.throw(
                    f"Identification TN du {label}: format invalide. "
                    f"Doit être 10 chiffres (ex: 1234567890)."
                )

    def clear_veau2_if_single(self):
        """CF-VEL-05: Clear veau2 fields if single birth"""
        if self.nombre_veaux == "1":
            self.sexe_veau2 = ""
            self.vivant_veau2 = 0
            self.poids_veau2 = None
            self.id_veau2 = None

    def auto_link_insemination(self):
        """CF-VEL-03: Auto-fill IA fecondante from animal"""
        if self.animal and not self.insemination:
            ia = frappe.db.get_value("Animal", self.animal, "id_ia_fecondante")
            if ia:
                self.insemination = ia

    def create_calves(self):
        """RG17: Create Animal for each live calf"""
        mother = frappe.get_doc("Animal", self.animal)

        # Get father from IA
        pere = None
        if self.insemination:
            pere = frappe.db.get_value("Insemination", self.insemination, "taureau")

        # Veau 1
        if self.vivant_veau1:
            veau1 = self._create_calf(
                sexe=self.sexe_veau1,
                identification=self.identification_veau1,
                poids=self.poids_veau1,
                mother=mother,
                pere=pere,
                num=1
            )
            self.db_set("id_veau1", veau1.name)

        # Veau 2
        if self.nombre_veaux == "2" and self.vivant_veau2:
            veau2 = self._create_calf(
                sexe=self.sexe_veau2,
                identification=self.identification_veau2,
                poids=self.poids_veau2,
                mother=mother,
                pere=pere,
                num=2
            )
            self.db_set("id_veau2", veau2.name)

    def _create_calf(self, sexe, identification, poids, mother, pere, num):
        """Create a single calf Animal + optional Pesee"""
        # Generate ID if not provided — find highest numeric ID and add 1
        if not identification:
            max_id = frappe.db.sql(
                """SELECT MAX(CAST(identification_tn AS UNSIGNED)) as max_id
                   FROM `tabAnimal`
                   WHERE identification_tn REGEXP '^[0-9]{10}$'""",
                as_dict=True
            )
            last_num = int(max_id[0].max_id or 0) if max_id and max_id[0].max_id else 0
            identification = str(last_num + 1).zfill(10)

        categorie = "VEAU" if sexe == "M" else "VELLE"

        calf = frappe.get_doc({
            "doctype": "Animal",
            "identification_tn": identification,
            "categorie": categorie,
            "sexe": sexe,
            "race": mother.race,
            "date_naissance": self.date_velage,
            "id_mere": mother.name,
            "id_pere": pere,
            "id_lot": "Individuel",
            "statut": "ACTIF",
            "est_achat": 0,
            "id_velage_naissance": self.name
        })
        calf.flags.ignore_validate = True
        calf.insert(ignore_permissions=True)

        # RG18: Create Pesee NAISSANCE if weight provided
        if poids:
            pesee = frappe.get_doc({
                "doctype": "Pesee",
                "animal": calf.name,
                "date_pesee": self.date_velage,
                "poids_kg": poids,
                "type_pesee": "NAISSANCE"
            })
            pesee.insert(ignore_permissions=True)

        frappe.msgprint(f"Veau {num} créé: {calf.name} ({categorie})")
        return calf

    def create_lactation(self):
        """RG07: Create new lactation EN_COURS for mother.
        Auto-close any existing EN_COURS lactation as TARIE first."""
        # Close previous lactation if still EN_COURS (farmer forgot to tarie)
        prev_lactation = frappe.db.get_value("Lactation", {
            "animal": self.animal,
            "statut": "EN_COURS"
        }, "name")
        if prev_lactation:
            lac = frappe.get_doc("Lactation", prev_lactation)
            lac.statut = "TARIE"
            lac.date_tarissement = self.date_velage
            # Calculate jours_lactation before saving (since ignore_validate skips it)
            if lac.date_debut:
                from frappe.utils import date_diff
                lac.jours_lactation = date_diff(getdate(self.date_velage), getdate(lac.date_debut))
            lac.flags.ignore_validate = True
            lac.save()
            frappe.msgprint(f"Lactation précédente #{lac.numero_lactation} clôturée automatiquement (TARIE).")

        count = frappe.db.count("Lactation", {"animal": self.animal})

        lactation = frappe.get_doc({
            "doctype": "Lactation",
            "animal": self.animal,
            "velage_debut": self.name,
            "numero_lactation": count + 1,
            "date_debut": self.date_velage,
            "statut": "EN_COURS"
        })
        lactation.flags.ignore_validate = True
        lactation.insert(ignore_permissions=True)

        self.db_set("lactation", lactation.name)
        frappe.msgprint(f"Lactation #{count + 1} créée pour {self.animal}")

    def update_mother(self):
        """RG15 + RG16: Reset mother gestation, GENISSE→VACHE"""
        animal = frappe.get_doc("Animal", self.animal)

        # RG15: Reset gestation
        animal.etat_gestation = "VIDE"
        animal.id_ia_fecondante = None
        animal.date_velage_prevue = None
        animal.date_tarissement = None

        # RG16: GENISSE becomes VACHE
        if animal.categorie == "GENISSE":
            animal.categorie = "VACHE"
            animal.date_premier_velage = self.date_velage

        animal.flags.ignore_validate = True
        animal.save()

        display_name = animal.nom_metier or self.animal
        frappe.msgprint(f"Animal {display_name}: gestation terminée, statut VIDE.")

    def close_open_alerts(self):
        """Close any remaining open alerts for this animal after velage"""
        open_alerts = frappe.get_all("Alerte", filters={
            "animal": self.animal,
            "statut": ["in", ["NOUVELLE", "CONFIRMEE"]]
        }, pluck="name")

        for alert in open_alerts:
            frappe.db.set_value("Alerte", alert, {
                "statut": "TRAITEE",
                "date_traitement": frappe.utils.today()
            })

    def on_trash(self):
        """Safe delete: check calves have no downstream records, then reverse everything"""
        self._check_calves_safe_to_delete()
        self._check_lactation_safe_to_delete()
        self._delete_calves()
        self._delete_lactation()
        self._restore_mother()

    def _check_calves_safe_to_delete(self):
        """Block deletion if calves have downstream records beyond birth pesée"""
        for veau_field in ["id_veau1", "id_veau2"]:
            veau = self.get(veau_field)
            if not veau:
                continue

            # Check for inseminations on this calf
            ia = frappe.db.exists("Insemination", {"animal": veau})
            if ia:
                frappe.throw(
                    f"Impossible de supprimer ce vêlage: le veau {veau} a une insémination ({ia}). "
                    f"Supprimez d'abord les enregistrements liés au veau."
                )

            # Check for pesées beyond NAISSANCE
            non_birth_pesee = frappe.db.exists("Pesee", {
                "animal": veau,
                "type_pesee": ["!=", "NAISSANCE"]
            })
            if non_birth_pesee:
                frappe.throw(
                    f"Impossible de supprimer ce vêlage: le veau {veau} a des pesées enregistrées. "
                    f"Supprimez d'abord les pesées du veau."
                )

            # Check for etat corporel
            ec = frappe.db.exists("Etat Corporel", {"animal": veau})
            if ec:
                frappe.throw(
                    f"Impossible de supprimer ce vêlage: le veau {veau} a un état corporel enregistré. "
                    f"Supprimez d'abord les enregistrements liés au veau."
                )

    def _check_lactation_safe_to_delete(self):
        """Block if lactation has traites"""
        if not self.lactation:
            return
        traite = frappe.db.exists("Traite", {"lactation": self.lactation})
        if traite:
            frappe.throw(
                f"Impossible de supprimer ce vêlage: la lactation {self.lactation} a des traites enregistrées. "
                f"Supprimez d'abord les traites."
            )

    def _delete_calves(self):
        """Delete created calves and their birth pesées"""
        for veau_field in ["id_veau1", "id_veau2"]:
            veau = self.get(veau_field)
            if not veau:
                continue

            # Delete birth pesée
            birth_pesees = frappe.get_all("Pesee", filters={
                "animal": veau, "type_pesee": "NAISSANCE"
            }, pluck="name")
            for p in birth_pesees:
                frappe.delete_doc("Pesee", p, ignore_permissions=True, force=True)

            # Delete calf
            frappe.delete_doc("Animal", veau, ignore_permissions=True, force=True)

    def _delete_lactation(self):
        """Delete the lactation created by this velage"""
        if not self.lactation:
            return
        lac = frappe.get_doc("Lactation", self.lactation)
        # Reset animal etat_lactation before deleting
        if lac.animal:
            frappe.db.set_value("Animal", lac.animal, "etat_lactation", "")
        frappe.delete_doc("Lactation", self.lactation, ignore_permissions=True, force=True)

    def _restore_mother(self):
        """Restore mother to GESTANTE state with IA fields from linked insemination"""
        if not self.animal:
            return
        animal = frappe.get_doc("Animal", self.animal)

        # Restore gestation from linked IA
        if self.insemination:
            ia = frappe.db.get_value("Insemination", self.insemination, "date_ia")
            if ia:
                tarissement_window = get_config("tarissement_window_jours", default=60)
                animal.id_ia_fecondante = self.insemination
                animal.date_velage_prevue = frappe.utils.add_days(ia, 280)
                animal.date_tarissement = frappe.utils.add_days(animal.date_velage_prevue, -tarissement_window)
                animal.etat_gestation = "GESTANTE"
        else:
            # No linked IA — just set back to GESTANTE
            animal.etat_gestation = "GESTANTE"

        # Reverse GENISSE→VACHE if this was the first velage
        if animal.date_premier_velage and str(animal.date_premier_velage) == str(self.date_velage):
            # Check if there are other velages for this animal
            other_velage = frappe.db.exists("Velage", {
                "animal": self.animal,
                "name": ["!=", self.name]
            })
            if not other_velage:
                animal.categorie = "GENISSE"
                animal.date_premier_velage = None

        animal.flags.ignore_validate = True
        animal.save()

        display_name = animal.nom_metier or self.animal
        frappe.msgprint(f"Animal {display_name}: vêlage annulé, état restauré à GESTANTE.")