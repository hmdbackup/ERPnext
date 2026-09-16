# Efficacité alimentaire — formula, coloring & rules

Deliverable for: *"Add an 'efficacité alimentaire' indicator to the hmd_agro dairy
reporting, and color it green / orange / red according to the farm's thresholds."*

Files in this folder:
- `efficacite_alimentaire_indicator.py` — proposed, self-contained code (formula +
  tri-color function + drop-in rows for the Indicateurs section). **Reference only — not
  applied to `hmd_agro/` per the eval rule.**
- `NOTES.md` — this file.

> Important finding: the indicator **already exists** in the real app as the row
> `"Efficacité Alimentaire (sur MS)"` in `rapport_mensuel._indicateurs` (line 1377),
> already colored via the PFE seuils. My deliverable therefore (a) documents its exact
> formula and coloring, and (b) proposes the *présente / lactante* split that the skill's
> Rule 1 asks for. The math/coloring below is the app's actual behaviour, verified in code.

---

## 1. The exact formula

**Efficacité alimentaire = lait produit ÷ MS ingérée**, in **L lait / kg MS**.

```
efficacité = lait (L)  ÷  MSI
MSI = MS distribuée − refus          (MSI = matière sèche ingérée)
MS distribuée = Σ ( quantité_distribuée_kg × MS%_de_l_aliment )
```

- **Target / objectif: 1.4 L/kg MS** (optimal). Source: PFE study (Nasrallah M. A.,
  INAT 2024), citing **Castellani 2014**. — `references/kpi-formulas.md`, Feed-economic
  table: *"Efficacité alimentaire = lait ÷ MSI, avec MSI = MS distribuée − refus —
  optimal 1.4 L/kg MS (Castellani 2014)"*.
- Reported for **two populations** (Rule 1): *par vache présente* and *par vache
  lactante*. The bilan's "Indicateurs des vaches" block (daily-report-structure §5)
  carries `Efficacité Alimentaire (L/kg MS)` in both a *Vache Présente* and a *Vache
  Lactante* row.

### How the app actually computes it (verified in code)
`hmd_agro/hmd_agro/report/rapport_mensuel/rapport_mensuel.py`:
- `_period_kpis(start, end)` (`:1260`): `"eff_alim": round(prod_ / ms_total_, 2) if ms_total_ else 0`
  where `prod_ = Σ Traite.quantite_litres` over the period and
  `ms_total_ = d_["cumulative_ms_cheptel"]`.
- `cumulative_ms_cheptel` is built at `:850, :859`: `ms_kg = qty * ms_pct;
  cumulative_ms_cheptel += ms_kg` — i.e. **Σ(qty × MS%)** = **MS distribuée**.
- The per-lot Ration view (`:1138-1155`, row `"Efficacité alimentaire L/Kg MS"`)
  divides per-lot milk by per-lot `daily_ms` the same way.

### Refus (MSI vs MS distribuée) — the one nuance
The skill's *ideal* denominator is **MSI = MS distribuée − refus**. At the **cheptel**
aggregate level the current app does **not** subtract refus (`cumulative_ms_cheptel` is
MS distribuée). Refus lives at the **per-lot Ration** level (daily-report-structure §7:
"Refus Brut / MS Refus ... Efficacité alimentaire ... Recall MSI = MS distribuée − refus";
data from `Lot Ration History` + `Composition Ration` MS%). My proposed
`efficacite_alimentaire(lait, ms_kg, refus_kg=0)` exposes the `− refus` term explicitly
while defaulting to MS distribuée so the new cheptel rows can never drift from the
existing report row.

---

## 2. The coloring (green / orange / red) and its source

Efficacité is **higher-is-better** with a single threshold pair (no upper alarm). Coloring:

| Condition | Color | Meaning |
|---|---|---|
| `valeur ≥ pfe_efficacite_min` (1.4) | **Green** | optimal — ration efficace |
| `pfe_efficacite_orange_min` (1.0) ≤ `valeur` < 1.4 | **Orange** | warning — à surveiller |
| `valeur < pfe_efficacite_orange_min` (1.0) | **Red** | alarm — gaspillage de MS |
| `valeur` is None or 0 | `""` (blank) | no data → no signal |

**Threshold source = `HMD Configuration` (Seuils PFE), read via `get_config`** — never
hardcoded (Rule 3). Fields and defaults (verified in code):

| Field | Default | Defined in |
|---|---|---|
| `pfe_efficacite_min` | **1.4** | `hmd_configuration.json:333` (label *"Efficacité Alimentaire Min (vert si ≥)"*), `init_pfe_seuils.py:18`, `hmd_configuration.js:42` |
| `pfe_efficacite_orange_min` | **1.0** | `hmd_configuration.json:342` (label *"Efficacité Alim Orange Min (rouge si <)"*), `init_pfe_seuils.py:19`, `hmd_configuration.js:43` |

The doctype field descriptions state the rule verbatim:
*"Production/MS ingérée ≥ cette valeur → VERT. PFE: 1.4 L/kg MS."* and
*"Production/MS entre cette valeur et seuil min → ORANGE. < cette valeur → ROUGE."*

These are **the farm's thresholds** — configurable per the PFE seuils mechanism. Defaults
match the PFE study target (1.4) with an orange floor at 1.0.

### How the decision is wired in the report (verified, `:1377-1380`)
```python
cfg_eff_min = float(get_config("pfe_efficacite_min",        default=1.4))   # :1250
cfg_eff_omn = float(get_config("pfe_efficacite_orange_min", default=1.0))   # :1251
...
row("Efficacité Alimentaire (sur MS)", cur["eff_alim"], "L/kg MS",
    indicator=_kpi_ind(cur["eff_alim"], green_min=cfg_eff_min, orange_min=cfg_eff_omn),
    valeur_m1=m1["eff_alim"], direction="up")
```
`_kpi_ind(value, green_min, orange_min)` (`:1187`) returns `"Green" / "Orange" / "Red"`,
which Frappe's Script Report renders as a colored dot on the row (the `indicator` key).
My `colorier_efficacite()` is byte-for-byte equivalent to that `_kpi_ind` branch.

---

## 3. Rules applied (cited from `hmd-agro-kpi/SKILL.md`)

- **Rule 1 — two populations (présente vs lactante).** SKILL.md §"Rule 1": *"Almost every
  per-cow KPI is reported both ways."* Efficacité is split into a *Vache Présente* and a
  *Vache Lactante* row (daily-report-structure §5). My proposed rows add the lactante split
  the cheptel-only report row is missing, always labeling the denominator.
- **Rule 2 — effectif reconstructed, never live.** SKILL.md §"Rule 2": counts come from
  `utils/live_state.py` (`effectif_on_date`), not `Animal.etat_*`. The proposed code reuses
  `effectif_on_date(end)` (via the report's existing `_period_kpis`) for VP/VL denominators —
  no live-field reads.
- **Rule 3 — thresholds are config (PFE seuils), tri-color, never hardcoded.** SKILL.md
  §"Rule 3" + threshold table (Efficacité: *"Green ≥1.4 (orange ≥1.0), Red <1.0,
  `pfe_efficacite_min` / `pfe_efficacite_orange_min`"*). The coloring reads both fields via
  `get_config(..., default=...)`; defaults (1.4 / 1.0) only stand in for an uninitialized
  Single (see `init_pfe_seuils.py`).
- **Add-a-KPI conventions** (reports-and-cards §"How to add..."): decorate `execute` with
  `@normalize_precision` (already on the report), pull seuils via `get_config`, source
  historical figures from `live_state`. The snippet reuses the report's existing helpers
  (`_kpi_ind`, `_period_kpis`, `_aliment_data_per_lot`, `row`) so the formula stays
  single-sourced and the indicator cannot drift from the L/C card or per-lot Ration view.

## 4. Sanity check (order of magnitude)
Sample dispositif day (daily-report-structure §5): *présente* eff. **1.032** → Orange
(1.0 ≤ 1.032 < 1.4); *lactante* eff. **1.484** → Green (≥ 1.4). Matches the coloring rule
above. (HMD 2023 data is fictitious — use for magnitude only.)
