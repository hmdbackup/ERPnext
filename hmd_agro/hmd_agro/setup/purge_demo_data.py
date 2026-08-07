"""Wipe the fabricated demo herd and its events, to make room for the real data.

Written for FIN-S99: the seeded demo dataset (animals `999xxxxxxx`, one catch-all
lot, invented traites) distorts every indicator, so it has to go before the real
export is loaded.

Deletes the herd-linked doctypes children-first, then the animals. Submitted
`Decompte Lait Mensuel` documents are cancelled first so their GL entries are
reversed rather than orphaned; everything else is removed with raw deletes
(link checks bypassed — the whole graph goes at once).

Masters that the real import re-uses (Lot, Batiment, Aliment, Ration, Personnel,
Taureau, Grille Prix Lait) are LEFT ALONE.

Idempotent / dry-run. TAKE A BACKUP FIRST — `bench --site <site> backup`.
Run: bench --site <site> execute hmd_agro.hmd_agro.setup.purge_demo_data.run --kwargs '{"dry_run": 1}'
"""
import frappe

# children-first; Animal last because everything links to it
ORDER = [
    "Traite",
    "Etat Corporel",
    "Pesee",
    "Avortement",
    "Note Mobilite",
    "Traitement",
    "Alerte",
    "Allotement History",
    "Lot Ration History",
    "Allotment Session",
    "Insemination",
    "Velage",
    "Lactation",
    "Bilan Lait Journalier",
    "Snapshot Journalier",
    "Rapport Journalier Importe",
    "Animal",
]

# Child tables of the doctypes above. A raw parent delete does NOT cascade, and
# orphan rows keep showing up in aggregate queries — they must go explicitly.
CHILD_TABLES = {
    "Bilan Lait Vente": "Bilan Lait Journalier",
    "Traitement Medicale": "Traitement",
    "Allotment Session Row": "Allotment Session",
}

# Animal fields pointing at docs deleted before it — cleared to avoid dangling links
ANIMAL_LINKS = ("id_ia_fecondante", "id_velage_naissance", "id_mere", "id_pere")


def _cancel_decomptes(dry_run, log):
    """Submitted docs: cancel so the GL entries reverse, then delete."""
    names = frappe.get_all("Decompte Lait Mensuel", pluck="name")
    if not names:
        log.append("Decompte Lait Mensuel : 0")
        return
    if not dry_run:
        for name in names:
            doc = frappe.get_doc("Decompte Lait Mensuel", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Decompte Lait Mensuel", name, force=True, ignore_permissions=True)
    log.append(f"Decompte Lait Mensuel : -{len(names)} (annulés puis supprimés)")


def run(dry_run=True):
    dry_run = int(dry_run)
    log = []

    _cancel_decomptes(dry_run, log)

    if not dry_run:
        for field in ANIMAL_LINKS:
            frappe.db.sql(f"UPDATE `tabAnimal` SET `{field}` = NULL")

    for doctype in ORDER:
        if not frappe.db.table_exists(doctype):
            continue
        count = frappe.db.count(doctype)
        if count and not dry_run:
            frappe.db.delete(doctype)
        log.append(f"{doctype:26s}: -{count}")

    for child, parent in CHILD_TABLES.items():
        if not frappe.db.table_exists(child):
            continue
        count = frappe.db.count(child)
        if count and not dry_run:
            frappe.db.delete(child, {"parenttype": parent})
        log.append(f"{child:26s}: -{count} (table enfant de {parent})")

    if not dry_run:
        frappe.db.sql("UPDATE `tabLot` SET nb_animaux = 0")
        frappe.db.commit()
        frappe.clear_cache()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Purge du jeu de démonstration")
    for line in log:
        print("  " + line)
    return {"mode": mode, "log": log}
