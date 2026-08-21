"""
SCRUM-9 — tests de la section Production du Rapport Périodique.

Trois défauts réels sont verrouillés ici, chacun invisible à l'œil nu :

  1. **La colonne morte.** « Commercialisé (L) » était déclarée à l'écran puis
     figée à vide sur chaque ligne — affichée à l'utilisateur, jamais remplie.
     Trois des quatre postes demandés (auto-consommation, lait veau, écart)
     n'avaient même pas de colonne, alors que le Bilan Lait Journalier porte
     les quatre au jour près.
  2. **Le dénominateur gonflé.** Les vaches étaient comptées sur TOUS les jours
     du mois, jours à venir compris. Plus on ouvrait le rapport tôt dans le
     mois, plus la moyenne par vache paraissait basse.
  3. **L'effectif ambigu.** Le total affichait l'effectif du DERNIER jour et
     l'appelait « effectif lactant », sans rien dire du choix. Sur un troupeau
     qui vêle et tarit, ce n'est pas l'effectif moyen — et la revue reporting a
     tranché pour la moyenne.

Le piège que le test n°4 protège : un jour qui porte une Traite mais AUCUN
bilan doit laisser la ventilation VIDE, jamais à 0. Écrire « 0 L
commercialisé » là où on ne sait rien est un mensonge silencieux, et il se
propage au total.

Fixtures isolées sur AVRIL 2025, préfixe ZZTEST_PROD — mois vierge de toute
Traite et de tout Bilan Lait Journalier sur le site réel, ce qui rend les
totaux absolus (on teste des égalités, pas des « au moins »).

Run: bench --site hmd.agro execute \
        hmd_agro.hmd_agro.tests.test_rapport_production.run
"""
import traceback

import frappe
from frappe.utils import getdate, today

from hmd_agro.hmd_agro.report.rapport_periodique.rapport_periodique import (
    couverture_lait, execute,
)

PREFIXE = "ZZTEST_PROD"

MOIS = "2025-04-15"                  # avril 2025 → 30 jours
NB_JOURS = 30
MOIS_SANS_TRAITE = "2025-10-15"      # vierge, et sans fixture

# 2 vaches lactantes + 1 tarie → VL = 2, VP = 3 tous les jours du mois.
NB_LACTANTES = 2
NB_PRESENTES = 3
LITRES_PAR_TRAITE = 10
# Un seul jour porte un bilan : le 5. Les 29 autres ont une traite sans bilan,
# c'est exactement le cas qui doit rester VIDE.
JOUR_AVEC_BILAN = 5
JOUR_SANS_BILAN = 6
VENDU = 300.0
CONSO_INTERNE = 20.0
LAIT_VEAU = 15.0
PRODUCTION_SAISIE = 340.0            # écart attendu = 340 − 335 = 5,0

_cree = []


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _cleanup():
    for dt, nom in reversed(_cree):
        frappe.db.sql(f"DELETE FROM `tab{dt}` WHERE name=%s", nom)
    _cree.clear()
    for dt in ("Traite", "Lactation", "Velage"):
        frappe.db.sql(f"DELETE FROM `tab{dt}` WHERE animal LIKE %s", f"{PREFIXE}%")
    frappe.db.sql("DELETE FROM `tabBilan Lait Journalier` WHERE `date` "
                  "BETWEEN '2025-04-01' AND '2025-04-30'")
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE name LIKE %s", f"{PREFIXE}%")
    frappe.db.commit()


# ─── Fixtures ───

def _vache(suffixe, tarie=False):
    """Une vache présente sur avril 2025, lactante ou tarie.

    L'état se RECONSTRUIT depuis les événements (règle du projet : jamais
    depuis Animal.etat_*), d'où le Vêlage — qui promeut Génisse → Vache — et
    la Lactation, dont la date de tarissement décide lactante ou tarie.
    """
    animal = frappe.get_doc({
        "doctype": "Animal", "identification_tn": f"{PREFIXE}{suffixe}",
        "nom_metier": f"{PREFIXE}{suffixe}", "categorie": "VACHE", "sexe": "F",
        "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION",
        "etat_gestation": "VIDE", "date_naissance": "2020-01-01",
    })
    animal.name = f"{PREFIXE}{suffixe}"
    animal.db_insert()
    _cree.append(("Animal", animal.name))

    velage = frappe.get_doc({
        "doctype": "Velage", "animal": animal.name,
        "date_velage": "2024-06-01", "type_velage": "FACILE",
        "nombre_veaux": "1", "sexe_veau1": "F", "vivant_veau1": 0,
    })
    velage.flags.ignore_validate = True
    velage.flags.ignore_links = True
    velage.db_insert()
    _cree.append(("Velage", velage.name))

    lactation = frappe.get_doc({
        "doctype": "Lactation", "animal": animal.name,
        "date_debut": "2024-06-01",
        "statut": "TARIE" if tarie else "EN_COURS",
        # Tarie AVANT la période : la reconstruction la classe « Vaches - Tarie »
        # sur tout avril 2025, donc présente mais hors du dénominateur VL.
        "date_tarissement": "2025-01-15" if tarie else None,
    })
    lactation.flags.ignore_validate = True
    lactation.flags.ignore_links = True
    lactation.db_insert()
    _cree.append(("Lactation", lactation.name))
    return animal.name


def _traite(animal, jour, litres=LITRES_PAR_TRAITE):
    doc = frappe.get_doc({
        "doctype": "Traite", "animal": animal,
        "date_traite": f"2025-04-{jour:02d}", "quantite_litres": litres,
        "type_traite": "MATIN",
    })
    doc.db_insert()
    _cree.append(("Traite", doc.name))


def _bilan(jour):
    doc = frappe.get_doc({
        "doctype": "Bilan Lait Journalier", "date": f"2025-04-{jour:02d}",
        "production_totale_saisie": PRODUCTION_SAISIE, "lait_vendu": VENDU,
        "consommation_interne": CONSO_INTERNE, "lait_veau": LAIT_VEAU,
    })
    doc.insert(ignore_permissions=True)
    _cree.append(("Bilan Lait Journalier", doc.name))


# ─── Lectures ───

def _production(date=MOIS):
    colonnes, lignes = execute({"date": date, "section": "Production"})[:2]
    return colonnes, lignes


def _jour(lignes, numero):
    return next((l for l in lignes if l.get("jour") == numero), None)


def _total(lignes):
    return next((l for l in lignes
                 if str(l.get("jour", "")).startswith("Total")), None)


# ─── Tests ───

def _test_structure(results):
    print("\n[1] Structure — les quatre postes de ventilation existent")
    colonnes, _ = _production()
    noms = [c["fieldname"] for c in colonnes]
    attendus = ["jour", "nb_lactantes", "nb_presentes", "production", "moyenne",
                "moyenne_vp", "taux_tb", "taux_tp", "commercialise",
                "auto_consommation", "lait_veau", "ecart"]
    _check(noms == attendus, f"les 12 colonnes attendues, dans l'ordre "
                             f"(got {noms})", results)
    libelles = {c["fieldname"]: c["label"] for c in colonnes}
    # Défaut 3 — deux écrans affichaient « production par vache » à un facteur
    # 30 l'un de l'autre sans rien pour les distinguer. L'unité est au libellé.
    _check("L/j" in libelles["moyenne"] and "L/j" in libelles["moyenne_vp"],
           "les moyennes annoncent leur unité (L/j) dans le libellé", results)


def _test_ventilation_quotidienne(results):
    print("\n[2] La ventilation quotidienne est réellement remplie")
    _, lignes = _production()
    jour = _jour(lignes, JOUR_AVEC_BILAN)
    _check(jour is not None and jour["commercialise"] == VENDU,
           f"« Commercialisé » vaut {VENDU} (got "
           f"{jour['commercialise'] if jour else None}) — la colonne n'est "
           f"plus morte", results)
    _check(jour is not None and jour["auto_consommation"] == CONSO_INTERNE,
           f"« Auto-conso » vaut {CONSO_INTERNE}", results)
    _check(jour is not None and jour["lait_veau"] == LAIT_VEAU,
           f"« Lait Veau » vaut {LAIT_VEAU}", results)
    ecart_attendu = round(PRODUCTION_SAISIE - (VENDU + CONSO_INTERNE + LAIT_VEAU), 1)
    _check(jour is not None and jour["ecart"] == ecart_attendu,
           f"« Écart » vaut {ecart_attendu} (production saisie − affecté)",
           results)


def _test_jour_sans_bilan_reste_vide(results):
    print("\n[3] Traite sans bilan → cases VIDES, jamais 0")
    _, lignes = _production()
    jour = _jour(lignes, JOUR_SANS_BILAN)
    _check(jour is not None and jour["production"] > 0,
           "le jour porte bien une production (la traite est là)", results)
    vides = all(jour[cle] is None for cle in
                ("commercialise", "auto_consommation", "lait_veau", "ecart"))
    _check(vides, "les quatre postes de ventilation restent None — écrire 0 "
                  "affirmerait qu'on a vendu zéro litre alors qu'on ne sait rien",
           results)


def _test_total_ventilation(results):
    print("\n[4] Le total ne somme que les jours renseignés")
    _, lignes = _production()
    total = _total(lignes)
    _check(total is not None and total["commercialise"] == VENDU,
           f"total commercialisé = {VENDU} (un seul jour renseigné) — les "
           f"cases vides ne sont pas comptées pour zéro", results)
    prod_attendue = round(NB_LACTANTES * LITRES_PAR_TRAITE * NB_JOURS, 1)
    _check(total is not None and total["production"] == prod_attendue,
           f"production totale = {prod_attendue} (got "
           f"{total['production'] if total else None})", results)


def _test_effectif_moyen_et_deux_denominateurs(results):
    print("\n[5] Effectif MOYEN, et les deux dénominateurs VL / VP")
    _, lignes = _production()
    jour = _jour(lignes, JOUR_AVEC_BILAN)
    _check(jour is not None and jour["nb_lactantes"] == NB_LACTANTES,
           f"VL du jour = {NB_LACTANTES} (got "
           f"{jour['nb_lactantes'] if jour else None})", results)
    _check(jour is not None and jour["nb_presentes"] == NB_PRESENTES,
           f"VP du jour = {NB_PRESENTES} — la tarie est présente mais pas "
           f"lactante (got {jour['nb_presentes'] if jour else None})", results)

    total = _total(lignes)
    _check(total is not None and total["nb_lactantes"] == NB_LACTANTES,
           "le total porte l'effectif MOYEN de la période", results)
    _check(total is not None and "moy" in str(total["jour"]),
           f"et le libellé du total dit que c'est une moyenne "
           f"(got « {total['jour'] if total else None} »)", results)

    # Les deux moyennes diffèrent dès qu'une vache est tarie : c'est tout
    # l'intérêt d'afficher les deux plutôt qu'un seul chiffre ambigu.
    attendue_vl = round(NB_LACTANTES * LITRES_PAR_TRAITE / NB_LACTANTES, 1)
    attendue_vp = round(NB_LACTANTES * LITRES_PAR_TRAITE / NB_PRESENTES, 1)
    _check(total is not None and total["moyenne"] == attendue_vl,
           f"Moy/VL = {attendue_vl} L/VL/j", results)
    _check(total is not None and total["moyenne_vp"] == attendue_vp,
           f"Moy/VP = {attendue_vp} L/VP/j (got "
           f"{total['moyenne_vp'] if total else None})", results)


def _test_mois_en_cours_ne_gonfle_pas(results):
    print("\n[6] Le mois en cours ne compte pas les jours à venir")
    aujourdhui = getdate(today())
    _, lignes = _production(str(aujourdhui))
    apres = [l for l in lignes if isinstance(l.get("jour"), int)
             and l["jour"] > aujourdhui.day]
    if not apres:
        _check(True, "dernier jour du mois : aucun jour à venir à vérifier",
               results)
        return
    _check(all(l["production"] is None for l in apres),
           "les jours à venir n'affichent aucune production", results)
    _check(all(l["nb_lactantes"] is None for l in apres),
           "et n'apportent aucune vache au dénominateur — sans quoi la moyenne "
           "par vache baissait mécaniquement en début de mois", results)


def _test_mois_sans_traite(results):
    print("\n[7] Un mois sans aucune traite → zéro, pas une erreur")
    _, lignes = _production(MOIS_SANS_TRAITE)
    total = _total(lignes)
    _check(total is not None, "le tableau se construit quand même", results)
    _check(total is not None and total["production"] == 0,
           f"production totale = 0 (got "
           f"{total['production'] if total else None})", results)
    _check(total is not None and total["commercialise"] is None,
           "et « commercialisé » reste vide plutôt que 0 : aucun bilan n'a été "
           "saisi, ce n'est pas la même chose que zéro litre vendu", results)


def _test_couverture_exige_les_deux(results):
    print("\n[8] Un jour n'est « saisi » que si traite ET bilan sont là")
    couv = couverture_lait("2025-04-01", "2025-04-30")
    _check(couv["jours_saisis"] == 1,
           f"1 seul jour sur 30 porte les deux saisies (got "
           f"{couv['jours_saisis']}) — 30 jours de traite ne suffisent plus",
           results)
    _check(not couv["complete"] and "traite ET bilan" in (couv["message"] or ""),
           "le message annonce que les deux sont exigés", results)


def _test_export(results):
    print("\n[9] Le rapport reste exportable")
    colonnes, lignes = _production()
    types = {c["fieldname"]: c["fieldtype"] for c in colonnes}
    # L'export CSV/Excel de Frappe sérialise les valeurs telles quelles : une
    # liste ou un dict dans une cellule casse le fichier produit.
    mauvais = [(l.get("jour"), cle, valeur) for l in lignes
               for cle, valeur in l.items()
               if cle in types and isinstance(valeur, (list, dict))]
    _check(not mauvais, f"aucune valeur non scalaire ({mauvais[:3]})", results)
    numeriques = [(l.get("jour"), cle, valeur) for l in lignes
                  for cle, valeur in l.items()
                  if types.get(cle) in ("Float", "Int", "Percent")
                  and valeur is not None and not isinstance(valeur, (int, float))]
    _check(not numeriques,
           f"les colonnes chiffrées ne portent que des nombres "
           f"({numeriques[:3]})", results)


def run():
    print("\n" + "=" * 70)
    print("  SCRUM-9 — Rapport Production (ventilation quotidienne)")
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

    vaches = [_vache("L1"), _vache("L2")]
    _vache("T1", tarie=True)
    for jour in range(1, NB_JOURS + 1):
        for vache in vaches:
            _traite(vache, jour)
    _bilan(JOUR_AVEC_BILAN)
    frappe.db.commit()

    _test_structure(results)
    _test_ventilation_quotidienne(results)
    _test_jour_sans_bilan_reste_vide(results)
    _test_total_ventilation(results)
    _test_effectif_moyen_et_deux_denominateurs(results)
    _test_mois_en_cours_ne_gonfle_pas(results)
    _test_mois_sans_traite(results)
    _test_couverture_exige_les_deux(results)
    _test_export(results)

    print("\n" + "-" * 70)
    print(f"  {results['pass']} OK / {results['fail']} FAIL")
    print("-" * 70)
    return results
