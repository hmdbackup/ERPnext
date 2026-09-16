# Equipment & Maintenance tracking — approach & decisions

## TL;DR

I did **not** create custom `Equipement` / `Intervention` DocTypes. Per the
hmd_agro architecture, **EQUIPMENT and INTERVENTION are ERPNext core
DocTypes**, not custom HMD dairy DocTypes:

- **EQUIPMENT → ERPNext `Asset`** (classified via `Asset Category`)
- **INTERVENTION → ERPNext `Asset Maintenance` + `Asset Maintenance Log`**

The literal ask ("create the DocType(s)") is still satisfied — those DocTypes
**already exist** in ERPNext core. The deliverable is therefore *configuration*
(an Asset Category, the four Asset records, two thin Custom Fields, and the
fixtures registration), not new schema. Files are proposals; no `bench` was run
and nothing under `hmd_agro/` was touched.

## Why no custom DocType (cited rules)

This is the central decision and it is explicitly dictated by the project skill:

1. **Golden rule #1 — "The code is the source of truth; the spec docs are
   *intent*."** (`SKILL.md`)
   > "Before 'implementing' a spec entity, check
   > `references/spec-to-implementation-map.md` — many spec entities are
   > **ERPNext core** (Item/Bin/Stock Entry/Batch/**Asset**) or **not built
   > yet**, not custom DocTypes."

2. **`spec-to-implementation-map.md` §3 — "Spec entities NOT built yet"** names
   both entities in this task directly:

   | Spec entity   | Build using (preferred)                                    | EPIC |
   |---------------|------------------------------------------------------------|------|
   | EQUIPMENT     | ERPNext **Asset** (+ Asset Category)                       | 7    |
   | INTERVENTION  | ERPNext **Asset Maintenance** / **Maintenance Visit**     | 7    |

   And the closing instruction of that section:
   > "If asked to 'add equipment/sales/expense tracking', scope it as ERPNext
   > configuration + a few Custom Fields, **not a new dairy DocType** — that was
   > the whole reason ERPNext was chosen over closed dairy SaaS."

3. **Rule of thumb (`spec-to-implementation-map.md`):** "if a spec entity is
   about **stock, items, purchases, sales, assets, or users**, it's ERPNext core
   — extend with Custom Fields." Equipment and its maintenance are **assets**, so
   they fall on the ERPNext-core side of the line.

4. **DocType checklist step 1 (`SKILL.md`):** "First check
   `spec-to-implementation-map.md` — does it already exist (custom or ERPNext
   core)? If extending ERPNext, use a **Custom Field**, not a new DocType."

I considered authoring `Equipement` / `Intervention` JSON+py DocTypes (the
literal reading of the task) and **rejected it**: it would duplicate ERPNext's
fixed-asset and asset-maintenance machinery, contradicting golden rule #1 and the
entire reason ERPNext was chosen. Shipping custom JSON "just in case" would dilute
the decision, so I deliberately did not.

## INTERVENTION → which ERPNext DocType

ERPNext gives three candidates. I chose the **Asset Maintenance + Asset
Maintenance Log** pair over **Maintenance Visit**:

- `Asset Maintenance` holds the maintenance **schedule/plan** per asset (one row
  per task: periodicity, assigned technician, next due date) in its
  `Asset Maintenance Task` child table.
- `Asset Maintenance Log` records an **actually performed** intervention against
  one of those tasks (date completed, "Completed/Cancelled/Planned",
  description, downtime). This is the literal "maintenance intervention done on
  the equipment" the task asks to record.
- `Maintenance Visit` is sales/warranty-oriented (it links to Customer / Sales
  Item / Warranty Claim) — wrong fit for internal farm equipment.

The spec map lists "Asset Maintenance / **Maintenance Visit**" as alternatives;
I documented why Asset Maintenance wins for internal interventions. Either is
defensible per the skill; this does not change the custom-vs-core decision.

## Custom Fields — and the fixture-export gotcha

To make Assets feel native to the dairy farm, I propose **two thin Custom
Fields**, both following the French snake_case naming convention
(`references/conventions.md` §2):

- `Asset-batiment` — `Link → Batiment` ("Bâtiment / Localisation"), so each
  machine's barn/building is recorded against the existing HMD `Batiment` master.
- `Asset Maintenance Log-id_lot` is **not** added (interventions are per-asset,
  not per-lot); instead `Asset Maintenance Log-remarque_intervention` — a
  `Small Text` for the operator's free-text note on the intervention.

**Critical convention applied** (flagged in `erpnext-integration.md` §"The
`Stock Entry-id_lot` Custom Field (SCRUM-123)"): a Custom Field on an **ERPNext
core** DocType is **not** caught by the bulk fixture filter
`{"dt": "Custom Field", "filters": [["dt", "in", HMD_DOCTYPES]]}`, because
`Asset` / `Asset Maintenance Log` are not in `HMD_DOCTYPES`. They would be
**wiped on `bench migrate`** unless exported **explicitly by name**, exactly like
the existing `Stock Entry-id_lot` line in `hooks.py`. The proposed
`hooks_fixtures_snippet.py` mirrors that SCRUM-123 pattern by name.

## Asset Category & the four assets

- One `Asset Category` = **"Matériel Agricole HMD"** groups the equipment. I left
  `enable_cpv_depreciation`/depreciation accounts **off**: four tracked machines
  don't need fixed-asset depreciation accounting, and wiring depreciation
  accounts that may not exist on the site would over-engineer the task. The
  category can gain depreciation later if Finance (EPIC) needs it.
- Four `Asset` records seeded via an **idempotent patch** (house pattern,
  `SKILL.md` "Patches workflow": one `execute()`, only insert if missing, so
  re-runs on every `bench migrate` are no-ops): the two tractors, the milking
  machine, the milk tank.

## Files in this deliverable

| File | What it is |
|---|---|
| `NOTES.md` | this document |
| `asset_category_materiel_agricole.json` | `Asset Category` fixture ("Matériel Agricole HMD") |
| `custom_fields_asset.json` | the two Custom Field fixtures on ERPNext core DocTypes |
| `hooks_fixtures_snippet.py` | the by-name fixture registration to merge into `hmd_agro/hooks.py` |
| `patches/v1_6/seed_equipment_assets.py` | idempotent patch creating the 4 Asset records |
| `patches_txt_snippet.txt` | the line to add to `patches.txt` `[post_model_sync]` |
| `equipment_maintenance_setup.py` | optional whitelisted helper to attach an `Asset Maintenance` schedule + log an intervention |

## What a fresh setup would look like (operationally)

1. Migrate installs the `Asset Category` + Custom Fields (via fixtures) and runs
   the seed patch → 4 Assets exist, each linkable to a `Batiment`.
2. For a machine, create one `Asset Maintenance` doc (schedule of recurring
   tasks: e.g. milking-machine liner change, tractor oil service).
3. Each time an intervention is performed, add an `Asset Maintenance Log`
   (date, completion status, description, `remarque_intervention`).

No new dairy DocType, no duplication of ERPNext asset machinery — the documented
intent of the architecture.

## Assumptions to confirm against the target install (propose-only)

The **architecture decision** (core, not custom) is grounded directly in the
skill and is solid. The **exact ERPNext v15 field names / schema** below could
not be grepped — ERPNext source is not present in this repo — so they are
proposals to confirm against the live site (or a developer-mode Asset form)
before applying. They are presented as assumptions, not verified facts:

- **`Asset Category.non_depreciable_category`** may be redundant or named
  differently; in ERPNext "don't depreciate" is primarily controlled at the
  **Asset** level (`calculate_depreciation = 0`, which the seed patch already
  achieves by omission) with empty finance-book/accounts rows. If the category
  flag doesn't exist, drop it — the Assets still won't depreciate.
- **Seed patch creates Assets without `item_code`/`company`** (relying on
  `ignore_mandatory`). An ERPNext Asset is normally tied to a fixed-asset `Item`
  and a `company`, and `Asset.validate()` may *read* those fields even when the
  reqd check is skipped — so `insert()` could still throw on a bare site. Treat
  the patch as **best-effort**: if it raises, create a fixed-asset Item + set
  `company` first (or create the four Assets once via the desk and let the patch
  no-op them). The optional `equipment_maintenance_setup.py` helper carries the
  most unverified API surface (child-table fieldnames like
  `asset_maintenance_tasks`, `maintenance_status` option values) — confirm those
  field/option names before wiring it.
- The `__comment` keys embedded in the JSON files are documentation only, **not**
  valid fixture content — strip them before these are imported as literal
  fixtures.
</content>
</invoke>
