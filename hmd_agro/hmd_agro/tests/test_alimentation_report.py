"""
Tests unitaires — Rapport Mensuel / Alimentation (Ration)

Convention: ms_pct stored as fraction (0.86 = 86%); the report multiplies by 100
for display. Ration composition is immutable — to change a ration, create a new
Ration. Mid-month switches are tracked via Lot Ration History.

Granularité modes (ctx["granularite"]):
  Quotidien    — only per-lot today's snapshot + Moy/jour mois
  Quinzaine    — per-lot today + cheptel-wide moy_q1 + moy_q2 + Δ Q2/Q1 + Moy/jour mois
  Hebdomadaire — per-lot today + cheptel-wide moy_s1..s4 + Moy/jour mois

Per-lot cells are ALWAYS today's snapshot regardless of mode (Option B
layout — keeps the table narrow). The granularité-specific columns are
cheptel-wide aggregates on the right side.

The "Moy/jour mois" column replaces the old "Cumulé" — same underlying
value (cumulative cheptel-wide kg per aliment) but divided by the number
of days walked since date_debut, so the value is comparable across modes.

Run: bench execute hmd_agro.hmd_agro.tests.test_alimentation_report.run_all_tests
"""
import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import _alimentation
from hmd_agro.hmd_agro.tests._sle_seed_helpers import (
    migrate_test_aliments, seed_distribution_walk, clean_test_stock,
)

PREFIX = "TEST-ALI-"

def _ctx(date_filter_str):
    return {
        "date_filter": getdate(date_filter_str),
        "date_debut": getdate("2024-03-01"),
        "date_fin": getdate("2024-03-31"),
        "nb_jours": 31, "mois": 3, "annee": 2024,
    }

CTX_END = _ctx("2024-03-31")  # default — full month covered


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

def _animal(suffix, lot, date_naissance="2020-01-01"):
    doc = frappe.get_doc({
        "doctype": "Animal", "identification_tn": f"{PREFIX}{suffix}",
        "nom_metier": f"{PREFIX}{suffix}", "categorie": "VACHE", "sexe": "F",
        "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION", "etat_gestation": "VIDE",
        "date_naissance": date_naissance, "date_entree": "2024-01-01", "id_lot": lot,
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

def _ration_history(lot, ration, date_debut, date_fin=None):
    """Insert a Lot Ration History episode row directly (bypasses the auto-tracker
    on Lot.on_update). Used to seed mid-month ration switches in test fixtures.
    date_fin=None ⇒ open episode (currently used by the lot)."""
    doc = frappe.get_doc({
        "doctype": "Lot Ration History",
        "lot": lot, "ration": ration,
        "date_debut": date_debut, "date_fin": date_fin,
        "changed_by": "Administrator", "source": "MANUAL",
    }).insert(ignore_permissions=True)
    _created.append(("Lot Ration History", doc.name))
    return doc.name

def _cleanup():
    # R2: drop SEs / SLE / Bin / Items BEFORE the Aliment so the chain
    # unwinds cleanly. clean_test_stock is idempotent and TEST-ALI-scoped.
    clean_test_stock(PREFIX)
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
        date_str = f"2024-03-{day:02d}"
        for a in (hp1, hp2, hp3): _traite(a.name, date_str, 10, lot_hp)
        for a in (mp1, mp2):     _traite(a.name, date_str, 5,  lot_mp)
    frappe.db.commit()


def _seed_test_sle():
    """Migrate test Aliments + walk-seed Stock Entries for the test month.
    Called by every test entry point AFTER fixtures are fully set up
    (including any mid-month population/ration changes the test layered
    on top of _setup_baseline). seed_distribution_walk reads the current
    Animal/Allotement/Lot Ration History state, so calling it last picks
    up every fixture variation transparently."""
    migrate_test_aliments(PREFIX)
    lots = [f"{PREFIX}HP", f"{PREFIX}MP"]
    seed_distribution_walk(lots, "2024-03-01", "2024-03-31")


# ─── Tests against baseline ─────────────────────────────────────────────────

def test_columns(results):
    log("Columns — Aliment + MS% + lots + Moy/jour mois (Quotidien default)", "HEAD")
    cols, _ = _alimentation(CTX_END)
    col_names = [c["fieldname"] for c in cols]
    check("aliment" in col_names, "Has aliment", "Missing aliment", results)
    check("ms_pct" in col_names, "Has ms_pct", "Missing ms_pct", results)
    check(f"{PREFIX}HP" in col_names, "Has HP lot", f"Cols: {col_names}", results)
    check(f"{PREFIX}MP" in col_names, "Has MP lot", f"Cols: {col_names}", results)
    check("moy_jour_mois" in col_names, "Has Moy/jour mois", f"Cols: {col_names}", results)
    moy_label = next(c["label"] for c in cols if c["fieldname"] == "moy_jour_mois")
    check("03/2024" in moy_label,
          f"Moy/jour mois label includes month: {moy_label}", f"Got {moy_label}", results)
    check("cumule" not in col_names, "cumule column removed", "cumule still present", results)

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

def test_aliment_moy_jour_mois(results):
    log("Moy/jour mois = cheptel kg / nb_jours_walked", "HEAD")
    _, data = _alimentation(CTX_END)
    soja = _find_row(data, f"{PREFIX}SOJA")
    mais = _find_row(data, f"{PREFIX}MAIS")
    # Soja cheptel: 248 kg over 31 days → moy = 8.0
    check(soja["moy_jour_mois"] == 8.0, "Soja moy/jour = 8.0 (248/31)",
          f"Got {soja['moy_jour_mois']}", results)
    # Mais cheptel: 651 kg over 31 days → moy = 21.0
    check(mais["moy_jour_mois"] == 21.0, "Mais moy/jour = 21.0 (651/31)",
          f"Got {mais['moy_jour_mois']}", results)

def test_ms_pct(results):
    log("MS% — Soja=90, Mais=88 (fraction × 100 for display)", "HEAD")
    _, data = _alimentation(CTX_END)
    soja = _find_row(data, f"{PREFIX}SOJA")
    mais = _find_row(data, f"{PREFIX}MAIS")
    check(soja["ms_pct"] == 90.0, "Soja MS% = 90", f"Got {soja['ms_pct']}", results)
    check(mais["ms_pct"] == 88.0, "Mais MS% = 88", f"Got {mais['ms_pct']}", results)

def test_ms_total(results, baseline_ms_moy):
    # Moy/jour is cheptel-wide (includes real DB data); assert delta added by fixtures.
    log("MS Total Distribué — daily per lot, moy/jour cheptel (delta)", "HEAD")
    _, data = _alimentation(CTX_END)
    row = _find_row(data, "MS Total Distribué")
    # HP daily: (2×0.9 + 5×0.88) × 3 = 6.2 × 3 = 18.6
    check(row[f"{PREFIX}HP"] == 18.6, "HP MS daily = 18.6", f"Got {row[f'{PREFIX}HP']}", results)
    # MP daily: (1×0.9 + 3×0.88) × 2 = 3.54 × 2 = 7.08
    check(row[f"{PREFIX}MP"] == 7.08, "MP MS daily = 7.08", f"Got {row[f'{PREFIX}MP']}", results)
    # Delta added by fixtures: (18.6 + 7.08) = 25.68 kg/day cheptel-wide constant
    delta = round((row["moy_jour_mois"] or 0) - (baseline_ms_moy or 0), 2)
    check(delta == 25.68, "Δ MS moy/jour cheptel = 25.68",
          f"Got Δ={delta} (moy={row['moy_jour_mois']}, baseline={baseline_ms_moy})", results)

def test_ms_tete(results):
    log("MS/Tête — daily per lot (moy/jour cheptel-wide, sanity-only)", "HEAD")
    _, data = _alimentation(CTX_END)
    row = _find_row(data, "MS Distribué/Tête")
    # HP daily: 18.6 / 3 = 6.2; MP daily: 7.08 / 2 = 3.54
    check(row[f"{PREFIX}HP"] == 6.2, "HP MS/cow daily = 6.2", f"Got {row[f'{PREFIX}HP']}", results)
    check(row[f"{PREFIX}MP"] == 3.54, "MP MS/cow daily = 3.54", f"Got {row[f'{PREFIX}MP']}", results)
    # Cheptel-wide moy MS/cow-day depends on the whole DB — sanity check it's positive.
    check((row["moy_jour_mois"] or 0) > 0, "MS/cow-day moy > 0",
          f"Got {row['moy_jour_mois']}", results)

def test_efficacite(results):
    log("Efficacité — daily per lot (moy/jour cheptel-wide, sanity-only)", "HEAD")
    _, data = _alimentation(CTX_END)
    row = _find_row(data, "Efficacité alimentaire L/Kg MS")
    # HP daily: 30L / 18.6 = 1.61; MP daily: 10L / 7.08 = 1.41
    check(row[f"{PREFIX}HP"] == 1.61, "HP eff daily = 1.61", f"Got {row[f'{PREFIX}HP']}", results)
    check(row[f"{PREFIX}MP"] == 1.41, "MP eff daily = 1.41", f"Got {row[f'{PREFIX}MP']}", results)
    # Cheptel-wide moy Eff depends on whole DB; sanity check it's a non-negative ratio.
    check((row["moy_jour_mois"] or 0) >= 0, "Eff moy cheptel >= 0",
          f"Got {row['moy_jour_mois']}", results)

def test_midmonth_filter_caps_moy(results):
    log("date_filter = 15/03 → Moy/jour computed on 15 days walked", "HEAD")
    _, data = _alimentation(_ctx("2024-03-15"))
    mais = _find_row(data, f"{PREFIX}MAIS")
    # Cells stay daily (constant pop/ration): HP=15, MP=6
    check(mais[f"{PREFIX}HP"] == 15, "HP Mais cell still daily = 15",
          f"Got {mais[f'{PREFIX}HP']}", results)
    # Mais cheptel over 15 days: HP (5×3×15=225) + MP (3×2×15=90) = 315 → moy 315/15 = 21.0
    check(mais["moy_jour_mois"] == 21.0, "Mais moy/jour 15j = 21.0 (315/15)",
          f"Got {mais['moy_jour_mois']}", results)


# ─── Setup B: population grows mid-month (day 15) ──────────────────────────

def _setup_population_change():
    _setup_baseline()
    extra1 = _animal("HP-EXTRA1", f"{PREFIX}MP")
    extra2 = _animal("HP-EXTRA2", f"{PREFIX}MP")
    _allotement_history(extra1.name, f"{PREFIX}MP", f"{PREFIX}HP", "2024-03-15 12:00:00")
    _allotement_history(extra2.name, f"{PREFIX}MP", f"{PREFIX}HP", "2024-03-15 12:00:00")
    frappe.db.commit()
    _seed_test_sle()

def test_population_change_midmonth(results):
    log("Mid-month pop change — HP 3→5, MP 4→2 on day 15", "HEAD")
    _, data = _alimentation(CTX_END)
    mais = _find_row(data, f"{PREFIX}MAIS")
    # Daily cells on March 31 (post-change): HP=5×5=25, MP=3×2=6
    check(mais[f"{PREFIX}HP"] == 25, "HP Mais cell = 25 (5 cows × 5kg)",
          f"Got {mais[f'{PREFIX}HP']}", results)
    check(mais[f"{PREFIX}MP"] == 6, "MP Mais cell = 6 (2 cows × 3kg)",
          f"Got {mais[f'{PREFIX}MP']}", results)
    # Mais cheptel: 905 kg over 31 days → moy 905/31 = 29.19
    check(mais["moy_jour_mois"] == 29.19, "Mais moy/jour cheptel = 29.19 (905/31)",
          f"Got {mais['moy_jour_mois']}", results)


# ─── Setup C: lot switches ration mid-month (day 15) ───────────────────────

def _setup_ration_switch():
    _setup_baseline()
    soja = f"{PREFIX}SOJA"; mais = f"{PREFIX}MAIS"
    ration_new = _ration("RATION-NEW", [(soja, 4), (mais, 8)])
    # Episode model: HP lot used RATION-HP from Mar 1 to Mar 15 (closed),
    # then RATION-NEW from Mar 15 onward (open). Half-open intervals: day 15
    # belongs to the new episode.
    _ration_history(f"{PREFIX}HP", f"{PREFIX}RATION-HP",
                    date_debut="2024-03-01", date_fin="2024-03-15")
    _ration_history(f"{PREFIX}HP", ration_new,
                    date_debut="2024-03-15", date_fin=None)
    frappe.db.commit()
    _seed_test_sle()

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
    # Soja cheptel: 350 kg over 31 days → moy 350/31 = 11.29
    check(soja["moy_jour_mois"] == 11.29, "Soja moy/jour cheptel = 11.29 (350/31)",
          f"Got {soja['moy_jour_mois']}", results)
    # Mais: 804 kg over 31 days → moy 804/31 = 25.94
    check(mais["moy_jour_mois"] == 25.94, "Mais moy/jour cheptel = 25.94 (804/31)",
          f"Got {mais['moy_jour_mois']}", results)


# ─── Quinzaine / Hebdomadaire mode tests (new feature) ─────────────────────

def _ctx_q(date_filter_str):
    return {**_ctx(date_filter_str), "granularite": "Quinzaine"}

def _ctx_h(date_filter_str):
    return {**_ctx(date_filter_str), "granularite": "Hebdomadaire"}


def test_quinzaine_columns(results):
    log("Quinzaine mode — per-lot single col + moy_q1/moy_q2 + Δ + moy_jour_mois", "HEAD")
    cols, _ = _alimentation(_ctx_q("2024-03-31"))
    col_names = [c["fieldname"] for c in cols]
    # Per-lot cols are still single (Option B keeps lot snapshot, not per-period)
    check(f"{PREFIX}HP" in col_names, "Per-lot HP col present", f"Cols: {col_names}", results)
    check(f"{PREFIX}MP" in col_names, "Per-lot MP col present", f"Cols: {col_names}", results)
    # Cheptel-wide period columns
    check("moy_q1" in col_names, "Has moy_q1", f"Cols: {col_names}", results)
    check("moy_q2" in col_names, "Has moy_q2", f"Cols: {col_names}", results)
    check("delta_q2_q1" in col_names, "Has Δ Q2/Q1", f"Cols: {col_names}", results)
    check("moy_jour_mois" in col_names, "Has moy_jour_mois", f"Cols: {col_names}", results)
    # No per-lot per-period composite columns
    check(f"{PREFIX}HP__Q1" not in col_names, "No per-lot Q1 composite",
          f"Cols: {col_names}", results)


def test_quinzaine_baseline_values(results):
    log("Quinzaine baseline (constant pop/ration) — moy_q1 == moy_q2 == cheptel daily", "HEAD")
    _, data = _alimentation(_ctx_q("2024-03-31"))
    mais = _find_row(data, f"{PREFIX}MAIS")
    # Per-lot cells = today's snapshot (constant pop): HP=3×5=15, MP=2×3=6
    check(mais[f"{PREFIX}HP"] == 15, "HP Mais today = 15", f"Got {mais[f'{PREFIX}HP']}", results)
    check(mais[f"{PREFIX}MP"] == 6, "MP Mais today = 6", f"Got {mais[f'{PREFIX}MP']}", results)
    # Cheptel daily Mais = 15 + 6 = 21. Constant → moy_q1 = moy_q2 = 21
    check(mais["moy_q1"] == 21, "moy_q1 cheptel = 21", f"Got {mais['moy_q1']}", results)
    check(mais["moy_q2"] == 21, "moy_q2 cheptel = 21", f"Got {mais['moy_q2']}", results)
    check(mais["delta_q2_q1"] == 0, "Δ Q2/Q1 = 0% (constant)",
          f"Got {mais['delta_q2_q1']}", results)


def test_quinzaine_population_change(results):
    log("Quinzaine + pop change day 15 — moy_q1 ≠ moy_q2 cheptel-wide", "HEAD")
    _, data = _alimentation(_ctx_q("2024-03-31"))
    mais = _find_row(data, f"{PREFIX}MAIS")
    # Per-lot today = post-move snapshot: HP=5×5=25, MP=2×3=6
    check(mais[f"{PREFIX}HP"] == 25, "HP Mais today (post-move) = 25",
          f"Got {mais[f'{PREFIX}HP']}", results)
    check(mais[f"{PREFIX}MP"] == 6, "MP Mais today (post-move) = 6",
          f"Got {mais[f'{PREFIX}MP']}", results)
    # Q1 cheptel: days 1-14 (HP=3, MP=4) → 3×5+4×3 = 27. Day 15 (HP=5, MP=2) → 5×5+2×3 = 31.
    # Total Q1 = 27×14 + 31 = 378+31 = 409. Moy = 409/15 = 27.27
    check(mais["moy_q1"] == 27.27, "moy_q1 = 27.27 (pop bumped on day 15)",
          f"Got {mais['moy_q1']}", results)
    # Q2 cheptel: HP=5, MP=2 constant → 31 kg/day every day
    check(mais["moy_q2"] == 31, "moy_q2 = 31 (post-bump constant)",
          f"Got {mais['moy_q2']}", results)


def test_quinzaine_partial_q2_midmonth(results):
    log("Quinzaine + date_filter = 20/03 → Q1 full, Q2 partial (5 days)", "HEAD")
    _, data = _alimentation(_ctx_q("2024-03-20"))
    mais = _find_row(data, f"{PREFIX}MAIS")
    # Cheptel daily Mais: HP(15) + MP(6) = 21. Constant.
    check(mais["moy_q1"] == 21, "moy_q1 full (15d) = 21", f"Got {mais['moy_q1']}", results)
    check(mais["moy_q2"] == 21, "moy_q2 partial (5d) = 21", f"Got {mais['moy_q2']}", results)
    check(mais["moy_jour_mois"] == 21.0, "Mais moy/jour mois (20j) = 21.0",
          f"Got {mais['moy_jour_mois']}", results)


def test_quinzaine_past_month_full_q2(results):
    """Past month → Q2 always populated regardless of cursor position. The
    walk extends to end-of-month so users browsing a past month see complete
    data, not a truncated view based on where their date cursor is."""
    log("Quinzaine + past month + cursor day 10 → Q2 still full (not capped)", "HEAD")
    _, data = _alimentation(_ctx_q("2024-03-10"))
    mais = _find_row(data, f"{PREFIX}MAIS")
    # Both periods walked to completion (March is past, full month is over)
    check(mais["moy_q1"] == 21, "moy_q1 full (15d) = 21", f"Got {mais['moy_q1']}", results)
    check(mais["moy_q2"] == 21, "moy_q2 full (16d) = 21 (past month - cursor doesn't truncate)",
          f"Got {mais['moy_q2']}", results)
    check(mais["delta_q2_q1"] == 0, "Δ Q2/Q1 = 0 (constant baseline)",
          f"Got {mais['delta_q2_q1']}", results)
    # Per-lot cell still reflects cursor day (day 10) — should match the
    # constant daily distribution since population/ration didn't change.
    check(mais[f"{PREFIX}HP"] == 15, "HP Mais today (cursor day 10) = 15",
          f"Got {mais[f'{PREFIX}HP']}", results)


def test_hebdomadaire_columns(results):
    log("Hebdomadaire mode — moy_s1..s4 cheptel-wide, no Δ", "HEAD")
    cols, _ = _alimentation(_ctx_h("2024-03-31"))
    col_names = [c["fieldname"] for c in cols]
    for s in ("s1", "s2", "s3", "s4"):
        check(f"moy_{s}" in col_names, f"Has moy_{s}", f"Cols: {col_names}", results)
    check("delta_q2_q1" not in col_names, "No Δ in Hebdomadaire",
          f"Cols: {col_names}", results)
    # Per-lot cols still single
    check(f"{PREFIX}HP" in col_names, "Per-lot HP col present", f"Cols: {col_names}", results)


def test_hebdomadaire_baseline_values(results):
    log("Hebdomadaire baseline — all 4 weeks = 21 kg/day cheptel for Mais", "HEAD")
    _, data = _alimentation(_ctx_h("2024-03-31"))
    mais = _find_row(data, f"{PREFIX}MAIS")
    for s in ("s1", "s2", "s3", "s4"):
        check(mais[f"moy_{s}"] == 21, f"moy_{s} = 21 (cheptel HP+MP)",
              f"Got {mais[f'moy_{s}']}", results)


# ─── Runner ───

def run_all_tests():
    print("\n" + "=" * 60)
    print("  RAPPORT MENSUEL / ALIMENTATION — TESTS")
    print("=" * 60)
    results = {"pass": 0, "fail": 0}

    print("\n  [Setup A: baseline]")
    # Capture cheptel-wide MS moy/jour BEFORE fixtures so we can assert the delta.
    _cleanup()
    _, baseline_data = _alimentation(CTX_END)
    baseline_row = next((r for r in baseline_data if r.get("aliment") == "MS Total Distribué"), None)
    baseline_ms_moy = (baseline_row or {}).get("moy_jour_mois") or 0
    try:
        _setup_baseline()
        _seed_test_sle()  # R2: SLE-based report needs Stock Entries seeded
        test_columns(results)
        test_aliment_daily_cells(results)
        test_aliment_moy_jour_mois(results)
        test_ms_pct(results)
        test_ms_total(results, baseline_ms_moy)
        test_ms_tete(results)
        test_efficacite(results)
        test_midmonth_filter_caps_moy(results)
    finally:
        _cleanup()

    print("\n  [Setup B: mid-month population change]")
    try:
        _setup_population_change()
        test_population_change_midmonth(results)
        test_quinzaine_population_change(results)
    finally:
        _cleanup()

    print("\n  [Setup C: mid-month ration switch]")
    try:
        _setup_ration_switch()
        test_ration_switch_midmonth(results)
    finally:
        _cleanup()

    print("\n  [Setup D: Quinzaine + Hebdomadaire (baseline)]")
    try:
        _setup_baseline()
        _seed_test_sle()  # R2: SLE-based report needs Stock Entries seeded
        test_quinzaine_columns(results)
        test_quinzaine_baseline_values(results)
        test_quinzaine_partial_q2_midmonth(results)
        test_quinzaine_past_month_full_q2(results)
        test_hebdomadaire_columns(results)
        test_hebdomadaire_baseline_values(results)
    finally:
        _cleanup()

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results
