"""Convert Lot Ration History from change-event rows to episode rows.

BEFORE this patch, each row recorded a single change event:
    (lot, from_ration, to_ration, creation)
"What changed at time T" — duration was implicit in the gap to the next row.

AFTER this patch, each row is one episode:
    (lot, ration, date_debut, date_fin)
"Lot L used Ration R during [date_debut, date_fin)". date_fin IS NULL means
the episode is currently open (the lot is still using that ration).

The from_ration / to_ration database columns linger as orphans (Frappe doesn't
drop columns when you remove fields from the doctype JSON) — we read them via
raw SQL during the conversion, then leave them in place. They're invisible to
Frappe afterward.

Idempotent: re-running does nothing (UPDATEs filter on `ration IS NULL`,
DELETEs find no close-only rows the second time, backfill INSERTs skip lots
that already have an open episode).
"""
import frappe
from frappe.utils import getdate, today


def execute():
    if not frappe.db.exists("DocType", "Lot Ration History"):
        return

    # Defensive: skip if the new columns somehow weren't created by model sync
    # (would mean a mis-ordered migration). Better to no-op than to crash.
    cols = {c["Field"] for c in frappe.db.sql(
        "SHOW COLUMNS FROM `tabLot Ration History`", as_dict=True
    )}
    if not {"ration", "date_debut", "date_fin"}.issubset(cols):
        frappe.log_error(
            "Lot Ration History migration skipped: new columns not present.",
            "v1_3 migration",
        )
        return

    # ── Step 1: Convert existing change-event rows to episodes ────────────────
    # Read every row with from_ration / to_ration data. We only process rows
    # that haven't been migrated yet (ration IS NULL) — guarantees idempotency.
    if "to_ration" in cols:
        rows = frappe.db.sql("""
            SELECT name, lot, to_ration, DATE(creation) AS dt
            FROM `tabLot Ration History`
            WHERE ration IS NULL
            ORDER BY lot, creation ASC
        """, as_dict=True)
    else:
        # to_ration column absent (e.g. fresh install) — nothing to migrate.
        rows = []

    by_lot = {}
    for r in rows:
        by_lot.setdefault(r.lot, []).append(r)

    deletes = []
    updated = 0

    for lot_name, events in by_lot.items():
        for i, ev in enumerate(events):
            if not ev.to_ration:
                # Close-only event (ration was cleared). Don't keep it as an
                # episode — the previous episode's date_fin already records the
                # end. Mark for deletion.
                deletes.append(ev.name)
                continue

            # Episode event: ration = to_ration, date_debut = event date.
            # date_fin = the next event's date (any kind — even a close-only
            # event closes this episode), or NULL if this is the latest event.
            next_dt = events[i + 1].dt if i + 1 < len(events) else None
            frappe.db.sql("""
                UPDATE `tabLot Ration History`
                SET ration = %s, date_debut = %s, date_fin = %s
                WHERE name = %s AND ration IS NULL
            """, (ev.to_ration, ev.dt, next_dt, ev.name))
            updated += 1

    if deletes:
        # Chunk the IN clause to avoid query-length limits on large datasets.
        for i in range(0, len(deletes), 500):
            chunk = deletes[i:i + 500]
            frappe.db.sql(
                "DELETE FROM `tabLot Ration History` WHERE name IN %s",
                (tuple(chunk),),
            )

    # ── Step 2: Backfill lots with id_ration_actuelle but no open episode ─────
    # Two cases:
    #   (a) Lot was created before the audit log existed (zero history rows)
    #   (b) Data drift: history says ration was cleared, but Lot.id_ration_actuelle
    #       is still set (someone bypassed _track_ration_change with raw SQL)
    # Both cases: insert an open BASELINE episode so the system reaches a
    # consistent state. Use the lot's creation date as a "best honest guess"
    # for date_debut when we have no better signal.
    backfill = frappe.db.sql("""
        SELECT l.name, l.id_ration_actuelle, DATE(l.creation) AS lot_creation
        FROM `tabLot` l
        WHERE l.id_ration_actuelle IS NOT NULL AND l.id_ration_actuelle != ''
          AND NOT EXISTS (
              SELECT 1 FROM `tabLot Ration History` h
              WHERE h.lot = l.name AND h.date_fin IS NULL AND h.ration IS NOT NULL
          )
    """, as_dict=True)

    backfilled = 0
    for lot in backfill:
        # If there's a previous closed episode, use its date_fin as the start
        # of the new open episode (no gap). Otherwise use the lot's creation.
        prev = frappe.db.sql("""
            SELECT MAX(date_fin) AS latest_fin
            FROM `tabLot Ration History`
            WHERE lot = %s AND date_fin IS NOT NULL
        """, (lot.name,), as_dict=True)
        date_debut = (
            prev[0].latest_fin if prev and prev[0].latest_fin
            else lot.lot_creation or today()
        )
        frappe.get_doc({
            "doctype": "Lot Ration History",
            "lot": lot.name,
            "ration": lot.id_ration_actuelle,
            "date_debut": date_debut,
            "date_fin": None,
            "changed_by": "Administrator",
            "source": "BASELINE",
        }).insert(ignore_permissions=True)
        backfilled += 1

    # ── Step 3: Close orphan open episodes for lots that have no ration set ───
    # Reverse data-drift case: history says lot is on ration X but
    # Lot.id_ration_actuelle is empty. Close the open episode at today.
    orphans = frappe.db.sql("""
        SELECT h.name FROM `tabLot Ration History` h
        JOIN `tabLot` l ON h.lot = l.name
        WHERE h.date_fin IS NULL
          AND (l.id_ration_actuelle IS NULL OR l.id_ration_actuelle = '')
    """, as_dict=True)
    today_d = today()
    for h in orphans:
        frappe.db.set_value(
            "Lot Ration History", h.name, "date_fin", today_d,
            update_modified=False,
        )

    # ── Step 4: Sync Lot.date_affectation_actuelle from open episodes ─────────
    # For every lot with an open episode, write the episode's date_debut into
    # the Lot's display field. Lots without an open episode get NULL.
    open_episodes = frappe.db.sql("""
        SELECT lot, MAX(date_debut) AS date_debut
        FROM `tabLot Ration History`
        WHERE date_fin IS NULL AND ration IS NOT NULL
        GROUP BY lot
    """, as_dict=True)
    open_lots = set()
    for ep in open_episodes:
        frappe.db.set_value(
            "Lot", ep.lot, "date_affectation_actuelle", ep.date_debut,
            update_modified=False,
        )
        open_lots.add(ep.lot)

    # Lots with no open episode → ensure date_affectation_actuelle is NULL
    # (covers the "ration cleared" case after Step 3).
    closed_lots = frappe.db.sql("""
        SELECT name FROM `tabLot`
        WHERE date_affectation_actuelle IS NOT NULL
    """, as_dict=True)
    for l in closed_lots:
        if l.name not in open_lots:
            frappe.db.set_value(
                "Lot", l.name, "date_affectation_actuelle", None,
                update_modified=False,
            )

    frappe.db.commit()
