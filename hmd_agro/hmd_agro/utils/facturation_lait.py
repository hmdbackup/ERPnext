"""
FIN-S21 / FIN-S94 (RG-FIN-10/11/12, RG-FIN-04) — factures lait de la période.

Aggregates `Bilan Lait Journalier.lait_vendu` over a period into ONE Sales
Invoice **par acheteur**, priced from the quality grid in force for that buyer
(TB/TP volume-weighted means over the same period).

Plusieurs acheteurs (FIN-S94) : la ferme vend à plusieurs clients externes.
La ventilation journalière (`Bilan Lait Journalier.ventes`, une ligne par
acheteur) dit qui a pris quoi ; la facturation en déduit les acheteurs de la
période et produit **un décompte + une facture par acheteur**, avec son
volume, ses TB/TP pondérés par ses litres, et sa grille. Sans aucune
ventilation sur la période, le comportement mono-acheteur historique
s'applique : un seul acheteur = `get_config("client_lait_defaut")`.
(L'atelier génisses n'est pas un acheteur : c'est de la facturation interne,
hors périmètre — le lait bu par les veaux est en `lait_veau`.)

Prix (RG-FIN-10/13 — aucun littéral) :
  1. `Grille Prix Lait` active à la date de facturation POUR CET ACHETEUR
     (FIN-S24/S94 — sa grille nominative, sinon la grille générale) : prix de
     base + paliers qualité TB/TP. C'est le chemin nominal.
  2. À défaut de grille : repli historique, prix plat = Item Price LAIT-CRU
     (fallback config `prix_reference_lait`) indexé linéairement par
     `lait_prime_tb_par_point` / `lait_prime_tp_par_point` (0 par défaut).
     Ce repli est signalé dans les remarques de la facture — un prix plat
     n'est pas un prix contractuel.
    (TB/TP en % — même unité que le BLJ ; primes négatives = pénalité)

Historisation stricte (FIN-B1) : chaque acheteur × période facturé passe par
un `Decompte Lait Mensuel` soumis — l'instantané figé du règlement (volumes,
TB/TP, grille, décomposition du prix, ajustement manuel négocié). La facture
est émise au `prix_final` du décompte ; les KPI (`finance_kpis.ecart_lait`)
relisent ces prix figés au lieu de recalculer. Un brouillon de décompte saisi
AVANT la facturation (pour porter un `ajustement_manuel` + motif) est
retrouvé, complété et soumis.

Bonus quantité (FIN-B1) : le volume vendu de la période À CET ACHETEUR est
passé à la grille (palier critère VOLUME, bornes en litres/mois).

Idempotence (RG-FIN-11) : d'abord le décompte soumis de l'acheteur pour la
période (source de vérité), puis — garde secondaire héritée — le marqueur
`LAIT_FACT_<debut>_<fin>` dans les remarques de la facture, désormais lu
acheteur par acheteur (le marqueur reste inchangé : le backfill v1_8 le
relit). Deleting/cancelling both then re-running regenerates them.

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
# Documented fallback for `client_lait_defaut` — the historical single buyer.
# Kept as the config default so a fresh DB behaves exactly as before.
CLIENT_LAIT_FALLBACK = "Centrale Laitière"
MARKER = "LAIT_FACT_{debut}_{fin}"


def client_lait_defaut():
    """Acheteur utilisé quand la période n'a aucune ventilation par acheteur.
    `get_config` peut rendre une chaîne vide (champ créé puis vidé) : on
    retombe alors sur la constante documentée."""
    return get_config("client_lait_defaut",
                      default=CLIENT_LAIT_FALLBACK) or CLIENT_LAIT_FALLBACK


def _marker(date_debut, date_fin):
    return MARKER.format(debut=date_debut, fin=date_fin)


def existing_invoice(date_debut, date_fin, customer=None):
    """Submitted-or-draft invoice already carrying this period's marker.
    Scopée par acheteur depuis FIN-S94 : le marqueur reste par période (le
    backfill v1_8 le relit tel quel), c'est le client de la facture qui
    distingue les acheteurs."""
    filtres = {
        "remarks": ["like", f"%{_marker(date_debut, date_fin)}%"],
        "docstatus": ["<", 2],
    }
    if customer:
        filtres["customer"] = customer
    return frappe.db.get_value("Sales Invoice", filtres, "name")


def existing_decompte(date_debut, date_fin, acheteur=None):
    """Submitted (frozen) Decompte for exactly this period, as a dict
    {name, facture, prix_final} — or None.

    FIN-S94 : scopé par acheteur (un mois = un décompte PAR acheteur). Sans
    acheteur précisé, la lecture reste globale — n'importe quel décompte figé
    de la période — ce qui sert les appels de pilotage et les contrôles
    « cette période a-t-elle déjà été réglée ? »."""
    if not frappe.db.table_exists("Decompte Lait Mensuel"):
        return None
    filtres = {"periode_debut": date_debut, "periode_fin": date_fin,
               "docstatus": 1}
    if acheteur:
        filtres["acheteur"] = acheteur
    return frappe.db.get_value(
        "Decompte Lait Mensuel", filtres,
        ["name", "facture", "prix_final"],
        as_dict=True,
    )


def compute_milk_rate(tb_moyen=None, tp_moyen=None, date=None, volume=None,
                      detail=False, acheteur=None):
    """Prix du litre à une date pour un acheteur (RG-FIN-10/13). Grille
    qualité si elle existe (celle de l'acheteur, sinon la grille générale —
    FIN-S94), sinon repli prix plat. TB/TP None → aucune prime (pas de donnée
    qualité). `volume` = litres vendus sur la période à cet acheteur, pour le
    bonus quantité (palier VOLUME de la grille, FIN-B1) — ignoré par le repli
    prix plat.

    detail=True retourne le décomposé {prix, prix_base, primes, grille, statut}
    — utilisé par la facture et le pilotage pour tracer d'où sort le prix."""
    from hmd_agro.hmd_agro.doctype.grille_prix_lait.grille_prix_lait import grille_active

    grille = grille_active(date, acheteur=acheteur)
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
        "grille": None, "statut": "PRIX_PLAT",
        "prime_totale": round(prime_totale, 3),
    }


def acheteurs_periode(date_debut, date_fin):
    """FIN-S94 — les acheteurs servis sur la période, du plus gros volume au
    plus petit, d'après la ventilation journalière. Liste vide = aucune
    ventilation saisie (mono-acheteur historique)."""
    if not frappe.db.table_exists("Bilan Lait Vente"):
        return []
    rows = frappe.db.sql("""
        SELECT v.acheteur AS acheteur, SUM(v.litres) AS litres
        FROM `tabBilan Lait Vente` v
        JOIN `tabBilan Lait Journalier` b ON b.name = v.parent
        WHERE b.date BETWEEN %s AND %s
          AND IFNULL(v.acheteur, '') != ''
        GROUP BY v.acheteur
        HAVING SUM(v.litres) > 0
        ORDER BY litres DESC, v.acheteur ASC
    """, (date_debut, date_fin), as_dict=True)
    return [r.acheteur for r in rows]


def _period_volumes(date_debut, date_fin, acheteur=None):
    """(volume vendu, TB moyen pondéré, TP moyen pondéré) sur la période.

    Sans acheteur : le total vendu, lu sur `lait_vendu` — qui reste LE total
    du jour (somme de la ventilation quand elle existe). Avec acheteur : ses
    seules lignes de ventilation. Les TB/TP sont des moyennes du jour pour
    tout le troupeau : les pondérer par les litres de l'acheteur donne bien
    « le TB du lait qu'il a reçu »."""
    if acheteur:
        row = frappe.db.sql("""
            SELECT COALESCE(SUM(v.litres), 0) AS volume,
                   SUM(CASE WHEN b.taux_tb_moyen > 0 THEN v.litres ELSE 0 END) AS vol_tb,
                   COALESCE(SUM(CASE WHEN b.taux_tb_moyen > 0
                                     THEN v.litres * b.taux_tb_moyen END), 0) AS somme_tb,
                   SUM(CASE WHEN b.taux_tp_moyen > 0 THEN v.litres ELSE 0 END) AS vol_tp,
                   COALESCE(SUM(CASE WHEN b.taux_tp_moyen > 0
                                     THEN v.litres * b.taux_tp_moyen END), 0) AS somme_tp
            FROM `tabBilan Lait Vente` v
            JOIN `tabBilan Lait Journalier` b ON b.name = v.parent
            WHERE b.date BETWEEN %s AND %s AND v.acheteur = %s
        """, (date_debut, date_fin, acheteur), as_dict=True)[0]
    else:
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


def _brouillon_exact(date_debut, date_fin, acheteur, accepter_sans_acheteur):
    """Draft decompte covering EXACTLY the billed period for this buyer.
    `accepter_sans_acheteur` autorise le repli sur un brouillon sans acheteur
    (saisi avant FIN-S94, ou par un opérateur qui n'a qu'un seul acheteur) —
    jamais quand la période sert plusieurs acheteurs, sinon on attribuerait
    l'ajustement d'un client à un autre."""
    nom = frappe.db.get_value(
        "Decompte Lait Mensuel",
        {"periode_debut": date_debut, "periode_fin": date_fin,
         "docstatus": 0, "acheteur": acheteur},
        "name",
    )
    if nom or not accepter_sans_acheteur:
        return nom
    orphelin = frappe.db.sql("""
        SELECT name FROM `tabDecompte Lait Mensuel`
        WHERE periode_debut = %s AND periode_fin = %s AND docstatus = 0
          AND IFNULL(acheteur, '') = ''
        LIMIT 1
    """, (date_debut, date_fin))
    return orphelin[0][0] if orphelin else None


def _find_or_create_decompte(date_debut, date_fin, customer, volume, tb, tp,
                             prix, acheteur_unique=True):
    """Draft Decompte for the period AND this buyer, filled from the live
    figures. A draft saisi avant facturation (pour l'ajustement manuel +
    motif) est retrouvé et complété — son ajustement est conservé et entre
    dans le prix final.

    La prime qualité stockée = prix grille − prix de base − prime quantité :
    elle absorbe plafond de prime et plancher de prix, si bien que
    prix_final = base + qualité + quantité + ajustement reste exactement le
    prix de la grille corrigé de l'ajustement."""
    # Reuse only a draft whose bounds match the billed period exactly — a
    # partial-period draft must never be silently repurposed (its bounds and
    # figures would be overwritten).
    nom = _brouillon_exact(date_debut, date_fin, customer,
                           accepter_sans_acheteur=acheteur_unique)
    if not nom:
        # An overlapping draft (same buyer, or buyer-less hence ambiguous)
        # would make the new decompte fail ERR-DLM-04 deep in the save —
        # surface an actionable error instead, so the scheduler failure is
        # diagnosable.
        chevauche = frappe.db.sql("""
            SELECT name, periode_debut, periode_fin, IFNULL(acheteur, '') AS acheteur
            FROM `tabDecompte Lait Mensuel`
            WHERE docstatus = 0
              AND IFNULL(acheteur, '') IN (%(acheteur)s, '')
              AND periode_debut <= %(fin)s AND periode_fin >= %(debut)s
            LIMIT 1
        """, {"acheteur": customer, "debut": date_debut, "fin": date_fin},
            as_dict=True)
        if chevauche:
            autre = chevauche[0]
            frappe.throw(
                _("ERR-DLM-05 : le brouillon de décompte « {0} » "
                  "({1} → {2}, {3}) chevauche la période à facturer "
                  "({4} → {5}) pour l'acheteur « {6} » sans la couvrir "
                  "exactement — corrigez ses bornes, précisez son acheteur, "
                  "ou supprimez ce brouillon, puis relancez la facturation.")
                .format(autre.name, autre.periode_debut, autre.periode_fin,
                        _("acheteur « {0} »").format(autre.acheteur)
                        if autre.acheteur else _("sans acheteur"),
                        date_debut, date_fin, customer)
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
    """Facture le lait de la période, UN ACHETEUR À LA FOIS (FIN-S94), chacun
    par son `Decompte Lait Mensuel` (FIN-B1).

    Acheteurs retenus :
      • `customer` fourni → lui seul (son volume ventilé s'il y a une
        ventilation, sinon tout le lait vendu de la période) ;
      • sinon les acheteurs de la ventilation journalière ;
      • sinon, aucune ventilation → un seul acheteur,
        `get_config("client_lait_defaut")`.

    Idempotent par acheteur : son décompte soumis gagne ; le marqueur legacy
    dans les remarques reste une garde secondaire.

    Retourne la LISTE des factures créées ou déjà émises (vide si aucun lait
    vendu) — une par acheteur."""
    date_debut, date_fin = str(getdate(date_debut)), str(getdate(date_fin))

    ventiles = acheteurs_periode(date_debut, date_fin)
    if customer:
        # Un acheteur imposé : on ne lui facture que SON lait s'il existe une
        # ventilation, sinon la totalité (mono-acheteur historique).
        repartition = [(customer, customer if ventiles else None)]
    elif ventiles:
        repartition = [(acheteur, acheteur) for acheteur in ventiles]
    else:
        repartition = [(client_lait_defaut(), None)]

    factures = []
    for acheteur, cle_ventilation in repartition:
        facture = _facturer_acheteur(
            date_debut, date_fin, acheteur, cle_ventilation,
            acheteur_unique=len(repartition) == 1, submit=submit)
        if facture:
            factures.append(facture)
    return factures


def _facturer_acheteur(date_debut, date_fin, customer, cle_ventilation,
                       acheteur_unique=True, submit=True):
    """Décompte + facture d'UN acheteur sur la période. `cle_ventilation` =
    l'acheteur dont on lit les lignes de ventilation, ou None pour lire le
    total vendu du jour (aucune ventilation sur la période)."""
    fige = existing_decompte(date_debut, date_fin, acheteur=customer)
    if fige:
        print(f"  [skip]   Décompte lait déjà figé pour {customer} "
              f"{date_debut} → {date_fin} "
              f"({fige.name}, facture {fige.facture or '—'})")
        return fige.facture or existing_invoice(date_debut, date_fin, customer)

    existing = existing_invoice(date_debut, date_fin, customer)
    if existing:
        print(f"  [skip]   Facture lait déjà émise pour {customer} "
              f"{date_debut} → {date_fin} ({existing})")
        return existing

    volume, tb, tp = _period_volumes(date_debut, date_fin, acheteur=cle_ventilation)
    if volume <= 0:
        print(f"  [skip]   Aucun lait vendu (BLJ) à {customer} sur "
              f"{date_debut} → {date_fin}")
        return None

    prix = compute_milk_rate(tb, tp, date=date_fin, volume=volume, detail=True,
                             acheteur=customer)

    dlm = _find_or_create_decompte(date_debut, date_fin, customer,
                                   volume, tb, tp, prix,
                                   acheteur_unique=acheteur_unique)
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
                    + f" — acheteur {customer}"
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
    print(f"  [create] Facture lait {si.name} ({customer}) : {volume:.0f} L "
          f"@ {rate} TND/L = {si.grand_total} TND ({_libelle_prix(prix)}) — "
          f"décompte {dlm.name}")
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
    """Scheduler job — facture le mois civil précédent, tous acheteurs
    confondus. Idempotent, safe daily. Retourne la liste des factures."""
    first_of_this_month = get_first_day(today())
    prev_last = add_days(first_of_this_month, -1)
    prev_first = get_first_day(prev_last)
    return generate_milk_invoice(str(prev_first), str(get_last_day(prev_last)))
