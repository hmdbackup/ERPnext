"""
Sprint 5 — SCRUM-123 — Feed distribution generator.

Posts one Stock Entry Material Issue per (lot, day) representing the daily
ration consumption for each active lot, with one line per aliment in the
ration. The resulting Stock Ledger Entries are immutable — future price
changes can't rewrite them, which is what the supervisor's price-history
concern requires.

Public API:
  - backfill_distribution(start_date, end_date, dry_run=False) — historical
  - generate_daily_distribution()                              — scheduler

Both use the same underlying per-date post_distribution_for_date function.

Idempotency: each Stock Entry carries `remarks` starting with
`RATION_DIST_<lot>_<date>`. Re-running on a (lot, date) that already has a
submitted SE is a no-op.

Self-contained: this module does NOT import from rapport_mensuel.py — the
population logic is replicated here. The Aliment Item link, prix_unitaire,
warehouse, and migration helpers ARE shared via the existing module layout.
"""
import frappe
from frappe.utils import getdate, add_days, today
from hmd_agro.hmd_agro.doctype.lot_ration_history.lot_ration_history import (
    ration_on_date,
)


COMPANY = "hmd-agro"
WAREHOUSE = "Magasin Principal - HMD"


# ───────────────────────── helpers ─────────────────────────

def _prefetch_population_data(end_date):
    """Pre-fetch Animal + Allotement History rows once for a backfill run.
    `end_date` caps the data — we don't need rows for events after that day.
    Returns a dict consumed by `_populations_on_date`."""
    animal_rows = frappe.db.sql("""
        SELECT name, est_achat, date_naissance, date_entree,
               statut, date_sortie, id_lot
        FROM `tabAnimal`
        WHERE (CASE WHEN est_achat=1 THEN date_entree ELSE date_naissance END) <= %s
    """, (end_date,), as_dict=True)
    for a in animal_rows:
        e = a.date_entree if a.est_achat else a.date_naissance
        a["entry_date"] = getdate(e) if e else None
        a["exit_date"] = getdate(a.date_sortie) if a.date_sortie else None

    allot_history = {}
    if animal_rows:
        names = [a.name for a in animal_rows]
        for r in frappe.db.sql("""
            SELECT animal, to_lot, DATE(creation) AS dt
            FROM `tabAllotement History`
            WHERE animal IN %s AND DATE(creation) <= %s
            ORDER BY animal, creation ASC
        """, (names, end_date), as_dict=True):
            allot_history.setdefault(r.animal, []).append((getdate(r.dt), r.to_lot))

    return {"animal_rows": animal_rows, "allot_history": allot_history}


def _populations_on_date(day, prefetched):
    """Return {lot_name: animal_count} for `day`, using pre-fetched data.
    Mirrors the logic in rapport_mensuel.py:680-695 — kept standalone so
    feed_distribution stays decoupled from the report module."""
    day = getdate(day)
    per_lot = {}
    for a in prefetched["animal_rows"]:
        if not a.entry_date or a.entry_date > day:
            continue
        # Skip if exited on or before this day (i.e., not present anymore)
        if a.statut != "ACTIF" and (not a.exit_date or a.exit_date <= day):
            continue
        # Walk allotement history backwards to find the lot on `day`
        lot = a.id_lot
        for h_dt, h_to in reversed(prefetched["allot_history"].get(a.name, [])):
            if h_dt <= day:
                lot = h_to
                break
        if lot:
            per_lot[lot] = per_lot.get(lot, 0) + 1
    return per_lot


# Module-level cache so we don't log the same missing-Item warning N times.
_warned_missing_items = set()


def _composition_for_ration(ration_name):
    """Return list of dicts: {aliment, item_code, qty_per_animal, stock_uom}.
    Filters out aliments not yet migrated to an ERPNext Item (warns once)."""
    rows = frappe.db.sql("""
        SELECT c.aliment, c.quantite, a.item, i.stock_uom
        FROM `tabComposition Ration` c
        JOIN `tabAliment` a ON c.aliment = a.name
        LEFT JOIN `tabItem` i ON i.name = a.item
        WHERE c.parent = %s
    """, ration_name, as_dict=True)
    out = []
    for r in rows:
        if not r.item:
            if r.aliment not in _warned_missing_items:
                print(f"     ⚠ aliment '{r.aliment}' n'a pas d'Item lié — "
                      f"sera ignoré dans la distribution. Lancez "
                      f"aliment_migration.migrate_aliments d'abord.")
                _warned_missing_items.add(r.aliment)
            continue
        out.append({
            "aliment": r.aliment,
            "item_code": r.item,
            "qty_per_animal": float(r.quantite or 0),
            "stock_uom": r.stock_uom or "Kg",
        })
    return out


def _already_posted(lot, day):
    """Check for an existing submitted Stock Entry tagged for this (lot, day).
    Returns True iff a matching SE exists (so the caller can skip)."""
    marker = f"RATION_DIST_{lot}_{getdate(day)}"
    row = frappe.db.sql("""
        SELECT name FROM `tabStock Entry`
        WHERE remarks LIKE %s AND docstatus = 1 LIMIT 1
    """, (f"{marker}%",))
    return bool(row)


# ───────────────────────── preview ─────────────────────────

@frappe.whitelist()
def get_distribution_preview(target_date):
    """Return what WOULD be posted for `target_date` without writing anything.
    Used by dry_run mode and by the future Saisie Alimentation page.
    Returns: {lot: [{item_code, qty, aliment, stock_uom, qty_per_animal, pop}]}"""
    target_date = getdate(target_date)
    prefetched = _prefetch_population_data(target_date)
    pop = _populations_on_date(target_date, prefetched)

    active_lots = frappe.get_all("Lot", filters={"actif": 1},
                                  fields=["name"], order_by="name")
    out = {}
    for lot in active_lots:
        n = pop.get(lot.name, 0)
        if n == 0:
            continue
        ration = ration_on_date(lot.name, target_date)
        if not ration:
            continue
        lines = []
        for c in _composition_for_ration(ration):
            qty = c["qty_per_animal"] * n
            if qty <= 0:
                continue
            lines.append({
                "item_code": c["item_code"],
                "qty": round(qty, 3),
                "aliment": c["aliment"],
                "stock_uom": c["stock_uom"],
                "qty_per_animal": c["qty_per_animal"],
                "pop": n,
            })
        if lines:
            out[lot.name] = lines
    return out


# ───────────────────────── posting ─────────────────────────

def _build_stock_entry(lot, day, lines):
    """Build (insert+submit) one Material Issue Stock Entry for (lot, day)
    with the given lines. Returns the SE name."""
    marker = f"RATION_DIST_{lot}_{day}"
    items = []
    for L in lines:
        items.append({
            "item_code": L["item_code"],
            "qty": L["qty"],
            "uom": L["stock_uom"],
            "stock_uom": L["stock_uom"],
            "conversion_factor": 1,
            "s_warehouse": WAREHOUSE,
        })
    # set_posting_time=1 is REQUIRED for backdated entries — without it
    # ERPNext silently overrides posting_date+posting_time to now() at submit.
    # posting_time fixed at 00:00:00 so all distribution SEs for one day are
    # deterministically ordered (by creation timestamp ties broken alphabetically
    # via lot name in the loop).
    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Issue",
        "company": COMPANY,
        "posting_date": day,
        "posting_time": "00:00:00",
        "set_posting_time": 1,
        "id_lot": lot,
        "items": items,
        "remarks": marker,
    })
    se.insert(ignore_permissions=True)
    se.submit()
    return se.name


@frappe.whitelist()
def cancel_distributions(start_date, end_date):
    """Cleanup helper: cancel every submitted Stock Entry with a
    RATION_DIST_*_<date> remark in the given date range (matched on the
    encoded date inside the marker, since posting_date may be wrong if a
    prior buggy run was made). The SE stays in DB as docstatus=2; safe to
    re-run backfill afterwards because `_already_posted` only looks at
    docstatus=1.

    Use sparingly — this is for unwinding a wrong backfill, not routine ops."""
    start = getdate(start_date)
    end = getdate(end_date)
    print(f"\n  Cancel distributions: {start} → {end}")
    cancelled = 0
    skipped = 0
    errors = 0
    day = start
    while day <= end:
        # Match marker by encoded date — robust to posting_date bug
        rows = frappe.db.sql("""
            SELECT name FROM `tabStock Entry`
            WHERE remarks LIKE %s AND docstatus = 1
        """, (f"RATION_DIST_%_{day}%",), as_dict=True)
        for r in rows:
            try:
                se = frappe.get_doc("Stock Entry", r.name)
                se.cancel()
                cancelled += 1
                print(f"     [cancel] {r.name}")
            except Exception as e:
                errors += 1
                print(f"     [ERROR]  {r.name}: {type(e).__name__}: {e}")
        day = add_days(day, 1)
    frappe.db.commit()
    print(f"\n  Cancelled: {cancelled}, errors: {errors}\n")
    return {"cancelled": cancelled, "errors": errors}


@frappe.whitelist()
def delete_cancelled_distributions():
    """Cleanup: delete every CANCELLED (docstatus=2) Stock Entry whose
    remarks match `RATION_DIST_*`. Use this to clear orphans left by a
    previous bad backfill that was already cancelled via `cancel_distributions`.

    Why this is safe: a docstatus=2 SE has no impact on stock (its SLEs are
    flagged is_cancelled=1, the Bin already reflects the reversal). Deleting
    just removes the lingering rows from list views."""
    rows = frappe.db.sql("""
        SELECT name FROM `tabStock Entry`
        WHERE remarks LIKE 'RATION_DIST_%' AND docstatus = 2
    """, as_dict=True)
    deleted = 0
    errors = 0
    for r in rows:
        try:
            frappe.delete_doc("Stock Entry", r.name,
                              ignore_permissions=True, force=True)
            deleted += 1
        except Exception as e:
            errors += 1
            print(f"     [ERROR] {r.name}: {type(e).__name__}: {e}")
    frappe.db.commit()
    print(f"\n  Deleted {deleted} cancelled distribution SEs, errors={errors}\n")
    return {"deleted": deleted, "errors": errors}


def post_distribution_for_date(target_date, dry_run=False, prefetched=None,
                                 verbose=True):
    """Post one Material Issue per active lot for `target_date`.
    Returns stats: {posted, skipped_already_posted, skipped_no_ration,
                    skipped_no_population, skipped_no_lines, errors}."""
    target_date = getdate(target_date)
    if prefetched is None:
        prefetched = _prefetch_population_data(target_date)
    pop = _populations_on_date(target_date, prefetched)

    stats = {"posted": 0, "skipped_already_posted": 0,
             "skipped_no_ration": 0, "skipped_no_population": 0,
             "skipped_no_lines": 0, "errors": 0}

    active_lots = frappe.get_all("Lot", filters={"actif": 1},
                                  fields=["name"], order_by="name")
    for lot_row in active_lots:
        lot = lot_row.name
        n = pop.get(lot, 0)
        if n == 0:
            if verbose:
                print(f"     [skip-pop=0]    {lot}")
            stats["skipped_no_population"] += 1
            continue
        if _already_posted(lot, target_date):
            if verbose:
                print(f"     [skip-seeded]   {lot} ({target_date})")
            stats["skipped_already_posted"] += 1
            continue
        ration = ration_on_date(lot, target_date)
        if not ration:
            if verbose:
                print(f"     [skip-no-rat]   {lot} (pas de ration pour {target_date})")
            stats["skipped_no_ration"] += 1
            continue
        lines = []
        for c in _composition_for_ration(ration):
            qty = c["qty_per_animal"] * n
            if qty <= 0:
                continue
            lines.append({
                "item_code": c["item_code"],
                "qty": round(qty, 3),
                "stock_uom": c["stock_uom"],
            })
        if not lines:
            if verbose:
                print(f"     [skip-empty]    {lot} (composition {ration} vide ou non migrée)")
            stats["skipped_no_lines"] += 1
            continue

        if dry_run:
            line_summary = ", ".join(
                f"{L['item_code']}×{L['qty']}" for L in lines
            )
            if verbose:
                print(f"     [DRY]           {lot} ({target_date}) "
                      f"pop={n} ration={ration} → {line_summary}")
            stats["posted"] += 1
            continue

        try:
            se_name = _build_stock_entry(lot, target_date, lines)
            if verbose:
                line_summary = ", ".join(
                    f"{L['item_code']}×{L['qty']}" for L in lines
                )
                print(f"     [post]          {lot} ({target_date}) "
                      f"pop={n} → SE={se_name} ({line_summary})")
            stats["posted"] += 1
            frappe.db.commit()
        except Exception as e:
            if verbose:
                print(f"     [ERROR]         {lot} ({target_date}): "
                      f"{type(e).__name__}: {e}")
            stats["errors"] += 1
            frappe.db.rollback()

    return stats


# ───────────────────────── backfill ─────────────────────────

@frappe.whitelist()
def backfill_distribution(start_date, end_date, dry_run=0):
    """Loop day-by-day from start_date to end_date inclusive.
    Pre-fetches Animal + Allotement History once for performance.

    Args:
        start_date: 'YYYY-MM-DD'
        end_date:   'YYYY-MM-DD'
        dry_run:    1 = log what would be posted, no DB writes
                    0 = post for real

    Returns aggregated stats dict."""
    start = getdate(start_date)
    end = getdate(end_date)
    dry_run = int(dry_run) == 1

    print("\n" + "=" * 70)
    print(f"  Feed distribution backfill — {start} → {end}"
          f" ({'DRY RUN' if dry_run else 'POSTING'})")
    print("=" * 70)

    if end < start:
        frappe.throw(f"end_date ({end}) before start_date ({start})")

    # One pre-fetch for the whole range — avoids re-querying Animals each day.
    prefetched = _prefetch_population_data(end)
    print(f"  Pre-fetched: {len(prefetched['animal_rows'])} animaux, "
          f"{sum(len(v) for v in prefetched['allot_history'].values())} "
          f"événements Allotement History\n")

    agg = {"posted": 0, "skipped_already_posted": 0, "skipped_no_ration": 0,
           "skipped_no_population": 0, "skipped_no_lines": 0, "errors": 0}

    day = start
    day_count = 0
    while day <= end:
        if day_count > 0 and day_count % 30 == 0:
            print(f"\n  ── Jour {day} ({day_count} jours traités) ──")
        else:
            print(f"\n  ── {day} ──")
        s = post_distribution_for_date(day, dry_run=dry_run,
                                        prefetched=prefetched, verbose=True)
        for k, v in s.items():
            agg[k] = agg.get(k, 0) + v
        day = add_days(day, 1)
        day_count += 1

    print("\n" + "=" * 70)
    print(f"  Résumé sur {day_count} jours ({'DRY RUN' if dry_run else 'POSTED'}):")
    for k, v in agg.items():
        if v:
            print(f"    {k:30s} : {v}")
    print("=" * 70 + "\n")
    return agg


# ───────────────────────── scheduler ─────────────────────────

@frappe.whitelist()
def generate_daily_distribution():
    """Scheduler entry point. Posts yesterday's distribution.
    Why yesterday: we want to record consumption for COMPLETED days only.
    Running at 00:01 UTC will post the previous day's data."""
    yesterday = add_days(getdate(today()), -1)
    print(f"\n[Scheduler] Generating feed distribution for {yesterday}")
    s = post_distribution_for_date(yesterday, dry_run=False, verbose=True)
    print(f"[Scheduler] Done: {s}")
    return s
