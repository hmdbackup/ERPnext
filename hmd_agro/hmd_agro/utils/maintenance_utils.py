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

Idempotence (pattern maison) : passer `reference` ; une intervention portant
déjà cette référence est retournée telle quelle, sans doublon.

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
from frappe.utils import flt, get_datetime, getdate, today

from hmd_agro.hmd_agro.utils.config import get_config
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


def _acc(number):
    return frappe.db.get_value("Account", {"company": COMPANY, "account_number": number})


def _marker(repair):
    return f"MAINT_{repair}"


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
        "failure_date": get_datetime(f"{date} 08:00:00"),
        "completion_date": get_datetime(f"{date} 12:00:00"),
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
    """Détail ligne à ligne des interventions de la période.

    `cout_maintenance` ci-dessus AGRÈGE (un montant, des compteurs) ; celle-ci
    DÉTAILLE. Les deux vivent ici pour la même raison : les rapports consomment
    ce module et n'ont pas à connaître `Asset Repair` — même posture que
    `cout_utilisation` vis-à-vis de « Utilisation Equipement ».

    Le montant lu est `total_repair_cost` (coût de réparation + pièces
    consommées), celui-là même que `cout_maintenance` totalise : les deux
    lectures ne peuvent donc pas diverger l'une de l'autre.

    Args:
        equipement: restreint à un Asset (optionnel)
        atelier:    restreint à un Cost Center (optionnel)

    Retourne une liste de dicts, les plus récentes d'abord, à coût décroissant
    à date égale. Une période sans intervention retourne [] — même posture
    honnête que `cout_maintenance` / `cout_utilisation`.
    """
    conditions = ""
    params = [COMPANY, getdate(date_debut), getdate(date_fin)]
    if equipement:
        conditions += " AND rep.asset = %s"
        params.append(equipement)
    if atelier:
        conditions += " AND rep.cost_center = %s"
        params.append(atelier)

    return frappe.db.sql(f"""
        SELECT rep.name, rep.asset, ast.asset_name,
               DATE(COALESCE(rep.completion_date, rep.failure_date)) AS date,
               rep.description, rep.type_intervention, rep.cost_center AS atelier,
               COALESCE(rep.total_repair_cost, 0) AS cout,
               rep.personnel, rep.downtime AS arret
        FROM `tabAsset Repair` rep
        LEFT JOIN `tabAsset` ast ON ast.name = rep.asset
        WHERE rep.docstatus = 1 AND rep.company = %s
          AND DATE(COALESCE(rep.completion_date, rep.failure_date))
              BETWEEN %s AND %s
          {conditions}
        ORDER BY date DESC, cout DESC
    """, params, as_dict=True)


def interventions_planifiees(jours=30, equipement=None, atelier=None):
    """Tâches de maintenance préventive dues dans les `jours` à venir (ou déjà
    en retard). Alimente le contrôle de cohérence et le pilotage.

    `equipement` / `atelier` restreignent le périmètre, pour qu'un rapport
    filtré ne puisse pas afficher un bloc préventif qui contredit son propre
    filtre. Piège ERPNext : dans « Asset Maintenance Log », `asset_name` est un
    Link vers Asset (pas un libellé) ; l'atelier, lui, n'existe que sur l'Asset,
    d'où la jointure.
    """
    from frappe.utils import add_days

    conditions = ""
    params = [add_days(today(), int(jours))]
    if equipement:
        conditions += " AND log.asset_name = %s"
        params.append(equipement)
    if atelier:
        conditions += " AND ast.cost_center = %s"
        params.append(atelier)

    return frappe.db.sql(f"""
        SELECT log.name, log.asset_name, log.task_name, log.due_date,
               log.maintenance_status
        FROM `tabAsset Maintenance Log` log
        LEFT JOIN `tabAsset` ast ON ast.name = log.asset_name
        WHERE log.maintenance_status IN ('Planned', 'Overdue')
          AND log.due_date <= %s
          {conditions}
        ORDER BY log.due_date ASC
    """, params, as_dict=True)
