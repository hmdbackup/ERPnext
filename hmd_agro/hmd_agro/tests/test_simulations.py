"""
Point 14 du compte-rendu du 05/08/2026 — tests du scénario de SIMULATIONS
(setup.finance.simulations).

Couvre :
  1. `setup_simulations` pose les 5 documents attendus (achat aliment, achat
     de service, achat de médicament, traitement, vente taxable)
  2. La TVA tombe sur le BON compte SCE et au BON taux : 4366 « TVA
     déductible » à 19 % (aliment, service) et 7 % (médicament) côté achats,
     4367 « TVA collectée » à 19 % côté vente — vérifié sur le document ET
     au Grand Livre
  3. L'achat d'aliment est bien réceptionné en stock (Bin) et bouge le CMP
  4. L'utilisation de médicaments décrémente le stock du nombre de flacons
     consommés ET poste la charge au Grand Livre pour la valeur au CMP ;
     le délai d'attente lait est posé sur l'animal
  5. Idempotence : deux exécutions = les mêmes documents, aucun doublon
  6. `apercu_tva` recolle avec les documents (collectée − déductible)

Pré-requis site : socle comptable + recettes + seed_demo_finance
(troupeau, aliments et médicaments de démonstration).

ATTENTION — ce test nettoie derrière lui : il annule/supprime les documents
SIMU_*. Il tente de reposer le scénario en fin de parcours ; si la
restauration échoue, relancer à la main
`setup.finance.simulations.setup_simulations` AVANT la revue client.

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_simulations.run
"""
import traceback

import frappe
from frappe.utils import flt, get_first_day, today

from hmd_agro.hmd_agro.setup.finance import simulations
from hmd_agro.hmd_agro.setup.finance.simulations import (
    ACHAT_ALIMENT,
    ACHAT_MEDICAMENT,
    ACHAT_SERVICE,
    MARQUEUR,
    TRAITEMENT,
    VENTE_FUMIER,
    apercu_tva,
    setup_simulations,
)
from hmd_agro.hmd_agro.utils.stock_utils import (
    DEFAULT_COMPANY as COMPANY,
    DEFAULT_WAREHOUSE as WAREHOUSE,
)

MARQUEURS_ACHAT = [f"{MARQUEUR}_ACHAT_ALIMENT", f"{MARQUEUR}_ACHAT_SERVICE",
                   f"{MARQUEUR}_ACHAT_MEDICAMENT"]
MARQUEURS_VENTE = [f"{MARQUEUR}_VENTE_TVA"]
MARQUEUR_TRAITEMENT = f"{MARQUEUR}_TRAITEMENT"

# Montants attendus — recalculés depuis les constantes du module, jamais
# recopiés : si le scénario change, le test suit sans être réécrit.
HT_ALIMENT = ACHAT_ALIMENT["quantite"] * ACHAT_ALIMENT["prix"]
HT_SERVICE = ACHAT_SERVICE["quantite"] * ACHAT_SERVICE["prix"]
HT_MEDICAMENT = ACHAT_MEDICAMENT["quantite"] * ACHAT_MEDICAMENT["prix"]
HT_FUMIER = VENTE_FUMIER["quantite"] * VENTE_FUMIER["prix"]


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _bin_qty(item_code):
    return float(frappe.db.get_value(
        "Bin", {"item_code": item_code, "warehouse": WAREHOUSE},
        "actual_qty") or 0)


def _cmp(item_code):
    return float(frappe.db.get_value(
        "Bin", {"item_code": item_code, "warehouse": WAREHOUSE},
        "valuation_rate") or 0)


def _gl_par_compte(voucher_type, voucher_no):
    """{account_number: (debit, credit)} d'une pièce, lu au Grand Livre."""
    rows = frappe.db.sql("""
        SELECT acc.account_number AS num,
               SUM(gle.debit) AS debit, SUM(gle.credit) AS credit
        FROM `tabGL Entry` gle
        JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.voucher_type = %s AND gle.voucher_no = %s
          AND gle.is_cancelled = 0
        GROUP BY acc.account_number
    """, (voucher_type, voucher_no), as_dict=True)
    return {r.num: (flt(r.debit), flt(r.credit)) for r in rows}


def _gl_traitement(traitement):
    """{account_number: (debit, credit)} des sorties de stock d'un Traitement."""
    rows = frappe.db.sql("""
        SELECT acc.account_number AS num,
               SUM(gle.debit) AS debit, SUM(gle.credit) AS credit
        FROM `tabGL Entry` gle
        JOIN `tabAccount` acc ON acc.name = gle.account
        JOIN `tabStock Entry` se ON se.name = gle.voucher_no
             AND gle.voucher_type = 'Stock Entry'
        WHERE gle.is_cancelled = 0 AND gle.company = %s AND se.remarks = %s
        GROUP BY acc.account_number
    """, (COMPANY, f"Traitement {traitement}"), as_dict=True)
    return {r.num: (flt(r.debit), flt(r.credit)) for r in rows}


def _compte_taxe(doc):
    """Numéro de compte SCE de la première ligne de taxe du document."""
    if not doc.taxes:
        return None
    return frappe.db.get_value("Account", doc.taxes[0].account_head,
                               "account_number")


def _cleanup():
    """Retire les documents de simulation.

    Ordre imposé par le stock : le Traitement d'abord (sa suppression reposte
    les flacons consommés via on_trash), les factures ensuite — sinon
    l'annulation de la réception laisserait un stock négatif de flacons déjà
    sortis. Les factures sont ANNULÉES (docstatus 2) et non effacées : ERPNext
    contrepasse alors proprement stock et Grand Livre, et les marqueurs
    (`docstatus < 2`) cessent de matcher, donc une re-simulation repart à zéro.
    """
    for nom in frappe.get_all(
            "Traitement",
            filters={"observations": ["like", f"%{MARQUEUR_TRAITEMENT}%"]},
            pluck="name"):
        frappe.delete_doc("Traitement", nom, force=True,
                          ignore_permissions=True, delete_permanently=True)
    for doctype, marqueurs in (("Purchase Invoice", MARQUEURS_ACHAT),
                               ("Sales Invoice", MARQUEURS_VENTE)):
        for marqueur in marqueurs:
            for nom in frappe.get_all(
                    doctype,
                    filters={"remarks": ["like", f"%{marqueur}%"],
                             "docstatus": 1},
                    pluck="name"):
                doc = frappe.get_doc(doctype, nom)
                doc.flags.ignore_permissions = True
                doc.cancel()
            for nom in frappe.get_all(
                    doctype,
                    filters={"remarks": ["like", f"%{marqueur}%"],
                             "docstatus": 0},
                    pluck="name"):
                frappe.delete_doc(doctype, nom, force=True,
                                  ignore_permissions=True)
    frappe.db.commit()


def _restaurer_demo():
    """Le site de démo doit rester démontrable : on repose le scénario après
    le ménage. Jamais bloquant — un échec ici ne doit pas masquer un échec de
    test, il doit juste être visible à l'écran."""
    try:
        setup_simulations()
        print("\n  ↻ Scénario de simulation reposé sur le site.")
    except Exception as exc:
        print(f"\n  ⚠ Restauration du scénario impossible ({exc}) — relancer "
              f"setup.finance.simulations.setup_simulations avant la revue.")


def run():
    print("\n" + "=" * 70)
    print("  SIMULATIONS — facture fournisseur, médicaments, TVA (point 14)")
    print("=" * 70)
    try:
        return _run_inner()
    except Exception:
        print("\n  ❌ Test crashed mid-flight:")
        print(traceback.format_exc())
        return {"pass": 0, "fail": 1}
    finally:
        _cleanup()
        _restaurer_demo()


def _run_inner():
    results = {"pass": 0, "fail": 0}
    _cleanup()

    item_aliment = frappe.db.get_value("Aliment", ACHAT_ALIMENT["aliment"], "item")
    item_medicament = frappe.db.get_value(
        "Medicament", ACHAT_MEDICAMENT["medicament"], "item")
    qty_aliment_avant = _bin_qty(item_aliment)
    cmp_aliment_avant = _cmp(item_aliment)
    qty_med_avant = _bin_qty(item_medicament)

    # ── 1. Le scénario se pose intégralement
    r1 = setup_simulations()
    for cle in ("facture_aliment", "facture_service", "facture_medicament",
                "traitement", "vente_taxable"):
        _check(bool(r1.get(cle)), f"{cle} créé ({r1.get(cle)})", results)

    pi_aliment = frappe.get_doc("Purchase Invoice", r1["facture_aliment"])
    pi_service = frappe.get_doc("Purchase Invoice", r1["facture_service"])
    pi_medicament = frappe.get_doc("Purchase Invoice", r1["facture_medicament"])
    si_fumier = frappe.get_doc("Sales Invoice", r1["vente_taxable"])

    _check(all(d.docstatus == 1 for d in
               (pi_aliment, pi_service, pi_medicament, si_fumier)),
           "Les 4 factures sont soumises (docstatus 1)", results)

    # ── 2. TVA : bon compte, bon taux, bon montant — sur le document
    _check(abs(flt(pi_aliment.net_total) - HT_ALIMENT) < 0.01,
           f"Aliment : HT {pi_aliment.net_total} = {HT_ALIMENT}", results)
    _check(_compte_taxe(pi_aliment) == simulations.COMPTE_TVA_DEDUCTIBLE
           and abs(flt(pi_aliment.taxes[0].rate) - 19.0) < 0.001,
           f"Aliment : TVA 19 % sur le compte "
           f"{_compte_taxe(pi_aliment)} (attendu 4366)", results)
    _check(abs(flt(pi_aliment.total_taxes_and_charges) - HT_ALIMENT * 0.19) < 0.01,
           f"Aliment : TVA {pi_aliment.total_taxes_and_charges} = "
           f"{HT_ALIMENT * 0.19:.3f}", results)
    _check(abs(flt(pi_aliment.grand_total) - HT_ALIMENT * 1.19) < 0.01,
           f"Aliment : TTC {pi_aliment.grand_total} = {HT_ALIMENT * 1.19:.3f}",
           results)

    _check(_compte_taxe(pi_medicament) == simulations.COMPTE_TVA_DEDUCTIBLE
           and abs(flt(pi_medicament.taxes[0].rate) - 7.0) < 0.001,
           f"Médicament : TVA 7 % (taux réduit) sur le compte "
           f"{_compte_taxe(pi_medicament)}", results)
    _check(abs(flt(pi_medicament.total_taxes_and_charges) - HT_MEDICAMENT * 0.07) < 0.01,
           f"Médicament : TVA {pi_medicament.total_taxes_and_charges} = "
           f"{HT_MEDICAMENT * 0.07:.3f}", results)

    _check(_compte_taxe(si_fumier) == simulations.COMPTE_TVA_COLLECTEE
           and abs(flt(si_fumier.taxes[0].rate) - 19.0) < 0.001,
           f"Vente : TVA collectée 19 % sur le compte "
           f"{_compte_taxe(si_fumier)} (attendu 4367)", results)
    _check(abs(flt(si_fumier.total_taxes_and_charges) - HT_FUMIER * 0.19) < 0.01,
           f"Vente : TVA {si_fumier.total_taxes_and_charges} = "
           f"{HT_FUMIER * 0.19:.3f}", results)

    # ── 3. TVA au Grand Livre — c'est là que le comptable la lit
    gl_aliment = _gl_par_compte("Purchase Invoice", pi_aliment.name)
    _check(simulations.COMPTE_TVA_DEDUCTIBLE in gl_aliment
           and abs(gl_aliment[simulations.COMPTE_TVA_DEDUCTIBLE][0]
                   - HT_ALIMENT * 0.19) < 0.01,
           f"GL : 4366 débité de {HT_ALIMENT * 0.19:.3f} TND (aliment)", results)
    _check(simulations.COMPTE_FOURNISSEURS in gl_aliment
           and abs(gl_aliment[simulations.COMPTE_FOURNISSEURS][1]
                   - HT_ALIMENT * 1.19) < 0.01,
           f"GL : 401 crédité du TTC {HT_ALIMENT * 1.19:.3f} TND", results)

    gl_service = _gl_par_compte("Purchase Invoice", pi_service.name)
    _check(simulations.COMPTE_ENTRETIEN in gl_service
           and abs(gl_service[simulations.COMPTE_ENTRETIEN][0] - HT_SERVICE) < 0.01,
           f"GL : 615 « Entretien » débité de {HT_SERVICE:.3f} TND (service)",
           results)

    gl_vente = _gl_par_compte("Sales Invoice", si_fumier.name)
    _check(simulations.COMPTE_TVA_COLLECTEE in gl_vente
           and abs(gl_vente[simulations.COMPTE_TVA_COLLECTEE][1]
                   - HT_FUMIER * 0.19) < 0.01,
           f"GL : 4367 crédité de {HT_FUMIER * 0.19:.3f} TND (vente)", results)

    # ── 4. L'achat d'aliment entre bien en stock
    qty_aliment_apres = _bin_qty(item_aliment)
    _check(abs((qty_aliment_apres - qty_aliment_avant)
               - ACHAT_ALIMENT["quantite"]) < 0.01,
           f"Stock aliment : +{ACHAT_ALIMENT['quantite']:.0f} kg "
           f"({qty_aliment_avant:.0f} → {qty_aliment_apres:.0f})", results)
    # Le CMP exact dépend du stock déjà présent : on vérifie qu'il se RAPPROCHE
    # du prix payé, ce qui est vrai quel que soit l'état de départ du site.
    cmp_aliment_apres = _cmp(item_aliment)
    prix = ACHAT_ALIMENT["prix"]
    _check(cmp_aliment_apres > 0
           and abs(cmp_aliment_apres - prix) <= abs(cmp_aliment_avant - prix) + 0.001,
           f"CMP aliment tiré vers le prix payé : {cmp_aliment_avant:.3f} → "
           f"{cmp_aliment_apres:.3f} TND/kg (achat @ {prix})", results)

    # ── 5. Utilisation de médicaments : stock décrémenté + charge postée
    qty_med_apres = _bin_qty(item_medicament)
    attendu = ACHAT_MEDICAMENT["quantite"] - TRAITEMENT["flacons"]
    _check(abs((qty_med_apres - qty_med_avant) - attendu) < 0.01,
           f"Stock médicament : +{ACHAT_MEDICAMENT['quantite']:.0f} reçus "
           f"− {TRAITEMENT['flacons']:.0f} consommés = {attendu:+.0f} "
           f"({qty_med_avant:.0f} → {qty_med_apres:.0f})", results)

    traitement = frappe.get_doc("Traitement", r1["traitement"])
    sorties = frappe.get_all(
        "Stock Entry",
        filters={"remarks": f"Traitement {traitement.name}", "docstatus": 1},
        pluck="name")
    _check(len(sorties) == 1,
           f"Une sortie de stock émise pour le traitement ({sorties})", results)

    gl_trt = _gl_traitement(traitement.name)
    debits = {num: montants for num, montants in gl_trt.items() if montants[0] > 0}
    _check(bool(debits),
           f"Charge postée au Grand Livre pour le traitement ({debits})", results)
    _check(simulations.COMPTE_MEDICAMENTS in debits,
           f"Charge imputée sur 602 « Consommation de médicaments » "
           f"(comptes débités : {sorted(debits)})", results)
    # La valeur de la charge est celle du stock sorti : on la confronte au
    # Stock Ledger plutôt qu'à un prix théorique — le CMP dépend de l'état du
    # site, la cohérence GL ↔ SLE, elle, doit être vraie partout.
    total_debit = sum(m[0] for m in debits.values())
    valeur_sle = float(frappe.db.sql("""
        SELECT COALESCE(SUM(-stock_value_difference), 0)
        FROM `tabStock Ledger Entry`
        WHERE voucher_type = 'Stock Entry' AND voucher_no IN %(sorties)s
          AND is_cancelled = 0
    """, {"sorties": tuple(sorties) or ("",)})[0][0] or 0)
    _check(total_debit > 0 and abs(total_debit - valeur_sle) < 0.01,
           f"Charge {total_debit:.3f} TND = valeur sortie du stock "
           f"{valeur_sle:.3f} TND ({TRAITEMENT['flacons']:.0f} flacons au CMP)",
           results)

    etat = frappe.db.get_value(
        "Animal", traitement.animal,
        ["attente_lait_active", "date_fin_attente_lait"], as_dict=True)
    _check(etat.attente_lait_active == 1 and bool(etat.date_fin_attente_lait),
           f"Délai d'attente lait posé sur {traitement.animal} "
           f"(jusqu'au {etat.date_fin_attente_lait})", results)

    # ── 6. Idempotence — deux exécutions, les mêmes documents
    r2 = setup_simulations()
    for cle in ("facture_aliment", "facture_service", "facture_medicament",
                "traitement", "vente_taxable"):
        _check(r2.get(cle) == r1.get(cle),
               f"Re-run → même {cle} ({r2.get(cle)})", results)
    for marqueur in MARQUEURS_ACHAT:
        n = len(frappe.get_all("Purchase Invoice",
                               filters={"remarks": ["like", f"%{marqueur}%"],
                                        "docstatus": ["<", 2]}))
        _check(n == 1, f"Une seule facture active pour {marqueur} (n={n})",
               results)
    for marqueur in MARQUEURS_VENTE:
        n = len(frappe.get_all("Sales Invoice",
                               filters={"remarks": ["like", f"%{marqueur}%"],
                                        "docstatus": ["<", 2]}))
        _check(n == 1, f"Une seule vente active pour {marqueur} (n={n})", results)
    n_trt = len(frappe.get_all(
        "Traitement",
        filters={"observations": ["like", f"%{MARQUEUR_TRAITEMENT}%"]}))
    _check(n_trt == 1, f"Un seul traitement simulé (n={n_trt})", results)
    _check(abs(_bin_qty(item_medicament) - qty_med_apres) < 0.01,
           "Re-run → aucun mouvement de stock supplémentaire", results)

    # ── 7. apercu_tva recolle avec les documents
    tva = apercu_tva(str(get_first_day(today())), today())
    _check(tva["collectee"] >= HT_FUMIER * 0.19 - 0.01,
           f"TVA collectée du mois ≥ celle de la vente simulée "
           f"({tva['collectee']})", results)
    tva_achats = (HT_ALIMENT + HT_SERVICE) * 0.19 + HT_MEDICAMENT * 0.07
    _check(tva["deductible"] >= tva_achats - 0.01,
           f"TVA déductible du mois ≥ celle des achats simulés "
           f"({tva['deductible']} ≥ {tva_achats:.3f})", results)
    _check(abs(tva["solde"] - (tva["collectee"] - tva["deductible"])) < 0.01
           and tva["sens"] in ("TVA À PAYER", "CRÉDIT DE TVA REPORTABLE",
                               "POSITION NULLE"),
           f"Position TVA cohérente : {tva['solde']} → {tva['sens']}", results)

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
