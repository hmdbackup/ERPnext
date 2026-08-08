"""
SCRUM-11 — Rapport Interventions : les interventions mécaniques de la période.

`maintenance_utils` sait depuis FIN-S32 enregistrer une intervention et en
totaliser le coût, mais rien ne les LISTAIT : le Rapport Performance n'en
affiche que le montant agrégé et le nombre. Un gérant qui voyait
« Interventions sur Équipements : 7 » ne pouvait pas savoir lesquelles.

Trois blocs :

  1. **Réalisées** — une ligne par intervention de la période
     (`interventions_realisees`), avec total.
  2. **Préventif** — les tâches dues ou en retard (`interventions_planifiees`).
     ⚠ Ce bloc est « à ce jour », PAS « sur la période » : ERPNext date les
     `Asset Maintenance Log` à leur échéance, laquelle est par nature dans le
     futur. Le libellé de section le dit à l'écran plutôt que de laisser
     croire à un filtrage par période.
  3. **Rapprochement** — l'écart entre le compte 615 du Grand Livre et la somme
     des interventions saisies.

━━ POURQUOI LE BLOC 3 EXISTE (et pourquoi il ne faut pas le masquer) ━━━━━━━━━
`cout_maintenance` lit DEUX sources qui ne peuvent pas coïncider :
  • `cout`           ← Grand Livre, compte 615 (SUM debit − credit)
  • `par_equipement` ← `Asset Repair` soumis (total_repair_cost)
Une facture d'entretien passée en comptabilité sans `Asset Repair` gonfle la
première sans toucher la seconde ; une intervention interne (coût 0) alimente
la seconde sans rien poster. L'écart est donc NORMAL — et c'est précisément
l'information utile : « 400 DT d'entretien qui ne sont rattachés à aucun
équipement ». N'afficher qu'un seul des deux montants transformerait un
rapport de pilotage en rapport rassurant.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Lecture seule — n'écrit rien, réexécutable à volonté.

Utilisation :
  • Desk → Rapport « Rapport Interventions »
  • Console :
        bench --site hmd.agro execute \\
            hmd_agro.hmd_agro.report.rapport_interventions.\\
rapport_interventions.execute --kwargs "{'filters': {'periode': 'Mois'}}"
"""
from frappe.utils import cint, flt, getdate, today

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.maintenance_utils import (
    cout_maintenance, interventions_planifiees, interventions_realisees,
)

# Horizon du bloc préventif, en jours. Le défaut 30 est celui de
# `interventions_planifiees`. Le contrôle de cohérence, lui, appelle
# `interventions_planifiees(0)` : il ne regarde que les retards, pas l'horizon —
# changer cette valeur ne le déplacera donc pas.
# Le champ n'existe pas encore dans HMD Configuration : `get_config` retombe sur
# ce défaut (comportement garanti par test_hmd_config.test_get_config_falls_back),
# et l'horizon devient réglable le jour où on ajoute le champ.
HORIZON_PREVENTIF_DEFAUT = 30

COLUMNS = [
    {"fieldname": "section", "label": "Section", "fieldtype": "Data", "width": 150},
    {"fieldname": "date", "label": "Date", "fieldtype": "Date", "width": 100},
    {"fieldname": "equipement", "label": "Équipement", "fieldtype": "Link",
     "options": "Asset", "width": 160},
    {"fieldname": "designation", "label": "Désignation", "fieldtype": "Data",
     "width": 180},
    {"fieldname": "type", "label": "Type", "fieldtype": "Data", "width": 110},
    {"fieldname": "libelle", "label": "Intervention", "fieldtype": "Data",
     "width": 300},
    {"fieldname": "atelier", "label": "Atelier", "fieldtype": "Link",
     "options": "Cost Center", "width": 170},
    {"fieldname": "intervenant", "label": "Intervenant", "fieldtype": "Link",
     "options": "Personnel", "width": 130},
    {"fieldname": "cout", "label": "Coût", "fieldtype": "Currency", "width": 120},
]


def execute(filters=None):
    filters = filters or {}
    periode = filters.get("periode") or "Mois"
    date = getdate(filters.get("date") or today())
    equipement = filters.get("equipement")
    atelier = filters.get("atelier")

    # `rapport_performance` détient les bornes de période (lui-même délègue les
    # bornes de semaine ISO à `rapport_periodique`). On ne les redérive pas —
    # même précédent que le lazy import de `couverture_lait`.
    from hmd_agro.hmd_agro.report.rapport_performance.rapport_performance import (
        period_bounds,
    )
    debut, fin = period_bounds(periode, date)

    today_dt = getdate(today())
    if debut > today_dt:
        # Aucune intervention réalisée ni rapprochement possible sur une période
        # à venir — mais le préventif, lui, est « à ce jour » : le masquer
        # cacherait les retards au moment précis où l'on prépare un planning.
        return COLUMNS, ([_row("INFO", libelle="Pas encore d'intervention sur "
                                               "cette période.")]
                         + _preventif(equipement, atelier))
    # On ne compte que les jours réellement écoulés (mois en cours).
    fin = min(fin, today_dt)

    lignes = interventions_realisees(debut, fin, equipement, atelier)

    data = _realisees(lignes)
    data.extend(_preventif(equipement, atelier))
    data.extend(_rapprochement(debut, fin, lignes, equipement, atelier))
    return COLUMNS, data


def _row(section, date=None, equipement=None, designation=None, type_=None,
         libelle=None, atelier=None, intervenant=None, cout=None, indicator=""):
    return {"section": section, "date": date, "equipement": equipement,
            "designation": designation, "type": type_, "libelle": libelle,
            "atelier": atelier, "intervenant": intervenant, "cout": cout,
            "indicator": indicator}


# ─── (i) Interventions réalisées ─────────────────────────────────────────────

def _realisees(lignes):
    s = "Réalisées"
    if not lignes:
        return [_row(s, libelle="Aucune intervention saisie sur la période.")]

    rows = []
    for ligne in lignes:
        # `enregistrer_intervention` impute toujours un atelier (`_cost_center`
        # tombe au pire sur Frais Généraux). Une intervention saisie
        # directement dans l'écran ERPNext, elle, peut n'en avoir aucun : on le
        # DIT dans le libellé plutôt que d'inventer une valeur — la colonne est
        # un Link, y écrire « Frais Généraux » sans le suffixe société
        # produirait un lien mort.
        libelle = ligne.description
        if not ligne.atelier:
            libelle = f"{libelle} — ⚠ aucun atelier imputé"
        rows.append(_row(
            s,
            date=ligne.date,
            equipement=ligne.asset,
            designation=ligne.asset_name,
            type_=ligne.type_intervention,
            libelle=libelle,
            atelier=ligne.atelier,
            intervenant=ligne.personnel,
            cout=flt(ligne.cout),
        ))
    rows.append(_row(s, libelle=f"TOTAL — {len(lignes)} intervention(s), "
                                f"{_nb_equipements(lignes)} équipement(s)",
                     cout=round(sum(flt(l.cout) for l in lignes), 2)))
    return rows


def _nb_equipements(lignes):
    return len({ligne.asset for ligne in lignes})


# ─── (ii) Préventif dû ou en retard ──────────────────────────────────────────

def _preventif(equipement=None, atelier=None):
    """Tâches de maintenance préventive dues sous N jours ou déjà en retard.

    Volontairement NON filtré par la PÉRIODE du rapport : une échéance est un
    fait à venir, la borner au mois affiché reviendrait à cacher les retards
    dès qu'on consulte un mois passé.

    En revanche il RESPECTE les filtres Équipement et Atelier : un bloc qui
    listerait tout le parc sous un filtre équipement ferait lire au gérant des
    retards qui ne concernent pas la machine qu'il regarde.
    """
    jours = cint(get_config("maintenance_horizon_jours",
                            default=HORIZON_PREVENTIF_DEFAUT))
    s = f"Préventif (à ce jour, {jours} j)"
    taches = interventions_planifiees(jours, equipement, atelier)
    if not taches:
        return [_row(s, libelle="Aucune tâche préventive due ou en retard.")]

    aujourdhui = getdate(today())
    rows = []
    for tache in taches:
        en_retard = tache.due_date and getdate(tache.due_date) < aujourdhui
        rows.append(_row(
            s,
            date=tache.due_date,
            # Piège ERPNext : dans « Asset Maintenance Log », `asset_name` est
            # un Link vers Asset, pas un libellé. Il va donc dans la colonne
            # Équipement (Link), jamais dans Désignation.
            equipement=tache.asset_name,
            type_="EN RETARD" if en_retard else "PLANIFIÉE",
            libelle=tache.task_name,
            indicator="Red" if en_retard else "",
        ))
    return rows


# ─── (iii) Rapprochement Grand Livre ↔ interventions ─────────────────────────

def _rapprochement(debut, fin, lignes, equipement, atelier):
    """Écart entre le compte 615 et la somme des interventions saisies.

    Voir l'encadré en tête de module : l'écart est normal, et c'est lui
    l'information.
    """
    s = "Rapprochement"
    # `cout_maintenance` ne sait pas filtrer par équipement ni par atelier :
    # confronter un Grand Livre entier à une liste filtrée produirait un écart
    # faux. On annonce le refus plutôt que d'afficher un chiffre trompeur.
    if equipement or atelier:
        return [_row(s, libelle="Rapprochement masqué : il porte sur la totalité "
                                "de la période, un filtre Équipement ou Atelier "
                                "le rendrait faux.")]

    maint = cout_maintenance(debut, fin)
    gl = flt(maint["cout"])
    saisi = round(sum(flt(ligne.cout) for ligne in lignes), 2)
    ecart = round(gl - saisi, 2)

    return [
        _row(s, libelle="Entretien au Grand Livre (compte 615)", cout=gl),
        _row(s, libelle="Somme des interventions saisies", cout=saisi),
        _row(s, libelle=_libelle_ecart(ecart),
             cout=ecart, indicator="Orange" if ecart else "Green"),
    ]


def _libelle_ecart(ecart):
    if not ecart:
        return "Écart — aucun, chaque dirham d'entretien est rattaché"
    if ecart > 0:
        return ("Écart — entretien comptabilisé SANS intervention saisie "
                "(facture non rattachée à un équipement)")
    return ("Écart — interventions saisies SANS écriture au 615 "
            "(interventions internes, ou charge imputée à un autre compte)")
