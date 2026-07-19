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
    mo                 64x
    EBE   = produits − (charges − 66x − 68x)   (avant amort. et financier)
    résultat = produits − charges
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

    out["ebe"] = out["produits"] - (
        out["charges"] - out["charges_financieres"] - out["amortissements"])
    out["resultat"] = out["produits"] - out["charges"]
    return out
