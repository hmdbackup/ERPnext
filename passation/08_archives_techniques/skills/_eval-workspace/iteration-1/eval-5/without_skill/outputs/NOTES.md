# Number Card: Average milk production per lactating cow (yesterday)

## What the metric is

"Average milk production per lactating cow for the herd, yesterday" =

```
total litres milked yesterday  /  number of lactating cows on that date
```

This is the **PL/VL** ("Production Laitière / Vache Laitière") KPI that the app
already tracks. The repo *already* has a datasource for it:

- `hmd_agro/hmd_agro/utils/dashboard_kpis.py` → `get_pl_vl()` returns exactly
  `prod_yesterday / vaches_lactantes_yesterday`, rounded to 1 decimal.
- It is exposed by two existing cards: `PL_VL` (in `fixtures/number_card.json`,
  on the workspace) and `Lait par Vache Lactante`
  (`number_card/lait_par_vache_lactante/`, defined but not on the workspace).

So there are two legitimate ways to deliver this card.

---

## Option A (recommended): reuse the existing datasource

No Python needed. Create a Number Card whose `method` points at the
already-tested `get_pl_vl`. This guarantees the card stays consistent with the
monthly report (both go through the same `effectif_on_date` primitive).

In `lait_moyen_par_vl.json` just change the `method` line to:

```json
"method": "hmd_agro.hmd_agro.utils.dashboard_kpis.get_pl_vl",
```

…and skip the Python file entirely. Everything else (registration steps below)
is identical.

## Option B (delivered here): a dedicated, self-describing datasource

If you want the card backed by its own clearly-named method (nicer label in
code, room to add a colour `indicator` later), append `get_lait_moyen_par_vl`
from `dashboard_kpis_addition.py` to the existing `dashboard_kpis.py`. It is a
thin alias that reuses the same canonical primitives, so the formula can never
drift from PL/VL:

```python
@frappe.whitelist()
def get_lait_moyen_par_vl():
    yesterday = add_days(today(), -1)
    prod = _prod_sum(yesterday, yesterday)          # SUM(quantite_litres) on D
    vl   = effectif_on_date(yesterday)["Vaches - Lact."]   # herd reconstruction
    moyenne = round(prod / vl, 1) if vl else 0      # guard divide-by-zero
    return {"value": moyenne, "fieldtype": "Float"}
```

### Why these specific building blocks

- **`_prod_sum(start, end)`** — existing module-level helper that sums
  `Traite.quantite_litres` over a date range on `date_traite`. Same source the
  `Production Journaliere` card uses.
- **`effectif_on_date(D)["Vaches - Lact."]`** — the *single source of truth* for
  the count of lactating cows on a past date. It reconstructs each animal's
  category/lactation state from herd events (Velage / Lactation / Insemination /
  Avortement), so it never drifts even if `Animal.etat_lactation` is stale. The
  module docstring explicitly forbids reading `Animal.etat_*` for past dates.
- **Return shape** `{"value": <float>, "fieldtype": "Float"}` — the contract a
  Custom Number Card's `method` must satisfy (matches `get_pl_vl`,
  `get_production_journaliere`, `get_lc_ratio`).
- **`@frappe.whitelist()`** — required; the framework calls the method over RPC
  when rendering the card.

---

## How to register the card

A standard Number Card in this app lives in **three** places. Add the new card
to all three so it survives `bench migrate` and shows on the workspace.

### 1. Card definition file (source of truth as a doctype JSON)

Create the folder + file, mirroring the existing `lait_par_vache_lactante` card:

```
hmd_agro/hmd_agro/number_card/lait_moyen_par_vl/lait_moyen_par_vl.json
```

Use `lait_moyen_par_vl.json` from this output dir. Key fields:
`type: "Custom"`, `method: ...get_lait_moyen_par_vl` (or `...get_pl_vl` for
Option A), `is_standard: 1`, `module: "HMD AGRO"`, `name: "Lait Moyen par VL"`.

> Add an empty `__init__.py` in the folder if you follow the convention of other
> `number_card/*` dirs (most here ship only the `.json`, so it's optional).

### 2. Fixtures (`hmd_agro/fixtures/number_card.json`)

This app ships Number Cards as a fixture (see `hooks.py` →
`fixtures = ["Number Card", ...]`). Append an object to the JSON array, copying
the `PL_VL` entry and changing `name`, `label`, `method`. Example entry:

```json
{
  "doctype": "Number Card",
  "type": "Custom",
  "function": "Sum",
  "is_public": 1,
  "is_standard": 1,
  "module": "HMD AGRO",
  "name": "Lait Moyen par VL",
  "label": "Lait Moyen / VL (L)",
  "method": "hmd_agro.hmd_agro.utils.dashboard_kpis.get_lait_moyen_par_vl",
  "stats_time_interval": "Daily",
  "show_full_number": 0,
  "show_percentage_stats": 0,
  "docstatus": 0
}
```

### 3. Workspace (`hmd_agro/hmd_agro/workspace/hmd_agro/hmd_agro.json`)

To make it appear on the dashboard, reference it in **two** places in that file:

a) The `number_cards` array — add:

```json
{ "label": "Lait Moyen par VL", "number_card_name": "Lait Moyen par VL" }
```

b) The escaped `content` string — add a `number_card` block next to the other
   cards in the "Tableau de Bord" section, e.g.:

```json
{"id":"nc_lmvl","type":"number_card","data":{"number_card_name":"Lait Moyen par VL","col":4}}
```

(`col: 4` = one-third width, matching the other KPI cards.)

### 4. Apply

```bash
bench --site <site> migrate          # imports the standard card + fixture
bench --site <site> clear-cache
```

(or `bench --site <site> import-doc <path>` for just the card during dev).

---

## Files in this directory

| File | Purpose |
|------|---------|
| `dashboard_kpis_addition.py` | The `get_lait_moyen_par_vl` datasource to append to `dashboard_kpis.py` (Option B). |
| `lait_moyen_par_vl.json` | The Number Card doctype JSON (goes under `number_card/lait_moyen_par_vl/`). |
| `NOTES.md` | This file. |

## Caveats / decisions

- **Strongly prefer Option A** unless you have a reason to want a separate
  method — the metric is definitionally identical to the existing PL/VL, and
  reusing `get_pl_vl` avoids two functions that must be kept in sync.
- The denominator uses **lactating cows on yesterday's date** (not "currently"),
  so the average is historically correct even after today's herd changes.
- Rounding to 1 decimal and the divide-by-zero guard match the existing
  `get_pl_vl` / `get_production_journaliere` behaviour.
- Per the task constraints, nothing under `hmd_agro/` was modified; the steps
  above describe where the changes *would* go.
