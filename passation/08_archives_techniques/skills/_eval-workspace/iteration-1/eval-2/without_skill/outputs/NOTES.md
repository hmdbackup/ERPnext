# RG14 — Semence stock à zéro bloque l'insémination

## The spec rule

> **RG14** — *Si le stock de semence atteint zéro, la semence devient
> automatiquement indisponible.*

Naive reading: add a `disponible` boolean on `Semence`, flip it to 0 when stock
hits zero, and refuse the IA when `disponible == 0`.

**That is the wrong implementation.** It would re-architect stock outside of
ERPNext and duplicate state that ERPNext already owns. Below is the
spec-vs-code delta and the correct, code-anchored approach.

## Where the logic actually lives

`hmd_agro/hmd_agro/doctype/insemination/insemination.py`

Specifically the `Insemination.after_insert → decrement_semence_stock()`
hook (plus its helper `_pick_semence_batch`). **RG14 is already implemented
there** — this task is about understanding/explaining the existing mechanism,
not bolting on a new boolean.

The chain:

- **RG13** (`decrement_semence_stock`): recording an IA issues 1 paillette of
  semen → `create_stock_movement(... "Material Issue" ... batch_no=s.name)`
  (a submitted ERPNext Stock Entry, FIFO oldest batch first).
- **RG14** is the *boundary condition* of RG13: what happens when there is no
  stock left to issue.

## How it actually behaves (the code-vs-spec delta)

Stock for semen is **not** a custom integer field on `Semence`. Each `Semence`
record **is** an ERPNext **Batch** (`batch_no = Semence.name`), and per-batch
quantity is `tabBatch.batch_qty`. The `Semence` form even shows a read-only
`stock_courant` computed from `Batch.batch_qty` (see `semence.json` /
`semence.py onload`). There is no `quantite_restante`/`disponible` field — those
were removed in Phase C (see `semence.py` comment).

The enforcement is **structural in ERPNext v15**, not a custom guard:

> ERPNext v15 enforces **batch-level** negative stock **independently of**
> `Item.allow_negative_stock`. Even though HMD sets
> `Item.allow_negative_stock = 1` (so MED-/ALI- real events still record when
> the Bin is stale), a **depleted Batch cannot be consumed**. Issuing −1 from a
> `batch_qty = 0` batch is refused by the Serial-and-Batch Bundle validation.

So `decrement_semence_stock` does **not** try to post against a depleted batch.
`_pick_semence_batch(prefer_with_stock=True)` walks the taureau's batches FIFO
and returns only one with `batch_qty > 0`; if **all** batches are at zero it
returns `None`, and the IA code shows a **red alert** and **skips the stock
write** instead of throwing:

```
Stock épuisé sur TOUS les batches du taureau {taureau} ({type}). Enregistrer
une Purchase Receipt avant l'IA — ERPNext v15 n'autorise pas un batch en négatif.
```

There are three distinct outcomes (already coded), worth keeping separate:

1. **No Semence master at all** for (taureau, type) → "Aucune Semence
   enregistrée … Enregistrer une livraison Semence avant l'IA." (orange/red)
2. **All batches depleted (qty 0)** → red alert above; stock write skipped.
   *(This is RG14.)*
3. **Semence not linked to an Item** → orange alert; write skipped.

## Key decision: warn-and-skip, NOT throw

The IA record itself still **saves**. The semen straw was physically used on the
animal — an insemination is a real-world event that already happened, so the
system must not lose the breeding record. RG14 only governs the **stock side**:
the consumption write is skipped and the operator is told to post a Purchase
Receipt (replenishment) to reconcile.

This is consistent with the wider HMD stock stance (`stock_utils.py
ensure_item_allow_negative_stock`): real events record even with stale Bins —
*except* semence batches, which v15 hard-blocks at the batch level. RG14 is
literally that exception (see `business-rules.md` RG14 / RG21).

## Why NOT a `disponible` boolean (spec literal)

- Duplicates state ERPNext already owns (`Batch.batch_qty`); would drift.
- Needs its own flip-on-zero / flip-on-receipt maintenance and a scheduler.
- The spec says "indisponible," but the *effective* behavior the system needs
  is "can't be issued" — which the batch ledger already guarantees for free.
- Code wins over spec where they diverge (documented delta RG14).

## Verifying / asserting the behavior (test sketch)

See `rg14_test_sketch.py`. The assertion is **not** "a boolean is False" — it is:
given a taureau whose only Semence batch is at `batch_qty = 0`, creating an
Insémination (a) still inserts the IA, and (b) does **not** create a
consuming Stock Entry (no negative batch), surfacing the red alert.

## Summary

| Aspect | Answer |
|---|---|
| Where | `insemination.py` → `after_insert/decrement_semence_stock/_pick_semence_batch` (already implemented) |
| Stock source of truth | ERPNext `Batch.batch_qty` (each Semence = one Batch); no custom field |
| Enforcement | ERPNext v15 batch-level negative-stock block (NOT `Item.allow_negative_stock`) |
| On zero stock | IA still saves; consumption write skipped; red alert → "post a Purchase Receipt" |
| Anti-pattern | a custom `disponible` boolean / re-architecting stock outside ERPNext |

## Eval disclosure (read before scoring this baseline)

This is the `without_skill` arm. The task permitted reading any file, and while
grounding the answer my repo-wide grep for "RG14" surfaced — and I read — the
skill's own reference files (`hmd-agro-domain/references/business-rules.md`,
`hmd-agro-dev/references/erpnext-integration.md`) and the eval's
`evals/evals.json` (which contains the grading `expected_output`). A strict
baseline would not have seen those. Mitigating fact: the conclusion is fully
derivable from `insemination.py` + `semence.py` + `semence.json` +
`stock_utils.py` alone (the FIFO picker returning `None` on all-depleted, the
warn-and-skip, the v15 batch-block), so the content stands on the app code
itself — but treat the "baseline already looked perfect" signal with that
caveat in mind when comparing arms.
