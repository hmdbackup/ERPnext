# RG14 — Semence at zero stock can no longer be used for an insemination

## The rule

**RG14** (Dossier de Spécification, French is canonical):
> *Si le stock de semence atteint zéro, la semence devient automatiquement
> indisponible.*

The task verb is the key: when a bull's semence stock hits zero, it
**can no longer be USED for an insemination**. "Used" = an `Insemination`
record must be **refused** for that bull, not merely flagged after the fact.

Related rules (cited from `references/business-rules.md`):
- **RG13** — *L'enregistrement d'une IA déclenche une sortie de stock (1 dose
  de semence).* The IA's job is to decrement one paillette.
- **RG21** — *Une sortie de stock est refusée si la quantité demandée est
  supérieure à la quantité disponible.* RG14 is the semence-specific, batch
  -level instance of this refusal.

## Where the logic belongs

**In `Insemination.validate()`** (a new method `validate_semence_disponible`),
alongside the existing pre-save guards `validate_animal_eligible` /
`validate_no_pending_ia` in `hmd_agro/hmd_agro/doctype/insemination/insemination.py`.

The proposed code is in `insemination_rg14_guard.py` in this directory.

### Why validate(), and why this isn't already done

The Frappe lifecycle dictates the answer. The *only* RG14-related code today is
`decrement_semence_stock()` (`insemination.py:220`), wired into **`after_insert`**
(`insemination.py:349-351`). `after_insert` runs **after the IA row is already
committed**. Its depleted-batch branch (`insemination.py:252`) only emits a soft
`frappe.msgprint(..., indicator="red", alert=True)` and skips the stock write —
**the IA still saves.** So the documented current behavior satisfies "stock write
is skipped" but **not** "la semence devient indisponible / can no longer be used."

To actually *prevent* usage you must `frappe.throw` **before** the record is
written, and the only lifecycle hook that can abort an insert is a **pre-save**
hook (`validate`). Hence: enforcement moves to `validate()`; the `after_insert`
decrement stays as the RG13 stock write (now also a TOCTOU fallback).

## How it behaves

1. Runs only when `self.is_new()` and not `flags.ignore_validate`, and only when
   `self.taureau` is set — mirroring every other guard in this controller and
   the early-return in `decrement_semence_stock`. **Existing (already-saved) IAs
   stay editable** (e.g. marking `resultat = ECHOUEE`); they consumed their dose
   at creation, so re-validating them must not re-block.
2. **Reuses the existing FIFO picker `_pick_semence_batch(...)`** — the same
   function `decrement_semence_stock` calls. This is the central design move: it
   guarantees `validate() passes  <=>  the decrement will find a non-empty batch`.
   One source of truth, no divergent stock logic.
   - `_pick_semence_batch(prefer_with_stock=False)` returns `None` ⇒ **no Semence
     master at all** for this `(taureau, type)` → throw `ERR-IA-07` (data-setup
     error: register a livraison first).
   - `_pick_semence_batch(prefer_with_stock=True)` returns `None` (a batch exists
     but every `Batch.batch_qty` is 0) ⇒ **RG14 hit** → throw `ERR-IA-08`
     (semence indisponible: post a Purchase Receipt first).
   - These two cases reuse the exact "master missing" vs "all depleted"
     distinction the picker already encodes (`insemination.py:237` vs `:246`),
     so messages stay precise.
3. `decrement_semence_stock()` (`after_insert`) is **left unchanged** — RG13's
   `Material Issue -1 paillette` (FIFO batch, `batch_no = Semence.name`). Its
   depleted-batch warning now only matters for the narrow concurrent-drain race
   between this IA's `validate()` and its `after_insert`.

## Invariants honored (from the skill)

- **Pre-save throw is the sanctioned block path** — same shape as the other
  `validate()` guards; scoped to `is_new()`, short-circuits on
  `flags.ignore_validate`, so hook-driven saves (Animal exit cascade flipping an
  IA to ECHOUEE via `ignore_validate`) are never blocked.
- **No new inline thresholds** — "zero" is the natural floor; per-batch quantity
  comes from `Batch.batch_qty` via the existing picker, not a hardcoded number.
- **Single stock write path preserved** — all stock math stays in
  `stock_utils.create_stock_movement`; the guard only *reads* via the picker.
- **Symmetry untouched** — `on_trash → restore_semence_stock` (+1) is unaffected.

## Explicit judgment call (code-vs-spec delta)

`references/business-rules.md` flags RG14 as a delta where **"code wins"**: the
existing implementation deliberately lets the IA save on depleted stock,
arguing in `decrement_semence_stock`'s docstring that "the real Insémination
still gets recorded against the correct taureau." This proposal **overrides that
choice** for the normal (non-race) case.

Justification: the task asks to *implement the rule that semence at zero can no
longer be used* — a **hard block**, which the current soft-warning behavior does
not deliver. The skill's "code wins" note documents the status quo; it does not
assert the status quo fully implements RG14. We satisfy RG14's plain meaning
(refuse usage) while keeping the soft-warning as a fallback for the genuine
TOCTOU race the original docstring was really protecting against. This is the
intended override, surfaced rather than buried.
