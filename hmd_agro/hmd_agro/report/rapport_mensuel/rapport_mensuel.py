import frappe
from frappe.utils import getdate, today, add_days
from calendar import monthrange

from hmd_agro.hmd_agro.utils.snapshot import (
    CATEGORIES, empty_row, set_total, get_day_state, diff_day, capture_events,
)


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
    """Per-day Effectif table: Initial (D-1 aggregates) → changes → Final (D aggregates)."""
    columns = [{"fieldname": "ligne", "label": "", "fieldtype": "Data", "width": 180}]
    for cat in CATEGORIES:
        columns.append({"fieldname": cat, "label": cat, "fieldtype": "Int", "width": 100})

    date = ctx["date_filter"]
    prev = get_day_state(add_days(date, -1))
    if not prev:
        return columns, [_gap_row(f"Snapshot initial manquant ({add_days(date, -1)}). Importer les données.")]
    curr = get_day_state(date)
    if not curr:
        return columns, [_gap_row(f"Pas de données pour le {date} (jour futur ou non figé).")]

    d = diff_day(prev["animals"], curr["animals"])
    ev = capture_events(date)

    naissances = empty_row()
    naissances["Veaux"] = ev["naissances_m"]
    naissances["Velles"] = ev["naissances_f"]
    set_total(naissances)

    avortements = empty_row()
    avortements["Total"] = ev["avortements"] + ev["mort_nes"]

    rows = [
        ("Effectif Initial",         prev["aggregates"], True),
        ("Changement Catégorie (+)", d["cat_plus"],      False),
        ("Changement Catégorie (-)", d["cat_minus"],     False),
        ("Vêlage",                   d["velage"],        False),
        ("Naissance",                naissances,         False),
        ("Avortement / Mort-né",     avortements,        False),
        ("Achat",                    d["achats"],        False),
        ("Vente (Quantité)",         d["ventes"],        False),
        ("Vente (Prix DT)",          d["prix_vente"],    False),
        ("Mortalité",                d["mortalite"],     False),
        ("Réforme",                  d["reformes"],      False),
        ("Effectif Final",           curr["aggregates"], True),
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
    nb_vl = frappe.db.count("Animal", {"categorie": "VACHE", "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION"})

    data = []
    total_prod = 0
    for j in range(1, ctx["nb_jours"] + 1):
        d = daily_map.get(j, {})
        prod = float(d.get("prod") or 0)
        total_prod += prod
        data.append({
            "jour": j, "nb_lactantes": nb_vl,
            "production": round(prod, 1),
            "moyenne": round(prod / nb_vl, 1) if nb_vl and prod else 0,
            "taux_tb": round(float(d.get("tb") or 0), 2) or None,
            "taux_tp": round(float(d.get("tp") or 0), 2) or None,
            "commercialise": None,
        })

    data.append({
        "jour": None, "is_total": 1, "nb_lactantes": nb_vl,
        "production": round(total_prod, 1),
        "moyenne": round(total_prod / (nb_vl * ctx["nb_jours"]), 1) if nb_vl else 0,
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
    """
    4-row table for the selected day (D) and previous day (D-1):
      Effectif       — lactantes per lot on day D (from snapshot lot membership)
      <D-1 date>     — production per lot on D-1
      <D date>       — production per lot on D
      Moyenne / lot  — prod(D) / effectif(D) per lot  (Excel: C24/C22)

    Uses the same snapshot state used by Effectif, so past days attribute
    production to each cow's lot *as of that day*, not its current lot.
    """
    columns_msg = [{"fieldname": "msg", "label": "", "fieldtype": "Data", "width": 300}]
    date = ctx["date_filter"]
    prev_date = add_days(date, -1)

    curr = get_day_state(date)
    prev = get_day_state(prev_date)
    if not curr or not prev:
        missing = prev_date if not prev else date
        return columns_msg, [{"msg": f"Snapshot manquant pour le {missing}."}]

    eff_curr = _lactantes_by_lot(curr["animals"])
    eff_prev = _lactantes_by_lot(prev["animals"])
    lots = sorted(set(eff_curr) | set(eff_prev))
    if not lots:
        return columns_msg, [{"msg": "Aucune vache lactante sur la période."}]

    prod_curr = _prod_by_lot(date, curr["animals"])
    prod_prev = _prod_by_lot(prev_date, prev["animals"])

    columns = [{"fieldname": "jour", "label": "", "fieldtype": "Data", "width": 100}]
    for lot in lots:
        columns.append({"fieldname": lot, "label": lot, "fieldtype": "Float", "precision": 1, "width": 100})
    columns.append({"fieldname": "total", "label": "Total", "fieldtype": "Float", "precision": 1, "width": 100})

    total_eff = sum(eff_curr.values())
    total_prod = sum(prod_curr.values())

    rows = [
        {"jour": "Effectif", "is_total": True, "total": total_eff,
         **{lot: eff_curr.get(lot, 0) for lot in lots}},
        _day_row(prev_date.strftime("%d/%m"), lots, prod_prev),
        _day_row(date.strftime("%d/%m"), lots, prod_curr),
        {"jour": "Moyenne / lot", "is_total": True,
         **{lot: _safe_div(prod_curr.get(lot, 0), eff_curr.get(lot, 0)) for lot in lots},
         "total": _safe_div(total_prod, total_eff)},
    ]
    return columns, rows


def _lactantes_by_lot(animals):
    out = {}
    for a in animals.values():
        if (a["statut"] == "ACTIF" and a["cat"] == "VACHE"
                and a["lact"] == "EN_PRODUCTION" and a["lot"]):
            out[a["lot"]] = out.get(a["lot"], 0) + 1
    return out


def _prod_by_lot(date, animals):
    """Sum Traite litres for `date` grouped by each cow's lot *on that day*."""
    rows = frappe.db.sql("""
        SELECT animal, SUM(quantite_litres) AS q
        FROM `tabTraite` WHERE date_traite = %s GROUP BY animal
    """, str(date), as_dict=True)
    out = {}
    for r in rows:
        lot = (animals.get(r.animal) or {}).get("lot")
        if lot:
            out[lot] = out.get(lot, 0) + float(r.q or 0)
    return out


def _day_row(label, lots, prod_map):
    row = {"jour": label}
    total = 0
    for lot in lots:
        v = prod_map.get(lot, 0)
        row[lot] = round(v, 1) or None
        total += v
    row["total"] = round(total, 1) or None
    return row


def _safe_div(num, den):
    return round(num / den, 1) if den else None


# ─── Alimentation ────────────────────────────────────────────────────────────

def _alimentation(ctx):
    lots = frappe.db.sql("""
        SELECT l.name, l.id_ration_actuelle, l.nb_animaux
        FROM `tabLot` l
        WHERE l.actif = 1 AND l.id_ration_actuelle IS NOT NULL AND l.id_ration_actuelle != ''
        ORDER BY l.name
    """, as_dict=True)

    if not lots:
        return [{"fieldname": "msg", "label": "", "fieldtype": "Data", "width": 300}], \
               [{"msg": "Aucun lot actif avec ration assignée."}]

    lot_names = [l.name for l in lots]
    lot_nb = {l.name: l.nb_animaux or 0 for l in lots}

    columns = [
        {"fieldname": "aliment", "label": "Aliment", "fieldtype": "Data", "width": 180},
        {"fieldname": "ms_pct", "label": "MS%", "fieldtype": "Percent", "width": 80},
    ]
    for lot in lot_names:
        columns.append({"fieldname": lot, "label": lot, "fieldtype": "Float", "precision": 2, "width": 100})

    aliments = {}
    for l in lots:
        comps = frappe.db.sql("""
            SELECT c.aliment, c.quantite, a.ms_pct
            FROM `tabComposition Ration` c JOIN `tabAliment` a ON c.aliment = a.name
            WHERE c.parent = %s
        """, l.id_ration_actuelle, as_dict=True)
        for c in comps:
            if c.aliment not in aliments:
                aliments[c.aliment] = {"ms_pct": float(c.ms_pct or 0), "qty": {}}
            aliments[c.aliment]["qty"][l.name] = float(c.quantite or 0)

    data = []
    ms_total_per_lot = {lot: 0 for lot in lot_names}

    for aliment_name, info in aliments.items():
        row = {"aliment": aliment_name, "ms_pct": info["ms_pct"]}
        for lot in lot_names:
            qty_per_animal = info["qty"].get(lot, 0)
            qty_total = qty_per_animal * lot_nb[lot]
            row[lot] = round(qty_total, 2) if qty_total else None
            ms_total_per_lot[lot] += qty_total * (info["ms_pct"] / 100.0)
        data.append(row)

    ms_total_row = {"aliment": "MS Total Distribué", "ms_pct": None, "is_total": True}
    for lot in lot_names:
        ms_total_row[lot] = round(ms_total_per_lot[lot], 2) if ms_total_per_lot[lot] else None
    data.append(ms_total_row)

    ms_tete_row = {"aliment": "MS Distribué/Tête", "ms_pct": None, "is_total": True}
    for lot in lot_names:
        nb = lot_nb[lot]
        ms_tete_row[lot] = round(ms_total_per_lot[lot] / nb, 2) if nb else None
    data.append(ms_tete_row)

    prod = frappe.db.sql("""
        SELECT a.id_lot, SUM(t.quantite_litres) as total_prod
        FROM `tabTraite` t JOIN `tabAnimal` a ON t.animal = a.name
        WHERE t.date_traite BETWEEN %s AND %s AND a.id_lot IN %s
        GROUP BY a.id_lot
    """, (ctx["date_debut"], ctx["date_fin"], lot_names), as_dict=True)
    prod_per_lot = {p.id_lot: float(p.total_prod or 0) for p in prod}

    eff_row = {"aliment": "Efficacité alimentaire L/Kg MS", "ms_pct": None, "is_total": True}
    for lot in lot_names:
        monthly_ms = ms_total_per_lot[lot] * ctx["nb_jours"]
        total_milk = prod_per_lot.get(lot, 0)
        eff_row[lot] = round(total_milk / monthly_ms, 2) if monthly_ms else None
    data.append(eff_row)

    return columns, data


# ─── Indicateurs ─────────────────────────────────────────────────────────────

def _indicateurs(ctx):
    columns = [
        {"fieldname": "indicateur", "label": "Indicateur", "fieldtype": "Data", "width": 280},
        {"fieldname": "valeur", "label": "Valeur", "fieldtype": "Float", "precision": 1, "width": 120},
        {"fieldname": "unite", "label": "Unité", "fieldtype": "Data", "width": 100},
    ]

    date_debut, date_fin = ctx["date_debut"], ctx["date_fin"]

    vp = frappe.db.count("Animal", {"categorie": "VACHE", "statut": "ACTIF"})
    vl = frappe.db.count("Animal", {"categorie": "VACHE", "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION"})
    vt = frappe.db.count("Animal", {"categorie": "VACHE", "statut": "ACTIF", "etat_lactation": "TARIE"})

    prod = frappe.db.sql("""
        SELECT SUM(quantite_litres) FROM `tabTraite`
        WHERE date_traite BETWEEN %s AND %s
    """, (date_debut, date_fin))[0][0] or 0

    concentre = _total_concentre(ctx["nb_jours"])
    nb_ia = frappe.db.count("Insemination", {"date_ia": ["between", [date_debut, date_fin]]})
    ia_ok = frappe.db.count("Insemination", {"date_ia": ["between", [date_debut, date_fin]], "resultat": "REUSSIE"})
    nb_vel = frappe.db.count("Velage", {"date_velage": ["between", [date_debut, date_fin]]})

    data = [
        {"indicateur": "Vaches Présentes", "valeur": vp, "unite": "têtes"},
        {"indicateur": "Vaches Lactantes", "valeur": vl, "unite": "têtes"},
        {"indicateur": "Vaches Taries", "valeur": vt, "unite": "têtes"},
        {"indicateur": "Production Totale", "valeur": round(prod, 1), "unite": "litres"},
        {"indicateur": "Moy. Production/VL/Jour", "valeur": round(prod / (vl * ctx["nb_jours"]), 1) if vl else 0, "unite": "L/tête"},
        {"indicateur": "Concentré Total", "valeur": round(concentre, 1), "unite": "kg"},
        {"indicateur": "Concentré/Tête", "valeur": round(concentre / vp, 1) if vp else 0, "unite": "kg/tête"},
        {"indicateur": "L/C (Efficacité)", "valeur": round(prod / concentre, 2) if concentre else 0, "unite": "L/kg"},
        {"indicateur": "Nombre IA", "valeur": nb_ia, "unite": ""},
        {"indicateur": "Taux Réussite IA", "valeur": round(ia_ok / nb_ia * 100, 1) if nb_ia else 0, "unite": "%"},
        {"indicateur": "Nombre Vêlages", "valeur": nb_vel, "unite": ""},
        {"indicateur": "Frais Concentré", "valeur": None, "unite": "DT (à intégrer)"},
        {"indicateur": "Frais Fourrage", "valeur": None, "unite": "DT (à intégrer)"},
        {"indicateur": "Coût Alimentaire/L", "valeur": None, "unite": "DT/L (à intégrer)"},
        {"indicateur": "Main d'Oeuvre", "valeur": None, "unite": "DT (à intégrer)"},
        {"indicateur": "Chiffre d'Affaires Lait", "valeur": None, "unite": "DT (à intégrer)"},
    ]

    return columns, data


def _total_concentre(nb_jours):
    lots = frappe.get_all("Lot", filters={"actif": 1, "id_ration_actuelle": ["is", "set"]},
                          fields=["id_ration_actuelle", "nb_animaux"])
    total = 0
    for lot in lots:
        comps = frappe.get_all("Composition Ration",
            filters={"parent": lot.id_ration_actuelle}, fields=["aliment", "quantite"])
        for c in comps:
            if frappe.db.get_value("Aliment", c.aliment, "type_aliment") == "CONCENTRE":
                total += float(c.quantite or 0) * (lot.nb_animaux or 0) * nb_jours
    return total


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
