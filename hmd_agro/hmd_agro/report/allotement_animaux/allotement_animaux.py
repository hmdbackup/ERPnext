import frappe
from frappe.utils import add_days, cint, date_diff, getdate, today

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.lot_utils import lot_sort_key
from hmd_agro.hmd_agro.utils.report_format import normalize_precision


@normalize_precision
def execute(filters=None):
    filters = filters or {}

    # Session viewing mode: a past session was picked, render its frozen snapshot.
    session_name = filters.get("session")
    if session_name:
        return _render_session(session_name, filters)

    # Live mode: J = yesterday (today's milking may not be complete yet).
    reference_date = getdate(add_days(today(), -1))
    date_j_1 = add_days(reference_date, -1)
    date_j_2 = add_days(reference_date, -2)

    columns = build_columns(reference_date, date_j_1, date_j_2)
    data = get_data(reference_date, date_j_1, date_j_2, filters)

    return columns, data


def _render_session(session_name, filters):
    """Render a stored Allotment Session as a printable movement list:
    only cows that actually changed lot, with the 3 columns the farm worker
    needs (cow ID, source lot, target lot)."""
    doc = frappe.get_doc("Allotment Session", session_name)
    columns = [
        {"fieldname": "nom_metier", "label": "N° Travail", "fieldtype": "Data", "width": 120},
        {"fieldname": "lot_actuel", "label": "Lot Actuel", "fieldtype": "Link", "options": "Lot", "width": 160},
        {"fieldname": "lot_destination", "label": "Lot Destination", "fieldtype": "Link", "options": "Lot", "width": 160},
    ]

    lot_filter = filters.get("lot")
    data = []
    for r in doc.rows:
        if not r.moved:
            continue
        if lot_filter and r.lot_before != lot_filter and r.lot_after != lot_filter:
            continue
        data.append({
            "animal": r.animal,
            "nom_metier": r.nom_metier,
            "lot_actuel": r.lot_before,
            "lot_destination": r.lot_after,
        })
    data.sort(key=lambda x: (lot_sort_key(x["lot_actuel"] or ""), x["nom_metier"] or ""))
    return columns, data


def build_columns(reference_date, date_j_1, date_j_2):
    return [
        {"fieldname": "nom_metier", "label": "N° Travail", "fieldtype": "Data", "width": 90},
        {"fieldname": "lot_actuel", "label": "Lot", "fieldtype": "Link", "options": "Lot", "width": 90},
        {"fieldname": "dim", "label": "Jour Lactation", "fieldtype": "Int", "width": 95},
        {"fieldname": "jours_gestation", "label": "Jour Gestation", "fieldtype": "Int", "width": 95},
        {"fieldname": "j_2", "label": date_j_2.strftime("Tot %d-%b"), "fieldtype": "Float", "precision": 1, "width": 85},
        {"fieldname": "j_1", "label": date_j_1.strftime("Tot %d-%b"), "fieldtype": "Float", "precision": 1, "width": 85},
        {"fieldname": "j", "label": reference_date.strftime("Tot %d-%b"), "fieldtype": "Float", "precision": 1, "width": 85},
        {"fieldname": "delta_j_vs_j_1", "label": "Delta J/J-1", "fieldtype": "Percent", "width": 95},
        {"fieldname": "moyenne_3j", "label": "Moy 3j", "fieldtype": "Float", "precision": 1, "width": 85},
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
            a.etat_lactation,
            a.id_ia_fecondante,
            a.date_velage_prevue,
            MAX(l.date_debut) AS date_debut_lactation,
            MAX(l.numero_lactation) AS numero_lactation,
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
        GROUP BY a.name, a.nom_metier, a.id_lot, a.etat_gestation, a.etat_lactation,
                 a.id_ia_fecondante, a.date_velage_prevue
        ORDER BY MAX(l.date_debut) ASC, a.nom_metier ASC
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
        delta = None
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
                "lot_actuel": r.lot_actuel or "",
                "dim": dim,
                "jours_gestation": jours_gestation,
                "numero_lactation": cint(r.numero_lactation),
                "etat_lactation": r.etat_lactation,
                "etat_gestation": r.etat_gestation,
                "date_velage_prevue": r.date_velage_prevue,
                "j_2": j_2,
                "j_1": j_1,
                "j": j,
                "delta_j_vs_j_1": delta,
                "moyenne_3j": moyenne_3j,
                "suggestion_lot": "",
            }
        )

    _apply_suggestions(data, reference_date)
    return data


@frappe.whitelist()
def get_lots_capacity():
    """Active lots with capacity + HP-adapted flag + seuil prod 3j —
    used by the dialog capacity preview table. Sorted: LOT1..LOTn first
    (numeric), then TARISSEMENT, then TARIE, then the rest alphabetically."""
    lots = frappe.get_all(
        "Lot",
        filters={"actif": 1},
        fields=["name", "lot_type", "nb_animaux",
                "capacite_optimale", "capacite_maximale",
                "adapte_hautes_performances", "seuil_production_3j"],
    )
    return sorted(lots, key=lambda l: lot_sort_key(l.get("name")))


@frappe.whitelist()
def update_lot_seuils(seuils):
    """Persist edited seuils from the Suggestions dialog. `seuils` is a
    JSON dict {lot_name: value}. Empty / invalid → stored as 0 (treated as
    "no seuil" by the consideration logic)."""
    import json
    if isinstance(seuils, str):
        seuils = json.loads(seuils)
    for lot_name, val in seuils.items():
        try:
            v = float(val) if val not in (None, "") else 0.0
        except (TypeError, ValueError):
            v = 0.0
        if v < 0:
            v = 0.0
        frappe.db.set_value("Lot", lot_name, "seuil_production_3j",
                            v, update_modified=False)
    frappe.db.commit()
    return {"updated": len(seuils)}


def _apply_suggestions(data, reference_date):
    # Map lot_type → lot name once, so the suggestion engine just looks up by category.
    by_type = {
        l.lot_type: l.name for l in frappe.get_all(
            "Lot", filters={"actif": 1, "lot_type": ["is", "set"]},
            fields=["name", "lot_type"]
        )
    }

    def find_lot(category):
        return by_type.get(category)

    for row in data:
        suggested = _get_suggestion(row, reference_date, find_lot)
        if suggested and suggested != row.get("lot_actuel"):
            row["suggestion_lot"] = suggested


def _get_suggestion(row, reference_date, find_lot):
    # Tarie → lot tarie (already dried off, waiting for vêlage)
    if row.get("etat_lactation") == "TARIE":
        return find_lot("TARIE")

    # Gestante close to calving → tarissement (dry-off needed)
    if row.get("etat_gestation") == "GESTANTE" and row.get("date_velage_prevue"):
        days_to_calving = cint(date_diff(row["date_velage_prevue"], reference_date))
        tarissement_window = get_config("tarissement_window_jours", default=60)
        if 0 < days_to_calving <= tarissement_window:
            return find_lot("TARISSEMENT")

    # 3. DIM-based
    dim = row.get("dim")
    if dim is None:
        return None

    primipare_cap = get_config("dim_primipare_cap", default=300)
    fv_max = get_config("dim_fv_max_multi", default=30)
    thp_max = get_config("dim_thp_max", default=120)
    hp_max = get_config("dim_hp_max", default=240)
    mp_max = get_config("dim_mp_max", default=305)

    # Primipare: stays in FV for whole lactation, then FP
    if row.get("numero_lactation") == 1:
        return find_lot("FV") if dim <= primipare_cap else find_lot("FP")

    # Multipare
    if dim <= fv_max:
        return find_lot("FV")
    if dim <= thp_max:
        return find_lot("THP")
    if dim <= hp_max:
        return find_lot("HP")
    if dim <= mp_max:
        return find_lot("MP")
    return find_lot("FP")
