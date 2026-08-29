"""
EPIC F — KPI économiques depuis le Grand Livre (FIN-S50, RC-FIN-50/51/52).

One aggregated read over GL Entry for a period, mapped to the SCE classes of
the socle (plan_comptable_sce). Everything is computed from posted GL rows —
frozen history, same stance as the SLE cost rows: a period with no postings
honestly returns 0.

Familles (préfixes account_number SCE) :
    ca_lait            701          (crédit − débit)
    produits           root Income
    charges            root Expense (total)
    charges_financieres 66x
    amortissements     68x
    mo                 64x          (640 salaires + 647 charges patronales)
    entretien          615          (interventions équipements — FIN-S32)
    EBE   = produits − (charges − 66x − 68x)   (avant amort. et financier)
    résultat = produits − charges

`ecart_lait` complète le tableau côté production : les litres écartés étaient
saisis mais jamais chiffrés (FIN-S25).
"""
import frappe

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY


def gl_sums(date_debut, date_fin):
    """Sommes GL de la période par famille SCE. Retourne un dict de floats
    (sens positif = produit pour Income, charge pour Expense)."""
    rows = frappe.db.sql("""
        SELECT acc.account_number AS num, acc.root_type,
               SUM(gle.debit - gle.credit) AS solde_debit
        FROM `tabGL Entry` gle
        JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.company = %s
          AND gle.is_cancelled = 0
          AND gle.posting_date BETWEEN %s AND %s
          AND acc.root_type IN ('Income', 'Expense')
        GROUP BY acc.account_number, acc.root_type
    """, (COMPANY, date_debut, date_fin), as_dict=True)

    out = {
        "ca_lait": 0.0, "produits": 0.0, "charges": 0.0,
        "charges_financieres": 0.0, "amortissements": 0.0, "mo": 0.0,
        "entretien": 0.0,
    }
    for r in rows:
        num = r.num or ""
        solde = float(r.solde_debit or 0)
        if r.root_type == "Income":
            out["produits"] += -solde          # produits sont créditeurs
            if num.startswith("701"):
                out["ca_lait"] += -solde
        else:
            out["charges"] += solde
            if num.startswith("66"):
                out["charges_financieres"] += solde
            elif num.startswith("68"):
                out["amortissements"] += solde
            elif num.startswith("64"):
                out["mo"] += solde
            elif num.startswith("615"):
                out["entretien"] += solde

    out["ebe"] = out["produits"] - (
        out["charges"] - out["charges_financieres"] - out["amortissements"])
    out["resultat"] = out["produits"] - out["charges"]
    return out


# ─── SCRUM-10 — ventilation par atelier ──────────────────────────────────────
#
# Postes de coût dans l'ORDRE demandé en revue reporting : « ration, mécanique,
# personnel, puis amortissements et charges générales ». L'ordre n'est pas
# cosmétique — c'est celui dans lequel le gérant lit son coût de revient, du
# plus pilotable au moins pilotable.
#
# Le préfixe le plus long gagne : 615 est de la mécanique, pas de l'« autre 6 ».
POSTES_CHARGES = (
    ("ration",              "Ration & Aliments (601)",           ("601",)),
    ("sante",               "Santé & Vétérinaire (602)",         ("602",)),
    ("mecanique",           "Mécanique — Entretien (615)",       ("615",)),
    ("personnel",           "Personnel (64x)",                   ("64",)),
    ("amortissements",      "Amortissements (68x)",              ("68",)),
    ("charges_financieres", "Charges financières (66x)",         ("66",)),
    ("autres",              "Autres charges d'exploitation",     ()),
)

# Atelier fourre-tout du plan analytique : une charge sans atelier explicite y
# tombe. Ce n'est PAS un atelier « non imputé » — c'est un vrai centre de coût
# (les charges générales / GNI de la revue), dont une quote-part revient au
# lait. Le vrai « non imputé », c'est une écriture SANS cost center du tout.
ATELIER_FRAIS_GENERAUX = "Frais Généraux"

# L'atelier dont on calcule le coût du litre (nom court du Cost Center).
ATELIER_LAIT = "Lait"

# Périmètre du coût complet au litre. Décidé en revue reporting : atelier Lait
# + quote-part des charges générales. La quote-part est la SOMME des
# répartitions saisies charge par charge (décision 26/08/2026, plus de clé
# calculée) ; le périmètre reste configurable parce que c'est une décision
# métier, pas une constante technique (convention maison : jamais de seuil en
# dur).
PERIMETRES_COUT_LITRE = ("LAIT_QUOTE_PART", "LAIT_SEUL", "TOUTES_CHARGES")

# Parents porteurs de la table enfant `Repartition Atelier Charge` (SCRUM-10).
PARENTS_REPARTITION = ("Purchase Invoice", "Journal Entry")


def _poste_de(num):
    for cle, _libelle, prefixes in POSTES_CHARGES:
        if any(num.startswith(p) for p in prefixes):
            return cle
    return "autres"


def _nom_court(cost_center):
    """« Lait - HMD » → « Lait ». Le suffixe société est du bruit à l'écran."""
    return cost_center.rsplit(" - ", 1)[0] if cost_center else cost_center


def gl_sums_par_atelier(date_debut, date_fin):
    """SCRUM-10 — charges de la période ventilées par ATELIER et par poste.

    `gl_sums` lit le Grand Livre sans jamais regarder le centre de coût : ni
    SELECT, ni filtre, ni GROUP BY. Conséquence, le coût complet au litre
    divisait TOUTES les charges de la ferme — génisses, cultures, traction,
    frais généraux compris — par les SEULS litres de lait. Il était
    structurellement surestimé, et rien ne le disait.

    Cette lecture-ci ajoute l'axe manquant. Elle ne remplace pas `gl_sums` :
    les deux doivent tomber sur le même total, et un test le vérifie.

    Le « non imputé » (écriture sans cost center) reste un poste VISIBLE,
    jamais fondu dans un atelier : une charge dont personne ne sait à quel
    atelier elle appartient est une information, pas un détail à lisser.

    Retourne {
        "ateliers": {nom court: {"total": float, "postes": {cle: float}}},
        "non_impute": {"total": float, "postes": {...}},
        "total": float,
        "postes": [(cle, libellé), ...]   # ordre d'affichage
    }
    """
    rows = frappe.db.sql("""
        SELECT gle.cost_center AS cc, acc.account_number AS num,
               SUM(gle.debit - gle.credit) AS solde
        FROM `tabGL Entry` gle
        JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.company = %s
          AND gle.is_cancelled = 0
          AND gle.posting_date BETWEEN %s AND %s
          AND acc.root_type = 'Expense'
        GROUP BY gle.cost_center, acc.account_number
    """, (COMPANY, date_debut, date_fin), as_dict=True)

    ateliers = {}
    non_impute = {"total": 0.0, "postes": {}}
    total = 0.0

    for r in rows:
        montant = float(r.solde or 0)
        poste = _poste_de(r.num or "")
        total += montant
        cible = non_impute if not r.cc else ateliers.setdefault(
            _nom_court(r.cc), {"total": 0.0, "postes": {}})
        cible["total"] += montant
        cible["postes"][poste] = cible["postes"].get(poste, 0.0) + montant

    return {
        "ateliers": ateliers,
        "non_impute": non_impute,
        "total": round(total, 2),
        "postes": [(cle, libelle) for cle, libelle, _p in POSTES_CHARGES],
    }


def repartitions_frais_generaux(date_debut, date_fin, ventilation=None):
    """SCRUM-10 — the Frais Généraux charges of the period and their
    analytical split by atelier, as typed on each charge.

    Reads the Purchase Invoice lines (submitted, credit notes excluded) and
    the Journal Entry lines (submitted, debit charge lines) booked on Frais
    Généraux, joined to their `Repartition Atelier Charge` parts (`parent`,
    `ligne` = idx). A charge without any part is listed with an empty split:
    it is what separates the GL total of Frais Généraux from the split total,
    and the report must be able to name it.

    `ventilation`: the `gl_sums_par_atelier` result the caller already holds
    (saves a second GL reading); read otherwise.

    Returns {
        "charges": [{voucher_type, voucher, ligne, libelle, compte, poste,
                     montant, repartition: [{atelier, pct, montant}]}],
        "par_atelier": {atelier: montant},
        "par_atelier_postes": {atelier: {poste: montant}},
        "total_reparti": x, "total_fg": y (GL),
        "total_liste": l (Σ of the PI/JE charges listed),
        "autres": y − l (vouchers booked on FG that cannot be listed: stock,
                         credit notes…),
        "non_reparti": l − x (signed, never hidden)
    }
    """
    charges = _charges_frais_generaux(date_debut, date_fin)
    _joindre_repartitions(charges)

    par_atelier, par_atelier_postes = {}, {}
    for charge in charges:
        for part in charge["repartition"]:
            atelier, poste, montant = part["atelier"], charge["poste"], part["montant"]
            par_atelier[atelier] = par_atelier.get(atelier, 0.0) + montant
            postes_atelier = par_atelier_postes.setdefault(atelier, {})
            postes_atelier[poste] = postes_atelier.get(poste, 0.0) + montant

    if ventilation is None:
        ventilation = gl_sums_par_atelier(date_debut, date_fin)
    total_fg = ventilation["ateliers"].get(
        ATELIER_FRAIS_GENERAUX, {"total": 0.0})["total"]
    total_reparti = sum(par_atelier.values())
    total_liste = sum(c["montant"] for c in charges)
    return {
        "charges": charges,
        "par_atelier": {a: round(m, 2) for a, m in par_atelier.items()},
        "par_atelier_postes": {
            a: {p: round(m, 2) for p, m in postes.items()}
            for a, postes in par_atelier_postes.items()},
        "total_reparti": round(total_reparti, 2),
        "total_fg": round(total_fg, 2),
        "total_liste": round(total_liste, 2),
        "autres": round(total_fg - total_liste, 2),
        "non_reparti": round(total_liste - total_reparti, 2),
    }


def _centres_frais_generaux():
    """Full names (company suffix included) of the Frais Généraux cost centers."""
    centres = frappe.get_all("Cost Center",
                             filters={"company": COMPANY, "is_group": 0},
                             pluck="name")
    return [cc for cc in centres if _nom_court(cc) == ATELIER_FRAIS_GENERAUX]


def _charges_frais_generaux(date_debut, date_fin):
    """Charge lines booked on Frais Généraux over the period — purchase
    invoices and journal entries merged, sorted by posting date, then voucher,
    then line number. The label follows the same rule as
    `repartition_charges.lignes_charges`: item name (invoice) or account name
    (entry)."""
    centres = _centres_frais_generaux()
    if not centres:
        return []
    params = {"company": COMPANY, "debut": date_debut, "fin": date_fin,
              "centres": centres}
    factures = frappe.db.sql("""
        SELECT 'Purchase Invoice' AS voucher_type, pi.name AS voucher,
               pi.posting_date, pii.idx AS ligne,
               COALESCE(pii.item_name, pii.item_code) AS libelle,
               acc.account_number AS compte, pii.base_net_amount AS montant
        FROM `tabPurchase Invoice Item` pii
        JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        JOIN `tabAccount` acc ON acc.name = pii.expense_account
        WHERE pi.docstatus = 1
          AND pi.company = %(company)s
          AND pi.is_return = 0
          AND pi.posting_date BETWEEN %(debut)s AND %(fin)s
          AND pii.cost_center IN %(centres)s
          AND acc.root_type = 'Expense'
    """, params, as_dict=True)
    ecritures = frappe.db.sql("""
        SELECT 'Journal Entry' AS voucher_type, je.name AS voucher,
               je.posting_date, jea.idx AS ligne,
               acc.account_name AS libelle, acc.account_number AS compte,
               (jea.debit - jea.credit) AS montant
        FROM `tabJournal Entry Account` jea
        JOIN `tabJournal Entry` je ON je.name = jea.parent
        JOIN `tabAccount` acc ON acc.name = jea.account
        WHERE je.docstatus = 1
          AND je.company = %(company)s
          AND je.posting_date BETWEEN %(debut)s AND %(fin)s
          AND jea.cost_center IN %(centres)s
          AND acc.root_type = 'Expense'
          AND jea.debit - jea.credit > 0
    """, params, as_dict=True)

    charges = []
    for r in sorted(factures + ecritures,
                    key=lambda r: (r.posting_date, r.voucher, r.ligne)):
        charges.append({
            "voucher_type": r.voucher_type, "voucher": r.voucher,
            "ligne": int(r.ligne), "libelle": r.libelle,
            "compte": r.compte or "", "poste": _poste_de(r.compte or ""),
            "montant": float(r.montant or 0), "repartition": [],
        })
    return charges


def _joindre_repartitions(charges):
    """Attaches to each charge the parts typed on it (atelier short name, pct,
    amount recomputed from the line — the charge line is the only source of
    the amount)."""
    if not charges or not frappe.db.table_exists("Repartition Atelier Charge"):
        return
    parts = frappe.get_all(
        "Repartition Atelier Charge",
        filters={"parenttype": ["in", list(PARENTS_REPARTITION)],
                 "parent": ["in", sorted({c["voucher"] for c in charges})]},
        fields=["parenttype", "parent", "ligne", "atelier", "pourcentage"],
        order_by="parent asc, ligne asc, idx asc")
    par_ligne = {}
    for part in parts:
        par_ligne.setdefault((part.parenttype, part.parent, int(part.ligne)),
                             []).append(part)
    for charge in charges:
        cle = (charge["voucher_type"], charge["voucher"], charge["ligne"])
        for part in par_ligne.get(cle, []):
            pct = float(part.pourcentage or 0)
            charge["repartition"].append({
                "atelier": _nom_court(part.atelier), "pct": pct,
                "montant": round(charge["montant"] * pct / 100, 2)})


def charges_lait(date_debut, date_fin, perimetre=None, repartitions=None):
    """Les charges retenues pour le COÛT DU LITRE, poste par poste.

    Périmètre décidé en revue reporting : **atelier Lait + quote-part des
    charges générales**. La quote-part est la **somme des répartitions
    saisies** sur chaque charge Frais Généraux (décision 26/08/2026 : le
    comptable répartit à la saisie, plus de clé calculée). Une charge FG non
    répartie reste à Frais Généraux, hors coût du litre — et le rapport le dit.

    Le « non imputé » n'entre JAMAIS dans le coût du litre : lui attribuer une
    quote-part reviendrait à imputer au lait une charge dont on ignore la
    destination. Il reste affiché à part, c'est le critère d'acceptation n°5.

    `repartitions` : résultat de `repartitions_frais_generaux` déjà en main
    chez l'appelant ; lu sinon.

    Retourne {postes: {cle: montant}, direct, quote_part, total, perimetre,
              non_impute, fg_total, fg_reparti, fg_non_reparti}
    """
    if perimetre is None:
        # An empty Select in the Single reads as "" — treat it as "not set".
        perimetre = get_config("cout_litre_perimetre") or "LAIT_QUOTE_PART"
    if perimetre not in PERIMETRES_COUT_LITRE:
        frappe.throw(f"ERR-FIN-10 : périmètre de coût du litre inconnu "
                     f"« {perimetre} ». Attendu : "
                     f"{', '.join(PERIMETRES_COUT_LITRE)}.")

    ventilation = gl_sums_par_atelier(date_debut, date_fin)
    if repartitions is None:
        repartitions = repartitions_frais_generaux(date_debut, date_fin,
                                                   ventilation=ventilation)
    frais_generaux = {"fg_total": repartitions["total_fg"],
                      "fg_reparti": repartitions["total_reparti"],
                      "fg_non_reparti": repartitions["non_reparti"]}
    ateliers = ventilation["ateliers"]
    non_impute = round(ventilation["non_impute"]["total"], 2)

    if perimetre == "TOUTES_CHARGES":
        # Comportement historique, conservé pour comparer avant/après : il
        # inclut jusqu'aux génisses et aux cultures.
        return {"postes": _postes_cumules(ateliers.values(),
                                          [ventilation["non_impute"]]),
                "direct": ventilation["total"], "quote_part": 0.0,
                "total": ventilation["total"], "perimetre": perimetre,
                "non_impute": non_impute, **frais_generaux}

    lait = ateliers.get(ATELIER_LAIT, {"total": 0.0, "postes": {}})
    direct = round(lait["total"], 2)
    postes = dict(lait["postes"])
    quote_part = 0.0

    if perimetre == "LAIT_QUOTE_PART":
        quote_part = repartitions["par_atelier"].get(ATELIER_LAIT, 0.0)
        for cle, montant in repartitions["par_atelier_postes"].get(
                ATELIER_LAIT, {}).items():
            postes[cle] = postes.get(cle, 0.0) + montant

    return {"postes": {c: round(v, 2) for c, v in postes.items()},
            "direct": direct, "quote_part": round(quote_part, 2),
            "total": round(direct + quote_part, 2), "perimetre": perimetre,
            "non_impute": non_impute, **frais_generaux}


def _postes_cumules(*groupes):
    """Cumule les postes de plusieurs blocs {"postes": {...}}."""
    cumul = {}
    for groupe in groupes:
        for element in groupe:
            for cle, montant in element["postes"].items():
                cumul[cle] = cumul.get(cle, 0.0) + montant
    return {c: round(v, 2) for c, v in cumul.items()}


def ecart_lait(date_debut, date_fin, prix_litre=None):
    """FIN-S25 (RC-FIN-14) — l'écart lait de la période, en litres ET en dinars.

    L'écart est déjà saisi (`Bilan Lait Journalier.ecart_litres` = production
    saisie − vendu − consommation interne − lait veau) mais n'était jamais
    chiffré : on savait combien de litres s'évaporaient, pas ce que ça coûtait.

    Valorisé au prix du litre de la période — **le même prix que la facture** :
    d'abord les `Decompte Lait Mensuel` soumis couvrant la période (prix figé,
    FIN-B1 — éditer une grille ne réécrit plus un mois clôturé), et seulement
    pour une période jamais décomptée le calcul en direct
    (`facturation_lait.compute_milk_rate`). Sinon la perte et le CA ne
    parleraient pas la même monnaie. C'est un manque à gagner : aucune écriture
    comptable n'est postée (le lait n'est pas suivi en stock).

    Plusieurs acheteurs (FIN-S94) : la période porte alors un décompte PAR
    acheteur, à des prix différents. Les litres écartés, eux, ne sont
    attribuables à personne — ils ne sont jamais partis. On les valorise donc
    au **prix moyen pondéré par les volumes** des décomptes de la période :
    c'est le prix moyen réellement obtenu pour un litre vendu ce mois-là, donc
    la meilleure estimation de ce que le litre perdu aurait rapporté. Une
    moyenne simple surpondérerait un petit acheteur cher. Si aucun décompte ne
    porte de volume, on retombe sur la moyenne arithmétique des prix.

    Un écart négatif signale une sur-affectation (vendu + CI + veau > production
    saisie) : c'est une erreur de saisie, pas un gain — il n'est donc jamais
    valorisé, seulement compté et remonté.

    Retourne {litres, litres_perdus, litres_negatifs, valeur, pct_production,
              production, prix_litre, prix_source, decompte, decomptes, jours}
    (prix_source : FOURNI / DECOMPTE / LIVE — d'où sort le prix du litre ;
     `decomptes` = la liste des décomptes retenus, `decompte` leur libellé)
    """
    row = frappe.db.sql("""
        SELECT COALESCE(SUM(ecart_litres), 0) AS net,
               COALESCE(SUM(CASE WHEN ecart_litres > 0 THEN ecart_litres END), 0) AS perdus,
               COALESCE(SUM(CASE WHEN ecart_litres < 0 THEN -ecart_litres END), 0) AS negatifs,
               COALESCE(SUM(production_totale_saisie), 0) AS production,
               COUNT(*) AS jours,
               SUM(CASE WHEN taux_tb_moyen > 0 THEN production_totale_saisie ELSE 0 END) AS vol_tb,
               COALESCE(SUM(CASE WHEN taux_tb_moyen > 0
                                 THEN production_totale_saisie * taux_tb_moyen END), 0) AS somme_tb,
               SUM(CASE WHEN taux_tp_moyen > 0 THEN production_totale_saisie ELSE 0 END) AS vol_tp,
               COALESCE(SUM(CASE WHEN taux_tp_moyen > 0
                                 THEN production_totale_saisie * taux_tp_moyen END), 0) AS somme_tp
        FROM `tabBilan Lait Journalier`
        WHERE date BETWEEN %s AND %s
    """, (date_debut, date_fin), as_dict=True)[0]

    perdus = float(row.perdus or 0)
    production = float(row.production or 0)

    prix_source = "FOURNI"
    decomptes = []
    if prix_litre is None:
        # FIN-B1 — frozen history first: the submitted Decomptes covering the
        # period carry THE settled prices (one per buyer since FIN-S94). Only
        # a never-settled/open period falls back to the live grid computation.
        decomptes = _decomptes_couvrant(date_debut, date_fin)
        if decomptes:
            prix_litre = _prix_moyen_pondere(decomptes)
            prix_source = "DECOMPTE"
        else:
            from hmd_agro.hmd_agro.utils.facturation_lait import compute_milk_rate

            tb = (row.somme_tb / row.vol_tb) if row.vol_tb else None
            tp = (row.somme_tp / row.vol_tp) if row.vol_tp else None
            # No buyer here on purpose: the milk is lost, not sold, so no
            # buyer's negotiated grid applies — the general grid prices it.
            prix_litre = compute_milk_rate(tb, tp, date=date_fin)
            prix_source = "LIVE"

    return {
        "litres": round(float(row.net or 0), 1),
        "litres_perdus": round(perdus, 1),
        "litres_negatifs": round(float(row.negatifs or 0), 1),
        "valeur": round(perdus * float(prix_litre), 2),
        "pct_production": round(perdus / production * 100, 2) if production else 0,
        "production": round(production, 1),
        "prix_litre": float(prix_litre),
        "prix_source": prix_source,
        "decompte": ", ".join(d.name for d in decomptes) if decomptes else None,
        "decomptes": [d.name for d in decomptes],
        "jours": int(row.jours or 0),
    }


def _decomptes_couvrant(date_debut, date_fin):
    """Les Decompte Lait Mensuel soumis dont la période couvre [debut, fin] —
    les prix figés du règlement (FIN-B1). Liste vide si jamais décompté.

    FIN-S94 : il y en a un PAR ACHETEUR, d'où la liste (un seul élément dans
    le cas mono-acheteur). Le plus gros volume d'abord, pour que le libellé
    du KPI cite d'abord l'acheteur principal."""
    if not frappe.db.table_exists("Decompte Lait Mensuel"):
        return []
    return frappe.db.sql("""
        SELECT name, acheteur, prix_final, volume_litres
        FROM `tabDecompte Lait Mensuel`
        WHERE docstatus = 1
          AND periode_debut <= %s AND periode_fin >= %s
        ORDER BY volume_litres DESC, name ASC
    """, (str(date_debut), str(date_fin)), as_dict=True)


def _prix_moyen_pondere(decomptes):
    """Prix du litre de la période = moyenne des prix figés PONDÉRÉE PAR LES
    VOLUMES (cf. docstring d'`ecart_lait`). Repli sur la moyenne simple quand
    aucun décompte ne porte de volume."""
    volume_total = sum(float(d.volume_litres or 0) for d in decomptes)
    if volume_total > 0:
        return sum(float(d.prix_final or 0) * float(d.volume_litres or 0)
                   for d in decomptes) / volume_total
    return sum(float(d.prix_final or 0) for d in decomptes) / len(decomptes)
