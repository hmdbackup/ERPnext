"""
Point 14 du compte-rendu du 05/08/2026 — SIMULATIONS de revue.

M. Samir a demandé à voir tourner, en séance : « une facture fournisseur,
l'utilisation de médicaments, la TVA ». Ce module pose le scénario complet,
en une commande, sur le site de démonstration :

  (a) FACTURE FOURNISSEUR D'ALIMENT — 10 t de concentré, TVA 19 % ventilée sur
      le compte SCE 4366 « État - TVA déductible », facture réceptionnée en
      stock (`update_stock`) : le CMP du concentré bouge, donc le coût de la
      ration et le coût du litre bougent avec lui.
  (b) FACTURE DE SERVICE — vidange du tracteur, TVA 19 %, charge d'entretien
      sur 615 / atelier Traction. Montre qu'une prestation se saisit exactement
      comme un achat, sans passer par le stock.
  (c) UTILISATION DE MÉDICAMENTS — la facture du vétérinaire (TVA 7 %, taux
      réduit tunisien) reconstitue le stock d'antibiotique, puis un Traitement
      réel sur une vache en production consomme 2 flacons : sortie de stock
      valorisée au CMP, charge postée au Grand Livre, et délai d'attente lait
      posé sur l'animal (le lait de cette vache est écarté 3 jours).
  (d) TVA COLLECTÉE — une vente taxable (fumier, TVA 19 %) fait bouger le
      compte 4367, puis `apercu_tva()` donne la position TVA de la période :
      collectée − déductible. Une ferme laitière qui achète à 19 % et livre du
      lait cru non taxé est structurellement en CRÉDIT de TVA : c'est ce que la
      simulation doit rendre visible.

Étape préalable (b/c) : `_comptes_de_charge()` renseigne, quand il est vide,
le compte de charge par défaut des Items ALI-* (601 « Consommation
d'aliments ») et MED-* (602 « Consommation de médicaments »). Sans lui, toute
sortie de stock retombait sur le compte par défaut de la société, 603
« Variation des stocks » : le montant était juste, le compte ne parlait pas
métier. On n'écrase jamais un compte déjà choisi à la main.

Garde-fous (pattern des voisins socle_comptable / seed_demo_finance) :
  • le socle comptable doit être en place (plan SCE + modèles de TVA) ;
  • ADDITIF UNIQUEMENT : aucune écriture existante n'est modifiée, annulée ni
    supprimée ; on refuse de poster dans un livre déjà arrêté — exercice gelé
    (`Accounts Settings.acc_frozen_upto`) ou clôturé (Period Closing Voucher) ;
  • idempotent : chaque document porte un marqueur SIMU_* dans ses remarques,
    une seconde exécution ne crée aucun doublon.

Run:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.setup.finance.simulations.setup_simulations

    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.setup.finance.simulations.apercu_tva \\
        --kwargs "{'date_debut': '2026-08-01', 'date_fin': '2026-08-31'}"
"""
import frappe
from frappe.utils import add_days, flt, get_first_day, getdate, today

from hmd_agro.hmd_agro.utils.stock_utils import (
    DEFAULT_COMPANY as COMPANY,
    DEFAULT_WAREHOUSE as WAREHOUSE,
)

MARQUEUR = "SIMU"

# Comptes SCE mobilisés (plan_comptable_sce.CHART_SCE)
COMPTE_FOURNISSEURS = "401"
COMPTE_TVA_DEDUCTIBLE = "4366"
COMPTE_TVA_COLLECTEE = "4367"
COMPTE_ALIMENTS = "601"
COMPTE_MEDICAMENTS = "602"
COMPTE_ENTRETIEN = "615"

# Modèles de TVA du socle (socle_comptable.PURCHASE_TVA / SALES_TVA)
TVA_ACHAT_19 = "TVA déductible 19%"
TVA_ACHAT_7 = "TVA déductible 7%"
TVA_VENTE_19 = "TVA collectée 19%"

DT_TVA_ACHAT = "Purchase Taxes and Charges Template"
DT_TVA_VENTE = "Sales Taxes and Charges Template"

# (nom, groupe fournisseur ERPNext)
FOURNISSEURS = [
    ("SCAPCO - Aliments du Bétail", "Local"),
    ("Garage Mécanique du Sahel", "Services"),
    ("Pharmacie Vétérinaire Ben Ammar", "Pharmaceutical"),
]

ITEM_SERVICE = "SERV-ENTRETIEN"
CLIENT_DIVERS = "Client Divers"
ITEM_FUMIER = "FUMIER"

# `jours` = décalage en jours par rapport au jour d'exécution. Tous les
# documents sont datés du JOUR MÊME (0) et c'est délibéré : une écriture de
# stock antidatée met ERPNext en repost différé (Repost Item Valuation), le
# Bin ne prend le nouveau CMP qu'après passage du worker — et la démo montrerait
# un CMP inchangé à l'écran. Daté du jour, le mouvement est le dernier du
# ledger : stock et CMP bougent immédiatement devant le client.

# (a) — facture d'aliment réceptionnée en stock
ACHAT_ALIMENT = {
    "fournisseur": "SCAPCO - Aliments du Bétail",
    "aliment": "Concentré VL Démo",
    "quantite": 10000.0,          # kg — un camion de 10 t
    "prix": 1.35,                 # TND/kg HT
    "piece": "FA-2026-0417",
    "jours": 0,
    "atelier": "Lait",
}

# (b) — facture de service (entretien)
ACHAT_SERVICE = {
    "fournisseur": "Garage Mécanique du Sahel",
    "designation": "Vidange 500 h tracteur — huile moteur + 3 filtres",
    "quantite": 1.0,
    "prix": 280.0,                # TND HT
    "piece": "FS-2026-1183",
    "jours": 0,
    "atelier": "Traction",
}

# (c) — facture vétérinaire puis traitement
ACHAT_MEDICAMENT = {
    "fournisseur": "Pharmacie Vétérinaire Ben Ammar",
    "medicament": "Amoxicilline Démo",
    "quantite": 20.0,             # flacons
    "prix": 25.0,                 # TND/flacon HT
    "piece": "FV-2026-0092",
    "jours": 0,
    "atelier": "Lait",
}
TRAITEMENT = {
    "jours": 0,
    "dose": 20.0,
    "unite_dose": "ml",
    "voie": "INJECTABLE_IM",
    "flacons": 2.0,               # qty_consumed — 2 flacons entamés
    "praticien": "Dr. Néjib Karoui",
    "diagnostic": "Mammite clinique — quartier arrière gauche",
}

# (d) — vente taxable, pour que la TVA collectée existe
VENTE_FUMIER = {
    "client": CLIENT_DIVERS,
    "quantite": 12.0,             # tonnes
    "prix": 45.0,                 # TND/t HT
    "jours": 0,
}


# ─── Helpers ────────────────────────────────────────────────────────────────

def _step(msg):
    print(f"\n  ── {msg}")


def _acc(number):
    """Nom du compte SCE `number` sur la société (None si absent)."""
    return frappe.db.get_value(
        "Account", {"company": COMPANY, "account_number": number})


def _abbr():
    return frappe.db.get_value("Company", COMPANY, "abbr")


def _cc(atelier):
    """Cost Center atelier ; repli sur Frais Généraux si l'atelier manque."""
    abbr = _abbr()
    for candidat in (f"{atelier} - {abbr}", f"Frais Généraux - {abbr}"):
        if frappe.db.exists("Cost Center", candidat):
            return candidat
    frappe.throw("ERR-SIM-07 : aucun Cost Center exploitable — "
                 "lancer setup_socle_comptable (RG-FIN-40).")


def _modele_tva(doctype, titre):
    return frappe.db.get_value(doctype, {"title": titre, "company": COMPANY})


def _lignes_tva(doctype, titre, cost_center):
    """Recopie les lignes du modèle de TVA du socle dans le document.

    On lit le modèle plutôt que de réécrire un taux en dur : la simulation
    montre EXACTEMENT le compte et le taux que l'utilisateur voit dans
    « Modèles de taxes », et suit toute modification faite côté paramétrage.
    """
    modele = frappe.get_doc(doctype, _modele_tva(doctype, titre))
    lignes = []
    for taxe in modele.taxes:
        ligne = {
            "charge_type": taxe.charge_type,
            "account_head": taxe.account_head,
            "description": taxe.description or titre,
            "rate": taxe.rate,
            "cost_center": cost_center,
        }
        if doctype == DT_TVA_ACHAT:
            ligne["category"] = taxe.category or "Total"
            ligne["add_deduct_tax"] = taxe.add_deduct_tax or "Add"
        lignes.append(ligne)
    return lignes


def _achat_existant(marqueur):
    return frappe.db.get_value(
        "Purchase Invoice",
        {"remarks": ["like", f"%{marqueur}%"], "docstatus": ["<", 2]},
        "name")


def _vente_existante(marqueur):
    return frappe.db.get_value(
        "Sales Invoice",
        {"remarks": ["like", f"%{marqueur}%"], "docstatus": ["<", 2]},
        "name")


def _bin_qty(item_code):
    return float(frappe.db.get_value(
        "Bin", {"item_code": item_code, "warehouse": WAREHOUSE},
        "actual_qty") or 0)


def _cmp(item_code):
    from hmd_agro.hmd_agro.utils.stock_utils import get_valuation_rate
    return get_valuation_rate(item_code, WAREHOUSE)


def _date(jours):
    return str(add_days(today(), jours))


# ─── Garde-fous ─────────────────────────────────────────────────────────────

def _garde_fous(dates):
    """Refuse de tourner si le socle manque, ou si le livre est déjà arrêté
    sur la période visée. Le module n'écrit QUE des documents neufs : il ne
    corrige, n'annule et ne supprime jamais un document existant."""
    manquants = [n for n in (COMPTE_FOURNISSEURS, COMPTE_TVA_DEDUCTIBLE,
                             COMPTE_TVA_COLLECTEE, COMPTE_ALIMENTS,
                             COMPTE_MEDICAMENTS, COMPTE_ENTRETIEN)
                 if not _acc(n)]
    if manquants:
        frappe.throw(
            f"ERR-SIM-01 : plan comptable SCE incomplet (comptes manquants : "
            f"{', '.join(manquants)}) — lancer d'abord "
            f"setup.finance.socle_comptable.setup_socle_comptable.")

    for doctype, titre in ((DT_TVA_ACHAT, TVA_ACHAT_19),
                           (DT_TVA_ACHAT, TVA_ACHAT_7),
                           (DT_TVA_VENTE, TVA_VENTE_19)):
        if not _modele_tva(doctype, titre):
            frappe.throw(
                f"ERR-SIM-02 : modèle de TVA « {titre} » absent — lancer "
                f"setup.finance.socle_comptable.setup_socle_comptable.")

    if not frappe.db.exists("Warehouse", WAREHOUSE):
        frappe.throw(f"ERR-SIM-03 : entrepôt « {WAREHOUSE} » absent — "
                     f"lancer setup.stock_foundation.")

    if not frappe.db.exists("Item", ITEM_FUMIER):
        frappe.throw("ERR-SIM-04 : référentiel de vente absent (Item FUMIER) — "
                     "lancer setup.finance.recettes.setup_recettes.")

    plus_ancienne = min(getdate(d) for d in dates)
    gel = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")
    if gel and getdate(gel) >= plus_ancienne:
        frappe.throw(
            f"ERR-SIM-05 : comptabilité gelée jusqu'au {getdate(gel)} — "
            f"la simulation poste à partir du {plus_ancienne}. Livre non "
            f"vierge sur la période : simulation refusée.")
    # Period Closing Voucher borne l'exercice clôturé par `period_end_date`
    # (et non par une date de pièce) : le livre est arrêté jusque-là.
    cloture = frappe.db.get_value(
        "Period Closing Voucher",
        {"company": COMPANY, "period_end_date": [">=", str(plus_ancienne)],
         "docstatus": 1}, "name")
    if cloture:
        frappe.throw(
            f"ERR-SIM-05 : exercice clôturé ({cloture}) couvrant la période de "
            f"simulation — livre non vierge, simulation refusée.")

    for d in dates:
        if not frappe.db.exists("Fiscal Year", {
                "year_start_date": ("<=", str(getdate(d))),
                "year_end_date": (">=", str(getdate(d)))}):
            frappe.throw(
                f"ERR-SIM-06 : aucun exercice comptable ouvert au {getdate(d)} "
                f"— lancer setup_socle_comptable.")


# ─── Référentiel de la simulation ───────────────────────────────────────────

def _referentiel():
    _step("Référentiel : fournisseurs, prestation d'entretien, comptes de charge")
    for nom, groupe in FOURNISSEURS:
        if frappe.db.exists("Supplier", nom):
            print(f"     [skip]   Fournisseur {nom}")
            continue
        groupe = groupe if frappe.db.exists("Supplier Group", groupe) \
            else "All Supplier Groups"
        frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": nom,
            "supplier_group": groupe,
            "supplier_type": "Company",
            "country": "Tunisia",
        }).insert(ignore_permissions=True)
        print(f"     [create] Fournisseur {nom} ({groupe})")

    if not frappe.db.exists("Customer", CLIENT_DIVERS):
        frappe.get_doc({
            "doctype": "Customer",
            "customer_name": CLIENT_DIVERS,
            "customer_type": "Company",
        }).insert(ignore_permissions=True)
        print(f"     [create] Client {CLIENT_DIVERS}")

    _item_service()
    _comptes_de_charge()


def _item_service():
    """Item de prestation : non stocké, imputé d'office sur 615 / Traction.
    C'est le support de toutes les factures d'entretien saisies au clavier."""
    if frappe.db.exists("Item", ITEM_SERVICE):
        print(f"     [skip]   Item {ITEM_SERVICE}")
        return
    groupe = "Services" if frappe.db.exists("Item Group", "Services") \
        else "All Item Groups"
    frappe.get_doc({
        "doctype": "Item",
        "item_code": ITEM_SERVICE,
        "item_name": "Entretien et réparation (prestation)",
        "item_group": groupe,
        "stock_uom": "Unit",
        "is_stock_item": 0,
        "is_purchase_item": 1,
        "is_sales_item": 0,
        "item_defaults": [{
            "company": COMPANY,
            "expense_account": _acc(COMPTE_ENTRETIEN),
            "buying_cost_center": _cc("Traction"),
        }],
    }).insert(ignore_permissions=True)
    print(f"     [create] Item {ITEM_SERVICE} → charge 615, atelier Traction")


def _comptes_de_charge():
    """Compte de charge par défaut des intrants : ALI-* → 601, MED-* → 602.

    Sans ce paramétrage, ERPNext retombe sur `Company.stock_adjustment_account`
    (603 « Variation des stocks ») pour toute sortie de stock : la charge était
    au bon montant mais sur un compte qui ne dit rien au client. On ne remplit
    que les cases vides — un compte choisi à la main n'est jamais écrasé."""
    for doctype, compte in (("Aliment", COMPTE_ALIMENTS),
                            ("Medicament", COMPTE_MEDICAMENTS)):
        cible = _acc(compte)
        poses, deja = 0, 0
        for item in frappe.get_all(doctype, pluck="item"):
            if not item or not frappe.db.exists("Item", item):
                continue
            defaut = frappe.db.get_value(
                "Item Default", {"parent": item, "company": COMPANY},
                ["name", "expense_account"], as_dict=True)
            if not defaut:
                continue
            if defaut.expense_account:
                deja += 1
                continue
            frappe.db.set_value("Item Default", defaut.name,
                                "expense_account", cible, update_modified=False)
            poses += 1
        if poses:
            # L'Item est mis en cache avec ses item_defaults : sans purge, la
            # sortie de stock qui suit dans le même passage lirait l'ancien
            # compte (pattern socle_comptable._set_company_defaults).
            frappe.clear_cache()
        print(f"     [done]   {doctype} : {poses} Item(s) → compte {compte} "
              f"({deja} déjà paramétré(s))")


# ─── (a) Facture fournisseur d'aliment, TVA 19 %, reçue en stock ────────────

def _facture_achat(fournisseur, ligne, titre_tva, piece, date, marqueur,
                   libelle, atelier, update_stock):
    """Une Purchase Invoice soumise, TVA prise au modèle du socle."""
    cost_center = _cc(atelier)
    ligne = dict(ligne)
    ligne["cost_center"] = cost_center
    if update_stock:
        ligne["warehouse"] = WAREHOUSE
    pi = frappe.get_doc({
        "doctype": "Purchase Invoice",
        "company": COMPANY,
        "supplier": fournisseur,
        "posting_date": date,
        "set_posting_time": 1,
        "bill_no": piece,
        "bill_date": date,
        "update_stock": 1 if update_stock else 0,
        # Sans ça, ERPNext arrondit le TTC au dinar et jette la différence sur
        # 658 : le Grand Livre ne dirait plus le même montant que la facture
        # affichée à l'écran. En Tunisie on facture au millime — on garde le
        # centime.
        "disable_rounded_total": 1,
        "items": [ligne],
        "taxes_and_charges": _modele_tva(DT_TVA_ACHAT, titre_tva),
        "taxes": _lignes_tva(DT_TVA_ACHAT, titre_tva, cost_center),
        "remarks": f"{marqueur} — {libelle} (pièce {piece})",
    })
    pi.insert(ignore_permissions=True)
    pi.submit()
    return pi


def _facture_aliment():
    _step("(a) Facture fournisseur d'aliment — TVA 19 %, réception en stock")
    marqueur = f"{MARQUEUR}_ACHAT_ALIMENT"
    deja = _achat_existant(marqueur)
    if deja:
        print(f"     [skip]   Facture aliment déjà simulée ({deja})")
        return deja

    item = frappe.db.get_value("Aliment", ACHAT_ALIMENT["aliment"], "item")
    if not item:
        frappe.throw(
            f"ERR-SIM-08 : Aliment « {ACHAT_ALIMENT['aliment']} » absent ou non "
            f"lié à un Item ERPNext — lancer seed_demo_finance puis "
            f"setup.aliment_migration.migrate_aliments.")

    uom = frappe.db.get_value("Item", item, "stock_uom") or "Kg"
    qty_avant, cmp_avant = _bin_qty(item), _cmp(item)
    if qty_avant < 0:
        # Le site de démonstration distribue de la ration sans avoir saisi les
        # achats correspondants : le stock est négatif. ERPNext régularise
        # alors l'écart de valorisation de la part négative sur le compte de
        # charge par défaut de la société (605) au lieu de tout porter au
        # stock. Ça n'arrive JAMAIS sur une base tenue à jour — mais il faut
        # le savoir avant de projeter le Grand Livre devant le client.
        print(f"     [warn]   Stock {ACHAT_ALIMENT['aliment']} négatif "
              f"({qty_avant:.0f} {uom}) avant l'achat : la facture portera une "
              f"ligne de régularisation sur le compte 605 en plus du compte de "
              f"stock 32. Voir scenario_demo_simulations.md § 1.")
    pi = _facture_achat(
        fournisseur=ACHAT_ALIMENT["fournisseur"],
        ligne={"item_code": item, "qty": ACHAT_ALIMENT["quantite"],
               "rate": ACHAT_ALIMENT["prix"], "uom": uom,
               "conversion_factor": 1},
        titre_tva=TVA_ACHAT_19,
        piece=ACHAT_ALIMENT["piece"],
        date=_date(ACHAT_ALIMENT["jours"]),
        marqueur=marqueur,
        libelle=f"{ACHAT_ALIMENT['quantite']:.0f} {uom} "
                f"{ACHAT_ALIMENT['aliment']}",
        atelier=ACHAT_ALIMENT["atelier"],
        update_stock=True,
    )
    qty_apres, cmp_apres = _bin_qty(item), _cmp(item)
    print(f"     [create] {pi.name} — {ACHAT_ALIMENT['quantite']:.0f} {uom} @ "
          f"{ACHAT_ALIMENT['prix']} TND")
    print(f"              HT {pi.net_total:.3f} | TVA 19 % "
          f"{pi.total_taxes_and_charges:.3f} | TTC {pi.grand_total:.3f} TND")
    print(f"              Stock {ACHAT_ALIMENT['aliment']} : "
          f"{qty_avant:.0f} → {qty_apres:.0f} {uom} | "
          f"CMP {cmp_avant:.3f} → {cmp_apres:.3f} TND/{uom}")
    return pi.name


# ─── (b) Facture de service (entretien) ─────────────────────────────────────

def _facture_service():
    _step("(b) Facture de service — vidange tracteur, TVA 19 %, charge 615")
    marqueur = f"{MARQUEUR}_ACHAT_SERVICE"
    deja = _achat_existant(marqueur)
    if deja:
        print(f"     [skip]   Facture de service déjà simulée ({deja})")
        return deja

    pi = _facture_achat(
        fournisseur=ACHAT_SERVICE["fournisseur"],
        ligne={"item_code": ITEM_SERVICE,
               "item_name": ACHAT_SERVICE["designation"],
               "description": ACHAT_SERVICE["designation"],
               "qty": ACHAT_SERVICE["quantite"],
               "rate": ACHAT_SERVICE["prix"], "uom": "Unit",
               "conversion_factor": 1,
               "expense_account": _acc(COMPTE_ENTRETIEN)},
        titre_tva=TVA_ACHAT_19,
        piece=ACHAT_SERVICE["piece"],
        date=_date(ACHAT_SERVICE["jours"]),
        marqueur=marqueur,
        libelle=ACHAT_SERVICE["designation"],
        atelier=ACHAT_SERVICE["atelier"],
        update_stock=False,
    )
    print(f"     [create] {pi.name} — {ACHAT_SERVICE['designation']}")
    print(f"              HT {pi.net_total:.3f} | TVA 19 % "
          f"{pi.total_taxes_and_charges:.3f} | TTC {pi.grand_total:.3f} TND")
    print(f"              Charge 615 « Entretien et réparations » sur atelier "
          f"{ACHAT_SERVICE['atelier']} — aucun mouvement de stock")
    return pi.name


# ─── (c) Utilisation de médicaments ─────────────────────────────────────────

def _facture_medicament():
    _step("(c1) Facture vétérinaire — médicament, TVA 7 %, réception en stock")
    marqueur = f"{MARQUEUR}_ACHAT_MEDICAMENT"
    deja = _achat_existant(marqueur)
    if deja:
        print(f"     [skip]   Facture vétérinaire déjà simulée ({deja})")
        return deja

    item = frappe.db.get_value("Medicament", ACHAT_MEDICAMENT["medicament"], "item")
    if not item:
        frappe.throw(
            f"ERR-SIM-09 : Médicament « {ACHAT_MEDICAMENT['medicament']} » absent "
            f"ou non lié à un Item ERPNext — lancer seed_demo_finance puis "
            f"setup.medicament_migration.")

    uom = frappe.db.get_value("Item", item, "stock_uom") or "Unit"
    qty_avant = _bin_qty(item)
    pi = _facture_achat(
        fournisseur=ACHAT_MEDICAMENT["fournisseur"],
        ligne={"item_code": item, "qty": ACHAT_MEDICAMENT["quantite"],
               "rate": ACHAT_MEDICAMENT["prix"], "uom": uom,
               "conversion_factor": 1},
        titre_tva=TVA_ACHAT_7,
        piece=ACHAT_MEDICAMENT["piece"],
        date=_date(ACHAT_MEDICAMENT["jours"]),
        marqueur=marqueur,
        libelle=f"{ACHAT_MEDICAMENT['quantite']:.0f} flacons "
                f"{ACHAT_MEDICAMENT['medicament']}",
        atelier=ACHAT_MEDICAMENT["atelier"],
        update_stock=True,
    )
    print(f"     [create] {pi.name} — {ACHAT_MEDICAMENT['quantite']:.0f} flacons @ "
          f"{ACHAT_MEDICAMENT['prix']} TND")
    print(f"              HT {pi.net_total:.3f} | TVA 7 % "
          f"{pi.total_taxes_and_charges:.3f} | TTC {pi.grand_total:.3f} TND")
    print(f"              Stock {ACHAT_MEDICAMENT['medicament']} : "
          f"{qty_avant:.0f} → {_bin_qty(item):.0f} flacons")
    return pi.name


def _animal_cible():
    """Une vache en production : le délai d'attente lait n'a de sens que sur un
    animal qui produit. Tri par nom pour que la démo soit reproductible."""
    return frappe.db.get_value(
        "Animal",
        {"statut": "ACTIF", "categorie": "VACHE",
         "etat_lactation": "EN_PRODUCTION"},
        "name", order_by="name asc")


def _charge_traitement(traitement):
    """Valeur sortie du stock + compte débité pour ce Traitement, lus au
    Grand Livre (et non recalculés) : c'est la preuve que la charge existe."""
    rows = frappe.db.sql("""
        SELECT gle.account, SUM(gle.debit) AS debit
        FROM `tabGL Entry` gle
        JOIN `tabStock Entry` se ON se.name = gle.voucher_no
             AND gle.voucher_type = 'Stock Entry'
        WHERE gle.is_cancelled = 0
          AND gle.company = %s
          AND se.remarks = %s
          AND gle.debit > 0
        GROUP BY gle.account
    """, (COMPANY, f"Traitement {traitement}"), as_dict=True)
    return rows


def _traitement_medicament():
    _step("(c2) Utilisation de médicaments — traitement sur une vache réelle")
    marqueur = f"{MARQUEUR}_TRAITEMENT"
    deja = frappe.db.get_value(
        "Traitement", {"observations": ["like", f"%{marqueur}%"]}, "name")
    if deja:
        print(f"     [skip]   Traitement déjà simulé ({deja})")
        return deja

    animal = _animal_cible()
    if not animal:
        frappe.throw(
            "ERR-SIM-10 : aucune vache ACTIF / EN_PRODUCTION — lancer "
            "setup.finance.seed_demo_finance.run pour peupler le troupeau.")
    medicament = ACHAT_MEDICAMENT["medicament"]
    item = frappe.db.get_value("Medicament", medicament, "item")
    delai = frappe.db.get_value("Medicament", medicament, "delai_attente_lait")

    qty_avant, cmp_actuel = _bin_qty(item), _cmp(item)
    doc = frappe.get_doc({
        "doctype": "Traitement",
        "animal": animal,
        "date_traitement": _date(TRAITEMENT["jours"]),
        "type_traitement": "TRAITEMENT_MEDICAL",
        "praticien": TRAITEMENT["praticien"],
        "observations": f"{marqueur} — simulation de revue (point 14 du "
                        f"compte-rendu du 05/08/2026)",
        "medicaments": [{
            "medicament": medicament,
            "dose": TRAITEMENT["dose"],
            "unite_dose": TRAITEMENT["unite_dose"],
            "qty_consumed": TRAITEMENT["flacons"],
            "voie_administration": TRAITEMENT["voie"],
            "diagnostic": TRAITEMENT["diagnostic"],
        }],
    })
    doc.insert(ignore_permissions=True)
    qty_apres = _bin_qty(item)

    nom_metier = frappe.db.get_value("Animal", animal, "nom_metier") or animal
    etat = frappe.db.get_value(
        "Animal", animal,
        ["attente_lait_active", "date_fin_attente_lait"], as_dict=True)
    print(f"     [create] {doc.name} — vache {nom_metier} ({animal})")
    print(f"              {TRAITEMENT['flacons']:.0f} flacon(s) "
          f"{medicament} @ CMP {cmp_actuel:.3f} TND")
    print(f"              Stock : {qty_avant:.0f} → {qty_apres:.0f} flacons "
          f"(sortie automatique, RG20)")
    for row in _charge_traitement(doc.name):
        print(f"              Charge : {row.account} débité de "
              f"{flt(row.debit):.3f} TND")
    print(f"              Attente lait : {etat.attente_lait_active} — lait écarté "
          f"jusqu'au {etat.date_fin_attente_lait} ({delai} j de délai)")
    return doc.name


# ─── (d) TVA collectée ──────────────────────────────────────────────────────

def _vente_taxable():
    _step("(d) Vente taxable — fumier, TVA collectée 19 % sur le compte 4367")
    marqueur = f"{MARQUEUR}_VENTE_TVA"
    deja = _vente_existante(marqueur)
    if deja:
        print(f"     [skip]   Vente taxable déjà simulée ({deja})")
        return deja

    cost_center = _cc("Cultures - Fourrage")
    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "company": COMPANY,
        "customer": VENTE_FUMIER["client"],
        "posting_date": _date(VENTE_FUMIER["jours"]),
        "set_posting_time": 1,
        "disable_rounded_total": 1,   # cf. _facture_achat — GL au millime
        "items": [{
            "item_code": ITEM_FUMIER,
            "qty": VENTE_FUMIER["quantite"],
            "rate": VENTE_FUMIER["prix"],
            "cost_center": cost_center,
        }],
        "taxes_and_charges": _modele_tva(DT_TVA_VENTE, TVA_VENTE_19),
        "taxes": _lignes_tva(DT_TVA_VENTE, TVA_VENTE_19, cost_center),
        "remarks": f"{marqueur} — {VENTE_FUMIER['quantite']:.0f} t de fumier",
    })
    si.insert(ignore_permissions=True)
    si.submit()
    print(f"     [create] {si.name} — {VENTE_FUMIER['quantite']:.0f} t @ "
          f"{VENTE_FUMIER['prix']} TND")
    print(f"              HT {si.net_total:.3f} | TVA 19 % "
          f"{si.total_taxes_and_charges:.3f} | TTC {si.grand_total:.3f} TND")
    print(f"              Produit 708, TVA collectée sur "
          f"{COMPTE_TVA_COLLECTEE}")
    return si.name


# ─── Position TVA de la période ─────────────────────────────────────────────

@frappe.whitelist()
def apercu_tva(date_debut=None, date_fin=None):
    """Position TVA de la période, lue au Grand Livre : collectée (4367) moins
    déductible (4366).

    Convention de lecture : la TVA collectée est une dette (compte créditeur),
    la TVA déductible une créance (compte débiteur). Solde positif = TVA à
    payer à la recette ; solde négatif = CRÉDIT de TVA reportable — le cas
    normal d'une ferme laitière qui achète à 19 % et vend du lait cru non taxé.

    Retourne {date_debut, date_fin, collectee, deductible, solde, sens}.
    """
    date_fin = str(getdate(date_fin or today()))
    date_debut = str(getdate(date_debut or get_first_day(date_fin)))

    rows = frappe.db.sql("""
        SELECT acc.account_number AS num,
               SUM(gle.debit) AS debit, SUM(gle.credit) AS credit
        FROM `tabGL Entry` gle
        JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.company = %s
          AND gle.is_cancelled = 0
          AND gle.posting_date BETWEEN %s AND %s
          AND acc.account_number IN (%s, %s)
        GROUP BY acc.account_number
    """, (COMPANY, date_debut, date_fin,
          COMPTE_TVA_DEDUCTIBLE, COMPTE_TVA_COLLECTEE), as_dict=True)

    deductible = collectee = 0.0
    for r in rows:
        if r.num == COMPTE_TVA_DEDUCTIBLE:
            deductible = flt(r.debit) - flt(r.credit)
        elif r.num == COMPTE_TVA_COLLECTEE:
            collectee = flt(r.credit) - flt(r.debit)
    solde = round(collectee - deductible, 3)
    sens = "TVA À PAYER" if solde > 0 else ("CRÉDIT DE TVA REPORTABLE"
                                            if solde < 0 else "POSITION NULLE")

    print("\n" + "=" * 70)
    print(f"  Position TVA du {date_debut} au {date_fin}")
    print("=" * 70)
    print(f"    TVA collectée   (4367, ventes)   : {collectee:12.3f} TND")
    print(f"    TVA déductible  (4366, achats)   : {deductible:12.3f} TND")
    print("    " + "-" * 46)
    print(f"    Solde                            : {solde:12.3f} TND  → {sens}")
    print("=" * 70 + "\n")
    return {"date_debut": date_debut, "date_fin": date_fin,
            "collectee": round(collectee, 3), "deductible": round(deductible, 3),
            "solde": solde, "sens": sens}


# ─── Point d'entrée ─────────────────────────────────────────────────────────

@frappe.whitelist()
def setup_simulations():
    """Pose le scénario de simulation complet. Idempotent, additif."""
    print("\n" + "=" * 70)
    print("  SIMULATIONS de revue — facture fournisseur, médicaments, TVA")
    print("  (point 14 du compte-rendu du 05/08/2026)")
    print("=" * 70)

    dates = [_date(ACHAT_ALIMENT["jours"]), _date(ACHAT_SERVICE["jours"]),
             _date(ACHAT_MEDICAMENT["jours"]), _date(TRAITEMENT["jours"]),
             _date(VENTE_FUMIER["jours"])]
    _garde_fous(dates)

    _referentiel()
    resume = {
        "facture_aliment": _facture_aliment(),
        "facture_service": _facture_service(),
        "facture_medicament": _facture_medicament(),
        "traitement": _traitement_medicament(),
        "vente_taxable": _vente_taxable(),
    }

    frappe.db.commit()

    # Position TVA du mois civil en cours : c'est la maille de la déclaration
    # tunisienne, et elle englobe forcément les documents simulés.
    _step("Position TVA du mois en cours")
    resume["tva"] = apercu_tva(str(get_first_day(today())), max(dates))

    print("=" * 70)
    print("  Documents de la simulation :")
    for cle, valeur in resume.items():
        if cle != "tva":
            print(f"    {cle:20s} : {valeur}")
    print("=" * 70)
    print("  Suivre scenario_demo_simulations.md pour la démonstration à l'écran.")
    print("=" * 70 + "\n")
    return resume
