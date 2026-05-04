"""
Rapport Reproduction — Multi-section report (modeled after Rapport Mensuel).
Each section reads LIVE data from Animal + linked event tables (Velage,
Lactation, Insemination, Avortement), with all event lookups capped at the
selected date_filter so the report reflects "as of date X".

Cohort: every active VACHE/GENISSE present on date_filter (born/entered ≤
date_filter, still in herd on date_filter — including cows since sold/dead
if their date_sortie > date_filter).
"""

import frappe
from frappe.utils import getdate, add_days, today, cint

from hmd_agro.hmd_agro.utils.report_format import normalize_precision

MOIS_FR = {1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
           5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
           9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"}


@normalize_precision
def execute(filters=None):
    filters = filters or {}
    date = getdate(filters.get("date") or today())
    section = filters.get("section") or "Reproduction"

    ctx = {"date_filter": date}

    builders = {
        "Reproduction": _reproduction,
        "Performance IA": _performance_ia,
        "Bilan Annuel": _bilan_annuel,
        # Future sections: "Naissances", "Sorties", ...
    }
    return builders.get(section, _reproduction)(ctx)


# ─── Section 1: Reproduction (per-cow live state, capped at date_filter) ────

def _reproduction(ctx):
    date_filter = ctx["date_filter"]
    columns = _reproduction_columns()

    if date_filter > getdate(today()):
        return columns, [{"nom_metier": "Pas encore de données pour cette date.",
                          "is_total": True}]

    # 1. Cohort — every cow/génisse present on date_filter
    animals = frappe.db.sql("""
        SELECT name, nom_metier, categorie, sexe,
               date_naissance, date_entree, est_achat, id_pere
        FROM `tabAnimal`
        WHERE categorie IN ('VACHE', 'GENISSE')
          AND (CASE WHEN est_achat = 1 THEN date_entree ELSE date_naissance END) <= %s
          AND (statut = 'ACTIF' OR (date_sortie IS NOT NULL AND date_sortie > %s))
    """, (date_filter, date_filter), as_dict=True)

    if not animals:
        return columns, []

    animal_names = [a.name for a in animals]

    # 2. All velages per cow (sorted ASC for IVV computation)
    velages_by_cow = {}
    for r in frappe.db.sql("""
        SELECT animal, date_velage FROM `tabVelage`
        WHERE date_velage <= %s AND animal IN %s
        ORDER BY date_velage ASC
    """, (date_filter, animal_names), as_dict=True):
        velages_by_cow.setdefault(r.animal, []).append(getdate(r.date_velage))

    # 3. Latest lactation + nb lactations + production lifetime (incl. PIC)
    latest_lact = {}
    nb_lactations = {}
    prod_vie = {}
    for r in frappe.db.sql("""
        SELECT animal, name, numero_lactation, date_debut, date_tarissement,
               statut, production_totale, lactation_305j, pic_production
        FROM `tabLactation`
        WHERE date_debut <= %s AND animal IN %s
        ORDER BY date_debut DESC
    """, (date_filter, animal_names), as_dict=True):
        if r.animal not in latest_lact:
            latest_lact[r.animal] = r
        nb_lactations[r.animal] = nb_lactations.get(r.animal, 0) + 1
        prod_vie[r.animal] = prod_vie.get(r.animal, 0) + float(r.production_totale or 0)

    # 4. IA history: latest IA + last REUSSIE + all IA dates for cycle counting
    last_ia = {}
    last_reussie = {}
    ia_dates_by_cow = {}
    for r in frappe.db.sql("""
        SELECT animal, date_ia, resultat FROM `tabInsemination`
        WHERE date_ia <= %s AND animal IN %s
        ORDER BY date_ia DESC
    """, (date_filter, animal_names), as_dict=True):
        if r.animal not in last_ia:
            last_ia[r.animal] = r
        if r.resultat == "REUSSIE" and r.animal not in last_reussie:
            last_reussie[r.animal] = r
        ia_dates_by_cow.setdefault(r.animal, []).append(getdate(r.date_ia))

    # 5. Latest vêlage's calf info (sex + alive flag, twin-aware)
    last_calf = {}
    for r in frappe.db.sql("""
        SELECT v.animal, v.nombre_veaux, v.sexe_veau1, v.vivant_veau1,
               v.sexe_veau2, v.vivant_veau2
        FROM `tabVelage` v
        INNER JOIN (
            SELECT animal, MAX(date_velage) AS max_d FROM `tabVelage`
            WHERE date_velage <= %s GROUP BY animal
        ) m ON v.animal = m.animal AND v.date_velage = m.max_d
        WHERE v.animal IN %s
    """, (date_filter, animal_names), as_dict=True):
        last_calf[r.animal] = r

    # 6. Last avortement (invalidates a REUSSIE IA before it)
    last_avortement = {}
    for r in frappe.db.sql("""
        SELECT animal, MAX(date_avortement) AS d FROM `tabAvortement`
        WHERE date_avortement <= %s AND animal IN %s GROUP BY animal
    """, (date_filter, animal_names), as_dict=True):
        last_avortement[r.animal] = getdate(r.d)

    # 7. Père names (id_pere → Taureau.nom)
    pere_ids = list({a.id_pere for a in animals if a.id_pere})
    pere_names = {}
    if pere_ids:
        for r in frappe.db.sql("""
            SELECT name, nom_taureau FROM `tabTaureau` WHERE name IN %s
        """, (pere_ids,), as_dict=True):
            pere_names[r.name] = r.nom_taureau or r.name

    rows = [_build_row(a, date_filter, velages_by_cow, latest_lact, nb_lactations,
                       prod_vie, last_ia, last_reussie, ia_dates_by_cow,
                       last_avortement, pere_names, last_calf) for a in animals]

    # Sort by catégorie (VACHE first, then GENISSE) then nom_metier
    rows.sort(key=lambda r: (0 if r["categorie"] == "VACHE" else 1, r["nom_metier"] or ""))
    return columns, rows


def _build_row(a, date_filter, velages_by_cow, latest_lact, nb_lactations,
               prod_vie, last_ia, last_reussie, ia_dates_by_cow,
               last_avortement, pere_names, last_calf):
    velages = velages_by_cow.get(a.name, [])
    last_vel = velages[-1] if velages else None
    first_vel = velages[0] if velages else None

    # IVV (vêlage-vêlage interval, days)
    ivv_list = [(velages[i] - velages[i-1]).days for i in range(1, len(velages))]
    avg_ivv = round(sum(ivv_list) / len(ivv_list)) if ivv_list else None
    last_ivv = ivv_list[-1] if ivv_list else None

    # Lactation status as of date_filter (from latest lactation ≤ date_filter)
    lact = latest_lact.get(a.name)
    etat_lact = ""
    dim = None
    if lact:
        if lact.date_tarissement and getdate(lact.date_tarissement) <= date_filter:
            etat_lact = "TARIE"
        else:
            etat_lact = "EN_PRODUCTION"
            dim = (date_filter - getdate(lact.date_debut)).days

    # Gestation status: REUSSIE IA strictly after the last velage AND last avortement
    etat_gest = "VIDE"
    date_ia_feco = None
    jours_gest = None
    date_velage_prevue = None
    lr = last_reussie.get(a.name)
    if lr:
        ia_d = getdate(lr.date_ia)
        after_velage = (last_vel is None) or (ia_d > last_vel)
        after_avo = (a.name not in last_avortement) or (ia_d > last_avortement[a.name])
        if after_velage and after_avo:
            etat_gest = "GESTANTE"
            date_ia_feco = ia_d
            jours_gest = (date_filter - ia_d).days
            date_velage_prevue = add_days(ia_d, 280)

    # IAs done in the current reproductive cycle (since last vêlage; for heifers,
    # since birth). Sorted ascending, padded to 5 fixed columns IA1..IA5.
    cycle_start = last_vel if last_vel else getdate(a.date_naissance)
    cycle_ias = sorted(d for d in ia_dates_by_cow.get(a.name, []) if d >= cycle_start)
    nb_ia_cycle = len(cycle_ias)
    ia_slots = (cycle_ias + [None] * 5)[:5]

    # V-IA1 = days from last vêlage to first IA of cycle (return-to-estrus signal)
    # V-Iad = days from last vêlage to fécondante IA (total open period)
    v_ia1 = (cycle_ias[0] - last_vel).days if (last_vel and cycle_ias) else None
    v_iad = (date_ia_feco - last_vel).days if (last_vel and date_ia_feco) else None

    # Catégorie as of date_filter (heifer becomes vache after first vêlage)
    cat_now = "VACHE" if last_vel else "GENISSE"

    # Age at first vêlage (in months)
    age_1er = None
    if first_vel and a.date_naissance:
        age_1er = round((first_vel - getdate(a.date_naissance)).days / 30, 1)

    # Statut reproduction (derived label for the farmer)
    statut_repro = _statut_repro(cat_now, etat_lact, etat_gest, jours_gest,
                                 last_vel, date_filter, last_ia.get(a.name))

    # Compact "Dernier né" label: "F ✓" / "M ✗" / "Twins F+M ✓✗" etc.
    dernier_ne = ""
    cf = last_calf.get(a.name)
    if cf:
        s1 = "F" if cf.sexe_veau1 == "F" else ("M" if cf.sexe_veau1 == "M" else "?")
        m1 = "✓" if cf.vivant_veau1 else "✗"
        if str(cf.nombre_veaux) == "2" and cf.sexe_veau2:
            s2 = "F" if cf.sexe_veau2 == "F" else "M"
            m2 = "✓" if cf.vivant_veau2 else "✗"
            dernier_ne = f"{s1}+{s2} {m1}{m2}"
        else:
            dernier_ne = f"{s1} {m1}"

    li = last_ia.get(a.name)
    return {
        "nom_metier": a.nom_metier or a.name[-4:],
        "categorie": cat_now,
        "date_naissance": a.date_naissance,
        "age_1er_velage": age_1er,
        "numero_lactation": nb_lactations.get(a.name, 0),
        "date_dernier_velage": last_vel,
        "dim": dim,
        "etat_lactation": etat_lact,
        "etat_gestation": etat_gest,
        "date_derniere_ia": getdate(li.date_ia) if li else None,
        "resultat_derniere_ia": li.resultat if li else None,
        "nb_ia_cycle": nb_ia_cycle,
        "ia1": ia_slots[0],
        "ia2": ia_slots[1],
        "ia3": ia_slots[2],
        "ia4": ia_slots[3],
        "ia5": ia_slots[4],
        "v_ia1": v_ia1,
        "v_iad": v_iad,
        "date_ia_feco": date_ia_feco,
        "jours_gestation": jours_gest,
        "date_velage_prevue": date_velage_prevue,
        "ivv_moyen": avg_ivv,
        "dernier_ivv": last_ivv,
        "production_lact_actuelle": round(float(lact.production_totale or 0), 1) if lact else None,
        "production_305j": round(float(lact.lactation_305j or 0), 1) if lact else None,
        "pic_production": round(float(lact.pic_production or 0), 1) if lact and lact.pic_production else None,
        "production_totale_vie": round(prod_vie.get(a.name, 0), 1),
        "dernier_ne": dernier_ne,
        "pere": pere_names.get(a.id_pere, "") if a.id_pere else "",
        "statut_repro": statut_repro,
    }


def _statut_repro(cat, etat_lact, etat_gest, jours_gest, last_vel, date_filter, last_ia):
    """Derive a human-readable reproduction status label."""
    if etat_gest == "GESTANTE":
        if jours_gest and jours_gest > 220:
            return "Gestante (proche tarissement)"
        return "Gestante"
    if etat_lact == "TARIE":
        return "Tarie"
    if cat == "GENISSE":
        return "Génisse vide"
    # VACHE vide — flag long delays since vêlage
    if last_vel and (date_filter - last_vel).days > 90:
        return "Vide >90j (à insémener)"
    return "Vide (à insémener)"


def _reproduction_columns():
    return [
        {"fieldname": "nom_metier", "label": "N° Travail", "fieldtype": "Data", "width": 95},
        {"fieldname": "categorie", "label": "Cat.", "fieldtype": "Data", "width": 70},
        {"fieldname": "date_naissance", "label": "Naissance", "fieldtype": "Date", "width": 90},
        {"fieldname": "age_1er_velage", "label": "Age V1 (mois)", "fieldtype": "Float", "precision": 1, "width": 95},
        {"fieldname": "numero_lactation", "label": "N° Lact°", "fieldtype": "Int", "width": 70},
        {"fieldname": "date_dernier_velage", "label": "Dernier Vêlage", "fieldtype": "Date", "width": 105},
        {"fieldname": "dim", "label": "DIM (j)", "fieldtype": "Int", "width": 70},
        {"fieldname": "etat_lactation", "label": "État Lactation", "fieldtype": "Data", "width": 115},
        {"fieldname": "etat_gestation", "label": "État Gest.", "fieldtype": "Data", "width": 95},
        {"fieldname": "date_derniere_ia", "label": "Dernière IA", "fieldtype": "Date", "width": 100},
        {"fieldname": "resultat_derniere_ia", "label": "Résultat IA", "fieldtype": "Data", "width": 100},
        {"fieldname": "nb_ia_cycle", "label": "Nb IA / Cycle", "fieldtype": "Int", "width": 95},
        {"fieldname": "ia1", "label": "IA1", "fieldtype": "Date", "width": 90},
        {"fieldname": "ia2", "label": "IA2", "fieldtype": "Date", "width": 90},
        {"fieldname": "ia3", "label": "IA3", "fieldtype": "Date", "width": 90},
        {"fieldname": "ia4", "label": "IA4", "fieldtype": "Date", "width": 90},
        {"fieldname": "ia5", "label": "IA5", "fieldtype": "Date", "width": 90},
        {"fieldname": "v_ia1", "label": "V-IA1 (j)", "fieldtype": "Int", "width": 80},
        {"fieldname": "v_iad", "label": "V-Iad (j)", "fieldtype": "Int", "width": 80},
        {"fieldname": "date_ia_feco", "label": "IA Fécondante", "fieldtype": "Date", "width": 105},
        {"fieldname": "jours_gestation", "label": "J Gest°", "fieldtype": "Int", "width": 75},
        {"fieldname": "date_velage_prevue", "label": "Vêlage Prévu", "fieldtype": "Date", "width": 105},
        {"fieldname": "ivv_moyen", "label": "IVV Moy", "fieldtype": "Int", "width": 80},
        {"fieldname": "dernier_ivv", "label": "Dernier IVV", "fieldtype": "Int", "width": 90},
        {"fieldname": "production_lact_actuelle", "label": "Prod Lact° (L)", "fieldtype": "Float", "precision": 0, "width": 105},
        {"fieldname": "production_305j", "label": "Prod 305j (L)", "fieldtype": "Float", "precision": 0, "width": 100},
        {"fieldname": "pic_production", "label": "PIC (L)", "fieldtype": "Float", "precision": 1, "width": 80},
        {"fieldname": "production_totale_vie", "label": "Prod Vie (L)", "fieldtype": "Float", "precision": 0, "width": 100},
        {"fieldname": "dernier_ne", "label": "Dernier né", "fieldtype": "Data", "width": 100},
        {"fieldname": "pere", "label": "Père", "fieldtype": "Data", "width": 110},
        {"fieldname": "statut_repro", "label": "Statut Reproduction", "fieldtype": "Data", "width": 180},
    ]


# ─── Section 2: Performance IA (monthly stats per IA attempt rank) ──────────

def _performance_ia(ctx):
    """Aggregate IA stats by month for the year of date_filter.
    Per month: NB IA at rank 1/2/3/>3, VG+ (REUSSIE count), success rate.
    Plus births (velles + veaux), losses, avortements. Mirrors Excel IA-25.
    """
    annee = ctx["date_filter"].year
    columns = _performance_ia_columns()

    if annee > getdate(today()).year:
        return columns, [{"mois": "Pas encore de données pour cette année.",
                          "is_total": True}], None, None, []

    rows = [_performance_ia_row(m, annee) for m in range(1, 13)]
    rows.append(_performance_ia_total(rows))

    chart = _performance_ia_chart(rows[:-1])
    summary = _performance_ia_summary(rows[-1], annee)
    return columns, rows, None, chart, summary


def _performance_ia_columns():
    return [
        {"fieldname": "mois", "label": "Le mois", "fieldtype": "Data", "width": 100},
        {"fieldname": "nb_velages", "label": "NB vêlage", "fieldtype": "Int", "width": 90},
        {"fieldname": "velles_nees", "label": "Velle Naissance", "fieldtype": "Int", "width": 110},
        {"fieldname": "velles_mortes", "label": "Velle Morte", "fieldtype": "Int", "width": 95},
        {"fieldname": "pct_perte_velles", "label": "% perte velles", "fieldtype": "Percent", "width": 95},
        {"fieldname": "veaux_nes", "label": "Veaux Naissance", "fieldtype": "Int", "width": 110},
        {"fieldname": "veaux_morts", "label": "Veaux Morts", "fieldtype": "Int", "width": 95},
        {"fieldname": "pct_perte_veaux", "label": "% perte veaux", "fieldtype": "Percent", "width": 95},
        {"fieldname": "nb_avortements", "label": "Avrtt", "fieldtype": "Int", "width": 70},
        {"fieldname": "nb_ia1", "label": "NB IA1", "fieldtype": "Int", "width": 75},
        {"fieldname": "vg_ia1", "label": "VG+ IA1", "fieldtype": "Int", "width": 80},
        {"fieldname": "pct_reussite_ia1", "label": "% réussite IA1", "fieldtype": "Percent", "width": 100},
        {"fieldname": "nb_ia2", "label": "NB IA2", "fieldtype": "Int", "width": 75},
        {"fieldname": "vg_ia2", "label": "VG+ IA2", "fieldtype": "Int", "width": 80},
        {"fieldname": "pct_reussite_ia2", "label": "% réussite IA2", "fieldtype": "Percent", "width": 100},
        {"fieldname": "nb_ia3", "label": "NB IA3", "fieldtype": "Int", "width": 75},
        {"fieldname": "vg_ia3", "label": "VG+ IA3", "fieldtype": "Int", "width": 80},
        {"fieldname": "pct_reussite_ia3", "label": "% réussite IA3", "fieldtype": "Percent", "width": 100},
        {"fieldname": "nb_ia_sup", "label": "NB >IA3", "fieldtype": "Int", "width": 80},
        {"fieldname": "vg_ia_sup", "label": "VG+ >IA3", "fieldtype": "Int", "width": 85},
        {"fieldname": "pct_reussite_ia_sup", "label": "% réussite >IA3", "fieldtype": "Percent", "width": 110},
        {"fieldname": "nb_ia_total", "label": "NB IA Global", "fieldtype": "Int", "width": 100},
        {"fieldname": "vg_total", "label": "VG+ Global", "fieldtype": "Int", "width": 95},
        {"fieldname": "pct_reussite_global", "label": "% réussite Global", "fieldtype": "Percent", "width": 115},
    ]


def _performance_ia_row(mois, annee):
    velages = frappe.db.sql("""
        SELECT nombre_veaux, sexe_veau1, vivant_veau1, sexe_veau2, vivant_veau2
        FROM `tabVelage`
        WHERE MONTH(date_velage) = %s AND YEAR(date_velage) = %s
    """, (mois, annee), as_dict=True)

    nb_velages = len(velages)
    velles_nees = velles_mortes = veaux_nes = veaux_morts = 0
    for v in velages:
        if v.sexe_veau1 == "F":
            velles_nees += 1
            if not v.vivant_veau1:
                velles_mortes += 1
        elif v.sexe_veau1 == "M":
            veaux_nes += 1
            if not v.vivant_veau1:
                veaux_morts += 1
        if cint(v.nombre_veaux) >= 2:
            if v.sexe_veau2 == "F":
                velles_nees += 1
                if not v.vivant_veau2:
                    velles_mortes += 1
            elif v.sexe_veau2 == "M":
                veaux_nes += 1
                if not v.vivant_veau2:
                    veaux_morts += 1

    nb_avortements = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabAvortement`
        WHERE MONTH(date_avortement) = %s AND YEAR(date_avortement) = %s
    """, (mois, annee))[0][0]

    ia_stats = frappe.db.sql("""
        SELECT
            CASE WHEN numero_ia = 1 THEN 1
                 WHEN numero_ia = 2 THEN 2
                 WHEN numero_ia = 3 THEN 3
                 ELSE 4 END AS rang,
            COUNT(*) AS nb,
            SUM(CASE WHEN resultat = 'REUSSIE' THEN 1 ELSE 0 END) AS vg
        FROM `tabInsemination`
        WHERE MONTH(date_ia) = %s AND YEAR(date_ia) = %s
        GROUP BY rang
    """, (mois, annee), as_dict=True)

    ia_map = {s.rang: s for s in ia_stats}
    nb_ia1 = (ia_map.get(1) or {}).get("nb", 0) or 0
    vg_ia1 = (ia_map.get(1) or {}).get("vg", 0) or 0
    nb_ia2 = (ia_map.get(2) or {}).get("nb", 0) or 0
    vg_ia2 = (ia_map.get(2) or {}).get("vg", 0) or 0
    nb_ia3 = (ia_map.get(3) or {}).get("nb", 0) or 0
    vg_ia3 = (ia_map.get(3) or {}).get("vg", 0) or 0
    nb_ia_sup = (ia_map.get(4) or {}).get("nb", 0) or 0
    vg_ia_sup = (ia_map.get(4) or {}).get("vg", 0) or 0

    nb_ia_total = nb_ia1 + nb_ia2 + nb_ia3 + nb_ia_sup
    vg_total = vg_ia1 + vg_ia2 + vg_ia3 + vg_ia_sup

    return {
        "mois": MOIS_FR[mois],
        "nb_velages": nb_velages,
        "velles_nees": velles_nees, "velles_mortes": velles_mortes,
        "pct_perte_velles": _pct(velles_mortes, velles_nees),
        "veaux_nes": veaux_nes, "veaux_morts": veaux_morts,
        "pct_perte_veaux": _pct(veaux_morts, veaux_nes),
        "nb_avortements": nb_avortements,
        "nb_ia1": nb_ia1, "vg_ia1": vg_ia1, "pct_reussite_ia1": _pct(vg_ia1, nb_ia1),
        "nb_ia2": nb_ia2, "vg_ia2": vg_ia2, "pct_reussite_ia2": _pct(vg_ia2, nb_ia2),
        "nb_ia3": nb_ia3, "vg_ia3": vg_ia3, "pct_reussite_ia3": _pct(vg_ia3, nb_ia3),
        "nb_ia_sup": nb_ia_sup, "vg_ia_sup": vg_ia_sup, "pct_reussite_ia_sup": _pct(vg_ia_sup, nb_ia_sup),
        "nb_ia_total": nb_ia_total, "vg_total": vg_total,
        "pct_reussite_global": _pct(vg_total, nb_ia_total),
    }


def _performance_ia_total(monthly_rows):
    sums = {k: 0 for k in [
        "nb_velages", "velles_nees", "velles_mortes", "veaux_nes", "veaux_morts",
        "nb_avortements", "nb_ia1", "vg_ia1", "nb_ia2", "vg_ia2",
        "nb_ia3", "vg_ia3", "nb_ia_sup", "vg_ia_sup", "nb_ia_total", "vg_total",
    ]}
    for r in monthly_rows:
        for k in sums:
            sums[k] += r.get(k) or 0
    return {
        "mois": "TOTAL", "is_total": True, **sums,
        "pct_perte_velles": _pct(sums["velles_mortes"], sums["velles_nees"]),
        "pct_perte_veaux": _pct(sums["veaux_morts"], sums["veaux_nes"]),
        "pct_reussite_ia1": _pct(sums["vg_ia1"], sums["nb_ia1"]),
        "pct_reussite_ia2": _pct(sums["vg_ia2"], sums["nb_ia2"]),
        "pct_reussite_ia3": _pct(sums["vg_ia3"], sums["nb_ia3"]),
        "pct_reussite_ia_sup": _pct(sums["vg_ia_sup"], sums["nb_ia_sup"]),
        "pct_reussite_global": _pct(sums["vg_total"], sums["nb_ia_total"]),
    }


def _pct(num, denom):
    return round((num / denom) * 100, 1) if denom else 0


def _performance_ia_chart(monthly_rows):
    return {
        "data": {
            "labels": [r["mois"][:3] for r in monthly_rows],
            "datasets": [
                {"name": "% IA1", "values": [r["pct_reussite_ia1"] for r in monthly_rows]},
                {"name": "% IA2", "values": [r["pct_reussite_ia2"] for r in monthly_rows]},
                {"name": "% IA3", "values": [r["pct_reussite_ia3"] for r in monthly_rows]},
                {"name": "% Global", "values": [r["pct_reussite_global"] for r in monthly_rows]},
            ],
        },
        "type": "line",
        "colors": ["#48bb78", "#4299e1", "#ed8936", "#9f7aea"],
    }


def _performance_ia_summary(total_row, annee):
    veaux_vivants = ((total_row["velles_nees"] - total_row["velles_mortes"]) +
                     (total_row["veaux_nes"] - total_row["veaux_morts"]))
    total_naissances = total_row["velles_nees"] + total_row["veaux_nes"]
    total_morts = total_row["velles_mortes"] + total_row["veaux_morts"]
    return [
        {"value": total_row["nb_velages"], "label": f"Vêlages {annee}", "datatype": "Int"},
        {"value": veaux_vivants, "label": "Veaux + velles vivants", "datatype": "Int"},
        {"value": _pct(total_morts, total_naissances), "label": "% perte global", "datatype": "Percent"},
        {"value": total_row["pct_reussite_global"], "label": "% réussite IA global", "datatype": "Percent"},
    ]


# ─── Section 3: Bilan Annuel (year-by-year multi-year comparison) ───────────

def _bilan_annuel(ctx):
    """One row per year from earliest event year up to date_filter.year.
    Current year is partial (Jan 1 → date_filter); past years are full
    (Jan 1 → Dec 31). Mirrors Excel BILAN_annuel."""
    from hmd_agro.hmd_agro.utils.live_state import effectif_on_date
    from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import _aliment_data_per_lot

    # Cap at today so future date_filter doesn't produce phantom future-year rows
    date_filter = min(ctx["date_filter"], getdate(today()))
    current_year = date_filter.year

    # Earliest year that has any reproductive event in the system
    earliest = frappe.db.sql("""
        SELECT MIN(d) FROM (
            SELECT MIN(date_velage) AS d FROM `tabVelage`
            UNION SELECT MIN(date_ia) FROM `tabInsemination`
            UNION SELECT MIN(date_avortement) FROM `tabAvortement`
            UNION SELECT MIN(date_naissance) FROM `tabAnimal`
        ) AS x WHERE d IS NOT NULL
    """)[0][0]

    columns = _bilan_annuel_columns()
    if not earliest:
        return columns, []

    earliest_year = getdate(earliest).year
    rows = []
    for year in range(earliest_year, current_year + 1):
        year_start = getdate(f"{year}-01-01")
        year_end = date_filter if year == current_year else getdate(f"{year}-12-31")
        rows.append(_bilan_year_row(year, year_start, year_end,
                                    is_partial=(year == current_year),
                                    effectif_fn=effectif_on_date,
                                    aliment_fn=_aliment_data_per_lot))
    return columns, rows


def _bilan_year_row(year, start, end, is_partial, effectif_fn, aliment_fn):
    # Vêlages + births breakdown
    velages = frappe.db.sql("""
        SELECT nombre_veaux, sexe_veau1, vivant_veau1, sexe_veau2, vivant_veau2
        FROM `tabVelage` WHERE date_velage BETWEEN %s AND %s
    """, (start, end), as_dict=True)
    nb_velages = len(velages)
    velles_nees = velles_mortes = veaux_nes = veaux_morts = 0
    for v in velages:
        if v.sexe_veau1 == "F":
            velles_nees += 1
            if not v.vivant_veau1:
                velles_mortes += 1
        elif v.sexe_veau1 == "M":
            veaux_nes += 1
            if not v.vivant_veau1:
                veaux_morts += 1
        if cint(v.nombre_veaux) >= 2:
            if v.sexe_veau2 == "F":
                velles_nees += 1
                if not v.vivant_veau2:
                    velles_mortes += 1
            elif v.sexe_veau2 == "M":
                veaux_nes += 1
                if not v.vivant_veau2:
                    veaux_morts += 1
    morts_total = velles_mortes + veaux_morts
    nes_total = velles_nees + veaux_nes
    pct_perte = _pct(morts_total, nes_total)

    # Avortements
    nb_avo = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabAvortement` WHERE date_avortement BETWEEN %s AND %s",
        (start, end))[0][0]

    # IAs total + reussies
    ia = frappe.db.sql("""
        SELECT COUNT(*) AS n,
               SUM(CASE WHEN resultat='REUSSIE' THEN 1 ELSE 0 END) AS r
        FROM `tabInsemination` WHERE date_ia BETWEEN %s AND %s
    """, (start, end), as_dict=True)[0]
    nb_ia = int(ia.n or 0)
    nb_ia_r = int(ia.r or 0)
    pct_ia = _pct(nb_ia_r, nb_ia)

    # Effectif at end of period (Dec 31 for past years, date_filter for current)
    eff = effectif_fn(end)
    vp = eff["Vaches - Lact."] + eff["Vaches - Tarie"]
    vl = eff["Vaches - Lact."]

    # V-V moyen for the year (avg of all velage-velage intervals where the
    # second velage falls in the year)
    vv_intervals = []
    velage_dates = frappe.db.sql("""
        SELECT animal, date_velage FROM `tabVelage`
        WHERE animal IN (
            SELECT DISTINCT animal FROM `tabVelage`
            WHERE date_velage BETWEEN %s AND %s
        )
        ORDER BY animal, date_velage ASC
    """, (start, end), as_dict=True)
    by_cow = {}
    for r in velage_dates:
        by_cow.setdefault(r.animal, []).append(getdate(r.date_velage))
    for cow, vels in by_cow.items():
        for i in range(1, len(vels)):
            if start <= vels[i] <= end:
                vv_intervals.append((vels[i] - vels[i-1]).days)
    vv_moy = round(sum(vv_intervals) / len(vv_intervals)) if vv_intervals else None

    # Production totale (L)
    prod = float(frappe.db.sql(
        "SELECT SUM(quantite_litres) FROM `tabTraite` WHERE date_traite BETWEEN %s AND %s",
        (start, end))[0][0] or 0)

    # Concentré + MS via the shared per-day reconstruction
    d = aliment_fn(start, end)
    concentre = (d or {}).get("cumulative_concentre_cheptel", 0)

    return {
        "annee": f"{year}{' *' if is_partial else ''}",
        "nb_velages": nb_velages,
        "nb_avortements": nb_avo,
        "velles_nees": velles_nees,
        "veaux_nes": veaux_nes,
        "pct_perte": pct_perte,
        "nb_ia": nb_ia,
        "pct_ia_global": pct_ia,
        "vp": vp,
        "vl": vl,
        "vv_moyen": vv_moy,
        "production_totale": round(prod, 1),
        "pl_par_vp": round(prod / vp, 1) if vp else 0,
        "pl_par_vl": round(prod / vl, 1) if vl else 0,
        "concentre_total": round(concentre, 1),
        "lc": round(prod / concentre, 2) if concentre else 0,
    }


def _bilan_annuel_columns():
    return [
        {"fieldname": "annee", "label": "Année", "fieldtype": "Data", "width": 80},
        {"fieldname": "nb_velages", "label": "Vêlages", "fieldtype": "Int", "width": 80},
        {"fieldname": "nb_avortements", "label": "Avortements", "fieldtype": "Int", "width": 95},
        {"fieldname": "velles_nees", "label": "Velles", "fieldtype": "Int", "width": 75},
        {"fieldname": "veaux_nes", "label": "Veaux", "fieldtype": "Int", "width": 75},
        {"fieldname": "pct_perte", "label": "% Perte Naiss.", "fieldtype": "Percent", "width": 105},
        {"fieldname": "nb_ia", "label": "NB IA", "fieldtype": "Int", "width": 75},
        {"fieldname": "pct_ia_global", "label": "% Réuss. IA", "fieldtype": "Percent", "width": 105},
        {"fieldname": "vp", "label": "VP", "fieldtype": "Int", "width": 70},
        {"fieldname": "vl", "label": "VL", "fieldtype": "Int", "width": 70},
        {"fieldname": "vv_moyen", "label": "V-V Moy (j)", "fieldtype": "Int", "width": 95},
        {"fieldname": "production_totale", "label": "PL Totale (L)", "fieldtype": "Float", "precision": 0, "width": 110},
        {"fieldname": "pl_par_vp", "label": "PL/VP (L)", "fieldtype": "Float", "precision": 0, "width": 95},
        {"fieldname": "pl_par_vl", "label": "PL/VL (L)", "fieldtype": "Float", "precision": 0, "width": 95},
        {"fieldname": "concentre_total", "label": "Concentré (kg)", "fieldtype": "Float", "precision": 0, "width": 105},
        {"fieldname": "lc", "label": "L/C", "fieldtype": "Float", "precision": 2, "width": 80},
    ]
