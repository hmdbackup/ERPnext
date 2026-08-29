# Copyright (c) 2026, HMD AGRO and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class RepartitionAtelierCharge(Document):
    """Analytical split of one Frais Généraux charge line across ateliers.

    Child of Purchase Invoice / Journal Entry. Rules live in
    hmd_agro.hmd_agro.utils.repartition_charges (validate hook of the parent).
    """
