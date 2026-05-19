"""
ST5-15 — Feed correction backend (Saisie Alimentation).

The nightly generator (SCRUM-123) posts a THEORETICAL Material Issue per
(lot, date) computed as `ration.composition × population`. Reality differs:
feed is spilled, lots get more/less than planned, sometimes no feed is
delivered at all. This module lets the farmer record the ACTUAL total
delivered per lot per day; the system proportionally scales each aliment
line and posts a delta Stock Entry to bring Bin / SLE / GL in line with
reality.

Design choices (the supervisor's "complementary ration" architecture call):
  * Saisie is by ONE total kg per lot per day (Option A) — proportional
    scaling, not per-aliment input. Matches the farm workflow where rations
    are mixed and delivered in bulk per lot.
  * The theoretical SE stays UNCHANGED — audit trail preserves both what was
    planned and what was actually given.
  * The correction SE is a SEPARATE Stock Entry tagged
    `RATION_CORRECTION_<lot>_<date>`:
       - actual > theoretical → Material Issue for the additional delta
       - actual < theoretical → Material Receipt putting stock back at the
         theoretical SE's own valuation rate (zero GL impact on round trip)
  * Re-saisie is idempotent: any existing correction SE is cancelled before
    posting the new one.

Public API (whitelisted):
  - get_saisie_state(date)      — UI fetch
  - post_correction(date, lot, actual_total_kg) — UI save
  - cancel_correction(date, lot)                — UI clear
"""
import frappe
from frappe.utils import getdate, flt

from hmd_agro.hmd_agro.utils.stock_utils import (
    DEFAULT_COMPANY as COMPANY,
    DEFAULT_WAREHOUSE as WAREHOUSE,
)


THEO_MARKER_PREFIX = "RATION_DIST_"
CORR_MARKER_PREFIX = "RATION_CORRECTION_"


# ───────────────────────── helpers ─────────────────────────

def _find_se(marker_prefix, lot, date):
    """Return the docstatus=1 Stock Entry name for (lot, date) under the
    given marker prefix, or None. Marker format: `<prefix><lot>_<date>`."""
    marker = f"{marker_prefix}{lot}_{getdate(date)}"
    row = frappe.db.sql("""
        SELECT name FROM `tabStock Entry`
        WHERE remarks LIKE %s AND docstatus = 1
        ORDER BY creation DESC LIMIT 1
    """, (f"{marker}%",))
    return row[0][0] if row else None


def _se_items(se_name):
    """Return list of {item_code, qty, stock_uom, aliment} for the SE's items
    table. Joins back to Aliment master via `Item.name = Aliment.item`."""
    return frappe.db.sql("""
        SELECT sed.item_code, sed.qty, sed.stock_uom,
               COALESCE(a.name, sed.item_code) AS aliment
        FROM `tabStock Entry Detail` sed
        LEFT JOIN `tabAliment` a ON a.item = sed.item_code
        WHERE sed.parent = %s
        ORDER BY sed.idx
    """, (se_name,), as_dict=True)


def _valuation_rate_at_issue(se_name, item_code):
    """Return the valuation_rate the theoretical SE applied to `item_code`,
    read from the SLE the Material Issue produced. Used as `basic_rate` for
    the Material Receipt side of the correction so the round trip nets to
    zero GL impact (we're putting back the same stock at the same cost)."""
    row = frappe.db.sql("""
        SELECT valuation_rate FROM `tabStock Ledger Entry`
        WHERE voucher_no = %s AND item_code = %s AND is_cancelled = 0
        LIMIT 1
    """, (se_name, item_code), as_dict=True)
    return flt(row[0].valuation_rate) if row else 0.0


# ───────────────────────── read ─────────────────────────

@frappe.whitelist()
def get_saisie_state(date):
    """Return the UI state for the saisie alimentation page on `date`.

    Shape:
        {
          "date": "YYYY-MM-DD",
          "lots": [
            {
              "lot": "LOT-1",
              "se_theoretical": "MAT-STE-2026-...",
              "theoretical_total": 312.5,   # kg (sum of theoretical items)
              "actual_total": 320.0,        # kg (theoretical + correction net)
              "has_correction": true,
              "correction_se": "MAT-STE-..." or null,
              "lines": [
                 {"aliment": "Maïs", "item_code": "ALI-Mais",
                  "qty_theoretical": 65.0, "qty_actual": 66.56,
                  "stock_uom": "Kg"},
                 ...
              ]
            },
            ...
          ]
        }

    Lots without a theoretical SE (scheduler hadn't run yet, or no population)
    are omitted — the UI shows "Aucune distribution prévue" if `lots` is empty.
    """
    date = getdate(date)

    # All theoretical SEs for this date — one per lot
    rows = frappe.db.sql("""
        SELECT name, id_lot, remarks
        FROM `tabStock Entry`
        WHERE remarks LIKE %s AND docstatus = 1
        ORDER BY id_lot
    """, (f"{THEO_MARKER_PREFIX}%_{date}%",), as_dict=True)

    out = []
    for r in rows:
        lot = r.id_lot
        if not lot:
            # Old SEs without id_lot custom field — skip
            continue
        theo_items = _se_items(r.name)
        theo_total = sum(flt(L.qty) for L in theo_items)
        if theo_total <= 0:
            continue

        corr_se = _find_se(CORR_MARKER_PREFIX, lot, date)
        corr_total_delta = 0.0
        corr_items_by_code = {}
        if corr_se:
            corr_doc_type = frappe.db.get_value("Stock Entry", corr_se,
                                                 "stock_entry_type")
            sign = 1 if corr_doc_type == "Material Issue" else -1
            for ci in _se_items(corr_se):
                corr_items_by_code[ci.item_code] = sign * flt(ci.qty)
                corr_total_delta += sign * flt(ci.qty)

        lines = []
        for L in theo_items:
            delta = corr_items_by_code.get(L.item_code, 0.0)
            lines.append({
                "aliment": L.aliment,
                "item_code": L.item_code,
                "qty_theoretical": round(flt(L.qty), 3),
                "qty_actual": round(flt(L.qty) + delta, 3),
                "stock_uom": L.stock_uom or "Kg",
            })

        out.append({
            "lot": lot,
            "se_theoretical": r.name,
            "theoretical_total": round(theo_total, 3),
            "actual_total": round(theo_total + corr_total_delta, 3),
            "has_correction": bool(corr_se),
            "correction_se": corr_se,
            "lines": lines,
        })

    return {"date": str(date), "lots": out}


# ───────────────────────── write ─────────────────────────

def _cancel_existing_correction(lot, date):
    """If a correction SE exists for (lot, date), cancel it. Returns the
    cancelled name or None. Idempotency helper for post_correction."""
    name = _find_se(CORR_MARKER_PREFIX, lot, date)
    if not name:
        return None
    se = frappe.get_doc("Stock Entry", name)
    se.cancel()
    return name


@frappe.whitelist()
def post_correction(date, lot, actual_total):
    """Reconcile actual vs theoretical for one (lot, date).

    Args:
        date:          'YYYY-MM-DD'
        lot:           Lot name (e.g. 'LOT-1')
        actual_total:  total kg actually distributed to this lot on `date`.
                       0 = none distributed (full reversal).

    Returns:
        {
          "status": "no_change" | "posted" | "reversed",
          "theoretical_total": <float>,
          "actual_total":       <float>,
          "delta":              <float>,
          "ratio":              <float>,
          "correction_se":      <name or None>,
          "cancelled_previous": <name or None>,
        }
    """
    date = getdate(date)
    actual_total = flt(actual_total)
    if actual_total < 0:
        frappe.throw("Le total réel ne peut pas être négatif.")

    theo_se = _find_se(THEO_MARKER_PREFIX, lot, date)
    if not theo_se:
        frappe.throw(
            f"Aucune distribution théorique trouvée pour le lot {lot} "
            f"au {date}. La saisie n'est possible qu'après que le générateur "
            f"automatique ait posté la distribution prévue."
        )

    theo_items = _se_items(theo_se)
    theo_total = sum(flt(L.qty) for L in theo_items)
    if theo_total <= 0:
        frappe.throw(f"Distribution théorique vide pour le lot {lot} au {date}.")

    # Idempotency: drop any prior correction before posting the new one.
    cancelled_previous = _cancel_existing_correction(lot, date)

    delta = actual_total - theo_total
    ratio = actual_total / theo_total

    no_change_response = {
        "status": "no_change",
        "theoretical_total": round(theo_total, 3),
        "actual_total": round(actual_total, 3),
        "delta": 0.0,
        "ratio": 1.0,
        "correction_se": None,
        "cancelled_previous": cancelled_previous,
    }

    # Sub-gram delta: nothing to post. Any prior correction is already cancelled.
    if abs(delta) < 0.001:
        frappe.db.commit()
        return no_change_response

    # Build the correction lines. Two directions:
    #   delta > 0  (more given)  → Material Issue, qty = theoretical × (ratio-1)
    #   delta < 0  (less given)  → Material Receipt at the theoretical SE's own
    #                              valuation_rate, so the round trip nets to
    #                              zero GL impact (same stock at same cost).
    is_issue = delta > 0
    purpose = "Material Issue" if is_issue else "Material Receipt"
    items = []
    for L in theo_items:
        scale = (ratio - 1.0) if is_issue else (1.0 - ratio)
        qty = flt(L.qty) * scale
        if qty <= 0.001:
            continue
        line = {
            "item_code": L.item_code,
            "qty": round(qty, 3),
            "uom": L.stock_uom,
            "stock_uom": L.stock_uom,
            "conversion_factor": 1,
        }
        if is_issue:
            line["s_warehouse"] = WAREHOUSE
        else:
            rate = _valuation_rate_at_issue(theo_se, L.item_code)
            line["t_warehouse"] = WAREHOUSE
            line["basic_rate"] = rate
            if rate == 0:
                # Theoretical SE had no valuation rate (Bin was already negative
                # before the issue). Accept the receipt at 0 — preserves
                # round-trip neutrality on the GL given the broken starting
                # state. Real fix: enter a real Purchase Receipt to seed value.
                line["allow_zero_valuation_rate"] = 1
        items.append(line)

    # Rounding can wipe every line if the delta is dust per aliment.
    if not items:
        frappe.db.commit()
        return no_change_response

    marker = f"{CORR_MARKER_PREFIX}{lot}_{date}"
    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": purpose,
        "company": COMPANY,
        "posting_date": date,
        "posting_time": "23:59:00",  # after the theoretical (00:00:00)
        "set_posting_time": 1,
        "id_lot": lot,
        "items": items,
        "remarks": marker,
    })
    se.insert(ignore_permissions=True)
    se.submit()
    frappe.db.commit()

    return {
        "status": "posted",
        "theoretical_total": round(theo_total, 3),
        "actual_total": round(actual_total, 3),
        "delta": round(delta, 3),
        "ratio": round(ratio, 4),
        "correction_se": se.name,
        "cancelled_previous": cancelled_previous,
    }


@frappe.whitelist()
def post_corrections_batch(date, entries):
    """Save several (lot, actual_total) corrections for one date in a single
    server-side call. Used by the Saisie Alimentation page so all lot rows
    are processed sequentially in one transaction — prevents MariaDB row-lock
    deadlocks that happen when the JS fires parallel post_correction calls
    that touch the same Bin row (most lots share Maïs / Soja).

    Args:
        date:     'YYYY-MM-DD'
        entries:  list of {lot: <name>, actual_total: <float>} (or JSON string)

    Returns:
        {
          "posted":    <int>,     # corrections actually written
          "no_change": <int>,     # actual == theoretical (prior also cleared)
          "errors":    [{"lot": ..., "error": ...}, ...],
        }
    """
    import json
    if isinstance(entries, str):
        entries = json.loads(entries)

    summary = {"posted": 0, "no_change": 0, "errors": []}
    for entry in entries or []:
        lot = entry.get("lot")
        actual = entry.get("actual_total")
        if lot is None or actual is None:
            summary["errors"].append({"lot": lot, "error": "lot or actual_total missing"})
            continue
        try:
            r = post_correction(date, lot, actual)
            if r["status"] == "posted":
                summary["posted"] += 1
            elif r["status"] == "no_change":
                summary["no_change"] += 1
        except Exception as e:
            summary["errors"].append({"lot": lot, "error": str(e)})
            # frappe.db.rollback() not needed: post_correction commits per-call
            # success and frappe.throw doesn't leave a half-written SE.
    return summary


@frappe.whitelist()
def cancel_correction(date, lot):
    """Cancel the correction SE for (lot, date) without posting a new one.
    Reverts the (lot, date) to the theoretical-only state. Returns the
    cancelled SE name, or None if there was nothing to cancel."""
    name = _cancel_existing_correction(lot, getdate(date))
    frappe.db.commit()
    return name
