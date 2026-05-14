import frappe
from frappe.utils import getdate, today, add_days, add_months
from calendar import monthrange

from hmd_agro.hmd_agro.utils.live_state import (
    CATEGORIES, effectif_on_date, lactantes_per_lot_on_date,
    empty_row, set_total,
    count_velages, count_naissances, count_avortements_mort_nes,
    count_achats, count_exits, count_changements_cat,
)
from hmd_agro.hmd_agro.utils.import_rapport import read_imported
from hmd_agro.hmd_agro.utils.lot_utils import lot_sort_key
from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.report_format import normalize_precision


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


@normalize_precision
def execute(filters=None):
    filters = filters or {}
    date = getdate(filters.get("date") or today())
    section = filters.get("section") or "Tout"
    # Granularité only affects _alimentation. UI default is Quinzaine; the
    # _alimentation function itself defaults to Quotidien when ctx omits the
    # key, so direct callers (tests, _bilan_annuel) keep their old behavior.
    granularite = filters.get("granularite") or "Quinzaine"
    # Effectif mode: Jour (default) shows that single day's events; Mois
    # aggregates events from date_debut through date_filter (or end of month).
    # Toggled by the "État du Mois" button on the report page.
    effectif_mode = filters.get("effectif_mode") or "Jour"
    # Période: Jour (default — D vs D-1) or Hebdomadaire (sem prév vs sem act
    # rolling 7-day windows ending at date_filter). Production par Lot only.
    periode = filters.get("periode") or "Jour"

    nb_jours = monthrange(date.year, date.month)[1]
    date_debut = getdate(f"{date.year}-{date.month:02d}-01")
    date_fin = getdate(f"{date.year}-{date.month:02d}-{nb_jours}")

    ctx = {"date_filter": date, "date_debut": date_debut,
           "date_fin": date_fin, "nb_jours": nb_jours,
           "granularite": granularite, "effectif_mode": effectif_mode,
           "periode": periode}

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
    """Effectif table — live from event doctypes (Jour mode = single-day events,
    Mois mode = aggregated month-to-date events). Imported fallback only used
    in Jour mode (each import is per-day, no aggregation across imports)."""
    columns = [{"fieldname": "ligne", "label": "", "fieldtype": "Data", "width": 180}]
    for cat in CATEGORIES:
        columns.append({"fieldname": cat, "label": cat, "fieldtype": "Int", "width": 100})

    date = ctx["date_filter"]
    mode = ctx.get("effectif_mode") or "Jour"

    if mode == "Jour":
        imp = read_imported(date)
        if imp:
            return columns, [_row(label, imp.get(key, {}), is_total)
                             for label, key, is_total in _IMPORTED_ROWS]

    if getdate(date) > getdate(today()):
        return columns, [_gap_row("Pas encore de données pour cette date.")]

    if mode == "Mois":
        return columns, _effectif_mois(ctx)

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


def _shift_minus_one_month(d):
    """Shift `d` back by one month. If `d` is the last day of its month, snap
    the result to the last day of the previous month — so that comparing a
    full 31-day month against M-1 covers the same number of days.

    `add_months` alone clamps the day to whatever fits, but doesn't extend.
    Example: add_months(2026-04-30, -1) = 2026-03-30 (drops March 31).
    With this helper: 2026-04-30 → 2026-03-31 (full month preserved)."""
    shifted = add_months(d, -1)
    if d.day == monthrange(d.year, d.month)[1]:
        last_of_prev = monthrange(shifted.year, shifted.month)[1]
        return shifted.replace(day=last_of_prev)
    return shifted


def _sum_rows(*rows):
    """Sum a sequence of category-keyed dicts (output of count_* helpers).
    Re-computes the Total field from the categories so it stays consistent."""
    out = empty_row()
    for r in rows:
        for cat in CATEGORIES:
            if cat == "Total":
                continue
            out[cat] = out.get(cat, 0) + (r.get(cat, 0) or 0)
    set_total(out)
    return out


def _effectif_mois(ctx):
    """Aggregate Effectif events for the calendar month of date_filter.

    End of aggregation window is determined by whether we're in the current
    calendar month or a past one:
      - Current month  → capped at today (the month is in progress, so we
                          only count events that have actually happened).
      - Past month     → end of that month (date_fin), regardless of where
                          the user's date cursor is. The month is complete.
    Effectif Initial = state at date_debut - 1 day (= last day of previous month).
    Effectif Final   = state at the end of the aggregation window.
    """
    date_debut = getdate(ctx["date_debut"])
    today_dt = getdate(today())
    date_filter = getdate(ctx["date_filter"])
    if date_filter.year == today_dt.year and date_filter.month == today_dt.month:
        end = today_dt
    else:
        end = getdate(ctx["date_fin"])

    cat_plus = empty_row()
    cat_minus = empty_row()
    velages = empty_row()
    naissances = empty_row()
    avortements = empty_row()
    achats = empty_row()
    vente_qty = empty_row()
    vente_prix = empty_row()
    mortalite = empty_row()
    reforme = empty_row()

    d = date_debut
    while d <= end:
        cp, cm = count_changements_cat(d)
        cat_plus = _sum_rows(cat_plus, cp)
        cat_minus = _sum_rows(cat_minus, cm)
        velages = _sum_rows(velages, count_velages(d))
        naissances = _sum_rows(naissances, count_naissances(d))
        avortements = _sum_rows(avortements, count_avortements_mort_nes(d))
        achats = _sum_rows(achats, count_achats(d))
        vq, vp = count_exits(d, "VENDU")
        vente_qty = _sum_rows(vente_qty, vq)
        vente_prix = _sum_rows(vente_prix, vp)
        mq, _ = count_exits(d, "MORT")
        mortalite = _sum_rows(mortalite, mq)
        rq, _ = count_exits(d, "REFORME")
        reforme = _sum_rows(reforme, rq)
        d = add_days(d, 1)

    initial = effectif_on_date(add_days(date_debut, -1))
    final = effectif_on_date(end)

    rows = [
        ("Effectif Initial",         initial,     True),
        ("Changement Catégorie (+)", cat_plus,    False),
        ("Changement Catégorie (-)", cat_minus,   False),
        ("Vêlage",                   velages,     False),
        ("Naissance",                naissances,  False),
        ("Avortement / Mort-né",     avortements, False),
        ("Achat",                    achats,      False),
        ("Vente (Quantité)",         vente_qty,   False),
        ("Vente (Prix DT)",          vente_prix,  False),
        ("Mortalité",                mortalite,   False),
        ("Réforme",                  reforme,     False),
        ("Effectif Final",           final,       True),
    ]
    return [_row(label, values, is_total) for label, values, is_total in rows]


def _row(label, values, is_total):
    return {"ligne": label, "is_total": is_total,
            **{cat: values.get(cat, 0) for cat in CATEGORIES}}


def _gap_row(msg):
    return {"ligne": msg, "is_total": True, **{cat: None for cat in CATEGORIES}}


def _is_future(ctx):
    """True if the report's date is strictly after today."""
    return getdate(ctx["date_filter"]) > getdate(today())


def _future_stub(extras=()):
    """Standard 'no data — future date' return for any section.
    Returns (columns, rows[, *extras]) with extras as None/[] padding so
    sections that include chart/summary still get a valid tuple shape."""
    cols = [{"fieldname": "msg", "label": "Information",
             "fieldtype": "Data", "width": 400}]
    rows = [{"msg": "Pas encore de données pour cette date."}]
    return (cols, rows) + tuple(extras)


# ─── Production ──────────────────────────────────────────────────────────────

def _production(ctx):
    columns = [
        {"fieldname": "jour", "label": "Jour", "fieldtype": "Data", "width": 60},
        {"fieldname": "nb_lactantes", "label": "VL", "fieldtype": "Int", "width": 60},
        {"fieldname": "production", "label": "Production (L)", "fieldtype": "Float", "precision": 1, "width": 110},
        {"fieldname": "moyenne", "label": "Moy/VL (L)", "fieldtype": "Float", "precision": 1, "width": 100},
        {"fieldname": "taux_tb", "label": "TB", "fieldtype": "Percent", "precision": 2, "width": 80},
        {"fieldname": "taux_tp", "label": "TP", "fieldtype": "Percent", "precision": 2, "width": 80},
        {"fieldname": "commercialise", "label": "Commercialisé (L)", "fieldtype": "Float", "precision": 1, "width": 120},
    ]

    if _is_future(ctx):
        return _future_stub((None, None))

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

    # Quinzaine/Hebdomadaire summary rows (kg + L/VL/jour per period). Spans
    # past today are skipped so an in-progress month only shows filled periods.
    granularite = ctx.get("granularite") or "Quotidien"
    today_dt = getdate(today())
    for label, start, end in _build_period_spans(granularite, ctx["date_debut"], ctx["nb_jours"]):
        span_end = min(end, today_dt)
        if span_end < start:
            continue
        sp_prod = 0.0
        sp_cow_days = 0
        d = start
        while d <= span_end:
            sp_prod += float(daily_map.get(d.day, {}).get("prod") or 0)
            sp_cow_days += vl_by_day.get(d.day, 0)
            d = add_days(d, 1)
        data.append({
            "jour": label, "is_total": 1, "tint": "orange",
            "production": round(sp_prod, 1),
            "moyenne": round(sp_prod / sp_cow_days, 1) if sp_cow_days else 0,
        })

    data.append({
        "jour": "Total", "is_total": 1, "nb_lactantes": nb_vl_end,
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
    """Lot table. Two modes via ctx["periode"]:
      Jour          — 4 rows: Effectif (D), D-1, D, Moyenne. Imported priority.
      Hebdomadaire  — 5 rows: Effectif (D), Sem. préc., Sem. act., Δ %, Moy/lact/jour.
                       Live data only (mixing imported/live across rolling
                       windows would be incoherent — daily mode keeps imports).
    Effectif and production are historical (frozen via Traite.id_lot at save time)."""
    if _is_future(ctx):
        return _future_stub()

    date = ctx["date_filter"]

    if ctx.get("periode") == "Hebdomadaire":
        return _render_live_lot_weekly(date)

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

    total_prev_prod = sum(prev_prod.get(lot, {}).get("production", 0) for lot in lots)
    rows = [
        {"jour": "Effectif", "is_total": True, "total": total_eff,
         **{lot: lot_data.get(lot, {}).get("effectif", 0) or None for lot in lots}},
        {"jour": prev_date.strftime("%d/%m"),
         **{lot: prev_prod.get(lot, {}).get("production", 0) or None for lot in lots},
         "total": total_prev_prod or None},
        {"jour": date.strftime("%d/%m"),
         **{lot: lot_data.get(lot, {}).get("production", 0) or None for lot in lots},
         "total": total_prod or None},
        {"jour": "Δ % (J vs J-1)", "is_total": True, "is_delta": True,
         **{lot: _delta_pct(lot_data.get(lot, {}).get("production", 0),
                            prev_prod.get(lot, {}).get("production", 0)) for lot in lots},
         "total": _delta_pct(total_prod, total_prev_prod)},
        {"jour": "Moyenne / lot", "is_total": True,
         **{lot: _safe_div(lot_data.get(lot, {}).get("production", 0),
                           lot_data.get(lot, {}).get("effectif", 0)) for lot in lots},
         "total": _safe_div(total_prod, total_eff)},
    ]
    return columns, rows


def _render_live_lot(date, prev_date):
    prod_curr = _traite_by_lot(date)
    prod_prev = _traite_by_lot(prev_date)
    eff_curr = lactantes_per_lot_on_date(date)

    # Always include all currently-lactating lots, plus any historical lots
    # that appear in D-1/D data (handles renamed lots gracefully). prod_curr
    # and eff_curr share the same Traite filters, so their key sets match.
    lots = sorted(set(_active_lactating_lots()) | set(prod_curr) | set(prod_prev),
                  key=lot_sort_key)
    columns = _lot_columns(lots)
    total_eff = sum(eff_curr.values())
    total_prod = sum(prod_curr.values())

    total_prev = sum(prod_prev.values())
    rows = [
        {"jour": "Effectif", "is_total": True, "total": total_eff,
         **{lot: eff_curr.get(lot, 0) or None for lot in lots}},
        _lot_day_row(prev_date.strftime("%d/%m"), lots, prod_prev),
        _lot_day_row(date.strftime("%d/%m"), lots, prod_curr),
        {"jour": "Δ % (J vs J-1)", "is_total": True, "is_delta": True,
         **{lot: _delta_pct(prod_curr.get(lot, 0), prod_prev.get(lot, 0)) for lot in lots},
         "total": _delta_pct(total_prod, total_prev)},
        {"jour": "Moyenne / lot", "is_total": True,
         **{lot: _safe_div(prod_curr.get(lot, 0), eff_curr.get(lot, 0)) for lot in lots},
         "total": _safe_div(total_prod, total_eff)},
    ]
    return columns, rows


def _render_live_lot_weekly(date):
    """Hebdomadaire mode for Production par Lot. Two window strategies:

    Past month — uses _build_period_spans S1..S4 chunks, same as Alimentation
    and Production Hebdomadaire summary rows. 'Sem. act.' is the chunk
    containing the cursor; 'Sem. préc.' is the chunk just before in time
    (same month if cursor is in S2/S3/S4, previous month's S4 if cursor is in
    S1). One Hebdomadaire definition app-wide.

    Current month — rolling 7-day ending at cursor. We have no future data to
    fill a chunk fairly; the partial start-of-week is the honest reflection of
    what's been recorded so far. Once the month finishes, the past-month
    branch takes over and chunks become full and stable."""
    today_dt = getdate(today())
    is_past_month = (date.year, date.month) != (today_dt.year, today_dt.month)

    if is_past_month:
        cur_first = getdate(f"{date.year}-{date.month:02d}-01")
        cur_days = monthrange(date.year, date.month)[1]
        cur_spans = _build_period_spans("Hebdomadaire", cur_first, cur_days)
        idx = next(i for i, (_, s, e) in enumerate(cur_spans) if s <= date <= e)
        _, sem_act_start, sem_act_end = cur_spans[idx]
        if idx > 0:
            _, sem_prev_start, sem_prev_end = cur_spans[idx - 1]
        else:
            # Cursor in S1 → Sem. préc. = S4 of previous calendar month
            last_of_prev = add_days(cur_first, -1)
            prev_first = getdate(f"{last_of_prev.year}-{last_of_prev.month:02d}-01")
            prev_days = monthrange(last_of_prev.year, last_of_prev.month)[1]
            _, sem_prev_start, sem_prev_end = _build_period_spans(
                "Hebdomadaire", prev_first, prev_days)[-1]
    else:
        sem_act_start = add_days(date, -6)
        sem_act_end = date
        sem_prev_start = add_days(date, -13)
        sem_prev_end = add_days(date, -7)

    prod_act = _traite_by_lot(sem_act_start, sem_act_end)
    prod_prev = _traite_by_lot(sem_prev_start, sem_prev_end)
    eff_curr = lactantes_per_lot_on_date(date)

    lots = sorted(set(_active_lactating_lots()) | set(prod_act) | set(prod_prev),
                  key=lot_sort_key)
    columns = _lot_columns(lots)

    # Two views over the same data:
    #   - Sem. préc. / Sem. act. rows show TOTAL kg over the week (what the
    #     farmer wants to see — "how much milk did we get this week").
    #   - Δ % and Moyenne / lact / jour use per-day rates so the comparison
    #     stays fair when weeks have different lengths (S4 can be 7–10 days).
    # Day count is included in the row label so the user understands the span.
    sem_act_days = (sem_act_end - sem_act_start).days + 1
    sem_prev_days = (sem_prev_end - sem_prev_start).days + 1
    total_act = {l: round(prod_act.get(l, 0), 1) for l in lots}
    total_prev = {l: round(prod_prev.get(l, 0), 1) for l in lots}
    avg_act_per_day = {l: prod_act.get(l, 0) / sem_act_days for l in lots}
    avg_prev_per_day = {l: prod_prev.get(l, 0) / sem_prev_days for l in lots}

    total_eff = sum(eff_curr.values())
    sum_total_act = round(sum(total_act.values()), 1)
    sum_total_prev = round(sum(total_prev.values()), 1)
    sum_avg_act_per_day = sum(avg_act_per_day.values())
    sum_avg_prev_per_day = sum(avg_prev_per_day.values())

    rows = [
        {"jour": "Effectif", "is_total": True, "total": total_eff,
         **{l: eff_curr.get(l, 0) or None for l in lots}},
        {"jour": f"Sem. préc. ({sem_prev_start.strftime('%d/%m')}-{sem_prev_end.strftime('%d/%m')}, {sem_prev_days}j)",
         "tint": "orange",
         **{l: total_prev[l] or None for l in lots},
         "total": sum_total_prev or None},
        {"jour": f"Sem. act. ({sem_act_start.strftime('%d/%m')}-{sem_act_end.strftime('%d/%m')}, {sem_act_days}j)",
         "tint": "orange",
         **{l: total_act[l] or None for l in lots},
         "total": sum_total_act or None},
        {"jour": "Δ % (sem. act. vs préc., L/jour)", "is_total": True, "is_delta": True,
         **{l: _delta_pct(avg_act_per_day[l], avg_prev_per_day[l]) for l in lots},
         "total": _delta_pct(sum_avg_act_per_day, sum_avg_prev_per_day)},
        {"jour": "Moyenne / lact / jour", "is_total": True,
         **{l: round(avg_act_per_day[l] / eff_curr[l], 1) if eff_curr.get(l) else None for l in lots},
         "total": round(sum_avg_act_per_day / total_eff, 1) if total_eff else None},
    ]
    return columns, rows


def _active_lactating_lots():
    """Distinct lots with at least one currently-lactating cow."""
    return [r[0] for r in frappe.db.sql("""
        SELECT DISTINCT id_lot FROM `tabAnimal`
        WHERE statut = 'ACTIF' AND etat_lactation = 'EN_PRODUCTION'
          AND id_lot IS NOT NULL AND id_lot != ''
    """)]


def _traite_by_lot(start, end=None):
    """Production per lot using Traite.id_lot (stamped at save time). Pass a
    single date for one day, or (start, end) for an inclusive range total."""
    if end is None:
        end = start
    rows = frappe.db.sql("""
        SELECT id_lot AS lot, SUM(quantite_litres) AS litres
        FROM `tabTraite`
        WHERE date_traite BETWEEN %s AND %s
          AND id_lot IS NOT NULL AND id_lot != ''
        GROUP BY id_lot
    """, (str(start), str(end)), as_dict=True)
    return {r.lot: round(float(r.litres or 0), 1) for r in rows}


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


def _delta_pct(curr, prev):
    """Δ % between current and previous values, rounded to 1 decimal. None
    when prev is 0 (or falsy) to avoid division-by-zero in the report cells."""
    return round((curr - prev) / prev * 100, 1) if prev else None


# ─── Alimentation ────────────────────────────────────────────────────────────

def _aliment_data_per_lot(date_debut, date_filter, period_spans=None,
                           daily_snapshot_date=None):
    """Per-day per-lot historical reconstruction shared by _alimentation and
    _indicateurs. Walks each day from date_debut → date_filter and returns:
        active_lots:                   list of all active lot names
        daily_qty:                     {(aliment, lot): kg distributed on snapshot day}
        daily_ms:                      {lot: kg MS on snapshot day}
        daily_pop:                     {lot: pop on snapshot day}
        cumulative_qty:                {aliment: cheptel-wide kg over period}
        cumulative_concentre_cheptel:  kg of CONCENTRE-type aliments over period
        cumulative_ms_cheptel:         kg MS over period
        cumulative_cow_days_cheptel:   cow-days over period
        aliment_ms_pct:                {aliment: ms_pct fraction}
        aliment_type:                  {aliment: type_aliment string}
        lots_with_data:                lots with data on snapshot day

    `daily_snapshot_date` (defaults to `date_filter` for backward compat) is
    the day used to populate the daily_* dicts. _alimentation passes the user's
    cursor here while letting `date_filter` go to the end of the walk window
    (= end of month for past months) — so daily snapshot reflects the cursor
    while period aggregates cover the full intended range.

    If `period_spans` is provided as a list of (label, start, end) tuples,
    additional per-period aggregates are returned (keys absent otherwise so
    callers like _indicateurs are unaffected):
        period_qty:           {(label, aliment, lot): kg total}
        period_ms:            {(label, lot): kg MS total}
        period_concentre:     {label: kg CONCENTRE total cheptel-wide}
        period_ms_cheptel:    {label: kg MS total cheptel-wide}
        period_cow_days:      {(label, lot): cow-days}
        period_cow_days_cheptel: {label: cheptel cow-days}
        period_days:          {label: number of actual days in the span (caps
                               at date_filter so partial periods work)}
    Returns None if no active lots.
    """
    if daily_snapshot_date is None:
        daily_snapshot_date = date_filter
    active_lots = frappe.get_all("Lot", filters={"actif": 1},
                                 fields=["name"], order_by="name")
    if not active_lots:
        return None

    lot_names_all = [l.name for l in active_lots]
    days_in_period = (date_filter - date_debut).days + 1
    days = [add_days(date_debut, i) for i in range(days_in_period)]

    # Pre-fetch all ration history (episodes) for active lots in 1 query.
    # Each row is one episode: ration used during [date_debut, date_fin).
    # date_fin IS NULL means the episode is currently open.
    history = {}
    for r in frappe.db.sql("""
        SELECT lot, ration, date_debut, date_fin
        FROM `tabLot Ration History`
        WHERE lot IN %s AND ration IS NOT NULL
        ORDER BY date_debut ASC
    """, (lot_names_all,), as_dict=True):
        history.setdefault(r.lot, []).append((r.date_debut, r.date_fin, r.ration))

    current_ration = {l.name: frappe.db.get_value("Lot", l.name, "id_ration_actuelle")
                      for l in active_lots}

    def ration_for(lot, day):
        # Episodes are non-overlapping; reverse-walk and return the first one
        # whose [date_debut, date_fin) interval covers `day`.
        for date_debut, date_fin, rat in reversed(history.get(lot, [])):
            if date_debut <= day and (date_fin is None or day < date_fin):
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

    # Pre-fetch population data: animals + Allotement History in 2 SQL calls.
    # Lets us compute lot population per day in pure Python (was 1 SQL per day —
    # too slow at year scale, e.g. 365 calls/year × 7 years for Bilan Annuel).
    animal_rows = frappe.db.sql("""
        SELECT name, est_achat, date_naissance, date_entree, statut, date_sortie, id_lot
        FROM `tabAnimal`
        WHERE (CASE WHEN est_achat=1 THEN date_entree ELSE date_naissance END) <= %s
    """, (date_filter,), as_dict=True)
    for a in animal_rows:
        e = a.date_entree if a.est_achat else a.date_naissance
        a["entry_date"] = getdate(e) if e else None
        a["exit_date"] = getdate(a.date_sortie) if a.date_sortie else None
    allot_history = {}
    if animal_rows:
        names = [a.name for a in animal_rows]
        for r in frappe.db.sql("""
            SELECT animal, to_lot, DATE(creation) AS dt
            FROM `tabAllotement History`
            WHERE animal IN %s AND DATE(creation) <= %s
            ORDER BY animal, creation ASC
        """, (names, date_filter), as_dict=True):
            allot_history.setdefault(r.animal, []).append((getdate(r.dt), r.to_lot))

    def populations_on_date(day):
        """Returns {lot: count} for `day` using pre-fetched in-memory data — no SQL."""
        per_lot = {}
        for a in animal_rows:
            if not a.entry_date or a.entry_date > day:
                continue
            if a.statut != "ACTIF" and (not a.exit_date or a.exit_date <= day):
                continue
            lot = a.id_lot
            for h_dt, h_to in reversed(allot_history.get(a.name, [])):
                if h_dt <= day:
                    lot = h_to
                    break
            if lot:
                per_lot[lot] = per_lot.get(lot, 0) + 1
        return per_lot

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

    period_qty = {}
    period_ms = {}
    period_concentre = {}
    period_ms_cheptel = {}
    period_cow_days = {}
    period_cow_days_cheptel = {}
    period_days = {}

    def _period_for(day):
        """Return the label of the period this day belongs to, or None."""
        if not period_spans:
            return None
        for label, start, end in period_spans:
            if start <= day <= end:
                return label
        return None

    for day in days:
        pop = populations_on_date(day)
        is_filter_day = (day == daily_snapshot_date)
        day_period = _period_for(day)
        if day_period is not None:
            period_days[day_period] = period_days.get(day_period, 0) + 1
        for lot in lot_names_all:
            n_pop = pop.get(lot, 0)
            if n_pop == 0:
                continue
            cumulative_cow_days_cheptel += n_pop
            if day_period is not None:
                period_cow_days[(day_period, lot)] = period_cow_days.get((day_period, lot), 0) + n_pop
                period_cow_days_cheptel[day_period] = period_cow_days_cheptel.get(day_period, 0) + n_pop
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
                if day_period is not None:
                    key = (day_period, aliment, lot)
                    period_qty[key] = period_qty.get(key, 0) + day_qty
                    period_ms[(day_period, lot)] = period_ms.get((day_period, lot), 0) + day_ms
                    period_ms_cheptel[day_period] = period_ms_cheptel.get(day_period, 0) + day_ms
                    if c.type_aliment == "CONCENTRE":
                        period_concentre[day_period] = period_concentre.get(day_period, 0) + day_qty
                    lots_with_data.add(lot)

    out = {
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
    if period_spans:
        out.update({
            "period_qty": period_qty,
            "period_ms": period_ms,
            "period_concentre": period_concentre,
            "period_ms_cheptel": period_ms_cheptel,
            "period_cow_days": period_cow_days,
            "period_cow_days_cheptel": period_cow_days_cheptel,
            "period_days": period_days,
        })
    return out


def _build_period_spans(granularite, date_debut, nb_jours_du_mois):
    """Compute the (label, start, end) spans for the chosen granularity over a
    full calendar month (date_debut + nb_jours_du_mois). Spans are NOT clipped
    to date_filter — the helper handles that naturally because its day walk
    only goes up to date_filter, so days past it never get attributed to a
    period (period_days[label] stays 0 for future spans).

    Returns:
      Quotidien     -> [] (caller falls back to daily-snapshot behavior)
      Quinzaine     -> 2 spans: Q1 (1-15) and Q2 (16-end)
      Hebdomadaire  -> 4 spans: S1 (1-7), S2 (8-14), S3 (15-21), S4 (22-end)
    """
    if granularite == "Quinzaine":
        return [
            ("Q1", date_debut, add_days(date_debut, 14)),
            ("Q2", add_days(date_debut, 15), add_days(date_debut, nb_jours_du_mois - 1)),
        ]
    if granularite == "Hebdomadaire":
        return [
            ("S1", date_debut, add_days(date_debut, 6)),
            ("S2", add_days(date_debut, 7), add_days(date_debut, 13)),
            ("S3", add_days(date_debut, 14), add_days(date_debut, 20)),
            ("S4", add_days(date_debut, 21), add_days(date_debut, nb_jours_du_mois - 1)),
        ]
    return []


def _alimentation(ctx):
    # Per-lot cells = TODAY's snapshot (kg distributed at date_filter), regardless
    # of granularité. Period summary columns (Moy/jour Q1/Q2, S1..S4) appear on
    # the right and are CHEPTEL-WIDE — they show how much/day the herd ate in each
    # period. "Moy/jour mois" column = cumulative cheptel kg / days walked.
    # The Δ Q2/Q1 column appears only in Quinzaine mode.
    if _is_future(ctx):
        return _future_stub()

    granularite = ctx.get("granularite") or "Quotidien"
    date_debut = ctx["date_debut"]
    date_fin = ctx["date_fin"]
    nb_jours = ctx["nb_jours"]
    cursor = min(getdate(ctx["date_filter"]), getdate(date_fin))
    today_dt = getdate(today())
    # Same scope rule as Effectif "État du Mois":
    #   past month  → walk_end = end of month (Q1 + Q2 always populated)
    #   current month → walk_end = today (in-progress, Q2 only fills past day 16)
    # The user's cursor stays as the daily snapshot date.
    if cursor.year == today_dt.year and cursor.month == today_dt.month:
        walk_end = min(cursor, today_dt)
    else:
        walk_end = getdate(date_fin)
    period_spans = _build_period_spans(granularite, date_debut, nb_jours)
    days_walked = (walk_end - date_debut).days + 1

    d = _aliment_data_per_lot(date_debut, walk_end,
                              period_spans=period_spans or None,
                              daily_snapshot_date=cursor)
    if d is None:
        return [{"fieldname": "msg", "label": "", "fieldtype": "Data", "width": 300}], \
               [{"msg": "Aucun lot actif."}]
    if not d["lots_with_data"]:
        return [{"fieldname": "msg", "label": "", "fieldtype": "Data", "width": 300}], \
               [{"msg": "Aucun lot avec ration assignée à cette date."}]

    lot_names = sorted(d["lots_with_data"], key=lot_sort_key)

    # ── Build columns ─────────────────────────────────────────────────────
    columns = [
        {"fieldname": "aliment", "label": "Aliment", "fieldtype": "Data", "width": 180},
        {"fieldname": "ms_pct", "label": "MS%", "fieldtype": "Percent", "width": 80},
    ]
    for lot in lot_names:
        columns.append({"fieldname": lot, "label": lot, "fieldtype": "Float",
                        "precision": 2, "width": 100})
    for label, _, _ in period_spans:
        columns.append({"fieldname": f"moy_{label.lower()}",
                        "label": f"Moy/jour {label}",
                        "fieldtype": "Float", "precision": 2, "width": 110})
    if granularite == "Quinzaine":
        columns.append({"fieldname": "delta_q2_q1", "label": "Δ Q2/Q1",
                        "fieldtype": "Percent", "precision": 1, "width": 90})
    columns.append({"fieldname": "moy_jour_mois",
                    "label": f"Moy/jour {date_debut.strftime('%m/%Y')}",
                    "fieldtype": "Float", "precision": 2, "width": 130})

    # ── Milk fetch: per-lot daily uses cursor (today's snapshot column),
    # ── cheptel-wide cumulative + per-period uses walk_end (full-month for past).
    prod_daily = frappe.db.sql("""
        SELECT id_lot, SUM(quantite_litres) AS prod
        FROM `tabTraite`
        WHERE date_traite = %s AND id_lot IN %s
        GROUP BY id_lot
    """, (cursor, lot_names), as_dict=True)
    prod_per_lot_daily = {p.id_lot: float(p.prod or 0) for p in prod_daily}

    cum_milk = frappe.db.sql("""
        SELECT SUM(quantite_litres) FROM `tabTraite`
        WHERE date_traite BETWEEN %s AND %s
    """, (date_debut, walk_end))[0][0] or 0
    cumulative_milk_cheptel = float(cum_milk)

    milk_per_period_cheptel = {}
    if period_spans:
        rows = frappe.db.sql("""
            SELECT date_traite, SUM(quantite_litres) AS prod
            FROM `tabTraite`
            WHERE date_traite BETWEEN %s AND %s
            GROUP BY date_traite
        """, (date_debut, walk_end), as_dict=True)
        for r in rows:
            day = getdate(r.date_traite)
            for label, start, end in period_spans:
                if start <= day <= end:
                    milk_per_period_cheptel[label] = milk_per_period_cheptel.get(label, 0) + float(r.prod or 0)
                    break

    # ── Helpers ──────────────────────────────────────────────────────────
    def _round_or_none(v, precision=2):
        return round(v, precision) if v else None

    def _delta_q2_q1(q1_val, q2_val, q1_n, q2_n):
        """% change Q2 vs Q1, or None if either period has no walked days."""
        if not (q1_n and q2_n) or not q1_val:
            return None
        return round((q2_val - q1_val) / q1_val * 100, 1)

    def _period_avg(period_total, period_label):
        """Cheptel-wide kg/day in a period given its total cheptel kg."""
        n = d["period_days"].get(period_label, 0)
        return round(period_total / n, 2) if (period_total and n) else None

    # ── Per-aliment data rows ────────────────────────────────────────────
    data = []
    aliments = sorted(set(a for a, _ in d["daily_qty"]) | set(d["cumulative_qty"]))
    for aliment in aliments:
        row = {"aliment": aliment, "ms_pct": d["aliment_ms_pct"].get(aliment, 0) * 100}

        # Per-lot today's snapshot
        for lot in lot_names:
            row[lot] = _round_or_none(d["daily_qty"].get((aliment, lot), 0))

        # Cheptel-wide period averages
        for label, _, _ in period_spans:
            cheptel_total = sum(d["period_qty"].get((label, aliment, l), 0) for l in lot_names)
            row[f"moy_{label.lower()}"] = _period_avg(cheptel_total, label)

        # Δ Q2/Q1 (Quinzaine only)
        if granularite == "Quinzaine":
            q1_total = sum(d["period_qty"].get(("Q1", aliment, l), 0) for l in lot_names)
            q2_total = sum(d["period_qty"].get(("Q2", aliment, l), 0) for l in lot_names)
            q1_n = d["period_days"].get("Q1", 0); q2_n = d["period_days"].get("Q2", 0)
            row["delta_q2_q1"] = _delta_q2_q1(
                q1_total / q1_n if q1_n else 0,
                q2_total / q2_n if q2_n else 0, q1_n, q2_n)

        # Moy/jour mois cheptel-wide
        cum = d["cumulative_qty"].get(aliment, 0)
        row["moy_jour_mois"] = round(cum / days_walked, 2) if (cum and days_walked) else None
        data.append(row)

    # ── MS Total Distribué (per-lot today; cheptel-wide for periods) ─────
    ms_total_row = {"aliment": "MS Total Distribué", "ms_pct": None, "is_total": True}
    for lot in lot_names:
        ms_total_row[lot] = _round_or_none(d["daily_ms"].get(lot, 0))
    for label, _, _ in period_spans:
        ms_total_row[f"moy_{label.lower()}"] = _period_avg(d["period_ms_cheptel"].get(label, 0), label)
    if granularite == "Quinzaine":
        q1_n = d["period_days"].get("Q1", 0); q2_n = d["period_days"].get("Q2", 0)
        ms_total_row["delta_q2_q1"] = _delta_q2_q1(
            d["period_ms_cheptel"].get("Q1", 0) / q1_n if q1_n else 0,
            d["period_ms_cheptel"].get("Q2", 0) / q2_n if q2_n else 0, q1_n, q2_n)
    ms_total_row["moy_jour_mois"] = (round(d["cumulative_ms_cheptel"] / days_walked, 2)
                                     if d["cumulative_ms_cheptel"] and days_walked else None)
    data.append(ms_total_row)

    # ── MS Distribué/Tête (kg MS per cow per day) ────────────────────────
    ms_tete_row = {"aliment": "MS Distribué/Tête", "ms_pct": None, "is_total": True}
    for lot in lot_names:
        nb = d["daily_pop"].get(lot, 0)
        ms_tete_row[lot] = round(d["daily_ms"].get(lot, 0) / nb, 2) if nb else None
    for label, _, _ in period_spans:
        cd = d["period_cow_days_cheptel"].get(label, 0)
        ms = d["period_ms_cheptel"].get(label, 0)
        ms_tete_row[f"moy_{label.lower()}"] = round(ms / cd, 2) if (ms and cd) else None
    if granularite == "Quinzaine":
        q1_cd = d["period_cow_days_cheptel"].get("Q1", 0)
        q2_cd = d["period_cow_days_cheptel"].get("Q2", 0)
        ms_tete_row["delta_q2_q1"] = _delta_q2_q1(
            d["period_ms_cheptel"].get("Q1", 0) / q1_cd if q1_cd else 0,
            d["period_ms_cheptel"].get("Q2", 0) / q2_cd if q2_cd else 0, q1_cd, q2_cd)
    ms_tete_row["moy_jour_mois"] = (round(d["cumulative_ms_cheptel"] / d["cumulative_cow_days_cheptel"], 2)
                                    if d["cumulative_cow_days_cheptel"] else None)
    data.append(ms_tete_row)

    # ── Efficacité alimentaire (L milk per kg MS) ────────────────────────
    eff_row = {"aliment": "Efficacité alimentaire L/Kg MS", "ms_pct": None, "is_total": True}
    for lot in lot_names:
        ms = d["daily_ms"].get(lot, 0)
        eff_row[lot] = round(prod_per_lot_daily.get(lot, 0) / ms, 2) if ms else None
    for label, _, _ in period_spans:
        ms = d["period_ms_cheptel"].get(label, 0)
        milk = milk_per_period_cheptel.get(label, 0)
        eff_row[f"moy_{label.lower()}"] = round(milk / ms, 2) if ms else None
    if granularite == "Quinzaine":
        q1_ms = d["period_ms_cheptel"].get("Q1", 0)
        q2_ms = d["period_ms_cheptel"].get("Q2", 0)
        eff_row["delta_q2_q1"] = _delta_q2_q1(
            milk_per_period_cheptel.get("Q1", 0) / q1_ms if q1_ms else 0,
            milk_per_period_cheptel.get("Q2", 0) / q2_ms if q2_ms else 0, q1_ms, q2_ms)
    eff_row["moy_jour_mois"] = (round(cumulative_milk_cheptel / d["cumulative_ms_cheptel"], 2)
                                if d["cumulative_ms_cheptel"] else None)
    data.append(eff_row)

    return columns, data


# ─── Indicateurs ─────────────────────────────────────────────────────────────

def _kpi_ind(value, green_max=None, orange_max=None, green_min=None, orange_min=None):
    """One-direction indicator. Pass green_max+orange_max for lower-better,
    or green_min+orange_min for higher-better. Returns "" when value is
    None/0 (no signal possible)."""
    if value is None or value == 0:
        return ""
    if green_max is not None:
        if value <= green_max: return "Green"
        if value <= orange_max: return "Orange"
        return "Red"
    if green_min is not None:
        if value >= green_min: return "Green"
        if value >= orange_min: return "Orange"
        return "Red"
    return ""


def _kpi_ind_range(value, green_low, green_high, low_alarm=None, high_alarm=None):
    """Range indicator. Green inside [green_low, green_high], Orange close,
    Red outside the alarm bounds. For metrics with an optimal middle range
    (e.g. L/C 2.0-2.4, persistance 0.85-0.95)."""
    if value is None or value == 0:
        return ""
    if green_low <= value <= green_high:
        return "Green"
    if (low_alarm is not None and value < low_alarm) or \
       (high_alarm is not None and value > high_alarm):
        return "Red"
    return "Orange"


def _indicateurs(ctx):
    """KPI dashboard. Vache counts = snapshot @ date_filter (reconstructed from
    events). Production / Concentré / MS = cumulative date_debut → date_filter
    (per-day historical reconstruction; no phantom future days).

    M-1 même période column shows the same KPIs computed for the previous
    calendar month, shifted by one month via add_months (handles short-month
    edges: e.g. cursor 31/03 → M-1 ends 28/02). Per-lactation aggregates (PIC
    moy, P305j moy, Persistance moy) skip M-1 — they're slow-moving herd
    snapshots dominated by the same cohort, so a monthly Δ adds noise not
    signal. Δ % is colored by `direction` ("up" higher-better, "down" lower-
    better, None for absolutes / range KPIs where direction isn't sign-based).

    Thresholds (PFE color on `valeur`) come from HMD Configuration → Seuils
    PFE. Cost metrics deferred until Stock/Finance integration."""
    if _is_future(ctx):
        return _future_stub()

    columns = [
        {"fieldname": "indicateur", "label": "Indicateur", "fieldtype": "Data", "width": 320},
        {"fieldname": "valeur", "label": "Valeur", "fieldtype": "Float", "precision": 2, "width": 110},
        {"fieldname": "valeur_m1", "label": "M-1 même période", "fieldtype": "Float", "precision": 2, "width": 130},
        {"fieldname": "delta_pct", "label": "Δ", "fieldtype": "Percent", "precision": 1, "width": 80},
        {"fieldname": "unite", "label": "Unité", "fieldtype": "Data", "width": 150},
    ]

    # Thresholds — sourced from HMD Configuration → Seuils PFE.
    # Defaults match Vallet & Paccard 1984 / PFE Chap 3.
    cfg_lc_min   = float(get_config("pfe_lc_optimal_min", default=2.0))
    cfg_lc_max   = float(get_config("pfe_lc_optimal_max", default=2.4))
    cfg_lc_alm_lo = float(get_config("pfe_lc_alarm_min", default=1.5))
    cfg_lc_alm_hi = float(get_config("pfe_lc_alarm_max", default=3.0))
    cfg_eff_min  = float(get_config("pfe_efficacite_min", default=1.4))
    cfg_eff_omn  = float(get_config("pfe_efficacite_orange_min", default=1.0))
    cfg_pers_min = float(get_config("pfe_persistance_min", default=0.85))
    cfg_pers_max = float(get_config("pfe_persistance_max", default=0.95))
    cfg_pers_alm_lo = float(get_config("pfe_persistance_alarm_min", default=0.7))
    cfg_pers_alm_hi = float(get_config("pfe_persistance_alarm_max", default=1.10))

    date_debut = ctx["date_debut"]
    date_filter = min(ctx["date_filter"], ctx["date_fin"])

    def _period_kpis(start, end):
        """Compute the period KPIs (effectif, prod, concentré, MS, ratios) for
        any [start, end] range. Reuses effectif_on_date and _aliment_data_per_lot
        — the canonical historical-reconstruction primitives."""
        eff = effectif_on_date(end)
        vl_ = eff["Vaches - Lact."]
        vt_ = eff["Vaches - Tarie"]
        vp_ = vl_ + vt_
        prod_ = float(frappe.db.sql("""
            SELECT SUM(quantite_litres) FROM `tabTraite`
            WHERE date_traite BETWEEN %s AND %s
        """, (start, end))[0][0] or 0)
        d_ = _aliment_data_per_lot(start, end)
        concentre_ = d_["cumulative_concentre_cheptel"] if d_ else 0
        ms_total_ = d_["cumulative_ms_cheptel"] if d_ else 0
        return {
            "vp": vp_, "vl": vl_, "vt": vt_,
            "prod": prod_, "concentre": concentre_, "ms_total": ms_total_,
            "lmv": round(prod_ / vp_, 1) if vp_ else 0,
            "pl_vl": round(prod_ / vl_, 1) if vl_ else 0,
            "lc": round(prod_ / concentre_, 2) if concentre_ else 0,
            "eff_alim": round(prod_ / ms_total_, 2) if ms_total_ else 0,
            "conc_per_vp": round(concentre_ / vp_, 2) if vp_ else 0,
            "conc_per_vl": round(concentre_ / vl_, 2) if vl_ else 0,
        }

    cur = _period_kpis(date_debut, date_filter)
    m1 = _period_kpis(add_months(date_debut, -1), _shift_minus_one_month(date_filter))

    # ── Per-lactation herd KPIs — NO M-1 (slow-moving cohort snapshots, monthly
    # Δ adds noise not signal; users compare to PFE benchmark instead).
    prod_stats = frappe.db.sql("""
        SELECT AVG(NULLIF(lactation_305j, 0)) AS p305_moy,
               AVG(NULLIF(pic_production, 0)) AS pic_moy
        FROM `tabLactation`
        WHERE statut = 'EN_COURS' AND date_debut <= %s
    """, (date_filter,), as_dict=True)[0]
    p305_moy = round(float(prod_stats.p305_moy), 1) if prod_stats.p305_moy else None
    pic_moy = round(float(prod_stats.pic_moy), 1) if prod_stats.pic_moy else None

    pers_rows = frappe.db.sql("""
        SELECT t.animal,
            SUM(CASE WHEN DATEDIFF(t.date_traite, l.date_debut) BETWEEN 0 AND 99
                     THEN t.quantite_litres ELSE 0 END) AS p0_100,
            SUM(CASE WHEN DATEDIFF(t.date_traite, l.date_debut) BETWEEN 100 AND 199
                     THEN t.quantite_litres ELSE 0 END) AS p100_200
        FROM `tabTraite` t
        INNER JOIN `tabLactation` l ON t.lactation = l.name
        WHERE l.statut = 'EN_COURS' AND t.date_traite <= %s
          AND DATEDIFF(t.date_traite, l.date_debut) BETWEEN 0 AND 199
        GROUP BY t.animal
    """, (date_filter,), as_dict=True)
    pers_values = [float(r.p100_200) / float(r.p0_100) for r in pers_rows
                   if r.p0_100 and r.p100_200]
    persistance_moy = round(sum(pers_values) / len(pers_values), 2) if pers_values else None

    period = f"{date_debut.strftime('%d/%m')} → {date_filter.strftime('%d/%m')}"

    def row(indicateur, valeur, unite, indicator="", valeur_m1=None, direction=None):
        """Build a KPI row. valeur_m1=None → M-1 column blank for this row.
        direction: 'up' (higher better), 'down' (lower better), None (no Δ
        coloring — used for absolutes/range KPIs where sign isn't meaningful).
        Δ % computed only when both values are non-zero (avoids /0)."""
        delta_pct = None
        if valeur_m1 is not None and valeur_m1 not in (0, 0.0) and valeur is not None:
            delta_pct = round((valeur - valeur_m1) / valeur_m1 * 100, 1)
        return {
            "indicateur": indicateur, "valeur": valeur, "unite": unite,
            "valeur_m1": valeur_m1, "delta_pct": delta_pct,
            "indicator": indicator, "direction": direction,
        }

    data = [
        # ── Effectif (snapshot — direction None, no inherent up/down better)
        row(f"Vaches Présentes (au {date_filter.strftime('%d/%m')})", cur["vp"], "têtes",
            valeur_m1=m1["vp"]),
        row(f"Vaches Lactantes (au {date_filter.strftime('%d/%m')})", cur["vl"], "têtes",
            valeur_m1=m1["vl"]),
        row(f"Vaches Taries (au {date_filter.strftime('%d/%m')})", cur["vt"], "têtes",
            valeur_m1=m1["vt"]),

        # ── Production
        row(f"Production Totale ({period})", round(cur["prod"], 1), "L",
            valeur_m1=round(m1["prod"], 1)),
        row("LMV — Lact Moy / Vache Présente", cur["lmv"], "L/tête",
            valeur_m1=m1["lmv"], direction="up"),
        row("PL/VL — Production / Vache Lactante", cur["pl_vl"], "L/tête",
            valeur_m1=m1["pl_vl"], direction="up"),
        row("PIC moyen (vaches actives)", pic_moy or 0, "L/jour"),
        row("P305j moyenne (vaches actives)", p305_moy or 0, "L"),
        row("Persistance moyenne", persistance_moy or 0, "ratio",
            indicator=_kpi_ind_range(persistance_moy, cfg_pers_min, cfg_pers_max,
                                     low_alarm=cfg_pers_alm_lo,
                                     high_alarm=cfg_pers_alm_hi)),

        # ── Alimentation
        row(f"Concentré Total ({period})", round(cur["concentre"], 1), "kg",
            valeur_m1=round(m1["concentre"], 1)),
        row("Concentré / Vache Présente", cur["conc_per_vp"], "kg/tête",
            valeur_m1=m1["conc_per_vp"], direction="down"),
        row("Concentré / Vache Lactante", cur["conc_per_vl"], "kg/tête",
            valeur_m1=m1["conc_per_vl"], direction="down"),
        row("L/C — Lait / Concentré", cur["lc"], "L/kg",
            indicator=_kpi_ind_range(cur["lc"], cfg_lc_min, cfg_lc_max,
                                     low_alarm=cfg_lc_alm_lo,
                                     high_alarm=cfg_lc_alm_hi),
            valeur_m1=m1["lc"]),
        row("Efficacité Alimentaire (sur MS)", cur["eff_alim"], "L/kg MS",
            indicator=_kpi_ind(cur["eff_alim"], green_min=cfg_eff_min,
                              orange_min=cfg_eff_omn),
            valeur_m1=m1["eff_alim"], direction="up"),

        # ── Économique (deferred — Stock/Finance integration)
        row("Frais Concentré", None, "DT (à intégrer)"),
        row("Frais Fourrage", None, "DT (à intégrer)"),
        row("Coût Alimentaire / L", None, "DT/L (à intégrer)"),
        row("Main d'Œuvre", None, "DT (à intégrer)"),
        row("Chiffre d'Affaires Lait", None, "DT (à intégrer)"),
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
