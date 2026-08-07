"""Run the contrôle-laitier import from the CLI, without the page.

The Import Traites page uploads a file, then enqueues `_process_import` on the
long queue. For a bulk load (a six-month workbook, ~18 000 traites) it is simpler
to point at a file already sitting in the site's private folder and run the same
job synchronously.

Reuses the page's `_process_import` verbatim, so the CLI path and the UI path
cannot drift apart.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_traites_fichier.run \
       --kwargs '{"filename": "CL.xlsx", "resolutions": {"9222": "2300259222"}}'
"""
import os
import shutil

import frappe

FOLDER = "farm_data_drive"


def ensure_file(filename, source_folder=FOLDER):
    """Copy the workbook into private/files and return its File doc's file_url."""
    src = os.path.join(frappe.get_site_path("private", source_folder), filename)
    if not os.path.exists(src):
        frappe.throw(f"Fichier introuvable : {src}")

    existing = frappe.db.get_value("File", {"file_name": filename}, "file_url")
    if existing:
        return existing

    # Let Frappe own the write. It renames on name collision and de-duplicates on
    # content hash, so the URL it stores is often NOT the one we asked for and the
    # in-memory doc keeps the stale value — read the row back to get the truth.
    with open(src, "rb") as f:
        doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "is_private": 1,
            "content": f.read(),
        })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return frappe.db.sql("SELECT file_url FROM `tabFile` WHERE name = %s", doc.name)[0][0]


def preview(filename="CL.xlsx"):
    from hmd_agro.hmd_agro.page.import_traites.import_traites import preview_import
    result = preview_import(ensure_file(filename))
    r = result["date_range"]
    print(f"\n[APERÇU] {filename} — {r['start']} → {r['end']} ({r['days']} jours)")
    print(f"  animaux dans le fichier : {result['total_animals_excel']}")
    print(f"  reconnus                : {result['matched']}")
    print(f"  inconnus                : {result['unmatched']}")
    print(f"  ambigus (à trancher)    : {result['duplicates']}")
    print(f"  traites estimées        : {result['estimated_traites']}")
    return result


def run(filename="CL.xlsx", keep_original=1, resolutions=None):
    """Import synchronously and print the summary."""
    from hmd_agro.hmd_agro.page.import_traites.import_traites import (
        _process_import, get_import_result,
    )
    file_url = ensure_file(filename)
    _process_import(file_url, int(keep_original), frappe.session.user, resolutions or {})
    result = get_import_result(file_url) or {}

    if not result.get("success"):
        print(f"\n[ÉCHEC] {result.get('error', 'aucun résultat')[:800]}")
        return result

    s = result["summary"]
    print(f"\n[IMPORT] {filename}")
    print(f"  traites créées            : {s['created']}")
    print(f"  écrasées                  : {s['overwritten']}")
    print(f"  doublons ignorés          : {s['skipped_duplicate']}")
    print(f"  ignorées — pas d'animal   : {s['skipped_no_animal']}")
    print(f"  ignorées — pas de lactation: {s['skipped_no_lactation']}")
    print(f"  ignorées — après sortie   : {s['skipped_after_sortie']}")
    print(f"  lactations recalculées    : {s['lactations_updated']}")
    print(f"  erreurs                   : {len(s['errors'])}")
    for e in s["errors"][:5]:
        print(f"    {e['animal']} {e['date']}: {e['reason']}")
    return result
