"""Workspace dashboard KPI cards.

Mirrors the per-period KPIs from rapport_mensuel `_indicateurs` but at fixed
windows tuned for the workspace card use case:
    - PL/VL: yesterday (single day, matches Production Journaliere pattern)
    - L/C:   7-day rolling (smoother than 1 day so PFE seuils make sense)

Reuses canonical primitives so the formulas can never drift from the report:
    effectif_on_date         — herd reconstruction from events
    _aliment_data_per_lot    — historical ration walker (gives concentré kg)
    _kpi_ind_range           — Green/Orange/Red mapping using PFE seuils
"""
import frappe
from frappe.utils import add_days, getdate, today

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.live_state import effectif_on_date


def _prod_sum(start, end):
    return float(frappe.db.sql(
        "SELECT SUM(quantite_litres) FROM `tabTraite` "
        "WHERE date_traite BETWEEN %s AND %s",
        (start, end))[0][0] or 0)


@frappe.whitelist()
def get_pl_vl():
    """PL/VL — litres of milk per lactating cow, yesterday."""
    yesterday = add_days(today(), -1)
    prod = _prod_sum(yesterday, yesterday)
    vl = effectif_on_date(yesterday)["Vaches - Lact."]
    ratio = round(prod / vl, 1) if vl else 0
    return {"value": ratio, "fieldtype": "Float"}


@frappe.whitelist()
def get_lc_ratio():
    """L/C — litres of milk per kg of concentré over a 7-day rolling window
    (ending yesterday). Indicator color uses the PFE seuils so the card stays
    consistent with the Indicateurs section of the monthly report."""
    from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import (
        _aliment_data_per_lot, _kpi_ind_range,
    )
    # _aliment_data_per_lot does date arithmetic (date - date), so pass date
    # objects, not strings — add_days(today(), ...) returns strings.
    end = getdate(add_days(today(), -1))
    start = getdate(add_days(end, -6))  # 7-day window inclusive

    prod = _prod_sum(start, end)
    d = _aliment_data_per_lot(start, end)
    concentre = d["cumulative_concentre_cheptel"] if d else 0
    ratio = round(prod / concentre, 2) if concentre else 0

    indicator = _kpi_ind_range(
        ratio,
        green_low=float(get_config("pfe_lc_optimal_min", default=2.0)),
        green_high=float(get_config("pfe_lc_optimal_max", default=2.4)),
        low_alarm=float(get_config("pfe_lc_alarm_min", default=1.5)),
        high_alarm=float(get_config("pfe_lc_alarm_max", default=3.0)),
    )
    return {"value": ratio, "fieldtype": "Float", "indicator": indicator}
