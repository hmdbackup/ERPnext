"""Derive one Lactation per producing cow from the contrôle-laitier workbook.

The import-traites page attaches every Traite to the Lactation covering its date,
so the lactations must exist first. The farm's export contains no `Lactation`
rows (nor `Velage`), so they are reconstructed from the milk matrix itself:

    date_debut       = the cow's first day with production in the file
    date_tarissement = her last day with production, IF she stops before the end
                       of the file (`DRY_GAP_DAYS` of zeros) — otherwise EN_COURS

APPROXIMATION, and a deliberate one: a cow that calved again inside the period
gets a single continuous lactation instead of two. It is enough for the herd-level
indicators (coût du litre, IOFC, ratio L/C) which sum litres regardless of
lactation, but per-cow lactation curves will be wrong until the real `Lactation`
and `Velage` exports arrive. Every row created is marked as such in `observations`.

Workbook layout: active sheet, row 1 = dates from column B, column A = cow number.

Idempotent (skips a cow that already has a lactation) / dry-run.
Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_lactation_depuis_cl.run --kwargs '{"dry_run": 1}'
"""
import os

import frappe
import openpyxl
from frappe.utils import getdate

FOLDER = "farm_data_drive"
DEFAULT_FILE = "CL.xlsx"
DRY_GAP_DAYS = 10          # trailing zero days after which we call her dry
ORIGIN = "Lactation reconstituée depuis le contrôle laitier (import automatique)"


def _path(source, filename):
    base = source or frappe.get_site_path("private", FOLDER)
    return os.path.join(base, filename)


def read_matrix(source=None, filename=DEFAULT_FILE):
    """Return (dates, {nom_metier: [values]}) from the milk workbook."""
    wb = openpyxl.load_workbook(_path(source, filename), read_only=True, data_only=True)
    rows = list(wb.active.iter_rows(values_only=True))
    if not rows:
        frappe.throw(f"{filename}: fichier vide")

    dates = []
    for cell in rows[0][1:]:
        if cell is None:
            break
        try:
            dates.append(getdate(cell))
        except Exception:
            break

    herd = {}
    for row in rows[1:]:
        if row[0] is None:
            continue
        key = row[0]
        nom = str(int(key)).zfill(4) if isinstance(key, (int, float)) else str(key).strip().zfill(4)
        herd[nom] = [v if isinstance(v, (int, float)) else 0 for v in row[1:1 + len(dates)]]
    return dates, herd


def _window(dates, values):
    """(first, last) dates with production, or (None, None) if she never milked."""
    produced = [i for i, v in enumerate(values) if v and v > 0]
    if not produced:
        return None, None
    return dates[produced[0]], dates[produced[-1]]


def run(dry_run=True, source=None, filename=DEFAULT_FILE, resolutions=None):
    """`resolutions` maps an ambiguous cow number to the Animal it really is —
    same shape as the import-traites page's resolution dialog, so both paths
    agree on which cow a number belongs to."""
    dry_run = int(dry_run)
    dates, herd = read_matrix(source, filename)
    if not dates:
        frappe.throw(f"{filename}: aucune date en ligne 1 (colonnes B+)")

    from hmd_agro.hmd_agro.page.import_traites.import_traites import build_animal_mapping
    animal_map, ambiguous = build_animal_mapping()
    for nom, animal in (resolutions or {}).items():
        animal_map[nom] = animal
        ambiguous.discard(nom)

    created = existing = no_animal = no_milk = 0
    dried = []
    unmatched = []

    for nom, values in herd.items():
        if nom in ambiguous or nom not in animal_map:
            no_animal += 1
            unmatched.append(nom)
            continue
        animal = animal_map[nom]

        debut, fin = _window(dates, values)
        if not debut:
            no_milk += 1
            continue
        if frappe.db.exists("Lactation", {"animal": animal}):
            existing += 1
            continue

        tarie = (dates[-1] - fin).days > DRY_GAP_DAYS
        doc = {
            "doctype": "Lactation",
            "animal": animal,
            "date_debut": str(debut),
            "statut": "TARIE" if tarie else "EN_COURS",
            "observations": ORIGIN,
        }
        if tarie:
            doc["date_tarissement"] = str(fin)
            dried.append(nom)

        if not dry_run:
            d = frappe.get_doc(doc)
            d.flags.ignore_validate = True
            d.flags.ignore_mandatory = True
            d.insert(ignore_permissions=True)
        created += 1

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Lactations reconstituées depuis {filename}")
    print(f"  période du fichier : {dates[0]} → {dates[-1]} ({len(dates)} jours)")
    print(f"  créées={created} (dont taries={len(dried)}), déjà présentes={existing}")
    print(f"  vaches sans production={no_milk}, sans animal correspondant={no_animal} {unmatched[:10]}")
    return {"mode": mode, "created": created, "existing": existing,
            "no_animal": no_animal, "unmatched": unmatched}
