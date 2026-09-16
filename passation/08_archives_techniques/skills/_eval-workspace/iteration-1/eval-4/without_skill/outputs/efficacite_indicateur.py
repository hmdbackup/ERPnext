"""
Efficacité alimentaire — KPI indicator with green / orange / red coloring.

This is a self-contained reference implementation matching how hmd_agro builds
the "Indicateurs" section of the Rapport Mensuel report
(hmd_agro/hmd_agro/report/rapport_mensuel/rapport_mensuel.py).

NOTE: In the live app this indicator ALREADY exists. See NOTES.md. This file
exists only to (a) demonstrate the exact formula and coloring decision in an
isolated, runnable form, and (b) provide a drop-in snippet should it ever need
to be re-added. It does NOT modify anything under hmd_agro/.

------------------------------------------------------------------------------
FORMULA
------------------------------------------------------------------------------
    Efficacité Alimentaire (sur MS) = Production laitière (L) / MS ingérée (kg)

  - Production = SUM(Traite.quantite_litres) over the period (cheptel-wide).
  - MS ingérée  = SUM over aliments of (kg distribué × ms_pct), i.e. the dry
                  matter actually consumed. In hmd_agro this is the SLE-derived
                  `cumulative_ms_cheptel` (net of Saisie Alimentation refusals/
                  corrections), so "MS ingérée = MS distribuée − refus".
  - Unit: L lait / kg MS.   Higher is better.

------------------------------------------------------------------------------
COLORING (one-directional, higher-is-better)
------------------------------------------------------------------------------
    value >= green_min (1.4)              -> "Green"
    orange_min (1.0) <= value < 1.4       -> "Orange"
    value < orange_min (1.0)              -> "Red"
    value is None or 0                    -> ""   (no signal -> uncolored)

Thresholds come from HMD Configuration (per-farm, editable):
    pfe_efficacite_min         default 1.4   (green if >=)
    pfe_efficacite_orange_min  default 1.0   (orange floor; red if <)
PFE reference: optimal 1.4 L/kg MS (Castellani 2014).
"""


def get_config(fieldname, default=None):
    """Stand-in for hmd_agro.hmd_agro.utils.config.get_config.

    In the app this reads `HMD Configuration` (a Single doctype) via
    frappe.db.get_single_value, falling back to `default` when the field is
    None/unset. Reproduced here so the snippet runs without Frappe.
    """
    try:
        import frappe  # noqa
        value = frappe.db.get_single_value("HMD Configuration", fieldname)
    except Exception:
        value = None
    return value if value is not None else default


def _kpi_ind(value, green_max=None, orange_max=None, green_min=None, orange_min=None):
    """One-direction indicator helper — VERBATIM from rapport_mensuel.py.

    Pass green_max + orange_max for a lower-is-better metric, or
    green_min + orange_min for a higher-is-better metric (efficacité uses this).
    Returns "" when value is None/0 (no signal possible -> cell left uncolored).
    """
    if value is None or value == 0:
        return ""
    if green_max is not None:
        if value <= green_max:
            return "Green"
        if value <= orange_max:
            return "Orange"
        return "Red"
    if green_min is not None:
        if value >= green_min:
            return "Green"
        if value >= orange_min:
            return "Orange"
        return "Red"
    return ""


def efficacite_alimentaire(production_litres, ms_ingeree_kg):
    """Return the efficacité alimentaire (L lait / kg MS), or 0 when MS is 0.

    Mirrors rapport_mensuel.py `_period_kpis`:
        "eff_alim": round(prod_ / ms_total_, 2) if ms_total_ else 0
    """
    if not ms_ingeree_kg:
        return 0
    return round(production_litres / ms_ingeree_kg, 2)


def build_efficacite_row(production_litres, ms_ingeree_kg,
                         valeur_m1=None, get_config=get_config):
    """Build the KPI row dict consumed by the report.

    The report's JS formatter colors the `valeur` cell from `data.indicator`
    (Green/orange/red) and the `delta_pct` cell from `direction`
    ("up" = higher-better). This is exactly how _indicateurs emits the row:

        row("Efficacité Alimentaire (sur MS)", cur["eff_alim"], "L/kg MS",
            indicator=_kpi_ind(cur["eff_alim"], green_min=cfg_eff_min,
                               orange_min=cfg_eff_omn),
            valeur_m1=m1["eff_alim"], direction="up")
    """
    # Per-farm thresholds (editable in HMD Configuration -> Seuils PFE).
    cfg_eff_min = float(get_config("pfe_efficacite_min", default=1.4))   # green if >=
    cfg_eff_omn = float(get_config("pfe_efficacite_orange_min", default=1.0))  # orange floor

    valeur = efficacite_alimentaire(production_litres, ms_ingeree_kg)
    indicator = _kpi_ind(valeur, green_min=cfg_eff_min, orange_min=cfg_eff_omn)

    delta_pct = None
    if valeur_m1 not in (None, 0, 0.0) and valeur is not None:
        delta_pct = round((valeur - valeur_m1) / valeur_m1 * 100, 1)

    return {
        "indicateur": "Efficacité Alimentaire (sur MS)",
        "valeur": valeur,
        "valeur_m1": valeur_m1,
        "delta_pct": delta_pct,
        "unite": "L/kg MS",
        "indicator": indicator,   # -> green/orange/red coloring of `valeur`
        "direction": "up",        # higher is better -> colors the Δ cell
    }


if __name__ == "__main__":
    # Demonstrate the three color bands against the default farm thresholds.
    # production / MS ingérée pairs chosen to land in each band.
    examples = [
        ("Green  (>=1.4)", 1500.0, 1000.0),   # 1.50 -> Green
        ("Orange (1.0-1.4)", 1200.0, 1000.0),  # 1.20 -> Orange
        ("Red    (<1.0)", 800.0, 1000.0),      # 0.80 -> Red
        ("No data (MS=0)", 1000.0, 0.0),       # 0    -> "" (uncolored)
    ]
    print(f"{'case':18} {'prod(L)':>9} {'MS(kg)':>8} {'eff':>6}  indicator")
    for label, prod, ms in examples:
        row = build_efficacite_row(prod, ms)
        print(f"{label:18} {prod:9.1f} {ms:8.1f} {row['valeur']:6} "
              f" {row['indicator'] or '(none)'}")
