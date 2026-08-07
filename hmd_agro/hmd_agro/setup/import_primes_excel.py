"""Import the farm's Aïd bonus sheet into Prime Personnel.

Source — `HMD LISTE DES PERSONNELS Eid 2026.xlsx`, one sheet per atelier
(ELVAGE, GC). Header row carries « NOM ET PRENOM » and the money columns;
the last row is a TOTAL and is skipped.

WHAT COUNTS AS A PRIME — only the columns in `PRIME_COLUMNS`:
  « Prime » and « Prime ensilage ».
« Tenue » (a uniform allowance paid to everyone) and « Pret » (a salary
advance, to be repaid) are NOT bonuses and are deliberately left out; a prime
feeds account 640 and the CNSS base, an advance does not. Their totals are
printed so the discrepancy with the sheet's TOTAL column is explainable.

MISSING EMPLOYEES — the sheet has names and amounts, nothing else. With
`create_missing`, a skeleton Personnel is created carrying ONLY what the file
actually says (name, atelier) plus explicit placeholders: salaire 0, rôle
AUTRE, embauche = `date_reference`. They are marked in `notes` so nobody
mistakes them for complete records. Salaire 0 is a truthful "unknown" — do not
replace it with a plausible-looking figure.

`periode` (AAAA-MM) is REQUIRED and has no default: the workbook is named
"Eid 2026" without a month, and Prime Personnel refuses a bonus on a month
whose salaries are already posted (ERR-PRIME-04). Guessing it here would put
the bonus on the wrong payroll month.

Idempotent (Prime Personnel refuses a duplicate personnel+période+motif) / dry-run.
Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_primes_excel.run \
       --kwargs '{"dry_run": 1, "periode": "2026-05"}'
"""
import os

import frappe
import openpyxl
from frappe.utils import flt

FOLDER = "farm_data_drive"
DEFAULT_FILE = "Primes.xlsx"

NAME_HEADER = "NOM ET PRENOM"
PRIME_COLUMNS = ("prime", "prime ensilage")
INFO_COLUMNS = ("tenue", "pret", "pret(optionel)")

# Sheet name -> Cost Center. ELVAGE covers the dairy staff, GC the field crops.
ATELIER = {
    "ELVAGE": "Lait - HMD",
    "GC": "Cultures - Fourrage - HMD",
}
DEFAULT_ATELIER = "Frais Généraux - HMD"
SKELETON_NOTE = ("Fiche créée depuis la liste des primes Aïd — salaire, rôle, "
                 "date d'embauche et atelier restent à compléter.")


def _path(source, filename):
    return os.path.join(source or frappe.get_site_path("private", FOLDER), filename)


def _norm(value):
    return str(value or "").strip().lower()


def read_sheet(ws):
    """Return (rows, extras) — one dict per employee, plus the ignored columns."""
    rows = list(ws.iter_rows(values_only=True))
    header_idx = next((i for i, r in enumerate(rows)
                       if any(_norm(c) == _norm(NAME_HEADER) for c in r)), None)
    if header_idx is None:
        return [], {}
    header = [_norm(c) for c in rows[header_idx]]
    name_col = header.index(_norm(NAME_HEADER))
    prime_cols = [i for i, h in enumerate(header) if h in PRIME_COLUMNS]
    info_cols = {header[i]: i for i, h in enumerate(header) if h in INFO_COLUMNS}

    people, extras = [], {k: 0.0 for k in info_cols}
    for r in rows[header_idx + 1:]:
        if len(r) <= name_col:
            continue
        nom = str(r[name_col] or "").strip()
        if not nom or nom.upper() == "TOTAL":
            continue
        montant = sum(flt(r[i]) for i in prime_cols if i < len(r) and isinstance(r[i], (int, float)))
        for label, i in info_cols.items():
            if i < len(r) and isinstance(r[i], (int, float)):
                extras[label] += flt(r[i])
        people.append({"nom": nom, "montant": round(montant, 3)})
    return people, extras


def _find_personnel(nom):
    """Match on nom_complet, case- and space-insensitive."""
    match = frappe.db.sql("""
        SELECT name FROM `tabPersonnel`
        WHERE LOWER(TRIM(nom_complet)) = %s
    """, (" ".join(nom.lower().split()),))
    return match[0][0] if match else None


def run(dry_run=True, periode=None, source=None, filename=DEFAULT_FILE,
        motif="Prime Aïd", create_missing=True, date_reference="2026-01-01"):
    dry_run, create_missing = int(dry_run), int(create_missing)
    if not periode:
        frappe.throw("`periode` est obligatoire (format AAAA-MM) — voir l'en-tête du module.")

    wb = openpyxl.load_workbook(_path(source, filename), read_only=True, data_only=True)
    created_pers, created_prime, skipped, errors = [], 0, 0, []
    total_prime, extras_all = 0.0, {}

    for sheet in wb.sheetnames:
        people, extras = read_sheet(wb[sheet])
        for label, montant in extras.items():
            extras_all[label] = extras_all.get(label, 0) + montant
        atelier = ATELIER.get(sheet.strip().upper(), DEFAULT_ATELIER)

        for p in people:
            if p["montant"] <= 0:          # ERR-PRIME-01 refuses 0 anyway
                skipped += 1
                continue
            personnel = _find_personnel(p["nom"])
            if not personnel:
                if not create_missing:
                    skipped += 1
                    errors.append((p["nom"], "aucune fiche Personnel"))
                    continue
                created_pers.append(f"{p['nom']} ({sheet})")
                if not dry_run:
                    doc = frappe.get_doc({
                        "doctype": "Personnel",
                        "nom_complet": p["nom"],
                        "role_personnel": "AUTRE",
                        "date_embauche": date_reference,
                        "statut": "ACTIF",
                        "salaire_brut_mensuel": 0,
                        "atelier": atelier,
                        "notes": SKELETON_NOTE,
                    })
                    doc.flags.ignore_mandatory = True
                    doc.insert(ignore_permissions=True)
                    personnel = doc.name

            total_prime += p["montant"]
            if dry_run:
                created_prime += 1
                continue
            try:
                frappe.get_doc({
                    "doctype": "Prime Personnel",
                    "personnel": personnel,
                    "periode": periode,
                    "montant": p["montant"],
                    "motif": motif,
                    "date_attribution": date_reference,
                }).insert(ignore_permissions=True)
                created_prime += 1
            except Exception as e:
                errors.append((p["nom"], str(e)[:120]))

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Primes « {motif} » sur la période {periode} — {filename}")
    print(f"  primes créées   : {created_prime} pour {round(total_prime, 2)} DT")
    print(f"  fiches Personnel créées (squelettes) : {len(created_pers)}")
    print(f"  lignes ignorées : {skipped}, erreurs : {len(errors)}")
    print("  colonnes NON importées (hors prime) : "
          + ", ".join(f"{k} = {round(v, 2)} DT" for k, v in sorted(extras_all.items())))
    for nom, err in errors[:8]:
        print(f"  ERR {nom}: {err}")
    return {"mode": mode, "primes": created_prime, "total": round(total_prime, 2),
            "personnel_crees": created_pers, "errors": errors}
