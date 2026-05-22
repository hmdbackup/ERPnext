# Copyright (c) 2026, Mouhib Bouzamita and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days, getdate


class TestVelage(FrappeTestCase):
    """Comprehensive tests for Velage doctype validations and side effects."""

    def setUp(self):
        # --- Batiment ---
        if not frappe.db.exists("Batiment", "Test Batiment VEL"):
            frappe.get_doc({
                "doctype": "Batiment",
                "nom_batiment": "Test Batiment VEL",
                "type_batiment": "ELEVAGE",
            }).insert(ignore_permissions=True)

        # --- Lot (with all required fields) ---
        if not frappe.db.exists("Lot", "Test Lot VEL"):
            frappe.get_doc({
                "doctype": "Lot",
                "nom": "Test Lot VEL",
                "batiment": "Test Batiment VEL",
                "superficie_m2": 100.0,
                "capacite_optimale": 20,
                "capacite_maximale": 30,
            }).insert(ignore_permissions=True)

        # --- Lot Individuel (needed for calves) ---
        if not frappe.db.exists("Lot", "Individuel"):
            frappe.get_doc({
                "doctype": "Lot",
                "nom": "Individuel",
                "batiment": "Test Batiment VEL",
                "superficie_m2": 50.0,
                "capacite_optimale": 10,
                "capacite_maximale": 20,
            }).insert(ignore_permissions=True)

        # --- Taureau ---
        if not frappe.db.exists("Taureau", "Test Taureau VEL"):
            frappe.get_doc({
                "doctype": "Taureau",
                "nom_taureau": "Test Taureau VEL",
                "code_taureau": "TVEL001",
                "race": "Holstein",
            }).insert(ignore_permissions=True)

        # --- Mere externe (no fields) ---
        self.mere_externe = None
        meres = frappe.get_all("Mere externe", limit=1)
        if meres:
            self.mere_externe = meres[0].name
        else:
            doc = frappe.get_doc({"doctype": "Mere externe"}).insert(ignore_permissions=True)
            self.mere_externe = doc.name

        # --- Semence ---
        existing_semence = frappe.get_all("Semence", filters={
            "taureau": "Test Taureau VEL",
            "type_semence": "CONVENTIONNELLE",
        }, limit=1)
        # ST5-14 (Phase C): legacy stock fields removed in ST5-12.
        if existing_semence:
            self.semence = existing_semence[0].name
        else:
            sem = frappe.get_doc({
                "doctype": "Semence",
                "taureau": "Test Taureau VEL",
                "type_semence": "CONVENTIONNELLE",
                "date_reception": add_days(today(), -30),
            }).insert(ignore_permissions=True)
            self.semence = sem.name

        # --- Animal (VACHE, ACTIF) — start as VIDE, will become GESTANTE via IA ---
        if not frappe.db.exists("Animal", "8200000001"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8200000001",
                "categorie": "VACHE",
                "sexe": "F",
                "race": "Holstein",
                "date_naissance": "2020-01-01",
                "id_lot": "Test Lot VEL",
                "id_pere": "Test Taureau VEL",
                "date_entree": add_days(today(), -500), "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
                "etat_gestation": "VIDE",
            }).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Animal", "8200000001", {
                "etat_gestation": "VIDE",
                "id_ia_fecondante": None,
                "date_velage_prevue": None,
                "date_tarissement": None,
                "categorie": "VACHE",
                "statut": "ACTIF",
                "etat_lactation": "",
                "date_premier_velage": None,
            })

        # --- Lactation EN_COURS for the animal ---
        existing_lac = frappe.db.exists("Lactation", {
            "animal": "8200000001",
            "statut": "EN_COURS",
        })
        if existing_lac:
            self.lactation = existing_lac
        else:
            lac = frappe.get_doc({
                "doctype": "Lactation",
                "animal": "8200000001",
                "statut": "EN_COURS",
                "date_debut": "2024-06-01",
            })
            lac.flags.ignore_validate = True
            lac.insert(ignore_permissions=True)
            self.lactation = lac.name

        # --- Insemination REUSSIE (makes animal GESTANTE) ---
        # IA date must be > 280 days ago so velage date (today) is valid (>=250 days)
        self.ia_date = add_days(today(), -280)
        existing_ia = frappe.db.exists("Insemination", {
            "animal": "8200000001",
            "resultat": "REUSSIE",
        })
        if existing_ia:
            self.insemination = existing_ia
            # Reset animal state to GESTANTE with this IA
            frappe.db.set_value("Animal", "8200000001", {
                "etat_gestation": "GESTANTE",
                "id_ia_fecondante": self.insemination,
                "date_velage_prevue": add_days(self.ia_date, 280),
                "date_tarissement": add_days(add_days(self.ia_date, 280), -60),
            })
        else:
            ia = frappe.get_doc({
                "doctype": "Insemination",
                "animal": "8200000001",
                "taureau": "Test Taureau VEL",
                "type_semence": "CONVENTIONNELLE",
                "date_ia": self.ia_date,
                "resultat": "EN_ATTENTE",
            })
            ia.insert(ignore_permissions=True)
            # Mark as REUSSIE to trigger update_animal_on_resultat → sets GESTANTE
            ia.resultat = "REUSSIE"
            ia.save()
            self.insemination = ia.name

        frappe.db.commit()

    def tearDown(self):
        frappe.db.rollback()

    # ─── Helpers ───────────────────────────────────────────────

    def _make_velage(self, **kwargs):
        """Create and return a Velage doc with sensible defaults (not yet inserted)."""
        defaults = {
            "doctype": "Velage",
            "animal": "8200000001",
            "date_velage": today(),
            "type_velage": "FACILE",
            "nombre_veaux": "1",
            "sexe_veau1": "F",
            "vivant_veau1": 1,
        }
        defaults.update(kwargs)
        return frappe.get_doc(defaults)

    def _create_genisse(self):
        """Create a GENISSE animal for specific tests."""
        name = "8200000002"
        if not frappe.db.exists("Animal", name):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": name,
                "categorie": "GENISSE",
                "sexe": "F",
                "race": "Holstein",
                "date_naissance": "2022-01-01",
                "id_lot": "Test Lot VEL",
                "id_pere": "Test Taureau VEL",
                "date_entree": add_days(today(), -500), "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
                "etat_gestation": "GESTANTE",
            }).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Animal", name, {
                "etat_gestation": "GESTANTE",
                "categorie": "GENISSE",
                "statut": "ACTIF",
                "date_premier_velage": None,
            })
        # Create IA REUSSIE for the genisse
        ia_date = add_days(today(), -280)
        existing_ia = frappe.db.exists("Insemination", {
            "animal": name,
            "resultat": "REUSSIE",
        })
        if not existing_ia:
            ia = frappe.get_doc({
                "doctype": "Insemination",
                "animal": name,
                "taureau": "Test Taureau VEL",
                "type_semence": "CONVENTIONNELLE",
                "date_ia": ia_date,
                "resultat": "EN_ATTENTE",
            })
            ia.flags.ignore_validate = True
            ia.insert(ignore_permissions=True)
            ia.resultat = "REUSSIE"
            ia.flags.ignore_validate = True
            ia.save()
            existing_ia = ia.name

        frappe.db.set_value("Animal", name, {
            "id_ia_fecondante": existing_ia,
            "date_velage_prevue": add_days(ia_date, 280),
            "date_tarissement": add_days(add_days(ia_date, 280), -60),
        })
        return name, existing_ia

    # ─── Happy Path ────────────────────────────────────────────

    def test_valid_velage_creation(self):
        """Happy path: velage creates calf, lactation, resets mother to VIDE."""
        vel = self._make_velage()
        vel.insert(ignore_permissions=True)

        # Calf created
        self.assertTrue(vel.id_veau1, "Calf 1 should be created")
        calf = frappe.get_doc("Animal", vel.id_veau1)
        self.assertEqual(calf.sexe, "F")
        self.assertEqual(calf.id_mere, "8200000001")
        self.assertEqual(calf.statut, "ACTIF")

        # Lactation created
        self.assertTrue(vel.lactation, "Lactation should be created")
        lac = frappe.get_doc("Lactation", vel.lactation)
        self.assertEqual(lac.statut, "EN_COURS")
        self.assertEqual(lac.animal, "8200000001")

        # Mother reset to VIDE
        mother = frappe.get_doc("Animal", "8200000001")
        self.assertEqual(mother.etat_gestation, "VIDE")
        self.assertIsNone(mother.id_ia_fecondante)
        self.assertIsNone(mother.date_velage_prevue)
        self.assertIsNone(mother.date_tarissement)

    # ─── Validation Errors ─────────────────────────────────────

    def test_velage_non_gestante_animal(self):
        """ERR-VEL-02: Velage on non-GESTANTE animal should fail."""
        frappe.db.set_value("Animal", "8200000001", "etat_gestation", "VIDE")
        vel = self._make_velage()
        self.assertRaisesRegex(
            frappe.exceptions.ValidationError,
            "ERR-VEL-02",
            vel.insert,
            ignore_permissions=True,
        )

    def test_velage_male_animal(self):
        """ERR-VEL-01: Velage on male animal should fail."""
        # Create a male animal
        male_name = "8200000003"
        if not frappe.db.exists("Animal", male_name):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": male_name,
                "categorie": "TAURILLON",
                "sexe": "M",
                "race": "Holstein",
                "date_naissance": "2020-01-01",
                "id_lot": "Test Lot VEL",
                "id_pere": "Test Taureau VEL",
                "date_entree": add_days(today(), -500), "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)

        vel = self._make_velage(animal=male_name)
        self.assertRaisesRegex(
            frappe.exceptions.ValidationError,
            "ERR-VEL-01",
            vel.insert,
            ignore_permissions=True,
        )

    def test_velage_date_in_future(self):
        """ERR-VEL-03: Velage date in future should fail."""
        vel = self._make_velage(date_velage=add_days(today(), 1))
        self.assertRaisesRegex(
            frappe.exceptions.ValidationError,
            "ERR-VEL-03",
            vel.insert,
            ignore_permissions=True,
        )

    def test_velage_date_before_birth(self):
        """ERR-VEL-04: Velage date before animal birth should fail."""
        vel = self._make_velage(date_velage="2019-12-31")
        self.assertRaisesRegex(
            frappe.exceptions.ValidationError,
            "ERR-VEL-04",
            vel.insert,
            ignore_permissions=True,
        )

    def test_velage_date_too_soon_after_ia(self):
        """ERR-VEL-05: Velage date < 250 days after IA should fail."""
        # Set insemination field explicitly and use a date too close to IA
        too_soon = add_days(self.ia_date, 200)
        vel = self._make_velage(
            date_velage=str(too_soon),
            insemination=self.insemination,
        )
        self.assertRaisesRegex(
            frappe.exceptions.ValidationError,
            "ERR-VEL-05",
            vel.insert,
            ignore_permissions=True,
        )

    def test_missing_sexe_veau1(self):
        """ERR-VEL-06: Missing sexe_veau1 should fail."""
        vel = self._make_velage(sexe_veau1="")
        self.assertRaisesRegex(
            frappe.exceptions.ValidationError,
            "ERR-VEL-06",
            vel.insert,
            ignore_permissions=True,
        )

    def test_twins_missing_sexe_veau2(self):
        """ERR-VEL-07: Twins without sexe_veau2 should fail."""
        vel = self._make_velage(nombre_veaux="2", sexe_veau2="")
        self.assertRaisesRegex(
            frappe.exceptions.ValidationError,
            "ERR-VEL-07",
            vel.insert,
            ignore_permissions=True,
        )

    # ─── Twins ─────────────────────────────────────────────────

    def test_twins_both_calves_created(self):
        """Twins: both calves should be created correctly."""
        vel = self._make_velage(
            nombre_veaux="2",
            sexe_veau1="M",
            vivant_veau1=1,
            sexe_veau2="F",
            vivant_veau2=1,
        )
        vel.insert(ignore_permissions=True)

        self.assertTrue(vel.id_veau1, "Calf 1 should be created")
        self.assertTrue(vel.id_veau2, "Calf 2 should be created")

        calf1 = frappe.get_doc("Animal", vel.id_veau1)
        self.assertEqual(calf1.sexe, "M")
        self.assertEqual(calf1.categorie, "VEAU")

        calf2 = frappe.get_doc("Animal", vel.id_veau2)
        self.assertEqual(calf2.sexe, "F")
        self.assertEqual(calf2.categorie, "VELLE")

    # ─── Dead Calf ─────────────────────────────────────────────

    def test_dead_calf_no_animal_created(self):
        """Dead calf (vivant_veau1=0): no Animal should be created."""
        vel = self._make_velage(vivant_veau1=0)
        vel.insert(ignore_permissions=True)

        vel.reload()
        self.assertFalse(vel.id_veau1, "No calf should be created for dead birth")

    # ─── GENISSE → VACHE ──────────────────────────────────────

    def test_genisse_becomes_vache_on_first_velage(self):
        """GENISSE should become VACHE on first velage."""
        genisse_name, ia_name = self._create_genisse()

        vel = self._make_velage(animal=genisse_name)
        vel.insert(ignore_permissions=True)

        animal = frappe.get_doc("Animal", genisse_name)
        self.assertEqual(animal.categorie, "VACHE")
        self.assertEqual(str(animal.date_premier_velage), today())

    # ─── Auto-close Previous Lactation ─────────────────────────

    def test_auto_close_previous_lactation(self):
        """Previous EN_COURS lactation should be auto-closed as TARIE."""
        vel = self._make_velage()
        vel.insert(ignore_permissions=True)

        # The pre-existing lactation should now be TARIE
        prev_lac = frappe.get_doc("Lactation", self.lactation)
        self.assertEqual(prev_lac.statut, "TARIE")
        self.assertEqual(str(prev_lac.date_tarissement), today())

        # A new lactation should have been created
        self.assertTrue(vel.lactation)
        self.assertNotEqual(vel.lactation, self.lactation)
        new_lac = frappe.get_doc("Lactation", vel.lactation)
        self.assertEqual(new_lac.statut, "EN_COURS")

    # ─── Auto Link Insemination ────────────────────────────────

    def test_auto_link_insemination(self):
        """auto_link_insemination should fill insemination from animal.id_ia_fecondante."""
        vel = self._make_velage()
        # Don't set insemination explicitly — let auto_link do it
        vel.insert(ignore_permissions=True)

        vel.reload()
        self.assertEqual(vel.insemination, self.insemination)

    # ─── Lock Identity Fields ──────────────────────────────────

    def test_lock_identity_fields_animal(self):
        """Cannot change animal after creation."""
        vel = self._make_velage()
        vel.insert(ignore_permissions=True)

        vel.animal = "SOME-OTHER-ANIMAL"
        self.assertRaises(
            frappe.exceptions.ValidationError,
            vel.save,
        )

    def test_lock_identity_fields_date_velage(self):
        """Cannot change date_velage after creation."""
        vel = self._make_velage()
        vel.insert(ignore_permissions=True)

        vel.date_velage = add_days(today(), -1)
        self.assertRaises(
            frappe.exceptions.ValidationError,
            vel.save,
        )

    # ─── Calf Categorie ───────────────────────────────────────

    def test_calf_categorie_female(self):
        """Female calf should get categorie VELLE."""
        vel = self._make_velage(sexe_veau1="F")
        vel.insert(ignore_permissions=True)

        calf = frappe.get_doc("Animal", vel.id_veau1)
        self.assertEqual(calf.categorie, "VELLE")

    def test_calf_categorie_male(self):
        """Male calf should get categorie VEAU."""
        vel = self._make_velage(sexe_veau1="M")
        vel.insert(ignore_permissions=True)

        calf = frappe.get_doc("Animal", vel.id_veau1)
        self.assertEqual(calf.categorie, "VEAU")

    # ─── Birth Pesee ──────────────────────────────────────────

    def test_birth_pesee_created_with_poids(self):
        """Pesee NAISSANCE should be created when poids is provided."""
        vel = self._make_velage(poids_veau1=35.0)
        vel.insert(ignore_permissions=True)

        vel.reload()
        pesee = frappe.get_all("Pesee", filters={
            "animal": vel.id_veau1,
            "type_pesee": "NAISSANCE",
            "date_pesee": today(),
        }, fields=["poids_kg", "date_pesee"])
        self.assertGreaterEqual(len(pesee), 1)
        self.assertEqual(pesee[0].poids_kg, 35.0)
        self.assertEqual(str(pesee[0].date_pesee), today())

    def test_no_pesee_without_poids(self):
        """When poids is not provided, no NEW pesee should be created by this velage."""
        # Count pesees before
        before_count = frappe.db.count("Pesee", {"type_pesee": "NAISSANCE"})

        vel = self._make_velage(poids_veau1=None)
        vel.insert(ignore_permissions=True)

        # Count pesees after — should be the same (no new NAISSANCE pesee created)
        after_count = frappe.db.count("Pesee", {"type_pesee": "NAISSANCE"})
        self.assertEqual(before_count, after_count, "No new NAISSANCE pesee should be created without poids")

    # ─── TEMP ID Generation ───────────────────────────────────

    def test_auto_id_generated_without_identification(self):
        """A 10-digit numeric ID should be auto-generated for a calf without
        identification (production spec: max existing identification_tn + 1,
        zero-padded to 10 digits). Updated from the previous TEMP-XX spec."""
        vel = self._make_velage(identification_veau1="")
        vel.insert(ignore_permissions=True)

        calf = frappe.get_doc("Animal", vel.id_veau1)
        self.assertTrue(
            calf.identification_tn.isdigit() and len(calf.identification_tn) == 10,
            f"Expected 10-digit auto-incremented ID, got {calf.identification_tn}",
        )

    def test_calf_with_explicit_identification(self):
        """Calf with explicit identification should use it."""
        vel = self._make_velage(identification_veau1="8200099999")
        vel.insert(ignore_permissions=True)

        calf = frappe.get_doc("Animal", vel.id_veau1)
        self.assertEqual(calf.identification_tn, "8200099999")
