"""Applique réellement les charges patronales à 30 % (réunion du 05/08/2026).

`v1_8/init_rh_defaults` a fait deux choses justes mais incomplètes : il a figé
l'ANCIEN taux (16,57 %) dans la ligne d'historique initiale — pour que les mois
déjà postés ne soient jamais réécrits — et porté le taux global à 30 %. Mais
`masse_salariale` lit le taux de la dernière ligne d'historique en vigueur :
sans nouvelle ligne, tous les mois À VENIR continuaient d'être calculés à
16,57 %, et le coût employeur affiché sur chaque fiche restait celui d'avant la
bascule. La décision de M. Samir n'avait donc aucun effet.

Ce patch journalise le changement de taux comme un événement daté :

    embauche ─── 16,57 % ───► 1er du mois courant ─── 30 % ───►

soit exactement la règle demandée : le passé reste figé, le présent et le futur
appliquent le nouveau taux. La date d'effet est le 1er du mois en cours, ou le
1er du mois suivant si la paie du mois est déjà passée au Grand Livre (on ne
crée jamais d'écart entre le registre et une écriture déjà postée).

Ne concerne que les salariés soumis CNSS et sans taux personnel : une surcharge
saisie sur une fiche est une décision de la ferme, elle est respectée.

Idempotent : ne fait rien dès que la dernière ligne d'historique porte déjà le
taux global courant.
"""
import frappe
from frappe.utils import add_months, cint, flt, get_first_day, getdate, today

MOTIF = "Passage aux charges patronales 30 % (réunion 05/08/2026)"


def execute():
    if not frappe.db.exists("DocType", "Personnel") or \
            not frappe.db.exists("DocType", "Personnel Salaire Historique"):
        return

    taux_global = flt(frappe.db.get_single_value(
        "HMD Configuration", "taux_charges_patronales_pct"))
    if not taux_global:
        return

    date_effet = _date_effet()
    touches = []
    for nom in frappe.get_all("Personnel", pluck="name"):
        if _appliquer(nom, taux_global, date_effet):
            touches.append(nom)

    if touches:
        frappe.db.commit()
        message = (f"appliquer_taux_charges_30: {len(touches)} fiche(s) passée(s) "
                   f"à {taux_global} % au {date_effet}")
        print(f"  [RH] {message}")
        frappe.logger("hmd_agro").info(message)


def _date_effet():
    """1er du mois courant — ou du mois suivant si sa paie est déjà postée."""
    from hmd_agro.hmd_agro.utils.charges_utils import existing_entry

    premier = get_first_day(getdate(today()))
    if existing_entry(premier.strftime("%Y-%m")):
        premier = get_first_day(add_months(premier, 1))
    return premier


def _appliquer(nom, taux_global, date_effet):
    doc = frappe.get_doc("Personnel", nom)

    # Surcharge salarié : décision de la ferme, on n'y touche pas.
    surcharge = flt(doc.get("taux_charges_patronales_pct"))
    taux_cible = surcharge or (taux_global if cint(doc.soumis_cnss) else 0.0)

    derniere = frappe.get_all(
        "Personnel Salaire Historique",
        filters={"parent": nom, "parenttype": "Personnel"},
        fields=["date_effet", "taux_charges_patronales_pct"],
        order_by="date_effet desc, idx desc", limit=1,
    )
    if derniere and abs(flt(derniere[0]["taux_charges_patronales_pct"]) - taux_cible) < 0.001:
        return _rafraichir_cout(doc, taux_cible)

    if derniere and getdate(derniere[0]["date_effet"]) >= getdate(date_effet):
        # Une ligne plus récente existe déjà : ne pas réécrire le journal.
        return _rafraichir_cout(doc, taux_cible)

    doc.append("historique_salaires", {
        "date_effet": date_effet,
        "salaire_brut_mensuel": flt(doc.salaire_brut_mensuel),
        "taux_activite_pct": flt(doc.taux_activite_pct or 100),
        "taux_charges_patronales_pct": taux_cible,
        "soumis_cnss": cint(doc.soumis_cnss),
        "motif": MOTIF,
    })
    # Données historiques : le patch journalise, il ne corrige pas les fiches
    # (atelier manquant, etc.) — mêmes garde-fous que init_rh_defaults.
    doc.flags.ignore_validate = True
    doc.flags.ignore_mandatory = True
    doc.save(ignore_permissions=True)
    _rafraichir_cout(doc, taux_cible)
    return True


def _rafraichir_cout(doc, taux):
    """Le coût employeur stocké est recalculé au taux applicable : sans cela la
    fiche continue d'afficher le montant d'avant la bascule jusqu'au prochain
    enregistrement manuel."""
    brut = flt(doc.salaire_brut_mensuel) * flt(doc.taux_activite_pct or 100) / 100.0
    cout = round(brut * (1 + flt(taux) / 100.0) if cint(doc.soumis_cnss) else brut, 3)
    if abs(flt(doc.cout_employeur_mensuel) - cout) >= 0.001:
        frappe.db.set_value("Personnel", doc.name, "cout_employeur_mensuel", cout,
                            update_modified=False)
        return True
    return False
