"""
Daily snapshot of farm state (one `Snapshot Journalier` row per date):
  - animals_json    : per-animal state at end of day
  - events_json     : domain-event counts for that day (vêlages, naissances, IA, avortements)
  - aggregates_json : category counts (fast read for Effectif Initial/Final)
  - frozen          : 1 once the day is closed

The Effectif report diffs two days' animals_json to build the change rows
(vêlage, tarissement, vente, mortalité, achat, changement catégorie).
Naissances / mort-nés / avortements / IA come from live event-table queries
so edits to past events are reflected; pre-frozen counts stay in events_json
for the daily-sheet view.
"""

import frappe
import json
from frappe.utils import getdate, today, add_days, cint

DOCTYPE = "Snapshot Journalier"


# ─── Report columns ──────────────────────────────────────────────────────────

CATEGORIES = [
    "Vaches - Lact.", "Vaches - Tarie", "Gén. - Vide", "Gén. - Pleine",
    "Veaux", "Engraiss.", "Velles", "Total",
]

_SIMPLE_CAT = {"VEAU": "Veaux", "TAURILLON": "Engraiss.", "VELLE": "Velles"}


def resolve_col(cat, lact, gest):
    """Map (categorie, etat_lactation, etat_gestation) → report column."""
    if cat == "VACHE":
        return "Vaches - Tarie" if lact == "TARIE" else "Vaches - Lact."
    if cat == "GENISSE":
        return "Gén. - Pleine" if gest == "GESTANTE" else "Gén. - Vide"
    return _SIMPLE_CAT.get(cat)


def empty_row():
    return {c: 0 for c in CATEGORIES}


def set_total(row):
    row["Total"] = sum(v for k, v in row.items() if k != "Total")


# ─── State capture ───────────────────────────────────────────────────────────

def _capture_animals():
    rows = frappe.db.sql("""
        SELECT name, categorie, etat_lactation, etat_gestation, statut,
               id_lot, prix_vente, date_sortie, est_achat, date_entree
        FROM `tabAnimal`
    """, as_dict=True)
    return {r.name: {
        "cat": r.categorie,
        "lact": r.etat_lactation or "",
        "gest": r.etat_gestation or "",
        "statut": r.statut,
        "lot": r.id_lot,
        "prix_vente": float(r.prix_vente or 0),
        "date_sortie": str(r.date_sortie) if r.date_sortie else None,
        "est_achat": cint(r.est_achat),
        "date_entree": str(r.date_entree) if r.date_entree else None,
    } for r in rows}


def capture_events(date_debut, date_fin=None):
    """Event aggregates on [date_debut, date_fin] inclusive (single day if date_fin omitted)."""
    date_debut = str(getdate(date_debut))
    date_fin = str(getdate(date_fin)) if date_fin else date_debut
    between = ["between", [date_debut, date_fin]]

    velages = frappe.db.sql("""
        SELECT sexe_veau1, vivant_veau1, sexe_veau2, vivant_veau2, nombre_veaux
        FROM `tabVelage` WHERE date_velage BETWEEN %s AND %s
    """, (date_debut, date_fin), as_dict=True)

    naiss_m = naiss_f = mort_nes = 0
    for v in velages:
        for sfx in ("1", "2"):
            if sfx == "2" and cint(v.nombre_veaux) < 2:
                continue
            sexe, vivant = v.get(f"sexe_veau{sfx}"), v.get(f"vivant_veau{sfx}")
            if not sexe:
                continue
            if vivant:
                if sexe == "M": naiss_m += 1
                elif sexe == "F": naiss_f += 1
            else:
                mort_nes += 1

    return {
        "velages": len(velages),
        "naissances_m": naiss_m,
        "naissances_f": naiss_f,
        "mort_nes": mort_nes,
        "avortements": frappe.db.count("Avortement", {"date_avortement": between}),
        "ia_total": frappe.db.count("Insemination", {"date_ia": between}),
        "ia_reussies": frappe.db.count("Insemination", {"date_ia": between, "resultat": "REUSSIE"}),
    }


def aggregate_counts(animals):
    """ACTIF animals grouped into report columns."""
    agg = empty_row()
    for a in animals.values():
        if a["statut"] != "ACTIF":
            continue
        col = resolve_col(a["cat"], a["lact"], a["gest"])
        if col:
            agg[col] += 1
    set_total(agg)
    return agg


# ─── Persistence ─────────────────────────────────────────────────────────────

def freeze_day(date):
    """Write (or overwrite) the frozen snapshot for `date` from current DB state."""
    date = str(getdate(date))
    animals = _capture_animals()
    payload = {
        "date_snapshot": date,
        "animals_json": json.dumps(animals),
        "events_json": json.dumps(capture_events(date)),
        "aggregates_json": json.dumps(aggregate_counts(animals)),
        "frozen": 1,
    }
    existing = frappe.db.get_value(DOCTYPE, {"date_snapshot": date})
    if existing:
        doc = frappe.get_doc(DOCTYPE, existing)
        doc.update(payload)
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({"doctype": DOCTYPE, **payload})
        doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


def freeze_yesterday():
    """Scheduler — at 00:00, freeze the day that just ended."""
    freeze_day(add_days(today(), -1))


def read_snapshot(date):
    """Return the frozen snapshot for `date` as a dict, or None."""
    date = str(getdate(date))
    row = frappe.db.get_value(DOCTYPE, {"date_snapshot": date},
        ["animals_json", "events_json", "aggregates_json"], as_dict=True)
    if not row:
        return None
    return {
        "animals": json.loads(row.animals_json or "{}"),
        "events": json.loads(row.events_json or "{}"),
        "aggregates": json.loads(row.aggregates_json or "{}"),
    }


def get_day_state(date):
    """Frozen snapshot if stored; live capture if `date` is today; else None."""
    snap = read_snapshot(date)
    if snap:
        return snap
    if getdate(date) == getdate(today()):
        animals = _capture_animals()
        return {
            "animals": animals,
            "events": capture_events(date),
            "aggregates": aggregate_counts(animals),
        }
    return None


# ─── Diff ────────────────────────────────────────────────────────────────────

_EXIT_TARGET = {"VENDU": "ventes", "MORT": "mortalite", "REFORME": "reformes"}
_DIFF_KEYS = ("cat_plus", "cat_minus", "velage", "mortalite", "ventes", "reformes", "achats", "prix_vente")


def _empty_diff():
    return {k: empty_row() for k in _DIFF_KEYS}


def _is_velage(p, c):
    """Vêlage = gestante→vide with Génisse→Vache (first) OR Tarie→Lactante."""
    if not (p["gest"] == "GESTANTE" and c["gest"] == "VIDE"):
        return False
    if p["cat"] == "GENISSE" and c["cat"] == "VACHE":
        return True
    return p["cat"] == "VACHE" and p["lact"] == "TARIE" and c["lact"] == "EN_PRODUCTION"


def diff_day(prev_animals, curr_animals):
    """Change counts between two daily Animal-state snapshots, bucketed by report column."""
    out = _empty_diff()

    for name in set(prev_animals) | set(curr_animals):
        p = prev_animals.get(name)
        c = curr_animals.get(name)

        if not p:
            if c and c.get("est_achat"):
                col = resolve_col(c["cat"], c["lact"], c["gest"])
                if col: out["achats"][col] += 1
            continue
        if not c:
            continue

        p_active, c_active = p["statut"] == "ACTIF", c["statut"] == "ACTIF"

        if p_active and not c_active:
            col = resolve_col(p["cat"], p["lact"], p["gest"])
            target = _EXIT_TARGET.get(c["statut"])
            if col and target:
                out[target][col] += 1
                if target in ("ventes", "reformes") and c.get("prix_vente"):
                    out["prix_vente"][col] += int(c["prix_vente"])
            continue

        if not p_active:
            continue

        prev_col = resolve_col(p["cat"], p["lact"], p["gest"])
        curr_col = resolve_col(c["cat"], c["lact"], c["gest"])
        if not prev_col or not curr_col or prev_col == curr_col:
            continue

        if _is_velage(p, c):
            out["velage"][curr_col] += 1
        else:
            out["cat_minus"][prev_col] += 1
            out["cat_plus"][curr_col] += 1

    for k in out:
        set_total(out[k])
    return out
