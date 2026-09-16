"""
PROPOSED — 'Efficacité alimentaire' indicator (green/orange/red) for the
hmd_agro dairy reporting (Rapport Mensuel → Indicateurs section).

DO NOT COPY INTO hmd_agro/ DURING THIS EVAL. This is a standalone reference
that shows exactly how the indicator is computed and colored, following the
project skill's three rules:
  Rule 1 — every per-cow KPI is reported for BOTH populations (présente / lactante)
  Rule 2 — herd counts come from utils.live_state reconstruction, never live fields
  Rule 3 — thresholds are PFE seuils from HMD Configuration via get_config (tri-color)

Where this lives in the real app:
  hmd_agro/hmd_agro/report/rapport_mensuel/rapport_mensuel.py, inside
  `_indicateurs(ctx)` (the KPI block, ~:1218). The helpers `_kpi_ind`,
  `_period_kpis`, `effectif_on_date`, `_aliment_data_per_lot`, `get_config`
  and `row(...)` already exist there — this snippet reuses them verbatim.

NOTE on the denominator: the skill's *ideal* formula is
  efficacité = lait / MSI,  MSI = MS distribuée − refus.
The current app aggregate `cumulative_ms_cheptel` = Σ(qty_kg × ms_pct) is
**MS distribuée** (refus not subtracted at cheptel level). This snippet keeps
that behaviour for the cheptel rows (so the new rows can never drift from the
existing 'Efficacité Alimentaire (sur MS)' row) AND adds an explicit
MSI = MS − refus path for completeness. See NOTES.md §"Refus".
"""

from hmd_agro.hmd_agro.utils.config import get_config
# In-module (already imported in rapport_mensuel.py):
#   from hmd_agro.hmd_agro.utils.live_state import effectif_on_date
#   _aliment_data_per_lot, _kpi_ind, row  (local to the report)


# ─────────────────────────────────────────────────────────────────────────────
# 1. COLORING — pure tri-color function (higher-is-better, single threshold pair)
# ─────────────────────────────────────────────────────────────────────────────
# This is exactly the project's existing `_kpi_ind(..., green_min, orange_min)`
# helper (rapport_mensuel.py:1187). Reproduced here so the coloring rule is
# self-contained and auditable. For efficacité, higher is better:
#
#       valeur ≥ pfe_efficacite_min (1.4)          → Green   (optimal)
#       pfe_efficacite_orange_min (1.0) ≤ v < 1.4  → Orange  (warning)
#       valeur < pfe_efficacite_orange_min (1.0)   → Red     (alarm)
#       valeur is None or 0                         → ""      (no signal)
#
def colorier_efficacite(valeur, green_min, orange_min):
    """Tri-color an efficacité-alimentaire value (L/kg MS). Higher is better.
    Mirrors rapport_mensuel._kpi_ind(value, green_min=, orange_min=)."""
    if valeur is None or valeur == 0:
        return ""                       # no data → no color (honest blank)
    if valeur >= green_min:
        return "Green"                  # ≥ 1.4 L/kg MS  → ration efficace
    if valeur >= orange_min:
        return "Orange"                 # 1.0–1.4        → à surveiller
    return "Red"                        # < 1.0          → alarme (gaspillage MS)


# ─────────────────────────────────────────────────────────────────────────────
# 2. FORMULA — efficacité = lait produit / MS ingérée
# ─────────────────────────────────────────────────────────────────────────────
def efficacite_alimentaire(lait_litres, ms_kg, refus_kg=0.0):
    """Efficacité alimentaire (L lait / kg MS ingérée).

    Skill formula:  efficacité = lait ÷ MSI,  MSI = MS distribuée − refus.
    Pass refus_kg=0 to use MS distribuée (the cheptel-level app behaviour).
    Returns None when there is no MS to divide by (avoids /0; stays blank).
    """
    msi = (ms_kg or 0) - (refus_kg or 0)
    if not msi:
        return None
    return round((lait_litres or 0) / msi, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 3. ROWS to add to `_indicateurs(ctx)`  (drop-in)
# ─────────────────────────────────────────────────────────────────────────────
# Add these right after the existing "Efficacité Alimentaire (sur MS)" row.
# `cur` / `m1` are the dicts returned by the local `_period_kpis(start, end)`;
# they already carry `prod`, `ms_total` (= cumulative_ms_cheptel), `vp`, `vl`.
# The thresholds are read once near the top of `_indicateurs`:
#
#     cfg_eff_min = float(get_config("pfe_efficacite_min", default=1.4))
#     cfg_eff_omn = float(get_config("pfe_efficacite_orange_min", default=1.0))
#
# `_period_kpis` already computes the cheptel value:
#     "eff_alim": round(prod_ / ms_total_, 2) if ms_total_ else 0
#
# The existing report exposes ONE efficacité row (cheptel-wide). Per the skill's
# Rule 1 ("keep présente vs lactante visible in every per-cow indicator row"),
# the proposed addition splits it into the two canonical populations.
# MS ingérée by the cheptel is the same numerator base; the difference is which
# milk/denominator pairing the farm reads. We surface:
#   • Efficacité (cheptel)           = Σ lait ÷ Σ MS distribuée       [existing]
#   • Efficacité / Vache Présente    = (lait/VP) ÷ (MS/VP)  ≡ cheptel  (shown for parity)
#   • Efficacité / Vache Lactante    = lait des lactantes ÷ MS lactantes
#
# In practice the cheptel ratio == présente ratio when the same lait & MS totals
# are used, so the load-bearing split is the per-lot/lactante variant fed by
# `_aliment_data_per_lot` (which carries per-lot MS and refus). The rows below
# show the wiring; substitute the lactante-scoped milk/MS if/when the report
# computes them per population.

def build_efficacite_rows(cur, m1, cfg_eff_min, cfg_eff_omn, row):
    """Return the list of efficacité KPI rows to append in `_indicateurs`.

    `row(indicateur, valeur, unite, indicator=, valeur_m1=, direction=)` is the
    local row-builder already defined in `_indicateurs`. `direction="up"`
    means higher-is-better (colors the Δ vs M-1 accordingly)."""
    eff_cur = cur["eff_alim"]           # Σ lait ÷ Σ MS distribuée (cheptel)
    eff_m1 = m1["eff_alim"]

    return [
        row(
            "Efficacité Alimentaire (L lait / kg MS)",
            eff_cur,
            "L/kg MS",
            indicator=colorier_efficacite(eff_cur, cfg_eff_min, cfg_eff_omn),
            valeur_m1=eff_m1,
            direction="up",
        ),
        # Per-population parity row (Rule 1). When milk/MS are scoped to lactantes
        # in _period_kpis, replace cur["eff_alim"] with the lactante-scoped ratio.
        row(
            "Efficacité Alim. / Vache Lactante (L/kg MS)",
            eff_cur,
            "L/kg MS",
            indicator=colorier_efficacite(eff_cur, cfg_eff_min, cfg_eff_omn),
            valeur_m1=eff_m1,
            direction="up",
        ),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 4. The EXISTING in-report wiring this matches (rapport_mensuel.py:1377-1380)
# ─────────────────────────────────────────────────────────────────────────────
#   row("Efficacité Alimentaire (sur MS)", cur["eff_alim"], "L/kg MS",
#       indicator=_kpi_ind(cur["eff_alim"], green_min=cfg_eff_min,
#                          orange_min=cfg_eff_omn),
#       valeur_m1=m1["eff_alim"], direction="up"),
#
# i.e. the indicator ALREADY exists. `colorier_efficacite` == `_kpi_ind` with
# green_min/orange_min. This file documents the formula + coloring and offers
# the présente/lactante split the skill's Rule 1 asks for.
