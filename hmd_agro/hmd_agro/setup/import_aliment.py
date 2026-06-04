"""Import the complete feed (Aliment) master — 13 feeds.

REWRITTEN 2026-06-04: was a *reconcile* (added 5 + updated prices of existing),
which fails on a fresh site (base feeds + company/warehouse/item-groups absent).
Now a COMPLETE create-if-not-exists import. Prices = current Rapport Mensuel values
(authoritative), Bicarbonate name corrected ("sodium"), ms_pct from the farm master
where known. Each Aliment auto-creates an ALI- Item under its type's Item Group.

PREREQUISITE: import_stock_setup (item groups + warehouse) + Company hmd-agro.
Idempotent / dry-run. Run AFTER import_stock_setup.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_aliment.run --kwargs '{"dry_run":1}'
"""
import frappe

# (nom, type_aliment, prix_unitaire, ms_pct|None) — unite is always KG
ALIMENTS = [
    ("Soja",                            "CONCENTRE",  1.4,   0.9038),
    ("Mais",                            "CONCENTRE",  1.0,   0.88),
    ("Dreche de Brasserie",             "CONCENTRE",  0.19,  0.27),
    ("7 Expert",                        "CONCENTRE",  1.246, None),
    ("Machia Genisse",                  "CONCENTRE",  1.091, None),
    ("Machia Starter",                  "CONCENTRE",  1.218, None),
    ("Ensilage Mais",                   "ENSILAGE",   0.4,   0.30),
    ("Ensilage Vece/Triticale/Avoine",  "ENSILAGE",   0.12,  None),
    ("Foin d'Avoine",                   "FOURRAGE",   0.58,  0.88),
    ("Foin de Luzerne",                 "FOURRAGE",   0.83,  None),
    ("CMV",                             "MINERAL",    2.5,   0.95),
    ("Paille de Ble",                   "PAILLE",     0.55,  0.905),
    ("Bicarbonate de sodium",           "SUPPLEMENT", 1.547, 0.99),
]


def run(dry_run=True):
    dry_run = int(dry_run)
    created = skipped = 0
    errors = []
    for nom, type_al, prix, ms in ALIMENTS:
        try:
            if frappe.db.exists("Aliment", nom):
                skipped += 1
                continue
            doc_dict = {
                "doctype": "Aliment",
                "nom_aliment": nom,
                "type_aliment": type_al,
                "unite": "KG",
                "prix_unitaire": prix,
            }
            if ms is not None:
                doc_dict["ms_pct"] = ms
            if not dry_run:
                frappe.get_doc(doc_dict).insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            errors.append({"nom": nom, "error": str(e)})

    if not dry_run:
        frappe.db.commit()
    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Aliment import (complete, {len(ALIMENTS)} feeds): "
          f"created={created}, skipped(existing)={skipped}, errors={len(errors)}")
    for e in errors[:5]:
        print(f"  ERR {e['nom']}: {e['error']}")
    return {"created": created, "skipped": skipped, "errors": errors}
