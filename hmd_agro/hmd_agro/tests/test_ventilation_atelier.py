"""
SCRUM-10 — tests de la ventilation des charges par atelier.

Le trou que ces tests ferment : la lecture du Grand Livre n'a jamais regardé le
centre de coût — ni SELECT, ni filtre, ni GROUP BY. Le coût complet au litre
divisait donc TOUTES les charges de la ferme (génisses, cultures, traction,
frais généraux compris) par les SEULS litres de lait. Il était structurellement
surestimé, et le chiffre s'affichait sans la moindre réserve.

Couvre les cinq cas de la sous-tâche 5 du ticket, plus le périmètre décidé en
revue reporting :

  1. Mois sans écriture → zéro honnête, pas d'erreur
  2. Somme des ateliers + non imputé = total, et ce total = `gl_sums` charges
     (les deux lectures ne peuvent pas diverger)
  3. Une charge imputée tombe dans SON atelier et dans SON poste
  4. Une écriture ANNULÉE n'est pas une charge
  5. Une charge sans centre de coût apparaît en « Non imputé » VISIBLE,
     jamais fondue dans un atelier
  6. Coût du litre = atelier Lait + quote-part des charges générales, la
     quote-part étant la SOMME des répartitions saisies sur chaque charge
     (décision 26/08/2026) : sans répartition → quote-part 0 et FG non réparti
     visible ; avec répartition → quote-part exacte. Le non imputé reste dehors
  7. Le coût mécanique n'entre toujours pas dans le coût complet (FIN-S96)
  8. Un périmètre inconnu lève ERR-FIN-10 plutôt que de calculer n'importe quoi

Fixtures isolées sur AVRIL 2025, préfixe ZZTEST_VENT. Le mois n'est pas choisi
au hasard : l'exercice 2025 est ACTIF (sans quoi le submit lève FiscalYearError)
et ne porte AUCUNE écriture réelle, ce qui rend les totaux absolus — on teste
des égalités, pas des « au moins ».

Pré-requis site : socle comptable (Cost Centers ateliers), DocType
Repartition Atelier Charge + Custom Fields SCRUM-10 migrés (cas 6b).

Run: bench --site hmd.agro execute \
        hmd_agro.hmd_agro.tests.test_ventilation_atelier.run
"""
import traceback

import frappe

from hmd_agro.hmd_agro.report.rapport_performance.rapport_performance import (
    SECTION_FRAIS_GENERAUX, execute as executer_rapport,
)
from hmd_agro.hmd_agro.utils.finance_kpis import (
    ATELIER_FRAIS_GENERAUX, charges_lait, gl_sums, gl_sums_par_atelier,
)

COMPANY = "hmd-agro"
PREFIXE = "ZZTEST_VENT"

DEBUT = "2025-04-01"
FIN = "2025-04-30"
DATE_ECRITURE = "2025-04-10"
DATE_RAPPORT = "2025-04-15"
MOIS_VIERGE_DEBUT = "2025-09-01"      # jamais alimenté, même exercice actif
MOIS_VIERGE_FIN = "2025-09-30"
DATE_RAPPORT_VIERGE = "2025-09-15"

# Scénario : 1 000 au Lait, 500 aux Génisses, 300 aux Frais Généraux SANS
# répartition (elle reste hors coût du litre), puis 200 aux Frais Généraux
# répartis 50 % Lait / 50 % Génisses → quote-part = 100, coût du lait = 1 100.
MONTANT_LAIT = 1000
MONTANT_GENISSES = 500
MONTANT_FRAIS_GENERAUX = 300
MONTANT_FG_REPARTI = 200
PART_LAIT_PCT = 50
MONTANT_NON_IMPUTE = 200
QUOTE_PART_ATTENDUE = 100.0
COUT_LAIT_ATTENDU = 1100.0
FG_NON_REPARTI_ATTENDU = 300.0


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _abbr():
    return frappe.db.get_value("Company", COMPANY, "abbr")


def _acc(numero):
    return frappe.db.get_value("Account", {"account_number": numero,
                                           "company": COMPANY}, "name")


def _cc(nom):
    return f"{nom} - {_abbr()}"


def _cleanup():
    for je in frappe.get_all("Journal Entry",
                             filters={"user_remark": ["like", f"%{PREFIXE}%"]},
                             pluck="name"):
        frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", je)
        frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent=%s", je)
        frappe.db.sql("DELETE FROM `tabRepartition Atelier Charge` WHERE parent=%s", je)
        frappe.db.sql("DELETE FROM `tabJournal Entry` WHERE name=%s", je)
    frappe.db.commit()


def _charge(compte, montant, atelier, suffixe, date=DATE_ECRITURE, repartition=()):
    """Une charge passée au compte `compte`, imputée à `atelier`, avec sa
    répartition éventuelle ((atelier, %), …) sur la ligne 1."""
    cc = _cc(atelier)
    je = frappe.get_doc({
        "doctype": "Journal Entry", "company": COMPANY,
        "voucher_type": "Journal Entry", "posting_date": date,
        "user_remark": f"{PREFIXE}_{suffixe}",
        "accounts": [
            {"account": _acc(compte), "debit_in_account_currency": montant,
             "cost_center": cc},
            {"account": _acc("54"), "credit_in_account_currency": montant,
             "cost_center": cc},
        ],
        "repartition_atelier": [
            {"ligne": 1, "atelier": _cc(nom), "pourcentage": pct}
            for nom, pct in repartition
        ],
    })
    je.insert(ignore_permissions=True)
    je.submit()
    return je.name


def _vider_cost_center(voucher):
    """Simule une écriture SANS atelier.

    ERPNext impose un centre de coût à la saisie ; les écritures orphelines
    viennent d'imports ou de reprises d'historique. On reproduit ce cas à la
    source — dans le Grand Livre — parce que c'est là que le rapport lit, et
    que c'est le seul moyen de vérifier que « Non imputé » n'est pas du code
    mort qui ne se déclenche jamais.
    """
    frappe.db.sql("UPDATE `tabGL Entry` SET cost_center=NULL WHERE voucher_no=%s",
                  voucher)
    frappe.db.commit()


def _ligne(rows, section, prefixe):
    return next((r for r in rows if r["section"] == section
                 and r["indicateur"].startswith(prefixe)), None)


# ─── Tests ───

def _test_mois_vierge(results):
    print("\n[1] Un mois sans écriture → zéro honnête")
    v = gl_sums_par_atelier(MOIS_VIERGE_DEBUT, MOIS_VIERGE_FIN)
    _check(v["total"] == 0, f"total = 0 (got {v['total']})", results)
    _check(v["ateliers"] == {}, "aucun atelier listé", results)
    _check(v["non_impute"]["total"] == 0, "non imputé = 0", results)
    lait = charges_lait(MOIS_VIERGE_DEBUT, MOIS_VIERGE_FIN)
    _check(lait["total"] == 0 and lait["quote_part"] == 0,
           "coût du lait = 0 sans lever d'erreur", results)


def _test_ventilation_et_postes(results):
    print("\n[2] Chaque charge tombe dans son atelier et son poste")
    v = gl_sums_par_atelier(DEBUT, FIN)
    lait = v["ateliers"].get("Lait", {})
    genisses = v["ateliers"].get("Élevage - Génisses", {})
    fg = v["ateliers"].get(ATELIER_FRAIS_GENERAUX, {})
    _check(round(lait.get("total", 0)) == MONTANT_LAIT,
           f"atelier Lait = {MONTANT_LAIT} (got {lait.get('total')})", results)
    _check(round(lait.get("postes", {}).get("ration", 0)) == MONTANT_LAIT,
           "la charge 601 est classée au poste « ration »", results)
    _check(round(genisses.get("total", 0)) == MONTANT_GENISSES,
           f"atelier Génisses = {MONTANT_GENISSES}", results)
    _check(round(genisses.get("postes", {}).get("personnel", 0)) == MONTANT_GENISSES,
           "la charge 640 est classée au poste « personnel »", results)
    _check(round(fg.get("total", 0)) == MONTANT_FRAIS_GENERAUX,
           f"atelier Frais Généraux = {MONTANT_FRAIS_GENERAUX}", results)


def _test_somme_egale_total(results):
    print("\n[3] La ventilation ne peut pas diverger du Grand Livre")
    v = gl_sums_par_atelier(DEBUT, FIN)
    somme = round(sum(a["total"] for a in v["ateliers"].values())
                  + v["non_impute"]["total"], 2)
    _check(somme == v["total"],
           f"somme des ateliers + non imputé = total ({somme} vs {v['total']})",
           results)
    _check(v["total"] == round(gl_sums(DEBUT, FIN)["charges"], 2),
           "et ce total égale les charges lues par gl_sums", results)


def _test_ecriture_annulee(results):
    print("\n[4] Une écriture annulée n'est pas une charge")
    avant = gl_sums_par_atelier(DEBUT, FIN)["total"]
    nom = _charge("601", 777, "Lait", "ANNULEE")
    frappe.get_doc("Journal Entry", nom).cancel()
    frappe.db.commit()
    apres = gl_sums_par_atelier(DEBUT, FIN)["total"]
    _check(apres == avant,
           f"le total n'a pas bougé après annulation ({avant} → {apres})",
           results)


def _test_non_impute_visible(results):
    print("\n[5] Une charge sans atelier est VISIBLE, pas fondue")
    nom = _charge("605", MONTANT_NON_IMPUTE, "Lait", "ORPHELINE")
    _vider_cost_center(nom)
    v = gl_sums_par_atelier(DEBUT, FIN)
    _check(round(v["non_impute"]["total"]) == MONTANT_NON_IMPUTE,
           f"non imputé = {MONTANT_NON_IMPUTE} "
           f"(got {v['non_impute']['total']})", results)
    _check(round(v["ateliers"]["Lait"]["total"]) == MONTANT_LAIT,
           "l'atelier Lait n'a PAS absorbé la charge orpheline", results)
    # Et la ligne existe à l'écran même quand elle vaut zéro : une ligne absente
    # se lit « rien à signaler », une ligne à 0 se lit « vérifié ».
    rows = executer_rapport({"periode": "Mois", "date": DATE_RAPPORT_VIERGE})[1]
    ligne = _ligne(rows, "Charges par Atelier", "Non imputé")
    _check(ligne is not None and ligne["valeur"] == 0,
           "sur un mois vierge, la ligne « Non imputé » s'affiche quand même à 0",
           results)


def _test_fg_sans_repartition(results):
    print("\n[6a] Frais généraux SANS répartition → quote-part 0, non réparti visible")
    lait = charges_lait(DEBUT, FIN)
    _check(lait["perimetre"] == "LAIT_QUOTE_PART",
           "périmètre par défaut = LAIT_QUOTE_PART (décision revue reporting)",
           results)
    _check(lait["direct"] == MONTANT_LAIT,
           f"charges directes du Lait = {MONTANT_LAIT} (got {lait['direct']})",
           results)
    _check(lait["quote_part"] == 0 and lait["total"] == MONTANT_LAIT,
           "sans répartition saisie, rien ne revient au lait "
           f"(quote-part {lait['quote_part']}, total {lait['total']})", results)
    _check(lait["fg_total"] == MONTANT_FRAIS_GENERAUX
           and lait["fg_non_reparti"] == MONTANT_FRAIS_GENERAUX,
           f"les {MONTANT_FRAIS_GENERAUX} de frais généraux sont signalés non "
           f"répartis (got {lait['fg_non_reparti']})", results)
    rows = executer_rapport({"periode": "Mois", "date": DATE_RAPPORT})[1]
    ligne = _ligne(rows, SECTION_FRAIS_GENERAUX, "Frais généraux non répartis")
    _check(ligne is not None and ligne["valeur"] == MONTANT_FRAIS_GENERAUX
           and ligne["indicator"] == "Orange",
           "le rapport nomme le non réparti, en orange", results)


def _test_fg_avec_repartition(results):
    print("\n[6b] Frais généraux répartis → quote-part = somme des parts Lait")
    lait = charges_lait(DEBUT, FIN)
    _check(lait["quote_part"] == QUOTE_PART_ATTENDUE,
           f"quote-part = {QUOTE_PART_ATTENDUE} ({PART_LAIT_PCT} % de "
           f"{MONTANT_FG_REPARTI}) (got {lait['quote_part']})", results)
    _check(lait["total"] == COUT_LAIT_ATTENDU,
           f"total retenu = {COUT_LAIT_ATTENDU} (got {lait['total']})", results)
    _check(lait["fg_reparti"] == MONTANT_FG_REPARTI
           and lait["fg_non_reparti"] == FG_NON_REPARTI_ATTENDU,
           f"réparti {MONTANT_FG_REPARTI}, non réparti {FG_NON_REPARTI_ATTENDU} "
           f"(got {lait['fg_reparti']} / {lait['fg_non_reparti']})", results)
    _check("cle_pct" not in lait, "plus aucune clé calculée (cle_pct)", results)
    # Le point qui justifie toute la story : l'ancien calcul retenait TOUT.
    toutes = charges_lait(DEBUT, FIN, perimetre="TOUTES_CHARGES")
    _check(toutes["total"] > lait["total"],
           f"l'ancien périmètre surestimait bien le lait "
           f"({toutes['total']} vs {lait['total']})", results)
    _check(charges_lait(DEBUT, FIN, perimetre="LAIT_SEUL")["total"] == MONTANT_LAIT,
           "le périmètre « Lait seul » retient exactement les charges directes",
           results)


def _test_non_impute_hors_cout_litre(results):
    print("\n[7] Le non imputé n'entre pas dans le coût du litre")
    lait = charges_lait(DEBUT, FIN)
    _check(lait["non_impute"] == MONTANT_NON_IMPUTE,
           f"il est remonté à part ({lait['non_impute']})", results)
    _check(lait["total"] == COUT_LAIT_ATTENDU,
           "et le total du coût du lait ne l'a pas absorbé", results)


def _test_perimetre_invalide(results):
    print("\n[8] Un périmètre inconnu est refusé, pas deviné")
    try:
        charges_lait(DEBUT, FIN, perimetre="N_IMPORTE_QUOI")
        _check(False, "aucune erreur levée — le calcul serait silencieusement faux",
               results)
    except frappe.ValidationError as erreur:
        _check("ERR-FIN-10" in str(erreur),
               "ERR-FIN-10 levée avec la liste des périmètres valides", results)


def _test_rapport_sections(results):
    print("\n[9] Le rapport expose la ventilation et le détail du coût du lait")
    rows = executer_rapport({"periode": "Mois", "date": DATE_RAPPORT})[1]
    sections = {r["section"] for r in rows}
    _check("Charges par Atelier" in sections,
           "section « Charges par Atelier » présente", results)
    _check("Coût du Lait (détail)" in sections,
           "section « Coût du Lait (détail) » présente", results)
    detail = [r for r in rows if r["section"] == "Coût du Lait (détail)"]
    total = next((r for r in detail
                  if r["indicateur"].startswith("TOTAL —")), None)
    _check(total is not None and total["valeur"] == COUT_LAIT_ATTENDU,
           f"le détail totalise {COUT_LAIT_ATTENDU} (got "
           f"{total['valeur'] if total else None})", results)
    # Rapprochement comptable : la somme des postes doit refaire le total.
    postes = [r["valeur"] for r in detail
              if not r["indicateur"].startswith(("Sous-total", "TOTAL",
                                                 "Quote-part", "Rappel"))]
    _check(abs(round(sum(postes), 2) - COUT_LAIT_ATTENDU) < 0.02,
           f"la somme des postes refait le total ({round(sum(postes), 2)})",
           results)
    controle = _ligne(rows, "Charges par Atelier", "Total ventilé")
    _check(controle is not None and "doit égaler" in controle["indicateur"],
           "la ligne de contrôle ne signale aucun écart", results)


def _test_meca_hors_cout_complet(results):
    print("\n[10] Le coût mécanique n'entre toujours pas dans le coût complet")
    rows = executer_rapport({"periode": "Mois", "date": DATE_RAPPORT})[1]
    complet = _ligne(rows, "Coûts Unitaires", "Coût Complet / L")
    _check(complet is not None
           and "quote-part" in complet["indicateur"],
           "le libellé nomme le périmètre retenu", results)
    meca = _ligne(rows, "Coûts Unitaires", "Coût Mécanique / L")
    _check(meca is not None and "non additionnable" in meca["indicateur"],
           "le coût mécanique reste annoncé non additionnable", results)
    # Avril 2025 n'a aucun lait produit : le coût au litre vaut 0, et c'est la
    # bonne réponse — on ne divise pas par zéro, on ne devine pas non plus.
    _check(complet is not None and complet["valeur"] == 0,
           "sans production, le coût au litre vaut 0 (pas d'erreur)", results)


def run():
    print("\n" + "=" * 70)
    print("  SCRUM-10 — Ventilation des charges par atelier")
    print("=" * 70)
    try:
        return _run_inner()
    except Exception:
        print("\n  ❌ Test crashed mid-flight:")
        print(traceback.format_exc())
        return {"pass": 0, "fail": 1}
    finally:
        _cleanup()


def _run_inner():
    results = {"pass": 0, "fail": 0}
    _cleanup()

    _test_mois_vierge(results)

    _charge("601", MONTANT_LAIT, "Lait", "RATION")
    _charge("640", MONTANT_GENISSES, "Élevage - Génisses", "MO")
    _charge("606", MONTANT_FRAIS_GENERAUX, ATELIER_FRAIS_GENERAUX, "FG")
    frappe.db.commit()

    _test_ventilation_et_postes(results)
    _test_somme_egale_total(results)
    _test_ecriture_annulee(results)
    _test_fg_sans_repartition(results)

    _charge("606", MONTANT_FG_REPARTI, ATELIER_FRAIS_GENERAUX, "FG_REPARTI",
            repartition=(("Lait", PART_LAIT_PCT),
                         ("Élevage - Génisses", 100 - PART_LAIT_PCT)))
    frappe.db.commit()

    _test_fg_avec_repartition(results)
    _test_non_impute_visible(results)
    _test_non_impute_hors_cout_litre(results)
    _test_perimetre_invalide(results)
    _test_rapport_sections(results)
    _test_meca_hors_cout_complet(results)

    print("\n" + "-" * 70)
    print(f"  {results['pass']} OK / {results['fail']} FAIL")
    print("-" * 70)
    return results
