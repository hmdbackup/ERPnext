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
