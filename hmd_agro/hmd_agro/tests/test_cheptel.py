"""
FIN-S31 — tests de la valorisation du cheptel reproducteur
(RG-FIN-32/33, RC-FIN-55, CF-FIN-33).

Couvre :
  1. `cheptel_mode` pilote tout : NON_VALORISE ne crée rien
  2. Valeur d'entrée : prix d'achat réel pour un animal acheté, forfait
     « coût d'élevage » pour un animal né sur la ferme
  3. Mise en service au premier vêlage
  4. Reprise de l'existant : amortissement déjà couru en ouverture, durée
     résiduelle amortie ; vache à durée épuisée laissée hors périmètre
  5. Idempotence de `synchroniser_cheptel` (une vache = une immobilisation)
  6. Éligibilité : seules les VACHE actives entrent à l'actif
  7. `valeur_cheptel` : brut, amortissements, VNC
  8. Sortie de l'animal (VENDU) → immobilisation mise au rebut, sans jamais
     empêcher l'enregistrement de la sortie

Pré-requis site : socle + immobilisations (Asset Category « Cheptel
reproducteur », Custom Field Asset-id_animal).

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_cheptel.run
"""
import traceback

import frappe
from frappe.utils import add_days, add_months, flt, today

from hmd_agro.hmd_agro.utils import cheptel_valorisation as cv

PREFIXE_TN = "8890000"
COMPANY = "hmd-agro"
MERE_TEST = "zztest_mere_cheptel"
MERE_ANIMAL_TN = f"{PREFIXE_TN}900"


def _cleanup():
    animaux = frappe.get_all("Animal",
                             filters={"identification_tn": ["like", f"{PREFIXE_TN}%"]},
                             fields=["name", "id_lot"])
    lots = {a.id_lot for a in animaux if a.id_lot}
    for animal in [a.name for a in animaux]:
        for asset in frappe.get_all("Asset", filters={"id_animal": animal}, pluck="name"):
            frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no IN "
                          "(SELECT name FROM `tabJournal Entry` WHERE name IN "
                          " (SELECT parent FROM `tabJournal Entry Account` "
                          "  WHERE reference_name=%s))", asset)
            frappe.db.sql("DELETE FROM `tabAsset Depreciation Schedule` WHERE asset=%s", asset)
            frappe.db.sql("DELETE FROM `tabDepreciation Schedule` WHERE parent=%s", asset)
            frappe.db.sql("DELETE FROM `tabAsset Finance Book` WHERE parent=%s", asset)
            frappe.db.sql("DELETE FROM `tabAsset Activity` WHERE asset=%s", asset)
            frappe.db.sql("DELETE FROM `tabAsset` WHERE name=%s", asset)
        for si in frappe.get_all(
                "Sales Invoice",
                filters={"remarks": ["like", f"%ANIMAL_VENTE_{animal}%"]}, pluck="name"):
            frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", si)
            frappe.db.sql("DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no=%s", si)
            frappe.db.sql("DELETE FROM `tabSales Invoice Item` WHERE parent=%s", si)
            frappe.db.sql("DELETE FROM `tabSales Invoice` WHERE name=%s", si)
        frappe.db.sql("DELETE FROM `tabAllotement History` WHERE animal=%s", animal)
        frappe.db.sql("DELETE FROM `tabAnimal` WHERE name=%s", animal)
    frappe.db.sql("DELETE FROM `tabMere externe` WHERE name=%s", MERE_TEST)
    frappe.db.commit()
    _rafraichir_lots(lots)


def _rafraichir_lots(lots):
    """Les suppressions ci-dessus passent en SQL direct : `Animal.on_trash` ne
    tourne pas, donc `Lot.nb_animaux` resterait gonflé — et la distribution
    alimentaire des tests suivants avec lui. On recompte explicitement."""
    from hmd_agro.hmd_agro.doctype.lot.lot import update_lot_animal_count

    for lot in {l for l in lots if l}:
        update_lot_animal_count(lot)
    frappe.db.commit()


def _mere_externe():
    """Toute vache doit avoir une mère (CF-ANI-03) : on rattache les animaux
    de test à une mère externe dédiée, supprimée avec eux."""
    if not frappe.db.exists("Mere externe", MERE_TEST):
        frappe.get_doc({"doctype": "Mere externe", "nom_mere": MERE_TEST,
                        "race": "Montbéliarde"}).insert(ignore_permissions=True)
    return MERE_TEST


def _taureau():
    """Père et lot sont obligatoires sur Animal — on réutilise l'existant du
    site plutôt que d'en créer (le test ne porte pas sur la généalogie)."""
    nom = frappe.db.get_value("Taureau", {}, "name")
    if not nom:
        nom = frappe.get_doc({"doctype": "Taureau", "nom_taureau": "ZZTEST Taureau",
                              "code_taureau": "ZZTEST",
                              "race": "Montbéliarde"}).insert(
            ignore_permissions=True).name
    return nom


def _lot():
    nom = frappe.db.get_value("Lot", {"actif": 1}, "name")
    if not nom:
        nom = frappe.get_doc({"doctype": "Lot", "nom": "ZZTEST Lot", "actif": 1,
                              "superficie_m2": 100, "capacite_optimale": 10,
                              "capacite_maximale": 15}).insert(
            ignore_permissions=True).name
    return nom


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _vache(suffixe, premier_velage_il_y_a_mois, achat=False, prix_achat=0,
           categorie="VACHE", mere=None, tn=None):
    """Vache de test : le premier vêlage date de N mois, ce qui fixe sa date
    de mise en service et donc l'amortissement déjà couru.

    Achetée → mère externe + prix d'achat ; née ici → mère du troupeau
    (CF-ANI-03 impose l'une ou l'autre)."""
    naissance = add_months(today(), -(premier_velage_il_y_a_mois + 26))
    payload = {
        "doctype": "Animal",
        "identification_tn": tn or f"{PREFIXE_TN}{suffixe:03d}",
        "categorie": categorie,
        "sexe": "F",
        "date_naissance": str(naissance),
        "date_premier_velage": str(add_months(today(), -premier_velage_il_y_a_mois)),
        "statut": "ACTIF",
        "id_pere": _taureau(),
        "id_lot": _lot(),
    }
    if achat:
        payload.update({"est_achat": 1, "prix_achat": prix_achat,
                        "date_entree": str(naissance),
                        "id_mere_externe": _mere_externe()})
    else:
        payload.update({"est_achat": 0, "id_mere": mere})
    doc = frappe.get_doc(payload)
    doc.insert(ignore_permissions=True)
    return doc.name


def run():
    print("\n" + "=" * 70)
    print("  FIN-S31 — Valorisation du cheptel reproducteur")
    print("=" * 70)
    mode_initial = cv.mode()
    try:
        return _run_inner()
    except Exception:
        print("\n  ❌ Test crashed mid-flight:")
        print(traceback.format_exc())
        return {"pass": 0, "fail": 1}
    finally:
        _cleanup()
        frappe.db.set_single_value("HMD Configuration", "cheptel_mode", mode_initial)
        frappe.clear_cache()
        frappe.db.commit()


def _set_mode(valeur):
    frappe.db.set_single_value("HMD Configuration", "cheptel_mode", valeur)
    frappe.clear_cache()


def _run_inner():
    results = {"pass": 0, "fail": 0}
    _cleanup()

    duree = cv.duree_amortissement()
    forfait = cv.cout_elevage()

    mere = _vache(0, premier_velage_il_y_a_mois=60, achat=True, prix_achat=3000,
                  tn=MERE_ANIMAL_TN)
    nee_ici = _vache(1, premier_velage_il_y_a_mois=6, mere=mere)
    achetee = _vache(2, premier_velage_il_y_a_mois=30, achat=True, prix_achat=4000)
    vieille = _vache(3, premier_velage_il_y_a_mois=12 * (duree + 1), mere=mere)
    genisse = _vache(4, premier_velage_il_y_a_mois=1, categorie="GENISSE", mere=mere)
    frappe.db.commit()

    # ── 1. Le mode pilote tout
    _set_mode(cv.MODE_NON_VALORISE)
    _check(cv.creer_actif_cheptel(nee_ici) is None,
           "Mode NON_VALORISE → aucune immobilisation créée", results)
    resume = cv.synchroniser_cheptel()
    _check(resume["crees"] == 0 and resume["mode"] == cv.MODE_NON_VALORISE,
           "synchroniser_cheptel reste sans effet hors mode actif", results)
    _check(cv.valeur_cheptel()["mode"] == cv.MODE_NON_VALORISE,
           "valeur_cheptel expose le mode courant", results)

    # ── 2/3. Valeur d'entrée et mise en service
    _set_mode(cv.MODE_ACTIF)
    animal_nee = frappe.get_doc("Animal", nee_ici)
    animal_achetee = frappe.get_doc("Animal", achetee)
    _check(cv.valeur_entree(animal_nee) == forfait,
           f"Animal né sur la ferme → forfait coût d'élevage ({forfait} TND)", results)
    _check(cv.valeur_entree(animal_achetee) == 4000,
           "Animal acheté → son prix d'achat réel (4000 TND)", results)
    _check(str(cv.date_mise_en_service(animal_nee)) == str(animal_nee.date_premier_velage),
           "Mise en service = date du premier vêlage", results)

    # ── 4. Création et reprise de l'existant
    asset_nee = cv.creer_actif_cheptel(nee_ici)
    _check(bool(asset_nee), f"Immobilisation créée pour la vache née ici ({asset_nee})",
           results)
    doc = frappe.get_doc("Asset", asset_nee)
    _check(doc.docstatus == 1 and doc.asset_category == cv.CATEGORIE_ASSET,
           "Immobilisation soumise dans la catégorie « Cheptel reproducteur »", results)
    _check(doc.id_animal == nee_ici,
           "L'immobilisation pointe vers l'animal (clé d'idempotence)", results)
    nom_metier_nee = frappe.db.get_value("Animal", nee_ici, "nom_metier")
    _check(bool(nom_metier_nee) and doc.asset_name == f"Vache {nom_metier_nee}",
           f"asset_name porte le N° travail ({doc.asset_name})", results)
    _check(flt(doc.gross_purchase_amount) == forfait
           and flt(doc.opening_accumulated_depreciation) == 0,
           "Vêlage il y a 6 mois → aucune annuité déjà courue", results)
    _check(doc.finance_books[0].total_number_of_depreciations == duree,
           f"Amortissement sur la durée configurée ({duree} ans)", results)

    asset_achetee = cv.creer_actif_cheptel(achetee)
    reprise = frappe.get_doc("Asset", asset_achetee)
    attendu = round(4000 * 2 / duree, 3)
    _check(abs(flt(reprise.opening_accumulated_depreciation) - attendu) < 0.01,
           f"Vêlage il y a 30 mois → 2 annuités d'ouverture ({attendu} TND)", results)
    _check(reprise.opening_number_of_booked_depreciations == 2,
           "Nombre d'annuités déjà courues transmis à ERPNext", results)

    # ── 4bis. TASK A1 : l'asset_name suit le N° travail
    # Rename (boucle changée — Administrator est System Manager, autorisé)
    nouveau_tn = f"{PREFIXE_TN}801"
    frappe.rename_doc("Animal", nee_ici, nouveau_tn)
    nee_ici = nouveau_tn
    frappe.db.commit()
    _check(frappe.db.get_value("Asset", asset_nee, "asset_name")
           == f"Vache {nouveau_tn[-4:]}",
           "Rename de l'animal → asset_name propagé (after_rename)", results)
    # Changement d'identification_fr → nom_metier change → asset retitré
    animal_doc = frappe.get_doc("Animal", nee_ici)
    animal_doc.identification_fr = "9988001177"
    animal_doc.save(ignore_permissions=True)
    _check(frappe.db.get_value("Asset", asset_nee, "asset_name") == "Vache 1177",
           "Changement d'identification_fr → asset_name resynchronisé (on_update)",
           results)

    # ── 5/6. Idempotence et éligibilité
    _check(cv.creer_actif_cheptel(nee_ici) == asset_nee,
           "Re-création = la même immobilisation (une vache, une Asset)", results)
    _check(cv.creer_actif_cheptel(genisse) is None,
           "Une GENISSE n'entre pas à l'actif (pas encore productive)", results)
    _check(cv.creer_actif_cheptel(vieille) is None,
           f"Vache au-delà de {duree} ans de production → hors périmètre", results)
    eligibles = cv.animaux_eligibles()
    _check(nee_ici in eligibles and genisse not in eligibles,
           "animaux_eligibles ne retient que les VACHE actives", results)

    # ── 7. Valeur du cheptel
    valeur = cv.valeur_cheptel()
    _check(valeur["effectif"] >= 2 and valeur["brut"] >= forfait + 4000,
           f"valeur_cheptel : {valeur['effectif']} têtes, brut {valeur['brut']} TND",
           results)
    _check(abs(valeur["brut"] - valeur["amortissements"] - valeur["net"]) < 0.02,
           "brut − amortissements = VNC", results)

    # ── 8. Sortie de l'animal → mise au rebut
    animal = frappe.get_doc("Animal", achetee)
    animal.statut = "VENDU"
    animal.date_sortie = str(add_days(today(), -1))
    animal.prix_vente = 3000
    animal.flags.ignore_validate = True
    animal.save(ignore_permissions=True)
    frappe.db.commit()
    statut_asset = frappe.db.get_value("Asset", asset_achetee, "status")
    _check(statut_asset == "Scrapped",
           f"Vente de l'animal → immobilisation mise au rebut ({statut_asset})", results)
    _check(frappe.db.get_value("Animal", achetee, "statut") == "VENDU",
           "La sortie de l'animal est enregistrée quoi qu'il arrive (CF-FIN-33)",
           results)
    apres = cv.valeur_cheptel()
    _check(apres["effectif"] == valeur["effectif"] - 1,
           "L'animal sorti quitte l'actif immobilisé", results)

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
