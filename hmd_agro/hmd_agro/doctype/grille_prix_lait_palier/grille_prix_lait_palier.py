# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class GrillePrixLaitPalier(Document):
    """Un palier de la grille qualité : « TB entre 3.8 et 4.1 → +0.030 TND/L ».
    Les bornes et le chevauchement sont validés par le parent Grille Prix Lait."""
    pass
