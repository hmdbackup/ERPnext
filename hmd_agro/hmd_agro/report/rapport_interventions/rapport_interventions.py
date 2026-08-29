"""
SCRUM-11 — Rapport Interventions : le parc et ses interventions.

`maintenance_utils` sait depuis FIN-S32 enregistrer une intervention et en
totaliser le coût, mais rien ne les LISTAIT : le Rapport Performance n'en
affiche que le montant agrégé et le nombre. Un gérant qui voyait
« Interventions sur Équipements : 7 » ne pouvait pas savoir lesquelles.

Quatre blocs (maquettes validées le 26/08/2026) :

  0. **Parc — état du matériel** — une ligne par équipement, « à ce jour » :
     PRÊT / EN ATTENTE DE MAINTENANCE / EN PANNE, dernière intervention
     terminée, prochaine échéance, heures d'utilisation sur la période
     (`etat_parc`). Une ligne de synthèse compte les états.
  1. **Réalisées** — une ligne par intervention validée de la période
     (`interventions_realisees`), pièces / main-d'œuvre / coût, avec total.
  2. **Préventif** — les échéances dues ou en retard : tâches ERPNext
     (PLANIFIÉE) et fiches « À venir » (`interventions_planifiees`).
     ⚠ Ce bloc est « à ce jour », PAS « sur la période » : une échéance est par
     nature dans le futur. Le libellé de section le dit à l'écran plutôt que
     de laisser croire à un filtrage par période.
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
from hmd_agro.hmd_agro.utils.format_fr import fr_date
from hmd_agro.hmd_agro.utils.maintenance_utils import (
    ECHEANCE_FICHE, PARC_EN_ATTENTE, PARC_EN_PANNE, PARC_PRET, cout_maintenance,
    etat_parc, interventions_planifiees, interventions_realisees,
)

# Horizon du bloc préventif ET de l'état « en attente de maintenance », en
# jours. Le défaut 30 est celui de `interventions_planifiees`. Le contrôle de
# cohérence, lui, appelle `interventions_planifiees(0)` : il ne regarde que les
# retards, pas l'horizon — changer cette valeur ne le déplacera donc pas.
# Le champ n'existe pas encore dans HMD Configuration : `get_config` retombe sur
# ce défaut (comportement garanti par test_hmd_config.test_get_config_falls_back),
# et l'horizon devient réglable le jour où on ajoute le champ.
HORIZON_PREVENTIF_DEFAUT = 30

SECTION_PARC = "Parc — état du matériel"
SECTION_REALISEES = "Réalisées"
SECTION_RAPPROCHEMENT = "Rapprochement"
SECTION_INFO = "INFO"

# What the reader sees for each fleet state, and the colour (`indicator`,
# computed here — never in the JS) that goes with it.
LIBELLES_ETAT_PARC = {
    PARC_PRET: "PRÊT",
    PARC_EN_ATTENTE: "EN ATTENTE DE MAINTENANCE",
    PARC_EN_PANNE: "EN PANNE",
}
INDICATEURS_ETAT_PARC = {
    PARC_PRET: "Green",
    PARC_EN_ATTENTE: "Orange",
    PARC_EN_PANNE: "Red",
}
# A deadline: ERPNext task, planned sheet, or either of them overdue.
TYPE_ECHEANCE_LOG = "PLANIFIÉE"
TYPE_ECHEANCE_FICHE = "À VENIR"
TYPE_ECHEANCE_RETARD = "EN RETARD"

INTERVENANT_INTERNE = "Interne"

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
    # Data, not Link: the intervener is an employee (Personnel) OR a
    # contractor (Supplier) — a single Link cannot point to both.
    {"fieldname": "intervenant", "label": "Intervenant", "fieldtype": "Data",
     "width": 170},
    {"fieldname": "pieces", "label": "Pièces (DT)", "fieldtype": "Currency",
     "width": 110},
    {"fieldname": "main_oeuvre", "label": "M.O. (DT)", "fieldtype": "Currency",
     "width": 110},
    {"fieldname": "cout", "label": "Coût", "fieldtype": "Currency", "width": 120},
    {"fieldname": "heures", "label": "Heures", "fieldtype": "Float", "width": 90},
    # Critère 2 — « il totalise : nombre d'interventions, nombre d'équipements ».
    # Ces deux compteurs vivaient dans le LIBELLÉ du TOTAL : lisibles à l'écran,
    # mais ni triables ni exploitables à l'export, donc le critère n'était rempli
    # qu'à moitié. Ils deviennent des colonnes typées, renseignées sur la seule
    # ligne TOTAL — les lignes de détail les laissent vides plutôt que d'y
    # répéter « 1 », qui se serait additionné dans un tableur.
    {"fieldname": "nb_interventions", "label": "Nb Interventions",
     "fieldtype": "Int", "width": 130},
    {"fieldname": "nb_equipements", "label": "Nb Équipements",
     "fieldtype": "Int", "width": 130},
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
    horizon = _horizon_jours()

    today_dt = getdate(today())
    if debut > today_dt:
        # No completed intervention nor reconciliation possible on a future
        # period — but the fleet and the preventive block are « as of today »:
        # hiding them would hide the delays at the very moment a schedule is
        # being prepared.
        return COLUMNS, (_parc(debut, fin, horizon, equipement, atelier)
                         + [_row(SECTION_INFO, libelle="Pas encore d'intervention "
                                                       "sur cette période.")]
                         + _preventif(horizon, equipement, atelier))
    # On ne compte que les jours réellement écoulés (mois en cours).
    fin_periode = fin
    fin = min(fin, today_dt)

    lignes = interventions_realisees(debut, fin, equipement, atelier)

    data = _parc(debut, fin, horizon, equipement, atelier)
    # Mois en cours : la liste s'arrête à aujourd'hui. Le taire donnait un
    # TOTAL qu'on prenait pour celui du mois entier — et un rapprochement au
    # 615 mécaniquement plus bas que la facture du mois. On le DIT, comme le
    # bloc préventif annonce déjà qu'il n'est pas borné par la période.
    if fin_periode > fin:
        data.append(_row(SECTION_INFO, libelle=(
            f"Période en cours : chiffres arrêtés au {fr_date(fin)} "
            f"(fin de période le {fr_date(fin_periode)}) — "
            f"les totaux ne couvrent pas encore le mois entier.")))
    data.extend(_realisees(lignes))
    data.extend(_preventif(horizon, equipement, atelier))
    data.extend(_rapprochement(debut, fin, lignes, equipement, atelier))
    return COLUMNS, data


def _horizon_jours():
    return cint(get_config("maintenance_horizon_jours",
                           default=HORIZON_PREVENTIF_DEFAUT))


def _row(section, date=None, equipement=None, designation=None, type_=None,
         libelle=None, atelier=None, intervenant=None, pieces=None,
         main_oeuvre=None, cout=None, heures=None, nb_interventions=None,
         nb_equipements=None, indicator=""):
    return {"section": section, "date": date, "equipement": equipement,
            "designation": designation, "type": type_, "libelle": libelle,
            "atelier": atelier, "intervenant": intervenant, "pieces": pieces,
            "main_oeuvre": main_oeuvre, "cout": cout, "heures": heures,
            "nb_interventions": nb_interventions,
            "nb_equipements": nb_equipements,
            "indicator": indicator}


def _montant_ou_rien(valeur):
    """A zero amount is displayed as a dash: « non imputé = un tiret, jamais un 0 »."""
    return flt(valeur) or None


# ─── (0) Parc — état du matériel ─────────────────────────────────────────────

def _parc(debut, fin, horizon, equipement=None, atelier=None):
    """Fleet state « as of today » (like the preventive block); only the usage
    hours are bounded by the displayed period."""
    parc = etat_parc(debut, fin, horizon, equipement, atelier)
    if not parc:
        return [_row(SECTION_PARC, libelle="Aucun équipement au parc "
                                           "(hors animaux, hors cessions).")]
    rows = [_synthese_parc(parc)]
    for eq in parc:
        prochaine = eq["prochaine"]
        rows.append(_row(
            SECTION_PARC,
            date=prochaine["date"] if prochaine else None,
            equipement=eq["asset"],
            designation=eq["designation"],
            type_=LIBELLES_ETAT_PARC[eq["etat"]],
            libelle=_libelle_parc(eq),
            atelier=eq["atelier"],
            heures=_montant_ou_rien(eq["heures"]),
            indicator=INDICATEURS_ETAT_PARC[eq["etat"]],
        ))
    return rows


def _synthese_parc(parc):
    etats = [eq["etat"] for eq in parc]
    en_panne = etats.count(PARC_EN_PANNE)
    en_attente = etats.count(PARC_EN_ATTENTE)
    en_retard = sum(1 for eq in parc if eq["prochaine"] and eq["prochaine"]["en_retard"])
    libelle = (f"{len(parc)} équipement(s) · {etats.count(PARC_PRET)} prêt(s) · "
               f"{en_attente} en attente · {en_panne} en panne · "
               f"{en_retard} échéance(s) dépassée(s)")
    if en_panne:
        indicator = "Red"
    elif en_attente or en_retard:
        indicator = "Orange"
    else:
        indicator = "Green"
    return _row(SECTION_PARC, libelle=libelle, nb_equipements=len(parc),
                indicator=indicator)


def _libelle_parc(eq):
    derniere, prochaine = eq["derniere"], eq["prochaine"]
    texte = (f"Dernière : {fr_date(derniere['date'])} — "
             f"{derniere['description']}"
             if derniere else "Aucune intervention terminée")
    if prochaine:
        texte += f" · Prochaine : {prochaine['libelle']}"
        if prochaine["en_retard"]:
            texte += f" — {TYPE_ECHEANCE_RETARD}"
    return texte


# ─── (i) Interventions réalisées ─────────────────────────────────────────────

def _realisees(lignes):
    s = SECTION_REALISEES
    if not lignes:
        # Critère 5 — « un mois sans intervention affiche zéro, pas une erreur ».
        # La phrase seule ne remplissait le critère qu'à moitié : elle explique
        # l'absence mais ne donne pas le chiffre, et l'export ne portait alors
        # aucune ligne de total. On rend les DEUX — la phrase pour l'écran, le
        # TOTAL à 0 pour le tableur et pour le lecteur qui cherche un nombre.
        return [
            _row(s, libelle="Aucune intervention saisie sur la période."),
            _row(s, libelle="TOTAL — 0 intervention(s), 0 équipement(s)",
                 cout=0.0, nb_interventions=0, nb_equipements=0),
        ]

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
            intervenant=_libelle_intervenant(ligne),
            pieces=_montant_ou_rien(ligne.cout_pieces),
            main_oeuvre=_montant_ou_rien(ligne.cout_main_oeuvre),
            cout=flt(ligne.cout),
        ))
    nb_equip = _nb_equipements(lignes)
    rows.append(_row(s, libelle=f"TOTAL — {len(lignes)} intervention(s), "
                                f"{nb_equip} équipement(s)",
                     pieces=_montant_ou_rien(_somme(lignes, "cout_pieces")),
                     main_oeuvre=_montant_ou_rien(_somme(lignes, "cout_main_oeuvre")),
                     cout=_somme(lignes, "cout"),
                     nb_interventions=len(lignes), nb_equipements=nb_equip))
    return rows


def _libelle_intervenant(ligne):
    """Contractor → company name; employee → « Interne — nom »; else « Interne »."""
    if ligne.prestataire:
        return ligne.prestataire_nom or ligne.prestataire
    if ligne.personnel:
        return f"{INTERVENANT_INTERNE} — {ligne.personnel_nom or ligne.personnel}"
    return INTERVENANT_INTERNE


def _somme(lignes, champ):
    return round(sum(flt(ligne.get(champ)) for ligne in lignes), 2)


def _nb_equipements(lignes):
    return len({ligne.asset for ligne in lignes})


# ─── (ii) Préventif dû ou en retard ──────────────────────────────────────────

def _preventif(jours, equipement=None, atelier=None):
    """Deadlines due within N days or already overdue: ERPNext preventive
    tasks (PLANIFIÉE) and « À venir » sheets (À VENIR).

    Deliberately NOT filtered by the report PERIOD: a deadline is a future
    fact, bounding it to the displayed month would hide the delays as soon as
    a past month is consulted.

    It DOES honour the Équipement and Atelier filters: a block listing the
    whole fleet under an equipment filter would make the manager read delays
    unrelated to the machine he is looking at.
    """
    s = f"Préventif (à ce jour, {jours} j)"
    taches = interventions_planifiees(jours, equipement, atelier)
    if not taches:
        return [_row(s, libelle="Aucune tâche préventive due ou en retard.")]

    aujourdhui = getdate(today())
    rows = []
    for tache in taches:
        en_retard = getdate(tache.due_date) < aujourdhui
        rows.append(_row(
            s,
            date=tache.due_date,
            equipement=tache.asset_name,
            designation=tache.designation,
            type_=_type_echeance(tache, en_retard),
            libelle=tache.task_name,
            atelier=tache.atelier,
            indicator=_indicateur_echeance(tache, en_retard),
        ))
    return rows


def _type_echeance(tache, en_retard):
    if en_retard:
        return TYPE_ECHEANCE_RETARD
    return TYPE_ECHEANCE_FICHE if tache.source == ECHEANCE_FICHE else TYPE_ECHEANCE_LOG


def _indicateur_echeance(tache, en_retard):
    if en_retard:
        return "Red"
    return "Blue" if tache.source == ECHEANCE_FICHE else ""


# ─── (iii) Rapprochement Grand Livre ↔ interventions ─────────────────────────

def _rapprochement(debut, fin, lignes, equipement, atelier):
    """Écart entre le compte 615 et la somme des interventions saisies.

    Voir l'encadré en tête de module : l'écart est normal, et c'est lui
    l'information.
    """
    s = SECTION_RAPPROCHEMENT
    # `cout_maintenance` ne sait pas filtrer par équipement ni par atelier :
    # confronter un Grand Livre entier à une liste filtrée produirait un écart
    # faux. On annonce le refus plutôt que d'afficher un chiffre trompeur.
    if equipement or atelier:
        return [_row(s, libelle="Rapprochement masqué : il porte sur la totalité "
                                "de la période, un filtre Équipement ou Atelier "
                                "le rendrait faux.")]

    maint = cout_maintenance(debut, fin)
    gl = flt(maint["cout"])
    saisi = _somme(lignes, "cout")
    ecart = round(gl - saisi, 2)

    return [
        _row(s, libelle="Entretien au Grand Livre (compte 615)", cout=gl),
        _row(s, libelle="Somme des interventions saisies", cout=saisi),
        _row(s, libelle=_libelle_ecart(ecart),
             cout=ecart, indicator="Orange" if ecart else "Green"),
    ]


def _libelle_ecart(ecart):
    if not ecart:
        return "Écart — aucun, chaque dinar d'entretien est rattaché"
    if ecart > 0:
        return ("Écart — entretien comptabilisé SANS intervention saisie "
                "(facture non rattachée à un équipement)")
    return ("Écart — interventions saisies SANS écriture au 615 "
            "(interventions internes, ou charge imputée à un autre compte)")
