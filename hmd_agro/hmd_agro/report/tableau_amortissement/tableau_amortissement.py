"""
TASK B3 (EPIC D, FIN-S30/S31) — Tableau d'amortissement consolidé.

ERPNext v15 removed its native depreciation ledgers ("Asset Depreciation
Ledger" / "Asset Depreciations and Balances"); the only survivor is the
"Fixed Asset Register" — English labels, no durée en mois, no mois amortis,
no clean date de sortie. This thin Script Report replaces the removed
ledgers in French: one line per immobilisation (équipements ET cheptel),
with the durée totale, les mois déjà amortis, le cumul et le reste à
amortir. Sold/Scrapped assets stay visible (M. Samir wants la date de
sortie) unless the `inclure_sortis` filter is unchecked.

Reading rules:
  • Durée (mois)  = total_number_of_depreciations × frequency_of_depreciation
                    (first Asset Finance Book row — multi-book guard).
  • Mois amortis  = (opening_number_of_booked_depreciations
                     + dotations réellement postées) × fréquence.
    In v15 the schedule lives in the submittable "Asset Depreciation
    Schedule" doctype; a row is "postée" when journal_entry is set.
  • Amortissement cumulé = valeur brute − reste à amortir
    (reste = value_after_depreciation, Finance Book first row).

Read-only — writes nothing, safe to rerun at will.

Utilisation :
  • Desk → Rapport « Tableau Amortissement »
  • Console :
        bench --site hmd.agro execute \\
            hmd_agro.hmd_agro.report.tableau_amortissement.\\
tableau_amortissement.run
"""
import frappe
from frappe.utils import cint, flt

from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

# ERPNext Asset.status → vocabulaire maison (UPPER_SNAKE français).
STATUTS_FR = {
    "Draft": "BROUILLON",
    "Submitted": "EN_SERVICE",
    "Partially Depreciated": "EN_AMORTISSEMENT",
    "Fully Depreciated": "AMORTI",
    "Sold": "VENDU",
    "Scrapped": "REBUT",
    "Capitalized": "CAPITALISE",
    "Decapitalized": "DECAPITALISE",
    "Cancelled": "ANNULE",
}


def execute(filters=None):
    filters = filters or {}
    return _columns(), _data(filters)


def _columns():
    return [
        {"fieldname": "actif", "label": "ID Actif", "fieldtype": "Link",
         "options": "Asset", "width": 170},
        {"fieldname": "designation", "label": "Désignation", "fieldtype": "Data",
         "width": 180},
        {"fieldname": "categorie", "label": "Catégorie", "fieldtype": "Link",
         "options": "Asset Category", "width": 160},
        {"fieldname": "animal", "label": "Animal", "fieldtype": "Link",
         "options": "Animal", "width": 130},
        {"fieldname": "valeur_initiale", "label": "Valeur initiale",
         "fieldtype": "Currency", "width": 130},
        {"fieldname": "date_acquisition", "label": "Date acquisition",
         "fieldtype": "Date", "width": 110},
        {"fieldname": "date_entree", "label": "Date entrée",
         "fieldtype": "Date", "width": 110},
        {"fieldname": "date_sortie", "label": "Date sortie",
         "fieldtype": "Date", "width": 110},
        {"fieldname": "duree_mois", "label": "Durée (mois)", "fieldtype": "Int",
         "width": 100, "disable_total": True},
        {"fieldname": "mois_amortis", "label": "Mois amortis", "fieldtype": "Int",
         "width": 100, "disable_total": True},
        {"fieldname": "amortissement_cumule", "label": "Amortissement cumulé",
         "fieldtype": "Currency", "width": 160},
        {"fieldname": "reste_a_amortir", "label": "Reste à amortir",
         "fieldtype": "Currency", "width": 140},
        {"fieldname": "statut", "label": "Statut", "fieldtype": "Data",
         "width": 130},
    ]


def _data(filters):
    asset_filters = {"docstatus": 1, "company": COMPANY}
    if filters.get("asset_category"):
        asset_filters["asset_category"] = filters["asset_category"]
    # Default = 1: Samir wants the sorties (date de sortie) on the tableau.
    inclure_sortis = filters.get("inclure_sortis")
    if inclure_sortis is None:
        inclure_sortis = 1
    if not cint(inclure_sortis):
        asset_filters["status"] = ["not in", ["Sold", "Scrapped"]]

    assets = frappe.get_all(
        "Asset",
        filters=asset_filters,
        fields=["name", "asset_name", "asset_category", "id_animal",
                "gross_purchase_amount", "purchase_date",
                "available_for_use_date", "disposal_date", "status",
                "value_after_depreciation",
                "opening_number_of_booked_depreciations"],
        order_by="asset_category asc, name asc",
    )
    if not assets:
        return []

    names = [a.name for a in assets]
    finance_books = _first_finance_books(names)
    dotations_postees = _booked_depreciations(names, finance_books)

    data = []
    for a in assets:
        fb = finance_books.get(a.name)
        frequence = cint(fb.frequency_of_depreciation) if fb else 0
        duree_mois = cint(fb.total_number_of_depreciations) * frequence if fb else 0
        mois_amortis = (cint(a.opening_number_of_booked_depreciations)
                        + dotations_postees.get(a.name, 0)) * frequence
        if fb and fb.value_after_depreciation is not None:
            reste = flt(fb.value_after_depreciation)
        elif a.value_after_depreciation is not None:
            reste = flt(a.value_after_depreciation)
        else:
            # No depreciation plan at all: nothing amortized yet.
            reste = flt(a.gross_purchase_amount)
        data.append({
            "actif": a.name,
            "designation": a.asset_name,
            "categorie": a.asset_category,
            "animal": a.id_animal,
            "valeur_initiale": flt(a.gross_purchase_amount),
            "date_acquisition": a.purchase_date,
            "date_entree": a.available_for_use_date,
            "date_sortie": a.disposal_date,          # vide si l'actif est actif
            "duree_mois": duree_mois,
            "mois_amortis": mois_amortis,
            "amortissement_cumule": flt(a.gross_purchase_amount) - reste,
            "reste_a_amortir": reste,
            "statut": STATUTS_FR.get(a.status, a.status),
        })
    return data


def _first_finance_books(asset_names):
    """First Asset Finance Book row per asset (idx order).

    An asset can carry several finance books; the tableau reads the first
    one only — same book ERPNext uses when none is specified. `parenttype`
    is filtered because Asset Category shares this child doctype.
    """
    rows = frappe.get_all(
        "Asset Finance Book",
        filters={"parent": ["in", asset_names], "parenttype": "Asset"},
        fields=["parent", "idx", "finance_book",
                "total_number_of_depreciations",
                "frequency_of_depreciation", "value_after_depreciation"],
        order_by="parent asc, idx asc",
    )
    first = {}
    for row in rows:
        first.setdefault(row.parent, row)
    return first


def _booked_depreciations(asset_names, finance_books):
    """{asset: nb de dotations réellement postées} — v15: a Depreciation
    Schedule row is booked when its journal_entry is set. One schedule per
    finance book: the schedule is matched on the finance_book of the chosen
    Asset Finance Book row (NULL/empty finance_book on either side counts as
    a match), so the dotations counted always belong to the same book as the
    durée read by `_first_finance_books`."""
    schedules = frappe.get_all(
        "Asset Depreciation Schedule",
        filters={"asset": ["in", asset_names], "docstatus": 1},
        fields=["name", "asset", "finance_book"],
        order_by="asset asc, creation asc",
    )
    schedule_of = {}
    for s in schedules:
        fb = finance_books.get(s.asset)
        wanted_book = (fb.finance_book or "") if fb else ""
        if (s.finance_book or "") != wanted_book:
            continue
        schedule_of.setdefault(s.asset, s.name)
    if not schedule_of:
        return {}

    counts = frappe.db.sql("""
        SELECT parent, COUNT(*) AS n
        FROM `tabDepreciation Schedule`
        WHERE parent IN %(parents)s AND IFNULL(journal_entry, '') != ''
        GROUP BY parent
    """, {"parents": list(schedule_of.values())}, as_dict=True)
    by_schedule = {c.parent: cint(c.n) for c in counts}
    return {asset: by_schedule.get(sched, 0)
            for asset, sched in schedule_of.items()}


# ─── Console ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def run(asset_category=None, inclure_sortis=1):
    """Console run — prints the tableau, returns the row count."""
    _, data = execute({"asset_category": asset_category,
                       "inclure_sortis": inclure_sortis})
    largeur = 132
    print("\n" + "=" * largeur)
    print("  TABLEAU D'AMORTISSEMENT CONSOLIDÉ")
    print("=" * largeur)
    for ligne in data:
        print(f"  {ligne['actif']:<22} │ {str(ligne['designation'])[:24]:<24} │ "
              f"{ligne['mois_amortis']:>3}/{ligne['duree_mois']:>3} mois │ "
              f"{ligne['amortissement_cumule']:>12.2f} amorti │ "
              f"{ligne['reste_a_amortir']:>12.2f} restant │ "
              f"{ligne['statut']}")
    print("=" * largeur)
    print(f"  {len(data)} immobilisation(s)")
    print("=" * largeur + "\n")
    return {"lignes": len(data)}
