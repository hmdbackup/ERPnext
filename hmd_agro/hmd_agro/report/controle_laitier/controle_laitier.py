import frappe
from frappe.utils import getdate, add_days, today

from hmd_agro.hmd_agro.utils.lot_utils import lot_sort_key
from hmd_agro.hmd_agro.doctype.allotement_history.allotement_history import lot_on_date


def execute(filters=None):
    filters = filters or {}
    mode = filters.get("view_mode") or "Conversion"
    if mode == "CL":
        return _execute_cl(filters)
    return _execute_conversion(filters)


# ─── Shared cohort: active VACHEs that have ever been milked ────────────────

def _cohort():
    return frappe.db.sql("""
        SELECT a.name, a.nom_metier
        FROM `tabAnimal` a
        WHERE a.statut = 'ACTIF' AND a.categorie = 'VACHE'
          AND EXISTS (SELECT 1 FROM `tabTraite` t WHERE t.animal = a.name)
        ORDER BY a.nom_metier
    """, as_dict=True)


def _daily_totals(animal_names, date_from, date_to):
    """Returns {animal: {date_str: total_l}}."""
    if not animal_names:
        return {}
    rows = frappe.db.sql("""
        SELECT animal, date_traite, SUM(quantite_litres) AS total
        FROM `tabTraite`
        WHERE date_traite BETWEEN %s AND %s AND animal IN %s
        GROUP BY animal, date_traite
    """, (date_from, date_to, animal_names), as_dict=True)
    out = {}
    for r in rows:
        out.setdefault(r.animal, {})[str(r.date_traite)] = float(r.total or 0)
    return out


# ─── Conversion mode (3 days + lot + delta) ─────────────────────────────────

def _execute_conversion(filters):
    ref = getdate(filters.get("reference_date") or add_days(today(), -1))
    j_2 = add_days(ref, -2)
    j_1 = add_days(ref, -1)

    columns = [
        {"fieldname": "nom_metier", "label": "N° Travail", "fieldtype": "Data", "width": 90},
        {"fieldname": "lot", "label": "Lot", "fieldtype": "Link", "options": "Lot", "width": 110},
        {"fieldname": "j_2", "label": j_2.strftime("%d/%m"), "fieldtype": "Float", "precision": 1, "width": 75},
        {"fieldname": "j_1", "label": j_1.strftime("%d/%m"), "fieldtype": "Float", "precision": 1, "width": 75},
        {"fieldname": "j",   "label": ref.strftime("%d/%m"), "fieldtype": "Float", "precision": 1, "width": 75},
        {"fieldname": "delta", "label": "Delta", "fieldtype": "Percent", "precision": 0, "width": 80},
        {"fieldname": "moyenne_3j", "label": "Moy 3j", "fieldtype": "Float", "precision": 1, "width": 80},
    ]

    if ref > getdate(today()):
        return columns, [{"nom_metier": "Pas encore de données pour cette date."}]

    cohort = _cohort()
    if not cohort:
        return columns, []

    by_cow = _daily_totals([c.name for c in cohort], j_2, ref)
    lot_filter = filters.get("lot")

    rows = []
    for c in cohort:
        cow_lot = lot_on_date(c.name, ref) or ""
        if lot_filter and cow_lot != lot_filter:
            continue
        d = by_cow.get(c.name, {})
        v_j2 = d.get(str(j_2), 0)
        v_j1 = d.get(str(j_1), 0)
        v_j  = d.get(str(ref), 0)
        delta = round((v_j - v_j1) / v_j1 * 100) if v_j1 else None
        s = v_j2 + v_j1 + v_j
        moy = round(s / 3, 1) if s else 0
        rows.append({
            "nom_metier": c.nom_metier or c.name[-4:],
            "lot": cow_lot,
            "j_2": v_j2, "j_1": v_j1, "j": v_j,
            "delta": delta, "moyenne_3j": moy,
        })

    rows.sort(key=lambda r: (lot_sort_key(r["lot"]), r["nom_metier"]))
    return columns, rows


# ─── CL mode (date range, no lot, with chart) ───────────────────────────────

def _execute_cl(filters):
    from_date = getdate(filters.get("from_date") or add_days(today(), -7))
    to_date   = getdate(filters.get("to_date")   or add_days(today(), -1))
    if from_date > to_date:
        frappe.throw("La date de début doit être avant ou égale à la date de fin.")
    if from_date > getdate(today()):
        cols = [{"fieldname": "nom_metier", "label": "N° Travail", "fieldtype": "Data", "width": 200}]
        return cols, [{"nom_metier": "Pas encore de données pour cette période."}], None, None, []

    dates = []
    d = from_date
    while d <= to_date:
        dates.append(d)
        d = add_days(d, 1)

    columns = [{"fieldname": "nom_metier", "label": "N° Travail", "fieldtype": "Data", "width": 90}]
    for date in dates:
        columns.append({
            "fieldname": str(date), "label": date.strftime("%d/%m"),
            "fieldtype": "Float", "precision": 1, "width": 65,
        })
    columns += [
        {"fieldname": "total",   "label": "Total", "fieldtype": "Float", "precision": 1, "width": 90},
        {"fieldname": "moyenne", "label": "Moy/j", "fieldtype": "Float", "precision": 1, "width": 80},
    ]

    cohort = _cohort()
    if not cohort:
        return columns, [], None, _empty_chart(dates), []

    by_cow = _daily_totals([c.name for c in cohort], from_date, to_date)
    lot_filter = filters.get("lot")

    rows = []
    daily_sums = [0.0] * len(dates)
    for c in cohort:
        if lot_filter and lot_on_date(c.name, to_date) != lot_filter:
            continue
        d_map = by_cow.get(c.name, {})
        row = {"nom_metier": c.nom_metier or c.name[-4:]}
        row_total = 0.0
        days_with_data = 0
        for i, date in enumerate(dates):
            v = d_map.get(str(date), 0)
            row[str(date)] = v
            row_total += v
            if v > 0:
                days_with_data += 1
            daily_sums[i] += v
        row["total"]   = round(row_total, 1) if row_total else None
        row["moyenne"] = round(row_total / days_with_data, 1) if days_with_data else None
        rows.append(row)

    chart = {
        "data": {
            "labels": [d.strftime("%d/%m") for d in dates],
            "datasets": [{"name": "Production (L)", "values": [round(v, 1) for v in daily_sums]}],
        },
        "type": "bar",
        "colors": ["#4299e1"],
    }

    grand = sum(daily_sums)
    summary = [
        {"value": round(grand, 1), "label": "Production Totale (L)", "datatype": "Float"},
        {"value": len(rows), "label": "Animaux", "datatype": "Int"},
        {"value": round(grand / len(dates), 1) if dates else 0, "label": "Moyenne/jour (L)", "datatype": "Float"},
        {"value": round(grand / len(rows), 1) if rows else 0, "label": "Moyenne/animal (L)", "datatype": "Float"},
    ]
    return columns, rows, None, chart, summary


def _empty_chart(dates):
    return {
        "data": {
            "labels": [d.strftime("%d/%m") for d in dates],
            "datasets": [{"name": "Production (L)", "values": [0] * len(dates)}],
        },
        "type": "bar",
        "colors": ["#4299e1"],
    }
