"""A2 — RH : nouveaux défauts et amorçage de l'historique de salaire.

(a) Chaque fiche Personnel sans historique reçoit sa ligne initiale, datée
    de l'embauche (ou d'aujourd'hui si la date manque), avec les valeurs
    vivantes actuelles : le journal immuable démarre de l'état connu et
    `masse_salariale` peut lire l'historique dès le premier mois. Le taux de
    charges patronales y est FIGÉ résolu : surcharge salarié si renseignée,
    sinon le taux global en vigueur AVANT la bascule 16.57 → 30 — les mois
    déjà postés ont été calculés avec l'ancien taux, la reprise doit les
    figer tels quels.
(b) `taux_charges_patronales_pct` (HMD Configuration) : 16.57 → 30.
    Décision explicite de M. Samir (réunion 05/08/2026). On ne touche la
    valeur que si elle est non initialisée (None/0/'') OU restée à l'ancien
    défaut seedé 16.57 — un taux saisi manuellement par la ferme est respecté.

Ordre volontaire : lire le taux global actuel, seeder l'historique avec lui,
PUIS seulement passer le global à 30 — sinon la migration elle-même
réécrirait les charges de tous les mois clôturés.

Idempotent : (a) filtre les fiches qui portent déjà des lignes ; (b) ne
s'applique plus dès que la valeur diffère de None/0/''/16.57.
"""
import frappe
from frappe.utils import cint, flt, getdate, today

ANCIEN_DEFAUT = 16.57
NOUVEAU_DEFAUT = 30.0


def execute():
    ancien_taux = _taux_global_avant()
    _seed_historique(ancien_taux)
    _maj_taux_global()


def _taux_global_avant():
    """Taux global effectif AVANT la bascule : la valeur stockée si elle est
    initialisée, sinon l'ancien défaut 16.57 (celui que `get_config` servait
    avant cette migration)."""
    if frappe.db.exists("DocType", "HMD Configuration"):
        doc = frappe.get_single("HMD Configuration")
        if doc.meta.has_field("taux_charges_patronales_pct"):
            current = flt(doc.get("taux_charges_patronales_pct"))
            if current:
                return current
    return ANCIEN_DEFAUT


def _maj_taux_global():
    if not frappe.db.exists("DocType", "HMD Configuration"):
        return
    doc = frappe.get_single("HMD Configuration")
    if not doc.meta.has_field("taux_charges_patronales_pct"):
        return
    current = doc.get("taux_charges_patronales_pct")
    non_initialise = current in (None, 0, "")
    ancien_defaut = abs(flt(current) - ANCIEN_DEFAUT) < 0.001
    if non_initialise or ancien_defaut:
        doc.taux_charges_patronales_pct = NOUVEAU_DEFAUT
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        # Loud on purpose : the operator must see the rate change in the
        # `bench migrate` output (explicit decision — M. Samir, 05/08/2026).
        message = (
            f"init_rh_defaults: taux_charges_patronales_pct "
            f"{flt(current)} -> {NOUVEAU_DEFAUT} "
            "(décision M. Samir, réunion du 05/08/2026)"
        )
        print(f"  [config] {message}")
        frappe.logger("hmd_agro").info(message)


def _seed_historique(ancien_taux):
    """Seed the initial history row of every Personnel without one. The
    employer-charge rate stored in the row is resolved with `ancien_taux`
    (the global rate read BEFORE `_maj_taux_global` bumps it to 30) so the
    migration never rewrites the charges of already-posted months."""
    if not frappe.db.exists("DocType", "Personnel") or \
            not frappe.db.exists("DocType", "Personnel Salaire Historique"):
        return
    avec_histo = set(frappe.get_all(
        "Personnel Salaire Historique",
        filters={"parenttype": "Personnel"}, pluck="parent"))
    changed = False
    for nom in frappe.get_all("Personnel", pluck="name"):
        if nom in avec_histo:
            continue
        doc = frappe.get_doc("Personnel", nom)
        if cint(doc.soumis_cnss):
            taux_fige = flt(doc.get("taux_charges_patronales_pct")) or flt(ancien_taux)
        else:
            taux_fige = 0.0
        doc.append("historique_salaires", {
            "date_effet": getdate(doc.date_embauche) if doc.date_embauche
                          else getdate(today()),
            "salaire_brut_mensuel": flt(doc.salaire_brut_mensuel),
            "taux_activite_pct": flt(doc.taux_activite_pct or 100),
            "taux_charges_patronales_pct": taux_fige,
            "soumis_cnss": cint(doc.soumis_cnss),
            "motif": "Reprise initiale (migration v1_8)",
        })
        # Legacy rows may fail today's validations (missing atelier, …) —
        # the patch only journals the current state, it must not fix data.
        doc.flags.ignore_validate = True
        doc.flags.ignore_mandatory = True
        doc.save(ignore_permissions=True)
        changed = True
    if changed:
        frappe.db.commit()
