"""Import the farm's daily milk workbook (`Lait 2026.xlsx`) into Bilan Lait Journalier.

One sheet per month, one row per day. Column layout (header row 1):

    B DATE | C V L | D LAIT VEAUX | E LAIT VENDU | F C INTERNE | G TOTAL
    H MOY  | I CC  | J L/CC       | K..  one column per buyer

Everything left of the buyer columns is fixed; the buyer columns are whatever
names sit in the header from `BUYER_START_COL` onwards, so adding a third
customer to the workbook needs no code change here.

`lait_vendu` is NOT written: Bilan Lait Journalier recomputes it as the sum of
the ventilation table (FIN-S94), and `ecart_litres` is derived in validate() —
so the doc is saved WITH validation, never with ignore_validate.

The daily concentré (column CC) lands in `concentre_kg`, which the periodic
report prefers over the ration-derived reconstruction when it is filled.

Missing customers are created (a milk buyer is a plain Customer).

Idempotent (skips a date already imported unless `overwrite`) / dry-run.
Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_bilan_lait_excel.run --kwargs '{"dry_run": 1}'
"""
import datetime
import os

import frappe
import openpyxl
from frappe.utils import flt, getdate

FOLDER = "farm_data_drive"
DEFAULT_FILE = "Lait.xlsx"

COL_DATE, COL_VEAU, COL_VENDU, COL_INTERNE, COL_TOTAL, COL_CC = 1, 3, 4, 5, 6, 8
BUYER_START_COL = 10
CUSTOMER_GROUP = "Commercial"


def _path(source, filename):
    return os.path.join(source or frappe.get_site_path("private", FOLDER), filename)


def _num(value):
    return flt(value) if isinstance(value, (int, float)) else 0.0


def read_rows(source=None, filename=DEFAULT_FILE):
    """Yield one dict per dated row across every monthly sheet."""
    wb = openpyxl.load_workbook(_path(source, filename), read_only=True, data_only=True)
    for sheet in wb.sheetnames:
        rows = list(wb[sheet].iter_rows(values_only=True))
        if not rows:
            continue
        header = rows[0]
        buyers = [(i, str(header[i]).strip())
                  for i in range(BUYER_START_COL, len(header))
                  if header[i] and str(header[i]).strip()]
        for row in rows[1:]:
            if len(row) <= COL_TOTAL:
                continue
            date = row[COL_DATE]
            if not isinstance(date, (datetime.datetime, datetime.date)):
                continue
            yield {
                "sheet": sheet,
                "date": getdate(date),
                "lait_veau": _num(row[COL_VEAU]),
                "lait_vendu": _num(row[COL_VENDU]),
                "consommation_interne": _num(row[COL_INTERNE]),
                "production_totale_saisie": _num(row[COL_TOTAL]),
                "concentre_kg": _num(row[COL_CC]) if len(row) > COL_CC else 0.0,
                "ventes": [(nom, _num(row[i])) for i, nom in buyers
                           if i < len(row) and _num(row[i]) > 0],
            }


def _ensure_customer(nom, dry_run, created):
    if frappe.db.exists("Customer", nom):
        return nom
    if not dry_run:
        doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": nom,
            "customer_group": (CUSTOMER_GROUP
                               if frappe.db.exists("Customer Group", CUSTOMER_GROUP)
                               else frappe.db.get_value("Customer Group", {"is_group": 0}, "name")),
            "customer_type": "Company",
        })
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
    created.add(nom)
    return nom


def run(dry_run=True, source=None, filename=DEFAULT_FILE, overwrite=False):
    dry_run, overwrite = int(dry_run), int(overwrite)
    created = updated = skipped = 0
    new_customers, mismatches, errors = set(), [], []
    dates = []

    for r in read_rows(source, filename):
        name = f"BLJ-{r['date']}"
        exists = frappe.db.exists("Bilan Lait Journalier", name)
        if exists and not overwrite:
            skipped += 1
            continue

        # The workbook carries both a LAIT VENDU total and a per-buyer split;
        # the doctype trusts the split. Flag any day where they disagree.
        split = round(sum(litres for _, litres in r["ventes"]), 1)
        if r["ventes"] and abs(split - r["lait_vendu"]) > 1:
            mismatches.append((str(r["date"]), r["lait_vendu"], split))

        try:
            doc = frappe.get_doc("Bilan Lait Journalier", name) if exists else frappe.new_doc(
                "Bilan Lait Journalier")
            doc.date = str(r["date"])
            doc.lait_veau = r["lait_veau"]
            doc.consommation_interne = r["consommation_interne"]
            doc.production_totale_saisie = r["production_totale_saisie"]
            doc.concentre_kg = r["concentre_kg"]
            doc.set("ventes", [])
            for nom, litres in r["ventes"]:
                doc.append("ventes", {
                    "acheteur": _ensure_customer(nom, dry_run, new_customers),
                    "litres": litres,
                })
            if not r["ventes"]:
                doc.lait_vendu = r["lait_vendu"]
            if not dry_run:
                doc.save(ignore_permissions=True)
            dates.append(r["date"])
            if exists:
                updated += 1
            else:
                created += 1
        except Exception as e:
            errors.append((str(r["date"]), str(e)[:140]))

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Bilans lait journaliers depuis {filename}")
    if dates:
        print(f"  période : {min(dates)} → {max(dates)}")
    print(f"  créés={created}, mis à jour={updated}, ignorés (déjà présents)={skipped}, erreurs={len(errors)}")
    print(f"  acheteurs créés : {sorted(new_customers) or 'aucun'}")
    if mismatches:
        print(f"  ! {len(mismatches)} jours où « LAIT VENDU » ≠ somme par acheteur "
              f"(la ventilation fait foi) : {mismatches[:5]}")
    for d, err in errors[:5]:
        print(f"  ERR {d}: {err}")
    return {"mode": mode, "created": created, "updated": updated,
            "skipped": skipped, "mismatches": len(mismatches), "errors": errors}
