"""
FIN-S21 (RG-FIN-10/11/12, RG-FIN-04) — facture lait de la période.

Aggregates `Bilan Lait Journalier.lait_vendu` over a period into ONE Sales
Invoice for the milk buyer, priced from the quality grid in force (TB/TP
volume-weighted means over the same period).

Prix (RG-FIN-10/13 — aucun littéral) :
  1. `Grille Prix Lait` active à la date de facturation (FIN-S24) — prix de
     base + paliers qualité TB/TP de la centrale. C'est le chemin nominal.
  2. À défaut de grille : repli historique, prix plat = Item Price LAIT-CRU
     (fallback config `prix_reference_lait`) indexé linéairement par
     `lait_prime_tb_par_point` / `lait_prime_tp_par_point` (0 par défaut).
     Ce repli est signalé dans les remarques de la facture — un prix plat
     n'est pas un prix contractuel.
    (TB/TP en % — même unité que le BLJ ; primes négatives = pénalité)

Historisation stricte (FIN-B1, Phase 1) : chaque période facturée passe par
un `Decompte Lait Mensuel` soumis — l'instantané figé du règlement (volumes,
TB/TP, grille, décomposition du prix, ajustement manuel négocié). La facture
est émise au `prix_final` du décompte ; les KPI (`finance_kpis.ecart_lait`)
relisent ce prix figé au lieu de recalculer depuis la grille du jour. Un
brouillon de décompte saisi AVANT la facturation (pour porter un
`ajustement_manuel` + motif) est retrouvé, complété et soumis.

Bonus quantité (FIN-B1) : le volume vendu de la période est passé à la grille
(palier critère VOLUME, bornes en litres/mois).

Idempotence (RG-FIN-11) : d'abord le décompte soumis de la période (source de
vérité), puis — garde secondaire héritée — le marqueur `LAIT_FACT_<debut>_
<fin>` dans les remarques de la facture. Deleting/cancelling both then
re-running regenerates them.

Monthly wrapper `generate_monthly_milk_invoice` (scheduler) bills the
previous calendar month — safe to run daily, idempotent.

Run manually:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.utils.facturation_lait.generate_milk_invoice \\
        --kwargs "{'date_debut': '2026-07-01', 'date_fin': '2026-07-31'}"
"""
import frappe
from frappe import _
from frappe.utils import add_days, flt, get_first_day, get_last_day, getdate, today

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

ITEM_LAIT = "LAIT-CRU"
PRICE_LIST = "Standard Selling"
CUSTOMER_LAIT = "Centrale Laitière"
MARKER = "LAIT_FACT_{debut}_{fin}"


def _marker(date_debut, date_fin):
    return MARKER.format(debut=date_debut, fin=date_fin)


def existing_invoice(date_debut, date_fin):
    """Submitted-or-draft invoice already carrying this period's marker."""
    return frappe.db.get_value(
        "Sales Invoice",
        {"remarks": ["like", f"%{_marker(date_debut, date_fin)}%"],
         "docstatus": ["<", 2]},
        "name",
    )


def existing_decompte(date_debut, date_fin):
    """Submitted (frozen) Decompte for exactly this period, as a dict
    {name, facture, prix_final} — or None.

    Phase-1 single-buyer semantics: not scoped by acheteur (one centrale).
    Multi-acheteur will require scoping this lookup — and the ERR-DLM-04
    overlap check + finance_kpis._decompte_couvrant — by acheteur."""
    if not frappe.db.table_exists("Decompte Lait Mensuel"):
        return None
    return frappe.db.get_value(
        "Decompte Lait Mensuel",
        {"periode_debut": date_debut, "periode_fin": date_fin, "docstatus": 1},
        ["name", "facture", "prix_final"],
        as_dict=True,
    )


def compute_milk_rate(tb_moyen=None, tp_moyen=None, date=None, volume=None,
                      detail=False):
    """Prix du litre à une date (RG-FIN-10/13). Grille qualité si elle existe,
    sinon repli prix plat. TB/TP None → aucune prime (pas de donnée qualité).
    `volume` = litres vendus sur la période, pour le bonus quantité (palier
    VOLUME de la grille, FIN-B1) — ignoré par le repli prix plat.

    detail=True retourne le décomposé {prix, prix_base, primes, grille, statut}
    — utilisé par la facture et le pilotage pour tracer d'où sort le prix."""
    from hmd_agro.hmd_agro.doctype.grille_prix_lait.grille_prix_lait import grille_active

    grille = grille_active(date)
    if grille:
        return grille.prix_du_litre(tb=tb_moyen, tp=tp_moyen, volume=volume,
                                    detail=detail)

    base = frappe.db.get_value(
        "Item Price", {"item_code": ITEM_LAIT, "price_list": PRICE_LIST},
        "price_list_rate",
    )
    prix_base = float(base if base is not None
                      else get_config("prix_reference_lait", default=1.6))
    primes = {}
    if tb_moyen:
        tb_ref = float(get_config("lait_tb_reference", default=3.8))
        prime_tb = float(get_config("lait_prime_tb_par_point", default=0.0))
        primes["TB"] = (float(tb_moyen) - tb_ref) * prime_tb
    if tp_moyen:
        tp_ref = float(get_config("lait_tp_reference", default=3.2))
        prime_tp = float(get_config("lait_prime_tp_par_point", default=0.0))
        primes["TP"] = (float(tp_moyen) - tp_ref) * prime_tp
    prime_totale = sum(primes.values())
    prix = round(max(prix_base + prime_totale, 0), 3)
    if not detail:
        return prix
    return {
        "prix": prix, "prix_base": prix_base,
        "primes": {k: round(v, 3) for k, v in primes.items() if v},
        "prime_totale": round(prime_totale, 3),
        "grille": None, "statut": "PRIX_PLAT",
    }


def _period_volumes(date_debut, date_fin):
    """(volume vendu, TB moyen pondéré, TP moyen pondéré) from BLJ rows."""
    row = frappe.db.sql("""
        SELECT COALESCE(SUM(lait_vendu), 0) AS volume,
               SUM(CASE WHEN taux_tb_moyen > 0 THEN lait_vendu ELSE 0 END) AS vol_tb,
               COALESCE(SUM(CASE WHEN taux_tb_moyen > 0
                                 THEN lait_vendu * taux_tb_moyen END), 0) AS somme_tb,
               SUM(CASE WHEN taux_tp_moyen > 0 THEN lait_vendu ELSE 0 END) AS vol_tp,
               COALESCE(SUM(CASE WHEN taux_tp_moyen > 0
                                 THEN lait_vendu * taux_tp_moyen END), 0) AS somme_tp
        FROM `tabBilan Lait Journalier`
        WHERE date BETWEEN %s AND %s
    """, (date_debut, date_fin), as_dict=True)[0]
    volume = float(row.volume or 0)
    tb = (row.somme_tb / row.vol_tb) if row.vol_tb else None
    tp = (row.somme_tp / row.vol_tp) if row.vol_tp else None
    return volume, tb, tp


def _find_or_create_decompte(date_debut, date_fin, customer, volume, tb, tp, prix):
    """Draft Decompte for the period, filled from the live figures. A draft
    saisi avant facturation (pour l'ajustement manuel + motif) est retrouvé et
    complété — son ajustement est conservé et entre dans le prix final.

    La prime qualité stockée = prix grille − prix de base − prime quantité :
    elle absorbe plafond de prime et plancher de prix, si bien que
    prix_final = base + qualité + quantité + ajustement reste exactement le
    prix de la grille corrigé de l'ajustement."""
    # Reuse only a draft whose bounds match the billed period exactly — a
    # partial-period draft must never be silently repurposed (its bounds and
    # figures would be overwritten). Phase-1 single-buyer: not scoped by
    # acheteur (see existing_decompte); multi-acheteur will require it.
    nom = frappe.db.get_value(
        "Decompte Lait Mensuel",
        {"periode_debut": date_debut, "periode_fin": date_fin, "docstatus": 0},
        "name",
    )
    if not nom:
        # An overlapping draft with different bounds would make the new
        # decompte fail ERR-DLM-04 deep in the save — surface an actionable
        # error instead, so the scheduler failure is diagnosable.
        chevauche = frappe.db.get_value(
            "Decompte Lait Mensuel",
            {
                "docstatus": 0,
                "periode_debut": ["<=", date_fin],
                "periode_fin": [">=", date_debut],
            },
            ["name", "periode_debut", "periode_fin"],
            as_dict=True,
        )
        if chevauche:
            frappe.throw(
                _("ERR-DLM-05 : le brouillon de décompte « {0} » "
                  "({1} → {2}) chevauche la période à facturer "
                  "({3} → {4}) sans la couvrir exactement — corrigez ses "
                  "bornes ou supprimez ce brouillon, puis relancez la "
                  "facturation.")
                .format(chevauche.name, chevauche.periode_debut,
                        chevauche.periode_fin, date_debut, date_fin)
            )
    dlm = (frappe.get_doc("Decompte Lait Mensuel", nom)
           if nom else frappe.new_doc("Decompte Lait Mensuel"))
    primes = prix.get("primes") or {}
    prime_quantite = round(flt(primes.get("VOLUME")), 3)
    prime_qualite = round(
        flt(prix["prix"]) - flt(prix["prix_base"]) - prime_quantite, 3)
    dlm.update({
        "periode_debut": date_debut,
        "periode_fin": date_fin,
        "acheteur": customer,
        "volume_litres": volume,
        "tb_moyen": round(tb, 2) if tb else None,
        "tp_moyen": round(tp, 2) if tp else None,
        "grille": prix.get("grille"),
        "prix_base": flt(prix["prix_base"]),
        "prime_qualite": prime_qualite,
        "prime_quantite": prime_quantite,
    })
    dlm.save(ignore_permissions=True)
    return dlm


@frappe.whitelist()
def generate_milk_invoice(date_debut, date_fin, customer=None, submit=True):
    """Create the period milk Sales Invoice through its Decompte Lait Mensuel
    (FIN-B1). Idempotent: a submitted Decompte for the period wins; the legacy
    remarks marker stays as a secondary guard.
    Returns the invoice name, or None (no volume / already billed)."""
    date_debut, date_fin = str(getdate(date_debut)), str(getdate(date_fin))

    fige = existing_decompte(date_debut, date_fin)
    if fige:
        print(f"  [skip]   Décompte lait déjà figé pour {date_debut} → {date_fin} "
              f"({fige.name}, facture {fige.facture or '—'})")
        return fige.facture or existing_invoice(date_debut, date_fin)

    existing = existing_invoice(date_debut, date_fin)
    if existing:
        print(f"  [skip]   Facture lait déjà émise pour {date_debut} → {date_fin} "
              f"({existing})")
        return existing

    volume, tb, tp = _period_volumes(date_debut, date_fin)
    if volume <= 0:
        print(f"  [skip]   Aucun lait vendu (BLJ) sur {date_debut} → {date_fin}")
        return None

    prix = compute_milk_rate(tb, tp, date=date_fin, volume=volume, detail=True)
    customer = customer or CUSTOMER_LAIT

    dlm = _find_or_create_decompte(date_debut, date_fin, customer,
                                   volume, tb, tp, prix)
    rate = flt(dlm.prix_final)

    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "company": COMPANY,
        "customer": customer,
        "posting_date": date_fin if getdate(date_fin) <= getdate(today()) else today(),
        "set_posting_time": 1,
        "items": [{
            "item_code": ITEM_LAIT,
            "qty": volume,
            "rate": rate,
        }],
        "remarks": (f"{_marker(date_debut, date_fin)} — {volume:.0f} L"
                    + (f", TB {tb:.1f}" if tb else "")
                    + (f", TP {tp:.1f}" if tp else "")
                    + f" — {_libelle_prix(prix)}"
                    + (f" — ajustement {flt(dlm.ajustement_manuel):+.3f} TND/L"
                       if flt(dlm.ajustement_manuel) else "")
                    + f" — décompte {dlm.name}"),
    })
    si.insert(ignore_permissions=True)
    dlm.facture = si.name
    dlm.flags.from_facturation = True   # authorizes submit (ERR-DLM-06 guard)
    if submit:
        si.submit()
        dlm.submit()          # freeze the snapshot (docstatus 1) — persists facture too
    else:
        dlm.save(ignore_permissions=True)
    print(f"  [create] Facture lait {si.name} : {volume:.0f} L @ {rate} TND/L "
          f"= {si.grand_total} TND ({_libelle_prix(prix)}) — décompte {dlm.name}")
    return si.name


def _libelle_prix(prix):
    """Trace lisible de l'origine du prix, gardée dans les remarques de la
    facture : on doit pouvoir dire six mois plus tard pourquoi ce prix-là."""
    if not prix.get("grille"):
        return ("prix plat (aucune grille active — RG-FIN-13, "
                "grille centrale à saisir)")
    detail = ", ".join(f"{critere} {montant:+.3f}"
                       for critere, montant in prix["primes"].items())
    libelle = (f"grille « {prix['grille'] } » base {prix['prix_base']:.3f}"
               + (f" ({detail})" if detail else " (aucune prime)"))
    if prix.get("statut") == "PROVISOIRE":
        libelle += " — GRILLE PROVISOIRE, à valider avec la centrale"
    return libelle


def generate_monthly_milk_invoice():
    """Scheduler job — facture le mois civil précédent. Idempotent, safe daily."""
    first_of_this_month = get_first_day(today())
    prev_last = add_days(first_of_this_month, -1)
    prev_first = get_first_day(prev_last)
    return generate_milk_invoice(str(prev_first), str(get_last_day(prev_last)))
