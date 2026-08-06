# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class BilanLaitVente(Document):
    """FIN-S94 — une ligne de ventilation du lait vendu : « ce jour-là, tant de
    litres sont partis chez cet acheteur ». Le total de la table alimente
    `Bilan Lait Journalier.lait_vendu`, qui reste LE total vendu du jour.
    L'unicité de l'acheteur et la somme sont validées par le parent."""
    pass
