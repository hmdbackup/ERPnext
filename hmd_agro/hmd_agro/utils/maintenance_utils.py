"""
FIN-S32 (RG-FIN-30/31, RC-FIN-54) — interventions sur les équipements.

On amortissait le matériel sans jamais savoir ce qu'il coûte à entretenir.
Ce module relie les deux :

  • `enregistrer_intervention` — UNE fonction pour saisir une intervention :
      1. un `Asset Repair` ERPNext (le suivi : panne, actions, arrêt, pièces),
      2. l'écriture de charge correspondante — débit 615 « Entretien et
         réparations » sur l'atelier de l'équipement, crédit fournisseur /
         caisse / banque.
    Les deux, parce qu'en v15 un Asset Repair non capitalisé ne produit
    AUCUNE écriture (cf. `asset_repair.before_submit`) : sans le pas 2, le
    coût de maintenance n'existerait nulle part dans le Grand Livre.

  • `planifier_maintenance` — le préventif : `Asset Maintenance` + tâches
    périodiques ; ERPNext génère les `Asset Maintenance Log` à échéance.

  • `cout_maintenance` / `interventions_planifiees` — les lectures qui
    alimentent le Rapport Periodique et le contrôle de cohérence.

  • `cout_horaire` / `cout_utilisation` (FIN-S96) — le coût mécanique : les
    heures saisies dans « Utilisation Equipement » valorisées au coût horaire
    forfaitaire de chaque équipement.

  • SCRUM-11 — la fiche d'intervention saisie À L'ÉCRAN (Asset Repair) :
    hooks `completer_couts_fiche` / `valider_fiche_intervention` /
    `verifier_fiche_avant_validation` (ERR-MNT-09 → 13), état dérivé
    `etat_fiche`, `planifier_intervention` (la fiche « À venir ») et
    `etat_parc` (Prêt / En attente de maintenance / En panne par équipement).

Idempotence (pattern maison) : passer `reference` ; une intervention portant
déjà cette référence est retournée telle quelle, sans doublon.

━━ SCRUM-11 — POURQUOI UN STATUT « Planned » (et pas Pending + date future) ━━
ERPNext `asset_repair.update_status` passe l'équipement « Out of Order » pour
TOUTE fiche `Pending`, quelle que soit sa date. Une intervention planifiée
n'est pas une panne : elle porte donc son propre statut (Property Setter sur
`repair_status`), que le rapport lit comme « À venir » et que `before_submit`
refuse de valider tant qu'elle n'est pas passée à Terminée.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━ FIN-S96 — POURQUOI LE COÛT HORAIRE NE POSTE RIEN (le piège) ━━━━━━━━━━━━━━
Le coût horaire forfaitaire d'un équipement = amortissement + maintenance +
mazout (25 DT/h par défaut, réunion du 05/08/2026, « option 2 »). Or ces trois
charges sont DÉJÀ au Grand Livre : l'amortissement par les écritures 68x
(`Asset Depreciation Schedule`), l'entretien par le compte 615
(`enregistrer_intervention` ci-dessus), le carburant par ses propres achats.
Elles sont donc DÉJÀ dans le coût complet du litre.

Poster une écriture à partir des heures d'utilisation compterait ces charges
UNE SECONDE FOIS. `cout_utilisation` est par construction une vue purement
ANALYTIQUE : elle RÉPARTIT entre ateliers une charge déjà comptabilisée. Les
rapports qui l'affichent doivent la présenter comme une clé de répartition —
jamais l'additionner aux charges du Grand Livre.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Run:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.utils.maintenance_utils.enregistrer_intervention \\
        --kwargs "{'asset': 'ACC-ASS-2026-00001', 'description': 'Vidange',
                   'cout': 320, 'type_intervention': 'PREVENTIVE'}"
"""
import frappe
from frappe.utils import add_days, cint, flt, get_datetime, getdate, today

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.format_fr import fr_date
from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

COMPTE_ENTRETIEN = "615"
COMPTES_REGLEMENT = {
    "FOURNISSEUR": "401",
    "CAISSE": "54",
    "BANQUE": "532",
}
FOURNISSEUR_DEFAUT = "Fournisseur Divers"
ATELIER_DEFAUT = "Frais Généraux"
STATUTS_ASSET_BLOQUANTS = ("Sold", "Scrapped")

# Heures conventionnelles d'une intervention datée au jour (ERPNext exige des
# Datetime) : début de matinée pour la panne, midi pour la fin des travaux.
HEURE_DEBUT_INTERVENTION = "08:00:00"
HEURE_FIN_INTERVENTION = "12:00:00"

# ── SCRUM-11 — statuts ERPNext de la fiche et états dérivés ──────────────────
FICHE_INTERVENTION = "Asset Repair"
STATUT_PLANIFIEE = "Planned"       # ajouté par Property Setter (voir en-tête)
STATUT_EN_ATTENTE = "Pending"      # panne déclarée : ERPNext passe l'équipement Out of Order
STATUT_TERMINEE = "Completed"
STATUT_ANNULEE = "Cancelled"

ETAT_A_VENIR = "A_VENIR"
ETAT_EN_ATTENTE = "EN_ATTENTE"
ETAT_TERMINEE = "TERMINEE"
ETAT_ANNULEE = "ANNULEE"
ETATS_PAR_STATUT = {
    STATUT_PLANIFIEE: ETAT_A_VENIR,
    STATUT_EN_ATTENTE: ETAT_EN_ATTENTE,
    STATUT_TERMINEE: ETAT_TERMINEE,
    STATUT_ANNULEE: ETAT_ANNULEE,
}

# États du parc, par équipement (`etat_parc`).
PARC_PRET = "PRET"
PARC_EN_ATTENTE = "EN_ATTENTE_MAINTENANCE"
PARC_EN_PANNE = "EN_PANNE"

# Provenance d'une échéance (`interventions_planifiees`).
ECHEANCE_LOG = "Asset Maintenance Log"
ECHEANCE_FICHE = FICHE_INTERVENTION

TYPE_PLANIFIEE_DEFAUT = "PREVENTIVE"
CHAMPS_COUT_FICHE = ("cout_pieces", "cout_main_oeuvre", "repair_cost")


def _acc(number):
    return frappe.db.get_value("Account", {"company": COMPANY, "account_number": number})


def _marker(repair):
    return f"MAINT_{repair}"


def _horodatage(date, heure):
    """Datetime of `date` at the conventional hour `heure` (HH:MM:SS)."""
    return get_datetime(f"{getdate(date)} {heure}")


def _filtres_sql(filtres):
    """SQL fragment + params for the `(condition, valeur)` pairs whose value is set.

    `condition` carries column and operator (`"rep.asset ="`, `"log.due_date <="`);
    the placeholder is appended. Empty values are skipped, so callers pass
    every optional filter unconditionally.
    """
    actifs = [(condition, valeur) for condition, valeur in filtres if valeur]
    return ("".join(f" AND {condition} %s" for condition, _ in actifs),
            [valeur for _, valeur in actifs])


def _cost_center(atelier=None, asset=None):
    """Atelier explicite > atelier de l'équipement > Frais Généraux."""
    abbr = frappe.db.get_value("Company", COMPANY, "abbr")
    for candidat in (atelier, f"{atelier} - {abbr}" if atelier else None,
                     frappe.db.get_value("Asset", asset, "cost_center") if asset else None,
                     f"{ATELIER_DEFAUT} - {abbr}"):
        if candidat and frappe.db.exists("Cost Center", candidat):
            return candidat
    frappe.throw("ERR-MNT-03 : aucun Cost Center exploitable (RG-FIN-40) — "
                 "lancer le socle comptable.")


def existing_intervention(reference):
    """Asset Repair actif (docstatus < 2) portant déjà cette référence HMD."""
    if not reference:
        return None
    return frappe.db.get_value(
        "Asset Repair",
        {"reference_hmd": reference, "docstatus": ["<", 2]},
        "name",
    )


# ─── Curatif : l'intervention et sa charge ───────────────────────────────────

@frappe.whitelist()
def enregistrer_intervention(asset, description, cout=0, date=None, atelier=None,
                             type_intervention="CURATIVE", personnel=None,
                             actions=None, arret=None, mode_reglement="FOURNISSEUR",
                             fournisseur=None, reference=None, submit=True):
    """Enregistre une intervention sur un équipement et poste sa charge.

    Args:
        asset:             nom de l'Asset ERPNext
        description:       nature de la panne / de l'intervention
        cout:              coût en TND (0 = intervention interne, aucun GL)
        date:              date de l'intervention (défaut : aujourd'hui)
        atelier:           Cost Center d'imputation (défaut : celui de l'Asset)
        type_intervention: CURATIVE | PREVENTIVE | REVISION | CONTROLE
        personnel:         intervenant (Link Personnel)
        arret:             durée d'immobilisation, texte libre (ex. « 4 h »)
        mode_reglement:    FOURNISSEUR | CAISSE | BANQUE
        reference:         marqueur d'idempotence (imports, seeds)
    Returns: {"asset_repair": …, "journal_entry": …, "cout": …}
    """
    cout = flt(cout)
    date = getdate(date or today())

    deja = existing_intervention(reference)
    if deja:
        print(f"  [skip]   Intervention {reference} déjà enregistrée ({deja})")
        return {"asset_repair": deja,
                "journal_entry": _journal_existant(deja),
                "cout": cout}

    if not frappe.db.exists("Asset", asset):
        frappe.throw(f"ERR-MNT-01 : équipement « {asset} » introuvable.")
    statut = frappe.db.get_value("Asset", asset, "status")
    if statut in STATUTS_ASSET_BLOQUANTS:
        frappe.throw(
            f"ERR-MNT-02 : l'équipement « {asset} » est {statut} — "
            "aucune intervention ne peut y être rattachée."
        )

    repair = frappe.get_doc({
        "doctype": "Asset Repair",
        "company": COMPANY,
        "asset": asset,
        "failure_date": _horodatage(date, HEURE_DEBUT_INTERVENTION),
        "completion_date": _horodatage(date, HEURE_FIN_INTERVENTION),
        "repair_status": "Completed",
        "description": description,
        "actions_performed": actions or description,
        "downtime": arret,
        "repair_cost": cout,
        "capitalize_repair_cost": 0,
        "cost_center": _cost_center(atelier, asset),
        "type_intervention": type_intervention,
        "personnel": personnel,
        "reference_hmd": reference,
    })
    repair.insert(ignore_permissions=True)
    if submit:
        repair.submit()

    je = None
    if cout > 0:
        je = _poster_charge(repair.name, cout, date, _cost_center(atelier, asset),
                            mode_reglement, fournisseur, description, submit)
    print(f"  [create] Intervention {repair.name} sur {asset} "
          f"({type_intervention}, {cout} TND)"
          + (f" — charge {je}" if je else " — sans charge (interne)"))
    return {"asset_repair": repair.name, "journal_entry": je, "cout": cout}


def _journal_existant(repair):
    return frappe.db.get_value(
        "Journal Entry",
        {"user_remark": ["like", f"%{_marker(repair)}%"], "docstatus": ["<", 2]},
        "name",
    )


def _poster_charge(repair, cout, date, cost_center, mode_reglement,
                   fournisseur, description, submit=True):
    """Débit 615 (atelier) / crédit fournisseur·caisse·banque. Idempotent par
    marqueur `MAINT_<repair>` dans user_remark."""
    existant = _journal_existant(repair)
    if existant:
        return existant

    compte_charge = _acc(COMPTE_ENTRETIEN)
    numero_contrepartie = COMPTES_REGLEMENT.get(mode_reglement)
    if not numero_contrepartie:
        frappe.throw(
            f"ERR-MNT-04 : mode de règlement « {mode_reglement} » inconnu "
            f"(attendu : {', '.join(COMPTES_REGLEMENT)})."
        )
    compte_contrepartie = _acc(numero_contrepartie)
    if not (compte_charge and compte_contrepartie):
        frappe.throw(
            f"ERR-MNT-05 : comptes {COMPTE_ENTRETIEN}/{numero_contrepartie} "
            "introuvables — lancer le socle comptable."
        )

    ligne_credit = {
        "account": compte_contrepartie,
        "credit_in_account_currency": cout,
    }
    if mode_reglement == "FOURNISSEUR":
        tiers = fournisseur or FOURNISSEUR_DEFAUT
        if not frappe.db.exists("Supplier", tiers):
            frappe.throw(
                f"ERR-MNT-06 : fournisseur « {tiers} » introuvable — le créer "
                "ou régler en CAISSE / BANQUE."
            )
        ligne_credit.update({"party_type": "Supplier", "party": tiers})

    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "company": COMPANY,
        "posting_date": date,
        "accounts": [
            {"account": compte_charge, "debit_in_account_currency": cout,
             "cost_center": cost_center},
            ligne_credit,
        ],
        "user_remark": f"{_marker(repair)} — {description[:120]}",
    })
    # Automatic entry: exempt from strict FG split mode (ERR-FIN-17).
    je.flags.ignore_repartition_fg = True
    je.insert(ignore_permissions=True)
    if submit:
        je.submit()
    return je.name


def annuler_intervention(repair):
    """Annulation symétrique (CF-FIN-31) : l'écriture de charge est annulée
    avec l'intervention — sinon le 615 garderait un coût sans justificatif."""
    je = _journal_existant(repair)
    if je and frappe.db.get_value("Journal Entry", je, "docstatus") == 1:
        doc = frappe.get_doc("Journal Entry", je)
        doc.flags.ignore_permissions = True
        doc.cancel()
    doc = frappe.get_doc("Asset Repair", repair)
    if doc.docstatus == 1:
        doc.flags.ignore_permissions = True
        doc.cancel()
    return je


# ─── SCRUM-11 : the intervention sheet typed on screen ───────────────────────
# Hooks declared in hooks.py (`doc_events["Asset Repair"]`). Frappe order:
# before_validate (here) → ERPNext validate (update_status, total_repair_cost)
# → validate (here) → ERPNext before_submit (refuses Pending) → before_submit (here).

def completer_couts_fiche(doc, method=None):
    """before_validate — `repair_cost` = pièces + main-d'œuvre when no invoice drives it.

    ERPNext fills `repair_cost` from `purchase_invoice` (client side) and then
    derives `total_repair_cost` from it in its own `validate`, which runs after
    this hook: setting `repair_cost` here is enough for the total to follow.
    A sheet without parts nor labour keeps whatever `repair_cost` it carries
    (`enregistrer_intervention` writes it directly).
    """
    if doc.purchase_invoice:
        return
    pieces, main_oeuvre = doc.get("cout_pieces"), doc.get("cout_main_oeuvre")
    # Also when one of them just went back to 0 — otherwise the old cost stays.
    if not (pieces or main_oeuvre or _couts_modifies(doc)):
        return
    doc.repair_cost = flt(pieces) + flt(main_oeuvre)


def _couts_modifies(doc):
    """True when `cout_pieces` / `cout_main_oeuvre` differ numerically from the
    saved sheet (None and 0 are the same amount — `has_value_changed` would
    see a change on every submit of a sheet posted without parts / labour)."""
    avant = doc.get_doc_before_save() if not doc.is_new() else None
    if not avant:
        return False
    return any(flt(doc.get(champ)) != flt(avant.get(champ))
               for champ in ("cout_pieces", "cout_main_oeuvre"))


def valider_fiche_intervention(doc, method=None):
    """validate — ERR-MNT-09 → 12, on every save of a sheet."""
    _verifier_intervenant_unique(doc)
    _verifier_couts_positifs(doc)
    if doc.repair_status == STATUT_PLANIFIEE:
        # A sheet already Planned in the past may still be re-saved (e.g. to
        # move it to Completed the day it is done): the date check only fires
        # when the sheet is new, its date changes or it becomes Planned.
        if (doc.is_new() or doc.has_value_changed("failure_date")
                or doc.has_value_changed("repair_status")):
            _verifier_date_planifiee(doc.failure_date, strict=False)
        _verifier_fiche_planifiee_vierge(doc)


def verifier_fiche_avant_validation(doc, method=None):
    """before_submit — ERR-MNT-13. ERPNext only refuses `Pending` here."""
    if doc.repair_status == STATUT_PLANIFIEE:
        frappe.throw(
            "ERR-MNT-13 : une fiche « À venir » ne se valide pas — passer d'abord "
            "son statut à Terminée (Completed), une fois l'intervention faite."
        )


def _verifier_intervenant_unique(doc):
    personnel, prestataire = doc.get("personnel"), doc.get("prestataire")
    if personnel and prestataire:
        frappe.throw(
            "ERR-MNT-09 : une intervention a UN intervenant — salarié "
            f"({personnel}) OU prestataire ({prestataire}), pas les deux."
        )


def _verifier_couts_positifs(doc):
    for champ in CHAMPS_COUT_FICHE:
        if flt(doc.get(champ)) < 0:
            libelle = frappe.get_meta(FICHE_INTERVENTION).get_label(champ)
            frappe.throw(
                f"ERR-MNT-10 : « {libelle} » ne peut pas être négatif "
                f"(saisi : {doc.get(champ)})."
            )


def _verifier_date_planifiee(date_prevue, strict=True):
    """A planned intervention lies in the future (ERR-MNT-11) — strictly
    after today when `strict` (`planifier_intervention`), today accepted
    otherwise (a sheet saved the day of the intervention)."""
    aujourdhui = getdate(today())
    depassee = (getdate(date_prevue) <= aujourdhui if strict
                else getdate(date_prevue) < aujourdhui) if date_prevue else True
    if depassee:
        frappe.throw(
            "ERR-MNT-11 : une intervention planifiée se situe dans le futur — "
            f"date prévue {fr_date(date_prevue)}, aujourd'hui "
            f"{fr_date(aujourdhui)}. Reporter la date, ou passer le statut à "
            "En attente / Terminée si l'intervention a lieu."
        )


def _verifier_fiche_planifiee_vierge(doc):
    """A planned sheet carries neither completion date nor any cost (ERR-MNT-12)."""
    renseigne = doc.completion_date or doc.purchase_invoice or any(
        flt(doc.get(champ)) for champ in CHAMPS_COUT_FICHE)
    if renseigne:
        frappe.throw(
            "ERR-MNT-12 : une fiche « À venir » ne porte ni date de fin, ni coût, "
            "ni facture — ils se saisissent une fois l'intervention faite "
            "(statut En attente ou Terminée)."
        )


def etat_fiche(repair):
    """Derived state of a sheet (doc or dict): A_VENIR / EN_ATTENTE / TERMINEE / ANNULEE.

    A cancelled document (docstatus 2) is ANNULEE whatever its status; an
    unknown status reads as EN_ATTENTE, ERPNext's own default (`Pending`).
    """
    if cint(repair.get("docstatus")) == 2:
        return ETAT_ANNULEE
    return ETATS_PAR_STATUT.get(repair.get("repair_status"), ETAT_EN_ATTENTE)


@frappe.whitelist()
def planifier_intervention(source, date_prevue, description=None):
    """Create the next sheet — a draft `Planned` — from a completed one.

    Copies equipment, type (PREVENTIVE if the source has none), cost center and
    intervener; completion date and costs stay empty (ERR-MNT-12) until the
    intervention is done. `date_prevue` must be after today (ERR-MNT-11).
    Returns the new sheet's name. Duplicate / delete are native Frappe actions.
    """
    frappe.has_permission(FICHE_INTERVENTION, "create", throw=True)
    origine = frappe.get_doc(FICHE_INTERVENTION, source)
    _verifier_date_planifiee(date_prevue)

    fiche = frappe.get_doc({
        "doctype": FICHE_INTERVENTION,
        "company": origine.company,
        "asset": origine.asset,
        "failure_date": _horodatage(date_prevue, HEURE_DEBUT_INTERVENTION),
        "repair_status": STATUT_PLANIFIEE,
        "type_intervention": origine.type_intervention or TYPE_PLANIFIEE_DEFAUT,
        "cost_center": origine.cost_center,
        "personnel": origine.personnel,
        "prestataire": origine.prestataire,
        "description": description
        or f"Prochaine : {origine.description or origine.asset_name}",
    })
    fiche.insert()
    return fiche.name


# ─── Préventif : le plan de maintenance ──────────────────────────────────────

@frappe.whitelist()
def planifier_maintenance(asset, taches, equipe=None, assigne=None):
    """Crée (ou complète) le plan de maintenance préventive d'un équipement.

    Args:
        asset:  nom de l'Asset
        taches: [{"tache": "Vidange moteur", "periodicite": "Half-yearly",
                  "date_debut": "2026-08-01", "type": "Preventive Maintenance"}]
                périodicités ERPNext : Daily, Weekly, Monthly, Quarterly,
                Half-yearly, Yearly, 2 Yearly, 3 Yearly.
        equipe: Asset Maintenance Team (défaut : « Maintenance HMD »)
    Returns: le nom du document Asset Maintenance (= le nom de l'Asset).
    """
    from hmd_agro.hmd_agro.setup.finance.maintenance import (
        EQUIPE_MAINTENANCE, utilisateur_assignable,
    )

    if isinstance(taches, str):
        import json
        taches = json.loads(taches)
    if not frappe.db.exists("Asset", asset):
        frappe.throw(f"ERR-MNT-01 : équipement « {asset} » introuvable.")

    equipe = equipe or EQUIPE_MAINTENANCE
    if not frappe.db.exists("Asset Maintenance Team", equipe):
        frappe.throw(
            f"ERR-MNT-07 : équipe de maintenance « {equipe} » absente — "
            "lancer setup.finance.maintenance.setup_maintenance."
        )
    # ERPNext assigne chaque tâche à un utilisateur (ToDo) : il faut un compte
    # dont l'email est le nom d'utilisateur, sinon l'assignation casse.
    assigne = utilisateur_assignable(
        assigne or frappe.db.get_value("Asset Maintenance Team", equipe,
                                       "maintenance_manager"))
    if not assigne:
        frappe.throw(
            "ERR-MNT-08 : aucun compte utilisateur assignable pour les tâches "
            "de maintenance. Créer un utilisateur nominatif (son email doit "
            "être son identifiant) et le rattacher au registre Personnel."
        )

    existant = frappe.db.exists("Asset Maintenance", {"asset_name": asset})
    doc = (frappe.get_doc("Asset Maintenance", existant) if existant
           else frappe.get_doc({"doctype": "Asset Maintenance", "asset_name": asset,
                                "company": COMPANY, "maintenance_team": equipe}))
    connues = {t.maintenance_task for t in doc.get("asset_maintenance_tasks", [])}
    ajoutees = 0
    for tache in taches:
        libelle = tache.get("tache") or tache.get("maintenance_task")
        if not libelle or libelle in connues:
            continue
        debut = getdate(tache.get("date_debut") or today())
        periodicite = tache.get("periodicite") or "Yearly"
        doc.append("asset_maintenance_tasks", {
            "maintenance_task": libelle,
            "maintenance_type": tache.get("type") or "Preventive Maintenance",
            "maintenance_status": "Planned",
            "start_date": debut,
            "periodicity": periodicite,
            # ERPNext ne calcule la prochaine échéance QUE côté client
            # (asset_maintenance.js) : sans ce calcul, les Asset Maintenance Log
            # naissent sans due_date et aucune échéance ne remonte jamais.
            "next_due_date": _prochaine_echeance(periodicite, debut),
            "assign_to": tache.get("assigne") or assigne,
        })
        ajoutees += 1
    if not ajoutees and existant:
        print(f"  [skip]   Plan de maintenance {asset} déjà à jour")
        return existant

    doc.save(ignore_permissions=True)
    frappe.db.set_value("Asset", asset, "maintenance_required", 1,
                        update_modified=False)
    print(f"  [create] Plan de maintenance {asset} : +{ajoutees} tâche(s)")
    return doc.name


def _prochaine_echeance(periodicite, date_debut):
    """Prochaine échéance d'une tâche périodique (délègue au calcul ERPNext)."""
    from erpnext.assets.doctype.asset_maintenance.asset_maintenance import (
        calculate_next_due_date,
    )

    return calculate_next_due_date(periodicity=periodicite, start_date=str(date_debut))


# ─── Lectures ────────────────────────────────────────────────────────────────

def cout_horaire(asset_name):
    """Coût horaire forfaitaire d'un équipement en DT/h (TASK B3, FIN-S96).

    Forfait « option 2 » de la réunion du 05/08/2026 : amortissement +
    maintenance + mazout dans un seul taux.
    Résolution : `Asset.cout_horaire` s'il est renseigné, sinon le défaut
    `equipement_cout_horaire_defaut` de HMD Configuration (25 DT/h).
    Consommé par `Utilisation Equipement.validate` (qui fige le taux sur la
    ligne) et par `cout_utilisation` ci-dessous.
    """
    valeur = flt(frappe.db.get_value("Asset", asset_name, "cout_horaire"))
    if valeur:
        return valeur
    return flt(get_config("equipement_cout_horaire_defaut", default=25))


def cout_utilisation(date_debut, date_fin):
    """Coût mécanique de la période, réparti par atelier et par équipement.

    Lit les saisies « Utilisation Equipement » (heures réellement travaillées)
    valorisées au taux figé sur chaque ligne. C'est LA lecture que les rapports
    appellent — ils n'ont pas à connaître le DocType.

    RAPPEL (cf. l'encadré en tête de module) : aucune écriture n'est produite
    et ce montant NE S'AJOUTE PAS aux charges du Grand Livre — amortissement et
    entretien y figurent déjà. C'est une clé de répartition entre ateliers.

    Retourne {"total": DT, "heures": h,
              "par_atelier": {cost_center: DT},
              "par_equipement": {asset: {"heures": h, "cout": DT}}}
    Une période sans saisie retourne des zéros — même posture honnête que
    `cout_maintenance` / `gl_sums`.
    """
    vide = {"total": 0.0, "heures": 0.0, "par_atelier": {}, "par_equipement": {}}
    # The DocType may not exist yet on a site migrated from an older version.
    if not frappe.db.table_exists("Utilisation Equipement"):
        return vide

    lignes = frappe.db.sql("""
        SELECT equipement, atelier,
               COALESCE(SUM(heures), 0) AS heures,
               COALESCE(SUM(cout_total), 0) AS cout
        FROM `tabUtilisation Equipement`
        WHERE docstatus < 2 AND `date` BETWEEN %s AND %s
        GROUP BY equipement, atelier
    """, (getdate(date_debut), getdate(date_fin)), as_dict=True)
    if not lignes:
        return vide

    par_atelier = {}
    par_equipement = {}
    for ligne in lignes:
        cout = float(ligne.cout or 0)
        heures = float(ligne.heures or 0)
        par_atelier[ligne.atelier] = round(par_atelier.get(ligne.atelier, 0) + cout, 3)
        agg = par_equipement.setdefault(ligne.equipement, {"heures": 0.0, "cout": 0.0})
        agg["heures"] = round(agg["heures"] + heures, 2)
        agg["cout"] = round(agg["cout"] + cout, 3)

    return {
        "total": round(sum(float(ligne.cout or 0) for ligne in lignes), 3),
        "heures": round(sum(float(ligne.heures or 0) for ligne in lignes), 2),
        "par_atelier": par_atelier,
        "par_equipement": par_equipement,
    }


def cout_maintenance(date_debut, date_fin):
    """Coût d'entretien de la période, lu au Grand Livre (compte 615) et
    croisé avec les interventions saisies.

    Retourne {"cout": DT, "interventions": n, "equipements": n,
              "par_equipement": {asset: DT}}
    Une période sans écriture retourne 0 — même posture que gl_sums.
    """
    cout = float(frappe.db.sql("""
        SELECT COALESCE(SUM(gle.debit - gle.credit), 0)
        FROM `tabGL Entry` gle
        JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.company = %s AND gle.is_cancelled = 0
          AND gle.posting_date BETWEEN %s AND %s
          AND acc.account_number = %s
    """, (COMPANY, date_debut, date_fin, COMPTE_ENTRETIEN))[0][0] or 0)

    lignes = frappe.db.sql("""
        SELECT asset, COALESCE(SUM(total_repair_cost), 0) AS cout, COUNT(*) AS n
        FROM `tabAsset Repair`
        WHERE docstatus = 1 AND company = %s
          AND DATE(COALESCE(completion_date, failure_date)) BETWEEN %s AND %s
        GROUP BY asset
    """, (COMPANY, date_debut, date_fin), as_dict=True)

    return {
        "cout": round(cout, 2),
        "interventions": sum(int(r.n) for r in lignes),
        "equipements": len(lignes),
        "par_equipement": {r.asset: round(float(r.cout), 2) for r in lignes},
    }


def interventions_realisees(date_debut, date_fin, equipement=None, atelier=None):
    """Line-by-line detail of the interventions of the period.

    `cout_maintenance` above AGGREGATES (one amount, counters); this one
    DETAILS. Both live here for the same reason: the reports consume this
    module and do not need to know `Asset Repair` — same stance as
    `cout_utilisation` towards « Utilisation Equipement ».

    The amount read is `total_repair_cost` (repair cost + consumed parts), the
    very one `cout_maintenance` totals: the two readings cannot diverge.

    Args:
        equipement: restricts to one Asset (optional)
        atelier:    restricts to one Cost Center (optional)

    Each row also carries the SCRUM-11 detail: `cout_pieces`,
    `cout_main_oeuvre`, the employee (`personnel`, `personnel_nom`) or the
    contractor (`prestataire`, `prestataire_nom` = company name).

    Returns a list of dicts, most recent first, decreasing cost on the same
    date. A period without intervention returns [] — same honest stance as
    `cout_maintenance` / `cout_utilisation`.
    """
    conditions, filtres = _filtres_sql([
        ("rep.asset =", equipement), ("rep.cost_center =", atelier),
    ])
    return frappe.db.sql(f"""
        SELECT rep.name, rep.asset, ast.asset_name,
               DATE(COALESCE(rep.completion_date, rep.failure_date)) AS date,
               rep.description, rep.type_intervention, rep.cost_center AS atelier,
               COALESCE(rep.total_repair_cost, 0) AS cout,
               COALESCE(rep.cout_pieces, 0) AS cout_pieces,
               COALESCE(rep.cout_main_oeuvre, 0) AS cout_main_oeuvre,
               rep.personnel, pers.nom_complet AS personnel_nom,
               rep.prestataire, four.supplier_name AS prestataire_nom,
               rep.downtime AS arret
        FROM `tabAsset Repair` rep
        LEFT JOIN `tabAsset` ast ON ast.name = rep.asset
        LEFT JOIN `tabPersonnel` pers ON pers.name = rep.personnel
        LEFT JOIN `tabSupplier` four ON four.name = rep.prestataire
        WHERE rep.docstatus = 1 AND rep.company = %s
          AND DATE(COALESCE(rep.completion_date, rep.failure_date))
              BETWEEN %s AND %s
          {conditions}
        ORDER BY date DESC, cout DESC
    """, [COMPANY, getdate(date_debut), getdate(date_fin), *filtres], as_dict=True)


def interventions_planifiees(jours=30, equipement=None, atelier=None):
    """Deadlines due within the next `jours` days (or already overdue): the
    ERPNext preventive maintenance tasks AND, since SCRUM-11, the « À venir »
    sheets (Asset Repair `Planned`). Feeds the consistency check and the
    steering — an overdue planned sheet is an overdue deadline.

    `equipement` / `atelier` narrow the scope, so that a filtered report can
    never show a preventive block contradicting its own filter. Both sources
    share one row shape, described in `_echeances_ouvertes`.
    """
    return _echeances_ouvertes(equipement, atelier,
                               limite=add_days(today(), cint(jours)))


def _echeances_ouvertes(equipement=None, atelier=None, limite=None):
    """Every open deadline, soonest first; `limite` (date) caps `due_date`.

    Uniform row shape whatever the source:
        name, source (ECHEANCE_LOG | ECHEANCE_FICHE), asset_name (Link Asset —
        ERPNext trap: in Asset Maintenance Log it is a Link, not a label),
        designation, atelier (both read on the Asset), task_name, due_date,
        maintenance_status, type_intervention (sheets only).
    """
    lignes = (_echeances_logs(equipement, atelier, limite)
              + _echeances_fiches(equipement, atelier, limite))
    return sorted(lignes, key=lambda ligne: getdate(ligne.due_date))


def _echeances_logs(equipement, atelier, limite):
    conditions, filtres = _filtres_sql([
        ("log.due_date <=", limite), ("log.asset_name =", equipement),
        ("ast.cost_center =", atelier),
    ])
    return frappe.db.sql(f"""
        SELECT log.name, %s AS source, log.asset_name,
               ast.asset_name AS designation, ast.cost_center AS atelier,
               log.task_name, log.due_date, log.maintenance_status,
               NULL AS type_intervention
        FROM `tabAsset Maintenance Log` log
        LEFT JOIN `tabAsset` ast ON ast.name = log.asset_name
        WHERE log.maintenance_status IN ('Planned', 'Overdue')
          AND log.due_date IS NOT NULL
          {conditions}
        ORDER BY log.due_date ASC
    """, [ECHEANCE_LOG, *filtres], as_dict=True)


def _echeances_fiches(equipement, atelier, limite):
    conditions, filtres = _filtres_sql([
        ("DATE(rep.failure_date) <=", limite), ("rep.asset =", equipement),
        ("ast.cost_center =", atelier),
    ])
    return frappe.db.sql(f"""
        SELECT rep.name, %s AS source, rep.asset AS asset_name,
               ast.asset_name AS designation, ast.cost_center AS atelier,
               rep.description AS task_name, DATE(rep.failure_date) AS due_date,
               rep.repair_status AS maintenance_status, rep.type_intervention
        FROM `tabAsset Repair` rep
        LEFT JOIN `tabAsset` ast ON ast.name = rep.asset
        WHERE rep.docstatus = 0 AND rep.repair_status = %s AND rep.company = %s
          {conditions}
        ORDER BY rep.failure_date ASC
    """, [ECHEANCE_FICHE, STATUT_PLANIFIEE, COMPANY, *filtres], as_dict=True)


# ─── SCRUM-11 : état du parc ─────────────────────────────────────────────────

def etat_parc(date_debut, date_fin, horizon_jours, equipement=None, atelier=None):
    """Fleet status as of today, one entry per equipment (« Parc — état du matériel »).

    Args:
        date_debut, date_fin: period over which usage hours are summed
                              (`cout_utilisation`) — the state itself is « today »
        horizon_jours:        a deadline within this many days puts the equipment
                              EN_ATTENTE_MAINTENANCE (same horizon as the
                              preventive block of the report)
        equipement / atelier: optional restriction (Asset / Cost Center)

    Returns, sorted by designation:
        [{"asset", "designation", "atelier", "etat", "derniere", "prochaine", "heures"}]
        etat:      PARC_PRET | PARC_EN_ATTENTE | PARC_EN_PANNE
        derniere:  {"date", "description"} — last completed, submitted sheet — or None
        prochaine: {"date", "libelle", "source", "en_retard"} — nearest open
                   deadline (planned sheet or preventive log) — or None
    EN_PANNE is decided by an open `Pending` sheet: the sheet is the source of
    truth, not a button. Animals immobilised as assets (`id_animal`) and
    disposed assets (Sold / Scrapped) are not part of the fleet.
    """
    equipements = _equipements_parc(equipement, atelier)
    if not equipements:
        return []
    en_panne = _equipements_en_panne()
    dernieres = _dernieres_interventions()
    prochaines = _prochaines_echeances(equipement, atelier)
    heures = cout_utilisation(date_debut, date_fin)["par_equipement"]
    limite = getdate(add_days(today(), cint(horizon_jours)))
    return [
        _entree_parc(eq, eq.name in en_panne, dernieres.get(eq.name),
                     prochaines.get(eq.name),
                     heures.get(eq.name, {}).get("heures", 0.0), limite)
        for eq in equipements
    ]


def _equipements_parc(equipement, atelier):
    """Submitted, non-animal, non-disposed assets — the machines of the fleet."""
    conditions, filtres = _filtres_sql([
        ("ast.name =", equipement), ("ast.cost_center =", atelier),
    ])
    return frappe.db.sql(f"""
        SELECT ast.name, ast.asset_name AS designation, ast.cost_center AS atelier
        FROM `tabAsset` ast
        WHERE ast.docstatus = 1 AND ast.company = %s
          AND COALESCE(ast.id_animal, '') = ''
          AND ast.status NOT IN %s
          {conditions}
        ORDER BY ast.asset_name, ast.name
    """, [COMPANY, STATUTS_ASSET_BLOQUANTS, *filtres], as_dict=True)


def _equipements_en_panne():
    """Assets carrying an open (draft) `Pending` sheet."""
    return set(frappe.get_all(
        FICHE_INTERVENTION,
        filters={"docstatus": 0, "repair_status": STATUT_EN_ATTENTE, "company": COMPANY},
        pluck="asset",
    ))


def _dernieres_interventions():
    """{asset: {date, description}} of the most recent completed, submitted sheet."""
    lignes = frappe.db.sql("""
        SELECT rep.asset,
               DATE(COALESCE(rep.completion_date, rep.failure_date)) AS date,
               rep.description
        FROM `tabAsset Repair` rep
        WHERE rep.docstatus = 1 AND rep.repair_status = %s AND rep.company = %s
        ORDER BY COALESCE(rep.completion_date, rep.failure_date) DESC
    """, (STATUT_TERMINEE, COMPANY), as_dict=True)
    dernieres = {}
    for ligne in lignes:
        dernieres.setdefault(ligne.asset, ligne)
    return dernieres


def _prochaines_echeances(equipement, atelier):
    """{asset: échéance} — the soonest open deadline of each equipment."""
    prochaines = {}
    for echeance in _echeances_ouvertes(equipement, atelier):
        prochaines.setdefault(echeance.asset_name, echeance)
    return prochaines


def _entree_parc(equipement, en_panne, derniere, prochaine, heures, limite):
    aujourdhui = getdate(today())
    return {
        "asset": equipement.name,
        "designation": equipement.designation,
        "atelier": equipement.atelier,
        "etat": _etat_equipement(en_panne, prochaine, limite),
        "derniere": ({"date": derniere.date, "description": derniere.description}
                     if derniere else None),
        "prochaine": ({"date": getdate(prochaine.due_date),
                       "libelle": prochaine.task_name,
                       "source": prochaine.source,
                       "en_retard": getdate(prochaine.due_date) < aujourdhui}
                      if prochaine else None),
        "heures": flt(heures),
    }


def _etat_equipement(en_panne, prochaine, limite):
    if en_panne:
        return PARC_EN_PANNE
    if prochaine and getdate(prochaine.due_date) <= limite:
        return PARC_EN_ATTENTE
    return PARC_PRET
