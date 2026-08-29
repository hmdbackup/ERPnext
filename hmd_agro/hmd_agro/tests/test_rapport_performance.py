"""
Tests — Rapport Performance (Phase 4).

Covers:
  1. Structure : colonnes typées (section / indicateur / valeur / unite),
     les 5 sections présentes, `valeur` numérique (export Excel propre)
  2. Bornes de période : Mois = mois calendaire, Semaine = ISO Lun-Dim
  3. Valeurs : Production Totale (Traite) et Lait Vendu (Bilan Lait
     Journalier) en delta par rapport à la baseline (les totaux cheptel
     incluent les données réelles de la base)
  4. FIN-S95 — garde-fou « période incomplète » : mars 2019 est saisi tous
     les jours (aucun avertissement, couleurs conservées) tandis que janvier
     2019 ne l'est que 2 jours (avertissement + couleurs éteintes)
  5. FIN-S96 — imputation du coût mécanique (heures, DT, DT/L) en VUE
     ANALYTIQUE : elle ne doit jamais gonfler le coût complet du litre
  6. Période « Année » = Year to Date (réunion 26/08/2026) et
     `previous_period_bounds` : veille / S-1 / Q-1 / M-1 / A-1 même période,
     période en cours comparée à jours écoulés égaux (label « même nombre de jours »)
  7. Colonnes comparatives (maquettes 24/08 + 26/08) : `precedent` libellé
     selon la période, `ecart_pct` signé sur un couple connu, vide sans base
     de comparaison, lignes INFO / Avertissement sans comparatif
  8. Section « Frais Généraux — répartition par atelier » présente

Fixtures isolées sur mars 2019 (période passée, avant tout backfill SLE —
les coûts alimentaires y valent honnêtement 0, ce que le rapport assume) ;
le comparatif s'appuie sur deux écritures de novembre / décembre 2025
(exercice ACTIF, aucune écriture réelle en 2025 — préfixe ZZTEST_PERF).

Run: bench --site <site> execute hmd_agro.hmd_agro.tests.test_rapport_performance.run
"""
import traceback

import frappe
from frappe.utils import getdate, today

from hmd_agro.hmd_agro.report.rapport_performance.rapport_performance import (
    LABELS_PRECEDENT, SECTION_FRAIS_GENERAUX, execute, period_bounds,
    previous_period_bounds,
)
from hmd_agro.hmd_agro.report.rapport_periodique.rapport_periodique import (
    INDICATEURS_SENSIBLES_LAIT, couverture_lait,
)
from hmd_agro.hmd_agro.utils.maintenance_utils import cout_utilisation

PREFIX = "TEST-PERF-"
COMPANY = "hmd-agro"
PREFIXE_JE = "ZZTEST_PERF"
MOIS_DATE = "2019-03-15"
SEM_DATE = "2019-03-06"        # mercredi → semaine ISO 04/03 - 10/03
COLONNES_ATTENDUES = ["section", "indicateur", "valeur", "precedent",
                      "ecart_pct", "unite"]
# Comparatif : main-d'œuvre 100 en novembre 2025, 150 en décembre → +50 %.
COMP_DATE_PREC = "2025-11-10"
COMP_DATE = "2025-12-10"
COMP_DATE_RAPPORT = "2025-12-15"
COMP_MO_PREC = 100
COMP_MO = 150
COMP_ECART_ATTENDU = 50.0
# Un jour n'est « saisi » que s'il porte une Traite ET un Bilan Lait Journalier
# renseigné (revue reporting : « saisie quotidienne obligatoire : traite et
# bilan journalier complet »). Mars 2019 porte donc les DEUX sur ses 31 jours —
# auparavant trois bilans suffisaient parce que l'un OU l'autre comptait, ce
# qui laissait passer un mois « complet » sans aucune ventilation du lait.
BLJ_DATES = [f"2019-03-{jour:02d}" for jour in range(1, 32)]
# Janvier 2019 : lait saisi 2 jours sur 31 — le trou de saisie à détecter.
TROU_DATE = "2019-01-15"
TROU_TRAITE_DATES = ["2019-01-02", "2019-01-03"]
# Les mêmes deux jours portent aussi leur bilan : sans lui la couverture
# tomberait à 0/31 et le test ne vérifierait plus un trou PARTIEL.
TROU_BLJ_DATES = list(TROU_TRAITE_DATES)

_created = []


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _find(rows, section, label_starts):
    return next((r for r in rows if r["section"] == section
                 and r["indicateur"].startswith(label_starts)), None)


# ─── Fixtures ───

def _animal(suffix):
    doc = frappe.get_doc({
        "doctype": "Animal", "identification_tn": f"{PREFIX}{suffix}",
        "nom_metier": f"{PREFIX}{suffix}", "categorie": "VACHE", "sexe": "F",
        "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION",
        "etat_gestation": "VIDE", "date_naissance": "2015-01-01",
    })
    doc.name = f"{PREFIX}{suffix}"
    doc.db_insert()
    _created.append(("Animal", doc.name))
    # Velage antérieur à la période pour que la reconstruction la voie VACHE
    vel = frappe.get_doc({
        "doctype": "Velage", "animal": doc.name,
        "date_velage": "2018-06-01", "type_velage": "FACILE",
        "nombre_veaux": "1", "sexe_veau1": "F", "vivant_veau1": 0,
    })
    vel.flags.ignore_validate = True
    vel.flags.ignore_links = True
    vel.db_insert()
    _created.append(("Velage", vel.name))
    return doc.name


def _traite(animal_name, date, litres):
    doc = frappe.get_doc({
        "doctype": "Traite", "animal": animal_name, "date_traite": date,
        "quantite_litres": litres, "type_traite": "MATIN",
    })
    doc.db_insert()
    _created.append(("Traite", doc.name))


def _seed_blj(dates=None):
    """One BLJ per date (100 L produits, 100 L vendus). A date already carrying
    a real BLJ is skipped — the expected delta counts only what we created.

    `production_totale_saisie` est OBLIGATOIRE pour que le jour compte comme
    saisi : un bilan créé puis laissé vide ne prouve rien, et `couverture_lait`
    l'ignore délibérément.
    """
    created_days = 0
    for d in (dates if dates is not None else BLJ_DATES):
        if frappe.db.exists("Bilan Lait Journalier", {"date": d}):
            continue
        doc = frappe.get_doc({
            "doctype": "Bilan Lait Journalier", "date": d,
            "production_totale_saisie": 100, "lait_vendu": 100,
        })
        doc.insert(ignore_permissions=True)
        _created.append(("Bilan Lait Journalier", doc.name))
        created_days += 1
    return created_days


def _acc(numero):
    return frappe.db.get_value("Account", {"account_number": numero,
                                           "company": COMPANY}, "name")


def _cc(nom):
    return f"{nom} - {frappe.db.get_value('Company', COMPANY, 'abbr')}"


def _charge(compte, montant, date, suffixe):
    """Une charge au compte `compte`, atelier Lait, datée `date` — le support
    du comparatif M / M-1 (même pattern que test_ventilation_atelier)."""
    cc = _cc("Lait")
    je = frappe.get_doc({
        "doctype": "Journal Entry", "company": COMPANY,
        "voucher_type": "Journal Entry", "posting_date": date,
        "user_remark": f"{PREFIXE_JE}_{suffixe}",
        "accounts": [
            {"account": _acc(compte), "debit_in_account_currency": montant,
             "cost_center": cc},
            {"account": _acc("54"), "credit_in_account_currency": montant,
             "cost_center": cc},
        ],
    })
    je.insert(ignore_permissions=True)
    je.submit()
    return je.name


def _cleanup_ecritures():
    for je in frappe.get_all("Journal Entry",
                             filters={"user_remark": ["like", f"%{PREFIXE_JE}%"]},
                             pluck="name"):
        frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", je)
        frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent=%s", je)
        frappe.db.sql("DELETE FROM `tabJournal Entry` WHERE name=%s", je)


def _cleanup():
    for dt, name in reversed(_created):
        frappe.db.sql(f"DELETE FROM `tab{dt}` WHERE name=%s", name)
    _created.clear()
    frappe.db.sql("DELETE FROM `tabTraite` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabVelage` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE name LIKE %s", f"{PREFIX}%")
    _cleanup_ecritures()
    frappe.db.commit()


# ─── Tests ───

def test_structure(results):
    print("  ----  Structure — colonnes typées + sections")
    cols, rows = execute({"periode": "Mois", "date": MOIS_DATE})
    names = [c["fieldname"] for c in cols]
    _check(names == COLONNES_ATTENDUES,
           f"Colonnes = {'/'.join(COLONNES_ATTENDUES)} (got {names})", results)
    for col in (cols[2], cols[3]):
        _check(col["fieldtype"] == "Float" and col.get("precision") == 2,
               f"Colonne {col['fieldname']} = Float precision 2 (export Excel propre)",
               results)
    _check(cols[3]["label"] == LABELS_PRECEDENT["Mois"] == "M-1",
           f"Colonne précédent libellée « M-1 » pour un mois (got {cols[3]['label']})",
           results)
    _check(cols[4]["fieldtype"] == "Percent" and cols[4]["label"] == "Écart %",
           "Colonne « Écart % » en Percent", results)
    sections = {r["section"] for r in rows}
    for s in ("Cheptel", "Production", "Alimentation", "Charges",
              "Charges par Atelier", SECTION_FRAIS_GENERAUX,
              "Coût du Lait (détail)", "Coûts Unitaires"):
        _check(s in sections, f"Section « {s} » présente", results)
    non_numeric = [r for r in rows for champ in ("valeur", "precedent", "ecart_pct")
                   if r[champ] is not None
                   and not isinstance(r[champ], (int, float))]
    _check(not non_numeric,
           f"Toutes les valeurs sont numériques ({len(non_numeric)} non conformes)",
           results)


def test_period_bounds(results):
    print("  ----  Bornes de période — Mois calendaire / Semaine ISO")
    debut, fin = period_bounds("Mois", getdate(MOIS_DATE))
    _check((str(debut), str(fin)) == ("2019-03-01", "2019-03-31"),
           f"Mois : 2019-03-01 → 2019-03-31 (got {debut} → {fin})", results)
    debut, fin = period_bounds("Semaine", getdate(SEM_DATE))
    _check((str(debut), str(fin)) == ("2019-03-04", "2019-03-10"),
           f"Semaine ISO : lundi 04/03 → dimanche 10/03 (got {debut} → {fin})",
           results)
    debut, fin = period_bounds("Année", getdate(MOIS_DATE))
    _check((str(debut), str(fin)) == ("2019-01-01", "2019-03-15"),
           f"Année = Year to Date : 01/01 → date choisie (got {debut} → {fin})",
           results)


def _bornes_prec(periode, debut, fin):
    d, f = previous_period_bounds(periode, getdate(debut), getdate(fin))
    return str(d), str(f)


def test_previous_period_bounds(results):
    print("  ----  Période précédente — veille / S-1 / Q-1 / M-1 / A-1")
    cas = (
        ("Jour", "2019-03-01", "2019-03-01", ("2019-02-28", "2019-02-28"),
         "Jour → la veille, même à cheval sur le mois"),
        ("Semaine", "2019-03-04", "2019-03-10", ("2019-02-25", "2019-03-03"),
         "Semaine → la semaine ISO précédente"),
        ("Quinzaine", "2019-03-16", "2019-03-31", ("2019-03-01", "2019-03-15"),
         "Quinzaine 16-31 → la 1-15 du même mois"),
        ("Quinzaine", "2019-03-01", "2019-03-15", ("2019-02-16", "2019-02-28"),
         "Quinzaine 1-15 → la 16-fin du mois précédent"),
        ("Mois", "2019-03-01", "2019-03-31", ("2019-02-01", "2019-02-28"),
         "Mois → le mois précédent entier"),
        ("Année", "2019-01-01", "2019-03-15", ("2018-01-01", "2018-03-15"),
         "Année → le même Year to Date un an plus tôt"),
        ("Année", "2024-01-01", "2024-02-29", ("2023-01-01", "2023-02-28"),
         "Année bissextile : le 29/02 retombe sur le 28/02"),
        # Période en cours (tronquée à aujourd'hui) : même nombre de jours écoulés.
        ("Mois", "2019-03-01", "2019-03-10", ("2019-02-01", "2019-02-10"),
         "Mois en cours (10 j) → les 10 premiers jours de M-1"),
        ("Quinzaine", "2019-03-16", "2019-03-20", ("2019-03-01", "2019-03-05"),
         "Quinzaine en cours (5 j) → les 5 premiers jours de Q-1"),
        ("Semaine", "2019-03-04", "2019-03-05", ("2019-02-25", "2019-02-26"),
         "Semaine en cours (2 j) → lundi-mardi de S-1"),
        ("Mois", "2019-04-01", "2019-04-30", ("2019-03-01", "2019-03-31"),
         "Mois entier de 30 j → M-1 entier (31 j), pas tronqué"),
    )
    for periode, debut, fin, attendu, msg in cas:
        obtenu = _bornes_prec(periode, debut, fin)
        _check(obtenu == attendu, f"{msg} (got {obtenu})", results)

    # The label follows: a month in progress announces « même nombre de jours ».
    aujourdhui = getdate(today())
    cols, _rows = execute({"periode": "Mois", "date": str(aujourdhui)})
    tronque = aujourdhui < period_bounds("Mois", aujourdhui)[1]
    attendu = "M-1" + (" (même nombre de jours)" if tronque else "")
    _check(cols[3]["label"] == attendu,
           f"Mois en cours : colonne précédent libellée « {attendu} » "
           f"(got {cols[3]['label']})", results)


def test_valeurs_mois(results, base_prod, base_vendu, blj_days):
    print("  ----  Valeurs mensuelles — deltas depuis la baseline")
    _, rows = execute({"periode": "Mois", "date": MOIS_DATE})
    prod = _find(rows, "Production", "Production Totale")["valeur"]
    # 2 vaches × 10 L × 31 jours = 620 L
    _check(round(prod - base_prod, 1) == 620,
           f"Δ Production Totale = 620 L (got {round(prod - base_prod, 1)})",
           results)
    vendu = _find(rows, "Production", "Lait Vendu")["valeur"]
    attendu = 100 * blj_days
    _check(round(vendu - base_vendu, 1) == attendu,
           f"Δ Lait Vendu = {attendu} L (got {round(vendu - base_vendu, 1)})",
           results)
    lc = _find(rows, "Alimentation", "L/C")
    _check(lc is not None and "cible" in lc["indicateur"],
           "Ligne L/C présente avec la cible dans le libellé", results)
    iofc = _find(rows, "Coûts Unitaires", "IOFC (Income Over Feed Cost) / Vache")
    _check(iofc is not None, "Ligne IOFC (Income Over Feed Cost)/VL/j présente",
           results)
    hors = _find(rows, "Coûts Unitaires", "Coût du Litre hors Amortissement")
    _check(hors is not None, "Ligne Coût du Litre hors Amortissement présente",
           results)


def test_valeurs_semaine(results, base_prod_sem):
    print("  ----  Valeurs hebdomadaires — production de la semaine ISO")
    _, rows = execute({"periode": "Semaine", "date": SEM_DATE})
    prod = _find(rows, "Production", "Production Totale")["valeur"]
    # 2 vaches × 10 L × 7 jours = 140 L
    _check(round(prod - base_prod_sem, 1) == 140,
           f"Δ Production semaine = 140 L (got {round(prod - base_prod_sem, 1)})",
           results)


def test_couverture_complete(results):
    """Mars 2019 : 31 jours de traite sur 31 → aucun avertissement, et la
    coloration des indicateurs reste ACTIVE (sinon on perd les vraies alertes)."""
    print("  ----  Garde-fou — période complète : pas d'alarme parasite")
    couv = couverture_lait("2019-03-01", "2019-03-31")
    _check(couv["jours_saisis"] == 31 and couv["complete"],
           f"Couverture 31/31 et complete=True (got {couv['jours_saisis']}/31)",
           results)
    _, rows = execute({"periode": "Mois", "date": MOIS_DATE})
    _check(not any(r["section"] == "Avertissement" for r in rows),
           "Aucune ligne « Avertissement »", results)
    ligne = _find(rows, "Production", "Couverture des Données (lait)")
    _check(ligne is not None and ligne["valeur"] == 31
           and ligne["unite"] == "jours sur 31",
           f"Ligne « Couverture des Données (lait) » = 31 jours sur 31 "
           f"(got {ligne})", results)


def test_couverture_trouee(results):
    """Janvier 2019 : lait saisi 2 jours sur 31 alors que le reste du rapport
    couvre le mois entier. Le rapport doit le DIRE en tête de tableau et
    éteindre la coloration des ratios faussés — sans masquer une valeur."""
    print("  ----  Garde-fou — période trouée : avertissement + couleurs éteintes")
    couv = couverture_lait("2019-01-01", "2019-01-31")
    _check(couv["jours_saisis"] == 2 and not couv["complete"],
           f"Couverture 2/31 et complete=False (got {couv['jours_saisis']}/31)",
           results)

    _, rows = execute({"periode": "Mois", "date": TROU_DATE})
    _check(rows and rows[0]["section"] == "Avertissement"
           and rows[0]["indicateur"].startswith("⚠"),
           f"Avertissement en TÊTE de tableau "
           f"(got {rows[0]['section'] if rows else None})", results)
    _check(rows and "2 jours sur 31" in (rows[0]["indicateur"] or ""),
           "Le message chiffre le trou (« 2 jours sur 31 »)", results)
    ligne = _find(rows, "Production", "Couverture des Données (lait)")
    _check(ligne is not None and ligne["valeur"] == 2,
           f"Ligne de couverture = 2 jours (got {ligne})", results)

    colores = [r["indicateur"] for r in rows if r.get("indicator")
               and r["indicateur"].startswith(INDICATEURS_SENSIBLES_LAIT)]
    _check(not colores, f"Aucun indicateur lait coloré (restants: {colores})",
           results)
    prod = _find(rows, "Production", "Production Totale")
    _check(prod is not None and prod["valeur"] is not None,
           "Les VALEURS restent affichées (on éteint la couleur, pas le chiffre)",
           results)


def test_cout_mecanique(results):
    """FIN-S96 — heures machine, coût mécanique et coût mécanique/L.

    Contrat central : c'est une VUE ANALYTIQUE. L'amortissement et l'entretien
    sont déjà dans les charges du Grand Livre — le coût mécanique ne doit donc
    entrer NI dans « Charges Totales » NI dans « Coût Complet / L ». Le libellé
    doit le rappeler à l'écran pour qu'on ne l'additionne pas à la main.
    """
    print("  ----  Coût mécanique — imputation analytique (FIN-S96)")
    _, rows = execute({"periode": "Mois", "date": MOIS_DATE})

    heures = _find(rows, "Charges", "Heures d'Équipement")
    _check(heures is not None and heures["unite"] == "h",
           f"Ligne « Heures d'Équipement » en h (got {heures})", results)
    meca = _find(rows, "Charges", "Coût d'Utilisation Mécanique")
    _check(meca is not None and meca["unite"] == "DT",
           f"Ligne « Coût d'Utilisation Mécanique » en DT (got {meca})", results)
    _check(meca is not None and "analytique" in meca["indicateur"],
           "Le libellé annonce la vue analytique (anti double-comptage)", results)
    meca_l = _find(rows, "Coûts Unitaires", "Coût Mécanique / L")
    _check(meca_l is not None and meca_l["unite"] == "DT/L",
           f"Ligne « Coût Mécanique / L » en DT/L (got {meca_l})", results)
    _check(meca_l is not None and "non additionnable" in meca_l["indicateur"],
           "Le libellé du coût unitaire interdit l'addition au coût complet",
           results)

    # Le coût complet reste STRICTEMENT charges GL / litres : le mécanique
    # n'y entre pas. On le revérifie arithmétiquement.
    charges = (_find(rows, "Charges", "Charges Totales") or {}).get("valeur") or 0
    prod = (_find(rows, "Production", "Production Totale") or {}).get("valeur") or 0
    complet = (_find(rows, "Coûts Unitaires", "Coût Complet / L")
               or {}).get("valeur") or 0
    attendu = round(charges / prod, 3) if prod else 0
    _check(abs(complet - attendu) < 0.005,
           f"Coût Complet / L = charges GL / litres ({complet} vs {attendu}) — "
           "le coût mécanique n'est pas ajouté", results)

    # Lecture source : sans saisie (ou sans le DocType), zéro honnête.
    lecture = cout_utilisation("2019-03-01", "2019-03-31")
    _check(set(lecture) == {"total", "heures", "par_atelier", "par_equipement"},
           f"cout_utilisation retourne la structure attendue ({sorted(lecture)})",
           results)
    _check(lecture["total"] == 0 and lecture["heures"] == 0,
           "Période sans saisie → 0 honnête (posture gl_sums)", results)


def test_periode_future(results):
    print("  ----  Période future — ligne INFO, pas de faux zéros")
    _, rows = execute({"periode": "Mois", "date": "2099-01-15"})
    _check(len(rows) == 1 and rows[0]["section"] == "INFO",
           "Période future → une seule ligne INFO", results)
    _check(rows[0]["precedent"] is None and rows[0]["ecart_pct"] is None,
           "La ligne INFO ne porte pas de comparatif", results)


def test_comparatif(results):
    """Décembre 2025 contre novembre 2025 : main-d'œuvre 150 vs 100 → +50 %.
    Le reste des charges vaut 0 des deux côtés → pas de base, écart vide."""
    print("  ----  Colonnes comparatives — M-1 et Écart % sur un couple connu")
    _, rows = execute({"periode": "Mois", "date": COMP_DATE_RAPPORT})
    mo = _find(rows, "Charges", "Main d'Œuvre (64x)")
    _check(mo is not None and mo["valeur"] == COMP_MO and mo["precedent"] == COMP_MO_PREC,
           f"Main d'Œuvre : valeur {COMP_MO}, M-1 {COMP_MO_PREC} (got {mo})", results)
    _check(mo is not None and mo["ecart_pct"] == COMP_ECART_ATTENDU,
           f"Écart % = +{COMP_ECART_ATTENDU} (got {mo and mo['ecart_pct']})", results)
    entretien = _find(rows, "Charges", "Entretien & Réparations (615)")
    _check(entretien is not None and entretien["ecart_pct"] is None,
           "Précédent nul → Écart % vide, jamais un 0 inventé", results)
    # Décembre 2025 n'a aucun lait saisi : l'avertissement est en tête, sans
    # comparatif, et les ratios lait perdent aussi leur Δ % (base tronquée).
    _check(rows[0]["section"] == "Avertissement" and rows[0]["precedent"] is None
           and rows[0]["ecart_pct"] is None,
           "La ligne Avertissement est en tête, sans comparatif", results)
    sensibles = [r for r in rows if r["indicateur"].startswith(INDICATEURS_SENSIBLES_LAIT)]
    _check(sensibles and all(r["precedent"] is None and r["ecart_pct"] is None
                             for r in sensibles),
           "Période trouée → les ratios lait n'ont ni précédent ni Écart %",
           results)
    cols, rows = execute({"periode": "Année", "date": COMP_DATE_RAPPORT})
    _check(cols[3]["label"] == LABELS_PRECEDENT["Année"],
           f"Année : colonne précédent = « {LABELS_PRECEDENT['Année']} »", results)
    mo = _find(rows, "Charges", "Main d'Œuvre (64x)")
    _check(mo is not None and mo["valeur"] >= COMP_MO + COMP_MO_PREC,
           f"Année = Year to Date : la main-d'œuvre cumule nov. + déc. (got {mo})",
           results)


# ─── Runner ───

def run():
    print("\n" + "=" * 70)
    print("  RAPPORT PERFORMANCE — TESTS")
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

    # Baselines avant fixtures (les totaux incluent les données réelles)
    _, base_rows = execute({"periode": "Mois", "date": MOIS_DATE})
    base_prod = (_find(base_rows, "Production", "Production Totale")
                 or {}).get("valeur", 0)
    base_vendu = (_find(base_rows, "Production", "Lait Vendu")
                  or {}).get("valeur", 0)
    _, base_sem = execute({"periode": "Semaine", "date": SEM_DATE})
    base_prod_sem = (_find(base_sem, "Production", "Production Totale")
                     or {}).get("valeur", 0)

    cows = [_animal(f"C{i}") for i in (1, 2)]
    for day in range(1, 32):
        for c in cows:
            _traite(c, f"2019-03-{day:02d}", 10)
    # Janvier 2019 volontairement troué : 2 jours de lait sur 31.
    for d in TROU_TRAITE_DATES:
        _traite(cows[0], d, 10)
    blj_days = _seed_blj()
    _seed_blj(TROU_BLJ_DATES)
    # Comparatif M / M-1 : deux écritures de main-d'œuvre, novembre et décembre 2025.
    _charge("640", COMP_MO_PREC, COMP_DATE_PREC, "MO_PREC")
    _charge("640", COMP_MO, COMP_DATE, "MO")
    frappe.db.commit()

    test_structure(results)
    test_period_bounds(results)
    test_previous_period_bounds(results)
    test_valeurs_mois(results, base_prod, base_vendu, blj_days)
    test_valeurs_semaine(results, base_prod_sem)
    test_couverture_complete(results)
    test_couverture_trouee(results)
    test_cout_mecanique(results)
    test_periode_future(results)
    test_comparatif(results)

    _cleanup()

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} "
          f"passés, {results['fail']} échoués")
    print("=" * 70)
    return results
