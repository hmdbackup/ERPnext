# OPTIONAL EXTENSION — NOT the default implementation of RG14.
# ===========================================================================
# RG14 is ALREADY satisfied by the existing post-save warn-and-skip mechanism
# (see rg14_explanation.py + NOTES.md). Per the hmd-agro-domain skill, a
# pre-save block should be added ONLY when the product owner explicitly wants
# to *reject the IA outright* before it is written:
#
#   "only add a pre-save `validate` guard if the user explicitly wants to
#    block the IA before it saves."
#
# This guard CHANGES documented behavior: the reproductive event would no
# longer be recorded when the bull's stock is dry. That trade-off (data
# completeness vs. hard stock enforcement) is a product decision, so the guard
# is gated behind a config flag and defaults OFF.
#
# Design constraints honored:
#   - Gate on the SAME canonical source as the decrement: Batch.batch_qty via
#     the existing `_pick_semence_batch(prefer_with_stock=True)` helper.
#     DO NOT gate on Semence.stock_courant (denormalized display value) and
#     DO NOT introduce a `disponible` boolean (the skill bans it).
#   - Run in `validate` (pre-save) so the IA is blocked before insertion.
#   - Only block on genuinely-new IAs; never re-block an existing record on
#     edit (the dose was already consumed at its original after_insert).
# ---------------------------------------------------------------------------

import frappe

from hmd_agro.hmd_agro.utils.config import get_config


class InseminationRG14HardBlockMixin:
    """Illustrative mixin. To adopt, fold `validate_semence_disponible` into
    Insemination.validate() (after the existing eligibility checks)."""

    def validate(self):
        # ... existing checks (validate_animal_eligible, set_lactation, ...) ...
        self.validate_semence_disponible()   # <-- the optional addition

    def validate_semence_disponible(self):
        """RG14 (hard pre-save variant): refuse a NEW IA when every Semence
        batch for (taureau, type_semence) is depleted.

        Default: OFF. Enable via HMD Configuration key
        `rg14_block_ia_when_stock_zero` (default False) so the app keeps its
        documented warn-and-skip behavior unless the farm opts in."""
        if not get_config("rg14_block_ia_when_stock_zero", default=False):
            return
        if not self.is_new() or not self.taureau:
            return

        # Reuse the canonical batch picker — it returns None when every batch
        # for this bull/type has Batch.batch_qty <= 0. That None is RG14's
        # "indisponible" condition, sourced from the exact same place the
        # decrement uses (no divergence, no new flag).
        batch_with_stock = self._pick_semence_batch(prefer_with_stock=True)
        if batch_with_stock:
            return  # at least one usable dose -> available, allow the IA

        any_batch = self._pick_semence_batch(prefer_with_stock=False)
        if not any_batch:
            frappe.throw(
                f"ERR-IA-07: Aucune Semence enregistrée pour le taureau "
                f"{self.taureau} ({self.type_semence or 'tous types'}). "
                f"Enregistrer une livraison avant l'insémination."
            )

        # Batches exist but all at zero -> RG14: semence indisponible.
        frappe.throw(
            f"ERR-IA-08 (RG14): Stock de semence épuisé pour le taureau "
            f"{self.taureau} ({self.type_semence or 'tous types'}). "
            f"La semence est indisponible — enregistrer une Purchase Receipt "
            f"avant l'insémination."
        )
