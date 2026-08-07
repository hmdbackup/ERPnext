"""Import the real herd from the farm's Frappe data-export CSVs (Drive, 06/08/2026).

Source = the "Manual Export" folder produced from the production site: one CSV per
doctype, in Frappe's *data import template* layout (13 preamble rows, then
`Nom de la Colonne:` = the technical fieldnames, then the data).

Loads, in dependency order:
    Batiment -> Taureau -> Lot -> Animal (2 passes for the dam links) -> Aliment

Taureau and Lot are NOT in the export, so they are reconstructed from the values
the animals reference (sire names, lot names). Lot dimensions are estimates —
see LOT_DEFAULTS — because the real Lot rows were never exported; everything else
comes verbatim from the export.

CSV folder: `sites/<site>/private/farm_data_drive/` by default (override with
`source=`), same convention as data_source.py.

Idempotent / dry-run.
Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_export_reel.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import csv
import os
import re

import frappe

FOLDER = "farm_data_drive"
DATE_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")

# Lot dimensions are not in the export — sized from the herd actually housed there.
# superficie_m2, capacite_optimale, capacite_maximale, adapte_hautes_performances
LOT_DEFAULTS = {
    "LOT1":       (900, 30, 40, 1),
    "LOT2":       (900, 30, 40, 0),
    "LOT3":       (900, 30, 40, 0),
    "LOT4":       (600, 20, 28, 0),
    "TARIE":      (700, 25, 35, 0),
    "GENISSE":    (800, 35, 45, 0),
    "VELLE":      (900, 60, 75, 0),
    "INFIRMERIE": (200,  8, 12, 0),
    "Individuel": (600, 30, 40, 0),
}
LOT_FALLBACK = (600, 25, 35, 0)


# ─── CSV parsing ─────────────────────────────────────────────────────────────

def folder(source=None):
    return source or frappe.get_site_path("private", FOLDER)


def parse(source, filename):
    """Read a Frappe export template, return rows as {fieldname: value} dicts.

    Values are trimmed, the ID column's surrounding quotes removed, and
    dd-mm-yyyy dates normalised to yyyy-mm-dd.
    """
    path = os.path.join(folder(source), filename)
    with open(path, newline="", encoding="utf-8-sig") as f:
        raw = list(csv.reader(f))

    header = next((i for i, r in enumerate(raw) if r and r[0].strip() == "Nom de la Colonne:"), None)
    if header is None:
        frappe.throw(f"{filename}: ligne 'Nom de la Colonne:' introuvable")
    fields = [c.strip() for c in raw[header]]

    skip = {"Obligatoire :", "Type :", "Info :", "Nom de la Colonne:"}
    rows = []
    for r in raw[header + 1:]:
        if not r or r[0].strip() in skip:
            continue
        if len(r) < 2 or not r[1].strip():      # the "Commencez à entrer..." instruction row
            continue
        rows.append({k: _clean(v) for k, v in zip(fields, r) if k})
    return rows


def _clean(value):
    value = (value or "").strip().strip('"').strip()
    m = DATE_RE.match(value)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else value


def _insert(doc_dict):
    doc = frappe.get_doc(doc_dict)
    doc.flags.ignore_validate = True
    doc.flags.ignore_mandatory = True
    doc.flags.lot_change_source = "IMPORT"
    doc.insert(ignore_permissions=True)
    return doc


# ─── Steps ───────────────────────────────────────────────────────────────────

def _batiments(rows, dry_run, log):
    created = 0
    for r in rows:
        nom = r.get("nom_batiment")
        if not nom or frappe.db.exists("Batiment", nom):
            continue
        if not dry_run:
            _insert({
                "doctype": "Batiment",
                "nom_batiment": nom,
                "type_batiment": r.get("type_batiment") or "ELEVAGE",
                "actif": int(r.get("actif") or 1),
            })
        created += 1
    log.append(f"Batiment      : +{created}")


def _taureaux(animals, dry_run, log):
    """Sires are referenced by name on Animal but were never exported."""
    noms = sorted({a["id_pere"] for a in animals if a.get("id_pere")})
    created = 0
    for nom in noms:
        if frappe.db.exists("Taureau", nom):
            continue
        if not dry_run:
            _insert({
                "doctype": "Taureau", "nom_taureau": nom,
                "code_taureau": nom[:10].upper(), "race": "Montbéliarde",
            })
        created += 1
    log.append(f"Taureau       : +{created} (sur {len(noms)} référencés)")


def _lots(animals, dry_run, log):
    batiment = frappe.db.get_value("Batiment", {"actif": 1}, "name") if not dry_run else "?"
    noms = sorted({a["id_lot"] for a in animals if a.get("id_lot")})
    created, estimated = 0, []
    for nom in noms:
        if frappe.db.exists("Lot", nom):
            continue
        surf, opt, maxi, hp = LOT_DEFAULTS.get(nom, LOT_FALLBACK)
        if nom not in LOT_DEFAULTS:
            estimated.append(nom)
        if not dry_run:
            _insert({
                "doctype": "Lot", "nom": nom, "batiment": batiment, "actif": 1,
                "superficie_m2": surf, "capacite_optimale": opt,
                "capacite_maximale": maxi, "adapte_hautes_performances": hp,
            })
        created += 1
    log.append(f"Lot           : +{created} (dimensions estimées, absentes de l'export)")
    if estimated:
        log.append(f"  ! lots sans gabarit connu : {estimated}")


def _animals(animals, dry_run, log):
    created = skipped = 0
    errors, dams = [], {}

    for a in animals:
        tn = a.get("identification_tn")
        if not tn:
            continue
        if frappe.db.exists("Animal", tn):
            skipped += 1
            continue
        if a.get("id_mere"):
            dams[tn] = a["id_mere"]
        try:
            doc = {
                "doctype": "Animal",
                "identification_tn": tn,
                "identification_fr": a.get("identification_fr") or None,
                "nom_metier": a.get("nom_metier") or tn[-4:],
                "nom": a.get("nom") or None,
                "race": a.get("race") or "Montbéliarde",
                "categorie": a.get("categorie") or "VACHE",
                "sexe": a.get("sexe") or "F",
                "date_naissance": a.get("date_naissance"),
                "est_achat": int(a.get("est_achat") or 0),
                "date_entree": a.get("date_entree") or None,
                "prix_achat": a.get("prix_achat") or 0,
                "id_pere": a.get("id_pere") or None,
                "id_lot": a.get("id_lot") or None,
                "statut": a.get("statut") or "ACTIF",
                "date_sortie": a.get("date_sortie") or None,
                "prix_vente": a.get("prix_vente") or 0,
                "etat_lactation": a.get("etat_lactation") or None,
                "etat_gestation": a.get("etat_gestation") or None,
                "dernier_poids": a.get("dernier_poids") or None,
                "date_velage_prevue": a.get("date_velage_prevue") or None,
                "date_premier_velage": a.get("date_premier_velage") or None,
                "date_tarissement": a.get("date_tarissement") or None,
            }
            if not dry_run:
                _insert({k: v for k, v in doc.items() if v not in (None, "")})
            created += 1
        except Exception as e:
            errors.append((tn, str(e)[:120]))

    # dam links in a second pass: the dam must already exist
    applied = 0
    if not dry_run:
        for daughter, dam in dams.items():
            if frappe.db.exists("Animal", daughter) and frappe.db.exists("Animal", dam):
                frappe.db.set_value("Animal", daughter, "id_mere", dam, update_modified=False)
                applied += 1

    log.append(f"Animal        : +{created}, déjà présents {skipped}, erreurs {len(errors)}")
    log.append(f"  mères reliées : {applied}/{len(dams)}")
    for tn, err in errors[:5]:
        log.append(f"  ERR {tn}: {err}")


def _aliments(rows, dry_run, log):
    created = 0
    for r in rows:
        nom = r.get("nom_aliment")
        if not nom or frappe.db.exists("Aliment", nom):
            continue
        if not dry_run:
            _insert({
                "doctype": "Aliment",
                "nom_aliment": nom,
                "type_aliment": r.get("type_aliment") or "CONCENTRE",
                "unite": r.get("unite") or "KG",
                "prix_unitaire": r.get("prix_unitaire") or 0,
                "ms_pct": r.get("ms_pct") or 0,
                "observations": r.get("observations") or None,
            })
        created += 1
    log.append(f"Aliment       : +{created}")


# ─── Entry point ─────────────────────────────────────────────────────────────

def run(dry_run=True, source=None):
    dry_run = int(dry_run)
    log = []

    animals = parse(source, "Animal.csv")
    _batiments(parse(source, "Batiment.csv"), dry_run, log)
    _taureaux(animals, dry_run, log)
    _lots(animals, dry_run, log)
    _animals(animals, dry_run, log)
    _aliments(parse(source, "Aliment.csv"), dry_run, log)

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Import du troupeau réel (export Drive 06/08/2026) — {len(animals)} animaux dans le fichier")
    for line in log:
        print("  " + line)
    return {"mode": mode, "log": log}
