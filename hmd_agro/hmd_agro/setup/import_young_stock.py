"""Import young stock (génisses + velles) from the fresh ETABLE HMD 2026.

Reads two CSVs:
  young_stock.csv     identification_tn, categorie (GENISSE|VELLE), date_naissance, sire, mere_fr
  young_stock_ia.csv  identification_tn, date_ia, taureau, resultat (REUSSIE|ECHOUEE)

77 animals: 13 GENISSE (currently bred) + 64 VELLE (not yet bred). For the 13, their IAs
are inserted so the fecundating REUSSIE fires the normal cascade
(Insemination.update_animal_on_resultat -> Animal GESTANTE + date_velage_prevue +
date_tarissement). The system computes those dates itself — we only supply the IA records.

Per animal:
  - Animal (ignore_validate, so set nom_metier/sexe/etat_gestation/race explicitly).
    lot = GENISSE or VELLE by categorie. id_mere resolved by mother's identification_fr,
    unknown -> PLACEHOLDER_TN founder. id_pere = sire. id_velage_naissance = the mother's
    Velage on the animal's birth date (best-effort exact match). etat_gestation = VIDE at
    creation so the IA inserts don't trip ERR-IA-06 (already gestante).

IA insertion order = ascending date (REUSSIE always last in this dataset):
  - ECHOUEE: insert EN_ATTENTE (bypass) then db.set_value ECHOUEE  (no cascade)
  - REUSSIE (fecundating): insert EN_ATTENTE then doc.save(resultat=REUSSIE) so on_update
    fires the gestation cascade. skip_semence_decrement on all (historical, no stock writes).

Missing IA bulls are auto-created as minimal Taureau records (flagged) so the IA validates.
Idempotent (skips existing Animal / IA). Dry-run by default. Run AFTER the herd + velages exist.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_young_stock.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.setup import data_source

PLACEHOLDER_TN = "0009999999"   # founder mother for unknown dams (created by import_animal)
RACE = "Montbéliarde"
LOT_BY_CAT = {"GENISSE": "GENISSE", "VELLE": "VELLE"}


def _resolve_mother(mere_fr):
    """Resolve the mother N° -> Animal name. The sheet uses the farm convention: a cow
    with a French tag is shown by identification_fr; a cow without one by her nom_metier
    (= identification_tn last 4). So match identification_fr first, then nom_metier
    (restricted to VACHE so a velle sibling can't match). None if the dam left the herd."""
    if not mere_fr:
        return None
    cands = {mere_fr, mere_fr.lstrip("0"), mere_fr.zfill(4)}
    for c in cands:
        name = frappe.db.get_value("Animal", {"identification_fr": c}, "name")
        if name:
            return name
    for c in cands:
        name = frappe.db.get_value("Animal", {"nom_metier": c, "categorie": "VACHE"}, "name")
        if name:
            return name
    return None


def _resolve_birth_velage(mother_tn, birth):
    """the mother's Velage on the animal's birth date (exact, then ±7 days)."""
    if not mother_tn or not birth:
        return None
    exact = frappe.db.get_value("Velage", {"animal": mother_tn, "date_velage": birth}, "name")
    if exact:
        return exact
    from frappe.utils import add_days
    lo, hi = str(add_days(birth, -7)), str(add_days(birth, 7))
    near = frappe.db.get_value("Velage",
        {"animal": mother_tn, "date_velage": ["between", [lo, hi]]}, "name")
    return near


def _ensure_taureau(nom, dry_run, created_bulls):
    """Create a minimal Taureau if missing (real bull absent from the 79-master)."""
    if not nom or frappe.db.exists("Taureau", nom):
        return True
    created_bulls.add(nom)
    if not dry_run:
        doc = frappe.get_doc({
            "doctype": "Taureau", "nom_taureau": nom, "code_taureau": nom,
            "race": RACE, "origine": "IMPORT — genetics à compléter",
        })
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
    return True


def run(dry_run=True, source=None):
    dry_run = int(dry_run)
    animals = list(data_source.read(source, "young_stock.csv"))
    ia_rows = list(data_source.read(source, "young_stock_ia.csv"))

    created = skipped = 0
    no_mother, no_velage, errors = [], [], []
    created_bulls = set()

    # ---- 1. animals ----
    for r in animals:
        tn = (r.get("identification_tn") or "").strip()
        if not tn:
            continue
        try:
            if frappe.db.exists("Animal", tn):
                skipped += 1
                continue
            cat = (r.get("categorie") or "VELLE").strip()
            birth = data_source.txt(r.get("date_naissance"))
            sire = data_source.txt(r.get("sire"))
            mere_fr = data_source.txt(r.get("mere_fr"))

            mother_tn = _resolve_mother(mere_fr)
            if not mother_tn:
                no_mother.append(tn)
                mother_tn = PLACEHOLDER_TN
            if sire:
                _ensure_taureau(sire, dry_run, created_bulls)

            birth_velage = _resolve_birth_velage(mother_tn, birth) if mother_tn != PLACEHOLDER_TN else None
            if mother_tn != PLACEHOLDER_TN and not birth_velage:
                no_velage.append(tn)

            doc_dict = {
                "doctype": "Animal",
                "identification_tn": tn,
                "nom_metier": tn[-4:],
                "race": RACE,
                "categorie": cat,
                "sexe": "F",
                "date_naissance": birth,
                "est_achat": 0,
                "id_mere": mother_tn,
                "id_pere": sire or None,
                "id_lot": LOT_BY_CAT.get(cat, "VELLE"),
                "statut": "ACTIF",
                "etat_gestation": "VIDE",   # cascade flips to GESTANTE via the fecundating IA
            }
            if birth_velage:
                doc_dict["id_velage_naissance"] = birth_velage
            if not dry_run:
                doc = frappe.get_doc(doc_dict)
                doc.flags.ignore_validate = True
                doc.flags.ignore_mandatory = True
                doc.flags.lot_change_source = "IMPORT"
                doc.insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            errors.append({"tn": tn, "phase": "animal", "error": str(e)})

    # ---- 2. inseminations for the bred génisses (group by animal, ascending date) ----
    from collections import OrderedDict
    cows = OrderedDict()
    for r in ia_rows:
        tn = (r.get("identification_tn") or "").strip()
        date = (r.get("date_ia") or "").strip()
        if tn and date:
            cows.setdefault(tn, []).append(
                (date, data_source.txt(r.get("taureau")), (r.get("resultat") or "").strip()))

    ia_created = ia_skipped = reussie = 0
    for tn, ias in cows.items():
        if not frappe.db.exists("Animal", tn) and dry_run:
            pass  # animal would be created above in a real run
        elif not frappe.db.exists("Animal", tn):
            errors.append({"tn": tn, "phase": "ia", "error": "animal not found"})
            continue
        ias.sort(key=lambda x: x[0])
        for i, (date, taureau, resultat) in enumerate(ias):
            try:
                if taureau:
                    _ensure_taureau(taureau, dry_run, created_bulls)
                if frappe.db.exists("Insemination", {"animal": tn, "date_ia": date}):
                    ia_skipped += 1
                    continue
                if not dry_run:
                    doc = frappe.get_doc({
                        "doctype": "Insemination",
                        "animal": tn,
                        "date_ia": date,
                        "taureau": taureau,
                        "type_semence": "CONVENTIONNELLE",
                        "resultat": "EN_ATTENTE",
                        "numero_ia": i + 1,
                        "lactation": None,
                    })
                    doc.flags.ignore_validate = True
                    doc.flags.ignore_mandatory = True
                    doc.flags.skip_semence_decrement = True
                    doc.insert(ignore_permissions=True)
                    if resultat == "ECHOUEE":
                        frappe.db.set_value("Insemination", doc.name, "resultat", "ECHOUEE")
                    elif resultat == "REUSSIE":
                        # save through the doc so on_update fires the gestation cascade
                        fec = frappe.get_doc("Insemination", doc.name)
                        fec.resultat = "REUSSIE"
                        fec.flags.skip_semence_decrement = True
                        fec.save(ignore_permissions=True)
                ia_created += 1
                if resultat == "REUSSIE":
                    reussie += 1
            except Exception as e:
                errors.append({"tn": tn, "date": date, "phase": "ia", "error": str(e)})

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Young stock import (génisses + velles, fresh ETABLE HMD 2026)")
    print(f"  animals would-create={created}, skipped(existing)={skipped}")
    print(f"  IA records would-create={ia_created} (REUSSIE/gestante={reussie}), skipped={ia_skipped}")
    print(f"  => expect 13 GENISSE GESTANTE + 64 VELLE")
    if created_bulls:
        print(f"  Taureau auto-created (missing from master — complete genetics): {sorted(created_bulls)}")
    if no_mother:
        print(f"  WARN dam unresolved -> placeholder ({len(no_mother)}): {no_mother}")
    if no_velage:
        print(f"  WARN birth-vêlage not matched ({len(no_velage)}): {no_velage}")
    for e in errors[:8]:
        print(f"  ERR {e.get('tn')} {e.get('date','')} [{e.get('phase')}]: {e['error']}")
    return {"created": created, "skipped": skipped, "ia_created": ia_created,
            "reussie": reussie, "ia_skipped": ia_skipped, "created_bulls": sorted(created_bulls),
            "no_mother": no_mother, "no_velage": no_velage, "errors": errors}
