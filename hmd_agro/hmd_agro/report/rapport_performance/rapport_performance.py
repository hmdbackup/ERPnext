"""
Rapport Performance (Phase 4) — synthèse jour / semaine / quinzaine / mois /
année consolidée, avec colonnes comparatives.

One flat table (section / indicateur / valeur / précédent / écart % / unite)
covering the whole farm for the selected period: mouvements cheptel,
production laitière, alimentation, charges comptables, charges par atelier,
frais généraux répartis et coûts unitaires. `valeur` and `precedent` stay
typed Floats so the native CSV/Excel export feeds the Excel template cleanly
(réunion 05/08/2026 : export vers template Excel plutôt que PDF).

Comparatif (maquettes validées 24/08 et 26/08/2026) : chaque ligne porte la
valeur de la période précédente de même granularité (Veille / S-1 / Q-1 /
M-1 / A-1 même période) et l'écart en %. Les lignes se construisent une fois
par période (`_construire_lignes`) puis se fusionnent par (section,
indicateur) dans l'ordre de la période courante.

Sources — always the canonical primitives, never re-derived:
    live_state count_* / effectif_on_date     — herd events, reconstructed
    Traite / Bilan Lait Journalier            — production volumes
    rapport_periodique._aliment_data_per_lot  — SLE-based feed costs (lazy
                                                import, dashboard_kpis precedent)
    rapport_periodique.couverture_lait        — garde-fou « période incomplète »
    finance_kpis.gl_sums                      — GL sums per SCE family
    finance_kpis.repartitions_frais_generaux  — répartition saisie des FG
    maintenance_utils.cout_maintenance        — équipement interventions
    maintenance_utils.cout_utilisation        — heures machine valorisées
                                                (vue ANALYTIQUE, cf. _charges)

A period with no postings honestly returns 0 — same stance as gl_sums.
"""
import frappe
from frappe.utils import add_days, add_years, getdate, today
from calendar import monthrange

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.format_fr import fr_nombre
from hmd_agro.hmd_agro.utils.finance_kpis import (
    ATELIER_FRAIS_GENERAUX, ATELIER_LAIT, charges_lait, gl_sums,
    gl_sums_par_atelier, repartitions_frais_generaux,
)
from hmd_agro.hmd_agro.utils.live_state import (
    effectif_on_date, count_velages, count_naissances,
    count_avortements_mort_nes, count_achats, count_exits,
)
from hmd_agro.hmd_agro.utils.maintenance_utils import (
    cout_maintenance, cout_utilisation,
)
from hmd_agro.hmd_agro.utils.repartition_charges import est_mode_strict


PERIODE_ANNEE = "Année"

# Label of the « previous » column by granularity (mock-up 24/08).
LABELS_PRECEDENT = {
    "Jour": "Veille",
    "Semaine": "S-1",
    "Quinzaine": "Q-1",
    "Mois": "M-1",
    PERIODE_ANNEE: "A-1 (même période)",
}
# Suffix of that label when the current period is still running: the
# comparison then covers the same number of elapsed days, not the whole
# previous period (see `previous_period_bounds`).
SUFFIXE_JOURS_EGAUX = " (même nombre de jours)"

# Tolerated gap between the GL total of Frais Généraux and the sum of the
# splits: a rounding to the cent, not a business threshold.
ECART_ARRONDI_DT = 0.01

SECTION_FRAIS_GENERAUX = "Frais Généraux — répartition par atelier"


def _colonnes(periode, tronquee=False):
    label_precedent = LABELS_PRECEDENT.get(periode, "Précédent")
    if tronquee and periode != PERIODE_ANNEE:
        label_precedent += SUFFIXE_JOURS_EGAUX
    return [
        {"fieldname": "section", "label": "Section", "fieldtype": "Data", "width": 160},
        {"fieldname": "indicateur", "label": "Indicateur", "fieldtype": "Data", "width": 340},
        {"fieldname": "valeur", "label": "Valeur", "fieldtype": "Float", "precision": 2, "width": 130},
        {"fieldname": "precedent", "label": label_precedent,
         "fieldtype": "Float", "precision": 2, "width": 130},
        {"fieldname": "ecart_pct", "label": "Écart %", "fieldtype": "Percent", "precision": 1,
         "width": 100},
        {"fieldname": "unite", "label": "Unité", "fieldtype": "Data", "width": 120},
    ]


def execute(filters=None):
    filters = filters or {}
    periode = filters.get("periode") or "Mois"
    date = getdate(filters.get("date") or today())
    debut, fin = period_bounds(periode, date)

    today_dt = getdate(today())
    if debut > today_dt:
        return _colonnes(periode), [
            _row("INFO", "Pas encore de données pour cette période.", None, "")]
    # Only count days that actually happened (open week/month/year in progress).
    fin = min(fin, today_dt)
    colonnes = _colonnes(periode, tronquee=est_periode_tronquee(periode, debut, fin))

    lignes, couverture = _construire_lignes(debut, fin)
    debut_prec, fin_prec = previous_period_bounds(periode, debut, fin)
    lignes_prec, couverture_prec = _construire_lignes(debut_prec, fin_prec)
    data = _fusionner_comparatif(lignes, lignes_prec)

    # A proven gap in milk entries on either period: a Δ % computed on a
    # truncated figure compares nothing — switched off for the milk ratios.
    if not couverture_prec["complete"]:
        _neutraliser_comparatif_lait(data)
    if not couverture["complete"]:
        # Say so at the top of the table and switch off the colouring of the
        # distorted ratios — without hiding a single value.
        from hmd_agro.hmd_agro.report.rapport_periodique.rapport_periodique import (
            neutraliser_indicateurs_lait,
        )
        neutraliser_indicateurs_lait(data)
        _neutraliser_comparatif_lait(data)
        data.insert(0, _row("Avertissement", couverture["message"], None, ""))
    return colonnes, data


def _construire_lignes(debut, fin):
    """All the report rows for one period, plus the milk coverage of that
    period. Called once for the current period and once for the previous."""
    # « Incomplete period » guard (FIN-S95) — the periodic report owns the
    # canonical reading of milk entry coverage (lazy import, dashboard_kpis
    # precedent).
    from hmd_agro.hmd_agro.report.rapport_periodique.rapport_periodique import (
        couverture_lait,
    )
    couverture = couverture_lait(debut, fin)
    # Machine cost of the period — ANALYTICAL view, see _charges / maintenance_utils.
    meca = cout_utilisation(debut, fin)

    data = []
    data.extend(_mouvements_cheptel(debut, fin))
    prod_rows, prod_ctx = _production(debut, fin, couverture)
    data.extend(prod_rows)
    alim_rows, alim_ctx = _alimentation(debut, fin, prod_ctx["prod"])
    data.extend(alim_rows)
    gl = gl_sums(debut, fin)
    data.extend(_charges(debut, fin, gl, meca))
    # SCRUM-10 — the atelier axis, so far absent from every GL reading.
    ventilation = gl_sums_par_atelier(debut, fin)
    data.extend(_charges_par_atelier(ventilation, gl))
    repartitions = repartitions_frais_generaux(debut, fin, ventilation=ventilation)
    data.extend(_frais_generaux_repartition(repartitions))
    lait = charges_lait(debut, fin, repartitions=repartitions)
    data.extend(_cout_lait_detail(ventilation, lait))
    data.extend(_couts_unitaires(debut, fin, gl, alim_ctx, prod_ctx, meca, lait))
    return data, couverture


# ─── Comparatif ──────────────────────────────────────────────────────────────

def _fusionner_comparatif(lignes, lignes_precedentes):
    """Adds `precedent` / `ecart_pct` to each current row from the previous
    period's row of the same (section, indicateur). Each previous row is
    consumed once, so two identical labels (two charges with the same name)
    pair up in order instead of both reading the first one."""
    precedents = {}
    for ligne in lignes_precedentes:
        precedents.setdefault(_cle_ligne(ligne), []).append(ligne["valeur"])
    for ligne in lignes:
        if ligne.get("sans_comparatif"):
            continue
        candidats = precedents.get(_cle_ligne(ligne))
        ligne["precedent"] = candidats.pop(0) if candidats else None
        ligne["ecart_pct"] = _ecart_pct(ligne["valeur"], ligne["precedent"])
    return lignes


def _cle_ligne(ligne):
    return (ligne["section"], ligne["indicateur"])


def _ecart_pct(valeur, precedent):
    """(valeur − précédent) / |précédent| × 100 — None when there is nothing
    to compare against (previous absent or nul)."""
    if valeur is None or not precedent:
        return None
    return round((valeur - precedent) / abs(precedent) * 100, 1)


def _neutraliser_comparatif_lait(lignes):
    """Blanks `precedent` / `ecart_pct` on the milk-sensitive rows — the
    counterpart of `neutraliser_indicateurs_lait` for the comparison columns
    (a Δ % against a truncated period is noise, not information)."""
    from hmd_agro.hmd_agro.report.rapport_periodique.rapport_periodique import (
        INDICATEURS_SENSIBLES_LAIT,
    )
    for ligne in lignes:
        if (ligne.get("indicateur") or "").startswith(INDICATEURS_SENSIBLES_LAIT):
            ligne["precedent"] = None
            ligne["ecart_pct"] = None
    return lignes


# ─── Périodes ────────────────────────────────────────────────────────────────

def period_bounds(periode, date):
    """(debut, fin) of the period containing `date` — a single day, a full ISO
    week (Mon-Sun), a calendar fortnight (1-15 / 16-fin), a full month, or the
    year to date (1 January → `date`, meeting 26/08/2026: « l'année 2026,
    Year to Date »). The granularities asked for in the meeting (« journalier,
    hebdomadaire, par quinzaine… il faut que ce soit flexible »)."""
    if periode == "Jour":
        return date, date
    if periode == "Semaine":
        # Lazy import — rapport_periodique owns the canonical week-bounds helper
        # (same precedent as dashboard_kpis importing report internals).
        from hmd_agro.hmd_agro.report.rapport_periodique.rapport_periodique import (
            _iso_week_bounds,
        )
        return _iso_week_bounds(date)
    if periode == PERIODE_ANNEE:
        return getdate(f"{date.year}-01-01"), date
    nb_jours = monthrange(date.year, date.month)[1]
    if periode == "Quinzaine":
        if date.day <= 15:
            return (getdate(f"{date.year}-{date.month:02d}-01"),
                    getdate(f"{date.year}-{date.month:02d}-15"))
        return (getdate(f"{date.year}-{date.month:02d}-16"),
                getdate(f"{date.year}-{date.month:02d}-{nb_jours}"))
    debut = getdate(f"{date.year}-{date.month:02d}-01")
    fin = getdate(f"{date.year}-{date.month:02d}-{nb_jours}")
    return debut, fin


def est_periode_tronquee(periode, debut, fin):
    """True when [debut, fin] stops before the natural end of its period — the
    week / fortnight / month in progress, cut at today by `execute`. Année is
    year-to-date by construction and never counts as truncated here."""
    if periode == PERIODE_ANNEE:
        return False
    return fin < period_bounds(periode, debut)[1]


def previous_period_bounds(periode, debut, fin):
    """(debut, fin) of the comparison period for [debut, fin] : the previous
    period of the same granularity (Jour → the day before, Semaine /
    Quinzaine / Mois → the previous one, whole), and for Année the same
    interval one year earlier — a year-to-date only compares with the same
    year-to-date.

    When [debut, fin] is a period in progress (cut at today), the previous
    period is cut too, to the same number of elapsed days: 10 days of March
    against 10 days of February, not against the whole of February."""
    if periode == PERIODE_ANNEE:
        return add_years(debut, -1), add_years(fin, -1)
    debut_prec, fin_prec = period_bounds(periode, add_days(debut, -1))
    if est_periode_tronquee(periode, debut, fin):
        fin_prec = min(fin_prec, add_days(debut_prec, (fin - debut).days))
    return debut_prec, fin_prec


def _row(section, indicateur, valeur, unite, indicator="", sans_comparatif=False):
    row = {"section": section, "indicateur": indicateur,
           "valeur": valeur, "precedent": None, "ecart_pct": None,
           "unite": unite, "indicator": indicator}
    if sans_comparatif:
        # Unit rows (one charge and its « └ » split) never pair with the
        # previous period — see `_fusionner_comparatif`.
        row["sans_comparatif"] = True
    return row


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

def _production(debut, fin, couverture):
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
        # Toujours affichée : 31/31 rassure autant que 10/31 alerte, et sans
        # elle personne ne peut savoir si un ratio bas vient du troupeau ou
        # d'un retard de saisie.
        _row(s, "Couverture des Données (lait)", couverture["jours_saisis"],
             f"jours sur {couverture['jours_periode']}"),
    ]
    return rows, {"prod": prod, "vl": vl}


# ─── (iii) Alimentation ──────────────────────────────────────────────────────

def _alimentation(debut, fin, prod):
    """Feed costs + L/C, from the canonical SLE-based walker of the periodic
    report (lazy in-function import — dashboard_kpis precedent)."""
    from hmd_agro.hmd_agro.report.rapport_periodique.rapport_periodique import (
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
        _row(s, f"L/C — Lait / Concentré (cible {fr_nombre(cfg_lc_cible)})", lc, "L/kg",
             indicator=lc_ind),
    ]
    return rows, {"frais_alim_total": frais_total}


# ─── (iv) Charges ────────────────────────────────────────────────────────────

def _charges(debut, fin, gl, meca):
    """Charges de la période, lues au Grand Livre.

    FIN-S96 — les deux lignes mécaniques (« Heures d'Équipement », « Coût
    d'Utilisation Mécanique ») sont une vue ANALYTIQUE et NON une charge de
    plus : le coût horaire forfaitaire d'un équipement agrège amortissement +
    entretien + mazout, or ces trois-là sont DÉJÀ dans les charges ci-dessus
    (68x, 615, achats de carburant). Les additionner à « Charges Totales »
    compterait deux fois la même dépense — c'est pourquoi elles restent hors
    du total et pourquoi leur libellé le rappelle à l'écran.
    Voir l'encadré en tête de `utils/maintenance_utils.py`.
    """
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
        _row(s, "Heures d'Équipement", meca["heures"], "h"),
        _row(s, "Coût d'Utilisation Mécanique (vue analytique — déjà compris "
                "dans les charges ci-dessus, ne pas additionner)",
             round(meca["total"], 2), "DT"),
    ]


# ─── (iv bis) Charges par atelier — SCRUM-10 ─────────────────────────────────

def _charges_par_atelier(ventilation, gl):
    """Criteria 1 and 5 — charges broken down by atelier, « non imputé » visible.

    Until now the GL reading ignored the cost center: the five ateliers
    existed, the entries carried them, and nobody used them. The full cost
    per litre paid the price (see `_couts_unitaires`).

    The « Non imputé » line is shown EVEN AT ZERO. A missing line reads
    « nothing to report »; a line at 0 reads « checked, there is none ». On a
    report used for accounting reconciliation the nuance matters.

    The final control line replays the sum: if the breakdown and the GL total
    diverge, it shows on screen, not only in a test.
    """
    s = "Charges par Atelier"
    rows = []
    for nom, atelier in sorted(ventilation["ateliers"].items(),
                               key=lambda kv: -kv[1]["total"]):
        rows.append(_row(s, nom, round(atelier["total"], 2), "DT"))

    non_impute = round(ventilation["non_impute"]["total"], 2)
    rows.append(_row(
        s, "Non imputé — écriture sans atelier", non_impute, "DT",
        indicator="Orange" if non_impute else ""))

    ventile = round(ventilation["total"], 2)
    ecart = round(ventile - round(gl["charges"], 2), 2)
    rows.append(_row(
        s,
        "Total ventilé — doit égaler « Charges Totales »" if not ecart
        else "⚠ Total ventilé ≠ Charges Totales — écart à investiguer",
        ventile, "DT", indicator="" if not ecart else "Red"))
    return rows


# ─── (iv ter) Frais généraux — répartition par atelier — SCRUM-10 ────────────

def _frais_generaux_repartition(repartitions):
    """The Frais Généraux charges one by one, with the split the accountant
    typed on each (decision 26/08/2026: no more computed key).

    One charge per row (label — account, amount) followed by its split
    « └ Lait 45 % · Cultures 35 % … » — empty value, hence a dash: a part is
    not one more amount. A charge without a split is named, in orange: it
    stays on Frais Généraux and leaves the cost per litre.

    The final control replays the sum against the GL: red when strict mode is
    on (a bare charge is then an anomaly), orange otherwise.
    """
    s = SECTION_FRAIS_GENERAUX
    rows = []
    for charge in repartitions["charges"]:
        rows.append(_row(s, f"{charge['libelle']} — {charge['compte']}",
                         round(charge["montant"], 2), "DT", sans_comparatif=True))
        rows.append(_row(s, _libelle_parts(charge["repartition"]), None, "",
                         indicator="" if charge["repartition"] else "Orange",
                         sans_comparatif=True))

    total_fg = round(repartitions["total_fg"], 2)
    total_liste = round(repartitions.get("total_liste", total_fg), 2)
    reparti = round(repartitions["total_reparti"], 2)
    autres = round(repartitions.get("autres", 0.0), 2)
    rows.append(_row(s, "Total Frais Généraux (Grand Livre)", total_fg, "DT"))
    rows.append(_row(s, "Contrôle — somme des répartitions = charges listées", reparti,
                     "DT", indicator=_indicateur_controle_fg(total_liste - reparti)))
    rows.append(_row(s, f"dont part atelier {ATELIER_LAIT} — somme des répartitions",
                     repartitions["par_atelier"].get(ATELIER_LAIT, 0.0), "DT"))
    non_reparti = round(repartitions["non_reparti"], 2)
    if abs(non_reparti) > ECART_ARRONDI_DT:
        rows.append(_row(s, "Frais généraux non répartis — hors coût du litre",
                         non_reparti, "DT", indicator="Orange"))
    if abs(autres) > ECART_ARRONDI_DT:
        rows.append(_row(s, "Autres pièces imputées à Frais Généraux (stock, "
                         "avoirs…) — non répartissables ici",
                         autres, "DT", indicator="Orange"))
    return rows


def _libelle_parts(parts):
    if not parts:
        return f"└ non répartie — reste à {ATELIER_FRAIS_GENERAUX}, hors coût du litre"
    return "└ " + " · ".join(f"{p['atelier']} {fr_nombre(round(p['pct'], 2))} %"
                             for p in parts)


def _indicateur_controle_fg(ecart):
    if abs(ecart) <= ECART_ARRONDI_DT:
        return ""
    return "Red" if est_mode_strict() else "Orange"


# ─── (iv quater) Coût du lait, ligne par ligne — SCRUM-10 ────────────────────

def _cout_lait_detail(ventilation, lait):
    """The milk cost item by item, for accounting reconciliation.

    Explicit request of the reporting review: « le rapport doit détailler le
    coût du lait ligne par ligne pour rapprochement comptable ». A lone total
    reconciles with nothing — the accountant needs to find their accounts.

    Every item is shown, including at zero: the table keeps the same shape
    from one month to the next, otherwise comparing two months means
    realigning the rows by hand.
    """
    s = "Coût du Lait (détail)"
    rows = []
    for cle, libelle in ventilation["postes"]:
        rows.append(_row(s, libelle, round(lait["postes"].get(cle, 0.0), 2), "DT"))

    rows.append(_row(s, f"Sous-total — charges directes atelier {ATELIER_LAIT}",
                     lait["direct"], "DT"))
    if lait["perimetre"] == "LAIT_QUOTE_PART":
        rows.append(_row(
            s, f"Quote-part {ATELIER_FRAIS_GENERAUX} — somme des répartitions saisies",
            lait["quote_part"], "DT"))
    rows.append(_row(s, "TOTAL — charges retenues pour le coût du litre",
                     lait["total"], "DT"))
    if lait["non_impute"]:
        # Never split: charging the milk with a cost of unknown destination
        # would manufacture a false, unverifiable cost price.
        rows.append(_row(
            s, "Rappel — charges non imputées, exclues du coût du litre",
            lait["non_impute"], "DT", indicator="Orange"))
    return rows


# ─── (v) Coûts unitaires ─────────────────────────────────────────────────────

# Libellé du coût complet selon le périmètre retenu — il DOIT être à l'écran :
# le même nombre ne veut pas dire la même chose selon ce qu'on y a mis, et le
# lecteur n'a aucun moyen de le deviner.
_LIBELLE_PERIMETRE = {
    "LAIT_QUOTE_PART": "atelier Lait + quote-part des charges générales",
    "LAIT_SEUL": "atelier Lait seul",
    "TOUTES_CHARGES": "toutes charges de la ferme — surestimé pour le lait",
}


def _couts_unitaires(debut, fin, gl, alim_ctx, prod_ctx, meca, lait):
    from hmd_agro.hmd_agro.report.rapport_periodique.rapport_periodique import _kpi_ind

    prod = prod_ctx["prod"]
    vl = prod_ctx["vl"]
    frais_alim = alim_ctx["frais_alim_total"]
    jours = max((fin - debut).days + 1, 1)

    cout_alim_l = round(frais_alim / prod, 3) if prod else 0
    # FIN-S96 — le coût mécanique au litre est une CLÉ DE RÉPARTITION : il
    # n'entre PAS dans `cout_complet_l` (amortissement et entretien y sont déjà
    # via les charges du Grand Livre). Cf. `_charges` et maintenance_utils.
    cout_meca_l = round(meca["total"] / prod, 3) if prod else 0
    # SCRUM-10 — the full cost no longer divides ALL the farm's charges
    # (heifers, crops, traction, overheads included) by the milk litres alone:
    # it keeps the scope decided in the reporting review. The former figure
    # stays available through the TOUTES_CHARGES scope.
    charges_retenues = lait["total"]
    amort_lait = lait["postes"].get("amortissements", 0.0)
    cout_complet_l = round(charges_retenues / prod, 3) if prod else 0
    cout_hors_amort_l = (round((charges_retenues - amort_lait) / prod, 3)
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
        _row(s, "Coût Mécanique / L (vue analytique — non additionnable au "
                "coût complet)", cout_meca_l, "DT/L"),
        _row(s, f"Coût Complet / L ({_LIBELLE_PERIMETRE[lait['perimetre']]})",
             cout_complet_l, "DT/L"),
        _row(s, "Coût du Litre hors Amortissement", cout_hors_amort_l, "DT/L"),
        _row(s, "IOFC (Income Over Feed Cost) — CA Lait − Coût Alimentaire",
             round(iofc, 2), "DT"),
        _row(s, "IOFC (Income Over Feed Cost) / Vache Lactante / Jour",
             iofc_vl_jour, "DT/VL/j", indicator=iofc_ind),
    ]
