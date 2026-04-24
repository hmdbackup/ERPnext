import frappe
from frappe.utils import getdate, today, add_days
from calendar import monthrange

from hmd_agro.hmd_agro.utils.live_state import (
    CATEGORIES, effectif_on_date,
    count_velages, count_naissances, count_avortements_mort_nes,
    count_achats, count_exits, count_changements_cat,
)
from hmd_agro.hmd_agro.utils.import_rapport import read_imported
from hmd_agro.hmd_agro.utils.lot_utils import lot_sort_key
from hmd_agro.hmd_agro.doctype.allotement_history.allotement_history import lot_population_on_date


# Row label → key mapping for imported days. Ordered to match the live report.
_IMPORTED_ROWS = [
    ("Effectif Initial",         "effectif_initial",     True),
    ("Changement Catégorie (+)", "changement_cat_plus",  False),
    ("Changement Catégorie (-)", "changement_cat_minus", False),
    ("Vêlage",                   "velage",               False),
    ("Naissance",                "naissance",            False),
    ("Avortement / Mort-né",     "avortement_mort_ne",   False),
    ("Achat",                    "achat",                False),
    ("Vente (Quantité)",         "vente_qty",            False),
    ("Vente (Prix DT)",          "vente_prix",           False),
    ("Mortalité",                "mortalite",            False),
    ("Réforme",                  "reforme",              False),
    ("Effectif Final",           "effectif_final",       True),
]


def execute(filters=None):
    filters = filters or {}
    date = getdate(filters.get("date") or today())
    section = filters.get("section") or "Tout"

    nb_jours = monthrange(date.year, date.month)[1]
    date_debut = getdate(f"{date.year}-{date.month:02d}-01")
    date_fin = getdate(f"{date.year}-{date.month:02d}-{nb_jours}")

    ctx = {"date_filter": date, "date_debut": date_debut,
           "date_fin": date_fin, "nb_jours": nb_jours}

    builders = {
        "Effectif": _effectif,
        "Production": _production,
        "Production par Lot": _production_lot,
        "Alimentation": _alimentation,
        "Indicateurs": _indicateurs,
    }
    return builders.get(section, _tout)(ctx)


# ─── Effectif ────────────────────────────────────────────────────────────────

def _effectif(ctx):
    """Per-day Effectif table — live from event doctypes, imported fallback."""
    columns = [{"fieldname": "ligne", "label": "", "fieldtype": "Data", "width": 180}]
    for cat in CATEGORIES:
        columns.append({"fieldname": cat, "label": cat, "fieldtype": "Int", "width": 100})

    date = ctx["date_filter"]

    imp = read_imported(date)
    if imp:
        return columns, [_row(label, imp.get(key, {}), is_total)
                         for label, key, is_total in _IMPORTED_ROWS]

    if getdate(date) > getdate(today()):
        return columns, [_gap_row("Pas encore de données pour cette date.")]

    initial = effectif_on_date(add_days(date, -1))
    final = effectif_on_date(date)
    cat_plus, cat_minus = count_changements_cat(date)
    vente_qty, vente_prix = count_exits(date, "VENDU")
    mortalite, _ = count_exits(date, "MORT")
    reforme, _ = count_exits(date, "REFORME")

    rows = [
        ("Effectif Initial",         initial,                          True),
        ("Changement Catégorie (+)", cat_plus,                         False),
        ("Changement Catégorie (-)", cat_minus,                        False),
        ("Vêlage",                   count_velages(date),              False),
        ("Naissance",                count_naissances(date),           False),
        ("Avortement / Mort-né",     count_avortements_mort_nes(date), False),
        ("Achat",                    count_achats(date),               False),
        ("Vente (Quantité)",         vente_qty,                        False),
        ("Vente (Prix DT)",          vente_prix,                       False),
        ("Mortalité",                mortalite,                        False),
        ("Réforme",                  reforme,                          False),
        ("Effectif Final",           final,                            True),
    ]
    return columns, [_row(label, values, is_total) for label, values, is_total in rows]


def _row(label, values, is_total):
    return {"ligne": label, "is_total": is_total,
            **{cat: values.get(cat, 0) for cat in CATEGORIES}}


def _gap_row(msg):
    return {"ligne": msg, "is_total": True, **{cat: None for cat in CATEGORIES}}


# ─── Production ──────────────────────────────────────────────────────────────

def _production(ctx):
    columns = [
        {"fieldname": "jour", "label": "Jour", "fieldtype": "Int", "width": 60},
        {"fieldname": "nb_lactantes", "label": "VL", "fieldtype": "Int", "width": 60},
        {"fieldname": "production", "label": "Production (L)", "fieldtype": "Float", "precision": 1, "width": 110},
        {"fieldname": "moyenne", "label": "Moy/VL (L)", "fieldtype": "Float", "precision": 1, "width": 100},
        {"fieldname": "taux_tb", "label": "TB (%)", "fieldtype": "Float", "precision": 2, "width": 80},
        {"fieldname": "taux_tp", "label": "TP (%)", "fieldtype": "Float", "precision": 2, "width": 80},
        {"fieldname": "commercialise", "label": "Commercialisé (L)", "fieldtype": "Float", "precision": 1, "width": 120},
    ]

    daily = frappe.db.sql("""
        SELECT DAY(date_traite) AS jour,
            SUM(quantite_litres) AS prod,
            AVG(NULLIF(taux_tb, 0)) AS tb,
            AVG(NULLIF(taux_tp, 0)) AS tp
        FROM `tabTraite`
        WHERE date_traite BETWEEN %s AND %s
        GROUP BY DAY(date_traite)
    """, (ctx["date_debut"], ctx["date_fin"]), as_dict=True)

    daily_map = {d.jour: d for d in daily}

    # Per-day historical lactating-cow count (reconstructed from events)
    vl_by_day = {
        j: effectif_on_date(add_days(ctx["date_debut"], j - 1))["Vaches - Lact."]
        for j in range(1, ctx["nb_jours"] + 1)
    }
    total_cow_days = sum(vl_by_day.values())
    nb_vl_end = vl_by_day[ctx["nb_jours"]]

    data = []
    total_prod = 0
    for j in range(1, ctx["nb_jours"] + 1):
        d = daily_map.get(j, {})
        prod = float(d.get("prod") or 0)
        total_prod += prod
        nb_vl = vl_by_day[j]
        data.append({
            "jour": j, "nb_lactantes": nb_vl,
            "production": round(prod, 1),
            "moyenne": round(prod / nb_vl, 1) if nb_vl and prod else 0,
            "taux_tb": round(float(d.get("tb") or 0), 2) or None,
            "taux_tp": round(float(d.get("tp") or 0), 2) or None,
            "commercialise": None,
        })

    data.append({
        "jour": None, "is_total": 1, "nb_lactantes": nb_vl_end,
        "production": round(total_prod, 1),
        "moyenne": round(total_prod / total_cow_days, 1) if total_cow_days else 0,
    })

    chart = {
        "data": {
            "labels": [str(j) for j in range(1, ctx["nb_jours"] + 1)],
            "datasets": [{"name": "Production (L)", "values": [
                float(daily_map.get(j, {}).get("prod") or 0) for j in range(1, ctx["nb_jours"] + 1)
            ]}]
        },
        "type": "bar", "colors": ["#4299e1"]
    }

    return columns, data, None, chart


# ─── Production par Lot ──────────────────────────────────────────────────────

def _production_lot(ctx):
    """4-row table: Effectif (D), D-1 production, D production, Moyenne (D).
    Effectif and production are historical (frozen via Traite.id_lot at save time).
    Sources: Rapport Journalier Importe (imported) or Traite.id_lot (live)."""
    date = ctx["date_filter"]
    prev_date = add_days(date, -1)

    imp = read_imported(date)
    if imp and imp.get("production_lot"):
        return _render_imported_lot(imp, date, prev_date)
    return _render_live_lot(date, prev_date)


def _render_imported_lot(imp, date, prev_date):
    lot_data = imp["production_lot"]
    # Try to also fetch D-1's import so the prev-day production row isn't always blank.
    prev_imp = read_imported(prev_date)
    prev_prod = (prev_imp or {}).get("production_lot") or {}

    lots = sorted(set(lot_data) | set(prev_prod), key=lot_sort_key)
    columns = _lot_columns(lots)
    total_eff = sum(lot_data.get(lot, {}).get("effectif", 0) for lot in lots)
    total_prod = sum(lot_data.get(lot, {}).get("production", 0) for lot in lots)

    rows = [
        {"jour": "Effectif", "is_total": True, "total": total_eff,
         **{lot: lot_data.get(lot, {}).get("effectif", 0) or None for lot in lots}},
        {"jour": prev_date.strftime("%d/%m"),
         **{lot: prev_prod.get(lot, {}).get("production", 0) or None for lot in lots},
         "total": sum(prev_prod.get(lot, {}).get("production", 0) for lot in lots) or None},
        {"jour": date.strftime("%d/%m"),
         **{lot: lot_data.get(lot, {}).get("production", 0) or None for lot in lots},
         "total": total_prod or None},
        {"jour": "Moyenne / lot", "is_total": True,
         **{lot: _safe_div(lot_data.get(lot, {}).get("production", 0),
                           lot_data.get(lot, {}).get("effectif", 0)) for lot in lots},
         "total": _safe_div(total_prod, total_eff)},
    ]
    return columns, rows


def _render_live_lot(date, prev_date):
    prod_curr = _traite_by_lot(date)
    prod_prev = _traite_by_lot(prev_date)
    eff_curr = _lactantes_by_lot_on_date(date)

    # Always include all currently-lactating lots, plus any historical lots
    # that appear in D-1/D data (handles renamed lots gracefully). prod_curr
    # and eff_curr share the same Traite filters, so their key sets match.
    lots = sorted(set(_active_lactating_lots()) | set(prod_curr) | set(prod_prev),
                  key=lot_sort_key)
    columns = _lot_columns(lots)
    total_eff = sum(eff_curr.values())
    total_prod = sum(prod_curr.values())

    rows = [
        {"jour": "Effectif", "is_total": True, "total": total_eff,
         **{lot: eff_curr.get(lot, 0) or None for lot in lots}},
        _lot_day_row(prev_date.strftime("%d/%m"), lots, prod_prev),
        _lot_day_row(date.strftime("%d/%m"), lots, prod_curr),
        {"jour": "Moyenne / lot", "is_total": True,
         **{lot: _safe_div(prod_curr.get(lot, 0), eff_curr.get(lot, 0)) for lot in lots},
         "total": _safe_div(total_prod, total_eff)},
    ]
    return columns, rows


def _active_lactating_lots():
    """Distinct lots with at least one currently-lactating cow."""
    return [r[0] for r in frappe.db.sql("""
        SELECT DISTINCT id_lot FROM `tabAnimal`
        WHERE statut = 'ACTIF' AND etat_lactation = 'EN_PRODUCTION'
          AND id_lot IS NOT NULL AND id_lot != ''
    """)]


def _traite_by_lot(date):
    """Production per lot using Traite.id_lot (stamped at save time)."""
    rows = frappe.db.sql("""
        SELECT id_lot AS lot, SUM(quantite_litres) AS litres
        FROM `tabTraite`
        WHERE date_traite = %s AND id_lot IS NOT NULL AND id_lot != ''
        GROUP BY id_lot
    """, str(date), as_dict=True)
    return {r.lot: round(float(r.litres or 0), 1) for r in rows}


def _lactantes_by_lot_on_date(date):
    """Historical lactantes count per lot for `date`, derived from Traite.id_lot
    (frozen at save time). Counts distinct animals milked per lot that day."""
    rows = frappe.db.sql("""
        SELECT id_lot AS lot, COUNT(DISTINCT animal) AS n
        FROM `tabTraite`
        WHERE date_traite = %s AND id_lot IS NOT NULL AND id_lot != ''
        GROUP BY id_lot
    """, str(date), as_dict=True)
    return {r.lot: int(r.n) for r in rows}


def _lot_columns(lots):
    cols = [{"fieldname": "jour", "label": "", "fieldtype": "Data", "width": 100}]
    for lot in lots:
        cols.append({"fieldname": lot, "label": lot, "fieldtype": "Float", "precision": 1, "width": 100})
    cols.append({"fieldname": "total", "label": "Total", "fieldtype": "Float", "precision": 1, "width": 100})
    return cols


def _lot_day_row(label, lots, prod_map):
    total = sum(prod_map.get(lot, 0) for lot in lots)
    return {"jour": label,
            **{lot: prod_map.get(lot, 0) or None for lot in lots},
            "total": round(total, 1) or None}


def _safe_div(num, den):
    return round(num / den, 1) if den else None


# ─── Alimentation ────────────────────────────────────────────────────────────

def _aliment_data_per_lot(date_debut, date_filter):
    """Per-day per-lot historical reconstruction shared by _alimentation and
    _indicateurs. Walks each day from date_debut → date_filter and returns:
        active_lots:                   list of all active lot names
        daily_qty:                     {(aliment, lot): kg distributed on date_filter}
        daily_ms:                      {lot: kg MS on date_filter}
        daily_pop:                     {lot: pop on date_filter}
        cumulative_qty:                {aliment: cheptel-wide kg over period}
        cumulative_concentre_cheptel:  kg of CONCENTRE-type aliments over period
        cumulative_ms_cheptel:         kg MS over period
        cumulative_cow_days_cheptel:   cow-days over period
        aliment_ms_pct:                {aliment: ms_pct fraction}
        aliment_type:                  {aliment: type_aliment string}
        lots_with_data:                lots with data on date_filter
    Returns None if no active lots.
    """
    active_lots = frappe.get_all("Lot", filters={"actif": 1},
                                 fields=["name"], order_by="name")
    if not active_lots:
        return None

    lot_names_all = [l.name for l in active_lots]
    days_in_period = (date_filter - date_debut).days + 1
    days = [add_days(date_debut, i) for i in range(days_in_period)]

    # Pre-fetch all ration history for active lots (1 query).
    history = {}
    for r in frappe.db.sql("""
        SELECT lot, to_ration, DATE(creation) AS dt
        FROM `tabLot Ration History`
        WHERE lot IN %s
        ORDER BY creation ASC
    """, (lot_names_all,), as_dict=True):
        history.setdefault(r.lot, []).append((r.dt, r.to_ration))

    current_ration = {l.name: frappe.db.get_value("Lot", l.name, "id_ration_actuelle")
                      for l in active_lots}

    def ration_for(lot, day):
        for dt, rat in reversed(history.get(lot, [])):
            if dt <= day:
                return rat
        return current_ration.get(lot)

    comp_cache = {}
    def composition(ration):
        if ration in comp_cache:
            return comp_cache[ration]
        rows = frappe.db.sql("""
            SELECT c.aliment, c.quantite, a.ms_pct, a.type_aliment
            FROM `tabComposition Ration` c JOIN `tabAliment` a ON c.aliment = a.name
            WHERE c.parent = %s
        """, ration, as_dict=True) if ration else []
        comp_cache[ration] = rows
        return rows

    daily_qty = {}
    daily_ms = {}
    daily_pop = {}
    cumulative_qty = {}
    cumulative_concentre_cheptel = 0
    cumulative_ms_cheptel = 0
    cumulative_cow_days_cheptel = 0
    aliment_ms_pct = {}
    aliment_type = {}
    lots_with_data = set()

    for day in days:
        pop = lot_population_on_date(day)
        is_filter_day = (day == date_filter)
        for lot in lot_names_all:
            n_pop = pop.get(lot, 0)
            if n_pop == 0:
                continue
            cumulative_cow_days_cheptel += n_pop
            ration = ration_for(lot, day)
            if not ration:
                continue
            for c in composition(ration):
                aliment = c.aliment
                ms_pct = float(c.ms_pct or 0)
                aliment_ms_pct[aliment] = ms_pct
                aliment_type[aliment] = c.type_aliment
                day_qty = float(c.quantite or 0) * n_pop
                day_ms = day_qty * ms_pct
                cumulative_qty[aliment] = cumulative_qty.get(aliment, 0) + day_qty
                cumulative_ms_cheptel += day_ms
                if c.type_aliment == "CONCENTRE":
                    cumulative_concentre_cheptel += day_qty
                if is_filter_day:
                    daily_qty[(aliment, lot)] = daily_qty.get((aliment, lot), 0) + day_qty
                    daily_ms[lot] = daily_ms.get(lot, 0) + day_ms
                    daily_pop[lot] = n_pop
                    lots_with_data.add(lot)

    return {
        "active_lots": lot_names_all,
        "daily_qty": daily_qty,
        "daily_ms": daily_ms,
        "daily_pop": daily_pop,
        "cumulative_qty": cumulative_qty,
        "cumulative_concentre_cheptel": cumulative_concentre_cheptel,
        "cumulative_ms_cheptel": cumulative_ms_cheptel,
        "cumulative_cow_days_cheptel": cumulative_cow_days_cheptel,
        "aliment_ms_pct": aliment_ms_pct,
        "aliment_type": aliment_type,
        "lots_with_data": lots_with_data,
    }


def _alimentation(ctx):
    # Cells = daily snapshot at date_filter (kg distributed today).
    # Cumulé column = cheptel-wide running total per aliment, date_debut → date_filter.
    date_debut = ctx["date_debut"]
    date_filter = min(ctx["date_filter"], ctx["date_fin"])
    d = _aliment_data_per_lot(date_debut, date_filter)
    if d is None:
        return [{"fieldname": "msg", "label": "", "fieldtype": "Data", "width": 300}], \
               [{"msg": "Aucun lot actif."}]
    if not d["lots_with_data"]:
        return [{"fieldname": "msg", "label": "", "fieldtype": "Data", "width": 300}], \
               [{"msg": "Aucun lot avec ration assignée à cette date."}]

    lot_names = sorted(d["lots_with_data"], key=lot_sort_key)
    period_label = f"Cumulé {date_debut.strftime('%d/%m')} → {date_filter.strftime('%d/%m')}"

    columns = [
        {"fieldname": "aliment", "label": "Aliment", "fieldtype": "Data", "width": 180},
        {"fieldname": "ms_pct", "label": "MS%", "fieldtype": "Percent", "width": 80},
    ]
    for lot in lot_names:
        columns.append({"fieldname": lot, "label": lot, "fieldtype": "Float", "precision": 2, "width": 100})
    columns.append({"fieldname": "cumule", "label": period_label, "fieldtype": "Float", "precision": 2, "width": 160})

    data = []
    for aliment in sorted(set(a for a, _ in d["daily_qty"]) | set(d["cumulative_qty"])):
        # ms_pct stored as fraction (0.86) — multiply by 100 for the % column display.
        row = {"aliment": aliment, "ms_pct": d["aliment_ms_pct"].get(aliment, 0) * 100}
        for lot in lot_names:
            v = d["daily_qty"].get((aliment, lot), 0)
            row[lot] = round(v, 2) if v else None
        cum = d["cumulative_qty"].get(aliment, 0)
        row["cumule"] = round(cum, 2) if cum else None
        data.append(row)

    ms_total_row = {"aliment": "MS Total Distribué", "ms_pct": None, "is_total": True}
    for lot in lot_names:
        v = d["daily_ms"].get(lot, 0)
        ms_total_row[lot] = round(v, 2) if v else None
    ms_total_row["cumule"] = round(d["cumulative_ms_cheptel"], 2) if d["cumulative_ms_cheptel"] else None
    data.append(ms_total_row)

    ms_tete_row = {"aliment": "MS Distribué/Tête", "ms_pct": None, "is_total": True}
    for lot in lot_names:
        nb = d["daily_pop"].get(lot, 0)
        ms_tete_row[lot] = round(d["daily_ms"].get(lot, 0) / nb, 2) if nb else None
    ms_tete_row["cumule"] = (round(d["cumulative_ms_cheptel"] / d["cumulative_cow_days_cheptel"], 2)
                             if d["cumulative_cow_days_cheptel"] else None)
    data.append(ms_tete_row)

    # Production: cells use date_filter only; cumulé uses date_debut → date_filter cheptel-wide.
    prod_daily = frappe.db.sql("""
        SELECT id_lot, SUM(quantite_litres) AS prod
        FROM `tabTraite`
        WHERE date_traite = %s AND id_lot IN %s
        GROUP BY id_lot
    """, (date_filter, lot_names), as_dict=True)
    prod_per_lot_daily = {p.id_lot: float(p.prod or 0) for p in prod_daily}

    cum_milk = frappe.db.sql("""
        SELECT SUM(quantite_litres) FROM `tabTraite`
        WHERE date_traite BETWEEN %s AND %s
    """, (date_debut, date_filter))[0][0] or 0
    cumulative_milk_cheptel = float(cum_milk)

    eff_row = {"aliment": "Efficacité alimentaire L/Kg MS", "ms_pct": None, "is_total": True}
    for lot in lot_names:
        ms = d["daily_ms"].get(lot, 0)
        milk = prod_per_lot_daily.get(lot, 0)
        eff_row[lot] = round(milk / ms, 2) if ms else None
    eff_row["cumule"] = (round(cumulative_milk_cheptel / d["cumulative_ms_cheptel"], 2)
                         if d["cumulative_ms_cheptel"] else None)
    data.append(eff_row)

    return columns, data


# ─── Indicateurs ─────────────────────────────────────────────────────────────

def _indicateurs(ctx):
    """Flat KPI list. Vache counts = snapshot @ date_filter (reconstructed from
    events). Production / Concentré / MS = cumulative date_debut → date_filter
    (per-day historical reconstruction; no phantom future days). Reproduction
    metrics (IA, vêlages) live in their own report. Cost metrics deferred until
    Stock/Finance integration."""
    columns = [
        {"fieldname": "indicateur", "label": "Indicateur", "fieldtype": "Data", "width": 280},
        {"fieldname": "valeur", "label": "Valeur", "fieldtype": "Float", "precision": 2, "width": 120},
        {"fieldname": "unite", "label": "Unité", "fieldtype": "Data", "width": 140},
    ]

    date_debut = ctx["date_debut"]
    date_filter = min(ctx["date_filter"], ctx["date_fin"])

    # End-of-period reconstructed snapshot
    eff = effectif_on_date(date_filter)
    vl = eff["Vaches - Lact."]
    vt = eff["Vaches - Tarie"]
    vp = vl + vt

    # Cumulative production (cap at date_filter, no phantom future days)
    prod = float(frappe.db.sql("""
        SELECT SUM(quantite_litres) FROM `tabTraite`
        WHERE date_traite BETWEEN %s AND %s
    """, (date_debut, date_filter))[0][0] or 0)

    # Reuse per-day historical reconstruction for concentré + MS
    d = _aliment_data_per_lot(date_debut, date_filter)
    concentre = d["cumulative_concentre_cheptel"] if d else 0
    ms_total = d["cumulative_ms_cheptel"] if d else 0

    period = f"{date_debut.strftime('%d/%m')} → {date_filter.strftime('%d/%m')}"

    data = [
        {"indicateur": f"Vaches Présentes (au {date_filter.strftime('%d/%m')})",
         "valeur": vp, "unite": "têtes"},
        {"indicateur": f"Vaches Lactantes (au {date_filter.strftime('%d/%m')})",
         "valeur": vl, "unite": "têtes"},
        {"indicateur": f"Vaches Taries (au {date_filter.strftime('%d/%m')})",
         "valeur": vt, "unite": "têtes"},
        {"indicateur": f"Production Totale ({period})",
         "valeur": round(prod, 1), "unite": "L"},
        {"indicateur": "Moyenne Production / Vache Présente",
         "valeur": round(prod / vp, 1) if vp else 0, "unite": "L/tête"},
        {"indicateur": "Moyenne Production / Vache Lactante",
         "valeur": round(prod / vl, 1) if vl else 0, "unite": "L/tête"},
        {"indicateur": f"Concentré Total ({period})",
         "valeur": round(concentre, 1), "unite": "kg"},
        {"indicateur": "Concentré / Vache Présente",
         "valeur": round(concentre / vp, 2) if vp else 0, "unite": "kg/tête"},
        {"indicateur": "Concentré / Vache Lactante",
         "valeur": round(concentre / vl, 2) if vl else 0, "unite": "kg/tête"},
        {"indicateur": "L/C (Efficacité production)",
         "valeur": round(prod / concentre, 2) if concentre else 0, "unite": "L/kg"},
        {"indicateur": "C/L (Concentré par L)",
         "valeur": round(concentre / prod, 3) if prod else 0, "unite": "kg/L"},
        {"indicateur": "Efficacité Alimentaire (sur MS)",
         "valeur": round(prod / ms_total, 2) if ms_total else 0, "unite": "L/kg MS"},
        # Cost section deferred until Stock/Finance integration
        {"indicateur": "Frais Concentré", "valeur": None, "unite": "DT (à intégrer)"},
        {"indicateur": "Frais Fourrage", "valeur": None, "unite": "DT (à intégrer)"},
        {"indicateur": "Coût Alimentaire / L", "valeur": None, "unite": "DT/L (à intégrer)"},
        {"indicateur": "Main d'Œuvre", "valeur": None, "unite": "DT (à intégrer)"},
        {"indicateur": "Chiffre d'Affaires Lait", "valeur": None, "unite": "DT (à intégrer)"},
    ]

    return columns, data


# ─── Tout ────────────────────────────────────────────────────────────────────

def _tout(ctx):
    columns = [
        {"fieldname": "label", "label": "", "fieldtype": "Data", "width": 280},
        {"fieldname": "valeur", "label": "Valeur", "fieldtype": "Data", "width": 150},
    ]

    _, eff_data = _effectif(ctx)[:2]
    _, prod_data = _production(ctx)[:2]
    _, ind_data = _indicateurs(ctx)[:2]

    data = []

    data.append({"label": "── EFFECTIF ──", "valeur": "", "is_header": 1})
    for row in eff_data:
        data.append({"label": row["ligne"], "valeur": str(row.get("Total", 0)), "is_total": row.get("is_total")})

    data.append({"label": "── PRODUCTION ──", "valeur": "", "is_header": 1})
    total = prod_data[-1] if prod_data else {}
    data.append({"label": "Production totale mois", "valeur": f"{total.get('production', 0)} L"})
    data.append({"label": "Moy/VL/Jour", "valeur": f"{total.get('moyenne', 0)} L"})

    data.append({"label": "── INDICATEURS ──", "valeur": "", "is_header": 1})
    for row in ind_data:
        val = row.get("valeur")
        unite = row.get("unite") or ""
        data.append({"label": row["indicateur"], "valeur": f"{val} {unite}" if val is not None else unite})

    return columns, data
