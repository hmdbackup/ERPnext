"""
SCRUM-10 — tests de la répartition des frais généraux par charge.

Décision du 26/08/2026 : plus de clé calculée. Sur chaque charge imputée à
Frais Généraux, le comptable saisit des lignes « atelier + % » dont le total
doit faire 100 % ; la quote-part du lait est la SOMME de ces parts. La
répartition est analytique — le Grand Livre reste à Frais Généraux.

Couvre :
   1. Répartition à 100 % acceptée, `montant` / `libelle` dérivés (JE)
   2. 80 %                       → ERR-FIN-12
   3. Ligne non FG / inexistante → ERR-FIN-11
   4. Atelier = Frais Généraux   → ERR-FIN-13
   5. Même atelier deux fois     → ERR-FIN-14
   6. Atelier groupe             → ERR-FIN-15
   7. Part hors ]0 ; 100]        → ERR-FIN-16
   8. Le chemin de la comptable : une Purchase Invoice répartie
   9. `repartitions_frais_generaux` : montants par atelier et par poste,
      charge nue listée, écriture annulée exclue, contrôle contre le GL
  10. `charges_lait` : quote-part = Σ Lait, plus de `cle_pct`, fg_* exposés
  11. Le rapport expose la section « Frais Généraux — répartition par atelier »
  12. Mode strict : ON bloque une ligne FG nue (ERR-FIN-17), OFF la laisse passer

Fixtures isolées sur JUIN 2025, préfixe ZZTEST_RFG. L'exercice 2025 est ACTIF
(sinon le submit lève FiscalYearError) et ne porte AUCUNE écriture réelle —
les totaux sont donc absolus. Avril et septembre 2025 appartiennent à
test_ventilation_atelier, mai 2025 à test_rapport_interventions.

Pré-requis site : socle comptable (Cost Centers ateliers, comptes 6xx / 54),
DocType Repartition Atelier Charge + Custom Fields SCRUM-10 migrés.

Run: bench --site hmd.agro execute \
        hmd_agro.hmd_agro.tests.test_repartition_charges.run
"""
import traceback

import frappe

from hmd_agro.hmd_agro.report.rapport_performance.rapport_performance import (
    SECTION_FRAIS_GENERAUX, execute as executer_rapport,
)
from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.finance_kpis import (
    ATELIER_FRAIS_GENERAUX, ATELIER_LAIT, charges_lait,
    repartitions_frais_generaux,
)

COMPANY = "hmd-agro"
PREFIXE = "ZZTEST_RFG"
CHAMP_MODE_STRICT = "repartition_fg_obligatoire"

DEBUT = "2025-06-01"
FIN = "2025-06-30"
DATE_ECRITURE = "2025-06-10"
DATE_FACTURE = "2025-06-12"
DATE_RAPPORT = "2025-06-15"

FOURNISSEUR = f"{PREFIXE} Assureur"
ITEM = f"{PREFIXE}-ASSURANCE"
ITEM_NOM = f"{PREFIXE} Assurance multirisque"

# Scénario (tous les montants en DT) :
#   JE 615 FG 1 000, répartie Lait 45 / Cultures 35 / Traction 20 → Lait 450
#   PI 616 FG 1 900, répartie Lait 50 / Génisses 50                → Lait 950
#   JE 606 FG   300, SANS répartition                              → non répartie
#   JE 601 Lait 500, charge directe de l'atelier Lait
MONTANT_ENTRETIEN = 1000
MONTANT_FACTURE = 1900
MONTANT_NUE = 300
MONTANT_LAIT_DIRECT = 500
PARTS_ENTRETIEN = (("Lait", 45), ("Cultures - Fourrage", 35), ("Traction", 20))
PARTS_FACTURE = (("Lait", 50), ("Élevage - Génisses", 50))

LAIT_ATTENDU = 1400.0
PAR_ATELIER_ATTENDU = {"Lait": 1400.0, "Cultures - Fourrage": 350.0,
                       "Traction": 200.0, "Élevage - Génisses": 950.0}
POSTES_LAIT_ATTENDUS = {"mecanique": 450.0, "autres": 950.0}
TOTAL_FG_ATTENDU = 3200.0
REPARTI_ATTENDU = 2900.0
NON_REPARTI_ATTENDU = 300.0
COUT_LAIT_ATTENDU = 1900.0


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _attendre_erreur(code, action, msg, results):
    """`action` must raise a frappe.ValidationError carrying `code`."""
    try:
        action()
        _check(False, f"{msg} — aucune erreur levée", results)
    except frappe.ValidationError as erreur:
        _check(code in str(erreur), f"{msg} → {code} (got : {str(erreur)[:90]})",
               results)


def _abbr():
    return frappe.db.get_value("Company", COMPANY, "abbr")


def _acc(numero):
    return frappe.db.get_value("Account", {"account_number": numero,
                                           "company": COMPANY}, "name")


def _cc(nom):
    return f"{nom} - {_abbr()}"


def _definir_mode_strict(valeur):
    frappe.db.set_single_value("HMD Configuration", CHAMP_MODE_STRICT, valeur)
    # get_single_value met la valeur en cache par requête — l'invalider pour
    # que la lecture suivante voie la nouvelle valeur (pattern test_personnel).
    getattr(frappe.db, "value_cache", {}).pop("HMD Configuration", None)


# ─── Fixtures ───

def _parts(parts, ligne=1):
    return [{"ligne": ligne, "atelier": _cc(atelier), "pourcentage": pct}
            for atelier, pct in parts]


def _ecriture(compte, montant, atelier, suffixe, parts=(), ligne=1,
              soumettre=True, flags=None):
    """Une charge au compte `compte`, imputée à `atelier`, avec ses parts.
    `flags` : posés sur le document avant l'insertion (pièces système)."""
    cc = _cc(atelier)
    je = frappe.get_doc({
        "doctype": "Journal Entry", "company": COMPANY,
        "voucher_type": "Journal Entry", "posting_date": DATE_ECRITURE,
        "user_remark": f"{PREFIXE}_{suffixe}",
        "accounts": [
            {"account": _acc(compte), "debit_in_account_currency": montant,
             "cost_center": cc},
            {"account": _acc("54"), "credit_in_account_currency": montant,
             "cost_center": cc},
        ],
        "repartition_atelier": _parts(parts, ligne),
    })
    for cle, valeur in (flags or {}).items():
        je.flags[cle] = valeur
    je.insert(ignore_permissions=True)
    if soumettre:
        je.submit()
    return je.name


def _fournisseur():
    if not frappe.db.exists("Supplier", FOURNISSEUR):
        frappe.get_doc({"doctype": "Supplier", "supplier_name": FOURNISSEUR,
                        "supplier_type": "Company"}).insert(ignore_permissions=True)
    return FOURNISSEUR


def _article():
    """Prestation non stockée, imputée d'office au 616 / Frais Généraux — le
    support de la facture d'assurance que saisit la comptable."""
    if not frappe.db.exists("Item", ITEM):
        frappe.get_doc({
            "doctype": "Item", "item_code": ITEM, "item_name": ITEM_NOM,
            "item_group": "All Item Groups", "stock_uom": "Unit",
            "is_stock_item": 0, "is_purchase_item": 1, "is_sales_item": 0,
            "item_defaults": [{
                "company": COMPANY, "expense_account": _acc("616"),
                "buying_cost_center": _cc(ATELIER_FRAIS_GENERAUX),
            }],
        }).insert(ignore_permissions=True)
    return ITEM


def _facture(montant, parts, suffixe):
    """Le chemin de la comptable : une Purchase Invoice à une ligne, imputée
    à Frais Généraux, répartie dans la table enfant."""
    pi = frappe.get_doc({
        "doctype": "Purchase Invoice", "company": COMPANY,
        "supplier": _fournisseur(), "posting_date": DATE_FACTURE,
        "set_posting_time": 1, "bill_no": f"{PREFIXE}_{suffixe}",
        "bill_date": DATE_FACTURE, "disable_rounded_total": 1,
        "remarks": f"{PREFIXE}_{suffixe}",
        "items": [{"item_code": _article(), "qty": 1, "rate": montant,
                   "cost_center": _cc(ATELIER_FRAIS_GENERAUX)}],
        "repartition_atelier": _parts(parts),
    })
    pi.insert(ignore_permissions=True)
    pi.submit()
    return pi.name


def _supprimer_piece(doctype, nom, enfants):
    frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", nom)
    frappe.db.sql("DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no=%s", nom)
    for enfant in enfants + ("Repartition Atelier Charge",):
        frappe.db.sql(f"DELETE FROM `tab{enfant}` WHERE parent=%s", nom)
    frappe.db.sql(f"DELETE FROM `tab{doctype}` WHERE name=%s", nom)


def _cleanup():
    for pi in frappe.get_all("Purchase Invoice",
                             filters={"remarks": ["like", f"%{PREFIXE}%"]},
                             pluck="name"):
        _supprimer_piece("Purchase Invoice", pi,
                         ("Purchase Invoice Item", "Purchase Taxes and Charges",
                          "Purchase Invoice Advance"))
    for je in frappe.get_all("Journal Entry",
                             filters={"user_remark": ["like", f"%{PREFIXE}%"]},
                             pluck="name"):
        _supprimer_piece("Journal Entry", je, ("Journal Entry Account",))
    for doctype, nom in (("Item", ITEM), ("Supplier", FOURNISSEUR)):
        if frappe.db.exists(doctype, nom):
            frappe.delete_doc(doctype, nom, force=1, ignore_permissions=True)
    frappe.db.commit()


# ─── Lectures ───

def _ligne_rapport(rows, prefixe):
    return next((r for r in rows if r["section"] == SECTION_FRAIS_GENERAUX
                 and r["indicateur"].startswith(prefixe)), None)


# ─── Tests ───

def _test_repartition_complete(results):
    print("\n[1] Une répartition à 100 % passe, montants et libellés dérivés")
    nom = _ecriture("615", MONTANT_ENTRETIEN, ATELIER_FRAIS_GENERAUX,
                    "ENTRETIEN", PARTS_ENTRETIEN)
    je = frappe.get_doc("Journal Entry", nom)
    _check(je.docstatus == 1, "l'écriture répartie 45 / 35 / 20 est soumise", results)
    montants = [round(p.montant, 2) for p in je.repartition_atelier]
    _check(montants == [450.0, 350.0, 200.0],
           f"montants dérivés = 1 000 × part (got {montants})", results)
    libelle_attendu = frappe.db.get_value("Account", _acc("615"), "account_name")
    _check(all(p.libelle == libelle_attendu for p in je.repartition_atelier),
           f"libellé dérivé = nom du compte « {libelle_attendu} »", results)
    return nom


def _test_erreurs_de_saisie(results):
    nom = _ecriture("615", 100, ATELIER_FRAIS_GENERAUX, "TIERS",
                    (("Lait", 33.33), ("Cultures - Fourrage", 33.33),
                     ("Traction", 33.33)), soumettre=False)
    _check(frappe.db.exists("Journal Entry", nom),
           "3 × 33,33 % = 99,99 % passe (comparaison à 2 décimales)", results)

    print("\n[2] 80 % → ERR-FIN-12")
    _attendre_erreur(
        "ERR-FIN-12",
        lambda: _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "INCOMPLETE",
                          (("Lait", 45), ("Cultures - Fourrage", 35))),
        "répartition à 80 % refusée", results)

    print("\n[3] Ligne non FG ou inexistante → ERR-FIN-11")
    _attendre_erreur(
        "ERR-FIN-11",
        lambda: _ecriture("606", 100, "Lait", "NON_FG", (("Traction", 100),)),
        "une charge de l'atelier Lait ne se répartit pas", results)
    _attendre_erreur(
        "ERR-FIN-11",
        lambda: _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "LIGNE_INEXISTANTE",
                          (("Lait", 100),), ligne=5),
        "une ligne qui n'existe pas est refusée", results)

    print("\n[4] Atelier = Frais Généraux → ERR-FIN-13")
    _attendre_erreur(
        "ERR-FIN-13",
        lambda: _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "SUR_SOI",
                          ((ATELIER_FRAIS_GENERAUX, 100),)),
        "répartir sur Frais Généraux lui-même est refusé", results)

    print("\n[5] Même atelier deux fois → ERR-FIN-14")
    _attendre_erreur(
        "ERR-FIN-14",
        lambda: _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "DOUBLON",
                          (("Lait", 50), ("Lait", 50))),
        "le doublon d'atelier est refusé", results)

    print("\n[6] Atelier groupe → ERR-FIN-15")
    _attendre_erreur(
        "ERR-FIN-15",
        lambda: _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "GROUPE",
                          (("HMD Agro", 100),)),
        "un centre de coût groupe est refusé", results)

    print("\n[7] Part hors ]0 ; 100] → ERR-FIN-16")
    _attendre_erreur(
        "ERR-FIN-16",
        lambda: _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "HORS_BORNES",
                          (("Lait", 150),)),
        "une part de 150 % est refusée", results)


def _test_facture_achat(results):
    print("\n[8] Le chemin de la comptable : une facture d'achat répartie")
    nom = _facture(MONTANT_FACTURE, PARTS_FACTURE, "FACTURE")
    pi = frappe.get_doc("Purchase Invoice", nom)
    _check(pi.docstatus == 1, "la facture répartie 50 / 50 est soumise", results)
    _check(pi.items[0].expense_account == _acc("616"),
           "la ligne est passée au 616 (compte par défaut de l'article)", results)
    montants = [round(p.montant, 2) for p in pi.repartition_atelier]
    _check(montants == [950.0, 950.0],
           f"montants dérivés = 1 900 × part (got {montants})", results)
    _check(all(p.libelle == ITEM_NOM for p in pi.repartition_atelier),
           "libellé dérivé = nom de l'article", results)
    return nom


def _test_lecture_repartitions(results, nom_annulee):
    print("\n[9] repartitions_frais_generaux — par atelier, par poste, contrôle GL")
    lecture = repartitions_frais_generaux(DEBUT, FIN)
    charges = lecture["charges"]
    _check(len(charges) == 3,
           f"3 charges FG listées (entretien, facture, nue) (got {len(charges)})",
           results)
    _check({c["voucher_type"] for c in charges} == {"Journal Entry", "Purchase Invoice"},
           "écritures ET factures remontent", results)
    _check(all(c["voucher"] != nom_annulee for c in charges),
           "l'écriture annulée n'est pas une charge", results)
    nue = next((c for c in charges if not c["repartition"]), None)
    _check(nue is not None and round(nue["montant"], 2) == MONTANT_NUE
           and nue["poste"] == "autres",
           f"la charge nue est listée sans part, poste « autres » (got {nue})",
           results)
    _check(lecture["par_atelier"] == PAR_ATELIER_ATTENDU,
           f"par atelier = {PAR_ATELIER_ATTENDU} (got {lecture['par_atelier']})",
           results)
    _check(lecture["par_atelier_postes"].get(ATELIER_LAIT) == POSTES_LAIT_ATTENDUS,
           f"postes du Lait = {POSTES_LAIT_ATTENDUS} "
           f"(got {lecture['par_atelier_postes'].get(ATELIER_LAIT)})", results)
    _check(lecture["total_fg"] == TOTAL_FG_ATTENDU,
           f"total FG (Grand Livre) = {TOTAL_FG_ATTENDU} (got {lecture['total_fg']})",
           results)
    _check(lecture["total_reparti"] == REPARTI_ATTENDU
           and lecture["non_reparti"] == NON_REPARTI_ATTENDU,
           f"réparti {REPARTI_ATTENDU} + non réparti {NON_REPARTI_ATTENDU} = total FG "
           f"(got {lecture['total_reparti']} / {lecture['non_reparti']})", results)


def _test_charges_lait(results):
    print("\n[10] charges_lait — quote-part = somme des parts Lait")
    lait = charges_lait(DEBUT, FIN)
    _check(lait["quote_part"] == LAIT_ATTENDU,
           f"quote-part = {LAIT_ATTENDU} (got {lait['quote_part']})", results)
    _check(lait["direct"] == MONTANT_LAIT_DIRECT and lait["total"] == COUT_LAIT_ATTENDU,
           f"total = direct {MONTANT_LAIT_DIRECT} + quote-part (got {lait['total']})",
           results)
    _check(lait["postes"] == {"ration": 500.0, **POSTES_LAIT_ATTENDUS},
           f"les postes du Lait cumulent direct et parts (got {lait['postes']})",
           results)
    _check("cle_pct" not in lait, "plus de clé calculée (cle_pct) — décision 26/08",
           results)
    _check((lait["fg_total"], lait["fg_reparti"], lait["fg_non_reparti"])
           == (TOTAL_FG_ATTENDU, REPARTI_ATTENDU, NON_REPARTI_ATTENDU),
           "fg_total / fg_reparti / fg_non_reparti exposés", results)
    _check(charges_lait(DEBUT, FIN, perimetre="LAIT_SEUL")["quote_part"] == 0,
           "le périmètre « Lait seul » ignore la quote-part", results)


def _test_rapport(results):
    print("\n[11] Le rapport expose la répartition, charge par charge")
    rows = executer_rapport({"periode": "Mois", "date": DATE_RAPPORT})[1]
    _check(any(r["section"] == SECTION_FRAIS_GENERAUX for r in rows),
           f"section « {SECTION_FRAIS_GENERAUX} » présente", results)
    total = _ligne_rapport(rows, "Total Frais Généraux")
    _check(total is not None and total["valeur"] == TOTAL_FG_ATTENDU,
           f"Total FG (Grand Livre) = {TOTAL_FG_ATTENDU} (got {total})", results)
    controle = _ligne_rapport(rows, "Contrôle")
    _check(controle is not None and controle["valeur"] == REPARTI_ATTENDU
           and controle["indicator"] == "Orange",
           "contrôle = somme des répartitions, orange (écart = charge nue, mode "
           f"non strict) (got {controle})", results)
    part_lait = _ligne_rapport(rows, f"dont part atelier {ATELIER_LAIT}")
    _check(part_lait is not None and part_lait["valeur"] == LAIT_ATTENDU,
           f"part Lait = {LAIT_ATTENDU} (got {part_lait})", results)
    non_reparti = _ligne_rapport(rows, "Frais généraux non répartis")
    _check(non_reparti is not None and non_reparti["valeur"] == NON_REPARTI_ATTENDU
           and non_reparti["indicator"] == "Orange",
           f"non réparti = {NON_REPARTI_ATTENDU}, orange (got {non_reparti})", results)
    ventilation = _ligne_rapport(rows, "└ Lait 45 % · Cultures - Fourrage 35 % · Traction 20 %")
    _check(ventilation is not None and ventilation["valeur"] is None,
           "la ligne « └ Lait 45 % · … » est là, sans valeur (tiret)", results)
    nue = _ligne_rapport(rows, "└ non répartie")
    _check(nue is not None and nue["indicator"] == "Orange",
           "la charge nue est nommée « └ non répartie », orange", results)
    quote_part = next((r for r in rows if r["section"] == "Coût du Lait (détail)"
                       and r["indicateur"].startswith("Quote-part")), None)
    _check(quote_part is not None and quote_part["valeur"] == LAIT_ATTENDU
           and "somme des répartitions" in quote_part["indicateur"],
           f"le détail du coût du lait reprend la quote-part (got {quote_part})",
           results)


def _test_mode_strict(results):
    print("\n[12] Mode strict — ON bloque une ligne FG nue, OFF la laisse passer")
    _definir_mode_strict(1)
    _attendre_erreur(
        "ERR-FIN-17",
        lambda: _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "STRICT_NUE",
                          soumettre=False),
        "strict ON : une ligne FG sans répartition est bloquée", results)
    nom = _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "STRICT_REPARTIE",
                    (("Lait", 100),), soumettre=False)
    _check(frappe.db.exists("Journal Entry", nom),
           "strict ON : une ligne FG répartie à 100 % passe", results)
    nom = _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "STRICT_SYSTEME",
                    soumettre=False, flags={"ignore_repartition_fg": True})
    _check(frappe.db.exists("Journal Entry", nom),
           "strict ON : une pièce système (flag ignore_repartition_fg) sans "
           "répartition passe", results)
    _definir_mode_strict(0)
    nom = _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "SOUPLE_NUE",
                    soumettre=False)
    _check(frappe.db.exists("Journal Entry", nom),
           "strict OFF : une ligne FG sans répartition passe (écritures "
           "automatiques salaires / interventions)", results)


# ─── Runner ───

def run():
    print("\n" + "=" * 70)
    print("  SCRUM-10 — Répartition des frais généraux par charge")
    print("=" * 70)
    mode_strict_initial = get_config(CHAMP_MODE_STRICT, default=0)
    try:
        return _run_inner()
    except Exception:
        print("\n  ❌ Test crashed mid-flight:")
        print(traceback.format_exc())
        return {"pass": 0, "fail": 1}
    finally:
        _definir_mode_strict(mode_strict_initial)
        _cleanup()


def _run_inner():
    results = {"pass": 0, "fail": 0}
    _cleanup()
    # Le scénario suppose le mode souple ; le mode initial est restauré par run().
    _definir_mode_strict(0)

    _test_repartition_complete(results)
    _test_erreurs_de_saisie(results)
    _test_facture_achat(results)

    _ecriture("606", MONTANT_NUE, ATELIER_FRAIS_GENERAUX, "NUE")
    _ecriture("601", MONTANT_LAIT_DIRECT, "Lait", "LAIT_DIRECT")
    nom_annulee = _ecriture("606", 777, ATELIER_FRAIS_GENERAUX, "ANNULEE",
                            (("Lait", 100),))
    frappe.get_doc("Journal Entry", nom_annulee).cancel()
    frappe.db.commit()

    _test_lecture_repartitions(results, nom_annulee)
    _test_charges_lait(results)
    _test_rapport(results)
    _test_mode_strict(results)

    print("\n" + "-" * 70)
    print(f"  {results['pass']} OK / {results['fail']} FAIL")
    print("-" * 70)
    return results
