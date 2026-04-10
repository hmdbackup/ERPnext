import frappe
from frappe.utils import add_days, cint, date_diff, getdate, today


def execute(filters=None):
    filters = filters or {}

    reference_date = getdate(filters.get("reference_date") or add_days(today(), -1))
    date_j_1 = add_days(reference_date, -1)
    date_j_2 = add_days(reference_date, -2)

    columns = build_columns(reference_date, date_j_1, date_j_2)
    data = get_data(reference_date, date_j_1, date_j_2, filters)

    return columns, data


def build_columns(reference_date, date_j_1, date_j_2):
    return [
        {"fieldname": "animal", "label": "Animal", "fieldtype": "Link", "options": "Animal", "width": 90},
        {"fieldname": "nom_metier", "label": "Vache", "fieldtype": "Data", "width": 90},
        {"fieldname": "lot_actuel", "label": "Lot", "fieldtype": "Link", "options": "Lot", "width": 90},
        {"fieldname": "dim", "label": "J L", "fieldtype": "Int", "width": 70},
        {"fieldname": "jours_gestation", "label": "GEST", "fieldtype": "Int", "width": 70},
        {"fieldname": "j_2", "label": date_j_2.strftime("Tot %d-%b"), "fieldtype": "Float", "precision": 1, "width": 85},
        {"fieldname": "j_1", "label": date_j_1.strftime("Tot %d-%b"), "fieldtype": "Float", "precision": 1, "width": 85},
        {"fieldname": "j", "label": reference_date.strftime("Tot %d-%b"), "fieldtype": "Float", "precision": 1, "width": 85},
        {"fieldname": "delta_j_vs_j_1", "label": "Delta J/J-1", "fieldtype": "Percent", "width": 95},
        {"fieldname": "moyenne_3j", "label": "Moy 3j", "fieldtype": "Float", "precision": 1, "width": 85}
    ]


def get_data(reference_date, date_j_1, date_j_2, filters):
    lot_filter = filters.get("lot")

    conditions = ["a.categorie = 'VACHE'", "a.statut = 'ACTIF'"]
    values = {
        "reference_date": reference_date,
        "date_j_1": date_j_1,
        "date_j_2": date_j_2,
    }

    if lot_filter:
        conditions.append("a.id_lot = %(lot)s")
        values["lot"] = lot_filter

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            a.name AS animal,
            a.nom_metier,
            a.id_lot AS lot_actuel,
            a.etat_gestation,
            a.id_ia_fecondante,
            l.date_debut AS date_debut_lactation,
            SUM(CASE WHEN t.date_traite = %(date_j_2)s THEN t.quantite_litres ELSE 0 END) AS j_2,
            SUM(CASE WHEN t.date_traite = %(date_j_1)s THEN t.quantite_litres ELSE 0 END) AS j_1,
            SUM(CASE WHEN t.date_traite = %(reference_date)s THEN t.quantite_litres ELSE 0 END) AS j
        FROM `tabAnimal` a
        LEFT JOIN `tabLactation` l
            ON l.animal = a.name AND l.statut = 'EN_COURS'
        LEFT JOIN `tabTraite` t
            ON t.animal = a.name
           AND t.date_traite BETWEEN %(date_j_2)s AND %(reference_date)s
        WHERE {where_clause}
        GROUP BY a.name, a.nom_metier, a.id_lot, a.etat_gestation, a.id_ia_fecondante, l.date_debut
        ORDER BY (
            SUM(CASE WHEN t.date_traite = %(date_j_2)s THEN t.quantite_litres ELSE 0 END)
            + SUM(CASE WHEN t.date_traite = %(date_j_1)s THEN t.quantite_litres ELSE 0 END)
            + SUM(CASE WHEN t.date_traite = %(reference_date)s THEN t.quantite_litres ELSE 0 END)
        ) DESC,
        l.date_debut ASC
        """,
        values,
        as_dict=True,
    )

    if not rows:
        return []

    ia_names = [r.id_ia_fecondante for r in rows if r.id_ia_fecondante]
    ia_dates = {}
    if ia_names:
        ia_data = frappe.get_all(
            "Insemination",
            filters={"name": ["in", ia_names]},
            fields=["name", "date_ia"],
        )
        ia_dates = {d.name: d.date_ia for d in ia_data}

    data = []
    for r in rows:
        j_2 = float(r.j_2 or 0)
        j_1 = float(r.j_1 or 0)
        j = float(r.j or 0)

        moyenne_3j = round((j_2 + j_1 + j) / 3, 1)
        delta = 0
        if j_1 > 0:
            delta = round(((j - j_1) / j_1) * 100, 1)

        dim = None
        if r.date_debut_lactation:
            dim = max(cint(date_diff(reference_date, r.date_debut_lactation)), 0)

        jours_gestation = None
        if r.etat_gestation == "GESTANTE" and r.id_ia_fecondante:
            date_ia = ia_dates.get(r.id_ia_fecondante)
            if date_ia:
                jours_gestation = max(cint(date_diff(reference_date, date_ia)), 0)

        data.append(
            {
                "animal": r.animal,
                "nom_metier": r.nom_metier or (r.animal[-4:] if r.animal else ""),
                "lot_actuel": "" if r.lot_actuel == "Individuel" else (r.lot_actuel or ""),
                "dim": dim,
                "jours_gestation": jours_gestation,
                "j_2": j_2,
                "j_1": j_1,
                "j": j,
                "delta_j_vs_j_1": delta,
                "moyenne_3j": moyenne_3j,
            }
        )

    return data
