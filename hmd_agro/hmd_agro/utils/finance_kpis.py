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


def ecart_lait(date_debut, date_fin, prix_litre=None):
    """FIN-S25 (RC-FIN-14) — l'écart lait de la période, en litres ET en dinars.

    L'écart est déjà saisi (`Bilan Lait Journalier.ecart_litres` = production
    saisie − vendu − consommation interne − lait veau) mais n'était jamais
    chiffré : on savait combien de litres s'évaporaient, pas ce que ça coûtait.

    Valorisé au prix du litre de la période — **le même prix que la facture** :
    d'abord le `Decompte Lait Mensuel` soumis couvrant la période (prix figé,
    FIN-B1 — éditer une grille ne réécrit plus un mois clôturé), et seulement
    pour une période jamais décomptée le calcul en direct
    (`facturation_lait.compute_milk_rate`). Sinon la perte et le CA ne
    parleraient pas la même monnaie. C'est un manque à gagner : aucune écriture
    comptable n'est postée (le lait n'est pas suivi en stock).

    Un écart négatif signale une sur-affectation (vendu + CI + veau > production
    saisie) : c'est une erreur de saisie, pas un gain — il n'est donc jamais
    valorisé, seulement compté et remonté.

    Retourne {litres, litres_perdus, litres_negatifs, valeur, pct_production,
              production, prix_litre, prix_source, decompte, jours}
    (prix_source : FOURNI / DECOMPTE / LIVE — d'où sort le prix du litre)
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
    decompte = None
    if prix_litre is None:
        # FIN-B1 — frozen history first: the submitted Decompte covering the
        # period carries THE settled price. Only a never-settled/open period
        # falls back to the live grid computation.
        decompte = _decompte_couvrant(date_debut, date_fin)
        if decompte:
            prix_litre = decompte.prix_final
            prix_source = "DECOMPTE"
        else:
            from hmd_agro.hmd_agro.utils.facturation_lait import compute_milk_rate

            tb = (row.somme_tb / row.vol_tb) if row.vol_tb else None
            tp = (row.somme_tp / row.vol_tp) if row.vol_tp else None
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
        "decompte": decompte.name if decompte else None,
        "jours": int(row.jours or 0),
    }


def _decompte_couvrant(date_debut, date_fin):
    """Submitted Decompte Lait Mensuel whose period covers [debut, fin] —
    the frozen settled price (FIN-B1). None if never settled.
    Phase-1 single-buyer: multi-acheteur will require scoping this lookup
    (and the ERR-DLM-04 overlap check) by acheteur."""
    if not frappe.db.table_exists("Decompte Lait Mensuel"):
        return None
    return frappe.db.get_value(
        "Decompte Lait Mensuel",
        {
            "docstatus": 1,
            "periode_debut": ["<=", str(date_debut)],
            "periode_fin": [">=", str(date_fin)],
        },
        ["name", "prix_final"],
        as_dict=True,
    )
