# =============================================================================
# PROPOSED ADDITION to:
#   hmd_agro/hmd_agro/utils/dashboard_kpis.py
#
# This is NOT a standalone module. The snippet below is meant to be appended to
# the existing `dashboard_kpis.py`, which already imports:
#
#     import frappe
#     from frappe.utils import add_days, getdate, today
#     from hmd_agro.hmd_agro.utils.live_state import effectif_on_date
#
# and already defines the `_prod_sum(start, end)` helper.
#
# IMPORTANT — read first:
# The metric requested ("average milk production per lactating cow for the herd,
# yesterday") is *exactly* what the existing `get_pl_vl()` already computes:
#
#     total litres milked yesterday  /  number of lactating cows on that date
#
# So the cleanest solution is to simply add a NEW Number Card that points at the
# existing, already-tested `get_pl_vl` method — no new Python is required at all
# (see NOTES.md, "Option A").
#
# The function below ("Option B") is provided only in case you want a card with
# its own distinct datasource (e.g. a clearer label/name in code, or to add a
# color "indicator" later). It is a thin, intention-revealing alias that reuses
# the same canonical primitives (`_prod_sum`, `effectif_on_date`) so the formula
# can never drift from PL/VL or from the monthly report.
# =============================================================================


@frappe.whitelist()
def get_lait_moyen_par_vl():
    """Average milk production per lactating cow for the herd — yesterday.

    Definition (identical to PL/VL):
        sum(quantite_litres milked yesterday)  /  nb lactating cows on that date

    - Production: total litres from `Traite` for yesterday's date.
    - Denominator: "Vaches - Lact." count reconstructed from herd events via
      `effectif_on_date` (the single source of truth — never read
      Animal.etat_lactation directly for a past date, it can drift).
    - Guards against division by zero (returns 0 when no lactating cows).

    Returns the dict shape expected by a Custom Number Card:
        {"value": <float>, "fieldtype": "Float"}
    """
    yesterday = add_days(today(), -1)
    prod = _prod_sum(yesterday, yesterday)
    vl = effectif_on_date(yesterday)["Vaches - Lact."]
    moyenne = round(prod / vl, 1) if vl else 0
    return {"value": moyenne, "fieldtype": "Float"}
