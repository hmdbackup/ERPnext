"""
J6 — Scénario démo finance de bout en bout (achats → consommations →
recettes → charges → immobilisation → KPI colorés).

Builds a small but complete economic month on the site :
  1. Masters troupeau (Batiment, Lot, Taureau, Mère externe) + intrants
     (2 Aliments, 1 Médicament, 1 Semence) avec prix réels
  2. 12 animaux à lifecycle réaliste (tests/seed_data.seed) si troupeau vide
  3. Achats seedés → Bin.valuation_rate réel (seed_demo_prices — FIN-S10)
  4. Ration affectée au lot + distribution backfillée 7 jours → coûts réels
     dans le SLE (FIN-S11)
  5. Traites récentes (setup/seed_recent_traites) + BLJ (lait_vendu, TB/TP)
  6. Facture lait de la semaine (FIN-S21) + vente d'un animal (FIN-S22)
  7. Salaires ventilés + électricité (FIN-S40/S41)
  8. Tracteur en Asset avec calendrier d'amortissement (FIN-S30)

Idempotent : chaque étape se re-skip (marqueurs / exists).

Run:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.setup.finance.seed_demo_finance.run
"""
import frappe
from frappe.utils import add_days, get_last_day, getdate, today

from hmd_agro.hmd_agro.utils.stock_utils import (
    DEFAULT_COMPANY as COMPANY,
    DEFAULT_WAREHOUSE as WAREHOUSE,
)

BATIMENT = "Étable Démo"
LOT = "Individuel"
TAUREAU = "Triad"
MERE = "mere_externe_01"
RATION = "Ration VL Démo"

ALIMENTS = [
    # (nom, type, unite, prix TND, ms_pct)
    ("Concentré VL Démo", "CONCENTRE", "KG", 1.25, 88),
    ("Foin Démo", "FOURRAGE", "KG", 0.45, 85),
]
MEDICAMENT = ("Amoxicilline Démo", "ANTIBIOTIQUE", 3, 25.0)   # délai lait 3 j
SEMENCE_PRIX = 45.0


def _step(msg):
    print(f"\n  ── {msg}")


@frappe.whitelist()
def run():
    print("\n" + "=" * 70)
    print("  Démo finance E2E — achats → coûts → recettes → KPI")
    print("=" * 70)

    _masters()
    _animaux()
    _prix()
    _ration_et_distribution()
    _traites_et_blj()
    _facture_lait()
    _vente_animal()
    _charges()
    _immobilisation()

    frappe.db.commit()
    print("\n  Démo finance seedée.\n" + "=" * 70 + "\n")


def _masters():
    _step("Masters troupeau + intrants")
    if not frappe.db.exists("Batiment", BATIMENT):
        frappe.get_doc({"doctype": "Batiment", "nom_batiment": BATIMENT,
                        "type_batiment": "ELEVAGE"}).insert(ignore_permissions=True)
        print(f"     [create] Batiment {BATIMENT}")
    if not frappe.db.exists("Lot", LOT):
        frappe.get_doc({"doctype": "Lot", "nom": LOT, "batiment": BATIMENT,
                        "actif": 1, "superficie_m2": 400,
                        "capacite_optimale": 20, "capacite_maximale": 30}
                       ).insert(ignore_permissions=True)
        print(f"     [create] Lot {LOT}")
    if not frappe.db.exists("Taureau", TAUREAU):
        frappe.get_doc({"doctype": "Taureau", "nom_taureau": TAUREAU,
                        "code_taureau": "TRIAD", "race": "Montbéliarde"}
                       ).insert(ignore_permissions=True)
        print(f"     [create] Taureau {TAUREAU}")
    if not frappe.db.exists("Mere externe", MERE):
        frappe.get_doc({"doctype": "Mere externe", "nom_mere": MERE,
                        "race": "Montbéliarde"}).insert(ignore_permissions=True)
        print(f"     [create] Mère externe {MERE}")
    for nom, type_, unite, prix, ms in ALIMENTS:
        if not frappe.db.exists("Aliment", nom):
            frappe.get_doc({"doctype": "Aliment", "nom_aliment": nom,
                            "type_aliment": type_, "unite": unite,
                            "prix_unitaire": prix, "ms_pct": ms}
                           ).insert(ignore_permissions=True)
            print(f"     [create] Aliment {nom} @ {prix} TND/{unite}")
    nom_med, type_med, delai, prix_med = MEDICAMENT
    if not frappe.db.exists("Medicament", nom_med):
        frappe.get_doc({"doctype": "Medicament", "nom_medicament": nom_med,
                        "type_medicament": type_med, "delai_attente_lait": delai,
                        "prix_unitaire": prix_med}).insert(ignore_permissions=True)
        print(f"     [create] Médicament {nom_med} @ {prix_med} TND")
    if not frappe.db.exists("Semence", {"taureau": TAUREAU}):
        frappe.get_doc({"doctype": "Semence", "taureau": TAUREAU,
                        "type_semence": "CONVENTIONNELLE",
                        "date_reception": add_days(today(), -60),
                        "prix_unitaire": SEMENCE_PRIX}).insert(ignore_permissions=True)
        print(f"     [create] Semence {TAUREAU} @ {SEMENCE_PRIX} TND/paillette")


def _animaux():
    _step("Troupeau (seed_data.seed si vide)")
    n = frappe.db.count("Animal", {"statut": "ACTIF"})
    if n >= 5:
        print(f"     [skip]   {n} animaux actifs")
        return
    from hmd_agro.hmd_agro.tests.seed_data import seed
    res = seed(n=12)
    print(f"     [create] {res['count']} animaux seedés")


def _prix():
    _step("Achats à prix réels → valuation_rate (FIN-S10)")
    from hmd_agro.hmd_agro.setup.seed_demo_prices import run as seed_prices
    seed_prices()


def _ration_et_distribution():
    _step("Ration + distribution 7 jours (FIN-S11)")
    if not frappe.db.exists("Ration", {"nom_ration": RATION}):
        frappe.get_doc({
            "doctype": "Ration",
            "nom_ration": RATION,
            "active": 1,
            "composition": [
                {"aliment": ALIMENTS[0][0], "quantite": 9, "unite": "KG"},
                {"aliment": ALIMENTS[1][0], "quantite": 14, "unite": "KG"},
            ],
        }).insert(ignore_permissions=True)
        print(f"     [create] Ration {RATION} (9 kg concentré + 14 kg foin /VL/j)")
    ration_name = frappe.db.get_value("Ration", {"nom_ration": RATION})
    lot = frappe.get_doc("Lot", LOT)
    if lot.id_ration_actuelle != ration_name:
        lot.id_ration_actuelle = ration_name
        lot.date_affectation_actuelle = add_days(today(), -8)
        lot.save(ignore_permissions=True)
        print(f"     [update] Lot {LOT} → {RATION}")
    from hmd_agro.hmd_agro.utils.feed_distribution import backfill_distribution
    backfill_distribution(add_days(today(), -7), add_days(today(), -1))
    print("     [done]   Distribution backfillée (7 jours)")


def _traites_et_blj():
    _step("Traites récentes + Bilan Lait Journalier")
    from hmd_agro.hmd_agro.setup.seed_recent_traites import run as seed_traites
    seed_traites()
    for i in range(7, 0, -1):
        day = add_days(today(), -i)
        if frappe.db.exists("Bilan Lait Journalier", {"date": day}):
            continue
        prod = float(frappe.db.sql(
            "SELECT COALESCE(SUM(quantite_litres),0) FROM `tabTraite` "
            "WHERE date_traite=%s", day)[0][0])
        if prod <= 0:
            continue
        frappe.get_doc({
            "doctype": "Bilan Lait Journalier",
            "date": day,
            "lait_vendu": round(prod * 0.93, 1),
            "consommation_interne": round(prod * 0.03, 1),
            "lait_veau": round(prod * 0.04, 1),
            "taux_tb_moyen": 3.9,
            "taux_tp_moyen": 3.25,
            "production_totale_saisie": round(prod, 1),
        }).insert(ignore_permissions=True)
    print("     [done]   BLJ des 7 derniers jours")


def _facture_lait():
    _step("Facture lait de la semaine (FIN-S21)")
    from hmd_agro.hmd_agro.utils.facturation_lait import generate_milk_invoice
    generate_milk_invoice(add_days(today(), -7), add_days(today(), -1))


def _vente_animal():
    _step("Vente d'un animal (FIN-S22)")
    deja = frappe.db.get_value(
        "Sales Invoice", {"remarks": ["like", "%ANIMAL_VENTE_%"],
                          "docstatus": ["<", 2]}, "name")
    if deja:
        print(f"     [skip]   Vente déjà facturée ({deja})")
        return
    cible = frappe.db.get_value(
        "Animal", {"statut": "ACTIF", "categorie": ["in", ["TAURILLON", "VEAU"]]},
        "name") or frappe.db.get_value(
        "Animal", {"statut": "ACTIF", "categorie": "VELLE"}, "name")
    if not cible:
        print("     [skip]   Aucun animal vendable")
        return
    animal = frappe.get_doc("Animal", cible)
    animal.prix_vente = 2500
    animal.statut = "VENDU"
    animal.date_sortie = today()
    animal.flags.ignore_validate = True
    animal.save(ignore_permissions=True)
    print(f"     [done]   {cible} VENDU @ 2500 TND")


def _charges():
    _step("Salaires ventilés + électricité (FIN-S40/S41)")
    from hmd_agro.hmd_agro.utils.charges_utils import post_salaires
    d = getdate(today())
    post_salaires(f"{d.year}-{d.month:02d}",
                  {"Lait": 3500, "Élevage - Génisses": 1200, "Frais Généraux": 800})
    marker = f"ELEC_{d.year}-{d.month:02d}"
    if frappe.db.get_value("Journal Entry",
                           {"user_remark": ["like", f"%{marker}%"],
                            "docstatus": ["<", 2]}):
        print("     [skip]   Électricité déjà postée")
        return
    abbr = frappe.db.get_value("Company", COMPANY, "abbr")
    acc_606 = frappe.db.get_value("Account", {"company": COMPANY, "account_number": "606"})
    acc_532 = frappe.db.get_value("Account", {"company": COMPANY, "account_number": "532"})
    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "company": COMPANY,
        "posting_date": today(),
        "accounts": [
            {"account": acc_606, "debit_in_account_currency": 850,
             "cost_center": f"Frais Généraux - {abbr}"},
            {"account": acc_532, "credit_in_account_currency": 850},
        ],
        "user_remark": f"{marker} — STEG facture électricité",
    })
    je.insert(ignore_permissions=True)
    je.submit()
    print(f"     [done]   Électricité 850 TND ({je.name})")


def _immobilisation():
    _step("Tracteur en immobilisation (FIN-S30)")
    if frappe.db.exists("Asset", {"asset_name": "Tracteur Démo"}):
        print("     [skip]   Asset Tracteur Démo existe")
        return
    if not frappe.db.exists("Item", "EQUIP-TRACTEUR"):
        frappe.get_doc({
            "doctype": "Item", "item_code": "EQUIP-TRACTEUR",
            "item_name": "Tracteur", "item_group": "All Item Groups",
            "stock_uom": "Unit", "is_stock_item": 0, "is_fixed_asset": 1,
            "asset_category": "Matériel de transport",
        }).insert(ignore_permissions=True)
    asset = frappe.get_doc({
        "doctype": "Asset",
        "company": COMPANY,
        "item_code": "EQUIP-TRACTEUR",
        "asset_name": "Tracteur Démo",
        "location": "Ferme HMD",
        "is_existing_asset": 1,
        "gross_purchase_amount": 45000,
        "purchase_date": f"{getdate(today()).year}-01-01",
        "available_for_use_date": f"{getdate(today()).year}-01-01",
        "calculate_depreciation": 1,
        "finance_books": [{
            "depreciation_method": "Straight Line",
            "total_number_of_depreciations": 5,
            "frequency_of_depreciation": 12,
            "depreciation_start_date": str(get_last_day(f"{getdate(today()).year}-12-01")),
        }],
    })
    asset.insert(ignore_permissions=True)
    asset.submit()
    print(f"     [done]   {asset.name} — 45 000 TND, 5 ans linéaire")
