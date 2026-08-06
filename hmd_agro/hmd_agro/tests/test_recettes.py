"""
EPIC C — tests recettes (FIN-S20/S21/S22/S24).

Covers:
  1. compute_milk_rate: grille qualité en vigueur, repli prix plat sinon
  2. generate_milk_invoice: agrégation BLJ.lait_vendu (TB/TP pondérés),
     Sales Invoice émise, idempotence (marqueur remarks → re-run no-op).
     NON-RÉGRESSION MONO-ACHETEUR (FIN-S94) : sans ventilation par acheteur,
     un seul acheteur — `client_lait_defaut` — et une seule facture, comme
     avant. `generate_milk_invoice` rend désormais une LISTE de factures.
  3. Vente animal: statut → VENDU poste la facture depuis prix_vente ;
     retour à ACTIF l'annule (écriture compensatoire) ; sortie sans prix
     → pas de facture, pas de blocage (CF-FIN-21)

Pré-requis site : setup.finance.socle_comptable + setup.finance.recettes.

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_recettes.run
"""
import traceback

import frappe
from frappe.utils import today

from hmd_agro.hmd_agro.doctype.grille_prix_lait.grille_prix_lait import grille_active
from hmd_agro.hmd_agro.utils import facturation_lait, vente_animal

PREFIX = "TEST-REC-"
TN = "888000"
BLJ_DEBUT = "2031-01-01"
BLJ_FIN = "2031-01-31"
# Antérieure à toute grille de prix : force le repli « prix plat » (FIN-S24).
DATE_SANS_GRILLE = "2018-06-30"


def _cleanup():
    for si in frappe.get_all(
            "Sales Invoice",
            filters={"remarks": ["like", f"%LAIT_FACT_{BLJ_DEBUT}%"]},
            pluck="name"):
        _hard_delete_si(si)
    for si in frappe.get_all(
            "Sales Invoice",
            filters={"remarks": ["like", f"%ANIMAL_VENTE_{TN}%"]},
            pluck="name"):
        _hard_delete_si(si)
    # FIN-B1 : la facturation fige aussi un Decompte Lait Mensuel — hard
    # delete SQL (docstatus 1 ne s'efface pas par l'API).
    if frappe.db.table_exists("Decompte Lait Mensuel"):
        frappe.db.sql("""DELETE FROM `tabDecompte Lait Mensuel`
                         WHERE periode_debut BETWEEN %s AND %s""",
                      (BLJ_DEBUT, BLJ_FIN))
    frappe.db.sql("DELETE FROM `tabBilan Lait Journalier` WHERE date BETWEEN %s AND %s",
                  (BLJ_DEBUT, BLJ_FIN))
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE identification_tn LIKE %s", f"{TN}%")
    frappe.db.commit()


def _hard_delete_si(name):
    """Test-only teardown: strip GL/SLE then hard-delete the invoice."""
    frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", name)
    frappe.db.sql("DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no=%s", name)
    frappe.db.sql("DELETE FROM `tabSales Invoice Item` WHERE parent=%s", name)
    frappe.db.sql("DELETE FROM `tabSales Taxes and Charges` WHERE parent=%s", name)
    frappe.db.sql("DELETE FROM `tabSales Invoice` WHERE name=%s", name)


def _blj(date, lait_vendu, tb=None, tp=None):
    doc = frappe.get_doc({
        "doctype": "Bilan Lait Journalier",
        "date": date,
        "lait_vendu": lait_vendu,
        "taux_tb_moyen": tb,
        "taux_tp_moyen": tp,
    })
    doc.flags.ignore_validate = True
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc


def _animal(suffix):
    animal = frappe.new_doc("Animal")
    animal.update({
        "identification_tn": f"{TN}{suffix:04d}",
        "nom_metier": f"{PREFIX}{suffix}",
        "categorie": "VACHE", "sexe": "F",
        "statut": "ACTIF",
        "date_naissance": "2022-01-01",
    })
    animal.flags.ignore_validate = True
    animal.flags.ignore_mandatory = True
    animal.insert(ignore_permissions=True)
    return animal


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def run():
    print("\n" + "=" * 70)
    print("  EPIC C — Recettes (FIN-S20/S21/S22)")
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

    # ── 1. compute_milk_rate — base sans qualité = Item Price
    base = float(frappe.db.get_value(
        "Item Price",
        {"item_code": "LAIT-CRU", "price_list": "Standard Selling"},
        "price_list_rate"))
    rate0 = facturation_lait.compute_milk_rate()
    _check(abs(rate0 - base) < 0.001,
           f"Taux sans qualité = Item Price ({rate0} = {base})", results)
    # Repli prix plat (aucune grille en vigueur à cette date, FIN-S24) : les
    # primes config valent 0 par défaut, donc TB/TP ne bougent pas le prix.
    plat = facturation_lait.compute_milk_rate(tb_moyen=4.1, tp_moyen=3.0,
                                              date=DATE_SANS_GRILLE, detail=True)
    _check(plat["statut"] == "PRIX_PLAT" and abs(plat["prix"] - base) < 0.001,
           f"Sans grille, primes config à 0 → taux inchangé ({plat['prix']})", results)
    # Avec une grille en vigueur, la qualité fait bouger le prix — c'est tout
    # l'objet de FIN-S24.
    grille = grille_active(today())
    if grille:
        rate_q = facturation_lait.compute_milk_rate(tb_moyen=4.1, tp_moyen=3.0,
                                                    date=today())
        _check(abs(rate_q - base) > 0.001,
               f"Grille « {grille.name} » active → prix indexé sur TB/TP "
               f"({rate_q} vs {base})", results)
    else:
        _check(True, "Aucune grille active sur le site — indexation non testée",
               results)

    # ── 2. Facture lait période — 3 BLJ (un jour sans vente), TB/TP pondérés
    _blj(BLJ_DEBUT, 1000, tb=3.8, tp=3.2)
    _blj("2031-01-02", 500, tb=4.1, tp=3.2)
    _blj("2031-01-03", 0)
    frappe.db.commit()
    factures = facturation_lait.generate_milk_invoice(BLJ_DEBUT, BLJ_FIN)
    si_name = factures[0] if factures else None
    _check(len(factures) == 1,
           f"Sans ventilation → une seule facture, un seul acheteur ({si_name})",
           results)
    if si_name:
        si = frappe.get_doc("Sales Invoice", si_name)
        _check(si.docstatus == 1, "Facture lait soumise", results)
        _check(si.customer == facturation_lait.client_lait_defaut(),
               f"Acheteur = config client_lait_defaut ({si.customer})", results)
        _check(abs(si.items[0].qty - 1500.0) < 0.001,
               f"Volume agrégé = {si.items[0].qty} L (attendu 1500)", results)
        _check(abs(si.items[0].rate - facturation_lait.compute_milk_rate(3.9, 3.2)) < 0.001,
               f"Taux facturé {si.items[0].rate} = taux TB pondéré 3.9 %", results)
        income = frappe.db.get_value(
            "Sales Invoice Item", si.items[0].name, "income_account") or ""
        _check(income.startswith("701"),
               f"Produit imputé sur 701 (Ventes de lait) : {income}", results)
    # idempotence
    again = facturation_lait.generate_milk_invoice(BLJ_DEBUT, BLJ_FIN)
    _check(again == [si_name], "Re-run → même facture, pas de doublon (RG-FIN-11)",
           results)
    count = len(frappe.get_all("Sales Invoice",
                filters={"remarks": ["like", f"%LAIT_FACT_{BLJ_DEBUT}%"],
                         "docstatus": ["<", 2]}))
    _check(count == 1, f"Une seule facture active pour la période (count={count})",
           results)

    # ── 3. Vente animal
    a1 = _animal(10)
    a1.reload()
    a1.prix_vente = 3500
    a1.statut = "VENDU"
    a1.date_sortie = "2031-01-15"
    a1.flags.ignore_validate = True
    a1.save(ignore_permissions=True)
    frappe.db.commit()
    si_a = vente_animal.existing_invoice(a1.name)
    _check(bool(si_a), f"Statut VENDU → facture émise ({si_a})", results)
    if si_a:
        si = frappe.get_doc("Sales Invoice", si_a)
        _check(abs(si.grand_total - 3500.0) < 0.01,
               f"Total = prix_vente ({si.grand_total})", results)
        cc = frappe.db.get_value("Sales Invoice Item", si.items[0].name, "cost_center") or ""
        _check(cc.startswith("Lait"),
               f"VACHE → atelier Lait ({cc})", results)
    # retour ACTIF → annulation compensatoire
    a1.reload()
    a1.statut = "ACTIF"
    a1.flags.ignore_validate = True
    a1.save(ignore_permissions=True)
    frappe.db.commit()
    _check(vente_animal.existing_invoice(a1.name) is None,
           "Statut revert → facture annulée (CF-FIN-21)", results)
    if si_a:
        _check(frappe.db.get_value("Sales Invoice", si_a, "docstatus") == 2,
               "L'annulée reste en base (audit, docstatus=2)", results)

    # sortie sans prix → pas de facture, pas d'exception
    a2 = _animal(20)
    a2.reload()
    a2.statut = "REFORME"
    a2.date_sortie = "2031-01-16"
    a2.flags.ignore_validate = True
    a2.save(ignore_permissions=True)
    frappe.db.commit()
    _check(vente_animal.existing_invoice(a2.name) is None,
           "REFORME sans prix_vente → pas de facture, sortie enregistrée", results)

    _cleanup()

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
