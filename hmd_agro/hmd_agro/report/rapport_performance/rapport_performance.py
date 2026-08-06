"""
Rapport Performance (Phase 4) — synthèse hebdomadaire / mensuelle consolidée.

One flat table (section / indicateur / valeur / unite) covering the whole
farm for the selected period: mouvements cheptel, production laitière,
alimentation, charges comptables et coûts unitaires. `valeur` stays a typed
Float so the native CSV/Excel export feeds the Excel template cleanly
(réunion 05/08/2026 : export vers template Excel plutôt que PDF).

Sources — always the canonical primitives, never re-derived:
    live_state count_* / effectif_on_date   — herd events, reconstructed
    Traite / Bilan Lait Journalier          — production volumes
    rapport_mensuel._aliment_data_per_lot   — SLE-based feed costs (lazy
                                              import, dashboard_kpis precedent)
    finance_kpis.gl_sums                    — GL sums per SCE family
    maintenance_utils.cout_maintenance      — équipement interventions

A period with no postings honestly returns 0 — same stance as gl_sums.
"""
import frappe
from frappe.utils import add_days, getdate, today
from calendar import monthrange

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.finance_kpis import gl_sums
from hmd_agro.hmd_agro.utils.live_state import (
    effectif_on_date, count_velages, count_naissances,
    count_avortements_mort_nes, count_achats, count_exits,
)
from hmd_agro.hmd_agro.utils.maintenance_utils import cout_maintenance


COLUMNS = [
    {"fieldname": "section", "label": "Section", "fieldtype": "Data", "width": 160},
    {"fieldname": "indicateur", "label": "Indicateur", "fieldtype": "Data", "width": 340},
    {"fieldname": "valeur", "label": "Valeur", "fieldtype": "Float", "precision": 2, "width": 130},
    {"fieldname": "unite", "label": "Unité", "fieldtype": "Data", "width": 120},
]


def execute(filters=None):
    filters = filters or {}
    periode = filters.get("periode") or "Mois"
    date = getdate(filters.get("date") or today())
    debut, fin = period_bounds(periode, date)

    today_dt = getdate(today())
    if debut > today_dt:
        return COLUMNS, [_row("INFO", "Pas encore de données pour cette période.",
                              None, "")]
    # Only count days that actually happened (open week/month in progress).
    fin = min(fin, today_dt)

    data = []
    data.extend(_mouvements_cheptel(debut, fin))
    prod_rows, prod_ctx = _production(debut, fin)
    data.extend(prod_rows)
    alim_rows, alim_ctx = _alimentation(debut, fin, prod_ctx["prod"])
    data.extend(alim_rows)
    gl = gl_sums(debut, fin)
    data.extend(_charges(debut, fin, gl))
    data.extend(_couts_unitaires(debut, fin, gl, alim_ctx, prod_ctx))
    return COLUMNS, data


def period_bounds(periode, date):
    """(debut, fin) of the period containing `date` — full ISO week (Mon-Sun)
    or full calendar month."""
    if periode == "Semaine":
        # Lazy import — rapport_mensuel owns the canonical week-bounds helper
        # (same precedent as dashboard_kpis importing report internals).
        from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import (
            _iso_week_bounds,
        )
        return _iso_week_bounds(date)
    nb_jours = monthrange(date.year, date.month)[1]
    debut = getdate(f"{date.year}-{date.month:02d}-01")
    fin = getdate(f"{date.year}-{date.month:02d}-{nb_jours}")
    return debut, fin


def _row(section, indicateur, valeur, unite, indicator=""):
    return {"section": section, "indicateur": indicateur,
            "valeur": valeur, "unite": unite, "indicator": indicator}


# ─── (i) Mouvements cheptel ──────────────────────────────────────────────────

def _mouvements_cheptel(debut, fin):
    """Herd movements over the period — day-by-day walk of the live_state
    count_* primitives (event reconstruction, never Animal.etat_* directly)."""
    naissances = velages = avortements = achats = 0
    ventes_qty = ventes_prix = morts = reformes = 0
    d = debut
    while d <= fin:
        naissances += count_naissances(d)["Total"]
        velages += count_velages(d)["Total"]
        avortements += count_avortements_mort_nes(d)["Total"]
        achats += count_achats(d)["Total"]
        vq, vp = count_exits(d, "VENDU")
        ventes_qty += vq["Total"]
        ventes_prix += vp["Total"]
        morts += count_exits(d, "MORT")[0]["Total"]
        reformes += count_exits(d, "REFORME")[0]["Total"]
        d = add_days(d, 1)

    eff_debut = effectif_on_date(add_days(debut, -1))["Total"]
    eff_fin = effectif_on_date(fin)["Total"]

    s = "Cheptel"
    return [
        _row(s, "Effectif Début de Période", eff_debut, "têtes"),
        _row(s, "Naissances", naissances, "nb"),
        _row(s, "Vêlages", velages, "nb"),
        _row(s, "Avortements / Mort-nés", avortements, "nb"),
        _row(s, "Achats", achats, "nb"),
        _row(s, "Ventes (Quantité)", ventes_qty, "nb"),
        _row(s, "Ventes (Prix)", ventes_prix, "DT"),
        _row(s, "Mortalité", morts, "nb"),
        _row(s, "Réformes", reformes, "nb"),
        _row(s, "Effectif Fin de Période", eff_fin, "têtes"),
    ]


# ─── (ii) Production ─────────────────────────────────────────────────────────

def _production(debut, fin):
    prod = float(frappe.db.sql("""
        SELECT SUM(quantite_litres) FROM `tabTraite`
        WHERE date_traite BETWEEN %s AND %s
    """, (debut, fin))[0][0] or 0)
    vl = effectif_on_date(fin)["Vaches - Lact."]

    blj = frappe.db.sql("""
        SELECT COALESCE(SUM(lait_vendu), 0) AS vendu,
               COALESCE(SUM(consommation_interne), 0) AS conso,
               COALESCE(SUM(lait_veau), 0) AS veau,
               COALESCE(SUM(ecart_litres), 0) AS ecart
        FROM `tabBilan Lait Journalier`
        WHERE date BETWEEN %s AND %s
    """, (debut, fin), as_dict=True)[0]

    s = "Production"
    rows = [
        _row(s, "Production Totale", round(prod, 1), "L"),
        _row(s, "PL/VL — Production / Vache Lactante",
             round(prod / vl, 1) if vl else 0, "L/tête"),
        _row(s, "Lait Vendu", round(float(blj.vendu), 1), "L"),
        _row(s, "Consommation Interne", round(float(blj.conso), 1), "L"),
        _row(s, "Lait Veau", round(float(blj.veau), 1), "L"),
        _row(s, "Écart Lait", round(float(blj.ecart), 1), "L"),
    ]
    return rows, {"prod": prod, "vl": vl}


# ─── (iii) Alimentation ──────────────────────────────────────────────────────

def _alimentation(debut, fin, prod):
    """Feed costs + L/C, from the canonical SLE-based walker of the monthly
    report (lazy in-function import — dashboard_kpis precedent)."""
    from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import (
        _aliment_data_per_lot, _kpi_ind_range,
    )
    d = _aliment_data_per_lot(debut, fin)
    concentre = d["cumulative_concentre_cheptel"] if d else 0
    frais_conc = d["cumulative_concentre_cost"] if d else 0
    frais_four = d["cumulative_fourrage_cost"] if d else 0
    frais_total = d["cumulative_aliment_cost"] if d else 0

    lc = round(prod / concentre, 2) if concentre else 0
    cfg_lc_cible = float(get_config("pfe_lc_cible", default=2.2))
    lc_ind = _kpi_ind_range(
        lc,
        float(get_config("pfe_lc_optimal_min", default=2.0)),
        float(get_config("pfe_lc_optimal_max", default=2.4)),
        low_alarm=float(get_config("pfe_lc_alarm_min", default=1.8)),
        high_alarm=float(get_config("pfe_lc_alarm_max", default=3.0)),
    )

    s = "Alimentation"
    rows = [
        _row(s, "Coût Concentré", round(frais_conc, 2), "DT"),
        _row(s, "Coût Fourrage", round(frais_four, 2), "DT"),
        _row(s, "Coût Alimentaire Total", round(frais_total, 2), "DT"),
        _row(s, f"L/C — Lait / Concentré (cible {cfg_lc_cible:g})", lc, "L/kg",
             indicator=lc_ind),
    ]
    return rows, {"frais_alim_total": frais_total}


# ─── (iv) Charges ────────────────────────────────────────────────────────────

def _charges(debut, fin, gl):
    maint = cout_maintenance(debut, fin)
    s = "Charges"
    return [
        _row(s, "Main d'Œuvre (64x)", round(gl["mo"], 2), "DT"),
        _row(s, "Entretien & Réparations (615)", round(gl["entretien"], 2), "DT"),
        _row(s, "Interventions sur Équipements", maint["interventions"], "nb"),
        _row(s, "Dotations aux Amortissements (68x)",
             round(gl["amortissements"], 2), "DT"),
        _row(s, "Charges Totales", round(gl["charges"], 2), "DT"),
        _row(s, "EBE — Excédent Brut d'Exploitation", round(gl["ebe"], 2), "DT"),
        _row(s, "Résultat de la Période", round(gl["resultat"], 2), "DT"),
    ]


# ─── (v) Coûts unitaires ─────────────────────────────────────────────────────

def _couts_unitaires(debut, fin, gl, alim_ctx, prod_ctx):
    from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import _kpi_ind

    prod = prod_ctx["prod"]
    vl = prod_ctx["vl"]
    frais_alim = alim_ctx["frais_alim_total"]
    jours = max((fin - debut).days + 1, 1)

    cout_alim_l = round(frais_alim / prod, 3) if prod else 0
    cout_complet_l = round(gl["charges"] / prod, 3) if prod else 0
    cout_hors_amort_l = (round((gl["charges"] - gl["amortissements"]) / prod, 3)
                         if prod else 0)
    iofc = gl["ca_lait"] - frais_alim
    iofc_vl_jour = round(iofc / vl / jours, 2) if vl else 0

    cout_alim_ind = _kpi_ind(
        cout_alim_l or None,
        green_max=float(get_config("objectif_cout_litre", default=0.65)),
        orange_max=float(get_config("objectif_cout_litre_alarme", default=0.85)),
    )
    iofc_ind = _kpi_ind(
        iofc_vl_jour or None,
        green_min=float(get_config("pfe_iofc_jour_min", default=3.0)),
        orange_min=float(get_config("pfe_iofc_jour_orange_min", default=1.5)),
    )

    s = "Coûts Unitaires"
    return [
        _row(s, "Coût Alimentaire / L", cout_alim_l, "DT/L",
             indicator=cout_alim_ind),
        _row(s, "Coût Complet / L (toutes charges)", cout_complet_l, "DT/L"),
        _row(s, "Coût du Litre hors Amortissement", cout_hors_amort_l, "DT/L"),
        _row(s, "IOFC (Income Over Feed Cost) — CA Lait − Coût Alimentaire",
             round(iofc, 2), "DT"),
        _row(s, "IOFC (Income Over Feed Cost) / Vache Lactante / Jour",
             iofc_vl_jour, "DT/VL/j", indicator=iofc_ind),
    ]
