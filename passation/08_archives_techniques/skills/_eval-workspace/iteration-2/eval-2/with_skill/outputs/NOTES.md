# RG14 — "Semence à zéro ⇒ indisponible pour l'insémination"

## The rule (canonical, French)

> **RG14** — *Si le stock de semence atteint zéro, la semence devient
> automatiquement indisponible.*

Plain reading: when a bull's semen batch reaches zero, that batch can no
longer be consumed by an insémination. "Indisponible" = "becomes
unavailable" = "can no longer be used" — it is a statement about
availability, **not** a request for a new pre-save block.

## TL;DR — RG14 is already implemented. Do NOT add anything.

RG14 is **already realized by the ERPNext stock layer**, not by a flag on
`Semence`. There is **no `disponible` boolean** to add and **no new guard**
to write. "Availability" is an *emergent* property of two existing facts:

1. The canonical per-batch quantity is `Batch.batch_qty` (each `Semence`
   record *is* an ERPNext `Batch`, batch name = `Semence.name`).
2. **ERPNext v15 refuses to take a batch negative** — independently of
   `Item.allow_negative_stock`. So once a batch's `batch_qty` hits 0, that
   batch is simply unconsumable. That refusal *is* RG14.

The HMD-AGRO code cooperates with this: it picks a batch **before** writing
stock and, when every batch for the bull is depleted, it **skips the stock
write and raises a red alert** instead of forcing a negative.

> Spec→code delta (authoritative list, `business-rules.md` RG14):
> the spec imagined a custom `disponible` flag; the code does **not** add
> one. **The code wins.** Do not introduce a boolean or a redundant guard.

## Where the logic lives (the "where does it belong" answer)

It belongs in **the stock layer**, surfaced through
`Insemination.after_insert`. There is no field anywhere that says
"available / unavailable" — availability is computed from `Batch.batch_qty`
at decrement time.

File: `hmd_agro/hmd_agro/doctype/insemination/insemination.py`

| Step | Method | Lines | What it does |
|------|--------|-------|--------------|
| Trigger | `after_insert` → `decrement_semence_stock()` | `:349-351`, `:220` | Fires the −1 paillette on IA save (RG13). |
| Batch pick | `_pick_semence_batch(prefer_with_stock=True)` | `:272-321` | FIFO oldest-first (`ORDER BY date_reception ASC`) **among batches where `COALESCE(Batch.batch_qty,0) > 0`**; returns `None` if all are depleted (`:316-320`). |
| RG14 enforcement | depleted-batch branch in `decrement_semence_stock` | `:246-259` | When the picker returns `None`, the Material Issue is **skipped** and a red `frappe.msgprint` tells the operator to post a Purchase Receipt first. The IA record itself still saves; only the stock write is omitted. |
| No-batch-at-all | `any_batch` check | `:237-245` | Distinct case: no `Semence` master for this `(taureau, type)` → separate red alert ("enregistrer une livraison"). |

Quantity source of truth: `tabBatch.batch_qty` (joined in `_pick_semence_batch`,
`:307-313`), **not** `Semence.stock_courant` (that field is a denormalized
display value) and **not** `tabBin` (in v15 `Bin` is per `(item, warehouse)`
only — batch tracking moved to the Serial-and-Batch Bundle).

## How it behaves (the "how should it behave" answer)

Recording an IA on a bull whose batches are all at zero:

1. `Insemination.validate` runs the normal eligibility checks (animal is
   VACHE/GENISSE, not already GESTANTE, lactation rules — RG10/RG11, etc.).
   These pass; stock is **not** checked here today.
2. The IA **saves** (the husbandry event genuinely happened and must be
   recorded against the correct `taureau`).
3. `after_insert → decrement_semence_stock`:
   - `_pick_semence_batch(prefer_with_stock=True)` returns `None` (every
     batch `batch_qty == 0`).
   - The `Material Issue` is **skipped**.
   - A **red alert** (`indicator="red", alert=True`) instructs the user to
     post a Purchase Receipt before the IA — quoting that v15 won't allow a
     negative batch.
4. Net effect: stock never goes negative, the depleted batch is effectively
   "indisponible" (RG14 satisfied), and the discrepancy is surfaced to the
   operator instead of being silently absorbed.

The behavior is **post-save warn-and-skip**, by design — consistent with the
app's philosophy that a real reproductive event should be recorded even when
the digital stock is stale, while the stock ledger stays honest.

## Related rules (cite together)

- **RG13** — *L'enregistrement d'une IA déclenche une sortie de stock
  (1 dose de semence).* → `decrement_semence_stock` posts Material Issue
  −1 paillette (FIFO batch). RG14 is the boundary condition of RG13.
- **RG21** — *Une sortie de stock est refusée si la quantité demandée est
  supérieure à la quantité disponible.* → ERPNext Stock Ledger validation.
  HMD sets `Item.allow_negative_stock=1` for medicament/aliment so real
  events still record; **semence batches are the exception** — v15
  batch-level negative-stock enforcement is exactly what makes RG14 work.

## Optional extension (only if a hard pre-save block is explicitly wanted)

Per the domain skill, the existing post-save warn-and-skip is the
implementation of RG14. The skill permits **one** addition, and only on
explicit request:

> *"only add a pre-save `validate` guard if the user explicitly wants to
> block the IA before it saves."*

The current task does **not** request that (it restates RG14's availability
semantics), so this is a footnote, not the implementation. If product later
decides an IA must be *rejected outright* when no stock exists, the correct
shape is in `proposed_validate_guard.py`:

- Gate on the **same** `Batch.batch_qty` source via `_pick_semence_batch`
  (reuse, don't duplicate the SQL; never gate on `Semence.stock_courant`
  and never introduce a `disponible` flag).
- Run in `validate` so it blocks before the row is written.
- This **changes the documented behavior** (event no longer recorded when
  stock is dry), so it should only ship behind a config toggle and an
  explicit product decision — hence "optional."

## Files in this deliverable

- `NOTES.md` — this file.
- `rg14_explanation.py` — annotated excerpt of the **existing** mechanism
  (read-only reference; this is the real implementation, not a change).
- `proposed_validate_guard.py` — the **optional** pre-save guard, clearly
  labeled as a non-default extension.
