# RG14 — "Si le stock de semence atteint zéro, la semence devient indisponible."
#
# PROPOSED CHANGE to hmd_agro/hmd_agro/doctype/insemination/insemination.py
# (shown as a diff-style snippet — DO NOT applied here, evaluation only).
#
# Intent: a bull's semence at zero stock can NO LONGER be USED for an
# insemination. "Used" = the IA record must be REFUSED before it is written,
# not merely warned about after it is already persisted.
#
# Why a NEW guard is needed (the gap):
#   Today the only RG14-related logic lives in `decrement_semence_stock`, which
#   runs in `after_insert` (insemination.py:220, :349). By then the IA row is
#   already committed. The depleted-batch branch (insemination.py:252) only
#   emits a soft `frappe.msgprint(..., indicator="red")` and skips the stock
#   write — the IA still saves. That satisfies "decrement is skipped" but NOT
#   "la semence devient indisponible / can no longer be used". To actually
#   block usage we must check BEFORE save, i.e. in `validate()` — the only
#   lifecycle point that can `frappe.throw` and abort the insert.
#
# Design principle: reuse the EXISTING picker `_pick_semence_batch(...)` so the
# guard and the decrement share one source of truth. This guarantees:
#       validate() passes  <=>  decrement_semence_stock() will succeed
# i.e. if we let the IA through, the FIFO batch it would consume is the same
# batch we proved is non-empty. No duplicated/divergent stock logic.

# =====================================================================
# 1) Register the guard in validate(), alongside the other CF-IA checks.
# =====================================================================

    def validate(self):
        self.validate_animal_eligible()
        self.validate_no_pending_ia()
        self.validate_semence_disponible()   # <-- NEW: RG14 enforcement
        self.validate_date_ia()
        self.validate_resultat_transition()
        self.lock_identity_fields()
        self.set_lactation()
        self.set_numero_ia()


# =====================================================================
# 2) The new guard method.
# =====================================================================

    def validate_semence_disponible(self):
        """RG14 — refuse the IA when the bull's semence stock is at zero.

        'Si le stock de semence atteint zéro, la semence devient indisponible.'

        Enforced at validate() (pre-save) so a depleted bull can NO LONGER be
        used: the insert is aborted instead of silently saving with the stock
        write skipped (the prior after_insert behaviour).

        Scope mirrors every other guard in this controller:
          * only on a NEW IA — an already-saved IA consumed its dose at
            creation and must stay editable (e.g. resultat -> ECHOUEE);
          * short-circuit when flags.ignore_validate (hook-driven saves);
          * early-return when no taureau, like decrement_semence_stock().

        Reuses _pick_semence_batch(prefer_with_stock=True) — the SAME FIFO
        picker decrement_semence_stock() uses — so 'validate passes' is exactly
        equivalent to 'a non-empty batch exists to consume'.
        """
        if not self.is_new() or self.flags.ignore_validate:
            return
        if not self.taureau:
            return

        # Does ANY Semence batch exist for this (taureau, type)?  This separates
        # 'master missing' (data-setup error) from 'all batches depleted'
        # (the RG14 case) — same distinction decrement_semence_stock() makes.
        any_batch = self._pick_semence_batch(prefer_with_stock=False)
        if not any_batch:
            frappe.throw(
                f"ERR-IA-07: Aucune Semence enregistrée pour taureau="
                f"{self.taureau}, type={self.type_semence or 'tous'}. "
                f"Enregistrez une livraison Semence avant l'insémination."
            )

        # A batch exists — is any of them in stock?  prefer_with_stock=True
        # returns the oldest FIFO batch with Batch.batch_qty > 0, or None when
        # every batch is at zero.
        in_stock = self._pick_semence_batch(prefer_with_stock=True)
        if not in_stock:
            frappe.throw(
                f"ERR-IA-08 (RG14): Stock de semence épuisé pour le taureau "
                f"{self.taureau} ({self.type_semence or 'tous types'}). "
                f"Cette semence est indisponible: enregistrez une Purchase "
                f"Receipt avant de saisir l'insémination."
            )


# =====================================================================
# 3) decrement_semence_stock() is LEFT AS-IS (insemination.py:220).
# =====================================================================
#
# It still runs in after_insert and remains the RG13 stock write (Material
# Issue -1 paillette, FIFO). Its depleted-batch branch now acts only as a
# TOCTOU safety net: if another IA drained the last paillette between this
# IA's validate() and its after_insert (concurrent save), the soft red
# msgprint still fires and the stock write is skipped — the IA is not lost,
# matching the existing "record the real event" philosophy for that narrow
# race. The HARD block for the normal case now lives in validate().
