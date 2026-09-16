"""
RG14 test sketch — assert the EFFECTIVE behavior, not a boolean.

Goal: given a taureau whose only Semence batch is depleted (batch_qty = 0),
creating an Insémination
  (1) still inserts the IA (the breeding event is real), and
  (2) does NOT produce a consuming Stock Entry (no negative batch is written).

This is the honest RG14 assertion: there is no `disponible` field to check, so
we check that the stock ledger was left untouched and the batch never went
negative.

Run inside a Frappe test context (FrappeTestCase). Pseudocode-ish; fill in the
real fixture helpers used by the app's existing tests (see
hmd_agro/hmd_agro/tests/test_semence_dual_write.py and seed_data.py).
"""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestRG14SemenceZeroStock(FrappeTestCase):
    def test_depleted_batch_blocks_stock_write_but_saves_ia(self):
        taureau = make_taureau()                      # fixture helper
        animal = make_eligible_vache_en_lactation()   # VACHE w/ lactation EN_COURS

        # One Semence batch, received then fully consumed -> batch_qty == 0.
        sem = make_semence(taureau=taureau, type_semence="CONVENTIONNELLE",
                           opening_qty=1)
        consume_one_paillette(sem)                     # bring batch_qty to 0
        self.assertEqual(
            float(frappe.db.get_value("Batch", sem.name, "batch_qty") or 0), 0,
        )

        se_before = frappe.db.count("Stock Entry")

        ia = frappe.get_doc({
            "doctype": "Insemination",
            "animal": animal.name,
            "taureau": taureau,
            "type_semence": "CONVENTIONNELLE",
            "date_ia": frappe.utils.today(),
        }).insert()

        # (1) IA is persisted despite zero stock.
        self.assertTrue(frappe.db.exists("Insemination", ia.name))

        # (2) No consuming Stock Entry was created; batch never went negative.
        self.assertEqual(frappe.db.count("Stock Entry"), se_before)
        self.assertGreaterEqual(
            float(frappe.db.get_value("Batch", sem.name, "batch_qty") or 0), 0,
        )

    def test_batch_with_stock_decrements_normally(self):
        # Control: when stock exists, RG13 fires and batch_qty drops by 1.
        taureau = make_taureau()
        animal = make_eligible_vache_en_lactation()
        sem = make_semence(taureau=taureau, type_semence="CONVENTIONNELLE",
                           opening_qty=2)

        frappe.get_doc({
            "doctype": "Insemination",
            "animal": animal.name,
            "taureau": taureau,
            "type_semence": "CONVENTIONNELLE",
            "date_ia": frappe.utils.today(),
        }).insert()

        self.assertEqual(
            float(frappe.db.get_value("Batch", sem.name, "batch_qty") or 0), 1,
        )


# --- fixture helpers (implement against the app's existing seed utilities) ---
def make_taureau(): ...
def make_eligible_vache_en_lactation(): ...
def make_semence(taureau, type_semence, opening_qty): ...
def consume_one_paillette(sem): ...
