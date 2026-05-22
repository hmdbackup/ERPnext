# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Medicament(Document):
    # ST5-13 (Phase C): the negative-stock validate() msgprint was removed.
    # Stock is now tracked exclusively via the ERPNext Stock module (Bin) —
    # the legacy `stock_actuel` field is gone in ST5-12. Low-stock signals
    # come from two sources:
    #   • native reorder Material Request (wired via ST5-08 + utils/reorder_sync.py),
    #     fires preventively when Bin falls to Item.reorder_level
    #   • soft form-level msgprint in Traitement.decrement_medicament_stock,
    #     fires when Bin <= 0 at consumption time

    def onload(self):
        """ST5-17: populate the read-only `stock_courant` display field with
        the current Bin.actual_qty. Recomputed on every form load — never
        persisted as a meaningful value (read_only + no_copy)."""
        if not self.item:
            return
        from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_WAREHOUSE
        self.stock_courant = float(frappe.db.get_value("Bin",
            {"item_code": self.item, "warehouse": DEFAULT_WAREHOUSE},
            "actual_qty") or 0)

    def after_insert(self):
        """Auto-create the matching ERPNext Item and link it. Without this hook,
        new Médicaments created via the UI wouldn't get an Item, breaking the
        Stock Entry dual-write path in Traitement and any future Phase B reports
        that aggregate from the Stock Ledger."""
        if not self.item:
            from hmd_agro.hmd_agro.setup.medicament_migration import _migrate_one_medicament
            _migrate_one_medicament(self)
        if self.reorder_level:
            from hmd_agro.hmd_agro.utils.reorder_sync import sync_reorder_level
            sync_reorder_level("Medicament", self.name)

    def on_update(self):
        """Sync reorder_level into Item.reorder_levels so ERPNext's native
        reorder_item scheduler can auto-create Material Requests when stock
        falls below threshold. Skipped on inserts (after_insert handles those)."""
        if self.is_new() or not self.has_value_changed("reorder_level"):
            return
        from hmd_agro.hmd_agro.utils.reorder_sync import sync_reorder_level
        sync_reorder_level("Medicament", self.name)
