"""Bulk recompute Animal.date_tarissement for all GESTANTE animals.

Triggered by HMD Configuration.on_update() when tarissement_window_jours
changes. Same pattern as lactation_recalc — propagates the new window to
already-stored Animal.date_tarissement values.

Uses frappe.db.set_value to bypass Animal.lock_identity_fields validation
(date_tarissement is a protected field on manual edits).
"""
import frappe
from frappe.utils import add_days, date_diff, getdate, today

from hmd_agro.hmd_agro.utils.config import get_config


@frappe.whitelist()
def recalculate_tarissement_dates():
    """Recompute Animal.date_tarissement = date_velage_prevue - window
    for every GESTANTE animal whose date_velage_prevue is set.
    Also refreshes the raison text of any open TARISSEMENT alerts so the
    operator-facing message stays consistent with the new planned date."""
    window = get_config("tarissement_window_jours", default=60)

    animals = frappe.get_all(
        "Animal",
        filters={
            "etat_gestation": "GESTANTE",
            "date_velage_prevue": ["is", "set"],
        },
        fields=["name", "date_velage_prevue"],
    )
    success, failed, alerts_refreshed = 0, [], 0

    for a in animals:
        try:
            new_date = add_days(getdate(a.date_velage_prevue), -window)
            frappe.db.set_value(
                "Animal", a.name, "date_tarissement", new_date,
                update_modified=False,
            )
            alerts_refreshed += _refresh_tarissement_alert_raison(a.name, new_date)
            success += 1
        except Exception as e:
            failed.append(a.name)
            frappe.log_error(
                f"Tarissement recalc failed for {a.name}: {e}",
                "Tarissement Bulk Recalc",
            )

    frappe.db.commit()
    frappe.publish_realtime(
        "tarissement_recalc_done",
        {"success": success, "failed": failed, "total": len(animals),
         "alerts_refreshed": alerts_refreshed},
    )
    return {"success": success, "failed": failed, "total": len(animals),
            "alerts_refreshed": alerts_refreshed}


def _refresh_tarissement_alert_raison(animal_name, new_date):
    """Update raison text of open TARISSEMENT alerts for this animal so the
    message reflects the recomputed date_tarissement. Returns count refreshed."""
    open_alerts = frappe.get_all("Alerte", filters={
        "animal": animal_name,
        "type_alerte": "TARISSEMENT",
        "statut": ["in", ["NOUVELLE", "CONFIRMEE"]],
    }, fields=["name"])
    if not open_alerts:
        return 0

    days_until = date_diff(new_date, getdate(today()))
    if days_until > 0:
        raison = f"Tarissement prevu dans {days_until} jour(s) ({new_date})"
    elif days_until == 0:
        raison = f"Tarissement prevu aujourd'hui ({new_date})"
    else:
        raison = f"Tarissement en retard de {abs(days_until)} jour(s) ({new_date})"

    for alert in open_alerts:
        frappe.db.set_value("Alerte", alert.name, "raison", raison,
                            update_modified=False)
    return len(open_alerts)
