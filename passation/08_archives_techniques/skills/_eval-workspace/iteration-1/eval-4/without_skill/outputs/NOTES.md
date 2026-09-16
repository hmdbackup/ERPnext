# Efficacité alimentaire — indicator + green/orange/red coloring

## TL;DR — it already exists

The `hmd_agro` app **already implements** an "Efficacité alimentaire" indicator,
colored green/orange/red against per-farm thresholds, in **two** places:

1. **Indicateurs KPI table** (the colored one) — row
   `"Efficacité Alimentaire (sur MS)"` in
   `hmd_agro/hmd_agro/report/rapport_mensuel/rapport_mensuel.py`,
   function `_indicateurs` (lines ~1377–1380). This is what gets the
   green/orange/red color.
2. **Alimentation table** — row `"Efficacité alimentaire L/Kg MS"` in the same
   file, function `_alimentation` (lines ~1138–1155). Per-lot + per-period
   breakdown; not color-coded (it's a detail grid, not a KPI verdict).

Because the task forbids modifying anything under `hmd_agro/`, this deliverable
**documents and reproduces** the existing mechanism rather than re-adding it.
The files here are a faithful, runnable extract you could drop in if the KPI
ever needed re-creating. Nothing under `hmd_agro/` was touched.

Files:
- `efficacite_indicateur.py` — self-contained formula + coloring helper +
  row builder (runnable demo of all 3 color bands).
- `rapport_mensuel_formatter.js` — the report's client formatter fragment that
  turns the server `indicator` string into a colored cell.

---

## Formula

```
Efficacité Alimentaire (sur MS) = Production laitière (L) / MS ingérée (kg)
```

Unit: **L lait / kg MS**. Higher is better.

In `_indicateurs._period_kpis` (rapport_mensuel.py):

```python
"eff_alim": round(prod_ / ms_total_, 2) if ms_total_ else 0
```

- `prod_` = `SUM(Traite.quantite_litres)` over the period (cheptel-wide).
- `ms_total_` = `cumulative_ms_cheptel` = Σ over aliments of
  `kg consommé × ms_pct`. The kg come from Stock Ledger Entry rows
  (`RATION_DIST_*` theoretical + `RATION_CORRECTION_*` Saisie Alimentation),
  so it is **MS ingérée = MS distribuée − refus**, net of corrections.
- Guard: returns `0` when MS = 0 (no division by zero, and `0` reads as
  "no signal" downstream → cell left uncolored).

KPI reference (`.claude/skills/hmd-agro-kpi/references/kpi-formulas.md`):
> **Efficacité alimentaire** = `lait ÷ MSI` (kg lait / kg MS ingérée), avec
> MSI = MS distribuée − refus. Optimal **1.4 L/kg MS** (Castellani 2014).

---

## How the coloring is decided

### Step 1 — server computes a verdict string (`indicator`)

`_indicateurs` builds the row with the **higher-is-better** branch of
`_kpi_ind`:

```python
row("Efficacité Alimentaire (sur MS)", cur["eff_alim"], "L/kg MS",
    indicator=_kpi_ind(cur["eff_alim"], green_min=cfg_eff_min,
                       orange_min=cfg_eff_omn),
    valeur_m1=m1["eff_alim"], direction="up")
```

`_kpi_ind` (higher-better branch):

```python
if value is None or value == 0: return ""      # no signal -> uncolored
if value >= green_min:  return "Green"
if value >= orange_min: return "Orange"
return "Red"
```

So the bands are:

| Efficacité value           | indicator | color  |
|----------------------------|-----------|--------|
| `>= pfe_efficacite_min` (1.4)        | `Green`  | green  |
| `pfe_efficacite_orange_min` (1.0) … < 1.4 | `Orange` | orange |
| `< pfe_efficacite_orange_min` (1.0)  | `Red`    | red    |
| `None` or `0` (no MS data)           | `""`     | none   |

### Step 2 — client formatter applies the color

`rapport_mensuel.js` `formatter(...)` colors the `valeur` cell from
`data.indicator`:

```js
if (column.fieldname === "valeur" && data && data.indicator) {
    const colors = {Green: "green", Orange: "orange", Red: "red"};
    const c = colors[data.indicator];
    if (c) {
        const w = data.indicator === "Red" ? "font-weight:bold;" : "font-weight:600;";
        html = `<span style="color:${c};${w}">${html}</span>`;
    }
}
```

(Red is also bolded.) The Δ / M-1 cell is colored separately by `direction`
(`"up"` here → a positive Δ is green = improving).

---

## Thresholds and their source

Thresholds are **per-farm**, stored in the `HMD Configuration` Single doctype
(Section "Seuils PFE"), read via `get_config(...)` so each farm can tune them
without code changes.

| Field                       | Default | Role |
|-----------------------------|---------|------|
| `pfe_efficacite_min`        | **1.4** | green if value ≥ this |
| `pfe_efficacite_orange_min` | **1.0** | orange floor; red if value < this |

Read in `_indicateurs`:

```python
cfg_eff_min = float(get_config("pfe_efficacite_min", default=1.4))
cfg_eff_omn = float(get_config("pfe_efficacite_orange_min", default=1.0))
```

Sources for the defaults / field definitions:
- Field defs + descriptions:
  `hmd_agro/hmd_agro/doctype/hmd_configuration/hmd_configuration.json`
  (label "Efficacité Alimentaire Min (vert si ≥)", description
  "Production/MS ingérée ≥ cette valeur → VERT. PFE: 1.4 L/kg MS.").
- Default seeding patch (because Frappe stores Float as 0.0 after migrate,
  breaking color logic): `hmd_agro/patches/v1_1/init_pfe_seuils.py`
  → `pfe_efficacite_min: 1.4`, `pfe_efficacite_orange_min: 1.0`.
- KPI reference table:
  `.claude/skills/hmd-agro-kpi/references/kpi-formulas.md`
  → "Efficacité | ≥1.4 (orange ≥1.0) | <1.0 |
  `pfe_efficacite_min`, `pfe_efficacite_orange_min`".
- Agronomic origin: optimal 1.4 L/kg MS (Castellani 2014 / PFE).

---

## Key decisions

- **Did not modify `hmd_agro/`** — required by the task. The indicator is
  already present; re-adding it would duplicate the row. The deliverable instead
  documents the live mechanism and provides an isolated, verified reproduction.
- **Kept the existing `_kpi_ind` semantics exactly**: higher-is-better,
  `Green/Orange/Red/""`, with `value==0 → ""` so "no MS data" stays uncolored
  rather than showing a misleading red.
- **Thresholds via `get_config` with the documented defaults (1.4 / 1.0)** so
  the verdict reflects each farm's editable HMD Configuration, not hard-coded
  literals.
- **MS ingérée = net consumed dry matter** (SLE, after Saisie Alimentation
  corrections), matching the report's `cumulative_ms_cheptel`, not raw
  distributed MS — so refusals lower the efficacité as they should.
- Verified: `python3 efficacite_indicateur.py` prints Green (1.50), Orange
  (1.20), Red (0.80), and uncolored for MS=0.
```
