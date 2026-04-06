import frappe
import openpyxl
from frappe.utils import getdate, today
from frappe.utils.background_jobs import enqueue, is_job_enqueued
from io import BytesIO


@frappe.whitelist()
def preview_import(file_url):
    """Parse Excel and return preview: matched animals, date range, row counts"""
    dates, animals_data = parse_excel(file_url)

    if not dates:
        frappe.throw("Aucune date trouvee dans le fichier (ligne 6, colonnes G+).")
    if not animals_data:
        frappe.throw("Aucun animal trouve dans le fichier (colonne F).")

    # Build animal mapping: nom_metier -> animal name
    animal_map, duplicate_noms = build_animal_mapping()

    # Match Excel animals to DB
    matched = []
    unmatched = []
    duplicates = []

    for row in animals_data:
        nom = str(row["nom_metier"]).zfill(4)
        if nom in duplicate_noms:
            duplicates.append(nom)
        elif nom in animal_map:
            matched.append({"nom_metier": nom, "animal": animal_map[nom]})
        else:
            unmatched.append(nom)

    # Build lactation info for matched animals
    lactation_info = {}
    for m in matched:
        lacs = get_animal_lactations(m["animal"])
        lactation_info[m["nom_metier"]] = {
            "animal": m["animal"],
            "lactations": len(lacs),
            "details": [
                {
                    "name": l.name,
                    "numero": l.numero_lactation,
                    "debut": str(l.date_debut),
                    "fin": str(l.date_tarissement) if l.date_tarissement else "en cours",
                    "statut": l.statut
                }
                for l in lacs
            ]
        }

    return {
        "date_range": {
            "start": str(dates[0]),
            "end": str(dates[-1]),
            "days": len(dates)
        },
        "total_animals_excel": len(animals_data),
        "matched": len(matched),
        "unmatched": unmatched,
        "duplicates": duplicates,
        "estimated_traites": len(matched) * len(dates) * 2,
        "lactation_info": lactation_info
    }


@frappe.whitelist()
def run_import(file_url, keep_original=1):
    """Enqueue the import as a background job"""
    keep_original = int(keep_original)
    job_id = f"import_traites::{file_url}"

    if is_job_enqueued(job_id):
        frappe.msgprint("Un import est deja en cours pour ce fichier.")
        return {"status": "already_running"}

    enqueue(
        _process_import,
        queue="long",
        timeout=6000,
        job_id=job_id,
        file_url=file_url,
        keep_original=keep_original,
        user=frappe.session.user,
        now=frappe.conf.developer_mode,
    )

    return {"status": "started"}


def _process_import(file_url, keep_original, user):
    """Background job: parse Excel and create Traite records"""
    frappe.set_user(user)

    try:
        dates, animals_data = parse_excel(file_url)

        if not dates or not animals_data:
            frappe.publish_realtime("import_traites_complete",
                {"success": False, "error": "Fichier invalide."},
                user=user)
            return

        animal_map, duplicate_noms = build_animal_mapping()

        summary = {
            "created": 0,
            "overwritten": 0,
            "skipped_no_animal": 0,
            "skipped_no_lactation": 0,
            "skipped_duplicate": 0,
            "errors": [],
            "lactations_updated": 0
        }

        affected_lactations = set()

        # Calculate total for progress
        total_cells = len(animals_data) * len(dates)
        processed = 0

        for row in animals_data:
            nom = str(row["nom_metier"]).zfill(4)

            # Skip unmatched or duplicate nom_metier
            if nom in duplicate_noms or nom not in animal_map:
                summary["skipped_no_animal"] += len(dates)
                processed += len(dates)
                frappe.publish_realtime("import_traites_progress",
                    {"current": processed, "total": total_cells},
                    user=user)
                continue

            animal_name = animal_map[nom]
            lactations = get_animal_lactations(animal_name)

            for i, date in enumerate(dates):
                value = row["values"][i] if i < len(row["values"]) else 0
                try:
                    value = float(value) if value else 0
                except (ValueError, TypeError):
                    summary["errors"].append({
                        "animal": nom,
                        "date": str(date),
                        "reason": f"Valeur non numerique: {value}"
                    })
                    processed += 1
                    continue

                # Find which lactation covers this date
                lactation = find_lactation_for_date(lactations, date)

                if not lactation:
                    if value > 0:
                        summary["skipped_no_lactation"] += 1
                        summary["errors"].append({
                            "animal": nom,
                            "date": str(date),
                            "reason": "Pas de lactation pour cette date"
                        })
                    else:
                        summary["skipped_no_lactation"] += 1
                    processed += 1
                    continue

                # 50/50 split
                half = round(value / 2, 1)

                for session in ["MATIN", "SOIR"]:
                    # Validate quantity (0-60 per session)
                    qty = half
                    if qty > 60:
                        summary["errors"].append({
                            "animal": nom,
                            "date": str(date),
                            "reason": f"Quantite {session} depasse 60L ({qty})"
                        })
                        continue

                    # Check duplicate
                    existing = frappe.db.exists("Traite", {
                        "animal": animal_name,
                        "date_traite": str(date),
                        "session": session
                    })
                    if existing:
                        if keep_original:
                            summary["skipped_duplicate"] += 1
                            continue
                        else:
                            # Override: update existing traite
                            frappe.db.set_value("Traite", existing,
                                {"quantite_litres": qty, "lactation": lactation.name})
                            summary["overwritten"] += 1
                            affected_lactations.add(lactation.name)
                            continue

                    doc = frappe.get_doc({
                        "doctype": "Traite",
                        "animal": animal_name,
                        "date_traite": str(date),
                        "session": session,
                        "quantite_litres": qty,
                        "lactation": lactation.name
                    })
                    doc.flags.ignore_validate = True
                    doc.flags.ignore_links = True
                    doc.insert(ignore_permissions=True)
                    summary["created"] += 1
                    affected_lactations.add(lactation.name)

                processed += 1

                # Publish progress every 50 cells
                if processed % 50 == 0:
                    frappe.publish_realtime("import_traites_progress",
                        {"current": processed, "total": total_cells},
                        user=user)

            # Commit per animal
            frappe.db.commit()

        # Recalculate production for all affected lactations
        for lac_name in affected_lactations:
            recalculate_lactation_production(lac_name)
        frappe.db.commit()

        summary["lactations_updated"] = len(affected_lactations)

        frappe.publish_realtime("import_traites_complete",
            {"success": True, "summary": summary},
            user=user)

    except Exception:
        frappe.db.rollback()
        frappe.log_error("Import traites failed")
        frappe.publish_realtime("import_traites_complete",
            {"success": False, "error": str(frappe.get_traceback())},
            user=user)


def find_lactation_for_date(lactations, date):
    """Find the lactation that covers the given date"""
    for lac in lactations:
        if not lac.date_debut:
            continue
        debut = getdate(lac.date_debut)
        if debut > date:
            continue
        # EN_COURS has no end date — covers up to today
        if not lac.date_tarissement:
            if date <= getdate(today()):
                return lac
        else:
            if date <= getdate(lac.date_tarissement):
                return lac
    return None


def recalculate_lactation_production(lactation_name):
    """Recalculate production totals for a lactation (same logic as Traite.update_lactation_production)"""
    date_debut = frappe.db.get_value("Lactation", lactation_name, "date_debut")

    total = frappe.db.sql("""
        SELECT SUM(quantite_litres)
        FROM `tabTraite`
        WHERE lactation = %s
    """, lactation_name)[0][0] or 0

    pic = frappe.db.sql("""
        SELECT MAX(daily_total) FROM (
            SELECT SUM(quantite_litres) as daily_total
            FROM `tabTraite`
            WHERE lactation = %s
              AND DATEDIFF(date_traite, %s) <= 150
            GROUP BY date_traite
        ) as daily
    """, (lactation_name, date_debut))[0][0] or 0

    updates = {
        "production_totale": total,
        "pic_production": pic
    }

    if date_debut:
        total_305 = frappe.db.sql("""
            SELECT SUM(quantite_litres)
            FROM `tabTraite`
            WHERE lactation = %s
              AND DATEDIFF(date_traite, %s) <= 305
        """, (lactation_name, date_debut))[0][0] or 0
        updates["lactation_305j"] = round(total_305, 2)

        prod_init = frappe.db.sql("""
            SELECT SUM(quantite_litres)
            FROM `tabTraite`
            WHERE lactation = %s
              AND DATEDIFF(date_traite, %s) <= 60
        """, (lactation_name, date_debut))[0][0] or 0
        updates["production_initiale"] = round(prod_init, 2)

        from frappe.utils import date_diff
        jours = date_diff(today(), date_debut)
        if jours > 0:
            updates["moyenne_production"] = round(total / jours, 2)

    frappe.db.set_value("Lactation", lactation_name, updates)


def parse_excel(file_url):
    """Parse the uploaded Excel file, return (dates, animals_data)"""
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    content = file_doc.get_content()
    wb = openpyxl.load_workbook(BytesIO(content), data_only=True)
    ws = wb.active

    # Row 6: date headers starting at col G (index 7)
    dates = []
    for col in range(7, ws.max_column + 1):
        val = ws.cell(6, col).value
        if val and hasattr(val, 'date'):
            dates.append(val.date())
        elif val and isinstance(val, str):
            try:
                dates.append(getdate(val))
            except Exception:
                break
        else:
            break

    # Rows 7+: col F = nom_metier, cols G+ = daily values
    animals_data = []
    for row in range(7, ws.max_row + 1):
        nom_metier = ws.cell(row, 6).value
        if nom_metier is None:
            continue

        values = []
        for col_idx in range(7, 7 + len(dates)):
            val = ws.cell(row, col_idx).value
            values.append(val if val is not None else 0)

        animals_data.append({
            "nom_metier": str(nom_metier).zfill(4) if isinstance(nom_metier, int) else str(nom_metier),
            "values": values
        })

    return dates, animals_data


def build_animal_mapping():
    """Build {nom_metier: animal_name} mapping. Returns (map, duplicates set)."""
    animals = frappe.db.get_all("Animal",
        fields=["name", "nom_metier"],
        filters={"nom_metier": ["is", "set"]}
    )

    # Detect duplicates
    from collections import Counter
    counts = Counter(a.nom_metier for a in animals)
    duplicates = {k for k, v in counts.items() if v > 1}

    mapping = {}
    for a in animals:
        if a.nom_metier not in duplicates:
            mapping[a.nom_metier] = a.name

    return mapping, duplicates


def get_animal_lactations(animal_name):
    """Get all lactations for an animal, sorted by date_debut"""
    return frappe.db.get_all("Lactation",
        filters={"animal": animal_name},
        fields=["name", "numero_lactation", "date_debut", "date_tarissement", "statut"],
        order_by="date_debut asc"
    )
