# Copyright (c) 2026, Mouhib Bouzamita and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days


class TestVaccination(FrappeTestCase):
    """Tests for Vaccination doctype validations."""

    def setUp(self):
        # --- Batiment ---
        if not frappe.db.exists("Batiment", "VAC-TEST-BAT"):
            frappe.get_doc({
                "doctype": "Batiment",
                "nom_batiment": "VAC-TEST-BAT",
                "type_batiment": "ELEVAGE",
            }).insert(ignore_permissions=True)

        # --- Lot ---
        if not frappe.db.exists("Lot", "VAC-TEST-LOT"):
            frappe.get_doc({
                "doctype": "Lot",
                "nom": "VAC-TEST-LOT",
                "batiment": "VAC-TEST-BAT",
                "superficie_m2": 100.0,
                "capacite_optimale": 20,
                "capacite_maximale": 30,
            }).insert(ignore_permissions=True)

        # --- Taureau ---
        if not frappe.db.exists("Taureau", "VAC-TEST-PERE"):
            frappe.get_doc({
                "doctype": "Taureau",
                "nom_taureau": "VAC-TEST-PERE",
                "code_taureau": "VACTP001",
                "race": "Holstein",
            }).insert(ignore_permissions=True)

        # --- Mere externe ---
        meres = frappe.get_all("Mere externe", limit=1)
        if meres:
            self.mere_externe = meres[0].name
        else:
            doc = frappe.get_doc({"doctype": "Mere externe"}).insert(ignore_permissions=True)
            self.mere_externe = doc.name

        # --- ACTIF animal ---
        if not frappe.db.exists("Animal", "8600000011"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8600000011",
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "id_lot": "VAC-TEST-LOT",
                "id_pere": "VAC-TEST-PERE",
                "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Animal", "8600000011", "statut", "ACTIF")

        # --- Non-ACTIF animal ---
        if not frappe.db.exists("Animal", "8600000012"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8600000012",
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "id_lot": "VAC-TEST-LOT",
                "id_pere": "VAC-TEST-PERE",
                "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)
            frappe.db.set_value("Animal", "8600000012", "statut", "VENDU")

        # --- VACCIN medicament ---
        if not frappe.db.exists("Medicament", "VAC-TEST-VACCIN"):
            frappe.get_doc({
                "doctype": "Medicament",
                "nom_medicament": "VAC-TEST-VACCIN",
                "type_medicament": "VACCIN",
                "delai_attente_lait": 0,
            }).insert(ignore_permissions=True)

        # --- Non-vaccine medicament ---
        if not frappe.db.exists("Medicament", "VAC-TEST-ANTIBIO"):
            frappe.get_doc({
                "doctype": "Medicament",
                "nom_medicament": "VAC-TEST-ANTIBIO",
                "type_medicament": "ANTIBIOTIQUE",
                "delai_attente_lait": 3,
            }).insert(ignore_permissions=True)

        for v in frappe.get_all("Vaccination", filters={"animal": "8600000011"}):
            frappe.delete_doc("Vaccination", v.name, force=True, ignore_permissions=True)

        frappe.db.commit()

    def tearDown(self):
        frappe.db.rollback()

    def test_valid_creation(self):
        """Happy path: a vaccination with a VACCIN medicament and a future rappel."""
        v = frappe.get_doc({
            "doctype": "Vaccination",
            "animal": "8600000011",
            "vaccin": "VAC-TEST-VACCIN",
            "date_vaccination": add_days(today(), -10),
            "date_rappel": add_days(today(), 355),
        }).insert(ignore_permissions=True)
        self.assertTrue(v.name)

    def test_rappel_optional(self):
        """date_rappel is optional — a vaccination without it is valid."""
        v = frappe.get_doc({
            "doctype": "Vaccination",
            "animal": "8600000011",
            "vaccin": "VAC-TEST-VACCIN",
            "date_vaccination": add_days(today(), -10),
        }).insert(ignore_permissions=True)
        self.assertTrue(v.name)

    def test_non_vaccin_medicament_fails(self):
        """ERR-VAC-01: a non-VACCIN medicament is rejected."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Vaccination",
                "animal": "8600000011",
                "vaccin": "VAC-TEST-ANTIBIO",
                "date_vaccination": add_days(today(), -10),
            }).insert(ignore_permissions=True)

    def test_non_actif_animal_fails(self):
        """A vaccination cannot be recorded for a non-ACTIF animal."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Vaccination",
                "animal": "8600000012",
                "vaccin": "VAC-TEST-VACCIN",
                "date_vaccination": add_days(today(), -10),
            }).insert(ignore_permissions=True)

    def test_future_vaccination_date_fails(self):
        """date_vaccination cannot be in the future."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Vaccination",
                "animal": "8600000011",
                "vaccin": "VAC-TEST-VACCIN",
                "date_vaccination": add_days(today(), 1),
            }).insert(ignore_permissions=True)

    def test_rappel_before_vaccination_fails(self):
        """date_rappel must be strictly after date_vaccination."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Vaccination",
                "animal": "8600000011",
                "vaccin": "VAC-TEST-VACCIN",
                "date_vaccination": add_days(today(), -10),
                "date_rappel": add_days(today(), -20),
            }).insert(ignore_permissions=True)

    def test_lock_identity_fields(self):
        """animal cannot be changed after creation."""
        v = frappe.get_doc({
            "doctype": "Vaccination",
            "animal": "8600000011",
            "vaccin": "VAC-TEST-VACCIN",
            "date_vaccination": add_days(today(), -10),
        }).insert(ignore_permissions=True)
        v.reload()
        v.animal = "8600000012"
        with self.assertRaises(frappe.exceptions.ValidationError):
            v.save(ignore_permissions=True)
