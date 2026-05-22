import frappe
from frappe.model.document import Document

from hmd_agro.hmd_agro.utils.config import get_config


class BilanLaitJournalier(Document):
    def validate(self):
        self.validate_taux()

    def validate_taux(self):
        max_tb = get_config("taux_tb_max_pct", default=10)
        max_tp = get_config("taux_tp_max_pct", default=10)
        if self.taux_tb_moyen and self.taux_tb_moyen > max_tb:
            frappe.throw(f"Le taux butyreux ne peut pas dépasser {max_tb}%.")
        if self.taux_tp_moyen and self.taux_tp_moyen > max_tp:
            frappe.throw(f"Le taux protéique ne peut pas dépasser {max_tp}%.")

    def on_update(self):
        self._propagate_taux_to_traites()

    def _propagate_taux_to_traites(self):
        """Fan out the daily herd TB/TP averages to every Traite of self.date.
        Fields stay aligned so rapport_mensuel's AVG(NULLIF(taux_tb, 0)) keeps
        returning the daily value without changing the report."""
        frappe.db.sql("""
            UPDATE `tabTraite`
            SET taux_tb = %s, taux_tp = %s
            WHERE date_traite = %s
        """, (self.taux_tb_moyen or 0, self.taux_tp_moyen or 0, self.date))
