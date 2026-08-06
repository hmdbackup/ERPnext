"""
FIN-B1 / FIN-S94 — tests de l'historisation stricte des recettes lait :
le Decompte Lait Mensuel fige le règlement d'une période, ACHETEUR PAR
ACHETEUR.

Couvre :
  1. generate_milk_invoice crée + soumet le décompte de la période :
     volumes, TB/TP pondérés, grille, décomposition du prix (base + prime
     qualité + prime quantité VOLUME), facture liée émise au prix_final
  2. Instantané figé : modifier un décompte soumis est rejeté (docstatus 1) ;
     modifier la grille référencée est rejeté (ERR-GRL-06)
  3. `ecart_lait` lit le prix figé du décompte pour une période clôturée
     (désactiver la grille ne change plus le KPI) ; repli LIVE sinon
  4. Ajustement manuel : brouillon saisi avant facturation (motif obligatoire,
     ERR-DLM-02) → retrouvé, conservé, répercuté sur le taux de la facture
  5. Idempotence : re-run → même facture, un seul décompte
  6. Garde-fous : ERR-DLM-01 (période incohérente), ERR-DLM-04 (chevauchement)
  7. ERR-DLM-06 : soumettre un décompte sans facture est bloqué (hors flux
     de facturation) — il doit rester en brouillon
  8. ERR-DLM-05 : un brouillon aux bornes différentes de la période facturée
     n'est jamais réutilisé — erreur explicite et actionnable
  9. Annulation décompte + facture → re-run regénère un décompte NEUF
     (nom au compteur DLM-{debut}-{##}) et une nouvelle facture
 10. FIN-S94 — plusieurs acheteurs : la ventilation journalière alimente le
     total `lait_vendu`, la facturation produit UN décompte + UNE facture par
     acheteur (volume et bonus quantité propres à chacun), deux décomptes du
     même mois pour deux acheteurs coexistent (ERR-DLM-04 scopé) mais un
     second décompte pour LE MÊME acheteur est refusé, et `ecart_lait`
     valorise au prix moyen PONDÉRÉ PAR LES VOLUMES

Les sections 1 à 9 servent aussi de non-régression mono-acheteur : sans
ventilation, tout se passe comme avant (un seul acheteur, celui de
`client_lait_defaut`).

Pré-requis site : setup.finance.socle_comptable + setup.finance.recettes.

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_decompte_lait.run
"""
import traceback

import frappe

from hmd_agro.hmd_agro.utils import facturation_lait, finance_kpis

PREFIXE = "ZZTEST Decompte"
# Fenêtre 2035, hors de toute donnée réelle (2031 = test_recettes,
# 2032 = test_finance_kpis, 2033/2034 = test_grille_lait).
GRILLE_DEBUT = "2035-01-01"
GRILLE_FIN = "2035-12-31"
P1_DEBUT, P1_FIN = "2035-03-01", "2035-03-31"
P2_DEBUT, P2_FIN = "2035-04-01", "2035-04-30"
# FIN-S94 — la période multi-acheteurs
P3_DEBUT, P3_FIN = "2035-09-01", "2035-09-30"
ACHETEUR_A = "Centrale Laitière"
ACHETEUR_B = "Client Divers"
ACHETEUR_C = "ZZTEST Acheteur C"

_SUSPENDUES = []


def _suspendre_grilles_reelles():
    _SUSPENDUES.clear()
    for name in frappe.get_all("Grille Prix Lait",
                               filters={"active": 1,
                                        "nom_grille": ["not like", "ZZTEST%"]},
                               pluck="name"):
        _SUSPENDUES.append(name)
        frappe.db.set_value("Grille Prix Lait", name, "active", 0,
                            update_modified=False)
    frappe.db.commit()


def _restaurer_grilles_reelles():
    for name in _SUSPENDUES:
        frappe.db.set_value("Grille Prix Lait", name, "active", 1,
                            update_modified=False)
    _SUSPENDUES.clear()
    frappe.db.commit()


def _hard_delete_si(name):
    """Test-only teardown: strip GL/SLE then hard-delete the invoice."""
    frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", name)
    frappe.db.sql("DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no=%s", name)
    frappe.db.sql("DELETE FROM `tabSales Invoice Item` WHERE parent=%s", name)
    frappe.db.sql("DELETE FROM `tabSales Taxes and Charges` WHERE parent=%s", name)
    frappe.db.sql("DELETE FROM `tabSales Invoice` WHERE name=%s", name)


def _cleanup():
    for debut in (P1_DEBUT, P2_DEBUT, P3_DEBUT):
        for si in frappe.get_all(
                "Sales Invoice",
                filters={"remarks": ["like", f"%LAIT_FACT_{debut}%"]},
                pluck="name"):
            _hard_delete_si(si)
    # Décomptes d'abord (une grille référencée refuse sa suppression),
    # hard delete SQL — docstatus 1 ne s'efface pas par l'API.
    frappe.db.sql("""DELETE FROM `tabDecompte Lait Mensuel`
                     WHERE periode_debut BETWEEN %s AND %s""",
                  (GRILLE_DEBUT, GRILLE_FIN))
    for name in frappe.get_all("Grille Prix Lait",
                               filters={"nom_grille": ["like", f"{PREFIXE}%"]},
                               pluck="name"):
        frappe.delete_doc("Grille Prix Lait", name, force=True,
                          ignore_permissions=True)
    # La ventilation est une table enfant : la purger AVANT le parent, sinon
    # des lignes orphelines survivent au DELETE SQL (FIN-S94).
    if frappe.db.table_exists("Bilan Lait Vente"):
        frappe.db.sql("""DELETE v FROM `tabBilan Lait Vente` v
                         JOIN `tabBilan Lait Journalier` b ON b.name = v.parent
                         WHERE b.date BETWEEN %s AND %s""",
                      (GRILLE_DEBUT, GRILLE_FIN))
    frappe.db.sql("DELETE FROM `tabBilan Lait Journalier` WHERE date BETWEEN %s AND %s",
                  (GRILLE_DEBUT, GRILLE_FIN))
    frappe.db.commit()
    # Le 3e acheteur n'est qu'un figurant du test : on le retire s'il est
    # libre (commit d'abord, pour ne rien perdre si la suppression échoue).
    # Les acheteurs du socle (Centrale Laitière, Client Divers) restent.
    for nom in frappe.get_all("Customer",
                              filters={"name": ["like", "ZZTEST%"]},
                              pluck="name"):
        try:
            frappe.delete_doc("Customer", nom, force=True, ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            # Un document s'y est accroché : on le laisse, ce n'est pas grave.
            frappe.db.rollback()
    _restaurer_grilles_reelles()


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _throws(fn, code, msg, results):
    try:
        fn()
        _check(False, f"{msg} (aucune exception)", results)
    except Exception as exc:
        _check(code in str(exc), f"{msg} → {code}", results)


def _customer(nom):
    """Les clients ne se suppriment pas (des factures s'y accrochent) — on
    garantit seulement leur présence."""
    if not frappe.db.exists("Customer", nom):
        frappe.get_doc({"doctype": "Customer", "customer_name": nom,
                        "customer_type": "Company"}).insert(ignore_permissions=True)
    return nom


def _blj(date, production, vendu=0, tb=None, tp=None, ventes=None):
    """`ventes` = [(acheteur, litres), …] — la ventilation FIN-S94. Quand elle
    est fournie, `lait_vendu` est recalculé par le contrôleur : on le laisse
    à 0 pour vérifier justement qu'il devient la somme de la table."""
    return frappe.get_doc({
        "doctype": "Bilan Lait Journalier", "date": date,
        "production_totale_saisie": production, "lait_vendu": vendu,
        "consommation_interne": 0, "lait_veau": 0,
        "taux_tb_moyen": tb or 0, "taux_tp_moyen": tp or 0,
        "ventes": [{"acheteur": acheteur, "litres": litres}
                   for acheteur, litres in (ventes or [])],
    }).insert(ignore_permissions=True)


def _une_facture(resultat):
    """FIN-S94 — `generate_milk_invoice` rend désormais LA LISTE des factures
    (une par acheteur). Les scénarios mono-acheteur n'en attendent qu'une."""
    return resultat[0] if resultat else None


def run():
    print("\n" + "=" * 70)
    print("  FIN-B1 — Décompte lait mensuel (historisation stricte)")
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
    _suspendre_grilles_reelles()

    # Grille 2035 : TB ≥ 4.0 → +0.060 ; bonus quantité ≥ 10 000 L/mois → +0.020
    grille = frappe.get_doc({
        "doctype": "Grille Prix Lait",
        "nom_grille": f"{PREFIXE} 2035",
        "statut": "VALIDEE", "active": 1,
        "date_debut": GRILLE_DEBUT, "date_fin": GRILLE_FIN,
        "prix_base": 1.500, "tb_reference": 3.8, "tp_reference": 3.2,
        "paliers": [
            {"critere": "TB", "borne_min": 4.0, "borne_max": None, "prime": 0.060},
            {"critere": "VOLUME", "borne_min": 10000, "borne_max": None, "prime": 0.020},
        ],
    }).insert(ignore_permissions=True)

    # ── 1. Décompte créé + figé par la facturation
    _blj(P1_DEBUT, production=6100, vendu=6000, tb=4.1)
    _blj("2035-03-02", production=6000, vendu=6000, tb=4.1)
    frappe.db.commit()

    si_name = _une_facture(facturation_lait.generate_milk_invoice(P1_DEBUT, P1_FIN))
    _check(bool(si_name), f"Facture lait créée ({si_name})", results)
    _check(frappe.db.get_value("Sales Invoice", si_name, "customer")
           == facturation_lait.client_lait_defaut(),
           "Sans ventilation → acheteur par défaut (config client_lait_defaut)",
           results)

    fige = facturation_lait.existing_decompte(P1_DEBUT, P1_FIN)
    _check(bool(fige), f"Décompte soumis pour la période ({fige and fige.name})",
           results)
    dlm = frappe.get_doc("Decompte Lait Mensuel", fige.name)
    _check(dlm.docstatus == 1, "Décompte figé (docstatus 1)", results)
    _check(dlm.facture == si_name, "Décompte lié à la facture", results)
    _check(abs(dlm.volume_litres - 12000) < 0.01,
           f"Volume figé = {dlm.volume_litres} L (attendu 12000)", results)
    _check(abs(dlm.tb_moyen - 4.1) < 0.01,
           f"TB pondéré figé = {dlm.tb_moyen} %", results)
    _check(dlm.grille == grille.name, "Grille appliquée tracée", results)
    _check(abs(dlm.prime_qualite - 0.060) < 0.0005,
           f"Prime qualité TB = {dlm.prime_qualite}", results)
    _check(abs(dlm.prime_quantite - 0.020) < 0.0005,
           f"Bonus quantité (12000 L ≥ 10000) = {dlm.prime_quantite}", results)
    _check(abs(dlm.prix_final - 1.580) < 0.0005,
           f"Prix final = base + qualité + quantité = {dlm.prix_final}", results)
    si = frappe.get_doc("Sales Invoice", si_name)
    _check(abs(si.items[0].rate - dlm.prix_final) < 0.0005,
           f"Facture émise au prix_final du décompte ({si.items[0].rate})", results)
    _check(abs(dlm.montant - 12000 * 1.580) < 0.01,
           f"Montant = volume × prix_final ({dlm.montant})", results)

    # ── 2. Instantané immuable
    def _modifier_decompte():
        doc = frappe.get_doc("Decompte Lait Mensuel", dlm.name)
        doc.prix_base = 9
        doc.save(ignore_permissions=True)

    _throws(_modifier_decompte, "", "Décompte soumis non modifiable", results)

    def _modifier_grille():
        doc = frappe.get_doc("Grille Prix Lait", grille.name)
        doc.prix_base = 1.700
        doc.save(ignore_permissions=True)

    _throws(_modifier_grille, "ERR-GRL-06",
            "Grille référencée par le décompte figée", results)

    # ── 3. ecart_lait lit le prix figé
    ec = finance_kpis.ecart_lait(P1_DEBUT, P1_FIN)
    _check(ec["prix_source"] == "DECOMPTE" and ec["decompte"] == dlm.name,
           f"Période clôturée → prix du décompte ({ec['prix_source']})", results)
    _check(abs(ec["prix_litre"] - 1.580) < 0.0005,
           f"Prix du litre = prix_final figé ({ec['prix_litre']})", results)
    _check(abs(ec["valeur"] - 100 * 1.580) < 0.01,
           f"Écart valorisé au prix figé ({ec['valeur']} TND)", results)
    # Couper la grille ne réécrit plus l'histoire : le KPI ne bouge pas.
    frappe.db.set_value("Grille Prix Lait", grille.name, "active", 0,
                        update_modified=False)
    ec2 = finance_kpis.ecart_lait(P1_DEBUT, P1_FIN)
    _check(abs(ec2["prix_litre"] - 1.580) < 0.0005,
           "Grille désactivée → le KPI de la période clôturée ne bouge pas",
           results)
    frappe.db.set_value("Grille Prix Lait", grille.name, "active", 1,
                        update_modified=False)
    # Période jamais décomptée → calcul en direct assumé
    vivant = finance_kpis.ecart_lait("2035-05-01", "2035-05-31")
    _check(vivant["prix_source"] == "LIVE",
           "Période jamais décomptée → repli calcul en direct (LIVE)", results)

    # ── 4. Ajustement manuel : brouillon avant facturation
    _throws(lambda: frappe.get_doc({
        "doctype": "Decompte Lait Mensuel",
        "periode_debut": P2_DEBUT, "periode_fin": P2_FIN,
        "ajustement_manuel": -0.050,
    }).insert(ignore_permissions=True),
        "ERR-DLM-02", "Ajustement sans motif refusé", results)

    brouillon = frappe.get_doc({
        "doctype": "Decompte Lait Mensuel",
        "periode_debut": P2_DEBUT, "periode_fin": P2_FIN,
        "ajustement_manuel": -0.050,
        "ajustement_motif": "Retenue qualité négociée avec la centrale (avril).",
    }).insert(ignore_permissions=True)
    _check(brouillon.docstatus == 0, "Brouillon d'ajustement saisi avant "
           "facturation", results)

    _blj(P2_DEBUT, production=5000, vendu=5000, tb=4.1)   # < 10000 L : pas de bonus
    frappe.db.commit()
    si2_name = _une_facture(facturation_lait.generate_milk_invoice(P2_DEBUT, P2_FIN))
    dlm2 = frappe.get_doc("Decompte Lait Mensuel", brouillon.name)
    _check(dlm2.docstatus == 1 and dlm2.facture == si2_name,
           "Le brouillon est retrouvé, complété et figé avec la facture", results)
    _check(abs(dlm2.ajustement_manuel + 0.050) < 0.0005,
           "L'ajustement saisi en brouillon est conservé", results)
    _check(abs(dlm2.prime_quantite) < 0.0005,
           "5000 L sous le seuil → pas de bonus quantité", results)
    _check(abs(dlm2.prix_final - 1.510) < 0.0005,
           f"Prix final = 1.500 + 0.060 − 0.050 = {dlm2.prix_final}", results)
    si2 = frappe.get_doc("Sales Invoice", si2_name)
    _check(abs(si2.items[0].rate - 1.510) < 0.0005,
           f"L'ajustement se répercute sur le taux facturé ({si2.items[0].rate})",
           results)

    # ── 5. Idempotence
    again = _une_facture(facturation_lait.generate_milk_invoice(P1_DEBUT, P1_FIN))
    _check(again == si_name, "Re-run → même facture (décompte figé prioritaire)",
           results)
    count = len(frappe.get_all("Decompte Lait Mensuel",
                filters={"periode_debut": P1_DEBUT, "docstatus": ["<", 2]}))
    _check(count == 1, f"Un seul décompte pour la période (count={count})",
           results)

    # ── 6. Garde-fous
    _throws(lambda: frappe.get_doc({
        "doctype": "Decompte Lait Mensuel",
        "periode_debut": "2035-06-30", "periode_fin": "2035-06-01",
    }).insert(ignore_permissions=True),
        "ERR-DLM-01", "Fin de période avant le début refusée", results)
    # Chevauchement : désormais scopé par acheteur (FIN-S94) — c'est le même
    # acheteur qui déclenche le refus.
    _throws(lambda: frappe.get_doc({
        "doctype": "Decompte Lait Mensuel",
        "periode_debut": "2035-03-15", "periode_fin": "2035-04-15",
        "acheteur": dlm.acheteur,
    }).insert(ignore_permissions=True),
        "ERR-DLM-04", "Chevauchement pour le MÊME acheteur refusé", results)

    # ── 7. ERR-DLM-06 : soumettre sans facture est bloqué
    sans_facture = frappe.get_doc({
        "doctype": "Decompte Lait Mensuel",
        "periode_debut": "2035-07-01", "periode_fin": "2035-07-31",
    }).insert(ignore_permissions=True)
    _throws(sans_facture.submit, "ERR-DLM-06",
            "Soumission manuelle d'un décompte sans facture refusée", results)
    doc = frappe.get_doc("Decompte Lait Mensuel", sans_facture.name)
    _check(doc.docstatus == 0, "Le décompte sans facture reste en brouillon",
           results)
    frappe.delete_doc("Decompte Lait Mensuel", sans_facture.name,
                      force=True, ignore_permissions=True)

    # ── 8. ERR-DLM-05 : brouillon aux bornes différentes jamais réutilisé
    partiel = frappe.get_doc({
        "doctype": "Decompte Lait Mensuel",
        "periode_debut": "2035-08-01", "periode_fin": "2035-08-15",
    }).insert(ignore_permissions=True)
    _blj("2035-08-02", production=3000, vendu=3000, tb=4.1)
    frappe.db.commit()
    _throws(lambda: facturation_lait.generate_milk_invoice(
        "2035-08-01", "2035-08-31"),
        "ERR-DLM-05",
        "Brouillon partiel (bornes différentes) → erreur explicite", results)
    _check(str(frappe.db.get_value("Decompte Lait Mensuel", partiel.name,
                                   "periode_fin")) == "2035-08-15",
           "Le brouillon partiel n'a pas été écrasé (bornes intactes)", results)
    frappe.delete_doc("Decompte Lait Mensuel", partiel.name,
                      force=True, ignore_permissions=True)

    # ── 9. Annulation décompte + facture → re-run crée un décompte NEUF
    ancien_dlm, ancienne_si = dlm.name, si_name
    frappe.get_doc("Decompte Lait Mensuel", ancien_dlm).cancel()
    frappe.get_doc("Sales Invoice", ancienne_si).cancel()
    frappe.db.commit()
    si3_name = _une_facture(facturation_lait.generate_milk_invoice(P1_DEBUT, P1_FIN))
    _check(bool(si3_name) and si3_name != ancienne_si,
           f"Nouvelle facture après annulation ({si3_name})", results)
    fige3 = facturation_lait.existing_decompte(P1_DEBUT, P1_FIN)
    _check(bool(fige3) and fige3.name != ancien_dlm,
           f"Décompte NEUF au compteur ({fige3 and fige3.name} ≠ {ancien_dlm})",
           results)
    _check(bool(fige3) and fige3.facture == si3_name,
           "Le nouveau décompte est lié à la nouvelle facture", results)

    # ── 10. FIN-S94 — plusieurs acheteurs sur le même mois
    _customer(ACHETEUR_A)
    _customer(ACHETEUR_B)
    _customer(ACHETEUR_C)
    # Deux jours ventilés : A prend 12 000 L (au-dessus du seuil de bonus
    # quantité), B en prend 4 000 (en dessous). 100 L s'écartent le 1er jour.
    blj1 = _blj(P3_DEBUT, production=8100, tb=4.1,
                ventes=[(ACHETEUR_A, 6000), (ACHETEUR_B, 2000)])
    _blj("2035-09-02", production=8000, tb=4.1,
         ventes=[(ACHETEUR_A, 6000), (ACHETEUR_B, 2000)])
    frappe.db.commit()

    _check(abs(blj1.lait_vendu - 8000) < 0.01,
           f"`lait_vendu` = somme de la ventilation ({blj1.lait_vendu} L)",
           results)
    _check(abs(blj1.ecart_litres - 100) < 0.01,
           f"L'écart reste calculé sur le total vendu ({blj1.ecart_litres} L)",
           results)
    _throws(lambda: _blj("2035-09-03", production=100,
                         ventes=[(ACHETEUR_A, 50), (ACHETEUR_A, 50)]),
            "ERR-BLJ-02",
            "Deux lignes pour le même acheteur le même jour refusées", results)

    factures = facturation_lait.generate_milk_invoice(P3_DEBUT, P3_FIN)
    _check(len(factures) == 2,
           f"Une facture par acheteur ({len(factures)} facture(s))", results)
    clients = sorted(frappe.db.get_value("Sales Invoice", f, "customer")
                     for f in factures)
    _check(clients == sorted([ACHETEUR_A, ACHETEUR_B]),
           f"Les deux acheteurs sont facturés ({', '.join(clients)})", results)

    dlm_a = facturation_lait.existing_decompte(P3_DEBUT, P3_FIN, acheteur=ACHETEUR_A)
    dlm_b = facturation_lait.existing_decompte(P3_DEBUT, P3_FIN, acheteur=ACHETEUR_B)
    _check(bool(dlm_a) and bool(dlm_b) and dlm_a.name != dlm_b.name,
           "Deux décomptes distincts pour le même mois — un par acheteur",
           results)
    doc_a = frappe.get_doc("Decompte Lait Mensuel", dlm_a.name)
    doc_b = frappe.get_doc("Decompte Lait Mensuel", dlm_b.name)
    _check(abs(doc_a.volume_litres - 12000) < 0.01
           and abs(doc_b.volume_litres - 4000) < 0.01,
           f"Chaque décompte porte le volume de son acheteur "
           f"({doc_a.volume_litres} / {doc_b.volume_litres} L)", results)
    _check(abs(doc_a.prix_final - 1.580) < 0.0005,
           f"A : base 1.500 + TB 0.060 + bonus quantité 0.020 = "
           f"{doc_a.prix_final}", results)
    _check(abs(doc_b.prix_final - 1.560) < 0.0005,
           f"B : sous le seuil de bonus → {doc_b.prix_final}", results)
    facture_a = frappe.get_doc("Sales Invoice", doc_a.facture)
    _check(abs(facture_a.items[0].qty - 12000) < 0.01
           and abs(facture_a.items[0].rate - 1.580) < 0.0005,
           "La facture de A reprend son volume et son prix", results)

    # Un troisième acheteur peut être décompté sur le même mois…
    try:
        dlm_c = frappe.get_doc({
            "doctype": "Decompte Lait Mensuel",
            "periode_debut": P3_DEBUT, "periode_fin": P3_FIN,
            "acheteur": ACHETEUR_C,
        }).insert(ignore_permissions=True)
        _check(True, "Un décompte pour un 3e acheteur coexiste sur le même "
                     "mois (ERR-DLM-04 scopé)", results)
        frappe.delete_doc("Decompte Lait Mensuel", dlm_c.name, force=True,
                          ignore_permissions=True)
    except Exception as exc:
        _check(False, f"Décompte d'un autre acheteur refusé à tort : {exc}",
               results)
    # …mais pas un second décompte pour un acheteur déjà réglé.
    _throws(lambda: frappe.get_doc({
        "doctype": "Decompte Lait Mensuel",
        "periode_debut": P3_DEBUT, "periode_fin": P3_FIN,
        "acheteur": ACHETEUR_A,
    }).insert(ignore_permissions=True),
        "ERR-DLM-04", "Second décompte pour un acheteur déjà réglé refusé",
        results)

    # Prix moyen PONDÉRÉ par les volumes : (12000×1.580 + 4000×1.560)/16000
    ec3 = finance_kpis.ecart_lait(P3_DEBUT, P3_FIN)
    _check(ec3["prix_source"] == "DECOMPTE" and len(ec3["decomptes"]) == 2,
           f"Les deux décomptes de la période sont retenus "
           f"({ec3['decompte']})", results)
    _check(abs(ec3["prix_litre"] - 1.575) < 0.0005,
           f"Prix pondéré par les volumes = {ec3['prix_litre']} "
           f"(moyenne simple : 1.570)", results)
    _check(abs(ec3["valeur"] - 100 * 1.575) < 0.01,
           f"Écart valorisé au prix moyen pondéré ({ec3['valeur']} TND)",
           results)

    # Idempotence multi-acheteurs : re-run → les deux mêmes factures.
    encore = facturation_lait.generate_milk_invoice(P3_DEBUT, P3_FIN)
    _check(sorted(encore) == sorted(factures),
           "Re-run multi-acheteurs → les mêmes factures, aucun doublon",
           results)

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
