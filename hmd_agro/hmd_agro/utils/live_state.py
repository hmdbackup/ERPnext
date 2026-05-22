"""
Reconstruct animal states and Effectif report rows from live event doctypes.

Single source of truth: states_on_date / state_on_date walk Velage, Lactation,
Insemination, Avortement to compute each animal's (categorie, etat_lactation,
etat_gestation) at any past date — independent of the live Animal table
(which only stores 'right now').

Every count_* function uses these helpers for historical correctness.
Never read Animal.categorie/etat_lactation/etat_gestation directly for past dates.
"""

import frappe
from frappe.utils import getdate, add_days, cint

CATEGORIES = [
    "Vaches - Lact.", "Vaches - Tarie", "Gén. - Vide", "Gén. - Pleine",
    "Veaux", "Engraiss.", "Velles", "Total",
]

_SIMPLE_CAT = {"VEAU": "Veaux", "TAURILLON": "Engraiss.", "VELLE": "Velles"}


def resolve_col(cat, lact, gest):
    if cat == "VACHE":
        return "Vaches - Tarie" if lact == "TARIE" else "Vaches - Lact."
    if cat == "GENISSE":
        return "Gén. - Pleine" if gest == "GESTANTE" else "Gén. - Vide"
    return _SIMPLE_CAT.get(cat)


def empty_row():
    return {c: 0 for c in CATEGORIES}


def set_total(row):
    row["Total"] = sum(v for k, v in row.items() if k != "Total")


# ─── Historical state helpers ───────────────────────────────────────────────

def states_on_date(animal_names, date):
    """Compute (categorie, etat_lactation, etat_gestation) for many animals at date D.
    Returns {animal_name: (cat, lact, gest)} — only for animals PRESENT on D
    (born/entered <= D and not exited by end of D).

    Walks events (Velage, Lactation, Insemination, Avortement) — the Animal
    table is consulted only for the original categorie at insert (Veau/Velle/
    Engraiss never transition; Genisse may become Vache via a velage)."""
    if not animal_names:
        return {}
    date = getdate(date)
    d = str(date)

    db_rows = {r.name: r for r in frappe.db.sql("""
        SELECT name, categorie, est_achat, date_naissance, date_entree, statut, date_sortie
        FROM `tabAnimal` WHERE name IN %s
    """, (animal_names,), as_dict=True)}

    # Presence filter (end-of-D semantics): keep only animals in the herd on D.
    present = {}
    for name, a in db_rows.items():
        entry = a.date_entree if a.est_achat else a.date_naissance
        if not entry or getdate(entry) > date:
            continue
        if a.statut != "ACTIF" and (not a.date_sortie or getdate(a.date_sortie) <= date):
            continue
        present[name] = a
    if not present:
        return {}
    db_cats = {n: a.categorie for n, a in present.items()}
    animal_names = list(present.keys())

    # First ever velage per animal — promotes Genisse → Vache once it happens
    first_velage = {r.animal: r.first_vel for r in frappe.db.sql("""
        SELECT animal, MIN(date_velage) AS first_vel
        FROM `tabVelage` WHERE animal IN %s GROUP BY animal
    """, (animal_names,), as_dict=True)}

    # Most recent lactation starting on/before D — En production unless tarie by D
    lact_state = {}
    for r in frappe.db.sql("""
        SELECT l1.animal, l1.date_tarissement
        FROM `tabLactation` l1
        INNER JOIN (
            SELECT animal, MAX(date_debut) AS max_debut
            FROM `tabLactation` WHERE date_debut <= %s
            GROUP BY animal
        ) l2 ON l1.animal = l2.animal AND l1.date_debut = l2.max_debut
        WHERE l1.animal IN %s
    """, (d, animal_names), as_dict=True):
        if r.date_tarissement and getdate(r.date_tarissement) <= date:
            lact_state[r.animal] = "TARIE"
        else:
            lact_state[r.animal] = "EN_PRODUCTION"

    # Last successful IA on/before D
    last_ia = {r.animal: r.last_ia_date for r in frappe.db.sql("""
        SELECT animal, MAX(date_ia) AS last_ia_date
        FROM `tabInsemination`
        WHERE resultat = 'REUSSIE' AND date_ia <= %s AND animal IN %s
        GROUP BY animal
    """, (d, animal_names), as_dict=True)}

    # Last "end of gestation" event (Velage or Avortement) on/before D
    last_end = {}
    for r in frappe.db.sql("""
        SELECT animal, MAX(date_velage) AS last_end
        FROM `tabVelage` WHERE date_velage <= %s AND animal IN %s GROUP BY animal
    """, (d, animal_names), as_dict=True):
        last_end[r.animal] = r.last_end
    for r in frappe.db.sql("""
        SELECT animal, MAX(date_avortement) AS last_end
        FROM `tabAvortement` WHERE date_avortement <= %s AND animal IN %s GROUP BY animal
    """, (d, animal_names), as_dict=True):
        prev = last_end.get(r.animal)
        if not prev or r.last_end > prev:
            last_end[r.animal] = r.last_end

    result = {}
    for name in animal_names:
        cat = db_cats.get(name)
        if cat is None:
            continue
        # Animal.categorie is mutated by the Velage hook (Genisse → Vache),
        # so for adult females we must derive cat from event history alone.
        if cat in ("GENISSE", "VACHE"):
            fv = first_velage.get(name)
            cat = "VACHE" if (fv and getdate(fv) <= date) else "GENISSE"

        lact = lact_state.get(name, "") if cat == "VACHE" else ""

        gest = "VIDE"
        ia_date = last_ia.get(name)
        if ia_date:
            end_date = last_end.get(name)
            if not end_date or getdate(ia_date) > getdate(end_date):
                gest = "GESTANTE"

        result[name] = (cat, lact, gest)

    return result


def state_on_date(animal_name, date):
    """Single-animal convenience wrapper around states_on_date."""
    return states_on_date([animal_name], date).get(animal_name, (None, "", ""))


# ─── Effectif aggregates ─────────────────────────────────────────────────────

def lactantes_per_lot_on_date(date):
    """Per-lot breakdown of effectif_on_date(D)["Vaches - Lact."]. Composes the
    existing primitives — states_on_date for the cat+lact reconstruction
    (single source of truth, same logic as effectif_on_date) and lot_on_date
    for the cow's lot on D via the Allotement History audit log.

    Decouples effectif from production (Traite), so weekly reports keep a
    meaningful Effectif row on days where no traites have been entered yet."""
    from hmd_agro.hmd_agro.doctype.allotement_history.allotement_history import lot_on_date
    target_d = getdate(date)
    d = str(target_d)
    animal_names = [r[0] for r in frappe.db.sql("""
        SELECT name FROM `tabAnimal`
        WHERE (CASE WHEN est_achat = 1 THEN date_entree ELSE date_naissance END) <= %s
          AND (statut = 'ACTIF' OR (date_sortie IS NOT NULL AND date_sortie > %s))
    """, (d, d))]
    states = states_on_date(animal_names, target_d)
    per_lot = {}
    for name, (cat, lact, _) in states.items():
        if cat != "VACHE" or lact != "EN_PRODUCTION":
            continue
        lot = lot_on_date(name, target_d)
        if lot:
            per_lot[lot] = per_lot.get(lot, 0) + 1
    return per_lot


def effectif_on_date(date):
    """Count animals per category on `date`. Always reconstructed from events,
    never read directly from Animal.etat_* (which can drift if a hook fails)."""
    date = getdate(date)
    d = str(date)
    # Pre-filter to animals possibly present (for performance) — states_on_date
    # re-checks presence rigorously.
    names = [r[0] for r in frappe.db.sql("""
        SELECT name FROM `tabAnimal`
        WHERE (CASE WHEN est_achat = 1 THEN date_entree ELSE date_naissance END) <= %s
          AND (statut = 'ACTIF' OR (date_sortie IS NOT NULL AND date_sortie > %s))
    """, (d, d))]
    agg = empty_row()
    for cat, lact, gest in states_on_date(names, date).values():
        col = resolve_col(cat, lact, gest)
        if col:
            agg[col] += 1
    set_total(agg)
    return agg


# ─── Change rows (events on date D) ─────────────────────────────────────────

def count_velages(date):
    """Vêlage row: bucketed by the cow's post-vêlage state (Lact normally, Tarie if same-day tarissement)."""
    d = str(getdate(date))
    rows = frappe.db.sql("""
        SELECT l.statut, l.date_tarissement
        FROM `tabVelage` v
        LEFT JOIN `tabLactation` l ON l.animal = v.animal AND l.date_debut = v.date_velage
        WHERE v.date_velage = %s
    """, d, as_dict=True)
    row = empty_row()
    for r in rows:
        if r.statut == "TARIE" and r.date_tarissement and str(r.date_tarissement) == d:
            row["Vaches - Tarie"] += 1
        else:
            row["Vaches - Lact."] += 1
    set_total(row)
    return row


def count_naissances(date):
    """Live births on D — every animal with date_naissance=D and est_achat=0,
    bucketed by her reconstructed category on D (so the row always matches what
    Final adds for these animals, even when seed data is inconsistent)."""
    date = getdate(date)
    d = str(date)
    names = [r[0] for r in frappe.db.sql(
        "SELECT name FROM `tabAnimal` WHERE date_naissance = %s AND est_achat = 0", d)]
    result = empty_row()
    for cat, lact, gest in states_on_date(names, date).values():
        col = resolve_col(cat, lact, gest)
        if col:
            result[col] += 1
    set_total(result)
    return result


def count_avortements_mort_nes(date):
    """Avortement bucketed by mother's pre-avortement state (D-1, before the
    cascade reset her gestation). Mort-nés bucketed as Veau/Velle by sex."""
    date = getdate(date)
    d = str(date)
    result = empty_row()

    avo_animals = [r[0] for r in frappe.db.sql(
        "SELECT animal FROM `tabAvortement` WHERE date_avortement = %s", d)]
    pre_states = states_on_date(avo_animals, add_days(date, -1))
    for name in avo_animals:
        cat, lact, _ = pre_states.get(name, (None, "", ""))
        # She was GESTANTE pre-avortement; force it for column placement.
        col = resolve_col(cat, lact, "GESTANTE")
        if col:
            result[col] += 1

    for v in frappe.db.sql("""
        SELECT sexe_veau1, vivant_veau1, sexe_veau2, vivant_veau2, nombre_veaux
        FROM `tabVelage` WHERE date_velage = %s
    """, d, as_dict=True):
        if not v.vivant_veau1:
            result["Veaux" if v.sexe_veau1 == "M" else "Velles"] += 1
        if v.nombre_veaux == "2" and not v.vivant_veau2:
            result["Veaux" if v.sexe_veau2 == "M" else "Velles"] += 1

    set_total(result)
    return result


def count_exits(date, statut):
    """Vente / Mortalité / Réforme bucketed by each animal's state day before exit
    (using D-1 to skip the cascade that closes her lactation on date_sortie)."""
    date = getdate(date)
    d = str(date)
    rows = frappe.db.sql("""
        SELECT name, prix_vente FROM `tabAnimal`
        WHERE date_sortie = %s AND statut = %s
    """, (d, statut), as_dict=True)
    names = [r.name for r in rows]
    pre_states = states_on_date(names, add_days(date, -1))

    qty, prix = empty_row(), empty_row()
    for r in rows:
        cat, lact, gest = pre_states.get(r.name, (None, "", ""))
        col = resolve_col(cat, lact, gest)
        if col:
            qty[col] += 1
            prix[col] += int(r.prix_vente or 0)
    set_total(qty)
    set_total(prix)
    return qty, prix


def count_achats(date):
    """Bucket each acheted animal by her state on the day she was bought."""
    date = getdate(date)
    d = str(date)
    names = [r[0] for r in frappe.db.sql(
        "SELECT name FROM `tabAnimal` WHERE est_achat = 1 AND date_entree = %s", d)]
    result = empty_row()
    for cat, lact, gest in states_on_date(names, date).values():
        col = resolve_col(cat, lact, gest)
        if col:
            result[col] += 1
    set_total(result)
    return result


def count_changements_cat(date):
    """Cat changes from events on D — symmetric ledger (Cat+ destinations,
    Cat- sources):
    - Tarissement (Vache Lact → Tarie)
    - IA REUSSIE on a Genisse (Gén. Vide → Pleine) — IAs on Vaches don't shift columns
    - Vêlage (source → destination): both sides counted so (Cat+) − (Cat-)
      always balances column movements. The Vêlage row remains as an event
      counter; the destination value will match the velage's destination cell.
    """
    date = getdate(date)
    d = str(date)
    cat_plus, cat_minus = empty_row(), empty_row()

    # Tarissement (excludes vêlage-induced same-day closes — those are
    # captured by the velage loop below to avoid double-counting).
    tarissements = frappe.db.sql("""
        SELECT animal FROM `tabLactation`
        WHERE date_tarissement = %s AND statut = 'TARIE'
        AND NOT EXISTS (
            SELECT 1 FROM `tabVelage` v
            WHERE v.animal = `tabLactation`.animal AND v.date_velage = %s
        )
    """, (d, d))
    cat_minus["Vaches - Lact."] += len(tarissements)
    cat_plus["Vaches - Tarie"] += len(tarissements)

    # IA REUSSIE — only counts as Vide→Pleine if the cow was actually Vide
    # (a Genisse Pleine getting another REUSSIE IA is a data anomaly; ignore it
    # for column-shift purposes since no real movement happened).
    ia_animals = [r[0] for r in frappe.db.sql(
        "SELECT animal FROM `tabInsemination` WHERE date_ia = %s AND resultat = 'REUSSIE'", d)]
    for name, (cat, _, gest) in states_on_date(ia_animals, add_days(date, -1)).items():
        if cat == "GENISSE" and gest == "VIDE":
            cat_minus["Gén. - Vide"] += 1
            cat_plus["Gén. - Pleine"] += 1

    # Vêlage: source loss + destination gain (skip if no movement, e.g. multipare Lact→Lact)
    velage_rows = frappe.db.sql("""
        SELECT v.animal, l.statut AS lact_statut, l.date_tarissement
        FROM `tabVelage` v
        LEFT JOIN `tabLactation` l ON l.animal = v.animal AND l.date_debut = v.date_velage
        WHERE v.date_velage = %s
    """, d, as_dict=True)
    velage_animals = [r.animal for r in velage_rows]
    pre_states = states_on_date(velage_animals, add_days(date, -1))
    for r in velage_rows:
        src_col = resolve_col(*pre_states.get(r.animal, (None, "", "")))
        if r.lact_statut == "TARIE" and r.date_tarissement and str(r.date_tarissement) == d:
            dst_col = "Vaches - Tarie"
        else:
            dst_col = "Vaches - Lact."
        if src_col and src_col != dst_col:
            cat_minus[src_col] += 1
            cat_plus[dst_col] += 1

    set_total(cat_plus)
    set_total(cat_minus)
    return cat_plus, cat_minus
