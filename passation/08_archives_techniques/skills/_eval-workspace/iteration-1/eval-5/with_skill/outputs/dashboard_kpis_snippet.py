# Proposed addition to:
#   hmd_agro/hmd_agro/utils/dashboard_kpis.py
#
# Number-card datasource for the workspace KPI card:
#   "Moyenne de production par vache lactante (hier)"
#   = average milk production per LACTATING cow for the whole herd, yesterday.
#
# This is the "production / vache lactante" production-performance KPI
# (kpi-formulas.md > Production): Σ lait du troupeau ÷ nb de vaches lactantes.
#
# It is the SAME math the app already ships as `get_pl_vl` (the "PL/VL" card).
# We keep that single-source convention: the snippet below is written so it can
# either (a) just reuse the existing `get_pl_vl`, or (b) be added as a thin,
# explicitly-named alias for a dedicated card. Both forms are shown.
#
# Conventions applied (see NOTES.md for citations):
#   - Custom number-card datasource returns {"value": ..., "fieldtype": ...}
#     (reports-and-cards.md "New number card" step 1).
#   - Effectif (lactating-cow count) is RECONSTRUCTED from events via
#     live_state.effectif_on_date(date) — never read from Animal.etat_lactation
#     for a past date (SKILL.md Rule 2; reports-and-cards.md live_state section).
#   - The lactating-cow denominator is the "Vaches - Lact." bucket of
#     effectif_on_date — the *vache lactante* population, not *présente*
#     (SKILL.md Rule 1: always state the denominator).
#   - "Yesterday" = add_days(today(), -1), matching get_pl_vl / Production
#     Journaliere (dashboard_kpis.py module docstring).
#   - Reuses the canonical primitives _prod_sum + effectif_on_date so the card
#     can never drift from the Indicateurs section of rapport_mensuel.
#
# NOTE on imports: these already exist at the top of dashboard_kpis.py:
#       import frappe
#       from frappe.utils import add_days, today
#       from hmd_agro.hmd_agro.utils.live_state import effectif_on_date
#   and `_prod_sum(start, end)` is already defined in that module.


import frappe
from frappe.utils import add_days, today

from hmd_agro.hmd_agro.utils.live_state import effectif_on_date


def _prod_sum(start, end):
    # Already defined in dashboard_kpis.py — reproduced here only so this
    # snippet is self-contained. Do NOT duplicate it when merging; reuse the
    # existing one.
    return float(frappe.db.sql(
        "SELECT SUM(quantite_litres) FROM `tabTraite` "
        "WHERE date_traite BETWEEN %s AND %s",
        (start, end))[0][0] or 0)


@frappe.whitelist()
def get_moyenne_production_vache_lactante():
    """Moyenne de production par vache lactante — litres de lait du troupeau
    par vache lactante, hier.

    Denominator = *vache lactante* (lactating cows only), reconstructed from
    events via live_state, NOT read live. Formula (kpi-formulas.md > Production,
    "Production / vache lactante"):

        Σ lait du troupeau (hier) ÷ nb de vaches lactantes (hier)

    (`get_pl_vl` is defined in the same module, dashboard_kpis.py, so the
    delegation below resolves once this function is appended there.)

    Identical math to the shipped `get_pl_vl`; exposed under an explicit name
    for a dedicated "Moyenne / VL" card. Returns the Custom-card payload
    {"value", "fieldtype"} expected by Frappe Number Cards.

    There is no PFE seuil for production/VL in the thresholds table
    (kpi-formulas.md), so this card carries NO "indicator" key — adding a
    green/orange/red color would mean hardcoding a target, which SKILL.md
    Rule 3 forbids.
    """
    # Single-source: delegate to the shipped `get_pl_vl`, which already is
    # "Σ lait (hier) ÷ effectif_on_date(hier)['Vaches - Lact.']". Delegating
    # (rather than re-implementing) makes 'can never drift' literally true.
    return get_pl_vl()


# Inlined equivalent, if you prefer the named card NOT to depend on get_pl_vl
# (identical result — kept here only to make the formula explicit):
#
#     yesterday = add_days(today(), -1)
#     prod = _prod_sum(yesterday, yesterday)
#     vl = effectif_on_date(yesterday)["Vaches - Lact."]  # vache LACTANTE denom.
#     moyenne = round(prod / vl, 1) if vl else 0
#     return {"value": moyenne, "fieldtype": "Float"}


# --- Alternative (preferred if a new card is overkill) -----------------------
# The app already ships exactly this metric as `get_pl_vl`. If you only need
# the card and not a new function name, point the new Number Card's `method`
# straight at the existing datasource instead of adding the function above:
#
#     "method": "hmd_agro.hmd_agro.utils.dashboard_kpis.get_pl_vl"
#
# get_pl_vl (current source) for reference:
#
#     @frappe.whitelist()
#     def get_pl_vl():
#         """PL/VL — litres of milk per lactating cow, yesterday."""
#         yesterday = add_days(today(), -1)
#         prod = _prod_sum(yesterday, yesterday)
#         vl = effectif_on_date(yesterday)["Vaches - Lact."]
#         ratio = round(prod / vl, 1) if vl else 0
#         return {"value": ratio, "fieldtype": "Float"}
