# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Aliment(Document):
    def onload(self):
        """ST5-17: populate the read-only `stock_courant` display field with
        the current Bin.actual_qty. Recomputed on every form load."""
        if not self.item:
            return
        from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_WAREHOUSE
        self.stock_courant = float(frappe.db.get_value("Bin",
            {"item_code": self.item, "warehouse": DEFAULT_WAREHOUSE},
            "actual_qty") or 0)

    def validate(self):
        if self.prix_unitaire is not None and self.prix_unitaire < 0:
            frappe.throw("Le prix unitaire ne peut pas etre negatif.")

    def after_insert(self):
        """Auto-create the matching ERPNext Item and link it. Without this hook,
        new Aliments wouldn't be visible to the daily Material Issue generator
        or the Item-valuation cost calculations planned in Phase B."""
        if not self.item:
            from hmd_agro.hmd_agro.setup.aliment_migration import _migrate_one_aliment
            _migrate_one_aliment(self)
        # Now that the Item link is set, sync any initial reorder_level
        if self.reorder_level:
            from hmd_agro.hmd_agro.utils.reorder_sync import sync_reorder_level
            sync_reorder_level("Aliment", self.name)

    def on_update(self):
        """Sync reorder_level into Item.reorder_levels so ERPNext's native
        reorder_item scheduler can auto-create Material Requests when stock
        falls below threshold. Skipped on inserts (after_insert handles those)."""
        if self.is_new() or not self.has_value_changed("reorder_level"):
            return
        from hmd_agro.hmd_agro.utils.reorder_sync import sync_reorder_level
        sync_reorder_level("Aliment", self.name)
