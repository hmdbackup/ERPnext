"""
FIN-S31 (RG-FIN-32/33, RC-FIN-55) — valorisation du cheptel reproducteur.

La catégorie d'immobilisation « Cheptel reproducteur » (225 / 285, 5 ans)
existait depuis l'EPIC D, mais aucune vache n'y entrait : le troupeau — le
premier actif de la ferme — était absent du bilan et non amorti.

Doctrine comptable retenue (SCE tunisien, alignée sur la pratique) :
  • **vache reproductrice en production** = immobilisation corporelle
    amortissable (225), mise en service au **premier vêlage** — c'est là
    qu'elle devient productive ;
  • **animaux destinés à la vente** (veaux, taurillons, réformes) = stock
    (37), donc hors de ce module ;
  • **génisses en croissance** = ni l'un ni l'autre tant qu'elles n'ont pas
    vêlé — elles entrent au premier vêlage, à leur coût d'élevage.

Le choix reste piloté par la configuration (`cheptel_mode`), parce que c'est
une décision comptable du client, pas une règle technique :

    NON_VALORISE     (défaut) — rien n'est créé, comportement historique
    ACTIF_BIOLOGIQUE — une Asset par vache, amortie sur la durée configurée
    STOCK            — le cheptel est suivi en stock (compte 37) : hors
                       périmètre de ce module, aucune Asset n'est créée

Valeur d'entrée (RC-FIN-55) :
    animal acheté   → son `prix_achat`
    animal né ici   → forfait `cheptel_cout_elevage` (coût d'élevage jusqu'au
                      premier vêlage) — un paramètre, jamais un littéral

Reprise de l'existant : une vache qui a déjà vêlé il y a N années entre au
bilan pour sa valeur brute avec l'amortissement déjà couru en
`opening_accumulated_depreciation`, et s'amortit sur sa durée résiduelle.
Une vache dont la durée est épuisée n'est pas créée (elle serait entièrement
amortie dès son entrée) — elle est comptée et signalée.

Run:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.utils.cheptel_valorisation.synchroniser_cheptel
"""
import frappe
from frappe.utils import add_months, date_diff, flt, get_last_day, getdate, today

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

MODE_NON_VALORISE = "NON_VALORISE"
MODE_ACTIF = "ACTIF_BIOLOGIQUE"
MODE_STOCK = "STOCK"

CATEGORIE_ASSET = "Cheptel reproducteur"
ITEM_CHEPTEL = "CHEPTEL-REPRO"
LOCATION = "Ferme HMD"
AGE_PREMIER_VELAGE_MOIS = 26          # repli si date_premier_velage manque
JOURS_PAR_AN = 365.25


def mode():
    return get_config("cheptel_mode", default=MODE_NON_VALORISE) or MODE_NON_VALORISE


def duree_amortissement():
    return int(get_config("cheptel_duree_amortissement_ans", default=5) or 5)


def cout_elevage():
    """Coût d'élevage d'une génisse née sur la ferme jusqu'au premier vêlage."""
    return flt(get_config("cheptel_cout_elevage", default=2500))


# ─── Éligibilité et valeur ───────────────────────────────────────────────────

def animaux_eligibles():
    """Vaches actives ayant vêlé — les reproductrices en production."""
    return frappe.db.sql_list("""
        SELECT name FROM `tabAnimal`
        WHERE statut = 'ACTIF' AND categorie = 'VACHE'
        ORDER BY name
    """)


def valeur_entree(animal):
    """Valeur d'entrée à l'actif (TND)."""
    if animal.est_achat and flt(animal.prix_achat) > 0:
        return flt(animal.prix_achat)
    return cout_elevage()


def date_mise_en_service(animal):
    """Premier vêlage = entrée en production. À défaut, naissance + âge type
    au premier vêlage ; à défaut encore, la date d'entrée sur la ferme."""
    if animal.date_premier_velage:
        return getdate(animal.date_premier_velage)
    if animal.date_naissance:
        return getdate(add_months(animal.date_naissance, AGE_PREMIER_VELAGE_MOIS))
    if animal.date_entree:
        return getdate(animal.date_entree)
    return None


def _annees_ecoulees(depuis):
    return int(date_diff(today(), depuis) / JOURS_PAR_AN)


def existing_asset(animal_name):
    return frappe.db.get_value(
        "Asset", {"id_animal": animal_name, "docstatus": ["<", 2]}, "name")


# ─── Création / sortie ───────────────────────────────────────────────────────

@frappe.whitelist()
def creer_actif_cheptel(animal_name, submit=True):
    """Crée l'immobilisation d'une vache (idempotent). Retourne le nom de
    l'Asset, ou None si l'animal n'est pas éligible."""
    if mode() != MODE_ACTIF:
        return None
    deja = existing_asset(animal_name)
    if deja:
        return deja

    animal = frappe.get_doc("Animal", animal_name)
    if animal.statut != "ACTIF" or animal.categorie != "VACHE":
        return None

    mise_en_service = date_mise_en_service(animal)
    if not mise_en_service:
        frappe.log_error(
            title=f"ERR-CHP-01 cheptel {animal_name}",
            message="Aucune date exploitable (premier vêlage / naissance / entrée).",
        )
        return None
    if mise_en_service > getdate(today()):
        mise_en_service = getdate(today())

    duree = duree_amortissement()
    ecoulees = min(_annees_ecoulees(mise_en_service), duree)
    restantes = duree - ecoulees
    if restantes <= 0:
        return None                      # entièrement amortie : hors périmètre

    valeur = valeur_entree(animal)
    amortissement_couru = round(valeur * ecoulees / duree, 3)

    _ensure_item_cheptel()
    asset = frappe.get_doc({
        "doctype": "Asset",
        "company": COMPANY,
        "item_code": ITEM_CHEPTEL,
        "asset_name": f"Vache {animal_name}",
        "asset_category": CATEGORIE_ASSET,
        "location": LOCATION,
        "cost_center": _cost_center_lait(),
        "id_animal": animal_name,
        "is_existing_asset": 1,
        "gross_purchase_amount": valeur,
        # Reprise de l'existant : ERPNext attend la durée TOTALE plus le
        # nombre d'annuités déjà courues ; il ne planifie alors que le solde.
        "opening_accumulated_depreciation": amortissement_couru,
        "opening_number_of_booked_depreciations": ecoulees,
        "purchase_date": str(mise_en_service),
        "available_for_use_date": str(mise_en_service),
        "calculate_depreciation": 1,
        "finance_books": [{
            "depreciation_method": "Straight Line",
            "total_number_of_depreciations": duree,
            "frequency_of_depreciation": 12,
            "depreciation_start_date": str(get_last_day(today())),
        }],
    })
    asset.insert(ignore_permissions=True)
    if submit:
        asset.submit()
    return asset.name


@frappe.whitelist()
def synchroniser_cheptel(limite=None):
    """Crée les immobilisations manquantes pour toutes les vaches éligibles.

    Idempotent et rejouable : les vaches déjà immobilisées sont ignorées.
    À lancer après un vêlage groupé, ou mensuellement.
    """
    courant = mode()
    print("\n" + "=" * 60)
    print(f"  FIN-S31 — Valorisation du cheptel (mode {courant})")
    print("=" * 60)
    if courant != MODE_ACTIF:
        print(f"  [skip]   mode = {courant} : aucune immobilisation créée.")
        print("           Basculer HMD Configuration → Cheptel → "
              f"cheptel_mode = {MODE_ACTIF} pour activer.")
        print("=" * 60 + "\n")
        return {"mode": courant, "crees": 0, "existants": 0, "hors_perimetre": 0}

    crees, existants, hors_perimetre, erreurs = 0, 0, 0, 0
    for animal_name in animaux_eligibles():
        if limite and crees >= int(limite):
            break
        if existing_asset(animal_name):
            existants += 1
            continue
        try:
            if creer_actif_cheptel(animal_name):
                crees += 1
            else:
                hors_perimetre += 1
        except Exception:
            erreurs += 1
            frappe.log_error(title=f"ERR-CHP-02 cheptel {animal_name}",
                             message=frappe.get_traceback())
    frappe.db.commit()

    resume = {"mode": courant, "crees": crees, "existants": existants,
              "hors_perimetre": hors_perimetre, "erreurs": erreurs}
    print(f"  [done]   {crees} immobilisation(s) créée(s), {existants} déjà en place, "
          f"{hors_perimetre} hors périmètre (durée épuisée / date manquante)"
          + (f", {erreurs} erreur(s) — voir Error Log" if erreurs else ""))
    print("=" * 60 + "\n")
    return resume


def sortir_actif_cheptel(animal_doc):
    """Sortie d'un animal immobilisé (VENDU / MORT / REFORME) → mise au rebut
    de l'Asset : la VNC part en charge et l'actif quitte le bilan.

    Non bloquant (CF-FIN-33, même posture que la facturation de vente) : une
    sortie d'animal doit toujours pouvoir s'enregistrer.
    """
    try:
        asset = existing_asset(animal_doc.name)
        if not asset:
            return None
        statut_asset = frappe.db.get_value("Asset", asset, "status")
        if animal_doc.statut == "ACTIF":
            return None                  # retour en arrière : rien à faire
        if statut_asset in ("Scrapped", "Sold", "Cancelled", "Draft"):
            return asset

        from erpnext.assets.doctype.asset.depreciation import scrap_asset

        scrap_asset(asset)
        frappe.msgprint(
            f"Immobilisation {asset} mise au rebut (sortie {animal_doc.statut} "
            f"de {animal_doc.name} — RG-FIN-33).",
            indicator="orange", alert=True,
        )
        return asset
    except Exception:
        frappe.log_error(
            title=f"ERR-CHP-03 sortie cheptel {animal_doc.name}",
            message=frappe.get_traceback(),
        )
        frappe.msgprint(
            f"ERR-CHP-03 : l'immobilisation de {animal_doc.name} n'a pas pu être "
            "sortie — voir le journal d'erreurs. La sortie de l'animal reste "
            "enregistrée.",
            indicator="red", alert=True,
        )
        return None


# ─── Lecture ─────────────────────────────────────────────────────────────────

def valeur_cheptel(date_reference=None):
    """Valeur du cheptel immobilisé : brut, amortissements, VNC + effectif."""
    date_reference = getdate(date_reference or today())
    row = frappe.db.sql("""
        SELECT COUNT(*) AS n,
               COALESCE(SUM(gross_purchase_amount), 0) AS brut,
               COALESCE(SUM(value_after_depreciation), 0) AS net
        FROM `tabAsset`
        WHERE docstatus = 1 AND company = %s AND asset_category = %s
          AND status NOT IN ('Scrapped', 'Sold', 'Cancelled')
          AND available_for_use_date <= %s
    """, (COMPANY, CATEGORIE_ASSET, date_reference), as_dict=True)[0]
    brut, net = float(row.brut or 0), float(row.net or 0)
    return {
        "effectif": int(row.n or 0),
        "brut": round(brut, 2),
        "amortissements": round(brut - net, 2),
        "net": round(net, 2),
        "mode": mode(),
    }


# ─── Référentiel ─────────────────────────────────────────────────────────────

def _cost_center_lait():
    abbr = frappe.db.get_value("Company", COMPANY, "abbr")
    candidat = f"Lait - {abbr}"
    return candidat if frappe.db.exists("Cost Center", candidat) else None


def _ensure_item_cheptel():
    """Item porteur des immobilisations cheptel (ERPNext exige un Item
    `is_fixed_asset` pour créer une Asset)."""
    if frappe.db.exists("Item", ITEM_CHEPTEL):
        return
    frappe.get_doc({
        "doctype": "Item",
        "item_code": ITEM_CHEPTEL,
        "item_name": "Vache reproductrice",
        "item_group": "All Item Groups",
        "stock_uom": "Unit",
        "is_stock_item": 0,
        "is_fixed_asset": 1,
        "asset_category": CATEGORIE_ASSET,
    }).insert(ignore_permissions=True)
