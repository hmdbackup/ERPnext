import frappe
import json
from frappe.utils import getdate, add_days, today


@frappe.whitelist()
def get_lactating_animals(date):
    """Get animals with active lactation + their traites + the day's bilan
    (lait vendu / CI / LV) — all in one round-trip so the saisie page can
    render its full state from a single fetch."""
    date = getdate(date)

    # Animals whose lactation covered the selected date
    # (date_debut <= D AND (date_tarissement IS NULL OR date_tarissement >= D))
    # and who were present in the herd on D (statut ACTIF or exited on/after D).
    animals = frappe.db.sql("""
        SELECT
            a.name as animal,
            a.nom_metier,
            a.identification_tn,
            a.id_lot as lot,
            IFNULL(a.attente_lait_active, 0) as attente_lait,
            l.name as lactation
        FROM `tabAnimal` a
        INNER JOIN `tabLactation` l ON l.animal = a.name
            AND l.date_debut <= %s
            AND (l.date_tarissement IS NULL OR l.date_tarissement >= %s)
        WHERE a.statut = 'ACTIF'
           OR (a.date_sortie IS NOT NULL AND a.date_sortie >= %s)
        ORDER BY a.id_lot ASC, a.nom_metier DESC
    """, (date, date, date), as_dict=True)

    if not animals:
        return []

    animal_names = [a.animal for a in animals]

    # Existing traites for the selected date
    traites = frappe.db.sql("""
        SELECT animal, session, quantite_litres, name, id_lot
        FROM `tabTraite`
        WHERE date_traite = %s AND animal IN %s
    """, (date, animal_names), as_dict=True)

    traite_map = {}
    historic_lot = {}
    for t in traites:
        traite_map.setdefault(t.animal, {})[t.session] = {
            "qty": t.quantite_litres,
            "name": t.name
        }
        if t.id_lot:
            historic_lot[t.animal] = t.id_lot

    # Previous day totals for drop detection
    prev_date = add_days(date, -1)
    prev_totals = frappe.db.sql("""
        SELECT animal, SUM(quantite_litres) as total
        FROM `tabTraite`
        WHERE date_traite = %s AND animal IN %s
        GROUP BY animal
    """, (prev_date, animal_names), as_dict=True)

    prev_map = {p.animal: p.total for p in prev_totals}

    result = []
    for a in animals:
        at = traite_map.get(a.animal, {})
        result.append({
            "animal": a.animal,
            "nom_metier": a.nom_metier or a.animal,
            "identification_tn": a.identification_tn or "",
            "lot": historic_lot.get(a.animal) or a.lot or "",
            "attente_lait": a.attente_lait,
            "lactation": a.lactation,
            "matin": at.get("MATIN"),
            "soir": at.get("SOIR"),
            "prev_total": prev_map.get(a.animal, 0) or 0
        })

    bilan_name = frappe.db.get_value("Bilan Lait Journalier", {"date": date}, "name")
    if bilan_name:
        b = frappe.db.get_value(
            "Bilan Lait Journalier", bilan_name,
            ["lait_vendu", "consommation_interne", "lait_veau"], as_dict=True)
        bilan = {
            "lait_vendu": float(b.lait_vendu or 0),
            "consommation_interne": float(b.consommation_interne or 0),
            "lait_veau": float(b.lait_veau or 0),
        }
    else:
        bilan = {"lait_vendu": 0, "consommation_interne": 0, "lait_veau": 0}

    return {"animals": result, "bilan": bilan}


@frappe.whitelist()
def save_traites(date, entries, bilan=None):
    """Save multiple traites at once. Uses frappe.get_doc so all validations fire.
    Optionally upserts the day's Bilan Lait Journalier (lait vendu / CI / LV).
    """
    if isinstance(entries, str):
        entries = json.loads(entries)
    if isinstance(bilan, str):
        bilan = json.loads(bilan)

    created = 0
    updated = 0
    errors = []

    for entry in entries:
        try:
            if entry.get("traite_name"):
                doc = frappe.get_doc("Traite", entry["traite_name"])
                doc.quantite_litres = entry["quantite_litres"]
                doc.save()
                updated += 1
            else:
                doc = frappe.get_doc({
                    "doctype": "Traite",
                    "animal": entry["animal"],
                    "date_traite": date,
                    "session": entry["session"],
                    "quantite_litres": entry["quantite_litres"]
                })
                doc.insert()
                created += 1
        except Exception as e:
            errors.append({
                "animal": entry.get("animal"),
                "session": entry.get("session"),
                "error": str(e)
            })

    bilan_status = None
    if bilan is not None:
        try:
            bilan_status = _upsert_bilan(date, bilan)
        except Exception as e:
            errors.append({"animal": "BILAN", "session": "", "error": str(e)})

    frappe.db.commit()

    return {
        "created": created,
        "updated": updated,
        "errors": errors,
        "bilan_status": bilan_status,
    }


def _upsert_bilan(date, bilan):
    """Insert or update the Bilan Lait Journalier row for `date`."""
    existing = frappe.db.get_value("Bilan Lait Journalier", {"date": date}, "name")
    payload = {
        "lait_vendu": float(bilan.get("lait_vendu") or 0),
        "consommation_interne": float(bilan.get("consommation_interne") or 0),
        "lait_veau": float(bilan.get("lait_veau") or 0),
    }
    if existing:
        doc = frappe.get_doc("Bilan Lait Journalier", existing)
        for k, v in payload.items():
            doc.set(k, v)
        doc.save()
        return "updated"
    else:
        doc = frappe.get_doc({
            "doctype": "Bilan Lait Journalier",
            "date": date,
            **payload,
        })
        doc.insert()
        return "created"
