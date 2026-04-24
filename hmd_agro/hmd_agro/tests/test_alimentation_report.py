"""
Tests unitaires — Rapport Mensuel / Alimentation (Ration)

Convention: ms_pct stored as fraction (0.86 = 86%); the report multiplies by 100
for display. Ration composition is immutable — to change a ration, create a new
Ration. Mid-month switches are tracked via Lot Ration History.

Each cell shows the daily snapshot AT date_filter (kg distributed that day).
The "Cumulé" column is cheptel-wide cumulative per aliment from date_debut →
date_filter (inclusive).

Run: bench execute hmd_agro.hmd_agro.tests.test_alimentation_report.run_all_tests
"""
import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import _alimentation

PREFIX = "TEST-ALI-"

def _ctx(date_filter_str):
    return {
        "date_filter": getdate(date_filter_str),
        "date_debut": getdate("2099-03-01"),
        "date_fin": getdate("2099-03-31"),
        "nb_jours": 31, "mois": 3, "annee": 2099,
    }

CTX_END = _ctx("2099-03-31")  # default — full month covered


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

def _aliment(suffix, nom, ms_pct=0.85, prix=1.0, type_aliment="CONCENTRE"):
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

def _animal(suffix, lot, date_naissance="2095-01-01"):
    doc = frappe.get_doc({
        "doctype": "Animal", "identification_tn": f"{PREFIX}{suffix}",
        "nom_metier": f"{PREFIX}{suffix}", "categorie": "VACHE", "sexe": "F",
        "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION", "etat_gestation": "VIDE",
        "date_naissance": date_naissance, "date_entree": "2099-01-01", "id_lot": lot,
    })
    doc.name = f"{PREFIX}{suffix}"
    doc.db_insert()
    _created.append(("Animal", doc.name))
    return doc

def _traite(animal_name, date, litres, lot):
    doc = frappe.get_doc({
        "doctype": "Traite", "animal": animal_name, "date_traite": date,
        "quantite_litres": litres, "type_traite": "MATIN", "id_lot": lot,
    })
    doc.db_insert()
    _created.append(("Traite", doc.name))

def _allotement_history(animal, from_lot, to_lot, creation_dt):
    """Insert an Allotement History row with a backdated `creation` so the
    population helper sees a mid-month move."""
    doc = frappe.get_doc({
        "doctype": "Allotement History",
        "animal": animal, "from_lot": from_lot, "to_lot": to_lot,
        "moved_by": "Administrator", "source": "MANUAL",
        "reason": "Test fixture",
    }).insert(ignore_permissions=True)
    frappe.db.sql("UPDATE `tabAllotement History` SET creation=%s, modified=%s WHERE name=%s",
                  (creation_dt, creation_dt, doc.name))
    _created.append(("Allotement History", doc.name))
    return doc.name

def _ration_history(lot, from_ration, to_ration, creation_dt):
    """Insert a Lot Ration History row with a backdated `creation` so the
    ration helper sees a mid-month switch."""
    doc = frappe.get_doc({
        "doctype": "Lot Ration History",
        "lot": lot, "from_ration": from_ration, "to_ration": to_ration,
        "changed_by": "Administrator", "source": "MANUAL",
    }).insert(ignore_permissions=True)
    frappe.db.sql("UPDATE `tabLot Ration History` SET creation=%s, modified=%s WHERE name=%s",
                  (creation_dt, creation_dt, doc.name))
    _created.append(("Lot Ration History", doc.name))
    return doc.name

def _cleanup():
    for dt, name in reversed(_created):
        frappe.db.sql(f"DELETE FROM `tab{dt}` WHERE name=%s", name)
    _created.clear()
    frappe.db.commit()

def _find_row(data, label):
    return next((r for r in data if r.get("aliment") == label), None)


# ─── Setup A: baseline (constant population, single ration per lot) ─────────

def _setup_baseline():
    frappe.db.sql("DELETE FROM `tabAliment` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabRation` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabComposition Ration` WHERE parent LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabLot` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE identification_tn LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabTraite` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabAllotement History` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabLot Ration History` WHERE lot LIKE %s", f"{PREFIX}%")
    frappe.db.commit()

    soja = _aliment("SOJA", "Soja", ms_pct=0.90, prix=1.4)
    mais = _aliment("MAIS", "Mais", ms_pct=0.88, prix=1.0)
    ration_hp = _ration("RATION-HP", [(soja, 2), (mais, 5)])
    ration_mp = _ration("RATION-MP", [(soja, 1), (mais, 3)])
    lot_hp = _lot("HP", ration_hp, 3)
    lot_mp = _lot("MP", ration_mp, 2)

    hp1 = _animal("HP1", lot_hp); hp2 = _animal("HP2", lot_hp); hp3 = _animal("HP3", lot_hp)
    mp1 = _animal("MP1", lot_mp); mp2 = _animal("MP2", lot_mp)

    for day in range(1, 32):
        date_str = f"2099-03-{day:02d}"
        for a in (hp1, hp2, hp3): _traite(a.name, date_str, 10, lot_hp)
        for a in (mp1, mp2):     _traite(a.name, date_str, 5,  lot_mp)
    frappe.db.commit()


# ─── Tests against baseline ─────────────────────────────────────────────────

def test_columns(results):
    log("Columns — Aliment + MS% + lots + Cumulé", "HEAD")
    cols, _ = _alimentation(CTX_END)
    col_names = [c["fieldname"] for c in cols]
    check("aliment" in col_names, "Has aliment", "Missing aliment", results)
    check("ms_pct" in col_names, "Has ms_pct", "Missing ms_pct", results)
    check(f"{PREFIX}HP" in col_names, "Has HP lot", f"Cols: {col_names}", results)
    check(f"{PREFIX}MP" in col_names, "Has MP lot", f"Cols: {col_names}", results)
    check("cumule" in col_names, "Has Cumulé", f"Cols: {col_names}", results)
    cum_label = next(c["label"] for c in cols if c["fieldname"] == "cumule")
    check("01/03" in cum_label and "31/03" in cum_label,
          f"Cumulé label spans period: {cum_label}", f"Got {cum_label}", results)

def test_aliment_daily_cells(results):
    log("Cells = daily snapshot at date_filter (constant pop/ration)", "HEAD")
    _, data = _alimentation(CTX_END)
    soja = _find_row(data, f"{PREFIX}SOJA")
    mais = _find_row(data, f"{PREFIX}MAIS")
    # HP daily: 3 cows × 2kg Soja = 6; 3 × 5 = 15
    check(soja[f"{PREFIX}HP"] == 6, "HP Soja jour = 6kg", f"Got {soja[f'{PREFIX}HP']}", results)
    check(mais[f"{PREFIX}HP"] == 15, "HP Mais jour = 15kg", f"Got {mais[f'{PREFIX}HP']}", results)
    # MP daily: 2 × 1 = 2; 2 × 3 = 6
    check(soja[f"{PREFIX}MP"] == 2, "MP Soja jour = 2kg", f"Got {soja[f'{PREFIX}MP']}", results)
    check(mais[f"{PREFIX}MP"] == 6, "MP Mais jour = 6kg", f"Got {mais[f'{PREFIX}MP']}", results)

def test_aliment_cumule_cheptel(results):
    log("Cumulé column = cheptel-wide kg × 31 days", "HEAD")
    _, data = _alimentation(CTX_END)
    soja = _find_row(data, f"{PREFIX}SOJA")
    mais = _find_row(data, f"{PREFIX}MAIS")
    # Soja cheptel: HP (2×3×31=186) + MP (1×2×31=62) = 248
    check(soja["cumule"] == 248, "Soja cumulé = 248kg cheptel",
          f"Got {soja['cumule']}", results)
    # Mais cheptel: HP (5×3×31=465) + MP (3×2×31=186) = 651
    check(mais["cumule"] == 651, "Mais cumulé = 651kg cheptel",
          f"Got {mais['cumule']}", results)

def test_ms_pct(results):
    log("MS% — Soja=90, Mais=88 (fraction × 100 for display)", "HEAD")
    _, data = _alimentation(CTX_END)
    soja = _find_row(data, f"{PREFIX}SOJA")
    mais = _find_row(data, f"{PREFIX}MAIS")
    check(soja["ms_pct"] == 90.0, "Soja MS% = 90", f"Got {soja['ms_pct']}", results)
    check(mais["ms_pct"] == 88.0, "Mais MS% = 88", f"Got {mais['ms_pct']}", results)

def test_ms_total(results, baseline_ms_cum):
    # Cumulé is cheptel-wide (includes real DB data); assert delta added by fixtures.
    log("MS Total Distribué — daily per lot, cumulative cheptel (delta)", "HEAD")
    _, data = _alimentation(CTX_END)
    row = _find_row(data, "MS Total Distribué")
    # HP daily: (2×0.9 + 5×0.88) × 3 = 6.2 × 3 = 18.6
    check(row[f"{PREFIX}HP"] == 18.6, "HP MS daily = 18.6", f"Got {row[f'{PREFIX}HP']}", results)
    # MP daily: (1×0.9 + 3×0.88) × 2 = 3.54 × 2 = 7.08
    check(row[f"{PREFIX}MP"] == 7.08, "MP MS daily = 7.08", f"Got {row[f'{PREFIX}MP']}", results)
    # Delta added by fixtures: (18.6 + 7.08) × 31 = 796.08
    delta = round((row["cumule"] or 0) - (baseline_ms_cum or 0), 2)
    check(delta == 796.08, "Δ MS cumulé cheptel = 796.08",
          f"Got Δ={delta} (cumulé={row['cumule']}, baseline={baseline_ms_cum})", results)

def test_ms_tete(results):
    log("MS/Tête — daily per lot (cumulative is cheptel-wide, not asserted)", "HEAD")
    _, data = _alimentation(CTX_END)
    row = _find_row(data, "MS Distribué/Tête")
    # HP daily: 18.6 / 3 = 6.2; MP daily: 7.08 / 2 = 3.54
    check(row[f"{PREFIX}HP"] == 6.2, "HP MS/cow daily = 6.2", f"Got {row[f'{PREFIX}HP']}", results)
    check(row[f"{PREFIX}MP"] == 3.54, "MP MS/cow daily = 3.54", f"Got {row[f'{PREFIX}MP']}", results)
    # Cheptel cumulé MS/cow-day depends on the whole DB, not just fixtures — sanity check it's positive.
    check((row["cumule"] or 0) > 0, "MS/cow-day cumulé > 0", f"Got {row['cumule']}", results)

def test_efficacite(results):
    log("Efficacité — daily per lot (cumulative is cheptel-wide, not asserted)", "HEAD")
    _, data = _alimentation(CTX_END)
    row = _find_row(data, "Efficacité alimentaire L/Kg MS")
    # HP daily: 30L / 18.6 = 1.61; MP daily: 10L / 7.08 = 1.41
    check(row[f"{PREFIX}HP"] == 1.61, "HP eff daily = 1.61", f"Got {row[f'{PREFIX}HP']}", results)
    check(row[f"{PREFIX}MP"] == 1.41, "MP eff daily = 1.41", f"Got {row[f'{PREFIX}MP']}", results)
    # Cheptel cumulé Eff depends on whole DB; sanity check it's a non-negative ratio.
    check((row["cumule"] or 0) >= 0, "Eff cumulé cheptel >= 0", f"Got {row['cumule']}", results)

def test_midmonth_filter_caps_cumule(results):
    log("date_filter = 15/03 → Cumulé only sums days 1-15", "HEAD")
    _, data = _alimentation(_ctx("2099-03-15"))
    mais = _find_row(data, f"{PREFIX}MAIS")
    # Cells stay daily (constant): HP=15, MP=6
    check(mais[f"{PREFIX}HP"] == 15, "HP Mais cell still daily = 15",
          f"Got {mais[f'{PREFIX}HP']}", results)
    # Cumulé only over 15 days: HP (5×3×15=225) + MP (3×2×15=90) = 315
    check(mais["cumule"] == 315, "Mais cumulé 15j = 315kg",
          f"Got {mais['cumule']}", results)


# ─── Setup B: population grows mid-month (day 15) ──────────────────────────

def _setup_population_change():
    _setup_baseline()
    extra1 = _animal("HP-EXTRA1", f"{PREFIX}MP")
    extra2 = _animal("HP-EXTRA2", f"{PREFIX}MP")
    _allotement_history(extra1.name, f"{PREFIX}MP", f"{PREFIX}HP", "2099-03-15 12:00:00")
    _allotement_history(extra2.name, f"{PREFIX}MP", f"{PREFIX}HP", "2099-03-15 12:00:00")
    frappe.db.commit()

def test_population_change_midmonth(results):
    log("Mid-month pop change — HP 3→5, MP 4→2 on day 15", "HEAD")
    _, data = _alimentation(CTX_END)
    mais = _find_row(data, f"{PREFIX}MAIS")
    # Daily cells on March 31 (post-change): HP=5×5=25, MP=3×2=6
    check(mais[f"{PREFIX}HP"] == 25, "HP Mais cell = 25 (5 cows × 5kg)",
          f"Got {mais[f'{PREFIX}HP']}", results)
    check(mais[f"{PREFIX}MP"] == 6, "MP Mais cell = 6 (2 cows × 3kg)",
          f"Got {mais[f'{PREFIX}MP']}", results)
    # Cumulé cheptel-wide: HP (5×(3×14+5×17)=635) + MP (3×(4×14+2×17)=270) = 905
    check(mais["cumule"] == 905, "Mais cumulé cheptel = 905kg",
          f"Got {mais['cumule']}", results)


# ─── Setup C: lot switches ration mid-month (day 15) ───────────────────────

def _setup_ration_switch():
    _setup_baseline()
    soja = f"{PREFIX}SOJA"; mais = f"{PREFIX}MAIS"
    ration_new = _ration("RATION-NEW", [(soja, 4), (mais, 8)])
    _ration_history(f"{PREFIX}HP", f"{PREFIX}RATION-HP", ration_new, "2099-03-15 12:00:00")
    frappe.db.commit()

def test_ration_switch_midmonth(results):
    log("Mid-month ration switch — HP RATION-HP → RATION-NEW on day 15", "HEAD")
    _, data = _alimentation(CTX_END)
    soja = _find_row(data, f"{PREFIX}SOJA")
    mais = _find_row(data, f"{PREFIX}MAIS")
    # Daily cells on March 31 (post-switch): HP uses RATION-NEW (4 Soja, 8 Mais)
    check(soja[f"{PREFIX}HP"] == 12, "HP Soja cell = 12 (3 cows × 4kg)",
          f"Got {soja[f'{PREFIX}HP']}", results)
    check(mais[f"{PREFIX}HP"] == 24, "HP Mais cell = 24 (3 cows × 8kg)",
          f"Got {mais[f'{PREFIX}HP']}", results)
    # Cumulé cheptel: Soja: HP (2×3×14 + 4×3×17 = 288) + MP (62) = 350
    check(soja["cumule"] == 350, "Soja cumulé cheptel = 350kg",
          f"Got {soja['cumule']}", results)
    # Mais: HP (5×3×14 + 8×3×17 = 618) + MP (186) = 804
    check(mais["cumule"] == 804, "Mais cumulé cheptel = 804kg",
          f"Got {mais['cumule']}", results)


# ─── Runner ───

def run_all_tests():
    print("\n" + "=" * 60)
    print("  RAPPORT MENSUEL / ALIMENTATION — TESTS")
    print("=" * 60)
    results = {"pass": 0, "fail": 0}

    print("\n  [Setup A: baseline]")
    # Capture cheptel-wide MS cumulé BEFORE fixtures so we can assert the delta.
    _cleanup()
    _, baseline_data = _alimentation(CTX_END)
    baseline_row = next((r for r in baseline_data if r.get("aliment") == "MS Total Distribué"), None)
    baseline_ms_cum = (baseline_row or {}).get("cumule") or 0
    try:
        _setup_baseline()
        test_columns(results)
        test_aliment_daily_cells(results)
        test_aliment_cumule_cheptel(results)
        test_ms_pct(results)
        test_ms_total(results, baseline_ms_cum)
        test_ms_tete(results)
        test_efficacite(results)
        test_midmonth_filter_caps_cumule(results)
    finally:
        _cleanup()

    print("\n  [Setup B: mid-month population change]")
    try:
        _setup_population_change()
        test_population_change_midmonth(results)
    finally:
        _cleanup()

    print("\n  [Setup C: mid-month ration switch]")
    try:
        _setup_ration_switch()
        test_ration_switch_midmonth(results)
    finally:
        _cleanup()

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results
