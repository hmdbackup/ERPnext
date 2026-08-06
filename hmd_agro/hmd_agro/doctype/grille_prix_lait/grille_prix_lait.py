# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

"""FIN-S24 (RG-FIN-10/13) — grille de prix qualité de la centrale.

Jusqu'ici le litre se payait à un prix plat : `lait_prime_tb_par_point` et
`lait_prime_tp_par_point` valaient 0, donc le CA lait ignorait la qualité du
lait produit. Ce DocType porte la grille réelle — celle du contrat centrale —
et devient la source du prix (`facturation_lait.compute_milk_rate`).

Deux formes de grille, cumulables :
  • **paliers** (la forme réelle des grilles tunisiennes) : « TB ≥ 4.1 →
    +0.060 TND/L », « TP < 2.9 → −0.040 TND/L ». Un palier par tranche.
  • **indexation linéaire** de secours : prime par point de % au-delà d'une
    référence — utilisée seulement pour un critère SANS palier, ce qui
    préserve le comportement historique quand la grille n'est pas détaillée.

Prix résultant (RC-FIN-13) :

    prix = prix_base + Σ primes(critères mesurés)
    prix = min(prix, prix_base + plafond_prime)   si plafond_prime
    prix = max(prix, plancher_prix)               si plancher_prix

`statut = PROVISOIRE` signale des valeurs indicatives non confirmées par la
centrale : la facture et le contrôle de cohérence le rappellent, pour qu'un
prix d'attente ne soit jamais lu comme un prix contractuel.

Bonus quantité (FIN-B1) : le critère `VOLUME` s'exprime en **litres vendus sur
le mois** (paliers uniquement, pas d'indexation linéaire) — la centrale prime
les gros apporteurs. La prime VOLUME entre dans le plafond de prime comme les
autres critères.

Immutabilité (FIN-B1, ERR-GRL-06/07) : dès qu'un `Decompte Lait Mensuel`
soumis référence la grille, ses valeurs de prix ne bougent plus — le décompte
est un instantané et la grille qui l'a produit doit rester lisible telle
quelle. Toute évolution = clôturer la grille (`date_fin`) et en créer une
nouvelle versionnée par dates.
"""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

CRITERES = ("TB", "TP", "GERMES", "CELLULES", "VOLUME")
DATE_INFINIE = "2999-12-31"

# Fields frozen once a submitted Decompte references the grid (ERR-GRL-06).
# `date_fin`, `active`, `statut`, notes stay editable — closing/annotating a
# grid never rewrites a settled price.
CHAMPS_FIGES_PRIX = (
    "prix_base", "plancher_prix", "plafond_prime",
    "tb_reference", "prime_tb_par_point",
    "tp_reference", "prime_tp_par_point",
    "date_debut",
)


class GrillePrixLait(Document):
    def validate(self):
        self.validate_dates()
        self.validate_prix()
        self.validate_paliers()
        self.validate_unicite_active()
        self.validate_immutabilite()

    def on_trash(self):
        fige = self._decompte_fige()
        if fige:
            frappe.throw(
                _("ERR-GRL-07 : la grille est référencée par le décompte lait "
                  "figé « {0} » — suppression interdite. La désactiver ou la "
                  "clôturer (date de fin).")
                .format(fige)
            )

    def validate_dates(self):
        if self.date_fin and getdate(self.date_fin) < getdate(self.date_debut):
            frappe.throw(
                _("ERR-GRL-01 : la date de fin ({0}) précède la date de début ({1}).")
                .format(self.date_fin, self.date_debut)
            )

    def validate_prix(self):
        if flt(self.prix_base) <= 0:
            frappe.throw(_("ERR-GRL-02 : le prix de base doit être strictement positif."))
        if flt(self.plancher_prix) and flt(self.plancher_prix) > flt(self.prix_base):
            frappe.msgprint(
                _("Le plancher de prix ({0}) dépasse le prix de base ({1}) — "
                  "toutes les pénalités seront neutralisées.")
                .format(self.plancher_prix, self.prix_base),
                indicator="orange", alert=True,
            )

    def validate_paliers(self):
        """Bornes croissantes et sans chevauchement, critère par critère —
        sinon deux primes s'appliqueraient au même taux."""
        par_critere = {}
        for palier in self.paliers or []:
            borne_min = flt(palier.borne_min)
            borne_max = flt(palier.borne_max) if palier.borne_max else None
            if borne_max is not None and borne_max <= borne_min:
                frappe.throw(
                    _("ERR-GRL-03 : palier {0} — la borne haute ({1}) doit être "
                      "strictement supérieure à la borne basse ({2}).")
                    .format(palier.idx, borne_max, borne_min)
                )
            par_critere.setdefault(palier.critere, []).append((borne_min, borne_max, palier.idx))

        for critere, bornes in par_critere.items():
            bornes.sort(key=lambda b: b[0])
            for i in range(1, len(bornes)):
                precedent_max = bornes[i - 1][1]
                if precedent_max is None or bornes[i][0] < precedent_max:
                    frappe.throw(
                        _("ERR-GRL-04 : les paliers {0} et {1} du critère {2} se "
                          "chevauchent — une même valeur donnerait deux primes.")
                        .format(bornes[i - 1][2], bornes[i][2], critere)
                    )

    def validate_unicite_active(self):
        """Une seule grille active peut couvrir une date donnée (RG-FIN-13) :
        sinon le prix du litre dépendrait de l'ordre de lecture."""
        if not self.active:
            return
        concurrentes = frappe.db.sql("""
            SELECT name, date_debut, IFNULL(date_fin, %(infini)s) AS date_fin
            FROM `tabGrille Prix Lait`
            WHERE active = 1 AND name != %(nom)s
              AND date_debut <= %(fin)s
              AND IFNULL(date_fin, %(infini)s) >= %(debut)s
        """, {
            "nom": self.name or "",
            "debut": self.date_debut,
            "fin": self.date_fin or DATE_INFINIE,
            "infini": DATE_INFINIE,
        }, as_dict=True)
        if concurrentes:
            autre = concurrentes[0]
            frappe.throw(
                _("ERR-GRL-05 : la grille « {0} » est déjà active sur cette "
                  "période ({1} → {2}). Désactiver l'une des deux.")
                .format(autre.name, autre.date_debut, autre.date_fin)
            )

    def validate_immutabilite(self):
        """FIN-B1 (ERR-GRL-06) — a grid referenced by a submitted Decompte is
        a frozen pricing fact: its price fields and paliers can't change.
        Versioning happens by dates (close this grid, create the next one)."""
        if self.is_new():
            return
        fige = self._decompte_fige()
        if not fige:
            return
        avant = self.get_doc_before_save()
        if not avant:
            return
        modifies = [
            self.meta.get_label(champ) for champ in CHAMPS_FIGES_PRIX
            if self._valeur_champ(avant, champ) != self._valeur_champ(self, champ)
        ]
        if self._signature_paliers(avant) != self._signature_paliers(self):
            modifies.append(_("Paliers"))
        if modifies:
            frappe.throw(
                _("ERR-GRL-06 : la grille est référencée par le décompte lait "
                  "figé « {0} » — {1} n'est plus modifiable. Clôturer cette "
                  "grille (date de fin) et créer une nouvelle grille "
                  "versionnée par dates.")
                .format(fige, ", ".join(modifies))
            )

    def _decompte_fige(self):
        """Name of a submitted Decompte referencing this grid, or None."""
        if not frappe.db.table_exists("Decompte Lait Mensuel"):
            return None
        return frappe.db.get_value(
            "Decompte Lait Mensuel",
            {"grille": self.name, "docstatus": 1},
            "name",
        )

    @staticmethod
    def _valeur_champ(doc, champ):
        if champ == "date_debut":
            return str(getdate(doc.get(champ))) if doc.get(champ) else ""
        return flt(doc.get(champ))

    @staticmethod
    def _signature_paliers(doc):
        return sorted(
            (p.critere, flt(p.borne_min), flt(p.borne_max or 0), flt(p.prime))
            for p in (doc.get("paliers") or [])
        )

    # ── moteur de prix ──────────────────────────────────────────────────────

    def prime_critere(self, critere, valeur):
        """Prime TND/L pour un critère mesuré. Palier prioritaire ; à défaut,
        indexation linéaire (TB/TP seulement) ; 0 si le critère n'est pas
        indexé. Pour VOLUME, `valeur` = litres vendus sur le mois (FIN-B1) —
        paliers uniquement, pas d'indexation de secours."""
        if valeur is None:
            return 0.0
        valeur = flt(valeur)
        paliers = [p for p in (self.paliers or []) if p.critere == critere]
        if paliers:
            for palier in paliers:
                borne_max = flt(palier.borne_max) if palier.borne_max else None
                if valeur >= flt(palier.borne_min) and (borne_max is None or valeur < borne_max):
                    return flt(palier.prime)
            return 0.0
        if critere == "TB":
            return (valeur - flt(self.tb_reference)) * flt(self.prime_tb_par_point)
        if critere == "TP":
            return (valeur - flt(self.tp_reference)) * flt(self.prime_tp_par_point)
        return 0.0

    def prix_du_litre(self, tb=None, tp=None, germes=None, cellules=None,
                      volume=None, detail=False):
        """Prix du litre selon la grille (RC-FIN-13). `volume` = litres vendus
        sur le mois, pour le bonus quantité (palier VOLUME, FIN-B1)."""
        primes = {
            "TB": self.prime_critere("TB", tb),
            "TP": self.prime_critere("TP", tp),
            "GERMES": self.prime_critere("GERMES", germes),
            "CELLULES": self.prime_critere("CELLULES", cellules),
            "VOLUME": self.prime_critere("VOLUME", volume),
        }
        prime_totale = sum(primes.values())
        if flt(self.plafond_prime) and prime_totale > flt(self.plafond_prime):
            prime_totale = flt(self.plafond_prime)
        prix = flt(self.prix_base) + prime_totale
        if flt(self.plancher_prix):
            prix = max(prix, flt(self.plancher_prix))
        prix = round(max(prix, 0), 3)
        if not detail:
            return prix
        return {
            "prix": prix,
            "prix_base": flt(self.prix_base),
            "primes": {k: round(v, 3) for k, v in primes.items() if v},
            "prime_totale": round(prime_totale, 3),
            "grille": self.name,
            "statut": self.statut,
        }


def grille_active(date=None):
    """La grille en vigueur à une date (None si aucune). Lecture unique et
    partagée : facturation, KPI et contrôle de cohérence lisent la même."""
    date = getdate(date or today())
    nom = frappe.db.sql("""
        SELECT name FROM `tabGrille Prix Lait`
        WHERE active = 1 AND date_debut <= %(date)s
          AND IFNULL(date_fin, %(infini)s) >= %(date)s
        ORDER BY date_debut DESC
        LIMIT 1
    """, {"date": date, "infini": DATE_INFINIE})
    return frappe.get_doc("Grille Prix Lait", nom[0][0]) if nom else None
