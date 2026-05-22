"""Bulk recompute Animal.date_velage_prevue + Animal.date_tarissement for
every GESTANTE animal that has a fecondante IA recorded.

Triggered by HMD Configuration.on_update() when periode_velage_jours changes.
Both dates shift in lockstep:
    date_velage_prevue = fecondante_IA.date_ia + periode_velage_jours
    date_tarissement   = date_velage_prevue - tarissement_window_jours

Same pattern as tarissement_recalc — uses frappe.db.set_value to bypass the
Animal identity-field locks (these are protected reproduction fields on
manual edits). Refreshes the raison text of any open VELAGE_IMMINENT and
TARISSEMENT alerts so the operator-facing message stays consistent.
"""
import frappe
from frappe.utils import add_days, date_diff, getdate, today

from hmd_agro.hmd_agro.utils.config import get_config


@frappe.whitelist()
def recalculate_velage_prevue_dates():
    """For every GESTANTE animal with id_ia_fecondante set, recompute
    date_velage_prevue from the fecondante IA's date_ia + current
    periode_velage_jours, and date_tarissement from velage_prevue -
    tarissement_window_jours."""
    period = get_config("periode_velage_jours", default=280)
    window = get_config("tarissement_window_jours", default=60)

    animals = frappe.get_all(
        "Animal",
        filters={
            "etat_gestation": "GESTANTE",
            "id_ia_fecondante": ["is", "set"],
        },
        fields=["name", "id_ia_fecondante"],
    )
    success, failed, alerts_refreshed = 0, [], 0

    for a in animals:
        try:
            date_ia = frappe.db.get_value("Insemination", a.id_ia_fecondante, "date_ia")
            if not date_ia:
                # Orphan link — fecondante IA missing or has no date. Skip.
                continue
            new_velage = add_days(getdate(date_ia), period)
            new_tarissement = add_days(new_velage, -window)
            frappe.db.set_value(
                "Animal", a.name,
                {"date_velage_prevue": new_velage, "date_tarissement": new_tarissement},
                update_modified=False,
            )
            alerts_refreshed += _refresh_velage_alert_raison(a.name, new_velage)
            alerts_refreshed += _refresh_tarissement_alert_raison(a.name, new_tarissement)
            success += 1
        except Exception as e:
            failed.append(a.name)
            frappe.log_error(
                f"Velage prevue recalc failed for {a.name}: {e}",
                "Velage Prevue Bulk Recalc",
            )

    frappe.db.commit()
    frappe.publish_realtime(
        "velage_prevue_recalc_done",
        {"success": success, "failed": failed, "total": len(animals),
         "alerts_refreshed": alerts_refreshed},
    )
    return {"success": success, "failed": failed, "total": len(animals),
            "alerts_refreshed": alerts_refreshed}


def _refresh_velage_alert_raison(animal_name, new_date):
    """Update raison text of open VELAGE_IMMINENT alerts so the message
    reflects the recomputed date_velage_prevue. Closed alerts left as-is."""
    open_alerts = frappe.get_all("Alerte", filters={
        "animal": animal_name,
        "type_alerte": "VELAGE_IMMINENT",
        "statut": ["in", ["NOUVELLE", "CONFIRMEE"]],
    }, fields=["name"])
    if not open_alerts:
        return 0

    days_until = date_diff(new_date, getdate(today()))
    if days_until > 0:
        raison = f"Velage prevu dans {days_until} jour(s) ({new_date})"
    elif days_until == 0:
        raison = f"Velage prevu aujourd'hui ({new_date})"
    else:
        raison = f"Velage en retard de {abs(days_until)} jour(s) ({new_date})"

    for alert in open_alerts:
        frappe.db.set_value("Alerte", alert.name, "raison", raison,
                            update_modified=False)
    return len(open_alerts)


def _refresh_tarissement_alert_raison(animal_name, new_date):
    """Update raison text of open TARISSEMENT alerts so the message reflects
    the recomputed date_tarissement. Same logic as tarissement_recalc; kept
    local to avoid a cross-module import dance."""
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
