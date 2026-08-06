"""
EPIC E — Charges & main-d'œuvre ventilées par atelier (FIN-S40/S41/S42,
RG-FIN-40/41).

Les charges diverses (énergie, eau, loyer, assurances…) se saisissent en
Purchase Invoice / Journal Entry standard, imputées aux comptes 60x/61x/62x
et au Cost Center atelier — rien à coder, le socle porte le référentiel.

Ce module porte le flux salaires sans module Payroll (`hrms` non installé) :
UNE écriture mensuelle ventilée par atelier, construite **depuis le registre
`Personnel`** (FIN-S42) — plus aucun montant global tapé à la main :

    Débit  640 Salaires            par atelier (brut × activité × prorata)
    Débit  647 Charges sociales    par atelier (charges patronales)
    Crédit 421 Personnel - rémunérations dues   (total brut)
    Crédit 453 Organismes sociaux               (total charges patronales)

Prorata (RC-FIN-42) : un salarié embauché ou sorti en cours de mois n'est
compté qu'au prorata des jours couverts — sinon le coût MO du mois d'entrée
est faux et le coût/litre avec lui.

Idempotente par marqueur `SALAIRES_<période>` dans user_remark (pattern maison).

Run:
    # depuis le registre Personnel (nominal)
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.utils.charges_utils.post_salaires \\
        --kwargs "{'periode': '2026-07'}"

    # montants forcés (reprise d'historique, avant que le registre existe)
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.utils.charges_utils.post_salaires \\
        --kwargs "{'periode': '2026-07', 'montants_par_atelier':
                   {'Lait': 4000, 'Élevage - Génisses': 1500}}"
"""
import json

import frappe
from frappe.utils import cint, flt, get_first_day, get_last_day, getdate, today

from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

COMPTE_SALAIRES = "640"
COMPTE_CHARGES_SOCIALES = "647"
COMPTE_PERSONNEL = "421"
COMPTE_ORGANISMES_SOCIAUX = "453"


def _acc(number):
    return frappe.db.get_value("Account", {"company": COMPANY, "account_number": number})


def _marker(periode):
    return f"SALAIRES_{periode}"


def _bornes(periode):
    """('YYYY-MM') → (premier jour, dernier jour) du mois."""
    premier = get_first_day(getdate(f"{periode}-01"))
    return premier, get_last_day(premier)


def existing_entry(periode):
    return frappe.db.get_value(
        "Journal Entry",
        {"user_remark": ["like", f"%{_marker(periode)}%"], "docstatus": ["<", 2]},
        "name",
    )


# ─── Masse salariale depuis le registre Personnel (FIN-S42) ──────────────────

def _remuneration_effective(nom, doc, date_reference):
    """Rémunération en vigueur à `date_reference` (A2) : la dernière ligne
    d'historique dont `date_effet` <= date_reference. Les lignes stockent le
    taux de charges patronales RÉSOLU au moment du changement (figé par
    `Personnel._append_historique`) : il est utilisé tel quel, SANS repli sur
    le taux global du jour — c'est ce qui empêche un changement du taux
    global de réécrire les charges des mois déjà postés. Les champs vivants
    de la fiche ne servent que de repli quand l'historique est vide (fiches
    d'avant la migration v1_8) ; sur ce chemin legacy seulement, un taux
    salarié vide se résout sur le taux global actuel."""
    from hmd_agro.hmd_agro.doctype.personnel.personnel import taux_charges_patronales

    lignes = frappe.get_all(
        "Personnel Salaire Historique",
        filters={"parent": nom, "parenttype": "Personnel",
                 "date_effet": ["<=", date_reference]},
        fields=["salaire_brut_mensuel", "taux_activite_pct",
                "taux_charges_patronales_pct", "soumis_cnss"],
        order_by="date_effet desc, idx desc",
        limit=1,
    )
    if lignes:
        source = lignes[0]
        taux_charges = flt(source.taux_charges_patronales_pct)
    else:
        source = doc
        taux_charges = flt(doc.taux_charges_patronales_pct) or taux_charges_patronales()
    return {
        "salaire": flt(source.salaire_brut_mensuel),
        "taux_activite": flt(source.taux_activite_pct or 100),
        "taux_charges": taux_charges,
        "soumis_cnss": cint(source.soumis_cnss),
    }


def _primes_de(nom, periode):
    """[{name, montant, motif}] — primes du salarié rattachées au mois."""
    return frappe.get_all(
        "Prime Personnel",
        filters={"personnel": nom, "periode": periode},
        fields=["name", "montant", "motif"],
        order_by="name",
    )


def masse_salariale(periode):
    """Reconstruit la masse salariale du mois depuis le registre `Personnel`.

    La rémunération de chaque salarié est celle **en vigueur sur le mois**
    (historique de salaire immuable — A2) ; les primes du mois (`Prime
    Personnel`) s'ajoutent au brut (640) et entrent dans l'assiette des
    charges patronales (647) seulement si le salarié est soumis CNSS.

    Retourne :
        {
          "salaires":        {cost_center: brut prorata + primes},
          "charges_sociales":{cost_center: charges patronales prorata},
          "effectif":        nombre de salariés comptés,
          "lignes":          [{personnel, nom, role, jours, brut, primes,
                               charges, detail_primes}, …],
        }
    Un mois sans salarié actif retourne des dicts vides — 0 honnête, même
    posture que les coûts SLE.
    """
    premier, dernier = _bornes(periode)
    jours_mois = (dernier - premier).days + 1

    # Présent sur le mois = embauché avant la fin ET pas encore sorti au début.
    noms = frappe.db.sql_list("""
        SELECT name FROM `tabPersonnel`
        WHERE date_embauche <= %s
          AND (date_sortie IS NULL OR date_sortie >= %s)
        ORDER BY name
    """, (dernier, premier))

    salaires, charges, lignes = {}, {}, []
    for nom in noms:
        doc = frappe.get_doc("Personnel", nom)
        debut = max(getdate(doc.date_embauche), premier)
        fin = min(getdate(doc.date_sortie), dernier) if doc.date_sortie else dernier
        jours = (fin - debut).days + 1
        if jours <= 0:
            continue
        prorata = jours / jours_mois
        remu = _remuneration_effective(nom, doc, dernier)
        # Taux déjà résolu par _remuneration_effective : figé (historique)
        # ou legacy (fiche + repli global) — pas de second repli ici.
        taux = remu["taux_charges"]
        primes_lignes = _primes_de(nom, periode)
        primes = sum(flt(p.montant) for p in primes_lignes)
        brut = remu["salaire"] * remu["taux_activite"] / 100.0 * prorata + primes
        charge = brut * taux / 100.0 if remu["soumis_cnss"] else 0.0
        if brut <= 0 and charge <= 0:
            continue
        for cc, part in doc.ventilation().items():
            if not cc:
                continue
            salaires[cc] = salaires.get(cc, 0.0) + brut * part / 100.0
            charges[cc] = charges.get(cc, 0.0) + charge * part / 100.0
        lignes.append({
            "personnel": nom, "nom": doc.nom_complet, "role": doc.role_personnel,
            "jours": jours, "brut": round(brut, 3), "primes": round(primes, 3),
            "charges": round(charge, 3),
            "detail_primes": [
                {"prime": p.name, "montant": flt(p.montant), "motif": p.motif}
                for p in primes_lignes
            ],
        })

    return {
        "salaires": {cc: round(v, 3) for cc, v in salaires.items() if v},
        "charges_sociales": {cc: round(v, 3) for cc, v in charges.items() if v},
        "effectif": len(lignes),
        "lignes": lignes,
    }


# ─── Écriture mensuelle ──────────────────────────────────────────────────────

@frappe.whitelist()
def post_salaires(periode, montants_par_atelier=None, submit=True):
    """Poste la masse salariale du mois ventilée par atelier (RG-FIN-40/41).

    Args:
        periode:              'YYYY-MM' (écriture datée au dernier jour du mois,
                              ou à aujourd'hui si le mois n'est pas terminé)
        montants_par_atelier: optionnel — dict {atelier: montant DT} pour forcer
                              les montants (reprise d'historique). L'atelier est
                              le nom court du Cost Center (ex. 'Lait') ou son
                              nom complet ('Lait - HMD'). Omis → la masse est
                              reconstruite depuis le registre `Personnel`.
    Returns: le nom du Journal Entry (existant si déjà posté — idempotent).
    """
    if isinstance(montants_par_atelier, str):
        montants_par_atelier = json.loads(montants_par_atelier)

    existing = existing_entry(periode)
    if existing:
        print(f"  [skip]   Salaires {periode} déjà postés ({existing})")
        return existing

    if montants_par_atelier:
        salaires = {k: float(v) for k, v in montants_par_atelier.items() if float(v) > 0}
        charges, effectif, source = {}, None, "montants forcés"
    else:
        masse = masse_salariale(periode)
        salaires, charges = masse["salaires"], masse["charges_sociales"]
        effectif, source = masse["effectif"], f"registre Personnel, {masse['effectif']} pers."

    if not salaires:
        print(f"  [skip]   Salaires {periode} : aucun montant "
              f"({'registre Personnel vide' if effectif == 0 else 'montants nuls'})")
        return None

    accounts, total_brut, total_charges = [], 0.0, 0.0
    for atelier, montant in salaires.items():
        accounts.append({
            "account": _compte(COMPTE_SALAIRES, "Salaires"),
            "debit_in_account_currency": round(montant, 3),
            "cost_center": _cost_center(atelier),
        })
        total_brut += montant
    for atelier, montant in charges.items():
        accounts.append({
            "account": _compte(COMPTE_CHARGES_SOCIALES, "Charges sociales"),
            "debit_in_account_currency": round(montant, 3),
            "cost_center": _cost_center(atelier),
        })
        total_charges += montant

    accounts.append({
        "account": _compte(COMPTE_PERSONNEL, "Personnel - rémunérations dues"),
        "credit_in_account_currency": round(total_brut, 3),
    })
    if total_charges:
        accounts.append({
            "account": _compte(COMPTE_ORGANISMES_SOCIAUX, "Organismes sociaux"),
            "credit_in_account_currency": round(total_charges, 3),
        })

    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "company": COMPANY,
        # Dernier jour du mois, mais jamais dans le futur : poster au 31 un
        # mois en cours daterait la charge d'après-demain — elle sortirait de
        # tout pilotage « mois à date » et fausserait le coût MO du litre.
        "posting_date": min(_bornes(periode)[1], getdate(today())),
        "accounts": accounts,
        "user_remark": (
            f"{_marker(periode)} — masse salariale ventilée sur "
            f"{len(salaires)} atelier(s) : {round(total_brut, 3)} TND de brut"
            + (f" + {round(total_charges, 3)} TND de charges patronales"
               if total_charges else "")
            + f" ({source})"
        ),
    })
    je.insert(ignore_permissions=True)
    if submit:
        je.submit()
    print(f"  [create] Salaires {periode} : {je.name} — "
          f"{round(total_brut + total_charges, 3)} TND sur {len(salaires)} ateliers "
          f"({source})")
    return je.name


def _compte(number, libelle):
    account = _acc(number)
    if not account:
        frappe.throw(
            f"ERR-FIN-05 : compte {number} ({libelle}) introuvable — "
            "lancer le socle comptable (setup.finance.socle_comptable)."
        )
    return account


def _cost_center(atelier):
    """Accepte le nom court ('Lait') ou complet ('Lait - HMD')."""
    if frappe.db.exists("Cost Center", atelier):
        return atelier
    abbr = frappe.db.get_value("Company", COMPANY, "abbr")
    complet = f"{atelier} - {abbr}"
    if not frappe.db.exists("Cost Center", complet):
        frappe.throw(f"ERR-FIN-06 : Cost Center '{complet}' introuvable (RG-FIN-40).")
    return complet


def post_salaires_mois_precedent():
    """Job mensuel — poste la masse salariale du mois civil écoulé depuis le
    registre Personnel. Idempotent (marqueur), sans effet si le registre est
    vide."""
    from frappe.utils import add_days

    dernier_mois = getdate(add_days(get_first_day(today()), -1))
    return post_salaires(f"{dernier_mois.year}-{dernier_mois.month:02d}")


@frappe.whitelist()
def apercu_masse_salariale(periode=None):
    """Aperçu console de la masse salariale d'un mois — sert au contrôle avant
    de poster (aucune écriture n'est créée)."""
    if not periode:
        d = getdate(today())
        periode = f"{d.year}-{d.month:02d}"
    masse = masse_salariale(periode)
    print(f"\n  Masse salariale {periode} — {masse['effectif']} salarié(s)")
    for ligne in masse["lignes"]:
        print(f"    {ligne['nom']:<28} {ligne['role']:<22} "
              f"{ligne['jours']:>2} j  {ligne['brut']:>10.3f} + "
              f"{ligne['charges']:>8.3f} TND")
    print("    " + "─" * 62)
    for cc, montant in sorted(masse["salaires"].items()):
        charge = masse["charges_sociales"].get(cc, 0)
        print(f"    {cc:<34} {montant:>10.3f} + {charge:>8.3f} TND")
    total = sum(masse["salaires"].values()) + sum(masse["charges_sociales"].values())
    print(f"    {'TOTAL coût employeur':<34} {total:>10.3f} TND\n")
    return masse
