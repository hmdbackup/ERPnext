import frappe
from frappe.model.document import Document

from hmd_agro.hmd_agro.utils.snapshot import (
    freeze_day, freeze_yesterday,  # noqa: F401 — scheduler / whitelisted entry points
)


class SnapshotJournalier(Document):
    pass


@frappe.whitelist()
def regenerate(date):
    """Rebuild (or create) the frozen snapshot for a given date from current DB state."""
    return freeze_day(date)
