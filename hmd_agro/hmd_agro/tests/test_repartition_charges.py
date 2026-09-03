"""
SCRUM-10 — tests des frais généraux répartis par la clé (Cost Center Allocation).

Décision du 03/09/2026 (revue avec Aymen, dans la ligne du 26/08) : plus de
saisie ligne par ligne. Le comptable impute la charge à Frais Généraux ; la
clé de répartition — une « Cost Center Allocation » ERPNext, fixée une fois —
ventile les ÉCRITURES COMPTABLES à la validation, sur toutes les lignes de la
pièce. La quote-part du lait est ce que la clé a envoyé à Lait.

Couvre :
   1. Une écriture sur Frais Généraux → le Grand Livre porte la clé (45/35/20)
   2. Le chemin de la comptable : une facture d'achat à DEUX lignes, rien à
      saisir, les deux lignes réparties — c'est le test demandé le 03/09
   3. Une charge postée AVANT la clé reste à Frais Généraux
   4. Changer la clé = nouvelle allocation datée, l'ancienne reste appliquée
      aux pièces antérieures
   5. `repartitions_frais_generaux` : clé jointe, montants par atelier et par
      poste, écriture annulée exclue, contrôle Grand Livre = clé sans écart
   6. `charges_lait` : total = Lait au Grand Livre, quote-part isolée, LAIT_SEUL
   7. Le rapport : clé en vigueur, « └ Lait 45 % … », charge sans clé nommée
      en orange, contrôle vert
   8. Mode strict : ON refuse une charge FG sans clé (ERR-FIN-11), OFF avertit
      seulement, pièce système exemptée
   9. `cle_en_vigueur` (le texte de l'en-tête de formulaire)

Fixtures isolées sur JUIN 2025, préfixe ZZTEST_RFG. L'exercice 2025 est ACTIF
(sinon le submit lève FiscalYearError) et ne porte AUCUNE écriture réelle —
les totaux sont donc absolus. Avril et septembre 2025 appartiennent à
test_ventilation_atelier, mai 2025 à test_rapport_interventions.

Les clés de test sont posées avec `_skip_from_date_validation` (ERPNext exige
sinon une date de début postérieure à la dernière écriture du centre) et
SUPPRIMÉES en `finally` : une clé oubliée répartirait les vraies écritures.

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
    ATELIER_FRAIS_GENERAUX, ATELIER_LAIT, charges_lait, cle_repartition,
    repartitions_frais_generaux,
)
from hmd_agro.hmd_agro.utils.repartition_charges import cle_en_vigueur

COMPANY = "hmd-agro"
PREFIXE = "ZZTEST_RFG"
CHAMP_MODE_STRICT = "repartition_fg_obligatoire"

DEBUT = "2025-06-01"
FIN = "2025-06-30"
DATE_AVANT_CLE = "2025-06-02"
DATE_CLE_A = "2025-06-05"
DATE_ECRITURE = "2025-06-10"
DATE_FACTURE = "2025-06-12"
DATE_RAPPORT = "2025-06-15"
DATE_CLE_B = "2025-06-20"
DATE_APRES_CLE_B = "2025-06-25"

FOURNISSEUR = f"{PREFIXE} Assureur"
ITEM = f"{PREFIXE}-ASSURANCE"
ITEM_NOM = f"{PREFIXE} Assurance multirisque"
ITEM_2 = f"{PREFIXE}-ENERGIE"
ITEM_2_NOM = f"{PREFIXE} Électricité"

# Scénario (tous les montants en DT) :
#   clé A dès le 05/06 : Lait 45 / Cultures 35 / Traction 20
#   JE 615 FG 1 000 le 10/06              → 450 / 350 / 200
#   PI le 12/06 : 616 1 900 + 606 100     → 855 / 665 / 380 et 45 / 35 / 20
#   JE 606 FG   300 le 02/06, AVANT la clé → reste à Frais Généraux
#   clé B dès le 20/06 : Lait 100
#   JE 606 FG   200 le 25/06              → 200 au Lait
#   JE 601 Lait 500, charge directe de l'atelier Lait
MONTANT_ENTRETIEN = 1000
MONTANT_FACTURE = 1900
MONTANT_FACTURE_2 = 100
MONTANT_AVANT_CLE = 300
MONTANT_APRES_CLE_B = 200
MONTANT_LAIT_DIRECT = 500
CLE_A = (("Lait", 45), ("Cultures - Fourrage", 35), ("Traction", 20))
CLE_B = (("Lait", 100),)

LAIT_ATTENDU = 1550.0
PAR_ATELIER_ATTENDU = {"Lait": 1550.0, "Cultures - Fourrage": 1050.0,
                       "Traction": 600.0}
POSTES_LAIT_ATTENDUS = {"mecanique": 450.0, "autres": 1100.0}
TOTAL_LISTE_ATTENDU = 3500.0
REPARTI_ATTENDU = 3200.0
NON_REPARTI_ATTENDU = 300.0
TOTAL_FG_GL_ATTENDU = 300.0
COUT_LAIT_ATTENDU = 2050.0


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

def _cle(valid_from, parts):
    """The key: a submitted Cost Center Allocation on Frais Généraux."""
    doc = frappe.get_doc({
        "doctype": "Cost Center Allocation", "company": COMPANY,
        "main_cost_center": _cc(ATELIER_FRAIS_GENERAUX), "valid_from": valid_from,
        "allocation_percentages": [
            {"cost_center": _cc(atelier), "percentage": pct} for atelier, pct in parts],
    })
    doc._skip_from_date_validation = True
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc.name


def _ecriture(compte, montant, atelier, suffixe, date=DATE_ECRITURE,
              soumettre=True, flags=None):
    """Une charge au compte `compte`, imputée à `atelier`.
    `flags` : posés sur le document avant l'insertion (pièces système)."""
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


def _article(code, nom, compte):
    """Prestation non stockée, imputée d'office à `compte` / Frais Généraux —
    le support des factures que saisit la comptable."""
    if not frappe.db.exists("Item", code):
        frappe.get_doc({
            "doctype": "Item", "item_code": code, "item_name": nom,
            "item_group": "All Item Groups", "stock_uom": "Unit",
            "is_stock_item": 0, "is_purchase_item": 1, "is_sales_item": 0,
            "item_defaults": [{
                "company": COMPANY, "expense_account": _acc(compte),
                "buying_cost_center": _cc(ATELIER_FRAIS_GENERAUX),
            }],
        }).insert(ignore_permissions=True)
    return code


def _facture(lignes, suffixe):
    """Le chemin de la comptable : une Purchase Invoice imputée à Frais
    Généraux, sans rien d'autre à saisir. `lignes` = [(item, montant)]."""
    pi = frappe.get_doc({
        "doctype": "Purchase Invoice", "company": COMPANY,
        "supplier": _fournisseur(), "posting_date": DATE_FACTURE,
        "set_posting_time": 1, "bill_no": f"{PREFIXE}_{suffixe}",
        "bill_date": DATE_FACTURE, "disable_rounded_total": 1,
        "remarks": f"{PREFIXE}_{suffixe}",
        "cost_center": _cc(ATELIER_FRAIS_GENERAUX),
        "items": [{"item_code": item, "qty": 1, "rate": montant,
                   "cost_center": _cc(ATELIER_FRAIS_GENERAUX)}
                  for item, montant in lignes],
    })
    pi.insert(ignore_permissions=True)
    pi.submit()
    return pi.name


def _gl_par_centre(voucher, compte):
    """{nom court du centre: débit} des écritures du compte sur la pièce."""
    rows = frappe.get_all("GL Entry",
                          filters={"voucher_no": voucher, "account": _acc(compte),
                                   "is_cancelled": 0},
                          fields=["cost_center", "debit"])
    par_centre = {}
    for r in rows:
        nom = r.cost_center.rsplit(" - ", 1)[0]
        par_centre[nom] = round(par_centre.get(nom, 0.0) + float(r.debit), 2)
    return par_centre


def _supprimer_piece(doctype, nom, enfants):
    frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", nom)
    frappe.db.sql("DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no=%s", nom)
    for enfant in enfants:
        frappe.db.sql(f"DELETE FROM `tab{enfant}` WHERE parent=%s", nom)
    frappe.db.sql(f"DELETE FROM `tab{doctype}` WHERE name=%s", nom)


def _supprimer_cles():
    """Every test key (June 2025 on Frais Généraux) — cancelled then deleted,
    so that no real posting ever meets a test key."""
    for nom in frappe.get_all("Cost Center Allocation",
                              filters={"main_cost_center": _cc(ATELIER_FRAIS_GENERAUX),
                                       "valid_from": ["between", [DEBUT, FIN]]},
                              pluck="name"):
        doc = frappe.get_doc("Cost Center Allocation", nom)
        if doc.docstatus == 1:
            doc.cancel()
        frappe.delete_doc("Cost Center Allocation", nom, force=1,
                          ignore_permissions=True)


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
    _supprimer_cles()
    for doctype, nom in (("Item", ITEM), ("Item", ITEM_2), ("Supplier", FOURNISSEUR)):
        if frappe.db.exists(doctype, nom):
            frappe.delete_doc(doctype, nom, force=1, ignore_permissions=True)
    frappe.db.commit()


# ─── Lectures ───

def _ligne_rapport(rows, prefixe, section=SECTION_FRAIS_GENERAUX):
    return next((r for r in rows if r["section"] == section
                 and r["indicateur"].startswith(prefixe)), None)


# ─── Tests ───

def _test_cle_dans_le_grand_livre(results):
    print("\n[1] Une écriture sur Frais Généraux → le Grand Livre porte la clé")
    nom = _ecriture("615", MONTANT_ENTRETIEN, ATELIER_FRAIS_GENERAUX, "ENTRETIEN")
    je = frappe.get_doc("Journal Entry", nom)
    _check(je.docstatus == 1, "l'écriture imputée à Frais Généraux est soumise",
           results)
    _check(je.accounts[0].cost_center == _cc(ATELIER_FRAIS_GENERAUX),
           "la pièce elle-même reste imputée à Frais Généraux (rien à saisir)",
           results)
    gl = _gl_par_centre(nom, "615")
    _check(gl == {"Lait": 450.0, "Cultures - Fourrage": 350.0, "Traction": 200.0},
           f"écritures comptables réparties 450 / 350 / 200 (got {gl})", results)
    _check(ATELIER_FRAIS_GENERAUX not in gl,
           "plus rien au Grand Livre sur Frais Généraux pour cette pièce", results)
    return nom


def _test_facture_achat(results):
    print("\n[2] Le chemin de la comptable : une facture à DEUX lignes, rien à saisir")
    nom = _facture([(_article(ITEM, ITEM_NOM, "616"), MONTANT_FACTURE),
                    (_article(ITEM_2, ITEM_2_NOM, "606"), MONTANT_FACTURE_2)],
                   "FACTURE")
    pi = frappe.get_doc("Purchase Invoice", nom)
    _check(pi.docstatus == 1, "la facture imputée à Frais Généraux est soumise",
           results)
    _check(pi.items[0].expense_account == _acc("616")
           and pi.items[1].expense_account == _acc("606"),
           "chaque ligne garde son compte de charge (616 / 606)", results)
    gl_616 = _gl_par_centre(nom, "616")
    _check(gl_616 == {"Lait": 855.0, "Cultures - Fourrage": 665.0, "Traction": 380.0},
           f"ligne 1 (1 900) répartie 855 / 665 / 380 au Grand Livre (got {gl_616})",
           results)
    gl_606 = _gl_par_centre(nom, "606")
    _check(gl_606 == {"Lait": 45.0, "Cultures - Fourrage": 35.0, "Traction": 20.0},
           f"ligne 2 (100) répartie 45 / 35 / 20 sans saisie supplémentaire "
           f"(got {gl_606})", results)
    return nom


def _test_charge_avant_cle(results):
    print("\n[3] Une charge postée AVANT la clé reste à Frais Généraux")
    nom = _ecriture("606", MONTANT_AVANT_CLE, ATELIER_FRAIS_GENERAUX, "AVANT_CLE",
                    date=DATE_AVANT_CLE)
    gl = _gl_par_centre(nom, "606")
    _check(gl == {ATELIER_FRAIS_GENERAUX: float(MONTANT_AVANT_CLE)},
           f"le Grand Livre garde les {MONTANT_AVANT_CLE} sur Frais Généraux "
           f"(got {gl})", results)
    _check(cle_repartition(_cc(ATELIER_FRAIS_GENERAUX), DATE_AVANT_CLE) is None,
           "aucune clé en vigueur à cette date", results)
    return nom


def _test_changement_de_cle(results):
    print("\n[4] Changer la clé = nouvelle allocation datée")
    _cle(DATE_CLE_B, CLE_B)
    nom = _ecriture("606", MONTANT_APRES_CLE_B, ATELIER_FRAIS_GENERAUX, "APRES_CLE_B",
                    date=DATE_APRES_CLE_B)
    gl = _gl_par_centre(nom, "606")
    _check(gl == {"Lait": float(MONTANT_APRES_CLE_B)},
           f"après le 20/06, 100 % Lait (got {gl})", results)
    cle_a = cle_repartition(_cc(ATELIER_FRAIS_GENERAUX), DATE_ECRITURE)
    _check(cle_a is not None and [(p["atelier"], p["pct"]) for p in cle_a["parts"]]
           == [(a, float(p)) for a, p in CLE_A],
           "au 10/06 la clé A reste celle qui s'applique (historique intact)",
           results)


def _test_lecture_repartitions(results, nom_annulee):
    print("\n[5] repartitions_frais_generaux — clé jointe, par atelier, contrôle GL")
    lecture = repartitions_frais_generaux(DEBUT, FIN)
    charges = lecture["charges"]
    _check(len(charges) == 5,
           f"5 charges FG listées (entretien, 2 lignes de facture, avant clé, "
           f"après clé B) (got {len(charges)})", results)
    _check({c["voucher_type"] for c in charges} == {"Journal Entry", "Purchase Invoice"},
           "écritures ET factures remontent", results)
    _check(all(c["voucher"] != nom_annulee for c in charges),
           "l'écriture annulée n'est pas une charge", results)
    sans_cle = [c for c in charges if not c["cle"]]
    _check(len(sans_cle) == 1 and round(sans_cle[0]["montant"], 2) == MONTANT_AVANT_CLE
           and sans_cle[0]["poste"] == "autres",
           f"la charge d'avant la clé est listée sans part, poste « autres » "
           f"(got {sans_cle})", results)
    _check(lecture["par_atelier"] == PAR_ATELIER_ATTENDU,
           f"par atelier = {PAR_ATELIER_ATTENDU} (got {lecture['par_atelier']})",
           results)
    _check(lecture["par_atelier_postes"].get(ATELIER_LAIT) == POSTES_LAIT_ATTENDUS,
           f"postes du Lait = {POSTES_LAIT_ATTENDUS} "
           f"(got {lecture['par_atelier_postes'].get(ATELIER_LAIT)})", results)
    _check(lecture["total_liste"] == TOTAL_LISTE_ATTENDU
           and lecture["total_reparti"] == REPARTI_ATTENDU
           and lecture["non_reparti"] == NON_REPARTI_ATTENDU,
           f"listé {TOTAL_LISTE_ATTENDU} = réparti {REPARTI_ATTENDU} + non réparti "
           f"{NON_REPARTI_ATTENDU} (got {lecture['total_liste']} / "
           f"{lecture['total_reparti']} / {lecture['non_reparti']})", results)
    _check(lecture["total_fg"] == TOTAL_FG_GL_ATTENDU and lecture["autres"] == 0,
           f"resté à FG au Grand Livre = {TOTAL_FG_GL_ATTENDU}, rien d'autre "
           f"(got {lecture['total_fg']} / {lecture['autres']})", results)
    _check(lecture["controle_gl"] == {"ecart": 0.0, "details": []},
           f"contrôle Grand Livre = clé : aucun écart (got {lecture['controle_gl']})",
           results)
    cles = lecture["cles_en_vigueur"]
    _check(len(cles) == 1 and cles[0]["centre"] == ATELIER_FRAIS_GENERAUX
           and cles[0]["valid_from"] and str(cles[0]["valid_from"]) == DATE_CLE_B,
           f"clé en vigueur au 30/06 = clé B (got {cles})", results)


def _test_charges_lait(results):
    print("\n[6] charges_lait — total = Lait au Grand Livre, quote-part isolée")
    lait = charges_lait(DEBUT, FIN)
    _check(lait["quote_part"] == LAIT_ATTENDU,
           f"quote-part envoyée par la clé = {LAIT_ATTENDU} (got {lait['quote_part']})",
           results)
    _check(lait["direct"] == MONTANT_LAIT_DIRECT and lait["total"] == COUT_LAIT_ATTENDU,
           f"total = direct {MONTANT_LAIT_DIRECT} + quote-part = {COUT_LAIT_ATTENDU} "
           f"(got {lait['direct']} / {lait['total']})", results)
    _check(lait["postes"] == {"ration": 500.0, **POSTES_LAIT_ATTENDUS},
           f"les postes du Lait cumulent direct et clé (got {lait['postes']})",
           results)
    _check((lait["fg_total"], lait["fg_reparti"], lait["fg_non_reparti"])
           == (TOTAL_FG_GL_ATTENDU, REPARTI_ATTENDU, NON_REPARTI_ATTENDU),
           "fg_total / fg_reparti / fg_non_reparti exposés", results)
    seul = charges_lait(DEBUT, FIN, perimetre="LAIT_SEUL")
    _check(seul["quote_part"] == 0 and seul["total"] == MONTANT_LAIT_DIRECT
           and seul["postes"] == {"ration": 500.0, "mecanique": 0.0, "autres": 0.0},
           f"« Lait seul » retire la part de la clé, poste par poste (got {seul})",
           results)


def _test_rapport(results):
    print("\n[7] Le rapport expose la clé, charge par charge, et le contrôle")
    rows = executer_rapport({"periode": "Mois", "date": DATE_RAPPORT})[1]
    _check(any(r["section"] == SECTION_FRAIS_GENERAUX for r in rows),
           f"section « {SECTION_FRAIS_GENERAUX} » présente", results)
    cle = _ligne_rapport(rows, f"Clé {ATELIER_FRAIS_GENERAUX} en vigueur au 30/06/2025")
    _check(cle is not None and "Lait 45 %" in cle["indicateur"]
           and "depuis le 05/06/2025" in cle["indicateur"],
           f"la clé en vigueur à la fin de la période est nommée (got {cle})", results)
    liste = _ligne_rapport(rows, "Total imputé à Frais Généraux")
    _check(liste is not None and liste["valeur"] == 3300.0,
           f"au 15/06 : 3 300 imputés à FG (got {liste})", results)
    reparti = _ligne_rapport(rows, "Réparti par la clé")
    _check(reparti is not None and reparti["valeur"] == 3000.0,
           f"3 000 répartis par la clé (got {reparti})", results)
    part_lait = _ligne_rapport(rows, f"dont part {ATELIER_LAIT}")
    _check(part_lait is not None and part_lait["valeur"] == 1350.0,
           f"part Lait = 1 350 (got {part_lait})", results)
    non_reparti = _ligne_rapport(rows, "Frais généraux non répartis")
    _check(non_reparti is not None and non_reparti["valeur"] == NON_REPARTI_ATTENDU
           and non_reparti["indicator"] == "Orange",
           f"non réparti = {NON_REPARTI_ATTENDU}, orange (got {non_reparti})", results)
    reste = _ligne_rapport(rows, "Total resté à Frais Généraux")
    _check(reste is not None and reste["valeur"] == TOTAL_FG_GL_ATTENDU,
           f"resté à FG (Grand Livre) = {TOTAL_FG_GL_ATTENDU} (got {reste})", results)
    ventilation = _ligne_rapport(rows, "└ Lait 45 % · Cultures - Fourrage 35 % · Traction 20 %")
    _check(ventilation is not None and ventilation["valeur"] is None,
           "la ligne « └ Lait 45 % · … » est là, sans valeur (tiret)", results)
    nue = _ligne_rapport(rows, "└ non répartie")
    _check(nue is not None and nue["indicator"] == "Orange"
           and "02/06/2025" in nue["indicateur"],
           "la charge d'avant la clé est nommée « └ non répartie », orange, datée",
           results)
    controle = _ligne_rapport(rows, "Contrôle — écritures comptables = clé")
    _check(controle is not None and controle["valeur"] == 0 and not controle["indicator"],
           f"contrôle écritures = clé, aucun écart (got {controle})", results)
    quote_part = _ligne_rapport(rows, "Quote-part", section="Coût du Lait (détail)")
    _check(quote_part is not None and quote_part["valeur"] == 1350.0
           and "clé de répartition" in quote_part["indicateur"],
           f"le détail du coût du lait isole la part envoyée par la clé "
           f"(got {quote_part})", results)


def _test_mode_strict(results):
    print("\n[8] Mode strict — ON refuse une charge FG sans clé, OFF avertit")
    _definir_mode_strict(1)
    _attendre_erreur(
        "ERR-FIN-11",
        lambda: _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "STRICT_SANS_CLE",
                          date=DATE_AVANT_CLE, soumettre=False),
        "strict ON : une charge FG à une date sans clé est bloquée", results)
    nom = _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "STRICT_AVEC_CLE",
                    soumettre=False)
    _check(frappe.db.exists("Journal Entry", nom),
           "strict ON : une charge FG à une date couverte par la clé passe", results)
    nom = _ecriture("606", 100, "Lait", "STRICT_LAIT", date=DATE_AVANT_CLE,
                    soumettre=False)
    _check(frappe.db.exists("Journal Entry", nom),
           "strict ON : une charge imputée directement à Lait n'est pas concernée",
           results)
    nom = _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "STRICT_SYSTEME",
                    date=DATE_AVANT_CLE, soumettre=False,
                    flags={"ignore_repartition_fg": True})
    _check(frappe.db.exists("Journal Entry", nom),
           "strict ON : une pièce système (flag ignore_repartition_fg) passe",
           results)
    _definir_mode_strict(0)
    nom = _ecriture("606", 100, ATELIER_FRAIS_GENERAUX, "SOUPLE_SANS_CLE",
                    date=DATE_AVANT_CLE, soumettre=False)
    _check(frappe.db.exists("Journal Entry", nom),
           "strict OFF : une charge FG sans clé passe (avertissement seulement)",
           results)


def _test_cle_en_vigueur(results):
    print("\n[9] cle_en_vigueur — le texte de l'en-tête du formulaire")
    reponse = cle_en_vigueur(COMPANY, DATE_ECRITURE, _cc(ATELIER_FRAIS_GENERAUX))
    _check(reponse["cle"] is not None
           and reponse["cle"]["libelle"] == "Lait 45 % · Cultures - Fourrage 35 % · Traction 20 %"
           and reponse["centre"] == ATELIER_FRAIS_GENERAUX,
           f"au 10/06 : « Lait 45 % · Cultures - Fourrage 35 % · Traction 20 % » "
           f"(got {reponse})", results)
    reponse = cle_en_vigueur(COMPANY, DATE_AVANT_CLE, _cc(ATELIER_FRAIS_GENERAUX))
    _check(reponse["cle"] is None and reponse["strict"] is False,
           "au 02/06 : aucune clé, mode souple", results)


# ─── Runner ───

def run():
    print("\n" + "=" * 70)
    print("  SCRUM-10 — Frais généraux répartis par la clé (Cost Center Allocation)")
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
    _cle(DATE_CLE_A, CLE_A)

    _test_cle_dans_le_grand_livre(results)
    _test_facture_achat(results)
    _test_charge_avant_cle(results)
    _ecriture("601", MONTANT_LAIT_DIRECT, "Lait", "LAIT_DIRECT")
    nom_annulee = _ecriture("606", 777, ATELIER_FRAIS_GENERAUX, "ANNULEE")
    frappe.get_doc("Journal Entry", nom_annulee).cancel()
    frappe.db.commit()
    # The report is read at 15/06 — before key B — so it sees key A only.
    _test_rapport(results)

    _test_changement_de_cle(results)
    frappe.db.commit()
    _test_lecture_repartitions(results, nom_annulee)
    _test_charges_lait(results)
    _test_mode_strict(results)
    _test_cle_en_vigueur(results)

    print("\n" + "-" * 70)
    print(f"  {results['pass']} OK / {results['fail']} FAIL")
    print("-" * 70)
    return results
