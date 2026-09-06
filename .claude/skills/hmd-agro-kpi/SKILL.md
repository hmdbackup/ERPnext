---
name: hmd-agro-kpi
description: >-
  Technico-economic KPIs, reports, and the daily/monthly herd report ('bilan' /
  Rapport Journalier) for the HMD AGRO dairy app (`hmd_agro`). Use this WHENEVER
  building or modifying reports, Number Cards, Dashboard Charts, allotement
  suggestions, or ANY dairy-indicator computation — production par vache
  (présente vs lactante), L/C, C/L, efficacité alimentaire (L/kg MS), lactation
  305j, persistance, TB/TP, IVIA1/IVIF/IVV, %3IA+, indice coïtal, TR1IA, taux de
  réforme, GMQ, THI. Also use when reproducing the Excel 'dispositif' structure,
  computing effectif via live_state reconstruction, or wiring the PFE seuils
  (green/orange/red) that color indicators. Trigger for asks like 'add a KPI',
  'build a dairy report', 'compute efficacité alimentaire', 'why is this
  indicator red', 'reproduce the monthly bilan'. Pair with hmd-agro-dev (where
  report code lives) and hmd-agro-domain (the events the KPIs measure).
---

# HMD AGRO — KPIs & Reporting

This app's analytical job is to reproduce — and improve on — the farm's Excel
**"dispositif"** (the *Rapport Journalier / Mensuel de l'élevage*) and the
technico-economic indicators from the founding PFE study. Two things make HMD's
KPIs specific: every per-cow metric is computed for **two populations**, and the
indicator thresholds are **configurable** (PFE seuils) and **color-coded**.

## Rule 1 — two populations: *vache présente* vs *vache lactante*

Almost every per-cow KPI is reported **both ways**, and they differ a lot:

- **par vache présente** — divided by the average number of cows *present* (whole
  herd, lactating + dry). This is the herd-economics view.
- **par vache lactante** — divided by the number of *lactating* cows only. This is
  the production-performance view.

Always state which denominator a metric uses; never silently mix them. (Example
day from the dispositif: concentré/tête présente 8.994 vs lactante 9.578; moyenne
16.069 L présente vs 18.416 L lactante.)

## Rule 2 — effectif and per-lot counts are *reconstructed*, never read live

For any date, get herd counts from **`utils/live_state.py`**
(`effectif_on_date`, `lactantes_per_lot_on_date`, `count_velages`, …), which
replays events (Velage/Lactation/Insemination/Avortement). **Never** read
`Animal.categorie/etat_lactation/etat_gestation` for a past date — live fields are
"now" only and drift. This is the rule every report follows.

## Rule 3 — thresholds are config (PFE seuils), and indicators are tri-color

Indicator coloring uses `HMD Configuration` `pfe_*` fields via `get_config`
(green = optimal, orange = warning, red = alarm). Never hardcode a target.

| Indicator | Green (optimal) | Orange | Red (alarm) | Config fields |
|---|---|---|---|---|
| **L/C** (lait/concentré) | 2.0–2.4 | between green & alarm | <1.5 or >3.0 | `pfe_lc_optimal_min/max`, `pfe_lc_alarm_min/max` |
| **Efficacité alimentaire** | ≥1.4 | 1.0–1.4 | <1.0 | `pfe_efficacite_min`, `pfe_efficacite_orange_min` |
| **Persistance** | 0.85–0.95 | between | <0.7 or >1.10 | `pfe_persistance_min/max`, `pfe_persistance_alarm_min/max` |
| **%3IA+** | ≤15% | 15–25% | >25% | `pfe_3ia_plus_max`, `pfe_3ia_plus_orange_max` |

## KPI families (formulas + targets → `references/kpi-formulas.md`)

- **Production:** production/vache (présente & lactante), `lactation_305j`
  (Fleischmann standardization), persistance, moyenne L/tête, pic (first 150 DIM).
- **Feed-economic:** **L/C** (target **2–2.4**), **C/L** (inverse), **efficacité
  alimentaire** = lait / MSI where **MSI = MS distribuée − refus** (target **1.4**
  L/kg MS), concentré/tête, and the cost rows **DT/L** & **DT/vache** for
  concentré / fourrage / alimentaire / total (Alim+MO+Traction).
- **Qualité:** TB (taux butyreux) / TP (taux protéique) — daily herd averages in
  `Bilan Lait Journalier`, validated `≤ taux_tb_max_pct/taux_tp_max_pct` (10).
- **Reproduction:** **IVIA1**, **IVIF** (target **90 j**; % >110 j should be <15%),
  **IVV** (~365 j), **%3IA+** (<15%), **TR1IA** (>60%), **indice coïtal** (≤1.6),
  age au 1ᵉʳ vêlage (~24 mo), taux de réforme (20–30%).
- **Croissance:** **GMQ** = (poids − poids précédent) / jours entre pesées.
- **Environnement:** **THI** = `1.8·Ta − (1 − HR)·(Ta − 14.3) + 32`; bands: confort,
  stress modéré (72–79), sévère.

## The daily/monthly report (the bilan)

The app's `Rapport Mensuel` (and the operational daily view) reproduces the Excel
dispositif's structure: **Évolution effectif par catégorie**, **Alimentation &
Allaitement**, **Production** (commercialisé / perte / auto-consommation /
stock), **Frais & coût** (concentré / fourrage / MO / traction), **Indicateurs
des vaches** (the KPI block, présente & lactante), **Production & Moyennes par
lot**, **Ration par lot** (with MS%, refus, efficacité), plus CA and
**Température/Humidité/THI**. Structure detail: `references/daily-report-structure.md`.

## Where report code lives

4 reports (`Rapport Mensuel`, `Controle Laitier`, `Rapport Reproduction`,
`Allotement Animaux`), Number Cards backed by `utils/dashboard_kpis.py`, Dashboard
Charts, and 4 desk pages. To add a KPI/report, see
`references/reports-and-cards.md` and hmd-agro-dev (module = `HMD AGRO`, export
fixtures, add JS-needed config to `boot.JS_FIELDS`).

## Reference files

- `references/kpi-formulas.md` — every indicator with its **exact formula,
  target/objectif, and source** (PFE study + Excel dispositif), grouped by family.
  Cite formulas from here.
- `references/daily-report-structure.md` — the bilan's column groups and indicator
  rows (what a daily/monthly report must reproduce), with sample values and the
  real client names (STIAL, Délice, Soprolait).
- `references/reports-and-cards.md` — the existing reports, number cards, charts,
  desk pages, the `live_state` reconstruction layer, and how to add a new one.
