"""
Tests unitaires — Rapport Periodique / Indicateurs

Vache counts = snapshot at date_filter (reconstructed from events).
Production / Concentré / MS = cumulative date_debut → date_filter.
Cheptel-wide values include real DB data; tests use baseline-delta to isolate fixtures.

Run: bench execute hmd_agro.hmd_agro.tests.test_indicateurs_report.run_all_tests
"""
import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.rapport_periodique.rapport_periodique import (
    _indicateurs, _kpi_ind_range,
    INDICATEURS_SENSIBLES_LAIT, couverture_lait, neutraliser_indicateurs_lait,
)
from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.tests._sle_seed_helpers import (
    migrate_test_aliments, seed_test_distribution, clean_test_stock,
)

PREFIX = "TEST-IND-"

def _ctx(date_filter_str):
    return {
        "date_filter": getdate(date_filter_str),
        "date_debut": getdate("2024-03-01"),
        "date_fin": getdate("2024-03-31"),
        "nb_jours": 31, "mois": 3, "annee": 2024,
    }

CTX_END = _ctx("2024-03-31")


def log(msg, level="INFO"):
    prefix = {"PASS": "  OK", "FAIL": "FAIL", "HEAD": "----"}.get(level, "    ")
    print(f"  {prefix}  {msg}")

def check(condition, pass_msg, fail_msg, results):
    if condition:
        log(pass_msg, "PASS")
        results["pass"] += 1
    else:
        log(fail_msg, "FAIL")
        results["fail"] += 1


_created = []

def _aliment(suffix, ms_pct, type_aliment="CONCENTRE"):
    name = f"{PREFIX}{suffix}"
    doc = frappe.get_doc({
        "doctype": "Aliment", "nom_aliment": name, "type_aliment": type_aliment,
        "unite": "KG", "prix_unitaire": 1.0, "ms_pct": ms_pct,
    })
    doc.name = name
    doc.db_insert()
    _created.append(("Aliment", name))
    return name

def _ration(suffix, composition):
    name = f"{PREFIX}{suffix}"
    doc = frappe.get_doc({
        "doctype": "Ration", "nom_ration": name, "active": 1,
    })
    doc.name = name
    doc.db_insert()
    _created.append(("Ration", name))
    for idx, (aliment_name, qty) in enumerate(composition, 1):
        child = frappe.get_doc({
            "doctype": "Composition Ration", "parent": name, "parenttype": "Ration",
            "parentfield": "composition", "idx": idx,
            "aliment": aliment_name, "quantite": qty, "unite": "KG",
        })
        child.db_insert()
        _created.append(("Composition Ration", child.name))
    return name

def _lot(suffix, ration, nb):
    name = f"{PREFIX}{suffix}"
    doc = frappe.get_doc({
        "doctype": "Lot", "nom": name, "actif": 1,
        "id_ration_actuelle": ration, "nb_animaux": nb,
    })
    doc.name = name
    doc.db_insert()
    _created.append(("Lot", name))
    return name

def _animal(suffix, lot):
    doc = frappe.get_doc({
        "doctype": "Animal", "identification_tn": f"{PREFIX}{suffix}",
        "nom_metier": f"{PREFIX}{suffix}", "categorie": "VACHE", "sexe": "F",
        "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION", "etat_gestation": "VIDE",
        "date_naissance": "2020-01-01", "date_entree": "2024-01-01", "id_lot": lot,
    })
    doc.name = f"{PREFIX}{suffix}"
    doc.db_insert()
    _created.append(("Animal", doc.name))
    # Velage so reconstruction sees her as VACHE
    vel = frappe.get_doc({
        "doctype": "Velage", "animal": doc.name,
        "date_velage": "2023-06-01", "type_velage": "FACILE",
        "nombre_veaux": "1", "sexe_veau1": "F", "vivant_veau1": 0,
    })
    vel.flags.ignore_validate = True
    vel.flags.ignore_links = True
    vel.db_insert()
    _created.append(("Velage", vel.name))
    return doc

def _traite(animal_name, date, litres, lot):
    doc = frappe.get_doc({
        "doctype": "Traite", "animal": animal_name, "date_traite": date,
        "quantite_litres": litres, "type_traite": "MATIN", "id_lot": lot,
    })
    doc.db_insert()
    _created.append(("Traite", doc.name))

def _cleanup():
    # Drop SEs / SLE / Bin / Items BEFORE the Aliment so the chain unwinds
    # cleanly. clean_test_stock is idempotent and only touches TEST-IND- rows.
    clean_test_stock(PREFIX)
    for dt, name in reversed(_created):
        frappe.db.sql(f"DELETE FROM `tab{dt}` WHERE name=%s", name)
    _created.clear()
    frappe.db.commit()

def _find(rows, label_starts):
    return next((r for r in rows if r["indicateur"].startswith(label_starts)), None)


def _setup():
    frappe.db.sql("DELETE FROM `tabAliment` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabRation` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabComposition Ration` WHERE parent LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabLot` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE identification_tn LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabTraite` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabVelage` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.commit()

    # 2 concentrés + 1 fourrage to verify the type filter
    soja = _aliment("SOJA", 0.90, "CONCENTRE")
    mais = _aliment("MAIS", 0.88, "CONCENTRE")
    foin = _aliment("FOIN", 0.85, "FOURRAGE")
    ration = _ration("RATION", [(soja, 2), (mais, 5), (foin, 10)])
    lot = _lot("LOT", ration, 4)

    cows = [_animal(f"C{i}", lot) for i in range(1, 5)]
    for day in range(1, 32):
        date_str = f"2024-03-{day:02d}"
        for c in cows:
            _traite(c.name, date_str, 25, lot)
    frappe.db.commit()

    # R2: SLE-based report needs Items + Stock Entries for the test period.
    # Migrate test Aliments to create their Items, then post a Material Issue
    # per day mirroring what the SCRUM-123 generator would have written.
    migrate_test_aliments(PREFIX)
    seed_test_distribution(lot, ration, "2024-03-01", "2024-03-31", n_pop=4)
    frappe.db.commit()


# ─── Tests ───

def test_columns(results):
    log("Columns — indicateur, valeur, valeur_m1, delta_pct, unité", "HEAD")
    cols, _ = _indicateurs(CTX_END)
    names = [c["fieldname"] for c in cols]
    check(names == ["indicateur", "valeur", "valeur_m1", "delta_pct", "unite"],
          "Has 5 expected columns (M-1 même période + Δ % added)",
          f"Got {names}", results)

def test_vache_counts_delta(results, base_vp, base_vl, base_vt):
    log("Vache counts — delta from baseline = +4 lact (test fixture)", "HEAD")
    _, rows = _indicateurs(CTX_END)
    vp = _find(rows, "Vaches Présentes")["valeur"]
    vl = _find(rows, "Vaches Lactantes")["valeur"]
    vt = _find(rows, "Vaches Taries")["valeur"]
    check(vp - base_vp == 4, "Δ Présentes = +4 (4 fixture cows)",
          f"Got Δ={vp - base_vp}", results)
    check(vl - base_vl == 4, "Δ Lactantes = +4", f"Got Δ={vl - base_vl}", results)
    check(vt - base_vt == 0, "Δ Taries = 0", f"Got Δ={vt - base_vt}", results)

def test_production_delta(results, base_prod):
    log("Production Totale — delta from baseline", "HEAD")
    _, rows = _indicateurs(CTX_END)
    prod = _find(rows, "Production Totale")["valeur"]
    # 4 cows × 25L × 31 days = 3100L
    delta = round(prod - base_prod, 1)
    check(delta == 3100, "Δ Production = 3100L", f"Got Δ={delta}", results)

def test_concentre_delta(results, base_conc):
    log("Concentré Total — only CONCENTRE-tagged aliments", "HEAD")
    _, rows = _indicateurs(CTX_END)
    conc = _find(rows, "Concentré Total")["valeur"]
    # Soja 2kg + Mais 5kg = 7kg/cow concentré (Foin not counted)
    # 4 cows × 7kg × 31 days = 868kg
    delta = round(conc - base_conc, 1)
    check(delta == 868, "Δ Concentré = 868kg (Foin FOURRAGE excluded)",
          f"Got Δ={delta}", results)

def test_concentre_source_mesure(results):
    """Le concentré relevé par la ferme prime sur la reconstitution rations.

    Sans relevé : source « rations » (reconstitution SLE). Dès qu'un Bilan Lait
    Journalier porte un concentre_kg sur la période, c'est lui qui alimente le
    L/C — une mesure vaut mieux qu'un plan, et elle couvre l'historique
    antérieur au backfill SLE où la reconstitution rend 0.
    """
    log("Concentré — le relevé ferme prime sur les rations", "HEAD")
    _, rows = _indicateurs(CTX_END)
    avant = _find(rows, "Concentré Total")
    check("source : rations" in avant["indicateur"],
          "sans relevé → source « rations »",
          f"libellé inattendu : {avant['indicateur']}", results)

    bljs = []
    try:
        for jour, kg in (("2024-03-10", 400.0), ("2024-03-11", 350.0)):
            doc = frappe.get_doc({
                "doctype": "Bilan Lait Journalier",
                "date": jour, "production_totale_saisie": 1000.0,
                "lait_vendu": 1000.0, "concentre_kg": kg,
            })
            doc.insert(ignore_permissions=True)
            bljs.append(doc.name)
        frappe.db.commit()

        _, rows = _indicateurs(CTX_END)
        apres = _find(rows, "Concentré Total")
        check("source : relevé ferme" in apres["indicateur"],
              "avec relevé → source « relevé ferme »",
              f"libellé inattendu : {apres['indicateur']}", results)
        check(apres["valeur"] == 750.0,
              "Concentré = 750 kg (somme des relevés, pas la reconstitution)",
              f"Got {apres['valeur']}", results)
        lc = _find(rows, "L/C")["valeur"]
        check(lc > 0, f"L/C recalculé sur le relevé (={lc})", f"L/C={lc}", results)
    finally:
        for name in bljs:
            frappe.delete_doc("Bilan Lait Journalier", name, force=True,
                              ignore_permissions=True)
        frappe.db.commit()


def test_efficacite_alim_delta(results):
    log("Efficacité Alim — sensible value (> 0)", "HEAD")
    _, rows = _indicateurs(CTX_END)
    eff = _find(rows, "Efficacité Alimentaire")["valeur"]
    check(eff > 0, f"Efficacité > 0 (got {eff})", f"Got {eff}", results)

def test_ratios(results):
    log("L/C ratio present and positive", "HEAD")
    _, rows = _indicateurs(CTX_END)
    lc = _find(rows, "L/C")["valeur"]
    check(lc > 0, f"L/C={lc} > 0", f"L/C={lc}", results)

def test_midmonth_caps(results):
    log("date_filter mid-month → cumulatives respect the cutoff", "HEAD")
    _, rows_mid = _indicateurs(_ctx("2024-03-15"))
    _, rows_end = _indicateurs(CTX_END)
    prod_mid = _find(rows_mid, "Production Totale")["valeur"]
    prod_end = _find(rows_end, "Production Totale")["valeur"]
    check(prod_mid < prod_end, f"Mid-month prod ({prod_mid}) < end-month prod ({prod_end})",
          f"prod_mid={prod_mid}, prod_end={prod_end}", results)


def test_lc_indicator_set(results):
    """L/C row has indicator set when value > 0. Thresholds come from HMD
    Configuration → Seuils PFE (defaults 2.0-2.4 / alarms 1.5-3.0)."""
    log("L/C row has indicator (PFE thresholds from config)", "HEAD")
    _, rows = _indicateurs(CTX_END)
    lc = _find(rows, "L/C")
    check(lc is not None, "L/C row present", f"Got {lc}", results)
    val = lc.get("valeur") if lc else 0
    ind = lc.get("indicator") if lc else ""
    if val and val > 0:
        check(ind in ("Green", "Orange", "Red"),
              f"L/C indicator set ({ind}) for value {val}",
              f"Got indicator={ind!r}", results)


def test_persistance_indicator_set(results):
    """Persistance row carries an indicator (Green inside config range,
    Red outside alarm bounds — defaults 0.85-0.95 / alarms 0.7-1.10)."""
    log("Persistance moyenne carries indicator (range from config)", "HEAD")
    _, rows = _indicateurs(CTX_END)
    pers = _find(rows, "Persistance")
    check(pers is not None, "Persistance row present", f"Got {pers}", results)
    val = pers.get("valeur") if pers else 0
    ind = pers.get("indicator") if pers else ""
    if val and val > 0:
        check(ind in ("Green", "Orange", "Red"),
              f"Persistance indicator set ({ind}) for value {val}",
              f"Got indicator={ind!r}", results)


def test_lc_alarm_18(results):
    """Réunion 05/08/2026 : L/C rouge sous 1,8 (patch v1_8/update_lc_seuils),
    et la ligne L/C affiche la cible (pfe_lc_cible, défaut 2.2)."""
    log("Seuil L/C alarme 1.8 (rouge) + cible dans le libellé", "HEAD")
    alarm_min = float(get_config("pfe_lc_alarm_min", default=1.8))
    check(alarm_min >= 1.8,
          f"pfe_lc_alarm_min = {alarm_min} (>= 1.8, seedé par v1_8)",
          f"pfe_lc_alarm_min = {alarm_min} (attendu >= 1.8)", results)
    check(_kpi_ind_range(1.7, 2.0, 2.4, low_alarm=1.8, high_alarm=3.0) == "Red",
          "L/C 1.7 → ROUGE (sous l'alarme 1.8)", "L/C 1.7 pas ROUGE", results)
    check(_kpi_ind_range(1.9, 2.0, 2.4, low_alarm=1.8, high_alarm=3.0) == "Orange",
          "L/C 1.9 → ORANGE (entre alarme et optimal)", "L/C 1.9 pas ORANGE", results)
    check(_kpi_ind_range(2.2, 2.0, 2.4, low_alarm=1.8, high_alarm=3.0) == "Green",
          "L/C 2.2 (cible) → VERT", "L/C 2.2 pas VERT", results)
    _, rows = _indicateurs(CTX_END)
    lc = _find(rows, "L/C")
    check(lc is not None and "cible" in lc["indicateur"],
          f"Libellé L/C porte la cible ({lc['indicateur'] if lc else None})",
          f"Libellé L/C sans cible: {lc}", results)


def test_cout_hors_amort(results):
    """Coût du Litre hors Amortissement = (charges − amortissements) / prod."""
    log("Coût du Litre hors Amortissement — cohérence arithmétique", "HEAD")
    _, rows = _indicateurs(CTX_END)
    hors = _find(rows, "Coût du Litre hors Amortissement")
    check(hors is not None, "Ligne présente", "Ligne absente", results)
    if hors is None:
        return
    complet = _find(rows, "Coût Complet / L")
    charges = _find(rows, "Charges Totales")["valeur"] or 0
    amort = _find(rows, "Dotations aux Amortissements")["valeur"] or 0
    prod = _find(rows, "Production Totale")["valeur"] or 0
    attendu = round((charges - amort) / prod, 3) if prod else 0
    check(abs((hors["valeur"] or 0) - attendu) < 0.005,
          f"Valeur = {hors['valeur']} (attendu {attendu})",
          f"Valeur = {hors['valeur']}, attendu {attendu}", results)
    check((hors["valeur"] or 0) <= (complet["valeur"] or 0),
          "Hors amortissement <= Coût Complet",
          f"hors={hors['valeur']} > complet={complet['valeur']}", results)
    check(hors.get("direction") == "down", "direction='down' (moins = mieux)",
          f"direction={hors.get('direction')}", results)


def test_couverture_complete(results):
    """FIN-S95 — 31 jours de traite sur 31 : aucune alarme parasite, la
    coloration des indicateurs reste ACTIVE (ne pas perdre les vraies alertes)."""
    log("Couverture complète — pas d'avertissement, couleurs conservées", "HEAD")
    couv = couverture_lait("2024-03-01", "2024-03-31")
    check(couv["jours_saisis"] == 31 and couv["jours_periode"] == 31,
          f"Couverture 31/31 ({couv['jours_saisis']}/{couv['jours_periode']})",
          f"Couverture {couv['jours_saisis']}/{couv['jours_periode']}", results)
    check(couv["complete"] and couv["message"] is None,
          "complete=True, aucun message", f"complete={couv['complete']}", results)

    _, rows = _indicateurs(CTX_END)
    check(not any(r["indicateur"].startswith("⚠") for r in rows),
          "Aucune ligne d'avertissement", "Un avertissement est apparu à tort",
          results)
    ligne_couv = _find(rows, "Couverture des Données (lait)")
    check(ligne_couv is not None and ligne_couv["valeur"] == 31,
          "Ligne « Couverture des Données (lait) » = 31 jours",
          f"Got {ligne_couv}", results)
    check(ligne_couv is not None and ligne_couv["unite"] == "jours sur 31",
          "Unité « jours sur 31 »",
          f"Got {ligne_couv['unite'] if ligne_couv else None}", results)
    lc = _find(rows, "L/C")
    if lc and lc["valeur"]:
        check(lc["indicator"] in ("Green", "Orange", "Red"),
              f"L/C garde sa couleur ({lc['indicator']}) sur période complète",
              f"L/C indicator={lc['indicator']!r} alors que la période est complète",
              results)


def test_neutralisation_ciblee(results):
    """La neutralisation ne touche QUE la famille « lait » : un indicateur
    étranger au lait (persistance, écart, entretien) garde sa couleur."""
    log("Neutralisation ciblée — seuls les indicateurs lait perdent la couleur", "HEAD")
    lignes = [
        {"indicateur": "L/C — Lait / Concentré (cible 2,2)", "indicator": "Red"},
        {"indicateur": "Coût Alimentaire / L", "indicator": "Red"},
        {"indicateur": "Coût Complet / L (toutes charges)", "indicator": "Orange"},
        {"indicateur": "Coût du Litre hors Amortissement", "indicator": "Orange"},
        {"indicateur": "IOFC (Income Over Feed Cost) / Vache Lactante / Jour",
         "indicator": "Red"},
        {"indicateur": "Efficacité Alimentaire (sur MS)", "indicator": "Red"},
        {"indicateur": "Persistance moyenne", "indicator": "Red"},
        {"indicateur": "Entretien / Produit Brut", "indicator": "Orange"},
    ]
    neutraliser_indicateurs_lait(lignes)
    eteints = [l["indicateur"] for l in lignes if not l["indicator"]]
    check(len(eteints) == 6, f"6 indicateurs lait éteints ({len(eteints)})",
          f"Éteints: {eteints}", results)
    check(lignes[-2]["indicator"] == "Red" and lignes[-1]["indicator"] == "Orange",
          "Persistance et Entretien gardent leur couleur (hors famille lait)",
          f"Got {lignes[-2]['indicator']!r} / {lignes[-1]['indicator']!r}", results)
    check(all(any(l["indicateur"].startswith(p) for p in INDICATEURS_SENSIBLES_LAIT)
              for l in lignes if not l["indicator"]),
          "Tous les éteints appartiennent à INDICATEURS_SENSIBLES_LAIT",
          "Un indicateur hors liste a été éteint", results)


def test_couverture_trouee(results):
    """Reproduction du cas réel constaté en base (juillet 2026) : le lait n'est
    saisi que la moitié des jours alors que les rations sont distribuées tous
    les jours. Le L/C s'effondre et passe au ROUGE — c'est un TROU DE SAISIE,
    pas un problème de troupeau. Le rapport doit l'annoncer et éteindre la
    couleur, SANS masquer une seule valeur.

    DESTRUCTIF (supprime les traites du 16 au 31) : à lancer en dernier."""
    log("Période trouée — avertissement + indicateurs neutralisés", "HEAD")
    frappe.db.sql("""DELETE FROM `tabTraite`
                     WHERE animal LIKE %s AND date_traite >= '2024-03-16'""",
                  f"{PREFIX}%")
    frappe.db.commit()

    couv = couverture_lait("2024-03-01", "2024-03-31")
    check(couv["jours_saisis"] == 15 and not couv["complete"],
          f"Couverture 15/31 et complete=False ({couv['jours_saisis']}/31)",
          f"Got {couv['jours_saisis']}/{couv['jours_periode']}, "
          f"complete={couv['complete']}", results)
    check(couv["message"] and "15 jours sur 31" in couv["message"],
          f"Message explicite : {couv['message']}", f"Got {couv['message']!r}",
          results)

    _, rows = _indicateurs(CTX_END)
    check(rows and rows[0]["indicateur"].startswith("⚠"),
          "Avertissement en TÊTE de section",
          f"Première ligne = {rows[0]['indicateur'] if rows else None}", results)
    ligne_couv = _find(rows, "Couverture des Données (lait)")
    check(ligne_couv is not None and ligne_couv["valeur"] == 15,
          "Ligne de couverture = 15 jours", f"Got {ligne_couv}", results)

    restants = [r["indicateur"] for r in rows if r.get("indicator")
                and r["indicateur"].startswith(INDICATEURS_SENSIBLES_LAIT)]
    check(not restants, "Aucun indicateur lait n'est encore coloré",
          f"Encore colorés : {restants}", results)

    lc = _find(rows, "L/C")
    check(lc is not None and lc["valeur"] > 0,
          f"La VALEUR du L/C reste affichée ({lc['valeur'] if lc else None}) — "
          "on neutralise la couleur, jamais le chiffre",
          f"Got {lc}", results)


# ─── Runner ───

def run_all_tests():
    print("\n" + "=" * 60)
    print("  RAPPORT PERIODIQUE / INDICATEURS — TESTS")
    print("=" * 60)
    results = {"pass": 0, "fail": 0}

    # Capture baseline before fixtures (cheptel-wide totals include real DB data)
    _cleanup()
    _, base_rows = _indicateurs(CTX_END)
    base_vp = (_find(base_rows, "Vaches Présentes") or {}).get("valeur", 0)
    base_vl = (_find(base_rows, "Vaches Lactantes") or {}).get("valeur", 0)
    base_vt = (_find(base_rows, "Vaches Taries") or {}).get("valeur", 0)
    base_prod = (_find(base_rows, "Production Totale") or {}).get("valeur", 0)
    base_conc = (_find(base_rows, "Concentré Total") or {}).get("valeur", 0)

    try:
        _setup()
        test_columns(results)
        test_vache_counts_delta(results, base_vp, base_vl, base_vt)
        test_production_delta(results, base_prod)
        test_concentre_delta(results, base_conc)
        test_concentre_source_mesure(results)
        test_efficacite_alim_delta(results)
        test_ratios(results)
        test_lc_indicator_set(results)
        test_persistance_indicator_set(results)
        test_midmonth_caps(results)
        test_lc_alarm_18(results)
        test_cout_hors_amort(results)
        test_couverture_complete(results)
        test_neutralisation_ciblee(results)
        # DESTRUCTIF (supprime les traites du 16 au 31) — toujours en dernier.
        test_couverture_trouee(results)
    finally:
        _cleanup()

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results
