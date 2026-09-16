"""
RG14 — reference of the EXISTING implementation (do not re-add to the app).

RG14 (spec): "Si le stock de semence atteint zéro, la semence devient
automatiquement indisponible."

Code reality (delta): there is NO `disponible` boolean. Each Semence record IS
an ERPNext Batch (batch_no = Semence.name); per-batch qty = tabBatch.batch_qty.
ERPNext v15 blocks batch-level negative stock independently of
Item.allow_negative_stock, so a depleted batch simply can't be consumed.

The rule therefore lives in the Insémination stock-decrement path. Below is the
load-bearing slice as it already exists in
  hmd_agro/hmd_agro/doctype/insemination/insemination.py
annotated to show exactly where RG14 is enforced.
"""

# ---- in class Insemination(Document) ----------------------------------------

def after_insert(self):
    # RG13: recording an IA issues one paillette of semen.
    self.decrement_semence_stock()
    self.close_chaleur_alerts()


def decrement_semence_stock(self):
    """RG13 consumption + RG14 boundary.

    Picks the FIFO oldest Semence batch that still has stock and posts a
    Material Issue of 1 paillette. If no batch has stock (all at qty 0),
    RG14 applies: the IA already saved, but the stock write is SKIPPED and a
    red alert tells the operator to post a Purchase Receipt first. We never
    try to issue against a depleted batch because ERPNext v15 would refuse it
    anyway (batch-level negative-stock block).
    """
    if not self.taureau:
        return
    from hmd_agro.hmd_agro.utils.stock_utils import create_stock_movement, DEFAULT_WAREHOUSE as WAREHOUSE

    # (a) No Semence master at all for (taureau, type) -> nothing to issue.
    any_batch = self._pick_semence_batch(prefer_with_stock=False)
    if not any_batch:
        frappe.msgprint(
            f"Aucune Semence enregistrée pour taureau={self.taureau}, "
            f"type={self.type_semence or 'tous'}. Enregistrer une livraison "
            f"Semence avant l'IA.",
            indicator="red", alert=True,
        )
        return

    # (b) RG14: batches exist but ALL are at qty 0 -> refuse the stock write.
    s = self._pick_semence_batch(prefer_with_stock=True)
    if not s:
        frappe.msgprint(
            f"Stock épuisé sur TOUS les batches du taureau {self.taureau} "
            f"({self.type_semence or 'tous types'}). Enregistrer une "
            f"Purchase Receipt avant l'IA — ERPNext v15 n'autorise pas un "
            f"batch en négatif.",
            indicator="red", alert=True,
        )
        return

    if not s.item:
        frappe.msgprint(
            f"Semence {s.name} non liée à un Item ERPNext — écriture stock "
            f"ignorée. Lancer semence_migration.",
            indicator="orange", alert=True,
        )
        return

    # Normal path: issue 1 paillette from the picked batch (FIFO).
    create_stock_movement(
        s.item, 1, "Material Issue", WAREHOUSE,
        f"Insemination {self.name} (batch {s.name})",
        self.date_ia, uom="Paillette", batch_no=s.name,
    )


def _pick_semence_batch(self, prefer_with_stock):
    """Resolve which Semence (= Batch) to charge.

    prefer_with_stock=True : FIFO oldest-first AMONG batches with batch_qty > 0;
                             returns None if none qualify  <-- this None IS RG14.
    prefer_with_stock=False: most-recent batch overall (used to detect existence
                             and to restore on delete).
    """
    conditions = ["s.taureau = %s"]
    params = [self.taureau]
    if self.type_semence:
        conditions.append("s.type_semence = %s")
        params.append(self.type_semence)
    order = "ASC" if prefer_with_stock else "DESC"
    rows = frappe.db.sql(
        f"""
        SELECT s.name, s.item, COALESCE(bat.batch_qty, 0) AS qty
        FROM `tabSemence` s
        LEFT JOIN `tabBatch` bat ON bat.name = s.name
        WHERE {" AND ".join(conditions)}
        ORDER BY s.date_reception {order}
        """,
        params, as_dict=True,
    )
    if not rows:
        return None
    if prefer_with_stock:
        for r in rows:
            if (r.qty or 0) > 0:
                return r
        return None  # all batches depleted -> RG14 path in caller
    return rows[0]
