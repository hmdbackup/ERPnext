# RG14 — "Si le stock de semence atteint zéro, la semence devient
#          automatiquement indisponible."
#
# THIS IS A READ-ONLY REFERENCE, NOT A PROPOSED CHANGE.
#
# RG14 is ALREADY implemented in the real app at
#   hmd_agro/hmd_agro/doctype/insemination/insemination.py
# There is no `disponible` boolean and no dedicated guard: "availability"
# is emergent from `Batch.batch_qty` + ERPNext v15's batch-level
# negative-stock refusal. The excerpt below is annotated to show exactly
# WHERE the rule lives and HOW it behaves.

# ---------------------------------------------------------------------------
# (1) Trigger: every IA save posts a -1 paillette stock movement (RG13).
#     RG14 is the boundary condition of this decrement.
# ---------------------------------------------------------------------------

def after_insert(self):                      # insemination.py:349
    self.decrement_semence_stock()           # <-- RG13 decrement / RG14 refusal
    self.close_chaleur_alerts()


# ---------------------------------------------------------------------------
# (2) The decrement. When ALL batches for this bull are at zero, the picker
#     returns None and we SKIP the Material Issue with a red alert instead
#     of forcing a negative batch. *That skip is RG14.*
# ---------------------------------------------------------------------------

def decrement_semence_stock(self):           # insemination.py:220
    if not self.taureau:
        return
    from hmd_agro.hmd_agro.utils.stock_utils import create_stock_movement

    # No Semence master at all for this (taureau, type)? Distinct from
    # "all depleted" so the operator message is precise.
    any_batch = self._pick_semence_batch(prefer_with_stock=False)
    if not any_batch:
        frappe.msgprint(
            f"Aucune Semence enregistrée pour taureau={self.taureau}, "
            f"type={self.type_semence or 'tous'}. Enregistrer une "
            f"livraison Semence avant l'IA.",
            indicator="red", alert=True,
        )
        return

    # >>> RG14 ENFORCEMENT POINT <<<
    # FIFO oldest-first AMONG batches with batch_qty > 0. If every batch is
    # depleted this returns None -> the semence is effectively "indisponible".
    s = self._pick_semence_batch(prefer_with_stock=True)
    if not s:
        # v15 enforces batch-level negative stock independent of
        # Item.allow_negative_stock, so refusing is the only honest option.
        # The IA still SAVES; only the stock write is skipped.
        frappe.msgprint(
            f"Stock épuisé sur TOUS les batches du taureau {self.taureau} "
            f"({self.type_semence or 'tous types'}). Enregistrer une "
            f"Purchase Receipt avant l'IA — ERPNext v15 n'autorise pas "
            f"un batch en négatif.",
            indicator="red", alert=True,
        )
        return

    if not s.item:
        frappe.msgprint(
            f"Semence {s.name} non liée à un Item ERPNext — écriture "
            f"stock ignorée. Lancer semence_migration.",
            indicator="orange", alert=True,
        )
        return

    # Normal path: post the -1 paillette Material Issue against the picked batch.
    create_stock_movement(
        s.item, 1, "Material Issue", WAREHOUSE,
        f"Insemination {self.name} (batch {s.name})",
        self.date_ia, uom="Paillette", batch_no=s.name,
    )


# ---------------------------------------------------------------------------
# (3) The batch picker — canonical quantity source is Batch.batch_qty,
#     NOT Semence.stock_courant and NOT Bin (v15 Bin has no batch_no column).
#     prefer_with_stock=True returns None when all batches are at zero.
# ---------------------------------------------------------------------------

def _pick_semence_batch(self, prefer_with_stock):    # insemination.py:272
    conditions = ["s.taureau = %s"]
    params = [self.taureau]
    if self.type_semence:
        conditions.append("s.type_semence = %s")
        params.append(self.type_semence)
    order = "ASC" if prefer_with_stock else "DESC"
    rows = frappe.db.sql(f"""
        SELECT s.name, s.item, COALESCE(bat.batch_qty, 0) AS qty
        FROM `tabSemence` s
        LEFT JOIN `tabBatch` bat ON bat.name = s.name
        WHERE {" AND ".join(conditions)}
        ORDER BY s.date_reception {order}
    """, params, as_dict=True)
    if not rows:
        return None
    if prefer_with_stock:
        for r in rows:
            if (r.qty or 0) > 0:        # <-- the qty > 0 gate that realizes RG14
                return r
        return None                     # all batches depleted -> "indisponible"
    return rows[0]
