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
# + quote-part des charges générales. La quote-part est ce que la CLÉ DE
# RÉPARTITION (Cost Center Allocation ERPNext) a envoyé de Frais Généraux vers
# Lait, pièce par pièce (réunions 26/08 et 03/09/2026 : la clé se fixe une
# fois, puis s'applique à chaque saisie — plus de clé calculée, plus de saisie
# ligne par ligne) ; le périmètre reste configurable parce que c'est une
# décision métier, pas une constante technique (convention maison : jamais de
# seuil en dur).
PERIMETRES_COUT_LITRE = ("LAIT_QUOTE_PART", "LAIT_SEUL", "TOUTES_CHARGES")


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


def cle_repartition(cost_center, date, company=COMPANY):
    """The ERPNext « Cost Center Allocation » in force on `date` for
    `cost_center` — the same lookup the General Ledger applies at posting time
    (`erpnext.accounts.general_ledger.get_cost_center_allocation_data`: the
    latest submitted allocation whose `valid_from` ≤ posting date).

    Returns {name, valid_from, parts: [{cost_center, atelier (short name),
    pct}]} or None when no key applies on that date (the charge then stays on
    the cost center it was booked on)."""
    if not cost_center:
        return None
    cle = frappe.db.get_value(
        "Cost Center Allocation",
        {"docstatus": 1, "company": company, "main_cost_center": cost_center,
         "valid_from": ("<=", date)},
        ["name", "valid_from"], order_by="valid_from desc", as_dict=True)
    if not cle:
        return None
    parts = frappe.get_all("Cost Center Allocation Percentage",
                           filters={"parent": cle.name},
                           fields=["cost_center", "percentage"],
                           order_by="idx asc")
    return {
        "name": cle.name, "valid_from": cle.valid_from,
        "parts": [{"cost_center": p.cost_center, "atelier": _nom_court(p.cost_center),
                   "pct": float(p.percentage or 0)} for p in parts],
    }


def libelle_cle(cle):
    """« Lait 60 % · Cultures - Fourrage 25 % · Élevage - Génisses 15 % »."""
    from hmd_agro.hmd_agro.utils.format_fr import fr_nombre

    return " · ".join(f"{p['atelier']} {fr_nombre(round(p['pct'], 2))} %"
                      for p in cle["parts"])


def repartitions_frais_generaux(date_debut, date_fin, ventilation=None):
    """The Frais Généraux charges of the period and how the KEY split them.

    Since 03/09/2026 the split is no longer typed on each charge: the
    accountant books the charge on Frais Généraux, and ERPNext's « Cost
    Center Allocation » (the key, fixed once by the administrator) splits the
    GL entries at submit time. This reader lists the Purchase Invoice lines
    (submitted, credit notes excluded) and the Journal Entry lines
    (submitted, debit charge lines) booked on a Frais Généraux cost center,
    and attaches to each the key in force on its posting date — exactly the
    key the ledger applied. A charge posted before any key is listed with an
    empty split: it stayed on Frais Généraux, and the report must name it.

    `ventilation`: the `gl_sums_par_atelier` result the caller already holds
    (saves a second GL reading); read otherwise.

    Returns {
        "charges": [{voucher_type, voucher, ligne, libelle, compte, poste,
                     montant, cost_center, posting_date, cle (name or None),
                     repartition: [{atelier, pct, montant}]}],
        "par_atelier": {atelier: montant},
        "par_atelier_postes": {atelier: {poste: montant}},
        "total_liste": Σ of the listed charges,
        "total_reparti": Σ of the charges split by a key,
        "non_reparti": Σ of the charges posted without a key (stayed on FG),
        "total_fg": GL balance left on Frais Généraux over the period,
        "autres": total_fg − non_reparti (vouchers left on FG that cannot be
                  listed here: stock movements, credit notes…),
        "controle_gl": {"ecart": Σ |GL − key| over the split charges,
                        "details": [...]} — the ledger really carries the split,
        "cles_en_vigueur": [{centre, name, valid_from, parts}] at date_fin,
    }
    """
    charges = _charges_frais_generaux(date_debut, date_fin)
    _joindre_cles(charges)

    par_atelier, par_atelier_postes = {}, {}
    for charge in charges:
        for part in charge["repartition"]:
            atelier, poste, montant = part["atelier"], charge["poste"], part["montant"]
            par_atelier[atelier] = par_atelier.get(atelier, 0.0) + montant
            postes_atelier = par_atelier_postes.setdefault(atelier, {})
            postes_atelier[poste] = postes_atelier.get(poste, 0.0) + montant

    if ventilation is None:
        ventilation = gl_sums_par_atelier(date_debut, date_fin)
    total_fg = sum(
        atelier["total"] for nom, atelier in ventilation["ateliers"].items()
        if nom in {_nom_court(cc) for cc in _centres_frais_generaux()})
    total_liste = sum(c["montant"] for c in charges)
    total_reparti = sum(c["montant"] for c in charges if c["cle"])
    non_reparti = total_liste - total_reparti
    return {
        "charges": charges,
        "par_atelier": {a: round(m, 2) for a, m in par_atelier.items()},
        "par_atelier_postes": {
            a: {p: round(m, 2) for p, m in postes.items()}
            for a, postes in par_atelier_postes.items()},
        "total_liste": round(total_liste, 2),
        "total_reparti": round(total_reparti, 2),
        "non_reparti": round(non_reparti, 2),
        "total_fg": round(total_fg, 2),
        "autres": round(total_fg - non_reparti, 2),
        "controle_gl": _controle_grand_livre(charges),
        "cles_en_vigueur": cles_en_vigueur(date_fin),
    }


def cles_en_vigueur(date):
    """The key in force on `date` for each Frais Généraux cost center —
    [{centre (short name), cost_center, name, valid_from, parts}], the centers
    without a key listed with `name` None so the report can say so."""
    cles = []
    for cc in _centres_frais_generaux():
        cle = cle_repartition(cc, date) or {"name": None, "valid_from": None,
                                             "parts": []}
        cles.append({"centre": _nom_court(cc), "cost_center": cc, **cle})
    return cles


def _centres_frais_generaux():
    """Full names (company suffix included) of the Frais Généraux cost
    centers: the ones named so, plus any cost center that carries a submitted
    key (a second « Frais Généraux Parc » key needs configuration, not
    code)."""
    centres = frappe.get_all("Cost Center",
                             filters={"company": COMPANY, "is_group": 0},
                             pluck="name")
    par_nom = {cc for cc in centres if _nom_court(cc) == ATELIER_FRAIS_GENERAUX}
    par_cle = set(frappe.get_all("Cost Center Allocation",
                                 filters={"docstatus": 1, "company": COMPANY},
                                 pluck="main_cost_center", distinct=True))
    return sorted(par_nom | (par_cle & set(centres)))


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
               acc.account_number AS compte, acc.name AS compte_nom,
               pii.cost_center, pii.base_net_amount AS montant
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
               acc.name AS compte_nom, jea.cost_center,
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
            "compte": r.compte or "", "compte_nom": r.compte_nom,
            "poste": _poste_de(r.compte or ""),
            "montant": float(r.montant or 0), "cost_center": r.cost_center,
            "posting_date": r.posting_date, "cle": None, "repartition": [],
        })
    return charges


def _joindre_cles(charges):
    """Attaches to each charge the key in force on its posting date — the
    split the ledger applied — as [{atelier, pct, montant}]. One lookup per
    (cost center, date)."""
    cache = {}
    for charge in charges:
        cle_cache = (charge["cost_center"], str(charge["posting_date"]))
        if cle_cache not in cache:
            cache[cle_cache] = cle_repartition(*cle_cache)
        cle = cache[cle_cache]
        if not cle:
            continue
        charge["cle"] = cle["name"]
        charge["repartition"] = [
            {"atelier": p["atelier"], "pct": p["pct"],
             "montant": round(charge["montant"] * p["pct"] / 100, 2)}
            for p in cle["parts"]]


def _controle_grand_livre(charges):
    """Replays the key against the ledger: for every (voucher, account) split
    by a key, the GL debit per target cost center must equal Σ line × pct.
    This is the check asked on 03/09/2026 — « valide la facture et regarde si
    les montants apparaissent bien répartis » — kept on the report, not only
    in a test. Returns {"ecart": Σ |gap|, "details": [{voucher, compte,
    cost_center, attendu, grand_livre}] for the gaps beyond the cent}."""
    attendus = {}
    for charge in charges:
        if not charge["cle"]:
            continue
        for part in charge["repartition"]:
            cle = (charge["voucher"], charge["compte_nom"])
            par_cc = attendus.setdefault(cle, {})
            par_cc[part["atelier"]] = par_cc.get(part["atelier"], 0.0) + part["montant"]
    if not attendus:
        return {"ecart": 0.0, "details": []}

    rows = frappe.db.sql("""
        SELECT voucher_no, account, cost_center,
               SUM(debit - credit) AS solde
        FROM `tabGL Entry`
        WHERE is_cancelled = 0
          AND voucher_no IN %(vouchers)s
        GROUP BY voucher_no, account, cost_center
    """, {"vouchers": sorted({v for v, _ in attendus})}, as_dict=True)
    reels = {}
    for r in rows:
        reels.setdefault((r.voucher_no, r.account), {})[_nom_court(r.cost_center)] = \
            float(r.solde or 0)

    ecart, details = 0.0, []
    for (voucher, compte), par_cc in attendus.items():
        for atelier, attendu in par_cc.items():
            reel = reels.get((voucher, compte), {}).get(atelier, 0.0)
            # Each GL row is rounded to the cent by ERPNext: one cent per part
            # is a rounding, anything beyond is a key the ledger did not apply.
            gap = round(abs(reel - attendu), 2)
            if gap > 0.01 * max(len(par_cc), 1):
                ecart += gap
                details.append({"voucher": voucher, "compte": compte,
                                "cost_center": atelier,
                                "attendu": round(attendu, 2),
                                "grand_livre": round(reel, 2)})
    return {"ecart": round(ecart, 2), "details": details}


def charges_lait(date_debut, date_fin, perimetre=None, repartitions=None):
    """Les charges retenues pour le COÛT DU LITRE, poste par poste.

    Périmètre décidé en revue reporting : **atelier Lait + quote-part des
    charges générales**. Depuis le 03/09/2026 la quote-part n'est plus
    ajoutée par le rapport : la **clé de répartition** (Cost Center
    Allocation ERPNext) a déjà envoyé, dans le Grand Livre, la part de chaque
    charge Frais Généraux vers Lait. Le total du Lait est donc lu tel quel au
    Grand Livre ; la quote-part est isolée pour information (somme des parts
    Lait des pièces listées par `repartitions_frais_generaux`) et le direct en
    est la différence. Une charge FG postée sans clé reste à Frais Généraux,
    hors coût du litre — et le rapport le dit.

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
    total_gl = round(lait["total"], 2)
    postes = dict(lait["postes"])
    # What the key sent to Lait — already inside the GL figures above.
    quote_part = round(repartitions["par_atelier"].get(ATELIER_LAIT, 0.0), 2)
    postes_quote_part = repartitions["par_atelier_postes"].get(ATELIER_LAIT, {})

    if perimetre == "LAIT_QUOTE_PART":
        direct, total = round(total_gl - quote_part, 2), total_gl
    else:  # LAIT_SEUL — the key's share taken back out, poste by poste
        for cle, montant in postes_quote_part.items():
            postes[cle] = postes.get(cle, 0.0) - montant
        direct = total = round(total_gl - quote_part, 2)
        quote_part = 0.0

    return {"postes": {c: round(v, 2) for c, v in postes.items()},
            "direct": direct, "quote_part": quote_part,
            "total": total, "perimetre": perimetre,
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
