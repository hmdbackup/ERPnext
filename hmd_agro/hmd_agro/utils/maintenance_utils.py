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
    alimentent le Rapport Mensuel et le contrôle de cohérence.

Idempotence (pattern maison) : passer `reference` ; une intervention portant
déjà cette référence est retournée telle quelle, sans doublon.

Run:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.utils.maintenance_utils.enregistrer_intervention \\
        --kwargs "{'asset': 'ACC-ASS-2026-00001', 'description': 'Vidange',
                   'cout': 320, 'type_intervention': 'PREVENTIVE'}"
"""
import frappe
from frappe.utils import flt, get_datetime, getdate, today

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


def interventions_planifiees(jours=30):
    """Tâches de maintenance préventive dues dans les `jours` à venir (ou déjà
    en retard). Alimente le contrôle de cohérence et le pilotage."""
    from frappe.utils import add_days

    return frappe.db.sql("""
        SELECT name, asset_name, task_name, due_date, maintenance_status
        FROM `tabAsset Maintenance Log`
        WHERE maintenance_status IN ('Planned', 'Overdue')
          AND due_date <= %s
        ORDER BY due_date ASC
    """, (add_days(today(), int(jours)),), as_dict=True)
