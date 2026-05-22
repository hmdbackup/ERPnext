"""
ST5-15 — Feed correction backend (Saisie Alimentation).

The nightly generator (SCRUM-123) posts a THEORETICAL Material Issue per
(lot, date) computed as `ration.composition × population`. Reality differs:
feed is spilled, lots get more/less than planned, sometimes no feed is
delivered at all. This module lets the farmer record the ACTUAL total
delivered per lot per day; the system proportionally scales each aliment
line and posts a delta Stock Entry to bring Bin / SLE / GL in line with
reality.

Design choices (the supervisor's per-aliment architecture call):
  * Saisie is by ONE total kg per ALIMENT per day — the farmer reports
    "we distributed X kg of Maïs across the farm". The system splits the
    delta proportionally back to each lot using that aliment.
  * The theoretical SE stays UNCHANGED — audit trail preserves both what was
    planned and what was actually given.
  * Each per-lot correction line gets its own Stock Entry tagged
    `RATION_CORRECTION_<lot>_<date>_<item_code>`:
       - actual > theoretical → Material Issue for the additional delta
       - actual < theoretical → Material Receipt putting stock back at the
         theoretical SE's own valuation rate (zero GL impact on round trip)
  * Re-saisie is idempotent: any existing per-(lot, item, date) correction
    SE is cancelled before posting the new one.

Public API (whitelisted):
  - get_aliment_state(date)                                — UI fetch
  - post_aliment_corrections_batch(date, entries)           — UI save
  - cancel_aliment_correction(date, item_code)              — UI clear
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

def _find_all_correction_ses(lot, date):
    """Return all submitted correction SEs for (lot, date), newest first.
    Per-aliment corrections post one SE per (item × direction) so a single
    (lot, date) can have multiple SEs that all need aggregating in the state
    view."""
    marker = f"{CORR_MARKER_PREFIX}{lot}_{getdate(date)}"
    return frappe.db.sql("""
        SELECT name, stock_entry_type FROM `tabStock Entry`
        WHERE remarks LIKE %s AND docstatus = 1
        ORDER BY creation DESC
    """, (f"{marker}%",), as_dict=True)


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

        # Aggregate across ALL correction SEs for this (lot, date) — the
        # per-aliment model posts one SE per item per direction, so multiple
        # SEs per lot are normal. corr_se (singular) is kept as the most
        # recent for backward compat with callers that just need ONE name.
        all_corr_ses = _find_all_correction_ses(lot, date)
        corr_se = all_corr_ses[0].name if all_corr_ses else None
        corr_total_delta = 0.0
        corr_items_by_code = {}
        for se_info in all_corr_ses:
            sign = 1 if se_info.stock_entry_type == "Material Issue" else -1
            for ci in _se_items(se_info.name):
                signed = sign * flt(ci.qty)
                corr_items_by_code[ci.item_code] = (
                    corr_items_by_code.get(ci.item_code, 0.0) + signed)
                corr_total_delta += signed

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


# ───────────────────────── per-aliment view (supervisor model) ─────────────────────────
# The page UI shows one row per aliment (not per lot). The farmer enters
# the TOTAL actual distributed across the farm for each aliment; the system
# splits the delta back proportionally across every lot that uses that
# aliment in its theoretical ration. Per-(lot, item) correction SEs are
# posted with marker `RATION_CORRECTION_<lot>_<date>_<item_code>`. Reports
# still filter on `RATION_CORRECTION_%` so they pick these up the same way.


@frappe.whitelist()
def get_aliment_state(date):
    """Return per-aliment state across the herd for `date` — transposes
    get_saisie_state so the UI can show one row per aliment with a per-lot
    drill-down. Aliments with theoretical_total = 0 are omitted (no
    distribution today, nothing to correct against).

    Shape:
      {
        "date": "YYYY-MM-DD",
        "aliments": [
          {
            "aliment": "Maïs", "item_code": "ALI-Mais", "stock_uom": "Kg",
            "theoretical_total": 168.0, "actual_total": 173.0,
            "has_correction": true,
            "lots": [
              {"lot": "LOT1", "qty_theoretical": 6.0, "qty_actual": 6.18},
              ...
            ]
          }, ...
        ]
      }
    """
    state = get_saisie_state(date)
    by_item = {}
    for lot_state in state["lots"]:
        for line in lot_state["lines"]:
            ic = line["item_code"]
            entry = by_item.setdefault(ic, {
                "aliment": line["aliment"], "item_code": ic,
                "stock_uom": line["stock_uom"],
                "theoretical_total": 0.0, "actual_total": 0.0,
                "has_correction": False, "lots": [],
            })
            entry["theoretical_total"] += line["qty_theoretical"]
            entry["actual_total"] += line["qty_actual"]
            if abs(line["qty_actual"] - line["qty_theoretical"]) > 0.001:
                entry["has_correction"] = True
            entry["lots"].append({
                "lot": lot_state["lot"],
                "qty_theoretical": line["qty_theoretical"],
                "qty_actual": line["qty_actual"],
            })
    aliments = [
        {**v, "theoretical_total": round(v["theoretical_total"], 3),
         "actual_total": round(v["actual_total"], 3)}
        for v in by_item.values() if v["theoretical_total"] > 0
    ]
    aliments.sort(key=lambda a: a["aliment"])
    return {"date": str(getdate(date)), "aliments": aliments}


def _find_aliment_correction_se(lot, date, item_code):
    """Find the per-(lot, date, item_code) correction SE if it exists. Marker
    suffix `_<item_code>` distinguishes per-aliment SEs from legacy per-lot
    corrections (which had no suffix). Returns SE name or None."""
    marker = f"{CORR_MARKER_PREFIX}{lot}_{getdate(date)}_{item_code}"
    row = frappe.db.sql("""
        SELECT name FROM `tabStock Entry`
        WHERE remarks = %s AND docstatus = 1
        ORDER BY creation DESC LIMIT 1
    """, (marker,))
    return row[0][0] if row else None


def _cancel_existing_aliment_correction(lot, date, item_code):
    """Idempotency: cancel any prior (lot, date, item_code) correction SE.
    Returns cancelled name or None."""
    name = _find_aliment_correction_se(lot, date, item_code)
    if not name:
        return None
    se = frappe.get_doc("Stock Entry", name)
    se.cancel()
    return name


def _post_lot_item_correction(date, lot, item_code, stock_uom, qty_delta, theo_se):
    """Post a single-line correction SE for one (lot, item_code) with the
    given signed `qty_delta`. Posts ONE single-line SE per call — supports
    mixed-direction days because each aliment gets its own SE.

    qty_delta > 0 → Material Issue (extra given)
    qty_delta < 0 → Material Receipt at the theoretical SE's own valuation
                    rate (GL-neutral round trip)
    """
    if abs(qty_delta) < 0.001:
        return None
    is_issue = qty_delta > 0
    qty = abs(qty_delta)
    line = {
        "item_code": item_code, "qty": round(qty, 3),
        "uom": stock_uom, "stock_uom": stock_uom, "conversion_factor": 1,
    }
    if is_issue:
        line["s_warehouse"] = WAREHOUSE
    else:
        rate = _valuation_rate_at_issue(theo_se, item_code)
        line["t_warehouse"] = WAREHOUSE
        line["basic_rate"] = rate
        if rate == 0:
            line["allow_zero_valuation_rate"] = 1

    marker = f"{CORR_MARKER_PREFIX}{lot}_{getdate(date)}_{item_code}"
    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Issue" if is_issue else "Material Receipt",
        "company": COMPANY,
        "posting_date": getdate(date),
        "posting_time": "23:59:00",
        "set_posting_time": 1,
        "id_lot": lot,
        "items": [line],
        "remarks": marker,
    })
    se.insert(ignore_permissions=True)
    se.submit()
    return se.name


@frappe.whitelist()
def post_aliment_corrections_batch(date, entries):
    """Apply per-aliment total corrections — proportional cross-lot split.

    For each (item_code, actual_total) in `entries`:
      1. Find every theoretical SE line containing item_code for `date`.
      2. theoretical_total = sum across lots.
      3. delta = actual_total - theoretical_total.
      4. Per lot with this item: share = lot_qty / theoretical_total
                                lot_delta = share * delta.
      5. Cancel any prior per-(lot, date, item_code) correction SE.
      6. Post a new single-line SE per lot (Issue or Receipt by sign).

    Mixed-direction days are naturally supported: each aliment gets its own
    SE per lot, independent of others.

    Args:
        date:    'YYYY-MM-DD'
        entries: list of {item_code, actual_total} (or JSON string)

    Returns:
        {
          "posted":    int,   # per-lot SEs written
          "no_change": int,   # aliments whose new total = theoretical
          "errors":    [{item_code, error}, ...],
        }
    """
    import json
    if isinstance(entries, str):
        entries = json.loads(entries)
    date = getdate(date)

    # Resolve theoretical {item_code: {lot: {qty, stock_uom, se_name}}}
    theo_rows = frappe.db.sql("""
        SELECT se.id_lot AS lot, se.name AS se_name,
               sed.item_code, sed.qty, sed.stock_uom
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        WHERE se.docstatus = 1
          AND se.remarks LIKE %s
          AND se.id_lot IS NOT NULL
    """, (f"{THEO_MARKER_PREFIX}%_{date}%",), as_dict=True)
    theo_by_item = {}
    for r in theo_rows:
        theo_by_item.setdefault(r.item_code, {})[r.lot] = {
            "qty": flt(r.qty), "stock_uom": r.stock_uom or "Kg",
            "se_name": r.se_name,
        }

    summary = {"posted": 0, "no_change": 0, "errors": []}
    for entry in entries or []:
        ic = entry.get("item_code")
        actual_total = entry.get("actual_total")
        if not ic or actual_total is None:
            summary["errors"].append({"item_code": ic,
                "error": "item_code or actual_total missing"})
            continue
        try:
            actual_total = flt(actual_total)
            if actual_total < 0:
                raise ValueError("Le total réel ne peut pas être négatif.")
            if ic not in theo_by_item:
                raise ValueError(f"Aucune ration n'utilise {ic} au {date}.")
            lot_qtys = theo_by_item[ic]
            theo_total = sum(v["qty"] for v in lot_qtys.values())
            if theo_total <= 0:
                raise ValueError(f"Total théorique nul pour {ic} au {date}.")
            delta = actual_total - theo_total

            # Idempotency: drop any prior per-lot SE for this aliment first.
            for lot in lot_qtys:
                _cancel_existing_aliment_correction(lot, date, ic)

            if abs(delta) < 0.001:
                summary["no_change"] += 1
                continue

            for lot, info in lot_qtys.items():
                share = info["qty"] / theo_total
                lot_delta = round(share * delta, 3)
                posted = _post_lot_item_correction(
                    date, lot, ic, info["stock_uom"], lot_delta, info["se_name"])
                if posted:
                    summary["posted"] += 1
        except Exception as e:
            summary["errors"].append({"item_code": ic, "error": str(e)})
    frappe.db.commit()
    return summary


@frappe.whitelist()
def cancel_aliment_correction(date, item_code):
    """Cancel all per-lot correction SEs for one (date, item_code) — UI
    'reset to theoretical' action. Returns count of SEs cancelled."""
    date = getdate(date)
    theo_lots = frappe.db.sql_list("""
        SELECT DISTINCT id_lot FROM `tabStock Entry`
        WHERE docstatus = 1 AND remarks LIKE %s AND id_lot IS NOT NULL
    """, (f"{THEO_MARKER_PREFIX}%_{date}%",))
    cancelled = 0
    for lot in theo_lots:
        if _cancel_existing_aliment_correction(lot, date, item_code):
            cancelled += 1
    frappe.db.commit()
    return {"cancelled": cancelled}


