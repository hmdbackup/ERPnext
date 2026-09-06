---
name: hmd-agro-dev
description: >-
  Conventions, architecture, and Frappe/ERPNext v15 patterns for developing the
  HMD AGRO dairy-farm app (`hmd_agro`). Use this WHENEVER you create or modify
  anything in the codebase: a DocType (.json/.py), a controller hook
  (validate/on_update/after_insert/on_trash), a custom field, a fixture, a
  patch/migration, a scheduler job, a report, a page, or a util. It enforces
  house conventions (French domain naming, 4-space Python indent, config-driven
  thresholds via HMD Configuration, the fixtures + patches workflow, RG/CF/ERR
  code conventions) and the critical spec→implementation map (which spec
  entities are real custom DocTypes vs ERPNext core like Item/Bin/Stock
  Entry/Batch/Asset vs not-yet-built). Trigger even for small asks — 'add a
  field to Animal', 'create a doctype for X', 'write a migration patch', 'where
  should this logic live'. Pair with hmd-agro-domain (business rules & state
  machines) and hmd-agro-kpi (reports & indicators).
---

# HMD AGRO — Developer Guide (`hmd_agro` Frappe app)

`hmd_agro` is a custom **Frappe/ERPNext v15** app: a dairy-herd management system
for **HMD AGRO** (a ~200-head Montbéliarde farm in Tunisia). The domain language
is **French**; the architecture is **event-driven** (DocType controller hooks +
daily scheduler jobs) and **configuration-driven** (one `HMD Configuration`
Single holds every threshold). Build to fit this app — don't impose generic
Frappe defaults over its established patterns.

## Golden rules (read before any change)

1. **The code is the source of truth; the spec docs are *intent*.** The Drive
   spec (Dossier de Spécification, MCD) describes a relational model that the
   implementation deliberately diverged from. Before "implementing" a spec
   entity, check `references/spec-to-implementation-map.md` — many spec entities
   are **ERPNext core** (Item/Bin/Stock Entry/Batch/Asset) or **not built yet**,
   not custom DocTypes. Re-implementing `Stock`/`Produit`/`Vente` from scratch
   would duplicate ERPNext.
2. **Never hardcode a threshold.** Every age/day/seuil comes from
   `HMD Configuration` via `get_config(...)`. See *Configuration is king* below.
3. **Respect the French domain vocabulary verbatim.** Field names, Select
   options, and user messages are French (`date_velage_prevue`, `EN_COURS`,
   `TARIE`, "L'animal est déjà gestant."). Code comments/docstrings are English.
4. **Match the surrounding code.** This is a mature, consistent codebase. Copy
   the patterns in the file you're editing rather than introducing new ones.

## Repository layout

```
hmd_agro/                         # bench app root (also the project root)
├── hmd_agro/                     # python package
│   ├── hooks.py                  # fixtures, scheduler_events, boot_session
│   ├── boot.py                   # injects JS_FIELDS into frappe.boot.hmd_config
│   ├── modules.txt               # module: "HMD AGRO"
│   ├── patches.txt               # migration registry (post_model_sync)
│   ├── hmd_agro/                 # the "HMD AGRO" module
│   │   ├── doctype/<slug>/<slug>.{json,py,js}   # 29 doctypes
│   │   ├── report/<slug>/        # 4 query/script reports
│   │   ├── page/<slug>/          # 4 custom desk pages
│   │   ├── number_card/ dashboard_chart/ workspace/
│   │   ├── utils/                # 14 shared modules (config, live_state, ...)
│   │   └── tests/                # test_*.py + seed_data.py
│   ├── patches/v1_0 … v1_5/      # idempotent migration scripts
│   └── hmd_agro_/                # EMPTY legacy dir — do not use, do not extend
├── deploy/  pyproject.toml  .pre-commit-config.yaml
```

> `hmd_agro/hmd_agro/hmd_agro_/` (trailing underscore) is an empty legacy
> artifact. Put nothing there.

## House conventions (the essentials)

- **Python indentation = 4 spaces.** The committed `.py` is space-indented even
  though `pyproject.toml` sets ruff `indent-style = "tab"`. **Do not run
  `ruff format` across the repo** — it would re-tabify everything and create a
  huge, meaningless diff. Match the file you edit (4 spaces).
- **Naming:** DocType names are Title Case with spaces (`Lot Ration History`);
  the on-disk slug is snake_case (`lot_ration_history`). Field names are
  snake_case French (`identification_tn`, `date_traite`). Select options are
  `UPPER_SNAKE` French (`VACHE`, `EN_COURS`, `A_VENDRE`). Private helpers are
  `_snake_case`; module constants `UPPER_SNAKE`.
- **Module value = `HMD AGRO`** (exactly; no trailing space). Every fixture and
  DocType JSON uses this string. (`app_title`/`modules.txt` carry a stray
  trailing space that Frappe strips — ignore it; always write `HMD AGRO`.)
- **Error / rule codes:** validation errors raised with `frappe.throw(...)` carry
  codes `ERR-<DT>-<nn>` (e.g. `ERR-IA-01`); business rules are `RGnn`;
  functional constraints `CF-<CTX>-<nn>`; calc rules `RC-...`. Warnings use
  `frappe.msgprint(..., indicator="orange", alert=True)`. Keep using these.

Full detail (naming tables, the error-code registry, doc_events vs in-controller
hooks): **`references/conventions.md`**.

## Configuration is king

All tunables live in the **`HMD Configuration`** Single (37 fields). Read them
through the one accessor — never `frappe.db.get_single_value` directly, never a
literal:

```python
from hmd_agro.hmd_agro.utils.config import get_config

periode = get_config("periode_velage_jours", default=280)   # default is the documented fallback
```

- The `default` is **mandatory in spirit**: it's the constant that preserves
  behavior on a fresh DB / in unit tests (Singles aren't initialized from JSON
  defaults for Int/Float — that's what the `v1_0`/`v1_1` patches are for).
- `HMD Configuration.on_update()` queues background recalcs when window fields
  change (`pic_production_jours`, `production_initiale_jours`,
  `tarissement_window_jours`, `periode_velage_jours`). If you add a field that
  feeds a stored metric, wire the same pattern.
- JS reports read config from `frappe.boot.hmd_config`, populated by
  `boot.py`'s `JS_FIELDS` dict. **If a new config field must be readable in
  client `.js`, add it to `JS_FIELDS` in `boot.py`** — it is not automatic.

The config field catalog + defaults lives in `references/conventions.md`; the
KPI-threshold (`pfe_*`) fields are documented in the **hmd-agro-kpi** skill.

## Where does logic go?

| Concern | Lives in | Notes |
|---|---|---|
| Per-document rules & cascades | DocType controller (`<slug>.py`) | `validate`, `before_insert`, `after_insert`, `on_update`, `on_trash`. The heavy controllers are animal/lactation/velage/insemination/traite/traitement/ration. |
| Shared/reused logic | `utils/<module>.py` | `config`, `live_state`, `feed_distribution`, `stock_utils`, `lot_utils`, `dashboard_kpis`, `*_recalc`. |
| Historical/aggregate reads | reports + `utils/live_state.py` | **Never read `Animal.categorie/etat_lactation/etat_gestation` for a *past* date** — reconstruct from events via `live_state.states_on_date(...)`. Live Animal fields are "now" only and can drift. |
| Daily automation | `scheduler_events["daily"]` in `hooks.py` | 3 jobs today: `alerte.generate_alerts`, `traitement.refresh_attente_lait`, `feed_distribution.generate_daily_distribution`. Add new jobs here; make them idempotent. |
| Stock movements | `utils/stock_utils.py` → ERPNext | Material Issue/Receipt; see ERPNext integration below. |

State-machine and cascade rules (what `after_insert`/`on_trash` must do for
Velage, Insemination, Lactation, Animal exit) are owned by the
**hmd-agro-domain** skill — consult it before touching those controllers.

## Creating or modifying a DocType — checklist

1. **First check** `references/spec-to-implementation-map.md` — does it already
   exist (custom or ERPNext core)? If extending ERPNext, use a **Custom Field**,
   not a new DocType.
2. Files live at `hmd_agro/hmd_agro/doctype/<slug>/<slug>.{json,py,js}`. Prefer
   editing the schema in **developer mode** (Frappe writes the `.json`); hand-edit
   JSON only for small surgical changes and preserve existing formatting.
3. Set `module` to `HMD AGRO`. Choose an `autoname` matching house style:
   `format:VEL-{animal}-{#####}`, `format:BLJ-{date}`, or `field:nom_xxx`.
4. Put controller logic in `<slug>.py` following the existing hook patterns; use
   `get_config` for any threshold; raise `frappe.throw` with an `ERR-` code.
5. If the DocType needs Custom Field / Property Setter fixtures, **add its name
   to `HMD_DOCTYPES` in `hooks.py`** (see Fixtures below).
6. Add a test under `tests/test_<area>.py`.

## Fixtures workflow

`hooks.py` exports these as fixtures so UI-created config survives `bench migrate`:

```python
HMD_DOCTYPES = ["Animal", "Lactation", "Traite", ...]   # extend when adding a doctype
fixtures = [
    {"dt": "Workspace",       "filters": [["module", "=", "HMD AGRO"]]},
    {"dt": "Property Setter", "filters": [["doc_type", "in", HMD_DOCTYPES]]},
    {"dt": "Custom Field",    "filters": [["dt", "in", HMD_DOCTYPES]]},
    {"dt": "Custom Field",    "filters": [["name", "=", "Stock Entry-id_lot"]]},  # SCRUM-123: CF on ERPNext core
    {"dt": "Number Card",     "filters": [["module", "=", "HMD AGRO"]]},
    {"dt": "Dashboard Chart", "filters": [["module", "=", "HMD AGRO"]]},
]
```

- After changing Custom Fields / Property Setters / Number Cards / Dashboard
  Charts / Workspace in the UI, re-export: `bench export-fixtures --app hmd_agro`,
  then commit the JSON.
- A Custom Field on an **ERPNext core** DocType (e.g. `Stock Entry-id_lot`)
  isn't caught by the `dt in HMD_DOCTYPES` filter — add it **explicitly by name**
  like the SCRUM-123 line, or it gets wiped on migrate.

## Patches (migrations) workflow

- One script per change at `hmd_agro/patches/v<major>_<minor>/<name>.py` with a
  module-level `execute()`. Register the dotted path in `patches.txt` under
  `[post_model_sync]` (runs after DocType schema sync).
- **Patches must be idempotent** — they re-run on every `bench migrate`. The house
  pattern: only write a value if it's still uninitialized (`None`/`0`), and filter
  on a sentinel (e.g. `WHERE ration IS NULL`) so re-runs are no-ops. See the
  `v1_0`–`v1_5` scripts for the template.
- Use patches to seed new `HMD Configuration` defaults (JSON defaults don't
  persist to `tabSingles` for Int/Float).

## ERPNext integration (stock, items, assets)

Spec entities `Produit / Stock / Mouvement Stock / Inventaire` are **ERPNext core**
(`Item` / `Bin` / `Stock Entry` / `Stock Reconciliation`), not custom DocTypes.
`Medicament`, `Aliment`, and `Semence` each link to an ERPNext `Item`; their
consumption posts **Material Issue/Receipt** via `utils/stock_utils.py`.
Semence uses a FIFO batch picker (`Batch`). Read
**`references/erpnext-integration.md`** before touching anything stock-related.

## Gotchas (must-read before editing controllers)

- **Protected Animal fields:** `etat_gestation`/`etat_lactation` reject manual
  edits; hooks bypass with `animal.flags.ignore_validate = True`. If your hook
  fails mid-save, animal state can drift from IA/Velage — keep on_trash cascades
  symmetric.
- **Bulk Traite imports:** set `flags.skip_lactation_update = True` and recompute
  once per lactation at the end, or you trigger N recalcs.
- **Ration is immutable** after first save (name + composition frozen);
  `active`/`description` stay editable. Don't "fix" a ration — create a new one.
- **Semence batch stock:** ERPNext v15 blocks batch-level negative stock
  independently of `Item.allow_negative_stock`; a depleted batch can't be
  consumed and the IA save warns. Don't disable the guard.
- **`HMD AGRO` trailing-space trap:** always write the module as `HMD AGRO`
  (the catalog confirms every JSON uses no trailing space).

## Reference files

- `references/spec-to-implementation-map.md` — **start here.** Every spec entity →
  custom DocType / ERPNext core / folded / not built. The map that prevents
  rebuilding what already exists.
- `references/doctype-catalog.md` — the 29 DocTypes: purpose, autoname, which have
  real controller logic, child tables, and the file to open. (Field lists live in
  the JSON — this points you there rather than duplicating volatile detail.)
- `references/conventions.md` — naming tables, error-code registry, the full
  `HMD Configuration` field catalog + defaults, scheduler jobs, doc_events, tests.
- `references/erpnext-integration.md` — Item/Batch/Bin/Stock Entry usage, the
  semence FIFO picker, reorder sync, the `Stock Entry-id_lot` custom field.
