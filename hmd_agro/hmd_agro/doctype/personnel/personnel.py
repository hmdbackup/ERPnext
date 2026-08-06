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
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, strip_html, today

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

# Remuneration fields journalled in the immutable salary history (A2).
CHAMPS_REMUNERATION = (
    "salaire_brut_mensuel", "taux_activite_pct",
    "taux_charges_patronales_pct", "soumis_cnss",
)
CHAMPS_HISTORIQUE = ("date_effet",) + CHAMPS_REMUNERATION + ("motif",)


class Personnel(Document):
    def validate(self):
        self.set_atelier_defaut()
        self.validate_remuneration()
        self.validate_dates()
        self.validate_statut()
        self.validate_ateliers()
        self.validate_repartition()
        self.proteger_historique()
        self.maintenir_historique()
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
        if self.taux_charges_patronales_pct is not None and \
                not (0 <= flt(self.taux_charges_patronales_pct) <= 100):
            frappe.throw(
                _("ERR-PERS-08 : le taux de charges patronales doit être compris "
                  "entre 0 et 100 % (saisi : {0}).").format(self.taux_charges_patronales_pct)
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

    # ── historique de salaire (A2) ──────────────────────────────────────────

    def proteger_historique(self):
        """History rows are an immutable journal (posted months were built
        from them) : any edit or deletion of an existing row is rejected.
        Escape hatch : a System Manager may edit or delete the MOST RECENT
        row only (fix a same-day typo, journal a correction) — older rows
        stay frozen for everyone."""
        if self.is_new():
            return
        db_rows = frappe.get_all(
            "Personnel Salaire Historique",
            filters={"parent": self.name, "parenttype": "Personnel"},
            fields=["name", "idx"] + list(CHAMPS_HISTORIQUE),
        )
        if not db_rows:
            return
        est_system_manager = "System Manager" in frappe.get_roles()
        derniere = max(db_rows, key=lambda r: cint(r["idx"]))["name"]
        actuels = {r.name: r for r in (self.historique_salaires or []) if r.name}
        for db_row in db_rows:
            if est_system_manager and db_row["name"] == derniere:
                continue
            row = actuels.get(db_row["name"])
            if not row:
                frappe.throw(
                    _("ERR-PERS-09 : l'historique de salaire est immuable — "
                      "suppression de la ligne du {0} refusée.").format(db_row["date_effet"])
                )
            for champ in CHAMPS_HISTORIQUE:
                if _differe(champ, row.get(champ), db_row.get(champ)):
                    frappe.throw(
                        _("ERR-PERS-09 : l'historique de salaire est immuable — "
                          "modification de la ligne du {0} (champ {1}) refusée. "
                          "Changer la rémunération sur la fiche : une nouvelle "
                          "ligne sera ajoutée.").format(db_row["date_effet"], champ)
                    )

    def maintenir_historique(self):
        """Append-only salary journal. On hire : one « situation initiale »
        row. Afterwards : any change to a remuneration field appends a row
        dated `date_effet_modification` (or today when empty — the field is
        cleared after use) — the past is never rewritten, and
        `masse_salariale` reads the row effective for the month it computes."""
        if self.is_new():
            if not self.historique_salaires:
                self._append_historique(self.date_embauche or today(),
                                        "Situation initiale")
            self.date_effet_modification = None
            return
        avant = frappe.db.get_value(
            "Personnel", self.name, CHAMPS_REMUNERATION, as_dict=True)
        if not avant:
            self.date_effet_modification = None
            return
        if any(_differe(champ, self.get(champ), avant.get(champ))
               for champ in CHAMPS_REMUNERATION):
            self._append_historique(self.date_effet_modification or today(),
                                    "Modification de la rémunération")
        self.date_effet_modification = None

    def _append_historique(self, date_effet, motif):
        """Journal one remuneration snapshot. The employer-charge rate is
        RESOLVED here (per-employee override or the CURRENT global rate) and
        frozen into the row : a later change of the global rate must not
        rewrite closed months — `masse_salariale` reads the stored rate
        as-is. A non-CNSS employee freezes 0."""
        taux_fige = self.taux_charges_effectif() if cint(self.soumis_cnss) else 0.0
        self.append("historique_salaires", {
            "date_effet": getdate(date_effet),
            "salaire_brut_mensuel": flt(self.salaire_brut_mensuel),
            "taux_activite_pct": flt(self.taux_activite_pct or 100),
            "taux_charges_patronales_pct": flt(taux_fige),
            "soumis_cnss": cint(self.soumis_cnss),
            "motif": motif,
        })

    # ── dérivé ──────────────────────────────────────────────────────────────

    def set_cout_employeur(self):
        self.cout_employeur_mensuel = round(self.cout_mensuel(), 3)

    def cout_mensuel(self, avec_charges=True):
        """Coût employeur d'un mois complet (RC-FIN-41)."""
        brut = flt(self.salaire_brut_mensuel) * flt(self.taux_activite_pct or 100) / 100.0
        if not avec_charges or not self.soumis_cnss:
            return brut
        return brut * (1 + self.taux_charges_effectif() / 100.0)

    def taux_charges_effectif(self):
        """Taux de charges patronales applicable à CE salarié : sa valeur
        propre si renseignée (> 0), sinon le taux global de HMD Configuration.
        Un salarié exonéré se décoche `soumis_cnss` (0 = « non renseigné »)."""
        if flt(self.taux_charges_patronales_pct):
            return flt(self.taux_charges_patronales_pct)
        return taux_charges_patronales()

    def ventilation(self):
        """{cost_center: part en %} — la table si elle existe, sinon 100 %
        sur l'atelier principal."""
        if self.repartition:
            return {r.atelier: flt(r.pourcentage) for r in self.repartition}
        return {self.atelier: 100.0}


def _differe(champ, a, b):
    """Field-aware comparison for remuneration/history values (dates vs
    numerics vs text) — avoids false « changed » on type round-trips."""
    if champ == "date_effet":
        return (getdate(a) if a else None) != (getdate(b) if b else None)
    if champ == "soumis_cnss":
        return cint(a) != cint(b)
    if champ == "motif":
        return (a or "") != (b or "")
    return abs(flt(a) - flt(b)) > 0.0001


def taux_charges_patronales():
    """Taux de charges patronales (%) global — surchargeable salarié par
    salarié via `Personnel.taux_charges_patronales_pct`. Jamais un littéral :
    HMD Configuration → Personnel (30 % — décision M. Samir, 05/08/2026)."""
    return flt(get_config("taux_charges_patronales_pct", default=30))


def cost_center_name(nom_court):
    """« Lait » → « Lait - HMD » (None si l'atelier n'existe pas encore)."""
    from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

    abbr = frappe.db.get_value("Company", COMPANY, "abbr")
    if not abbr:
        return None
    complet = f"{nom_court} - {abbr}"
    return complet if frappe.db.exists("Cost Center", complet) else None


@frappe.whitelist()
def attribuer_prime_bulk(personnels, montant, periode, motif=None):
    """Create one `Prime Personnel` per selected employee (listview action
    « Attribuer une prime »). Validation (montant > 0, période AAAA-MM,
    doublons, mois non posté) is enforced by the Prime Personnel controller —
    each insert runs under its own savepoint, so a failure on one employee
    rolls back only its own row and does not block the others."""
    from hmd_agro.hmd_agro.utils.charges_utils import existing_entry

    if isinstance(personnels, str):
        personnels = json.loads(personnels)

    # Fail fast : same guard as ERR-PRIME-04 (Prime Personnel.validate) —
    # inutile de boucler si tout le mois est déjà posté au Grand Livre.
    je_existante = existing_entry(periode)
    if je_existante:
        frappe.throw(
            _("ERR-PRIME-04 : les salaires de {0} sont déjà postés au Grand "
              "Livre ({1}) — annuler ou régulariser cette écriture avant "
              "d'attribuer une prime sur ce mois.").format(periode, je_existante)
        )

    created, errors = 0, []
    for i, nom in enumerate(personnels):
        savepoint = f"prime_bulk_{i}"
        frappe.db.savepoint(savepoint)
        try:
            frappe.get_doc({
                "doctype": "Prime Personnel",
                "personnel": nom,
                "montant": flt(montant),
                "periode": periode,
                "motif": motif or "",
                "date_attribution": today(),
            }).insert()
            created += 1
        except Exception as exc:
            frappe.db.rollback(save_point=savepoint)
            libelle = frappe.db.get_value("Personnel", nom, "nom_complet") or nom
            errors.append({"personnel": libelle, "error": strip_html(str(exc))})

    return {"created": created, "errors": errors}


@frappe.whitelist()
def effectif_actif(date_reference=None):
    """Nombre de salariés présents à une date (registre RH, pas le cheptel)."""
    date_reference = getdate(date_reference or today())
    return frappe.db.count("Personnel", {
        "date_embauche": ["<=", date_reference],
        "statut": "ACTIF",
    })
