"""
FIN-S70 (RG-FIN-70) — Contrôle de cohérence finance.

Tous les chiffres du module finance venaient jusqu'ici d'un jeu de données
seedé. Ce rapport est l'outil qui permet de le brancher sur **n'importe quelle
base** — en particulier une restauration de la production — et de savoir en
une lecture si les données tiennent debout : socle en place, Grand Livre
équilibré, lait produit ↔ lait facturé, coûts valorisés, masse salariale
postée, immobilisations amorties, sorties d'animaux facturées.

Chaque ligne est un contrôle indépendant, avec trois issues :
    OK       le contrôle passe
    ALERTE   anomalie probable — à regarder, pas bloquant
    ERREUR   incohérence certaine — le chiffre publié est faux

Aucun contrôle n'écrit quoi que ce soit : lecture seule, rejouable à volonté.

Utilisation :
  • Desk → Rapport « Controle Coherence Finance » (filtres de période)
  • Console, pour une restauration de production :
        bench --site <site> execute \\
            hmd_agro.hmd_agro.report.controle_coherence_finance.\\
controle_coherence_finance.run --kwargs "{'date_debut':'2026-01-01','date_fin':'2026-12-31'}"
"""
import frappe
from frappe.utils import flt, get_first_day, get_last_day, getdate, today

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

OK, ALERTE, ERREUR = "OK", "ALERTE", "ERREUR"
INDICATEURS = {OK: "Green", ALERTE: "Orange", ERREUR: "Red"}

COMPTES_REQUIS = [
    ("101", "Capital"), ("701", "Ventes de lait"), ("601", "Consommation aliments"),
    ("615", "Entretien et réparations"), ("640", "Salaires"),
    ("647", "Charges sociales"), ("421", "Rémunérations dues"),
    ("453", "Organismes sociaux"), ("681", "Dotations amortissements"),
]
ATELIERS_REQUIS = ["Lait", "Élevage - Génisses", "Cultures - Fourrage",
                   "Traction", "Frais Généraux"]


def execute(filters=None):
    filters = filters or {}
    debut = getdate(filters.get("date_debut") or get_first_day(today()))
    fin = getdate(filters.get("date_fin") or get_last_day(today()))
    if fin < debut:
        debut, fin = fin, debut

    columns = [
        {"fieldname": "domaine", "label": "Domaine", "fieldtype": "Data", "width": 150},
        {"fieldname": "controle", "label": "Contrôle", "fieldtype": "Data", "width": 330},
        {"fieldname": "statut", "label": "Statut", "fieldtype": "Data", "width": 90},
        {"fieldname": "valeur", "label": "Valeur", "fieldtype": "Data", "width": 140},
        {"fieldname": "detail", "label": "Détail / action", "fieldtype": "Data", "width": 560},
    ]

    ctx = {"debut": str(debut), "fin": str(fin),
           "jours": (fin - debut).days + 1}

    data = []
    for section in (_socle, _grand_livre, _lait, _couts, _personnel,
                    _immobilisations, _troupeau):
        try:
            data.extend(section(ctx))
        except Exception:
            frappe.log_error(title=f"ERR-CTL-01 {section.__name__}",
                             message=frappe.get_traceback())
            data.append(_ligne(section.__name__, "Section non exécutée", ERREUR,
                               "exception",
                               "Voir Error Log — le contrôle lui-même a échoué."))

    data.insert(0, _synthese(data, ctx))
    return columns, data


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _ligne(domaine, controle, statut, valeur="", detail=""):
    return {"domaine": domaine, "controle": controle, "statut": statut,
            "valeur": str(valeur), "detail": detail,
            "indicator": INDICATEURS.get(statut, "")}


def _verdict(condition_ok, condition_alerte=False):
    if condition_ok:
        return OK
    return ALERTE if condition_alerte else ERREUR


def _synthese(data, ctx):
    erreurs = sum(1 for d in data if d["statut"] == ERREUR)
    alertes = sum(1 for d in data if d["statut"] == ALERTE)
    statut = ERREUR if erreurs else (ALERTE if alertes else OK)
    return _ligne(
        "SYNTHÈSE", f"Période {ctx['debut']} → {ctx['fin']} ({ctx['jours']} j)",
        statut, f"{erreurs} erreur(s), {alertes} alerte(s)",
        f"{len(data)} contrôles exécutés sur la société « {COMPANY} ».",
    )


def _acc(number):
    return frappe.db.get_value("Account", {"company": COMPANY, "account_number": number})


# ─── 1. Socle comptable ──────────────────────────────────────────────────────

def _socle(ctx):
    lignes = []

    if not frappe.db.exists("Company", COMPANY):
        return [_ligne("Socle", f"Société « {COMPANY} »", ERREUR, "absente",
                       "Lancer setup.finance.socle_comptable.setup_socle_comptable.")]
    devise = frappe.db.get_value("Company", COMPANY, "default_currency")
    lignes.append(_ligne("Socle", "Devise de la société", _verdict(devise == "TND"),
                         devise, "Le plan SCE et tous les seuils sont en TND."))

    manquants = [f"{n} ({lib})" for n, lib in COMPTES_REQUIS if not _acc(n)]
    lignes.append(_ligne(
        "Socle", "Comptes SCE indispensables",
        _verdict(not manquants), f"{len(COMPTES_REQUIS) - len(manquants)}/{len(COMPTES_REQUIS)}",
        "Manquants : " + ", ".join(manquants) if manquants
        else "Tous présents (capital, ventes, achats, paie, entretien, dotations)."))

    abbr = frappe.db.get_value("Company", COMPANY, "abbr")
    absents = [a for a in ATELIERS_REQUIS
               if not frappe.db.exists("Cost Center", f"{a} - {abbr}")]
    lignes.append(_ligne(
        "Socle", "Ateliers analytiques (Cost Centers)", _verdict(not absents),
        f"{len(ATELIERS_REQUIS) - len(absents)}/{len(ATELIERS_REQUIS)}",
        "Manquants : " + ", ".join(absents) if absents
        else "Toute charge peut être imputée à un atelier (RG-FIN-40)."))

    exercice = frappe.db.exists("Fiscal Year", {
        "year_start_date": ("<=", ctx["debut"]), "year_end_date": (">=", ctx["fin"])})
    lignes.append(_ligne(
        "Socle", "Exercice fiscal couvrant la période", _verdict(bool(exercice)),
        exercice or "aucun",
        "Sans exercice couvrant la période, aucune écriture ne peut être postée."))
    return lignes


# ─── 2. Grand Livre ──────────────────────────────────────────────────────────

def _grand_livre(ctx):
    lignes = []
    solde = frappe.db.sql("""
        SELECT COALESCE(SUM(debit), 0) AS d, COALESCE(SUM(credit), 0) AS c,
               COUNT(*) AS n
        FROM `tabGL Entry`
        WHERE company = %s AND is_cancelled = 0 AND posting_date BETWEEN %s AND %s
    """, (COMPANY, ctx["debut"], ctx["fin"]), as_dict=True)[0]
    ecart = flt(solde.d) - flt(solde.c)
    lignes.append(_ligne(
        "Grand Livre", "Équilibre débit / crédit de la période",
        _verdict(abs(ecart) < 0.01), f"{ecart:+.3f} TND",
        f"{int(solde.n)} écritures, {flt(solde.d):.2f} DT au débit."))

    if not solde.n:
        lignes.append(_ligne(
            "Grand Livre", "Écritures sur la période", ALERTE, "0",
            "Aucune écriture : période antérieure à la bascule, ou saisie non faite."))
        return lignes

    sans_atelier = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabGL Entry` gle
        JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.company = %s AND gle.is_cancelled = 0
          AND gle.posting_date BETWEEN %s AND %s
          AND acc.root_type = 'Expense' AND IFNULL(gle.cost_center, '') = ''
    """, (COMPANY, ctx["debut"], ctx["fin"]))[0][0]
    lignes.append(_ligne(
        "Grand Livre", "Charges imputées à un atelier",
        _verdict(not sans_atelier, condition_alerte=True), f"{sans_atelier} sans atelier",
        "Une charge sans Cost Center ne remonte dans aucun coût de revient (RG-FIN-40)."
        if sans_atelier else "Toutes les charges de la période portent un atelier."))

    brouillons = frappe.db.count("Journal Entry", {"docstatus": 0, "company": COMPANY})
    lignes.append(_ligne(
        "Grand Livre", "Écritures restées en brouillon",
        _verdict(not brouillons, condition_alerte=True), brouillons,
        "Un brouillon n'existe pas au Grand Livre : les KPI l'ignorent."
        if brouillons else "Aucun brouillon en attente."))
    return lignes


# ─── 3. Lait : produit ↔ facturé ─────────────────────────────────────────────

def _lait(ctx):
    from hmd_agro.hmd_agro.doctype.grille_prix_lait.grille_prix_lait import grille_active
    from hmd_agro.hmd_agro.utils.finance_kpis import ecart_lait, gl_sums

    lignes = []
    blj = frappe.db.sql("""
        SELECT COALESCE(SUM(lait_vendu), 0) AS vendu,
               COALESCE(SUM(production_totale_saisie), 0) AS saisie,
               COUNT(*) AS jours
        FROM `tabBilan Lait Journalier` WHERE date BETWEEN %s AND %s
    """, (ctx["debut"], ctx["fin"]), as_dict=True)[0]
    traites = flt(frappe.db.sql("""
        SELECT COALESCE(SUM(quantite_litres), 0) FROM `tabTraite`
        WHERE date_traite BETWEEN %s AND %s
    """, (ctx["debut"], ctx["fin"]))[0][0])

    # Des jours manquants restent une alerte, jamais une erreur : une période
    # sans bilan est peut-être simplement une période sans activité.
    lignes.append(_ligne(
        "Lait", "Jours de Bilan Lait saisis sur la période",
        _verdict(int(blj.jours) >= ctx["jours"] * 0.9, condition_alerte=True),
        f"{int(blj.jours)}/{ctx['jours']} j",
        "Les jours manquants sortent du CA, de l'écart lait et du prix moyen."))

    ecart_traite = flt(blj.saisie) - traites
    lignes.append(_ligne(
        "Lait", "Bilan Lait ↔ somme des traites",
        _verdict(abs(ecart_traite) < max(1.0, traites * 0.01), condition_alerte=True),
        f"{ecart_traite:+.1f} L",
        f"Production saisie {flt(blj.saisie):.0f} L vs traites {traites:.0f} L."))

    facture = frappe.db.sql("""
        SELECT COALESCE(SUM(sii.qty), 0) AS litres,
               COALESCE(SUM(sii.base_net_amount), 0) AS montant,
               COUNT(DISTINCT si.name) AS n
        FROM `tabSales Invoice Item` sii
        JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE si.docstatus = 1 AND si.company = %s
          AND sii.item_code = 'LAIT-CRU'
          AND si.posting_date BETWEEN %s AND %s
    """, (COMPANY, ctx["debut"], ctx["fin"]), as_dict=True)[0]
    manque = flt(blj.vendu) - flt(facture.litres)
    lignes.append(_ligne(
        "Lait", "Lait vendu (BLJ) ↔ lait facturé",
        _verdict(abs(manque) < max(1.0, flt(blj.vendu) * 0.01),
                 condition_alerte=flt(facture.litres) > 0),
        f"{manque:+.0f} L",
        f"{flt(blj.vendu):.0f} L déclarés vendus, {flt(facture.litres):.0f} L facturés "
        f"sur {int(facture.n)} facture(s)."))

    grille = grille_active(ctx["fin"])
    if not grille:
        lignes.append(_ligne(
            "Lait", "Grille de prix qualité", ALERTE, "aucune",
            "Le litre est payé à un prix plat : le CA lait ignore le TB/TP. "
            "Saisir la grille de la centrale (Grille Prix Lait)."))
    else:
        lignes.append(_ligne(
            "Lait", "Grille de prix qualité",
            _verdict(grille.statut == "VALIDEE", condition_alerte=True),
            grille.statut,
            f"« {grille.name} » base {flt(grille.prix_base):.3f} TND/L, "
            f"{len(grille.paliers or [])} paliers."
            + ("" if grille.statut == "VALIDEE" else
               " Valeurs indicatives — à confirmer avec la centrale puis passer "
               "le statut à VALIDEE.")))

    gl_ = gl_sums(ctx["debut"], ctx["fin"])
    if flt(facture.litres):
        prix_moyen = gl_["ca_lait"] / flt(facture.litres)
        attendu = grille.prix_du_litre() if grille else flt(
            get_config("prix_reference_lait", default=1.6))
        lignes.append(_ligne(
            "Lait", "Prix moyen réalisé vs prix de base",
            _verdict(abs(prix_moyen - attendu) <= max(0.15, attendu * 0.15),
                     condition_alerte=True),
            f"{prix_moyen:.3f} TND/L",
            f"Prix de base attendu {attendu:.3f} TND/L (primes qualité comprises, "
            "l'écart normal reste faible)."))

    ec = ecart_lait(ctx["debut"], ctx["fin"])
    seuil = flt(get_config("ecart_lait_seuil_perte_pct", default=5))
    alarme = flt(get_config("ecart_lait_seuil_alarme_pct", default=10))
    lignes.append(_ligne(
        "Lait", "Écart lait (litres non affectés)",
        _verdict(ec["pct_production"] <= seuil,
                 condition_alerte=ec["pct_production"] <= alarme),
        f"{ec['valeur']:.2f} TND",
        f"{ec['litres_perdus']:.0f} L perdus ({ec['pct_production']:.2f} % de la "
        f"production) valorisés à {ec['prix_litre']:.3f} TND/L. "
        f"Seuils {seuil} % / {alarme} %."))
    if ec["litres_negatifs"]:
        lignes.append(_ligne(
            "Lait", "Écarts lait négatifs (sur-affectation)", ERREUR,
            f"{ec['litres_negatifs']:.0f} L",
            "Vendu + consommation interne + lait veau dépasse la production "
            "saisie : erreur de saisie à corriger."))
    return lignes


# ─── 4. Coûts & valorisation ─────────────────────────────────────────────────

def _couts(ctx):
    lignes = []
    sans_cmp = frappe.db.sql("""
        SELECT COUNT(DISTINCT b.item_code) FROM `tabBin` b
        WHERE b.actual_qty > 0 AND IFNULL(b.valuation_rate, 0) = 0
    """)[0][0]
    lignes.append(_ligne(
        "Coûts", "Articles en stock sans coût unitaire (CMP)",
        _verdict(not sans_cmp, condition_alerte=True), sans_cmp,
        "Un CMP à 0 fait sortir la consommation à 0 : le coût alimentaire est "
        "sous-évalué (FIN-S10)." if sans_cmp
        else "Toutes les consommations sortent valorisées."))

    sle = frappe.db.sql("""
        SELECT COUNT(*) AS n, COALESCE(SUM(ABS(stock_value_difference)), 0) AS val
        FROM `tabStock Ledger Entry`
        WHERE is_cancelled = 0 AND posting_date BETWEEN %s AND %s
    """, (ctx["debut"], ctx["fin"]), as_dict=True)[0]
    lignes.append(_ligne(
        "Coûts", "Mouvements de stock valorisés sur la période",
        _verdict(int(sle.n) == 0 or flt(sle.val) > 0, condition_alerte=True),
        f"{int(sle.n)} mvts / {flt(sle.val):.2f} TND",
        "Des mouvements à valeur nulle signalent des achats sans prix." ))

    distributions = frappe.db.count("Stock Entry", {
        "docstatus": 1, "posting_date": ["between", [ctx["debut"], ctx["fin"]]]})
    lignes.append(_ligne(
        "Coûts", "Sorties de stock enregistrées",
        _verdict(distributions > 0, condition_alerte=True), distributions,
        "Sans distribution d'aliments postée, le coût alimentaire de la période "
        "est nul par construction (FIN-S11)." if not distributions
        else "La distribution alimente le coût réel du litre."))
    return lignes


# ─── 5. Personnel & masse salariale ──────────────────────────────────────────

def _personnel(ctx):
    from hmd_agro.hmd_agro.utils.charges_utils import existing_entry, masse_salariale
    from hmd_agro.hmd_agro.utils.finance_kpis import gl_sums

    lignes = []
    effectif = frappe.db.count("Personnel", {"statut": "ACTIF"})
    lignes.append(_ligne(
        "Personnel", "Registre du personnel renseigné",
        _verdict(effectif > 0, condition_alerte=True), f"{effectif} actif(s)",
        "Sans registre, la masse salariale reste une saisie manuelle et le coût "
        "MO du litre n'a pas de source (FIN-S42)." if not effectif
        else "La masse salariale est reconstruite depuis ce registre."))

    orphelins = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabPersonnel`
        WHERE statut = 'ACTIF' AND IFNULL(atelier, '') = ''
    """)[0][0]
    if effectif:
        lignes.append(_ligne(
            "Personnel", "Salariés rattachés à un atelier",
            _verdict(not orphelins), f"{effectif - orphelins}/{effectif}",
            "Un salarié sans atelier ne peut pas être ventilé (RG-FIN-40)."
            if orphelins else "Chaque salarié porte un atelier d'imputation."))

    # Mois de la période sans écriture de salaires
    manquants, mois = [], _mois_de_la_periode(ctx)
    for periode in mois:
        if not existing_entry(periode):
            manquants.append(periode)
    lignes.append(_ligne(
        "Personnel", "Masse salariale postée pour chaque mois",
        _verdict(not manquants, condition_alerte=bool(effectif)),
        f"{len(mois) - len(manquants)}/{len(mois)} mois",
        ("Mois sans écriture : " + ", ".join(manquants)) if manquants
        else "Chaque mois de la période porte son écriture 640/647."))

    if effectif and mois:
        # Comparé au compte 64x complet : le registre porte le brut ET les
        # charges patronales, comme les débits 640 + 647.
        masse = masse_salariale(mois[0])
        attendu = (sum(masse["salaires"].values())
                   + sum(masse["charges_sociales"].values()))
        gl_mo = gl_sums(f"{mois[0]}-01", str(get_last_day(f"{mois[0]}-01")))["mo"]
        lignes.append(_ligne(
            "Personnel", f"Registre ↔ Grand Livre 64x ({mois[0]})",
            _verdict(gl_mo > 0 and abs(gl_mo - attendu) <= max(1.0, attendu * 0.25),
                     condition_alerte=True),
            f"{gl_mo:.2f} vs {attendu:.2f} TND",
            "Écart entre la masse salariale théorique du registre et ce qui est "
            "réellement comptabilisé sur la période."))
    return lignes


def _mois_de_la_periode(ctx):
    """['2026-06', '2026-07', …] — un libellé par mois civil touché."""
    from frappe.utils import add_months

    fin = getdate(ctx["fin"])
    mois, curseur = [], get_first_day(getdate(ctx["debut"]))
    while curseur <= fin:
        mois.append(f"{curseur.year}-{curseur.month:02d}")
        curseur = getdate(add_months(curseur, 1))
    return mois


# ─── 6. Immobilisations & maintenance ────────────────────────────────────────

def _immobilisations(ctx):
    from hmd_agro.hmd_agro.utils.cheptel_valorisation import (
        MODE_ACTIF, animaux_eligibles, existing_asset, valeur_cheptel,
    )
    from hmd_agro.hmd_agro.utils.maintenance_utils import (
        cout_maintenance, interventions_planifiees,
    )

    lignes = []
    total = frappe.db.count("Asset", {"docstatus": 1, "company": COMPANY})
    sans_amort = frappe.db.count("Asset", {
        "docstatus": 1, "company": COMPANY, "calculate_depreciation": 0})
    lignes.append(_ligne(
        "Immobilisations", "Immobilisations avec plan d'amortissement",
        _verdict(total == 0 or not sans_amort, condition_alerte=True),
        f"{total - sans_amort}/{total}",
        "Une immobilisation sans amortissement ne charge jamais le résultat."
        if sans_amort else "Toutes les immobilisations s'amortissent."))

    maint = cout_maintenance(ctx["debut"], ctx["fin"])
    lignes.append(_ligne(
        "Maintenance", "Interventions saisies sur la période",
        _verdict(maint["interventions"] > 0, condition_alerte=True),
        f"{maint['interventions']} / {maint['cout']:.2f} TND",
        "Aucune intervention enregistrée : on amortit le matériel sans savoir "
        "ce qu'il coûte à entretenir (FIN-S32)." if not maint["interventions"]
        else f"{maint['equipements']} équipement(s) concerné(s)."))

    retard = [t for t in interventions_planifiees(0)
              if t.due_date and getdate(t.due_date) < getdate(today())]
    lignes.append(_ligne(
        "Maintenance", "Tâches de maintenance préventive en retard",
        _verdict(not retard, condition_alerte=True), len(retard),
        ", ".join(f"{t.asset_name} — {t.task_name}" for t in retard[:4])
        if retard else "Aucune échéance dépassée."))

    cheptel = valeur_cheptel(ctx["fin"])
    if cheptel["mode"] != MODE_ACTIF:
        lignes.append(_ligne(
            "Cheptel", "Valorisation du cheptel reproducteur", ALERTE,
            cheptel["mode"],
            "Le troupeau — premier actif de la ferme — n'est ni au bilan ni "
            "amorti. Décision comptable à trancher (HMD Configuration → "
            "Personnel & Cheptel)."))
    else:
        eligibles = animaux_eligibles()
        non_immobilisees = [a for a in eligibles if not existing_asset(a)]
        lignes.append(_ligne(
            "Cheptel", "Vaches en production immobilisées",
            _verdict(not non_immobilisees, condition_alerte=True),
            f"{len(eligibles) - len(non_immobilisees)}/{len(eligibles)}",
            "Lancer cheptel_valorisation.synchroniser_cheptel." if non_immobilisees
            else f"VNC du cheptel : {cheptel['net']:.2f} TND "
                 f"(brut {cheptel['brut']:.2f})."))
    return lignes


# ─── 7. Troupeau ↔ finance ───────────────────────────────────────────────────

def _troupeau(ctx):
    from hmd_agro.hmd_agro.utils.vente_animal import existing_invoice

    lignes = []
    sorties = frappe.get_all(
        "Animal",
        filters={"statut": ["in", ["VENDU", "REFORME"]],
                 "date_sortie": ["between", [ctx["debut"], ctx["fin"]]]},
        fields=["name", "prix_vente"],
    )
    non_facturees = [a.name for a in sorties
                     if flt(a.prix_vente) > 0 and not existing_invoice(a.name)]
    lignes.append(_ligne(
        "Troupeau", "Sorties d'animaux facturées",
        _verdict(not non_facturees), f"{len(sorties) - len(non_facturees)}/{len(sorties)}",
        ("Sans facture : " + ", ".join(non_facturees[:5])) if non_facturees
        else "Chaque sortie valorisée porte sa facture (RG-FIN-20)."))

    sans_prix = [a.name for a in sorties if not flt(a.prix_vente)]
    if sans_prix:
        lignes.append(_ligne(
            "Troupeau", "Sorties sans prix de vente", ALERTE, len(sans_prix),
            "Réformes/morts sans valorisation : " + ", ".join(sans_prix[:5])))

    encore_actifs = frappe.db.sql_list("""
        SELECT a.name FROM `tabAnimal` a
        JOIN `tabAsset` ast ON ast.id_animal = a.name
        WHERE a.statut != 'ACTIF' AND ast.docstatus = 1
          AND ast.status NOT IN ('Scrapped', 'Sold', 'Cancelled')
    """)
    lignes.append(_ligne(
        "Troupeau", "Immobilisations d'animaux sortis",
        _verdict(not encore_actifs), len(encore_actifs),
        ("Encore au bilan : " + ", ".join(encore_actifs[:5])) if encore_actifs
        else "Aucun animal sorti ne reste inscrit à l'actif."))
    return lignes


# ─── Console ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def run(date_debut=None, date_fin=None):
    """Exécution console — sert à valider une base restaurée (production)."""
    _, data = execute({"date_debut": date_debut, "date_fin": date_fin})
    largeur = 132
    print("\n" + "=" * largeur)
    print("  CONTRÔLE DE COHÉRENCE FINANCE")
    print("=" * largeur)
    for ligne in data:
        print(f"  {ligne['statut']:<7} │ {ligne['domaine']:<15} │ "
              f"{ligne['controle'][:44]:<44} │ {ligne['valeur'][:22]:<22}")
        if ligne["statut"] != OK and ligne["detail"]:
            print(f"          └─ {ligne['detail'][:112]}")
    # La ligne de synthèse n'est pas un contrôle : elle les résume.
    controles = [d for d in data if d["domaine"] != "SYNTHÈSE"]
    erreurs = sum(1 for d in controles if d["statut"] == ERREUR)
    alertes = sum(1 for d in controles if d["statut"] == ALERTE)
    print("=" * largeur)
    print(f"  {len(controles)} contrôles — {erreurs} erreur(s), {alertes} alerte(s)")
    print("=" * largeur + "\n")
    return {"controles": len(controles), "erreurs": erreurs, "alertes": alertes}
