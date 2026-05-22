# Copyright (c) 2026, Mouhib Bouzamita and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days


class TestAvortement(FrappeTestCase):
    """Comprehensive tests for Avortement doctype validations and side effects."""

    def setUp(self):
        # --- Batiment ---
        if not frappe.db.exists("Batiment", "AVO-TEST-BAT"):
            frappe.get_doc({
                "doctype": "Batiment",
                "nom_batiment": "AVO-TEST-BAT",
                "type_batiment": "ELEVAGE",
            }).insert(ignore_permissions=True)

        # --- Lot ---
        if not frappe.db.exists("Lot", "AVO-TEST-LOT"):
            frappe.get_doc({
                "doctype": "Lot",
                "nom": "AVO-TEST-LOT",
                "batiment": "AVO-TEST-BAT",
                "superficie_m2": 100.0,
                "capacite_optimale": 20,
                "capacite_maximale": 30,
            }).insert(ignore_permissions=True)

        # --- Taureau ---
        if not frappe.db.exists("Taureau", "AVO-TEST-PERE"):
            frappe.get_doc({
                "doctype": "Taureau",
                "nom_taureau": "AVO-TEST-PERE",
                "code_taureau": "AVOTP001",
                "race": "Holstein",
            }).insert(ignore_permissions=True)

        # --- Mere externe ---
        meres = frappe.get_all("Mere externe", limit=1)
        if meres:
            self.mere_externe = meres[0].name
        else:
            doc = frappe.get_doc({"doctype": "Mere externe"}).insert(ignore_permissions=True)
            self.mere_externe = doc.name

        # --- Semence (for insemination) ---
        existing_semence = frappe.get_all("Semence", filters={
            "taureau": "AVO-TEST-PERE",
            "type_semence": "CONVENTIONNELLE",
        }, limit=1)
        # ST5-14 (Phase C): legacy `quantite_recue`/`quantite_restante` fields
        # removed in ST5-12; Semence stock now lives in Batch.batch_qty. These
        # tests don't assert on stock, so we just need a Semence row to exist.
        if existing_semence:
            self.semence = existing_semence[0].name
        else:
            sem = frappe.get_doc({
                "doctype": "Semence",
                "taureau": "AVO-TEST-PERE",
                "type_semence": "CONVENTIONNELLE",
                "date_reception": add_days(today(), -100),
            }).insert(ignore_permissions=True)
            self.semence = sem.name

        # --- GESTANTE animal ---
        if not frappe.db.exists("Animal", "8700000001"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8700000001",
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "id_lot": "AVO-TEST-LOT",
                "id_pere": "AVO-TEST-PERE",
                "date_entree": add_days(today(), -500), "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)

        # --- VIDE animal (for ERR-AVO-01) ---
        if not frappe.db.exists("Animal", "8700000002"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8700000002",
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "id_lot": "AVO-TEST-LOT",
                "id_pere": "AVO-TEST-PERE",
                "date_entree": add_days(today(), -500), "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)
        frappe.db.set_value("Animal", "8700000002", "etat_gestation", "VIDE")

        # Clean up avortements for test animal
        for avo in frappe.get_all("Avortement", filters={"animal": "8700000001"}):
            doc = frappe.get_doc("Avortement", avo.name)
            doc.flags.ignore_validate = True
            doc.delete(force=True, ignore_permissions=True)

        # --- Create insemination and set animal to GESTANTE ---
        # First ensure a lactation exists for insemination
        existing_lac = frappe.db.exists("Lactation", {
            "animal": "8700000001",
            "statut": "EN_COURS",
        })
        if not existing_lac:
            lac = frappe.get_doc({
                "doctype": "Lactation",
                "animal": "8700000001",
                "statut": "EN_COURS",
                "date_debut": add_days(today(), -200),
            })
            lac.flags.ignore_validate = True
            lac.insert(ignore_permissions=True)

        # Create or reuse insemination. When reusing, REFRESH date_ia so the
        # stade_gestation arithmetic stays anchored on `today` — otherwise the
        # test drifts (the IA's date_ia is locked at whatever `today` was the
        # first time setUp ran, so later runs compute the wrong gestation days).
        existing_ia = frappe.get_all("Insemination", filters={
            "animal": "8700000001",
            "resultat": "REUSSIE",
        }, limit=1)
        if existing_ia:
            self.insemination = existing_ia[0].name
            frappe.db.set_value("Insemination", self.insemination,
                "date_ia", add_days(today(), -120))
        else:
            ia = frappe.get_doc({
                "doctype": "Insemination",
                "animal": "8700000001",
                "date_ia": add_days(today(), -120),
                "taureau": "AVO-TEST-PERE",
                "type_semence": "CONVENTIONNELLE",
                "resultat": "REUSSIE",
            })
            ia.flags.ignore_validate = True
            ia.insert(ignore_permissions=True)
            self.insemination = ia.name

        # Set animal to GESTANTE state
        frappe.db.set_value("Animal", "8700000001", {
            "etat_gestation": "GESTANTE",
            "id_ia_fecondante": self.insemination,
            "date_velage_prevue": add_days(today(), 160),
            "date_tarissement": add_days(today(), 100),
        })

        frappe.db.commit()

    def tearDown(self):
        frappe.db.rollback()

    # ──────────────────────────────────────────────
    # Happy path
    # ──────────────────────────────────────────────
    def test_valid_creation(self):
        """Happy path: create an avortement for a GESTANTE animal."""
        avo = frappe.get_doc({
            "doctype": "Avortement",
            "animal": "8700000001",
            "date_avortement": add_days(today(), -5),
            "cause": "INCONNUE",
        }).insert(ignore_permissions=True)

        self.assertTrue(avo.name)

    # ──────────────────────────────────────────────
    # Validation errors
    # ──────────────────────────────────────────────
    def test_non_gestante_animal_fails(self):
        """ERR-AVO-01: Non-GESTANTE animal cannot have an avortement."""
        with self.assertRaises(frappe.exceptions.ValidationError) as ctx:
            frappe.get_doc({
                "doctype": "Avortement",
                "animal": "8700000002",
                "date_avortement": add_days(today(), -5),
                "cause": "INCONNUE",
            }).insert(ignore_permissions=True)
        self.assertIn("ERR-AVO-01", str(ctx.exception))

    def test_future_date_fails(self):
        """ERR-AVO-02: Future date is not allowed."""
        with self.assertRaises(frappe.exceptions.ValidationError) as ctx:
            frappe.get_doc({
                "doctype": "Avortement",
                "animal": "8700000001",
                "date_avortement": add_days(today(), 5),
                "cause": "INCONNUE",
            }).insert(ignore_permissions=True)
        self.assertIn("ERR-AVO-02", str(ctx.exception))

    def test_date_before_ia_fails(self):
        """ERR-AVO-03: Date before insemination date is not allowed."""
        with self.assertRaises(frappe.exceptions.ValidationError) as ctx:
            frappe.get_doc({
                "doctype": "Avortement",
                "animal": "8700000001",
                "date_avortement": add_days(today(), -200),
                "insemination": self.insemination,
                "cause": "INCONNUE",
            }).insert(ignore_permissions=True)
        self.assertIn("ERR-AVO-03", str(ctx.exception))

    # ──────────────────────────────────────────────
    # Auto-link insemination
    # ──────────────────────────────────────────────
    def test_auto_link_insemination(self):
        """Insemination is auto-linked from animal's id_ia_fecondante."""
        avo = frappe.get_doc({
            "doctype": "Avortement",
            "animal": "8700000001",
            "date_avortement": add_days(today(), -5),
            "cause": "INCONNUE",
        }).insert(ignore_permissions=True)

        self.assertEqual(avo.insemination, self.insemination)

    # ──────────────────────────────────────────────
    # Calculate stade gestation
    # ──────────────────────────────────────────────
    def test_calculate_stade_gestation(self):
        """stade_gestation = date_avortement - date_ia."""
        avo = frappe.get_doc({
            "doctype": "Avortement",
            "animal": "8700000001",
            "date_avortement": add_days(today(), -5),
            "cause": "INCONNUE",
        }).insert(ignore_permissions=True)

        # IA was 120 days ago, avortement was 5 days ago => stade = 115
        self.assertEqual(avo.stade_gestation, 115)

    # ──────────────────────────────────────────────
    # Animal reset to VIDE
    # ──────────────────────────────────────────────
    def test_animal_reset_to_vide_after_insert(self):
        """After avortement, animal is reset to VIDE."""
        frappe.get_doc({
            "doctype": "Avortement",
            "animal": "8700000001",
            "date_avortement": add_days(today(), -5),
            "cause": "INCONNUE",
        }).insert(ignore_permissions=True)

        animal = frappe.get_doc("Animal", "8700000001")
        self.assertEqual(animal.etat_gestation, "VIDE")
        self.assertFalse(animal.id_ia_fecondante)
        self.assertFalse(animal.date_velage_prevue)
        self.assertFalse(animal.date_tarissement)

    # ──────────────────────────────────────────────
    # Lock identity fields
    # ──────────────────────────────────────────────
    def test_lock_identity_fields(self):
        """Cannot change animal or date_avortement after creation."""
        avo = frappe.get_doc({
            "doctype": "Avortement",
            "animal": "8700000001",
            "date_avortement": add_days(today(), -5),
            "cause": "INCONNUE",
        }).insert(ignore_permissions=True)

        avo.reload()
        avo.animal = "8700000002"
        with self.assertRaises(frappe.exceptions.ValidationError):
            avo.save(ignore_permissions=True)

    # ──────────────────────────────────────────────
    # on_trash restores animal to GESTANTE
    # ──────────────────────────────────────────────
    def test_on_trash_restores_animal_to_gestante(self):
        """Deleting an avortement restores the animal to GESTANTE."""
        avo = frappe.get_doc({
            "doctype": "Avortement",
            "animal": "8700000001",
            "date_avortement": add_days(today(), -5),
            "cause": "INCONNUE",
        }).insert(ignore_permissions=True)

        # Confirm animal is VIDE after avortement
        self.assertEqual(
            frappe.db.get_value("Animal", "8700000001", "etat_gestation"),
            "VIDE"
        )

        # Delete the avortement
        frappe.delete_doc("Avortement", avo.name, force=True, ignore_permissions=True)

        # Animal should be restored to GESTANTE
        animal = frappe.get_doc("Animal", "8700000001")
        self.assertEqual(animal.etat_gestation, "GESTANTE")
        self.assertEqual(animal.id_ia_fecondante, self.insemination)
