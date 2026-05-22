# Copyright (c) 2026, Mouhib Bouzamita and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days


class TestTraite(FrappeTestCase):
    """Comprehensive tests for Traite doctype validations and side effects."""

    def setUp(self):
        # --- Batiment ---
        if not frappe.db.exists("Batiment", "TRA-TEST-BAT"):
            frappe.get_doc({
                "doctype": "Batiment",
                "nom_batiment": "TRA-TEST-BAT",
                "type_batiment": "ELEVAGE",
            }).insert(ignore_permissions=True)

        # --- Lot ---
        if not frappe.db.exists("Lot", "TRA-TEST-LOT"):
            frappe.get_doc({
                "doctype": "Lot",
                "nom": "TRA-TEST-LOT",
                "batiment": "TRA-TEST-BAT",
                "superficie_m2": 100.0,
                "capacite_optimale": 20,
                "capacite_maximale": 30,
            }).insert(ignore_permissions=True)

        # --- Taureau ---
        if not frappe.db.exists("Taureau", "TRA-TEST-PERE"):
            frappe.get_doc({
                "doctype": "Taureau",
                "nom_taureau": "TRA-TEST-PERE",
                "code_taureau": "TRATP001",
                "race": "Holstein",
            }).insert(ignore_permissions=True)

        # --- Mere externe ---
        meres = frappe.get_all("Mere externe", limit=1)
        if meres:
            self.mere_externe = meres[0].name
        else:
            doc = frappe.get_doc({"doctype": "Mere externe"}).insert(ignore_permissions=True)
            self.mere_externe = doc.name

        # --- Female VACHE animal ---
        if not frappe.db.exists("Animal", "8400000001"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8400000001",
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "date_entree": add_days(today(), -800),
                "id_lot": "TRA-TEST-LOT",
                "id_pere": "TRA-TEST-PERE",
                "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Animal", "8400000001", {
                "statut": "ACTIF",
                "attente_lait_active": 0,
                "date_fin_attente_lait": None,
            })

        # --- Lactation EN_COURS ---
        existing_lac = frappe.db.exists("Lactation", {
            "animal": "8400000001",
            "statut": "EN_COURS",
        })
        if existing_lac:
            self.lactation = existing_lac
        else:
            lac = frappe.get_doc({
                "doctype": "Lactation",
                "animal": "8400000001",
                "statut": "EN_COURS",
                "date_debut": add_days(today(), -60),
            })
            lac.flags.ignore_validate = True
            lac.insert(ignore_permissions=True)
            self.lactation = lac.name

        # Clean up traites for test animal
        for t in frappe.get_all("Traite", filters={"animal": "8400000001"}):
            frappe.delete_doc("Traite", t.name, force=True, ignore_permissions=True)

        frappe.db.commit()

    def tearDown(self):
        frappe.db.rollback()

    # ──────────────────────────────────────────────
    # Happy path
    # ──────────────────────────────────────────────
    def test_valid_creation(self):
        """Happy path: create a valid traite."""
        traite = frappe.get_doc({
            "doctype": "Traite",
            "animal": "8400000001",
            "date_traite": add_days(today(), -1),
            "session": "MATIN",
            "quantite_litres": 15.0,
        }).insert(ignore_permissions=True)

        self.assertTrue(traite.name)
        self.assertEqual(traite.quantite_litres, 15.0)

    # ──────────────────────────────────────────────
    # Auto-link lactation
    # ──────────────────────────────────────────────
    def test_auto_link_to_lactation(self):
        """Traite should auto-link to animal's active lactation."""
        traite = frappe.get_doc({
            "doctype": "Traite",
            "animal": "8400000001",
            "date_traite": add_days(today(), -1),
            "session": "MATIN",
            "quantite_litres": 10.0,
        }).insert(ignore_permissions=True)

        self.assertEqual(traite.lactation, self.lactation)

    # ──────────────────────────────────────────────
    # Validation errors
    # ──────────────────────────────────────────────
    def test_no_lactation_fails(self):
        """CF-TRA-01: Animal without active lactation cannot have a traite."""
        # Create animal without lactation
        if not frappe.db.exists("Animal", "8400000002"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8400000002",
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "date_entree": add_days(today(), -800),
                "id_lot": "TRA-TEST-LOT",
                "id_pere": "TRA-TEST-PERE",
                "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)

        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Traite",
                "animal": "8400000002",
                "date_traite": add_days(today(), -1),
                "session": "MATIN",
                "quantite_litres": 10.0,
            }).insert(ignore_permissions=True)

    def test_future_date_fails(self):
        """CF-TRA-02: Future date is not allowed."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Traite",
                "animal": "8400000001",
                "date_traite": add_days(today(), 1),
                "session": "MATIN",
                "quantite_litres": 10.0,
            }).insert(ignore_permissions=True)

    def test_date_before_lactation_start_fails(self):
        """Date before lactation date_debut is not allowed."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Traite",
                "animal": "8400000001",
                "lactation": self.lactation,
                "date_traite": add_days(today(), -100),
                "session": "MATIN",
                "quantite_litres": 10.0,
            }).insert(ignore_permissions=True)

    def test_negative_quantity_fails(self):
        """Negative quantity is not allowed."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Traite",
                "animal": "8400000001",
                "date_traite": add_days(today(), -1),
                "session": "MATIN",
                "quantite_litres": -5.0,
            }).insert(ignore_permissions=True)

    def test_quantity_over_60_fails(self):
        """Quantity > 60 litres is not allowed."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Traite",
                "animal": "8400000001",
                "date_traite": add_days(today(), -1),
                "session": "MATIN",
                "quantite_litres": 65.0,
            }).insert(ignore_permissions=True)

    def test_duplicate_session_fails(self):
        """CF-TRA-03: Same animal + date + session cannot be duplicated."""
        # First create a traite via SQL so it definitely exists
        dup_date = add_days(today(), -55)
        dup_name = f"TRA-8400000001-{dup_date}-MATIN"
        # Ensure clean state
        frappe.db.sql("DELETE FROM `tabTraite` WHERE name = %s", dup_name)
        frappe.db.sql("""
            INSERT INTO `tabTraite` (name, animal, date_traite, session, quantite_litres, lactation,
                owner, creation, modified, modified_by, docstatus)
            VALUES (%s, '8400000001', %s, 'MATIN', 10.0, %s,
                'Administrator', NOW(), NOW(), 'Administrator', 0)
        """, (dup_name, dup_date, self.lactation))

        # Now trying to create a duplicate via the normal path should fail
        with self.assertRaises((frappe.exceptions.ValidationError, frappe.exceptions.DuplicateEntryError)):
            frappe.get_doc({
                "doctype": "Traite",
                "animal": "8400000001",
                "date_traite": dup_date,
                "session": "MATIN",
                "quantite_litres": 12.0,
            }).insert(ignore_permissions=True)

    def test_taux_tb_over_10_fails(self):
        """taux_tb > 10 is not allowed."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Traite",
                "animal": "8400000001",
                "date_traite": add_days(today(), -1),
                "session": "MATIN",
                "quantite_litres": 10.0,
                "taux_tb": 12.0,
            }).insert(ignore_permissions=True)

    def test_taux_tp_over_10_fails(self):
        """taux_tp > 10 is not allowed."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Traite",
                "animal": "8400000001",
                "date_traite": add_days(today(), -1),
                "session": "MATIN",
                "quantite_litres": 10.0,
                "taux_tp": 15.0,
            }).insert(ignore_permissions=True)

    # ──────────────────────────────────────────────
    # Warnings
    # ──────────────────────────────────────────────
    def test_warn_attente_lait(self):
        """Animal with attente_lait_active should trigger a warning (msgprint)."""
        frappe.db.set_value("Animal", "8400000001", {
            "attente_lait_active": 1,
            "date_fin_attente_lait": add_days(today(), 5),
        })

        # Should not raise, but should show msgprint warning
        traite = frappe.get_doc({
            "doctype": "Traite",
            "animal": "8400000001",
            "date_traite": add_days(today(), -1),
            "session": "SOIR",
            "quantite_litres": 10.0,
        }).insert(ignore_permissions=True)

        self.assertTrue(traite.name)

    # ──────────────────────────────────────────────
    # Lock identity fields
    # ──────────────────────────────────────────────
    def test_lock_identity_fields(self):
        """Cannot change the animal field after creation."""
        # Create second animal with lactation
        if not frappe.db.exists("Animal", "8400000003"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8400000003",
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "date_entree": add_days(today(), -800),
                "id_lot": "TRA-TEST-LOT",
                "id_pere": "TRA-TEST-PERE",
                "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)

        traite = frappe.get_doc({
            "doctype": "Traite",
            "animal": "8400000001",
            "date_traite": add_days(today(), -2),
            "session": "MATIN",
            "quantite_litres": 10.0,
        }).insert(ignore_permissions=True)

        traite.reload()
        traite.animal = "8400000003"
        with self.assertRaises(frappe.exceptions.ValidationError):
            traite.save(ignore_permissions=True)

    # ──────────────────────────────────────────────
    # Lactation production update
    # ──────────────────────────────────────────────
    def test_update_lactation_production_after_insert(self):
        """After inserting a traite, lactation.production_totale should be updated."""
        frappe.get_doc({
            "doctype": "Traite",
            "animal": "8400000001",
            "date_traite": add_days(today(), -10),
            "session": "MATIN",
            "quantite_litres": 12.5,
        }).insert(ignore_permissions=True)

        frappe.get_doc({
            "doctype": "Traite",
            "animal": "8400000001",
            "date_traite": add_days(today(), -10),
            "session": "SOIR",
            "quantite_litres": 10.0,
        }).insert(ignore_permissions=True)

        lac = frappe.get_doc("Lactation", self.lactation)
        self.assertAlmostEqual(lac.production_totale, 22.5, places=1)

    # ──────────────────────────────────────────────
    # Brut fallback (reconciliation bookkeeping field)
    # ──────────────────────────────────────────────
    def test_brut_fallback_on_direct_create(self):
        """When creating a Traite directly without setting brut, validate() should seed it from quantite_litres."""
        traite = frappe.get_doc({
            "doctype": "Traite",
            "animal": "8400000001",
            "date_traite": add_days(today(), -3),
            "session": "MATIN",
            "quantite_litres": 18.0,
        }).insert(ignore_permissions=True)
        self.assertEqual(traite.quantite_litres_brut, 18.0)

    def test_brut_explicit_value_preserved(self):
        """If brut is set explicitly (saisie_traite reconciliation flow),
        the fallback must NOT overwrite it."""
        traite = frappe.get_doc({
            "doctype": "Traite",
            "animal": "8400000001",
            "date_traite": add_days(today(), -4),
            "session": "MATIN",
            "quantite_litres": 18.9,      # reconciled value
            "quantite_litres_brut": 20.0,  # original measurement
        }).insert(ignore_permissions=True)
        self.assertEqual(traite.quantite_litres, 18.9)
        self.assertEqual(traite.quantite_litres_brut, 20.0)
