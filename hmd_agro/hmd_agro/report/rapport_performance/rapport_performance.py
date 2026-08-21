"""
Rapport Performance (Phase 4) — synthèse hebdomadaire / mensuelle consolidée.

One flat table (section / indicateur / valeur / unite) covering the whole
farm for the selected period: mouvements cheptel, production laitière,
alimentation, charges comptables et coûts unitaires. `valeur` stays a typed
Float so the native CSV/Excel export feeds the Excel template cleanly
(réunion 05/08/2026 : export vers template Excel plutôt que PDF).

Sources — always the canonical primitives, never re-derived:
    live_state count_* / effectif_on_date     — herd events, reconstructed
    Traite / Bilan Lait Journalier            — production volumes
    rapport_periodique._aliment_data_per_lot  — SLE-based feed costs (lazy
                                                import, dashboard_kpis precedent)
    rapport_periodique.couverture_lait        — garde-fou « période incomplète »
    finance_kpis.gl_sums                      — GL sums per SCE family
    maintenance_utils.cout_maintenance        — équipement interventions
    maintenance_utils.cout_utilisation        — heures machine valorisées
                                                (vue ANALYTIQUE, cf. _charges)

A period with no postings honestly returns 0 — same stance as gl_sums.
"""
import frappe
from frappe.utils import add_days, getdate, today
from calendar import monthrange

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.finance_kpis import (
    ATELIER_FRAIS_GENERAUX, charges_lait, gl_sums, gl_sums_par_atelier,
)
from hmd_agro.hmd_agro.utils.live_state import (
    effectif_on_date, count_velages, count_naissances,
    count_avortements_mort_nes, count_achats, count_exits,
)
from hmd_agro.hmd_agro.utils.maintenance_utils import (
    cout_maintenance, cout_utilisation,
)


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

    # Garde-fou « période incomplète » (FIN-S95) — le rapport périodique possède
    # la lecture canonique de la couverture de saisie du lait (lazy import,
    # précédent dashboard_kpis).
    from hmd_agro.hmd_agro.report.rapport_periodique.rapport_periodique import (
        couverture_lait, neutraliser_indicateurs_lait,
    )
    couverture = couverture_lait(debut, fin)
    # Coût mécanique de la période — vue ANALYTIQUE, cf. _charges / maintenance_utils.
    meca = cout_utilisation(debut, fin)

    data = []
    data.extend(_mouvements_cheptel(debut, fin))
    prod_rows, prod_ctx = _production(debut, fin, couverture)
    data.extend(prod_rows)
    alim_rows, alim_ctx = _alimentation(debut, fin, prod_ctx["prod"])
    data.extend(alim_rows)
    gl = gl_sums(debut, fin)
    data.extend(_charges(debut, fin, gl, meca))
    # SCRUM-10 — l'axe atelier, jusqu'ici absent de toute lecture du Grand Livre.
    ventilation = gl_sums_par_atelier(debut, fin)
    data.extend(_charges_par_atelier(ventilation, gl))
    lait = charges_lait(debut, fin)
    data.extend(_cout_lait_detail(ventilation, lait))
    data.extend(_couts_unitaires(debut, fin, gl, alim_ctx, prod_ctx, meca, lait))

    # Trou de saisie avéré : on annonce la couleur en tête de tableau et on
    # éteint la coloration des ratios faussés — sans masquer une seule valeur.
    if not couverture["complete"]:
        neutraliser_indicateurs_lait(data)
        data.insert(0, _row("Avertissement", couverture["message"], None, ""))
    return COLUMNS, data


def _fr(valeur):
    """Nombre en écriture française (virgule décimale) pour les libellés."""
    return f"{valeur:g}".replace(".", ",")


def period_bounds(periode, date):
    """(debut, fin) of the period containing `date` — a single day, a full ISO
    week (Mon-Sun), a calendar fortnight (1-15 / 16-fin) or a full month.
    Les quatre granularités demandées en réunion (« journalier, hebdomadaire,
    par quinzaine… il faut que ce soit flexible »)."""
    if periode == "Jour":
        return date, date
    if periode == "Semaine":
        # Lazy import — rapport_periodique owns the canonical week-bounds helper
        # (same precedent as dashboard_kpis importing report internals).
        from hmd_agro.hmd_agro.report.rapport_periodique.rapport_periodique import (
            _iso_week_bounds,
        )
        return _iso_week_bounds(date)
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
        _row(s, f"L/C — Lait / Concentré (cible {_fr(cfg_lc_cible)})", lc, "L/kg",
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
    """Critères 1 et 5 — les charges ventilées par atelier, « non imputé » visible.

    Jusqu'ici la lecture du Grand Livre ignorait le centre de coût : les cinq
    ateliers existaient, les écritures les portaient, et personne ne s'en
    servait. Le coût complet au litre en payait le prix (cf. `_couts_unitaires`).

    Le poste « Non imputé » est affiché MÊME À ZÉRO. Une ligne absente se lit
    « rien à signaler » ; une ligne à 0 se lit « vérifié, il n'y en a pas ».
    Sur un rapport qui sert au rapprochement comptable, la nuance compte.

    La ligne de contrôle finale rejoue la somme : si la ventilation et le total
    du Grand Livre divergent, c'est visible à l'écran, pas seulement en test.
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


# ─── (iv ter) Coût du lait, ligne par ligne — SCRUM-10 ───────────────────────

def _cout_lait_detail(ventilation, lait):
    """Le coût du lait poste par poste, pour rapprochement comptable.

    Demande explicite de la revue reporting : « le rapport doit détailler le
    coût du lait ligne par ligne pour rapprochement comptable ». Un total seul
    ne se rapproche de rien — le comptable a besoin de retrouver ses comptes.

    Tous les postes sont affichés, y compris à zéro : la forme du tableau
    reste stable d'un mois à l'autre, sans quoi comparer deux mois oblige à
    réaligner les lignes à la main.
    """
    s = "Coût du Lait (détail)"
    rows = []
    for cle, libelle in ventilation["postes"]:
        rows.append(_row(s, libelle, round(lait["postes"].get(cle, 0.0), 2), "DT"))

    rows.append(_row(s, "Sous-total — charges directes atelier Lait",
                     lait["direct"], "DT"))
    if lait["perimetre"] == "LAIT_QUOTE_PART":
        rows.append(_row(
            s,
            f"Quote-part des charges générales ({ATELIER_FRAIS_GENERAUX}) — "
            f"clé {_fr(lait['cle_pct'])} % des charges directes",
            lait["quote_part"], "DT"))
    rows.append(_row(s, "TOTAL — charges retenues pour le coût du litre",
                     lait["total"], "DT"))
    if lait["non_impute"]:
        # Jamais réparti : imputer au lait une charge dont on ignore la
        # destination fabriquerait un coût de revient faux et invérifiable.
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
    # SCRUM-10 — le coût complet ne divise plus TOUTES les charges de la ferme
    # (génisses, cultures, traction, frais généraux compris) par les seuls
    # litres de lait : il retient le périmètre décidé en revue reporting.
    # L'ancien calcul restait consultable via le périmètre TOUTES_CHARGES.
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
