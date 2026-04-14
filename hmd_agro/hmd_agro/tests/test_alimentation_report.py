"""
Tests unitaires — Rapport Mensuel / Alimentation (Ration)
Run: bench execute hmd_agro.hmd_agro.tests.test_alimentation_report.run_all_tests
"""
import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import _alimentation

PREFIX = "TEST-ALI-"
CTX = {"date_debut": getdate("2099-03-01"), "date_fin": getdate("2099-03-31"),
       "nb_jours": 31, "mois": 3, "annee": 2099, "jour": 1}


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

def _aliment(suffix, nom, ms_pct=85.0, prix=1.0, type_aliment="CONCENTRE"):
    name = f"{PREFIX}{suffix}"
    doc = frappe.get_doc({
        "doctype": "Aliment", "nom_aliment": name, "type_aliment": type_aliment,
        "unite": "KG", "prix_unitaire": prix, "ms_pct": ms_pct,
    })
    doc.name = name
    doc.db_insert()
    _created.append(("Aliment", name))
    return name

def _ration(suffix, composition):
    name = f"{PREFIX}{suffix}"
    # Insert parent
    doc = frappe.get_doc({
        "doctype": "Ration", "nom_ration": name, "active": 1,
    })
    doc.name = name
    doc.db_insert()
    _created.append(("Ration", name))
    # Insert child rows
    for idx, (aliment_name, qty) in enumerate(composition, 1):
        child = frappe.get_doc({
            "doctype": "Composition Ration", "parent": name, "parenttype": "Ration",
            "parentfield": "composition", "idx": idx,
            "aliment": aliment_name, "quantite": qty, "unite": "KG",
        })
        child.db_insert()
        _created.append(("Composition Ration", child.name))
    return name

def _lot(suffix, ration, nb_animaux):
    name = f"{PREFIX}{suffix}"
    doc = frappe.get_doc({
        "doctype": "Lot", "nom": name, "actif": 1,
        "id_ration_actuelle": ration, "nb_animaux": nb_animaux,
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
        "date_naissance": "2095-01-01", "date_entree": "2099-01-01", "id_lot": lot,
    })
    doc.name = f"{PREFIX}{suffix}"
    doc.db_insert()
    _created.append(("Animal", doc.name))
    return doc

def _traite(animal_name, date, litres):
    doc = frappe.get_doc({
        "doctype": "Traite", "animal": animal_name, "date_traite": date,
        "quantite_litres": litres, "type_traite": "MATIN",
    })
    doc.db_insert()
    _created.append(("Traite", doc.name))

def _cleanup():
    for dt, name in reversed(_created):
        frappe.db.sql(f"DELETE FROM `tab{dt}` WHERE name=%s", name)
    _created.clear()
    frappe.db.commit()

def _find_row(data, label):
    return next((r for r in data if r.get("aliment") == label), None)


def _setup():
    # Clean stale
    frappe.db.sql("DELETE FROM `tabAliment` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabRation` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabComposition Ration` WHERE parent LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabLot` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE identification_tn LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabTraite` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.commit()

    # 2 aliments
    soja = _aliment("SOJA", "Soja", ms_pct=90.0, prix=1.4)
    mais = _aliment("MAIS", "Mais", ms_pct=88.0, prix=1.0)

    # 2 rations: HP (Soja=2kg + Mais=5kg), MP (Soja=1kg + Mais=3kg)
    ration_hp = _ration("RATION-HP", [(soja, 2), (mais, 5)])
    ration_mp = _ration("RATION-MP", [(soja, 1), (mais, 3)])

    # 2 lots: HP (3 cows), MP (2 cows)
    lot_hp = _lot("HP", ration_hp, 3)
    lot_mp = _lot("MP", ration_mp, 2)

    # Animals for each lot (for milk production)
    hp1 = _animal("HP1", lot_hp)
    hp2 = _animal("HP2", lot_hp)
    hp3 = _animal("HP3", lot_hp)
    mp1 = _animal("MP1", lot_mp)
    mp2 = _animal("MP2", lot_mp)

    # Milk production: HP = 930 L/month (3 cows × 10 L/day × 31 days)
    #                   MP = 310 L/month (2 cows × 5 L/day × 31 days)
    for day in range(1, 32):
        date_str = f"2099-03-{day:02d}"
        _traite(hp1.name, date_str, 10)
        _traite(hp2.name, date_str, 10)
        _traite(hp3.name, date_str, 10)
        _traite(mp1.name, date_str, 5)
        _traite(mp2.name, date_str, 5)

    frappe.db.commit()


# ─── Tests ───

def test_columns(results):
    log("Columns — Aliment + MS% + lots", "HEAD")
    cols, _ = _alimentation(CTX)
    col_names = [c["fieldname"] for c in cols]
    check("aliment" in col_names, "Has aliment", "Missing aliment", results)
    check("ms_pct" in col_names, "Has ms_pct", "Missing ms_pct", results)
    check(f"{PREFIX}HP" in col_names, "Has HP lot", f"Cols: {col_names}", results)
    check(f"{PREFIX}MP" in col_names, "Has MP lot", f"Cols: {col_names}", results)

def test_aliment_rows(results):
    log("Aliment rows — HP: Soja=6, Mais=15; MP: Soja=2, Mais=6", "HEAD")
    _, data = _alimentation(CTX)
    soja = _find_row(data, f"{PREFIX}SOJA")
    mais = _find_row(data, f"{PREFIX}MAIS")
    # HP has 3 cows × 2kg Soja = 6kg; 3 × 5kg Mais = 15kg
    check(soja[f"{PREFIX}HP"] == 6, "HP Soja = 6kg", f"Got {soja[f'{PREFIX}HP']}", results)
    check(mais[f"{PREFIX}HP"] == 15, "HP Mais = 15kg", f"Got {mais[f'{PREFIX}HP']}", results)
    # MP has 2 cows × 1kg Soja = 2kg; 2 × 3kg Mais = 6kg
    check(soja[f"{PREFIX}MP"] == 2, "MP Soja = 2kg", f"Got {soja[f'{PREFIX}MP']}", results)
    check(mais[f"{PREFIX}MP"] == 6, "MP Mais = 6kg", f"Got {mais[f'{PREFIX}MP']}", results)

def test_ms_pct(results):
    log("MS% — Soja=90, Mais=88", "HEAD")
    _, data = _alimentation(CTX)
    soja = _find_row(data, f"{PREFIX}SOJA")
    mais = _find_row(data, f"{PREFIX}MAIS")
    check(soja["ms_pct"] == 90.0, "Soja MS% = 90", f"Got {soja['ms_pct']}", results)
    check(mais["ms_pct"] == 88.0, "Mais MS% = 88", f"Got {mais['ms_pct']}", results)

def test_ms_total(results):
    log("MS Total Distribué — HP", "HEAD")
    _, data = _alimentation(CTX)
    row = _find_row(data, "MS Total Distribué")
    # HP: Soja 6kg × 0.9 + Mais 15kg × 0.88 = 5.4 + 13.2 = 18.6
    check(row[f"{PREFIX}HP"] == 18.6, "HP MS Total = 18.6", f"Got {row[f'{PREFIX}HP']}", results)
    # MP: Soja 2kg × 0.9 + Mais 6kg × 0.88 = 1.8 + 5.28 = 7.08
    check(row[f"{PREFIX}MP"] == 7.08, "MP MS Total = 7.08", f"Got {row[f'{PREFIX}MP']}", results)

def test_ms_tete(results):
    log("MS Distribué/Tête — HP: 18.6/3=6.2, MP: 7.08/2=3.54", "HEAD")
    _, data = _alimentation(CTX)
    row = _find_row(data, "MS Distribué/Tête")
    check(row[f"{PREFIX}HP"] == 6.2, "HP MS/tête = 6.2", f"Got {row[f'{PREFIX}HP']}", results)
    check(row[f"{PREFIX}MP"] == 3.54, "MP MS/tête = 3.54", f"Got {row[f'{PREFIX}MP']}", results)

def test_efficacite(results):
    log("Efficacité alimentaire — L milk / Kg MS monthly", "HEAD")
    _, data = _alimentation(CTX)
    row = _find_row(data, "Efficacité alimentaire L/Kg MS")
    # HP: milk = 3 cows × 10 L × 31 days = 930 L; MS monthly = 18.6 × 31 = 576.6; eff = 930/576.6 = 1.61
    check(row[f"{PREFIX}HP"] == 1.61, "HP eff = 1.61", f"Got {row[f'{PREFIX}HP']}", results)
    # MP: milk = 310 L; MS monthly = 7.08 × 31 = 219.48; eff = 310/219.48 = 1.41
    check(row[f"{PREFIX}MP"] == 1.41, "MP eff = 1.41", f"Got {row[f'{PREFIX}MP']}", results)

def test_row_count(results):
    log("Row count — 2 aliments + 3 summary rows = 5", "HEAD")
    _, data = _alimentation(CTX)
    # Filter only our test data
    test_aliments = [r for r in data if r.get("aliment", "").startswith(PREFIX) or r.get("aliment") in ("MS Total Distribué", "MS Distribué/Tête", "Efficacité alimentaire L/Kg MS")]
    check(len(test_aliments) >= 5, "At least 5 rows", f"Got {len(test_aliments)}", results)


# ─── Runner ───

def run_all_tests():
    print("\n" + "=" * 60)
    print("  RAPPORT MENSUEL / ALIMENTATION — TESTS")
    print("=" * 60)

    results = {"pass": 0, "fail": 0}
    try:
        _setup()
        test_columns(results)
        test_aliment_rows(results)
        test_ms_pct(results)
        test_ms_total(results)
        test_ms_tete(results)
        test_efficacite(results)
        test_row_count(results)
    finally:
        _cleanup()

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results
