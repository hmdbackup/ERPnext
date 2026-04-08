import frappe
from frappe.utils import getdate, add_days


def execute(filters=None):
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    lot = filters.get("lot")

    # Build date range
    dates = []
    d = from_date
    while d <= to_date:
        dates.append(d)
        d = add_days(d, 1)

    # Columns: Animal, Lot, dates, Total, Moyenne, Delta
    columns = [
        {"fieldname": "nom_metier", "label": "Animal", "fieldtype": "Data", "width": 70},
        {"fieldname": "lot", "label": "Lot", "fieldtype": "Data", "width": 80},
    ]
    for date in dates:
        columns.append({
            "fieldname": str(date),
            "label": date.strftime("%d/%m"),
            "fieldtype": "Float",
            "precision": 1,
            "width": 65,
        })
    columns.extend([
        {"fieldname": "total", "label": "Total", "fieldtype": "Float", "precision": 1, "width": 80},
        {"fieldname": "moyenne", "label": "Moy/j", "fieldtype": "Float", "precision": 1, "width": 70},
        {"fieldname": "delta", "label": "Delta", "fieldtype": "Percent", "precision": 0, "width": 80},
    ])

    # Get all active cows
    animal_filters = {"statut": "ACTIF", "categorie": "VACHE"}
    if lot:
        animal_filters["id_lot"] = lot

    animals = frappe.get_all("Animal",
        filters=animal_filters,
        fields=["name", "nom_metier", "id_lot"],
        order_by="id_lot asc, nom_metier desc"
    )

    if not animals:
        return columns, []

    animal_names = [a.name for a in animals]

    # Get all traites in date range for these animals
    traites = frappe.db.sql("""
        SELECT animal, date_traite, SUM(quantite_litres) as daily_total
        FROM `tabTraite`
        WHERE date_traite BETWEEN %s AND %s
        AND animal IN %s
        GROUP BY animal, date_traite
    """, (from_date, to_date, animal_names), as_dict=True)

    # Build lookup: {animal: {date: total}}
    traite_map = {}
    for t in traites:
        traite_map.setdefault(t.animal, {})[str(t.date_traite)] = float(t.daily_total or 0)

    # Build rows
    result = []
    for a in animals:
        row = {
            "nom_metier": a.nom_metier or a.name[-4:],
            "lot": a.id_lot if a.id_lot != "Individuel" else "",
        }
        row_total = 0
        days_with_data = 0
        for date in dates:
            val = traite_map.get(a.name, {}).get(str(date), 0)
            row[str(date)] = val
            row_total += val
            if val > 0:
                days_with_data += 1

        row["total"] = round(row_total, 1) if row_total else None
        row["moyenne"] = round(row_total / days_with_data, 1) if days_with_data else None

        # Delta: find last two days WITH data (not just last two calendar days)
        animal_dates = traite_map.get(a.name, {})
        filled_days = sorted([d for d in dates if animal_dates.get(str(d), 0) > 0], reverse=True)

        if len(filled_days) >= 2:
            last_val = animal_dates[str(filled_days[0])]
            prev_val = animal_dates[str(filled_days[1])]
            row["delta"] = round(((last_val - prev_val) / prev_val) * 100)
        else:
            row["delta"] = None

        result.append(row)

    # Chart: daily totals
    daily_totals = []
    for date in dates:
        day_sum = sum(traite_map.get(a.name, {}).get(str(date), 0) for a in animals)
        daily_totals.append(day_sum)

    chart = {
        "data": {
            "labels": [d.strftime("%d/%m") for d in dates],
            "datasets": [{"name": "Production (L)", "values": daily_totals}]
        },
        "type": "bar",
        "colors": ["#4299e1"]
    }

    # Summary
    grand_total = sum(daily_totals)
    avg_per_day = round(grand_total / len(dates), 1) if dates else 0
    avg_per_animal = round(grand_total / len(animals), 1) if animals else 0

    report_summary = [
        {"value": round(grand_total, 1), "label": "Production Totale (L)", "datatype": "Float"},
        {"value": len(animals), "label": "Animaux", "datatype": "Int"},
        {"value": avg_per_day, "label": "Moyenne/jour (L)", "datatype": "Float"},
        {"value": avg_per_animal, "label": "Moyenne/animal (L)", "datatype": "Float"},
    ]

    return columns, result, None, chart, report_summary
