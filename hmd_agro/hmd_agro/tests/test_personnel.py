"""
FIN-S42 — tests du registre Personnel et de la masse salariale (RG-FIN-41,
RC-FIN-41/42).

Couvre :
  1. Saisie : atelier proposé par le rôle, coût employeur calculé
  2. Garde-fous ERR-PERS-01/02/03/05/06/07
  3. `masse_salariale` : prorata d'entrée/sortie, ventilation multi-ateliers,
     charges patronales seulement sur les salariés assujettis
  4. `post_salaires` depuis le registre : écriture 640/647 ↔ 421/453
     équilibrée, ventilée, idempotente
  5. Le chemin « montants forcés » (reprise d'historique) reste intact

Pré-requis site : socle comptable (comptes 640/647/421/453 + ateliers).

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_personnel.run
"""
import traceback

import frappe
from frappe.utils import get_first_day, get_last_day, getdate, today

from hmd_agro.hmd_agro.utils import charges_utils, finance_kpis

PREFIXE = "ZZTEST"
COMPANY = "hmd-agro"


def _abbr():
    return frappe.db.get_value("Company", COMPANY, "abbr")


def _cc(nom_court):
    return f"{nom_court} - {_abbr()}"


def _periode():
    d = getdate(today())
    return f"{d.year}-{d.month:02d}"


def _cleanup():
    for name in frappe.get_all(
            "Personnel", filters={"nom_complet": ["like", f"{PREFIXE}%"]}, pluck="name"):
        frappe.delete_doc("Personnel", name, force=True, ignore_permissions=True)
    je = charges_utils.existing_entry(_periode())
    if je:
        frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", je)
        frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent=%s", je)
        frappe.db.sql("DELETE FROM `tabJournal Entry` WHERE name=%s", je)
    frappe.db.commit()


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


def _personnel(nom, **kwargs):
    payload = {
        "doctype": "Personnel",
        "nom_complet": f"{PREFIXE} {nom}",
        "role_personnel": "OUVRIER_TRAITE",
        "date_embauche": str(get_first_day(today())),
        "statut": "ACTIF",
        "salaire_brut_mensuel": 1000,
    }
    payload.update(kwargs)
    return frappe.get_doc(payload).insert(ignore_permissions=True)


def run():
    print("\n" + "=" * 70)
    print("  FIN-S42 — Registre Personnel & masse salariale")
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

    periode = _periode()
    premier, dernier = get_first_day(today()), get_last_day(today())
    jours_mois = (dernier - premier).days + 1
    taux = float(frappe.db.get_single_value(
        "HMD Configuration", "taux_charges_patronales_pct") or 16.57)

    base = charges_utils.masse_salariale(periode)

    # ── 1. Saisie
    p1 = _personnel("Plein Temps", role_personnel="OUVRIER_TRAITE",
                    salaire_brut_mensuel=1000)
    _check(p1.atelier == _cc("Lait"),
           f"Atelier proposé par le rôle OUVRIER_TRAITE → {p1.atelier}", results)
    attendu = 1000 * (1 + taux / 100)
    _check(abs(p1.cout_employeur_mensuel - attendu) < 0.01,
           f"Coût employeur = brut + {taux} % de charges "
           f"({p1.cout_employeur_mensuel:.2f})", results)

    p2 = _personnel("Mi Temps", salaire_brut_mensuel=1000, taux_activite_pct=50,
                    soumis_cnss=0)
    _check(abs(p2.cout_employeur_mensuel - 500) < 0.01,
           "Taux d'activité 50 % sans CNSS → coût 500", results)

    # ── 2. Garde-fous
    _throws(lambda: _personnel("Negatif", salaire_brut_mensuel=-1),
            "ERR-PERS-01", "Salaire négatif refusé", results)
    _throws(lambda: _personnel("Dates", date_embauche=str(dernier),
                               date_sortie=str(premier)),
            "ERR-PERS-02", "Sortie avant embauche refusée", results)
    _throws(lambda: _personnel(
        "Repartition", repartition=[{"atelier": _cc("Lait"), "pourcentage": 60},
                                    {"atelier": _cc("Traction"), "pourcentage": 30}]),
        "ERR-PERS-03", "Répartition ≠ 100 % refusée", results)
    _throws(lambda: _personnel("Doublon",
                               repartition=[{"atelier": _cc("Lait"), "pourcentage": 50},
                                            {"atelier": _cc("Lait"), "pourcentage": 50}]),
            "ERR-PERS-07", "Atelier en double refusé", results)
    _throws(lambda: _personnel("Activite", taux_activite_pct=150),
            "ERR-PERS-05", "Taux d'activité > 100 % refusé", results)
    _throws(lambda: _personnel("Sorti", statut="SORTI"),
            "ERR-PERS-06", "Statut SORTI sans date refusé", results)
    _throws(lambda: _personnel("Groupe", atelier=frappe.db.get_value(
        "Cost Center", {"company": COMPANY, "is_group": 1}, "name")),
        "ERR-PERS-04", "Atelier groupe refusé", results)

    p3 = _personnel("Parti", date_embauche=str(premier), date_sortie=str(dernier))
    _check(p3.statut == "SORTI",
           "Date de sortie renseignée → statut basculé à SORTI", results)

    # ── 3. Masse salariale : prorata et ventilation
    mi_mois = getdate(premier).replace(day=min(16, jours_mois))
    jours_attendus = (dernier - mi_mois).days + 1
    _personnel("Arrivee Mi Mois", salaire_brut_mensuel=1200,
               date_embauche=str(mi_mois), soumis_cnss=0)
    _personnel("Multi Atelier", salaire_brut_mensuel=1000, soumis_cnss=0,
               atelier=_cc("Lait"),
               repartition=[{"atelier": _cc("Lait"), "pourcentage": 70},
                            {"atelier": _cc("Traction"), "pourcentage": 30}])

    masse = charges_utils.masse_salariale(periode)
    ligne_prorata = next(l for l in masse["lignes"]
                         if l["nom"].endswith("Arrivee Mi Mois"))
    _check(ligne_prorata["jours"] == jours_attendus,
           f"Prorata d'entrée : {ligne_prorata['jours']} j sur {jours_mois}", results)
    _check(abs(ligne_prorata["brut"] - 1200 * jours_attendus / jours_mois) < 0.01,
           f"Brut proratisé = {ligne_prorata['brut']:.2f} TND", results)
    _check(ligne_prorata["charges"] == 0,
           "Salarié non assujetti → aucune charge patronale", results)

    delta_traction = masse["salaires"].get(_cc("Traction"), 0) \
        - base["salaires"].get(_cc("Traction"), 0)
    _check(abs(delta_traction - 300) < 0.01,
           f"Ventilation 70/30 : {delta_traction:.2f} TND sur Traction", results)

    # p3 est sorti le dernier jour du mois : il compte encore ce mois-ci
    _check(any(l["nom"].endswith("Parti") for l in masse["lignes"]),
           "Un salarié sorti en fin de mois est compté sur le mois", results)

    # ── 4. Écriture depuis le registre
    je_name = charges_utils.post_salaires(periode)
    _check(bool(je_name), f"Écriture de salaires postée ({je_name})", results)
    je = frappe.get_doc("Journal Entry", je_name)
    _check(je.docstatus == 1, "Écriture soumise", results)
    _check(abs(je.total_debit - je.total_credit) < 0.01,
           f"Écriture équilibrée ({je.total_debit:.2f} TND)", results)

    comptes = {}
    for ligne in je.accounts:
        numero = frappe.db.get_value("Account", ligne.account, "account_number")
        comptes.setdefault(numero, {"debit": 0.0, "credit": 0.0, "cc": set()})
        comptes[numero]["debit"] += ligne.debit_in_account_currency or 0
        comptes[numero]["credit"] += ligne.credit_in_account_currency or 0
        if ligne.cost_center:
            comptes[numero]["cc"].add(ligne.cost_center)

    total_brut = sum(masse["salaires"].values())
    total_charges = sum(masse["charges_sociales"].values())
    _check(abs(comptes.get("640", {}).get("debit", 0) - total_brut) < 0.01,
           f"640 Salaires débité du brut ({total_brut:.2f})", results)
    _check(abs(comptes.get("647", {}).get("debit", 0) - total_charges) < 0.01,
           f"647 Charges sociales débité ({total_charges:.2f})", results)
    _check(abs(comptes.get("421", {}).get("credit", 0) - total_brut) < 0.01,
           "421 Rémunérations dues créditées du brut", results)
    _check(abs(comptes.get("453", {}).get("credit", 0) - total_charges) < 0.01,
           "453 Organismes sociaux crédités des charges", results)
    _check(len(comptes.get("640", {}).get("cc", set())) >= 2,
           f"Salaires ventilés sur {len(comptes['640']['cc'])} ateliers "
           "(RG-FIN-40)", results)

    _check(charges_utils.post_salaires(periode) == je_name,
           "Re-post = no-op (idempotence par marqueur)", results)

    # `_cleanup` a retiré toute autre écriture de salaires du mois : le 64x du
    # Grand Livre ne contient que celle qu'on vient de poster.
    gl = finance_kpis.gl_sums(str(premier), str(dernier))
    _check(abs(gl["mo"] - (total_brut + total_charges)) < 0.02,
           f"MO du Grand Livre (64x) = brut + charges ({gl['mo']:.2f})", results)

    # ── 5. Chemin « montants forcés » (reprise d'historique)
    _cleanup()
    je_force = charges_utils.post_salaires(periode, {"Lait": 2000})
    forcee = frappe.get_doc("Journal Entry", je_force)
    _check(abs(forcee.total_debit - 2000) < 0.01,
           "Montants forcés : écriture de 2000 TND inchangée", results)
    _check(all(frappe.db.get_value("Account", l.account, "account_number") in ("640", "421")
               for l in forcee.accounts),
           "Montants forcés : uniquement 640/421 (pas de charges patronales)", results)

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
