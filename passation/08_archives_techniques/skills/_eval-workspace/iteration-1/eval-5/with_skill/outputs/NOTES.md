# Number Card — Moyenne de production par vache lactante (hier)

**Goal:** a workspace Number Card showing the **average milk production per
lactating cow for the herd, yesterday**.

## Deliverables in this folder

| File | What it is | Maps to (real app) |
|---|---|---|
| `dashboard_kpis_snippet.py` | The Custom-card datasource `get_moyenne_production_vache_lactante()` | append to `hmd_agro/hmd_agro/utils/dashboard_kpis.py` |
| `moyenne_production_vache_lactante.json` | The Number Card doc | `hmd_agro/hmd_agro/number_card/moyenne_production_vache_lactante/…json` |

> Per the eval rules nothing under `hmd_agro/` was modified — these are proposals only.

## The metric

"Average milk production per lactating cow" is the **Production / vache lactante**
KPI — the *performance* denominator:

```
moyenne_VL = Σ lait du troupeau (hier)  ÷  nb de vaches LACTANTES (hier)
```

Source: `references/kpi-formulas.md` → **Production** table, row *"Production /
vache lactante"* = `Σ lait ÷ nb de vaches lactantes` (performance denominator).

## Rules & conventions applied (cited)

1. **Two populations — pick the right denominator (SKILL.md Rule 1).**
   The request says *per lactating cow*, so the divisor is the **vache lactante**
   count, NOT *vache présente* (whole herd). In code this is the
   `"Vaches - Lact."` bucket of `effectif_on_date()` (the bucket name is defined
   in `live_state.CATEGORIES`). The docstring states the denominator explicitly,
   as Rule 1 requires ("never silently mix them").

2. **Effectif is reconstructed, never read live (SKILL.md Rule 2 /
   reports-and-cards.md live_state section).**
   The lactating-cow count comes from `live_state.effectif_on_date(yesterday)`,
   which replays events — we never read `Animal.etat_lactation`. Even though the
   numerator is "yesterday" (recent), routing the count through `live_state`
   keeps the card single-sourced with every report.
   *(Side note: this is a **Custom** card, not a Document Type card. The
   load-bearing reason is structural — it's a **ratio of two sources** (Σ Traite
   litres ÷ lactating-cow count), which a Document Type card (a single filtered
   count/sum on one table) cannot express. Document-Type cards also only read the
   live tables ("now"), whereas the denominator here must come from the
   `live_state` reconstruction — reports-and-cards.md "Number Cards & Charts".)*

3. **No hardcoded target → no indicator color (SKILL.md Rule 3).**
   The PFE-seuils threshold table (`kpi-formulas.md` end; SKILL.md Rule 3 table)
   covers L/C, Efficacité, Persistance, %3IA+ — **not** production/VL. So this
   card returns `{"value", "fieldtype"}` **without** an `"indicator"` key. Adding
   a green/orange/red color would mean hardcoding a target, which Rule 3 forbids
   ("Never hardcode a target"). Cards that do color (e.g. `get_lc_ratio`) read
   `pfe_*` via `get_config`; this one has no seuil to read.

4. **Custom number-card contract (reports-and-cards.md → "New number card").**
   - Datasource is a `@frappe.whitelist()` function returning
     `{"value": ..., "fieldtype": ...}`.
   - KPI math lives in `utils/dashboard_kpis.py` and **reuses report primitives**
     (`_prod_sum`, `effectif_on_date`) "so formulas stay single-sourced."
   - The card JSON is `type: "Custom"`, `method:` pointing at the whitelisted
     function, `module: "HMD AGRO"`.

5. **"Yesterday" window matches the existing pattern.**
   `yesterday = add_days(today(), -1)`, same as `get_pl_vl` and the Production
   Journaliere card (dashboard_kpis.py module docstring: *"PL/VL: yesterday
   (single day, matches Production Journaliere pattern)"*).

## Important: this metric already ships

The app **already** has this exact computation as `get_pl_vl` (the
**"PL/VL" / "Lait par Vache Lactante"** cards) — `dashboard_kpis.py:28`:
```python
prod = _prod_sum(yesterday, yesterday)
vl = effectif_on_date(yesterday)["Vaches - Lact."]
ratio = round(prod / vl, 1) if vl else 0
```
That **is** "average milk production per lactating cow, yesterday."

So two valid options:
- **Reuse (recommended, zero new code):** create only the new card JSON and
  point its `method` at `…dashboard_kpis.get_pl_vl`. Re-labels the same metric
  without adding a duplicate function.
- **New named alias (provided here):** add
  `get_moyenne_production_vache_lactante()` for an explicitly-named datasource,
  then register the card against it. Functionally identical to `get_pl_vl`;
  chosen here because the task asked to "show the datasource function."

## How to register the card

1. **Add the datasource.** Append `get_moyenne_production_vache_lactante()` from
   `dashboard_kpis_snippet.py` to
   `hmd_agro/hmd_agro/utils/dashboard_kpis.py`. (`_prod_sum`, `effectif_on_date`,
   `add_days`, `today`, `frappe` are already imported there — do not duplicate.)

2. **Add the card doc** at
   `hmd_agro/hmd_agro/number_card/moyenne_production_vache_lactante/moyenne_production_vache_lactante.json`
   (contents = `moyenne_production_vache_lactante.json` here). `module` MUST be
   `"HMD AGRO"` so the hooks fixtures filter catches it. The card mirrors the
   shipped `lait_par_vache_lactante.json` (Custom / Sum / is_public / is_standard
   / Daily).

3. **Fixtures registration is already wired by module** — `hooks.py` has:
   ```python
   {"dt": "Number Card", "filters": [["module", "=", "HMD AGRO"]]},
   ```
   so no hooks edit is needed; setting `module: "HMD AGRO"` is what makes the
   card exportable (reports-and-cards.md "New number card" step 2).

4. **Persist the fixture:**
   ```bash
   bench export-fixtures --app hmd_agro
   ```
   (reports-and-cards.md step 3). This rewrites `hmd_agro/fixtures/number_card.json`
   to include the new card.

5. Drag the card onto the **HMD AGRO** workspace (or add it via the workspace
   editor) so it renders on the desk.

## Sanity check

Reference order-of-magnitude (kpi-formulas.md "Reference values"): production /
lactante ≈ **7 383 L/an** ≈ **~20 L/VL/day** — a daily value of roughly 16–20 L
is expected (the dispositif sample day shows moyenne lactante **18.416 L**).
`fieldtype: "Float"`, rounded to 1 decimal — consistent with the app's
`@normalize_precision` (precision=1) convention.
