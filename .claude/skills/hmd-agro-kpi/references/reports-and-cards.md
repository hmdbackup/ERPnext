# Reports & Cards — HMD AGRO reporting surfaces

The desk-facing reporting layer is built from four Script Reports, eleven Number Cards,
one Dashboard Chart, and four custom desk pages — all under module **HMD AGRO**.
Underneath them sits `utils/live_state.py`, the historical-truth reconstruction layer that
every report (and the Custom number cards) draws on so any past-date figure is computed
from events, never read from the live `Animal.etat_*` fields.

KPI formulas and PFE seuils are **not** restated here — see `kpi-formulas.md` and the
PFE seuils reference. This file is the map of *where the surfaces live and how to add one*.

All four `execute()` functions are wrapped with `@normalize_precision`
(`utils/report_format.py`), which forces `precision=1` on every Float/Percent/Currency
column and pre-formats summary cards (French space-thousands).

---

## Reports

All four are **Script Report** (`report_type: "Script Report"`, `is_standard: "Yes"`).
The `.json` carries only metadata + `ref_doctype`; columns/filters are produced in Python,
and the filter widgets live in the sibling `.js`.

### Rapport Mensuel — `report/rapport_mensuel/rapport_mensuel.py`
`execute(filters)` at **`:35`**. `ref_doctype: Animal`. The workhorse: a single report that
dispatches to six section builders. Imported Excel days (via `utils/import_rapport`) take
priority over live reconstruction in single-day Effectif/Lot views.

Filters (from `rapport_mensuel.js`): `date` (cursor, with ◀/▶ day-arrows), `section`
Select, `granularite` Select (`Quinzaine|Quotidien|Hebdomadaire`, shown for
Alimentation/Production/Tout), `periode` Select (`Jour|Hebdomadaire`, shown for Production
par Lot/Tout), and a hidden `effectif_mode` (`Jour|Mois`) toggled by the **"État du Mois"**
custom button (visible only for Effectif/Tout).

| `section` | mode filter that applies | output |
|-----------|--------------------------|--------|
| **Tout** | all (composes Effectif+Production+Indicateurs into a flat label/valeur list) | `_tout` |
| **Effectif** | `effectif_mode` Jour (single-day events) / Mois (month-to-date, capped at today for current month) | per-category herd table |
| **Production** | `granularite` adds Q1/Q2 or S1..Sn summary rows | daily milk L, VL/day, Moy/VL, TB/TP + bar chart |
| **Production par Lot** | `periode` Jour (Eff/D-1/D/Moyenne) vs Hebdomadaire (Sem. préc./Sem. act./Δ%/Moy/lact/jour, ISO-week) | per-lot litres, imported-priority in Jour mode only |
| **Alimentation** | `granularite` drives period columns | per-aliment kg/lot snapshot, MS Total/Tête, Efficacité L/kg MS, Coût Total DT |
| **Indicateurs** | (period = date_debut→date_filter, with M-1 column) | Effectif/Production/Alimentation/Économique KPI rows |

### Controle Laitier — `report/controle_laitier/controle_laitier.py`
`execute(filters)` at **`:10`**. `ref_doctype: Traite`. Per-cow milk tracking over the
cohort of active VACHEs that have ever been milked. Two modes via `view_mode`:
- **Conversion** (default): `reference_date` + `lot` MultiSelect → 3-day grid (J-2, J-1, J),
  per-cow Delta %, Moy 3j, lot-on-date, TOTAL row.
- **CL**: `from_date`/`to_date` range + `lot` → one column per day, Total, Moy/j, daily
  bar chart, and a 4-item summary (Production Totale, Animaux, Moy/jour, Moy/animal).

### Rapport Reproduction — `report/rapport_reproduction/rapport_reproduction.py`
`execute(filters)` at **`:23`**. `ref_doctype: Animal`. Multi-section, all lookups capped at
`date` (= "as of date X"). Sections via `section` Select:
- **Reproduction** (default): one row per VACHE/GENISSE present on date — DIM, état
  lactation/gestation, IA1..IA5, V-IA1/V-Iad, IVV, gestation, persistance, statut repro,
  + herd-level repro KPI summary (IVIA1/IVIF/IVV/IC).
- **Performance IA**: per-month IA ranks (NB/VG+/% at rank 1/2/3/>3), births, losses,
  avortements for the year, + line chart + summary.
- **Bilan Annuel**: one row per year (earliest event year → date_filter year); current
  year partial. Vêlages, IA distribution, VP/VL, taux réforme, IVV/IVIA1/IVIF, prod, L/C.

### Allotement Animaux — `report/allotement_animaux/allotement_animaux.py`
`execute(filters)` at **`:10`**. `ref_doctype: Animal`. Lot-assignment worksheet for active
VACHEs: yesterday's 3-day production grid + DIM + jours gestation + `suggestion_lot`
(computed by `_get_suggestion` from DIM/lactation rang/gestation using `get_config` seuils).
When `filters["session"]` is set, renders a frozen **Allotment Session** snapshot (only cows
that changed lot). Whitelisted helpers: `get_lots_capacity`, `update_lot_seuils`.

---

## Number Cards & Charts

Eleven Number Cards + one Dashboard Chart, all `module: HMD AGRO`. The **Custom** cards call
whitelisted functions returning `{"value": ..., "fieldtype": ...}` (the `get_*` datasources
in `utils/dashboard_kpis.py` also add `"indicator"`). **Document Type** cards are plain
filtered counts on the *live* `Animal`/`Lactation` tables — correct here because cards show
"now"; this is the deliberate contrast with reports, which reconstruct past state.

| Card | type | source |
|------|------|--------|
| Animaux Actifs | Document Type | `Animal` count, `statut=ACTIF` |
| Gestantes | Document Type | `Animal` count, `etat_gestation=GESTANTE` + `statut=ACTIF` |
| Lactations en Cours | Document Type | `Lactation` count, `statut=EN_COURS` |
| Sous Traitement | Document Type | `Animal` count, `attente_lait_active=1` |
| Attente Lait | Document Type | `Animal` count, `attente_lait_active=1` *(dup of Sous Traitement)* |
| Alertes en Attente | Custom | `doctype.alerte.alerte.get_alertes_count` (`statut=NOUVELLE`) |
| Production Journaliere | Custom | `doctype.traite.traite.get_production_journaliere` (yesterday total) |
| PL_VL / PL/VL | Custom | `dashboard_kpis.get_pl_vl` **`:28`** *(both `pl_vl` & `lait_par_vache_lactante`)* |
| L_C / L/C 7j | Custom | `dashboard_kpis.get_lc_ratio` **`:38`** *(both `l_c` & `lait_par_concentre`)* |

`get_pl_vl` = milk/VL yesterday via `effectif_on_date`. `get_lc_ratio` = milk per kg
concentré over a 7-day window, reusing report primitives `_aliment_data_per_lot` +
`_kpi_ind_range` so the card can never drift from the Indicateurs section.

**Dashboard Chart** — `dashboard_chart/production_lait_journaliere`: native Frappe chart,
`document_type: Traite`, `chart_type: Sum` of `quantite_litres` `based_on date_traite`,
Bar, timeseries Daily over Last Month (no Python).

---

## `live_state.py` — the historical truth layer

**Rule, loud:** effectif, per-lot, and per-category counts for any date are reconstructed
from event doctypes (Velage / Lactation / Insemination / Avortement). **Never read
`Animal.categorie` / `etat_lactation` / `etat_gestation` for past dates** — those fields
hold "right now" and drift if a hook fails. Every `count_*` helper and every report's
historical column routes through these functions (`utils/live_state.py`):

- `states_on_date(names, date)` **`:42`** — (categorie, etat_lactation, etat_gestation) per present animal, walked from events. Single source of truth.
- `state_on_date(name, date)` **`:145`** — single-animal wrapper.
- `effectif_on_date(date)` **`:179`** — per-category herd counts (CATEGORIES) at a date.
- `lactantes_per_lot_on_date(date)` **`:152`** — lactating-cow count per lot (uses `lot_on_date` audit log).
- `count_velages(date)` **`:202`** — vêlages bucketed by post-vêlage state.
- `count_naissances(date)` **`:221`** — live births, bucketed by reconstructed category.
- `count_avortements_mort_nes(date)` **`:238`** — avortements (mother's pre-event state) + mort-nés by sex.
- `count_exits(date, statut)` **`:268`** — VENDU/MORT/REFORME (qty, prix) by D-1 state.
- `count_achats(date)` **`:292`** — purchased animals by state on entry day.
- `count_changements_cat(date)` **`:307`** — symmetric Cat(+)/Cat(−) ledger from tarissement, IA réussie on génisse, vêlage.

Helpers: `resolve_col`, `empty_row`, `set_total`, and the `CATEGORIES` list.

---

## Custom desk pages

Four pages under `hmd_agro/page/` (module HMD AGRO, `standard: Yes`):

- **centre_alertes** ("Centre Alertes") — monitoring console for pending Alerte records (not data entry).
- **import_traites** ("Import Traites") — bulk import / paste of Traite (milking) records.
- **saisie_alimentation** ("Saisie Alimentation") — daily ration-distribution entry per lot; posts SLE `RATION_CORRECTION_` rows that feed the Alimentation report.
- **saisie_traite** ("Saisie Traite") — fast per-cow milk-quantity capture for a milking session.

---

## How to add a report or number card

**New report**
1. Create `report/<slug>/<slug>.{py,json,js}` with `module: "HMD AGRO"`, `report_type: "Script Report"`, `is_standard: "Yes"`, and a sensible `ref_doctype`.
2. Define `execute(filters=None)` returning `(columns, data[, message, chart, summary])`; decorate it with `@normalize_precision` from `utils/report_format` for consistent number display.
3. For any historical figure, call `live_state` (`effectif_on_date`, `lactantes_per_lot_on_date`, `count_*`) — do **not** read `Animal.etat_*` for past dates.
4. Pull thresholds/seuils from `utils/config.get_config(field, default=...)` (never hard-code PFE constants).
5. If a `.js` filter needs a config value at render time, add the field to `boot.JS_FIELDS` (`hmd_agro/boot.py`) so it lands in `frappe.boot.hmd_config.<field>` — no extra HTTP call.

**New number card**
1. Custom card → add a `@frappe.whitelist()` function returning `{"value": ..., "fieldtype": ...}` (add `"indicator"` for Green/Orange/Red); put KPI math in `utils/dashboard_kpis.py` and reuse report primitives so formulas stay single-sourced. Document Type card → just set `document_type` + `filters_json`.
2. Register the **Number Card** with `module: "HMD AGRO"` so the hooks `fixtures` filter (`{"dt": "Number Card", "filters": [["module", "=", "HMD AGRO"]]}`) catches it.
3. Run `bench export-fixtures --app hmd_agro` to persist it — same applies to Dashboard Charts.
