"""Import the 2026 calves (VEAUX 2026 tab) as VELLE Animals linked to mother + birth vêlage.

Reads veaux.csv: identification_tn, mere_fr, sire, date_naissance, date_vente, prix_vente.
All 14 are female (categorie VELLE, sexe F per the farm). Each calf:
  - Animal (ignore_validate -> set nom_metier/sexe/race explicitly), lot VELLE.
  - id_mere resolved by mother's identification_fr then nom_metier (=TN last4), unknown ->
    PLACEHOLDER_TN. id_pere = sire (Taureau). date_naissance = the mother's calving date.
  - id_velage_naissance = the mother's existing Velage on that date (the 325 already there;
    set at creation, is_new bypasses the protect guard).
  - sold ones (date_vente present): statut VENDU + date_sortie + prix_vente.

Back-link: fills the birth Velage's id_veau1/id_veau2 (+ sexe/vivant/identification + bumps
nombre_veaux for twins) when empty, so the vêlage shows its calves both ways.

Idempotent (skips existing Animal). Dry-run by default. Run AFTER the herd + velages exist.
Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_veaux.run --kwargs '{"dry_run": 1}'
"""
import frappe

from hmd_agro.hmd_agro.setup import data_source

PLACEHOLDER_TN = "0009999999"
RACE = "Montbéliarde"
LOT = "VELLE"


def _resolve_mother(mere_fr):
    if not mere_fr:
        return None
    cands = {mere_fr, mere_fr.lstrip("0"), mere_fr.zfill(4)}
    for c in cands:
        n = frappe.db.get_value("Animal", {"identification_fr": c}, "name")
        if n:
            return n
    for c in cands:
        n = frappe.db.get_value("Animal", {"nom_metier": c, "categorie": "VACHE"}, "name")
        if n:
            return n
    return None


def _backlink_velage(velage, calf_tn, dry_run):
    """Fill id_veau1/id_veau2 on the birth vêlage when empty (handles twins)."""
    if dry_run:
        return
    v = frappe.get_doc("Velage", velage)
    if not v.id_veau1:
        v.db_set("id_veau1", calf_tn)
        v.db_set("sexe_veau1", "F")
        v.db_set("vivant_veau1", 1)
        v.db_set("identification_veau1", calf_tn)
    elif not v.id_veau2 and v.id_veau1 != calf_tn:
        v.db_set("id_veau2", calf_tn)
        v.db_set("sexe_veau2", "F")
        v.db_set("vivant_veau2", 1)
        v.db_set("identification_veau2", calf_tn)
        v.db_set("nombre_veaux", "2")


def run(dry_run=True, source=None):
    dry_run = int(dry_run)
    created = skipped = sold = 0
    no_mother, no_velage, errors = [], [], []

    for r in data_source.read(source, "veaux.csv"):
        tn = (r.get("identification_tn") or "").strip()
        if not tn:
            continue
        try:
            if frappe.db.exists("Animal", tn):
                skipped += 1
                continue
            birth = data_source.txt(r.get("date_naissance"))
            sire = data_source.txt(r.get("sire"))
            mere_fr = data_source.txt(r.get("mere_fr"))
            vente = data_source.txt(r.get("date_vente"))
            prix = data_source.num(r.get("prix_vente"))

            mother_tn = _resolve_mother(mere_fr)
            if not mother_tn:
                no_mother.append(tn)
                mother_tn = PLACEHOLDER_TN

            birth_velage = None
            if mother_tn != PLACEHOLDER_TN:
                birth_velage = frappe.db.get_value("Velage",
                    {"animal": mother_tn, "date_velage": birth}, "name")
                if not birth_velage and birth:
                    # the two sheets can record the same calving a few days apart;
                    # a cow calves ~once/year, so the nearest vêlage in a wide window
                    # is unambiguous.
                    from frappe.utils import add_days
                    lo, hi = str(add_days(birth, -30)), str(add_days(birth, 30))
                    near = frappe.db.get_all("Velage",
                        filters={"animal": mother_tn, "date_velage": ["between", [lo, hi]]},
                        fields=["name", "date_velage"], order_by="date_velage desc")
                    if near:
                        birth_velage = near[0].name
                if not birth_velage:
                    no_velage.append(tn)

            doc_dict = {
                "doctype": "Animal",
                "identification_tn": tn,
                "nom_metier": tn[-4:],
                "race": RACE,
                "categorie": "VELLE",
                "sexe": "F",
                "date_naissance": birth,
                "est_achat": 0,
                "id_mere": mother_tn,
                "id_pere": sire or None,
                "id_lot": LOT,
                "statut": "ACTIF",
                "etat_gestation": "VIDE",
            }
            if birth_velage:
                doc_dict["id_velage_naissance"] = birth_velage
            if vente:
                doc_dict["statut"] = "VENDU"
                doc_dict["date_sortie"] = vente
                if prix:
                    doc_dict["prix_vente"] = prix
                sold += 1

            if not dry_run:
                doc = frappe.get_doc(doc_dict)
                doc.flags.ignore_validate = True
                doc.flags.ignore_mandatory = True
                doc.flags.lot_change_source = "IMPORT"
                doc.insert(ignore_permissions=True)
                if birth_velage:
                    _backlink_velage(birth_velage, tn, dry_run)
            created += 1
        except Exception as e:
            errors.append({"tn": tn, "error": str(e)})

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Veaux import (VEAUX 2026 -> VELLE)")
    print(f"  would-create={created} (sold/VENDU={sold}), skipped(existing)={skipped}, errors={len(errors)}")
    if no_mother:
        print(f"  WARN dam unresolved -> placeholder ({len(no_mother)}): {no_mother}")
    if no_velage:
        print(f"  WARN birth-vêlage not matched ({len(no_velage)}): {no_velage}")
    for e in errors[:8]:
        print(f"  ERR {e.get('tn')}: {e['error']}")
    return {"created": created, "sold": sold, "skipped": skipped,
            "no_mother": no_mother, "no_velage": no_velage, "errors": errors}
