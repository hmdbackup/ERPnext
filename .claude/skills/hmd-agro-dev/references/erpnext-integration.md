# ERPNext Stock Integration

The spec's stock entities are **ERPNext core**, not custom DocTypes. HMD AGRO never
defines a Produit/Stock/Inventaire DocType — it writes through ERPNext's stock ledger.
The HMD masters (`Medicament`, `Aliment`, `Semence`) each carry a Link field `item` →
`Item`, and all stock math happens in `Bin` / `Stock Ledger Entry`.

| Spec entity        | ERPNext core                              | Notes                                                        |
|--------------------|-------------------------------------------|--------------------------------------------------------------|
| PRODUIT            | `Item`                                    | one per Medicament / Aliment / Semence (codes `MED-`/`ALI-`/`SEM-`) |
| STOCK              | `Bin` (`actual_qty`, `valuation_rate`=CMP) | per (item, warehouse); Semence per-batch qty = `Batch.batch_qty` |
| MOUVEMENT_STOCK    | `Stock Entry` → `Stock Ledger Entry`       | submitted, immutable; the audit trail                        |
| INVENTAIRE         | `Stock Reconciliation`                    | physical count adjustments (native ERPNext)                  |

## stock_utils — the single write path

`hmd_agro/hmd_agro/utils/stock_utils.py` is the only place the app builds a Stock Entry.

Constants (`stock_utils.py:8-10`):
```python
DEFAULT_COMPANY   = "hmd-agro"
DEFAULT_WAREHOUSE = "Magasin Principal - HMD"
DEFAULT_UOM       = "Unit"
```

Core helper (`stock_utils.py:75`):
```python
def create_stock_movement(item_code, qty, purpose, warehouse, remark,
                          posting_date=None, company=None, uom=None, batch_no=None):
```
- Builds a **single-line submitted** Stock Entry. `purpose` must be `"Material Issue"`
  (sets `s_warehouse`, consumption) or `"Material Receipt"` (sets `t_warehouse`, intake);
  anything else `frappe.throw`s (`stock_utils.py:118`).
- `qty` is always **positive**; direction comes from the purpose. Line uses
  `conversion_factor=1`. **Valuation (FIN-S11, RG-FIN-30):** Material Issues carry no
  forced rate — ERPNext values them at the item's CMP (`Bin.valuation_rate`), so
  `SLE.stock_value_difference` is real; Material Receipts post at the optional
  `basic_rate=` kwarg (purchases) or default to current CMP (restoration receipts stay
  value-symmetric with the issue they compensate). **Garde-fou CF-FIN-31:** if CMP is
  still 0 (item never purchased) the legacy `basic_rate=0` +
  `allow_zero_valuation_rate=1` flags apply so field entry is never blocked — same
  per-line fallback in `feed_distribution._build_stock_entry`. Covered by
  `tests/test_valorisation_cmp.py`. `batch_no` is set only when passed (required for
  `has_batch_no` Items).
- `se.insert(ignore_permissions=True); se.submit()` — Bin updates immediately. Returns
  the SE name (e.g. `"MAT-STE-2026-00006"`).

Two idempotent default-setters back this up: `ensure_item_default` (writes
`Item.item_defaults` warehouse row via `db_insert`, bypassing `Item.save()` to avoid
duplicate `uoms` rows — ST5-13) and `ensure_item_allow_negative_stock` (sets
`Item.allow_negative_stock=1` so real-world events always record even on stale Bin).

## Semence (semen) stock — batch-level, FIFO

Each `Semence` record **is** an ERPNext `Batch` (batch name = `Semence.name`), linked to a
shared `SEM-` Item via `Semence.item`. Stock is one paillette per unit.

`Insemination.after_insert` → `decrement_semence_stock()` (`insemination.py:220`):
1. `_pick_semence_batch(prefer_with_stock=True)` — FIFO **oldest-first** (`ORDER BY
   s.date_reception ASC`) among batches where `COALESCE(Batch.batch_qty,0) > 0`
   (`insemination.py:307-320`).
2. Posts `create_stock_movement(s.item, 1, "Material Issue", WAREHOUSE, ..., self.date_ia,
   uom="Paillette", batch_no=s.name)` (`insemination.py:267`) → Bin −1.

`Insemination.on_trash` → `restore_semence_stock()` (`insemination.py:393`): picks the
**most-recent** batch (`prefer_with_stock=False`, `ORDER BY date_reception DESC`) and posts
a compensating **Material Receipt +1**. FIFO is irreversible, so "latest batch" is a
documented proxy.

**v15 gotcha — depleted batch refusal.** In v15 batch tracking moved to the
Serial-and-Batch Bundle and `Batch.batch_qty` is the canonical per-batch quantity (`Bin`
is per (item, warehouse) only, no `batch_no`). v15 blocks a **batch** from going negative
*independently* of `Item.allow_negative_stock`. So if all batches are at 0, the picker
returns `None` and the IA save **warns instead of decrementing** (`insemination.py:252`):
```python
frappe.msgprint(
    f"Stock épuisé sur TOUS les batches du taureau {self.taureau} ... "
    f"Purchase Receipt avant l'IA — ERPNext v15 n'autorise pas un batch en négatif.",
    indicator="red", alert=True)
```
The IA record itself still saves; only the stock write is skipped. If *no* batch exists at
all (Semence master missing), a separate red alert tells the operator to register a
livraison first (`insemination.py:239`).

## Medicament stock — per-row Material Issue

`Traitement.after_insert` → `decrement_medicament_stock()` (`traitement.py:71`), only for
`type_traitement == "TRAITEMENT_MEDICAL"`. One Material Issue per medicament child row:
```python
qty  = float(row.qty_consumed or 1)     # STOCK units (e.g. 0.5 flacon) — NOT dose
item = frappe.db.get_value("Medicament", row.medicament, "item")
create_stock_movement(item, qty, "Material Issue", WAREHOUSE, f"Traitement {self.name}", ...)
```
**`qty_consumed` vs `dose`** (ST5-11): `dose` is the medical metadata (e.g. 50 ml); the
stock decrement uses the separate `qty_consumed` field (stock-unit count, default 1). A vet
giving half a flacon sets `qty_consumed=0.5`. If Bin ≤ 0 a soft orange `msgprint` warns but
the issue still posts (`allow_negative_stock=1`). Unmigrated medicament (no `item`) → warn,
skip. `on_trash` → `restore_medicament_stock()` posts the mirror Material Receipt of the same
`qty_consumed` (`traitement.py:119`).

## Feed (aliment) distribution — daily scheduler

`hmd_agro/hmd_agro/utils/feed_distribution.py` records theoretical daily ration consumption.
Wired in `hooks.py:188` under `scheduler_events["daily"]` →
`generate_daily_distribution(catchup_days=7)`. For each missing completed day (oldest first,
never today) it calls `post_distribution_for_date`, which for every active `Lot`:
- `qty = qty_per_animal × population_on_date` per aliment in the lot's ration-on-date;
- posts **one Material Issue per (lot, day)** with one line per aliment, `s_warehouse =
  WAREHOUSE`, `set_posting_time=1` + `posting_time="00:00:00"` for deterministic backdating
  (`_build_stock_entry`, `feed_distribution.py:173`), and the custom field `id_lot = lot`.

**Idempotency** via the Stock Entry `remarks` marker `RATION_DIST_<lot>_<date>`
(`feed_distribution.py:176`). `_already_posted` (`:121`) matches `remarks LIKE
'RATION_DIST_<lot>_<date>%' AND docstatus=1`; a re-run is a no-op, so a server outage up to
`catchup_days` self-heals. **Backfill**: `backfill_distribution(start, end, dry_run)`
(`:357`) loops day-by-day with one prefetch of Animal + Allotement History. Cleanup helpers
`cancel_distributions` / `delete_cancelled_distributions` unwind a bad run (cancelled SEs are
docstatus=2, ignored by `_already_posted`). Aliments without an `Item` link are warned-once
and skipped (`_composition_for_ration`, `:93`).

## Reorder sync — feeding ERPNext's native reorder

`hmd_agro/hmd_agro/utils/reorder_sync.py::sync_reorder_level(doctype, name)` mirrors the
farmer-facing `reorder_level` field (on `Aliment` / `Medicament`) into the linked
`Item.reorder_levels` child row for `DEFAULT_WAREHOUSE`, with `material_request_type =
"Purchase"`. Called from the Aliment/Medicament controllers on insert + when `reorder_level`
changes (`aliment.py:31`, `medicament.py:37`). `level > 0` upserts the row; `level = 0`
deletes it (reordering off); no `item` link → no-op. ERPNext's native
`erpnext.stock.reorder_item.reorder_item` scheduler then auto-creates a Material Request when
projected qty hits the level (requires `Stock Settings.auto_indent`). HMD owns one simple
field; ERPNext owns the requesting workflow.

## The `Stock Entry-id_lot` Custom Field (SCRUM-123)

A `Link → Lot` Custom Field added to the **ERPNext core** `Stock Entry` DocType, inserted
after `posting_time`, label "Lot HMD" (`hmd_agro/fixtures/custom_field.json`). It tags each
feed-distribution SE with the originating `Lot` so consumption is reportable per lot without a
separate join table; it is empty on all other Stock Entries.

Because the app's bulk Custom Field fixture filters by `["dt", "in", HMD_DOCTYPES]` and
`Stock Entry` is **not** an HMD DocType, this one custom field is exported **explicitly by
name** in `hooks.py:25`:
```python
{"dt": "Custom Field", "filters": [["name", "=", "Stock Entry-id_lot"]]},
```
so a fresh-site install / `bench migrate` recreates it.

## Gotchas

- **Depleted Semence batch is refused, not forced negative** — v15 blocks batch-level
  negative stock regardless of `Item.allow_negative_stock`; the IA saves but the stock write
  is skipped with a red alert. Medicament/Aliment Items *can* go negative (Item flag).
- **Per-lot / default warehouse must exist** — all writes target `"Magasin Principal - HMD"`;
  feed SEs need that warehouse and the lot's `id_lot` value to be valid `Lot` records.
- **Keep `item` links in sync** — `Medicament`/`Aliment`/`Semence` must point at their `Item`
  or the stock write is silently skipped (warn-once). Migrations
  (`semence_migration` / `medicament_migration` / `aliment_migration`) populate `item`; the
  Semence↔Batch↔Bin coherence is asserted by
  `hmd_agro/hmd_agro/tests/test_semence_dual_write.py` (Material Issue −1 on insert, Material
  Receipt restore on delete, FIFO picker, depleted-batch fallback).
- **`qty_consumed` ≠ `dose`** — never decrement stock by the medical `dose`; use the stock
  unit `qty_consumed`.
- **SEs are submitted & immutable** — corrections come via new compensating entries
  (Material Receipt / cancel), never edits; this is what preserves price/consumption history.
