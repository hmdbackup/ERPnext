# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

"""FIN-S42 (RG-FIN-41) — registre du personnel de la ferme.

Le DocType demandé par la maîtrise d'ouvrage : « qui travaille ici, quel rôle,
combien il est payé » — et surtout **sur quel atelier son coût est imputé**.
C'est la source de données de la masse salariale : `charges_utils.post_salaires`
reconstruit l'écriture mensuelle 640/647 depuis ce registre au lieu d'un montant
global tapé à la main.

Modèle de coût (RC-FIN-41) :

    coût employeur = salaire_brut_mensuel × taux_activite_pct / 100
                     × (1 + taux_charges_patronales_pct / 100 si soumis_cnss)

Ventilation analytique (RG-FIN-40) : `atelier` (Cost Center) porte 100 % du
coût, sauf si la table `repartition` détaille des parts — dont la somme doit
faire 100 %.

Note : le module Payroll d'ERPNext (app `hrms`) n'est pas installé sur
l'instance. Si la ferme l'adopte un jour, ce registre devient la table de
correspondance vers `Employee` — la ventilation analytique reste ici.
"""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from hmd_agro.hmd_agro.utils.config import get_config

# Atelier par défaut proposé selon le rôle (nom court du Cost Center — le
# suffixe « - <abbr> » est ajouté à la volée). Pure ergonomie de saisie :
# l'utilisateur reste libre de changer.
ATELIER_PAR_ROLE = {
    "OUVRIER_TRAITE": "Lait",
    "SOIGNEUR": "Lait",
    "RESPONSABLE_TROUPEAU": "Lait",
    "INSEMINATEUR": "Lait",
    "VETERINAIRE": "Lait",
    "TRACTORISTE": "Traction",
    "MAINTENANCE": "Frais Généraux",
    "MAGASINIER": "Frais Généraux",
    "GARDIEN": "Frais Généraux",
    "ADMINISTRATIF": "Frais Généraux",
    "COMPTABLE": "Frais Généraux",
    "AUTRE": "Frais Généraux",
}

TOLERANCE_PCT = 0.01


class Personnel(Document):
    def validate(self):
        self.set_atelier_defaut()
        self.validate_remuneration()
        self.validate_dates()
        self.validate_statut()
        self.validate_ateliers()
        self.validate_repartition()
        self.set_cout_employeur()

    # ── saisie ──────────────────────────────────────────────────────────────

    def set_atelier_defaut(self):
        """Propose l'atelier du rôle tant que rien n'est saisi (jamais écrasant)."""
        if self.atelier or not self.role_personnel:
            return
        court = ATELIER_PAR_ROLE.get(self.role_personnel)
        if not court:
            return
        candidat = cost_center_name(court)
        if candidat:
            self.atelier = candidat

    # ── règles ──────────────────────────────────────────────────────────────

    def validate_remuneration(self):
        if flt(self.salaire_brut_mensuel) < 0:
            frappe.throw(_("ERR-PERS-01 : le salaire brut mensuel ne peut pas être négatif."))
        if self.taux_activite_pct is None:
            self.taux_activite_pct = 100
        if not (0 < flt(self.taux_activite_pct) <= 100):
            frappe.throw(
                _("ERR-PERS-05 : le taux d'activité doit être compris entre 0 (exclu) "
                  "et 100 % (saisi : {0}).").format(self.taux_activite_pct)
            )

    def validate_dates(self):
        if self.date_sortie and self.date_embauche and \
                getdate(self.date_sortie) < getdate(self.date_embauche):
            frappe.throw(
                _("ERR-PERS-02 : la date de sortie ({0}) ne peut pas précéder "
                  "la date d'embauche ({1}).").format(self.date_sortie, self.date_embauche)
            )

    def validate_statut(self):
        """Invariant : sortie ⇔ date de sortie. Sinon la masse salariale
        continuerait à compter un salarié parti (ou l'inverse)."""
        if self.date_sortie and self.statut != "SORTI":
            self.statut = "SORTI"
            frappe.msgprint(
                _("Statut passé à SORTI (date de sortie renseignée)."),
                indicator="orange", alert=True,
            )
        if self.statut == "SORTI" and not self.date_sortie:
            frappe.throw(
                _("ERR-PERS-06 : un salarié SORTI doit porter une date de sortie "
                  "(elle borne le prorata de la masse salariale).")
            )

    def validate_ateliers(self):
        for cc in [self.atelier] + [r.atelier for r in (self.repartition or [])]:
            if not cc:
                continue
            if not frappe.db.exists("Cost Center", cc):
                frappe.throw(
                    _("ERR-PERS-04 : atelier « {0} » introuvable (RG-FIN-40).").format(cc)
                )
            if frappe.db.get_value("Cost Center", cc, "is_group"):
                frappe.throw(
                    _("ERR-PERS-04 : l'atelier « {0} » est un groupe — choisir un "
                      "centre de coût terminal.").format(cc)
                )

    def validate_repartition(self):
        if not self.repartition:
            return
        total = sum(flt(r.pourcentage) for r in self.repartition)
        if abs(total - 100.0) > TOLERANCE_PCT:
            frappe.throw(
                _("ERR-PERS-03 : la répartition par atelier doit totaliser 100 % "
                  "(actuellement {0} %). Vider la table pour imputer 100 % sur "
                  "l'atelier principal.").format(round(total, 2))
            )
        vus = set()
        for ligne in self.repartition:
            if ligne.atelier in vus:
                frappe.throw(
                    _("ERR-PERS-07 : l'atelier « {0} » apparaît deux fois dans "
                      "la répartition.").format(ligne.atelier)
                )
            vus.add(ligne.atelier)

    # ── dérivé ──────────────────────────────────────────────────────────────

    def set_cout_employeur(self):
        self.cout_employeur_mensuel = round(self.cout_mensuel(), 3)

    def cout_mensuel(self, avec_charges=True):
        """Coût employeur d'un mois complet (RC-FIN-41)."""
        brut = flt(self.salaire_brut_mensuel) * flt(self.taux_activite_pct or 100) / 100.0
        if not avec_charges or not self.soumis_cnss:
            return brut
        return brut * (1 + taux_charges_patronales() / 100.0)

    def ventilation(self):
        """{cost_center: part en %} — la table si elle existe, sinon 100 %
        sur l'atelier principal."""
        if self.repartition:
            return {r.atelier: flt(r.pourcentage) for r in self.repartition}
        return {self.atelier: 100.0}


def taux_charges_patronales():
    """Taux de charges patronales (%) — CNSS régime agricole amélioré par
    défaut. Jamais un littéral : HMD Configuration → Personnel."""
    return flt(get_config("taux_charges_patronales_pct", default=16.57))


def cost_center_name(nom_court):
    """« Lait » → « Lait - HMD » (None si l'atelier n'existe pas encore)."""
    from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

    abbr = frappe.db.get_value("Company", COMPANY, "abbr")
    if not abbr:
        return None
    complet = f"{nom_court} - {abbr}"
    return complet if frappe.db.exists("Cost Center", complet) else None


@frappe.whitelist()
def effectif_actif(date_reference=None):
    """Nombre de salariés présents à une date (registre RH, pas le cheptel)."""
    date_reference = getdate(date_reference or today())
    return frappe.db.count("Personnel", {
        "date_embauche": ["<=", date_reference],
        "statut": "ACTIF",
    })
