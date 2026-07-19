"""
FIN-S21 (RG-FIN-10/11/12, RG-FIN-04) — facture lait de la période.

Aggregates `Bilan Lait Journalier.lait_vendu` over a period into ONE Sales
Invoice for the milk buyer, priced from Item Price + primes/pénalités
qualité TB/TP (volume-weighted means over the same period).

Prix (RG-FIN-10 — aucun littéral) :
    taux = Item Price LAIT-CRU (fallback config `prix_reference_lait`)
         + (TB_moy − `lait_tb_reference`) × `lait_prime_tb_par_point`
         + (TP_moy − `lait_tp_reference`) × `lait_prime_tp_par_point`
    (TB/TP en % — même unité que le BLJ ; primes par point de %,
    négatives en dessous de la référence → pénalité)

Idempotence (RG-FIN-11, house pattern « marqueur remarks ») : the invoice
carries `LAIT_FACT_<debut>_<fin>` in remarks; a re-run finds it and no-ops.
Deleting/cancelling the invoice then re-running regenerates it.

Monthly wrapper `generate_monthly_milk_invoice` (scheduler) bills the
previous calendar month — safe to run daily, idempotent.

Run manually:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.utils.facturation_lait.generate_milk_invoice \\
        --kwargs "{'date_debut': '2026-07-01', 'date_fin': '2026-07-31'}"
"""
import frappe
from frappe.utils import add_days, get_first_day, get_last_day, getdate, today

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

ITEM_LAIT = "LAIT-CRU"
PRICE_LIST = "Standard Selling"
CUSTOMER_LAIT = "Centrale Laitière"
MARKER = "LAIT_FACT_{debut}_{fin}"


def _marker(date_debut, date_fin):
    return MARKER.format(debut=date_debut, fin=date_fin)


def existing_invoice(date_debut, date_fin):
    """Submitted-or-draft invoice already carrying this period's marker."""
    return frappe.db.get_value(
        "Sales Invoice",
        {"remarks": ["like", f"%{_marker(date_debut, date_fin)}%"],
         "docstatus": ["<", 2]},
        "name",
    )


def compute_milk_rate(tb_moyen=None, tp_moyen=None):
    """Prix du litre = base Item Price + primes qualité (RG-FIN-10).
    TB/TP None → base rate only (pas de données qualité, pas de prime)."""
    base = frappe.db.get_value(
        "Item Price", {"item_code": ITEM_LAIT, "price_list": PRICE_LIST},
        "price_list_rate",
    )
    rate = float(base if base is not None
                 else get_config("prix_reference_lait", default=1.6))
    if tb_moyen:
        tb_ref = float(get_config("lait_tb_reference", default=3.8))
        prime_tb = float(get_config("lait_prime_tb_par_point", default=0.0))
        rate += (float(tb_moyen) - tb_ref) * prime_tb
    if tp_moyen:
        tp_ref = float(get_config("lait_tp_reference", default=3.2))
        prime_tp = float(get_config("lait_prime_tp_par_point", default=0.0))
        rate += (float(tp_moyen) - tp_ref) * prime_tp
    return round(max(rate, 0), 3)


def _period_volumes(date_debut, date_fin):
    """(volume vendu, TB moyen pondéré, TP moyen pondéré) from BLJ rows."""
    row = frappe.db.sql("""
        SELECT COALESCE(SUM(lait_vendu), 0) AS volume,
               SUM(CASE WHEN taux_tb_moyen > 0 THEN lait_vendu ELSE 0 END) AS vol_tb,
               COALESCE(SUM(CASE WHEN taux_tb_moyen > 0
                                 THEN lait_vendu * taux_tb_moyen END), 0) AS somme_tb,
               SUM(CASE WHEN taux_tp_moyen > 0 THEN lait_vendu ELSE 0 END) AS vol_tp,
               COALESCE(SUM(CASE WHEN taux_tp_moyen > 0
                                 THEN lait_vendu * taux_tp_moyen END), 0) AS somme_tp
        FROM `tabBilan Lait Journalier`
        WHERE date BETWEEN %s AND %s
    """, (date_debut, date_fin), as_dict=True)[0]
    volume = float(row.volume or 0)
    tb = (row.somme_tb / row.vol_tb) if row.vol_tb else None
    tp = (row.somme_tp / row.vol_tp) if row.vol_tp else None
    return volume, tb, tp


@frappe.whitelist()
def generate_milk_invoice(date_debut, date_fin, customer=None, submit=True):
    """Create the period milk Sales Invoice. Idempotent (remarks marker).
    Returns the invoice name, or None (no volume / already billed)."""
    date_debut, date_fin = str(getdate(date_debut)), str(getdate(date_fin))

    existing = existing_invoice(date_debut, date_fin)
    if existing:
        print(f"  [skip]   Facture lait déjà émise pour {date_debut} → {date_fin} "
              f"({existing})")
        return existing

    volume, tb, tp = _period_volumes(date_debut, date_fin)
    if volume <= 0:
        print(f"  [skip]   Aucun lait vendu (BLJ) sur {date_debut} → {date_fin}")
        return None

    rate = compute_milk_rate(tb, tp)
    customer = customer or CUSTOMER_LAIT
    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "company": COMPANY,
        "customer": customer,
        "posting_date": date_fin if getdate(date_fin) <= getdate(today()) else today(),
        "set_posting_time": 1,
        "items": [{
            "item_code": ITEM_LAIT,
            "qty": volume,
            "rate": rate,
        }],
        "remarks": (f"{_marker(date_debut, date_fin)} — {volume:.0f} L"
                    + (f", TB {tb:.1f}" if tb else "")
                    + (f", TP {tp:.1f}" if tp else "")),
    })
    si.insert(ignore_permissions=True)
    if submit:
        si.submit()
    print(f"  [create] Facture lait {si.name} : {volume:.0f} L @ {rate} TND/L "
          f"= {si.grand_total} TND")
    return si.name


def generate_monthly_milk_invoice():
    """Scheduler job — facture le mois civil précédent. Idempotent, safe daily."""
    first_of_this_month = get_first_day(today())
    prev_last = add_days(first_of_this_month, -1)
    prev_first = get_first_day(prev_last)
    return generate_milk_invoice(str(prev_first), str(get_last_day(prev_last)))
