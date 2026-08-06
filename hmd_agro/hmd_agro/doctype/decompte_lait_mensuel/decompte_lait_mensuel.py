# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

"""FIN-B1 (Phase 1) — décompte lait mensuel : l'historisation stricte du prix.

Jusqu'ici le prix du litre n'existait qu'« en vol » : la facture le portait,
mais chaque rapport le recalculait en direct depuis la grille en vigueur — et
éditer une grille réécrivait rétroactivement les KPI des mois clôturés.

Ce DocType fige le règlement d'une période : volumes, TB/TP pondérés, grille
appliquée, décomposition du prix (base + prime qualité + prime quantité +
ajustement manuel négocié) et facture émise. Une fois soumis (docstatus 1),
c'est un instantané immuable :

  • la facture lait est émise au `prix_final` du décompte ;
  • `finance_kpis.ecart_lait` lit le prix figé au lieu de recalculer ;
  • la grille référencée devient elle-même immuable (ERR-GRL-06/07) —
    toute évolution passe par une nouvelle grille versionnée par dates.

L'`ajustement_manuel` (TND/L, motif obligatoire) se saisit en brouillon AVANT
la facturation : `facturation_lait.generate_milk_invoice` retrouve le
brouillon de la période, le complète et le soumet avec la facture.
"""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class DecompteLaitMensuel(Document):
    def validate(self):
        self.validate_periode()
        self.validate_ajustement()
        self.compute_prix()

    def validate_periode(self):
        if getdate(self.periode_fin) < getdate(self.periode_debut):
            frappe.throw(
                _("ERR-DLM-01 : la fin de période ({0}) précède le début ({1}).")
                .format(self.periode_fin, self.periode_debut)
            )
        # Two settlements over the same days would double-count the milk and
        # make the KPI lookup (which decompte covers this period?) ambiguous.
        # Phase-1 single-buyer semantics: the overlap check is deliberately NOT
        # scoped by acheteur (one centrale buys all the milk). Multi-acheteur
        # will require scoping this check — and the existing_decompte /
        # _decompte_couvrant lookups — by acheteur.
        chevauche = frappe.db.get_value(
            "Decompte Lait Mensuel",
            {
                "name": ["!=", self.name or ""],
                "docstatus": ["<", 2],
                "periode_debut": ["<=", self.periode_fin],
                "periode_fin": [">=", self.periode_debut],
            },
            "name",
        )
        if chevauche:
            frappe.throw(
                _("ERR-DLM-04 : le décompte « {0} » couvre déjà une partie de "
                  "cette période — un jour de lait ne se règle qu'une fois.")
                .format(chevauche)
            )

    def before_submit(self):
        # A decompte submitted without its invoice would be found by
        # existing_decompte and silently block billing of the period forever.
        # Only the billing flow (facturation_lait) may submit an unfactured
        # decompte — it sets flags.from_facturation and links the invoice.
        if not self.facture and not self.flags.get("from_facturation"):
            frappe.throw(
                _("ERR-DLM-06 : ce décompte n'est lié à aucune facture — le "
                  "soumettre ainsi bloquerait définitivement la facturation de "
                  "la période. Laissez-le en brouillon : le traitement de "
                  "facturation (generate_milk_invoice) le complétera et le "
                  "soumettra avec la facture.")
            )

    def validate_ajustement(self):
        if flt(self.ajustement_manuel) and not (self.ajustement_motif or "").strip():
            frappe.throw(
                _("ERR-DLM-02 : un ajustement manuel ({0} TND/L) exige un motif — "
                  "on doit pouvoir dire six mois plus tard pourquoi.")
                .format(self.ajustement_manuel)
            )

    def compute_prix(self):
        """prix_final and montant are always recomputed server-side — the
        stored decomposition IS the price, nothing else can override it."""
        self.prix_final = round(
            flt(self.prix_base) + flt(self.prime_qualite)
            + flt(self.prime_quantite) + flt(self.ajustement_manuel), 3)
        # A pre-billing draft (ajustement saisi, prix pas encore rempli) may be
        # transiently negative; a priced or submitted decompte may not.
        if self.prix_final < 0 and (flt(self.prix_base) or self.docstatus == 1):
            frappe.throw(
                _("ERR-DLM-03 : le prix final est négatif ({0} TND/L) — "
                  "l'ajustement dépasse le prix du lait.")
                .format(self.prix_final)
            )
        self.montant = round(flt(self.volume_litres) * flt(self.prix_final), 3)
