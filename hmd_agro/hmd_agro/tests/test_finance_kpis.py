"""
EPIC F — tests pilotage économique (FIN-S50/S51, RC-FIN-50/51/52).

Covers:
  1. gl_sums : CA lait (701), MO (64x), produits/charges, EBE, résultat
     agrégés du Grand Livre sur une période
  2. Coloration seuils : coût/L vert-orange-rouge (objectif_cout_litre),
     IOFC vert-orange-rouge (pfe_iofc_jour_min) via _kpi_ind
  3. Les seuils viennent de la config (patch v1_6 seedé)

Pré-requis site : socle + recettes + patch v1_6 (bench migrate).

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_finance_kpis.run
"""
import traceback

import frappe
from frappe.utils import get_first_day, get_last_day, getdate, today

from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import _kpi_ind
from hmd_agro.hmd_agro.utils import charges_utils, facturation_lait, finance_kpis
from hmd_agro.hmd_agro.utils.config import get_config

BLJ_DEBUT = "2032-01-01"
BLJ_FIN = "2032-01-31"


def _periode_mo():
    d = getdate(today())
    return f"{d.year}-{d.month:02d}"


def _cleanup():
    for si in frappe.get_all(
            "Sales Invoice",
            filters={"remarks": ["like", f"%LAIT_FACT_{BLJ_DEBUT}%"]},
            pluck="name"):
        frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", si)
        frappe.db.sql("DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no=%s", si)
        frappe.db.sql("DELETE FROM `tabSales Invoice Item` WHERE parent=%s", si)
        frappe.db.sql("DELETE FROM `tabSales Taxes and Charges` WHERE parent=%s", si)
        frappe.db.sql("DELETE FROM `tabSales Invoice` WHERE name=%s", si)
    je = charges_utils.existing_entry(_periode_mo())
    if je:
        frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", je)
        frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent=%s", je)
        frappe.db.sql("DELETE FROM `tabJournal Entry` WHERE name=%s", je)
    # FIN-B1 : la facturation fige aussi un Decompte Lait Mensuel — hard
    # delete SQL (docstatus 1 ne s'efface pas par l'API).
    if frappe.db.table_exists("Decompte Lait Mensuel"):
        frappe.db.sql("""DELETE FROM `tabDecompte Lait Mensuel`
                         WHERE periode_debut BETWEEN %s AND %s""",
                      (BLJ_DEBUT, BLJ_FIN))
    frappe.db.sql("DELETE FROM `tabBilan Lait Journalier` WHERE date BETWEEN %s AND %s",
                  (BLJ_DEBUT, BLJ_FIN))
    frappe.db.commit()


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def run():
    print("\n" + "=" * 70)
    print("  EPIC F — Pilotage économique (FIN-S50/S51)")
    print("=" * 70)
    try:
        return _run_inner()
    except Exception:
        print("\n  ❌ Test crashed mid-flight:")
        print(traceback.format_exc())
        return {"pass": 0, "fail": 1}


def _run_inner():
    results = {"pass": 0, "fail": 0}
    _cleanup()

    fenetre = (str(get_first_day(today())), str(get_last_day(today())))
    base = finance_kpis.gl_sums(*fenetre)

    # ── écritures de la période : facture lait (posting = today) + salaires
    frappe.get_doc({
        "doctype": "Bilan Lait Journalier", "date": BLJ_DEBUT,
        "lait_vendu": 1500,
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    si = facturation_lait.generate_milk_invoice(BLJ_DEBUT, BLJ_FIN)
    _check(bool(si), f"Facture lait postée ({si})", results)
    # Prix daté : depuis FIN-S24 le tarif dépend de la grille en vigueur à la
    # date facturée, pas de celle d'aujourd'hui.
    ca_attendu = 1500 * facturation_lait.compute_milk_rate(date=BLJ_FIN)

    je = charges_utils.post_salaires(_periode_mo(), {"Lait": 2000})
    _check(bool(je), f"Salaires postés ({je})", results)

    # ── 1. gl_sums
    s = finance_kpis.gl_sums(*fenetre)
    _check(abs((s["ca_lait"] - base["ca_lait"]) - ca_attendu) < 0.01,
           f"CA lait (701) = {s['ca_lait'] - base['ca_lait']:.2f} "
           f"(attendu {ca_attendu:.2f})", results)
    _check(abs((s["mo"] - base["mo"]) - 2000.0) < 0.01,
           f"MO (64x) = {s['mo'] - base['mo']:.2f} (attendu 2000)", results)
    _check(abs((s["produits"] - base["produits"]) - ca_attendu) < 0.01,
           "Produits = CA lait (seule recette de la période)", results)
    delta_ebe = (s["ebe"] - base["ebe"])
    _check(abs(delta_ebe - (ca_attendu - 2000.0)) < 0.01,
           f"EBE = produits − charges d'exploitation = {delta_ebe:.2f}", results)
    _check(abs((s["resultat"] - base["resultat"]) - (ca_attendu - 2000.0)) < 0.01,
           "Résultat = produits − toutes charges", results)

    # ── 2. Coloration seuils config (RG-FIN-60)
    vert_max = float(get_config("objectif_cout_litre", default=0.65))
    alarme = float(get_config("objectif_cout_litre_alarme", default=0.85))
    _check(vert_max == 0.65 and alarme == 0.85,
           f"Seuils coût/L seedés par v1_6 ({vert_max}/{alarme})", results)
    _check(_kpi_ind(0.60, green_max=vert_max, orange_max=alarme) == "Green",
           "Coût/L 0.60 → VERT", results)
    _check(_kpi_ind(0.75, green_max=vert_max, orange_max=alarme) == "Orange",
           "Coût/L 0.75 → ORANGE", results)
    _check(_kpi_ind(0.95, green_max=vert_max, orange_max=alarme) == "Red",
           "Coût/L 0.95 → ROUGE", results)
    iofc_min = float(get_config("pfe_iofc_jour_min", default=3.0))
    iofc_omn = float(get_config("pfe_iofc_jour_orange_min", default=1.5))
    _check(_kpi_ind(3.5, green_min=iofc_min, orange_min=iofc_omn) == "Green",
           "IOFC 3.5 DT/VL/j → VERT", results)
    _check(_kpi_ind(2.0, green_min=iofc_min, orange_min=iofc_omn) == "Orange",
           "IOFC 2.0 → ORANGE", results)
    _check(_kpi_ind(1.0, green_min=iofc_min, orange_min=iofc_omn) == "Red",
           "IOFC 1.0 → ROUGE", results)

    _cleanup()

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
