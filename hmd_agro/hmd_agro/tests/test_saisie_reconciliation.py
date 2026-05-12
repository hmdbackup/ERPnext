# Copyright (c) 2026, Mouhib Bouzamita and Contributors
# See license.txt
"""End-to-end tests for the saisie_traite reconciliation flow.

Covers the math in `save_traites`:
  - fresh-day reconciliation (ratio applied)
  - no `lait_vendu` → ratio=1.0, raw values stored
  - negative écart (consumed > brut_sum) → ratio=1.0, raw values stored, warning
  - edit detection: unchanged cell keeps its stored brut (no drift on re-save)
  - edit a single cell → ratio recomputes from new brut_sum
  - Bilan stored fields (production_totale_saisie + ecart_litres) reflect raw totals
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days

from hmd_agro.hmd_agro.page.saisie_traite.saisie_traite import save_traites


ANIMAL = "8500000001"
LOT = "RECON-TEST-LOT"
BATIMENT = "RECON-TEST-BAT"
PERE = "RECON-TEST-PERE"


class TestSaisieReconciliation(FrappeTestCase):

    def setUp(self):
        # Batiment / Lot / Taureau / Mere
        if not frappe.db.exists("Batiment", BATIMENT):
            frappe.get_doc({
                "doctype": "Batiment",
                "nom_batiment": BATIMENT,
                "type_batiment": "ELEVAGE",
            }).insert(ignore_permissions=True)

        if not frappe.db.exists("Lot", LOT):
            frappe.get_doc({
                "doctype": "Lot",
                "nom": LOT,
                "batiment": BATIMENT,
                "superficie_m2": 100.0,
                "capacite_optimale": 20,
                "capacite_maximale": 30,
            }).insert(ignore_permissions=True)

        if not frappe.db.exists("Taureau", PERE):
            frappe.get_doc({
                "doctype": "Taureau",
                "nom_taureau": PERE,
                "code_taureau": "RTP001",
                "race": "Holstein",
            }).insert(ignore_permissions=True)

        meres = frappe.get_all("Mere externe", limit=1)
        if meres:
            self.mere = meres[0].name
        else:
            self.mere = frappe.get_doc({"doctype": "Mere externe"}).insert(
                ignore_permissions=True).name

        # Animal + lactation
        if not frappe.db.exists("Animal", ANIMAL):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": ANIMAL,
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "date_entree": add_days(today(), -800),
                "id_lot": LOT,
                "id_pere": PERE,
                "est_achat": 1,
                "id_mere_externe": self.mere,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Animal", ANIMAL, {
                "statut": "ACTIF",
                "attente_lait_active": 0,
                "date_fin_attente_lait": None,
            })

        lac = frappe.db.exists("Lactation", {"animal": ANIMAL, "statut": "EN_COURS"})
        if lac:
            self.lactation = lac
        else:
            l = frappe.get_doc({
                "doctype": "Lactation",
                "animal": ANIMAL,
                "statut": "EN_COURS",
                "date_debut": add_days(today(), -120),
            })
            l.flags.ignore_validate = True
            l.insert(ignore_permissions=True)
            self.lactation = l.name

        # Clean any leftover Traites / Bilan
        frappe.db.sql("DELETE FROM `tabTraite` WHERE animal = %s", ANIMAL)
        frappe.db.sql("DELETE FROM `tabBilan Lait Journalier`")
        frappe.db.commit()

        self.date = add_days(today(), -2)

    def tearDown(self):
        frappe.db.sql("DELETE FROM `tabTraite` WHERE animal = %s", ANIMAL)
        frappe.db.sql("DELETE FROM `tabBilan Lait Journalier`")
        frappe.db.commit()

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────
    def _entries(self, matin, soir, matin_name=None, soir_name=None):
        return [
            {"animal": ANIMAL, "session": "MATIN",
             "quantite_litres": matin, "traite_name": matin_name},
            {"animal": ANIMAL, "session": "SOIR",
             "quantite_litres": soir, "traite_name": soir_name},
        ]

    def _bilan(self, vendu, ci, lv):
        return {
            "lait_vendu": vendu,
            "consommation_interne": ci,
            "lait_veau": lv,
        }

    def _read(self, session):
        name = frappe.db.get_value("Traite", {"animal": ANIMAL,
                                              "date_traite": self.date,
                                              "session": session},
                                   ["name", "quantite_litres", "quantite_litres_brut"],
                                   as_dict=True)
        return name

    def _read_bilan(self):
        return frappe.db.get_value("Bilan Lait Journalier", {"date": self.date},
                                   ["production_totale_saisie", "ecart_litres",
                                    "lait_vendu", "consommation_interne", "lait_veau"],
                                   as_dict=True)

    # ──────────────────────────────────────────────────────────────────
    # Fresh-day reconciliation: brut=[20,15], consumed=33 → ratio=0.9429
    # → reconciled=[18.9, 14.1], Bilan stores brut_sum=35, ecart=2
    # ──────────────────────────────────────────────────────────────────
    def test_fresh_reconciliation(self):
        result = save_traites(self.date, self._entries(20, 15), self._bilan(30, 2, 1))
        self.assertEqual(result["created"], 2)
        self.assertAlmostEqual(result["ratio"], 33 / 35, places=4)

        m = self._read("MATIN")
        s = self._read("SOIR")
        self.assertAlmostEqual(m.quantite_litres, 18.9, places=1)
        self.assertAlmostEqual(m.quantite_litres_brut, 20.0, places=1)
        self.assertAlmostEqual(s.quantite_litres, 14.1, places=1)
        self.assertAlmostEqual(s.quantite_litres_brut, 15.0, places=1)

        b = self._read_bilan()
        self.assertAlmostEqual(b.production_totale_saisie, 35.0, places=1)
        self.assertAlmostEqual(b.ecart_litres, 2.0, places=1)

    # ──────────────────────────────────────────────────────────────────
    # No vendu → ratio=1, raw values stored
    # ──────────────────────────────────────────────────────────────────
    def test_no_vendu_no_scaling(self):
        result = save_traites(self.date, self._entries(20, 15), self._bilan(0, 0, 0))
        self.assertEqual(result["ratio"], 1.0)

        m = self._read("MATIN")
        s = self._read("SOIR")
        self.assertAlmostEqual(m.quantite_litres, 20.0, places=1)
        self.assertAlmostEqual(m.quantite_litres_brut, 20.0, places=1)
        self.assertAlmostEqual(s.quantite_litres, 15.0, places=1)
        self.assertAlmostEqual(s.quantite_litres_brut, 15.0, places=1)

        b = self._read_bilan()
        self.assertAlmostEqual(b.production_totale_saisie, 35.0, places=1)
        self.assertAlmostEqual(b.ecart_litres, 35.0, places=1)

    # ──────────────────────────────────────────────────────────────────
    # Negative écart (consumed > brut_sum) → ratio=1, warning flag set
    # ──────────────────────────────────────────────────────────────────
    def test_negative_ecart_skips_scaling(self):
        result = save_traites(self.date, self._entries(20, 15), self._bilan(40, 0, 0))
        self.assertEqual(result["ratio"], 1.0)
        self.assertTrue(result["negative_ecart"])

        m = self._read("MATIN")
        s = self._read("SOIR")
        self.assertAlmostEqual(m.quantite_litres, 20.0, places=1)
        self.assertAlmostEqual(s.quantite_litres, 15.0, places=1)

        b = self._read_bilan()
        self.assertAlmostEqual(b.production_totale_saisie, 35.0, places=1)
        self.assertAlmostEqual(b.ecart_litres, -5.0, places=1)

    # ──────────────────────────────────────────────────────────────────
    # Re-save unchanged inputs on a reconciled day → no drift
    # First save: reconciled=[18.9, 14.1] with brut=[20, 15]
    # Re-save sending the displayed values back → cells detected as unchanged
    # → keeps stored brut → same result, no drift
    # ──────────────────────────────────────────────────────────────────
    def test_resave_unchanged_no_drift(self):
        save_traites(self.date, self._entries(20, 15), self._bilan(30, 2, 1))
        m = self._read("MATIN")
        s = self._read("SOIR")

        # Second save: send the displayed (reconciled) values back, same bilan
        save_traites(
            self.date,
            self._entries(m.quantite_litres, s.quantite_litres,
                          matin_name=m.name, soir_name=s.name),
            self._bilan(30, 2, 1),
        )
        m2 = self._read("MATIN")
        s2 = self._read("SOIR")
        # No drift in quantite_litres
        self.assertAlmostEqual(m2.quantite_litres, m.quantite_litres, places=1)
        self.assertAlmostEqual(s2.quantite_litres, s.quantite_litres, places=1)
        # Brut preserved (20 and 15, NOT the reconciled 18.9/14.1)
        self.assertAlmostEqual(m2.quantite_litres_brut, 20.0, places=1)
        self.assertAlmostEqual(s2.quantite_litres_brut, 15.0, places=1)
        # Bilan still reflects the raw totals
        b = self._read_bilan()
        self.assertAlmostEqual(b.production_totale_saisie, 35.0, places=1)
        self.assertAlmostEqual(b.ecart_litres, 2.0, places=1)

    # ──────────────────────────────────────────────────────────────────
    # Edit one cell on a reconciled day → ratio recomputes
    # First save: brut=[20, 15], reconciled=[18.9, 14.1]
    # Then edit MATIN to 22 → backend detects edit, brut=[22, 15], brut_sum=37,
    # ratio = 33/37 = 0.8919 → reconciled=[19.6, 13.4]
    # ──────────────────────────────────────────────────────────────────
    def test_edit_one_cell_recomputes_ratio(self):
        save_traites(self.date, self._entries(20, 15), self._bilan(30, 2, 1))
        m = self._read("MATIN")
        s = self._read("SOIR")

        # Edit MATIN: send a value DIFFERENT from the stored quantite_litres (18.9)
        result = save_traites(
            self.date,
            self._entries(22, s.quantite_litres,  # 22 ≠ 18.9 → edit detected
                          matin_name=m.name, soir_name=s.name),
            self._bilan(30, 2, 1),
        )
        self.assertAlmostEqual(result["ratio"], 33 / 37, places=4)

        m2 = self._read("MATIN")
        s2 = self._read("SOIR")
        # New brut: MATIN updated, SOIR preserved
        self.assertAlmostEqual(m2.quantite_litres_brut, 22.0, places=1)
        self.assertAlmostEqual(s2.quantite_litres_brut, 15.0, places=1)
        # Reconciled values with new ratio
        self.assertAlmostEqual(m2.quantite_litres, round(22 * 33 / 37, 1), places=1)
        self.assertAlmostEqual(s2.quantite_litres, round(15 * 33 / 37, 1), places=1)
        # Bilan reflects new brut sum
        b = self._read_bilan()
        self.assertAlmostEqual(b.production_totale_saisie, 37.0, places=1)
        self.assertAlmostEqual(b.ecart_litres, 4.0, places=1)

    # ──────────────────────────────────────────────────────────────────
    # Reconciled sum should equal consumed (modulo ≤0.5 L rounding residue)
    # ──────────────────────────────────────────────────────────────────
    def test_reconciled_sum_matches_consumed(self):
        save_traites(self.date, self._entries(20, 15), self._bilan(30, 2, 1))
        m = self._read("MATIN")
        s = self._read("SOIR")
        consumed = 33.0
        # Sum of reconciled values should be ≈ consumed
        self.assertAlmostEqual(m.quantite_litres + s.quantite_litres, consumed, delta=0.5)
