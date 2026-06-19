import frappe
import json
from frappe.utils import getdate, add_days, today


@frappe.whitelist()
def get_lactating_animals(date):
    """Get animals with active lactation + their traites + the day's bilan
    (lait vendu / CI / LV) — all in one round-trip so the saisie page can
    render its full state from a single fetch."""
    date = getdate(date)

    # Animals whose lactation covered the selected date
    # (date_debut <= D AND (date_tarissement IS NULL OR date_tarissement >= D))
    # and who were present in the herd on D (statut ACTIF or exited on/after D).
    animals = frappe.db.sql("""
        SELECT
            a.name as animal,
            a.nom_metier,
            a.identification_tn,
            a.id_lot as lot,
            IFNULL(a.attente_lait_active, 0) as attente_lait,
            l.name as lactation
        FROM `tabAnimal` a
        INNER JOIN `tabLactation` l ON l.animal = a.name
            AND l.date_debut <= %s
            AND (l.date_tarissement IS NULL OR l.date_tarissement >= %s)
        WHERE a.statut = 'ACTIF'
           OR (a.date_sortie IS NOT NULL AND a.date_sortie >= %s)
        ORDER BY a.id_lot ASC, a.nom_metier DESC
    """, (date, date, date), as_dict=True)

    if not animals:
        return []

    animal_names = [a.animal for a in animals]

    # Existing traites for the selected date
    traites = frappe.db.sql("""
        SELECT animal, session, quantite_litres, quantite_litres_brut, name, id_lot
        FROM `tabTraite`
        WHERE date_traite = %s AND animal IN %s
    """, (date, animal_names), as_dict=True)

    traite_map = {}
    historic_lot = {}
    for t in traites:
        traite_map.setdefault(t.animal, {})[t.session] = {
            "qty": t.quantite_litres,
            "brut": t.quantite_litres_brut if t.quantite_litres_brut is not None else t.quantite_litres,
            "name": t.name
        }
        if t.id_lot:
            historic_lot[t.animal] = t.id_lot

    # Previous day totals for drop detection
    prev_date = add_days(date, -1)
    prev_totals = frappe.db.sql("""
        SELECT animal, SUM(quantite_litres) as total
        FROM `tabTraite`
        WHERE date_traite = %s AND animal IN %s
        GROUP BY animal
    """, (prev_date, animal_names), as_dict=True)

    prev_map = {p.animal: p.total for p in prev_totals}

    result = []
    for a in animals:
        at = traite_map.get(a.animal, {})
        result.append({
            "animal": a.animal,
            "nom_metier": a.nom_metier or a.animal,
            "identification_tn": a.identification_tn or "",
            "lot": historic_lot.get(a.animal) or a.lot or "",
            "attente_lait": a.attente_lait,
            "lactation": a.lactation,
            "matin": at.get("MATIN"),
            "soir": at.get("SOIR"),
            "prev_total": prev_map.get(a.animal, 0) or 0
        })

    # Production-cycle lot order (LOT1..n → TARISSEMENT → TARIE → INFIRMERIE → others),
    # then N° ascending — same ordering as the printable milking sheet.
    from hmd_agro.hmd_agro.utils.lot_utils import lot_sort_key
    result.sort(key=lambda r: (lot_sort_key(r["lot"]), r["nom_metier"] or ""))

    bilan_name = frappe.db.get_value("Bilan Lait Journalier", {"date": date}, "name")
    if bilan_name:
        b = frappe.db.get_value(
            "Bilan Lait Journalier", bilan_name,
            ["lait_vendu", "consommation_interne", "lait_veau",
             "taux_tb_moyen", "taux_tp_moyen"], as_dict=True)
        bilan = {
            "lait_vendu": float(b.lait_vendu or 0),
            "consommation_interne": float(b.consommation_interne or 0),
            "lait_veau": float(b.lait_veau or 0),
            "taux_tb_moyen": float(b.taux_tb_moyen or 0),
            "taux_tp_moyen": float(b.taux_tp_moyen or 0),
        }
    else:
        bilan = {
            "lait_vendu": 0, "consommation_interne": 0, "lait_veau": 0,
            "taux_tb_moyen": 0, "taux_tp_moyen": 0,
        }

    return {"animals": result, "bilan": bilan}


@frappe.whitelist()
def get_milking_sheet(date=None):
    """Printable milking sheet: lactating cows in lot order (LOT1..n → … → INFIRMERIE →
    others, via lot_sort_key), each with existing Matin/Soir values for `date`, date+1,
    date+2. Values are pre-filled where already entered, blank otherwise (handwriting)."""
    from hmd_agro.hmd_agro.utils.lot_utils import lot_sort_key

    base = getdate(date or today())
    dates = [add_days(base, i) for i in range(3)]
    dstrs = [str(d) for d in dates]

    animals = frappe.db.sql("""
        SELECT a.name AS animal, a.nom_metier, a.id_lot AS lot
        FROM `tabAnimal` a
        INNER JOIN `tabLactation` l ON l.animal = a.name
            AND l.date_debut <= %s
            AND (l.date_tarissement IS NULL OR l.date_tarissement >= %s)
        WHERE a.statut = 'ACTIF'
           OR (a.date_sortie IS NOT NULL AND a.date_sortie >= %s)
    """, (base, base, base), as_dict=True)

    out = {"dates": [d.strftime("%d/%m") for d in dates], "rows": []}
    if not animals:
        return out

    names = [a.animal for a in animals]
    traites = frappe.db.sql("""
        SELECT animal, date_traite, session, quantite_litres
        FROM `tabTraite`
        WHERE date_traite IN %s AND animal IN %s
    """, (dstrs, names), as_dict=True)
    tmap = {}
    for t in traites:
        tmap.setdefault(t.animal, {})[(str(t.date_traite), t.session)] = t.quantite_litres

    animals.sort(key=lambda a: (lot_sort_key(a.lot or ""), a.nom_metier or ""))
    for a in animals:
        days = []
        for ds in dstrs:
            am = tmap.get(a.animal, {})
            days.append({"matin": am.get((ds, "MATIN")), "soir": am.get((ds, "SOIR"))})
        out["rows"].append({"nom_metier": a.nom_metier or a.animal, "lot": a.lot or "", "days": days})
    return out


@frappe.whitelist()
def save_traites(date, entries, bilan=None):
    """Save multiple traites at once with bilan-driven reconciliation.

    Reconciliation flow:
      1. For each entry, decide its `brut`:
         - existing Traite, value unchanged → keep its stored brut
         - existing Traite, value edited    → brut = entered value (new measurement)
         - new entry                        → brut = entered value
      2. brut_sum = Σ brut
      3. ratio = consumed / brut_sum (where consumed = vendu + CI + LV)
         skipped (ratio = 1.0) when consumed = 0, brut_sum = 0, or consumed > brut_sum
         (negative écart → leave raw values, warn).
      4. Save each Traite with quantite_litres = brut × ratio (rounded) and brut.
      5. Upsert Bilan with stored production_totale_saisie + ecart_litres.
    """
    if isinstance(entries, str):
        entries = json.loads(entries)
    if isinstance(bilan, str):
        bilan = json.loads(bilan)

    consumed = 0.0
    if bilan:
        consumed = (
            float(bilan.get("lait_vendu") or 0)
            + float(bilan.get("consommation_interne") or 0)
            + float(bilan.get("lait_veau") or 0)
        )

    # ── Step 1: resolve effective brut per entry ─────────────────────────
    for entry in entries:
        entered = float(entry.get("quantite_litres") or 0)
        if entry.get("traite_name"):
            stored = frappe.db.get_value(
                "Traite",
                entry["traite_name"],
                ["quantite_litres", "quantite_litres_brut"],
                as_dict=True,
            ) or {}
            stored_qty = float(stored.get("quantite_litres") or 0)
            stored_brut = float(stored.get("quantite_litres_brut") or stored_qty)
            if abs(entered - stored_qty) < 0.05:
                # Unchanged from what's displayed → keep original brut
                entry["_brut"] = stored_brut
            else:
                # User edited → entered value is the new measurement
                entry["_brut"] = entered
        else:
            entry["_brut"] = entered

    # ── Step 2 + 3: compute ratio ────────────────────────────────────────
    brut_sum = sum(e["_brut"] for e in entries)
    negative_ecart = False
    if consumed > 0 and brut_sum > 0 and consumed < brut_sum:
        ratio = consumed / brut_sum
    else:
        ratio = 1.0
        if consumed > brut_sum > 0:
            negative_ecart = True

    # ── Step 4: save each Traite with both fields ────────────────────────
    created = 0
    updated = 0
    errors = []

    for entry in entries:
        try:
            brut = entry["_brut"]
            reconciled = round(brut * ratio, 1)
            if entry.get("traite_name"):
                doc = frappe.get_doc("Traite", entry["traite_name"])
                doc.quantite_litres = reconciled
                doc.quantite_litres_brut = brut
                doc.save()
                updated += 1
            else:
                doc = frappe.get_doc({
                    "doctype": "Traite",
                    "animal": entry["animal"],
                    "date_traite": date,
                    "session": entry["session"],
                    "quantite_litres": reconciled,
                    "quantite_litres_brut": brut,
                })
                doc.insert()
                created += 1
        except Exception as e:
            errors.append({
                "animal": entry.get("animal"),
                "session": entry.get("session"),
                "error": str(e)
            })

    # ── Step 5: upsert Bilan with derived stored values ──────────────────
    bilan_status = None
    if bilan is not None:
        try:
            bilan_status = _upsert_bilan(date, bilan, brut_sum, brut_sum - consumed)
        except Exception as e:
            errors.append({"animal": "BILAN", "session": "", "error": str(e)})

    frappe.db.commit()

    if negative_ecart:
        frappe.msgprint(
            f"Vendu+CI+LV ({consumed:.1f} L) dépasse la production saisie "
            f"({brut_sum:.1f} L). Aucune réconciliation appliquée — vérifiez les saisies.",
            indicator="orange",
            alert=True,
        )

    return {
        "created": created,
        "updated": updated,
        "errors": errors,
        "bilan_status": bilan_status,
        "ratio": ratio,
        "negative_ecart": negative_ecart,
    }


def _upsert_bilan(date, bilan, brut_sum, ecart):
    """Insert or update the Bilan Lait Journalier row for `date`.
    `brut_sum` and `ecart` are computed by save_traites and stored as derived
    fields so the Bilan form + future reports can read them directly."""
    existing = frappe.db.get_value("Bilan Lait Journalier", {"date": date}, "name")
    payload = {
        "lait_vendu": float(bilan.get("lait_vendu") or 0),
        "consommation_interne": float(bilan.get("consommation_interne") or 0),
        "lait_veau": float(bilan.get("lait_veau") or 0),
        "taux_tb_moyen": float(bilan.get("taux_tb_moyen") or 0),
        "taux_tp_moyen": float(bilan.get("taux_tp_moyen") or 0),
        "production_totale_saisie": round(brut_sum, 1),
        "ecart_litres": round(ecart, 1),
    }
    if existing:
        doc = frappe.get_doc("Bilan Lait Journalier", existing)
        for k, v in payload.items():
            doc.set(k, v)
        doc.save()
        return "updated"
    else:
        doc = frappe.get_doc({
            "doctype": "Bilan Lait Journalier",
            "date": date,
            **payload,
        })
        doc.insert()
        return "created"
