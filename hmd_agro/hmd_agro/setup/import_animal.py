"""Import the current milking herd into the Animal doctype (Phase 1: bare records).

Data is BAKED IN (no Excel / pandas / xlrd needed on the server), following the
import_taureau.py / import_aliment.py convention. It was extracted offline from:
  - med.xlsx  (Feuil1) ......... the current cheptel: 99 adult cows, giving the
                                 real 10-digit identification_tn (prefix TN2300xx
                                 + 4-digit suffix).
  - Etable HMD 2025 (1).xls > REPRO2025 ... joined on the 4-digit Tunisien N°
                                 (col 16) for date_naissance (col 3) and sire
                                 (Pere Nom, col 5). Join verified 99/99, 0 dup.

SCOPE: current herd ONLY (no sold/dead/reformed cows).
PHASE 1 ONLY: bare Animal records, no events. Velage/Insemination/Traite are a
separate later phase (importing them here would fire the cascading hooks).

MOTHER HANDLING
  REPRO2025 records no dam for adult cows. To keep id_mere non-empty (so editing
  a cow in the UI later does not trip validate_mere_obligatoire) without building
  a chain of fake cows, a single placeholder founder is created first:
      PLACEHOLDER_TN, est_achat=1  -> its required parent is a *Mere externe*
      (a leaf doctype), left empty -> NO link to another Animal -> no chain.
      statut=REFORME               -> excluded from active-herd KPIs (filters
                                      that use statut='ACTIF' ignore it).
  90 cows link to this placeholder; 9 cows get their REAL dam (DAM_LINKS, recovered
  from génisses_IA where the heifer + its mother are both in the current herd) via
  a post-pass that overrides id_mere after all animals exist.

INSERT FLAGS
  ignore_validate  -> skip validate_mere_obligatoire; we replicate the few useful
                      derivations explicitly (nom_metier, sexe, etat_gestation).
  ignore_mandatory -> belt-and-braces (all required fields are now populated).
  (Link validation still runs, so the placeholder is created BEFORE the 99, and
   every id_pere is a real Taureau — verified Taureau.name == uppercase sire.)

KNOWN DATA GAPS:
  - 2300254581 birth date -> estimated 2019-09-01 (2019 cohort, predates génisses_IA;
    supervisor confirms). All 4 former sire-gaps now have REAL sires recovered from
    génisses_IA (3385->MUSTIK, 3393->MUSTIK, 3405->MINSK, 3415->MINSK), so the old
    "INCONNU" placeholder sire is no longer used.

Run (dev):
    bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.import_animal.run --kwargs '{"dry_run": 1}'
Run (prod):
    docker compose exec backend bench --site <site> execute hmd_agro.hmd_agro.setup.import_animal.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe

PLACEHOLDER_TN = "0009999999"   # founder mother for cows with no recoverable dam.
# Deliberately LOW (~10M): Velage._create_calf auto-numbers calves as
# MAX(identification_tn)+1, so a near-9999999999 placeholder would push calf IDs
# to 11 digits. Low keeps it out of that max. nom_metier stays "9999".
IMPORT_LOT = "LOT1"

# Real dams recovered from génisses_IA (heifer -> in-herd mother). Applied as a
# post-pass after all 99 exist, replacing the placeholder mother for these 9.
DAM_LINKS = {
    "2300259203": "2300254560",
    "2300261986": "2300254544",
    "2300273393": "2300254540",
    "2300273394": "2300254525",
    "2300273405": "2300254576",
    "2300273406": "2300254587",
    "2300273410": "2300254604",
    "2300273411": "2300254546",
    "2300273415": "2300254605",
}

# (identification_tn, date_naissance ISO|None, id_pere uppercase|None)
HERD = [
    ("2300254525", "2019-08-30", "MARMADUC"),
    ("2300254578", "2019-10-07", "MARLEY"),
    ("2300254598", "2019-08-07", "MESSI"),
    ("2300254583", "2019-08-21", "LOGIN"),
    ("2300254592", "2019-09-28", "MARLEY"),
    ("2300254597", "2019-10-21", "MALAVITA"),
    ("2300254586", "2019-08-01", "MALOR"),
    ("2300254591", "2019-11-05", "ELASTAR"),
    ("2300254560", "2019-06-03", "MINNESOTA"),
    ("2300254540", "2019-11-18", "MALAVITA"),
    ("2300254550", "2019-11-10", "HELUX"),
    ("2300254568", "2019-10-29", "ILANNE"),
    ("2300254544", "2019-10-12", "MARADONA"),
    ("2300254541", "2019-10-25", "HALLEZ"),
    ("2300254605", "2019-11-08", "NESTRA"),
    ("2300254577", "2019-11-22", "HELUX"),
    ("2300254572", "2019-08-29", "MAYFLOWER"),
    ("2300254587", "2019-08-25", "MESSI"),
    ("2300254575", "2019-11-13", "NICKY"),
    ("2300254549", "2019-08-27", "LELABEL"),
    ("2300254556", "2019-07-31", "MALPUECH"),
    ("2300254519", "2019-08-03", "MARMADUC"),
    ("2300254607", "2019-09-15", "MINSK"),
    ("2300254585", "2019-10-01", "MORENO"),
    ("2300254520", "2020-02-12", "NEKFEU"),
    ("2300254551", "2019-10-20", "MARMADUC"),
    ("2300254576", "2019-10-20", "MILLENIUM"),
    ("2300254603", "2019-06-03", "GARGANO"),
    ("2300254559", "2019-08-01", "MILKYWAY"),
    ("2300254529", "2019-09-22", "GIOVANNI"),
    ("2300254573", "2019-08-15", "MARMADUC"),
    ("2300254574", "2019-10-05", "HELUX"),
    ("2300254581", "2019-09-01", "NIRVANAVR"),  # date estimated (2019 cohort) — supervisor to confirm
    ("2300254609", "2019-10-12", "MINNESOTA"),
    ("2300254582", "2019-08-01", "NOBIN"),
    ("2300254610", "2019-11-09", "HALLEZ"),
    ("2300254604", "2019-08-28", "MOBIDIC"),
    ("2300254569", "2019-12-28", "NIRVANAVR"),
    ("2300254566", "2019-11-03", "NICKY"),
    ("2300254546", "2019-08-07", "MALAVITA"),
    ("2300254579", "2019-12-16", "NEKFEU"),
    ("2300254528", "2019-11-10", "NEKFEU"),
    ("2300254518", "2019-08-07", "MERCHANT"),
    ("2300254532", "2019-08-08", "GONESSE"),
    ("2300254565", "2019-07-16", "MARADONA"),
    ("2300254561", "2019-09-15", "MILTON"),
    ("2300254543", "2019-10-19", "MESSI"),
    ("2300254527", "2019-08-19", "MAGIMOND"),
    ("2300254534", "2019-10-15", "MERCHANT"),
    ("2300254562", "2019-08-10", "MERIBEL"),
    ("2300254589", "2019-07-20", "MORTIMER"),
    ("2300254554", "2019-11-30", "MIGUEL"),
    ("2300254600", "2019-07-26", "MARMADUC"),
    ("2300254595", "2019-09-13", "MINNESOTA"),
    ("2300254570", "2019-06-20", "MANHATTAN"),
    ("2300254538", "2019-08-19", "GOODYEAR"),
    ("2300254590", "2019-09-12", "MILTON"),
    ("2300254539", "2019-09-07", "MARLEY"),
    ("2300254553", "2019-10-20", "MINSK"),
    ("2300254599", "2019-07-29", "MARMADUC"),
    ("2300254557", "2019-09-21", "MARATHON"),
    ("2300254555", "2019-09-22", "MAGIMOND"),
    ("2300254516", "2019-09-06", "MAYFLOWER"),
    ("2300254602", "2019-09-13", "MARLEY"),
    ("2300254548", "2019-11-27", "MARSHAL"),
    ("2300254558", "2019-10-20", "GONESSE"),
    ("2300254547", "2020-01-26", "NAGUI"),
    ("2300254584", "2020-03-08", "MALOR"),
    ("2300254608", "2019-07-16", "MALAVITA"),
    ("2300254521", "2019-11-26", "MALOR"),
    ("2300254612", "2021-12-13", "INTERPOL"),
    ("2300259224", "2022-02-18", "PANDORE"),
    ("2300254613", "2022-01-09", "PITCHOU"),
    ("2300261968", "2022-03-19", "FARAGO"),
    ("2300261976", "2022-03-22", "OCHAMPAS"),
    ("2300261957", "2022-03-11", "ONDURAS"),
    ("2300259222", "2022-02-16", "PITCHOU"),
    ("2300261984", "2022-04-10", "MALOR"),
    ("2300259229", "2022-02-21", "ODYNO"),
    ("2300261979", "2022-03-26", "PRIMO"),
    ("2300261964", "2022-03-15", "PRETTO"),
    ("2300261978", "2022-03-26", "PAGNOL"),
    ("2300261953", "2022-03-09", "HELUX"),
    ("2300261974", "2022-03-22", "INTERPOL"),
    ("2300261975", "2022-03-22", "INTERPOL"),
    ("2300261983", "2022-04-06", "OWINGS"),
    ("2300259203", "2022-02-04", "PIAGGIO"),
    ("2300261971", "2022-03-21", "PISCO"),
    ("2300273394", "2023-02-26", "MINSK"),
    ("2300261986", "2022-12-09", "LEBELOR"),
    ("2300273397", "2023-03-01", "MINSK"),
    ("2300273411", "2023-04-22", "MINSK"),
    ("2300261999", "2023-01-31", "MUSTIK"),
    ("2300273410", "2023-04-11", "MINSK"),
    ("2300273406", "2023-03-26", "MINSK"),
    ("2300273405", "2023-03-24", "MINSK"),   # sire recovered from génisses_IA
    ("2300273393", "2023-02-25", "MUSTIK"),  # sire recovered from génisses_IA
    ("2300273385", "2023-02-14", "MUSTIK"),  # sire recovered from génisses_IA
    ("2300273415", "2023-05-15", "MINSK"),   # sire recovered from génisses_IA
]


def _placeholder_doc():
    return {
        "doctype": "Animal",
        "identification_tn": PLACEHOLDER_TN,
        "nom": "Mère placeholder (import)",
        "nom_metier": PLACEHOLDER_TN[-4:],
        "race": "Holstein",
        "categorie": "VACHE",
        "sexe": "F",
        "date_naissance": "2010-01-01",
        "est_achat": 1,
        "date_entree": "2010-01-01",
        "prix_achat": 0,
        "statut": "REFORME",
        "date_sortie": "2015-01-01",
        "etat_gestation": "VIDE",
    }


def _insert(doc_dict):
    doc = frappe.get_doc(doc_dict)
    doc.flags.ignore_validate = True
    doc.flags.ignore_mandatory = True
    doc.flags.lot_change_source = "IMPORT"
    doc.insert(ignore_permissions=True)
    return doc


def run(dry_run=True):
    dry_run = int(dry_run)
    created = skipped = 0
    errors = []
    missing_sire, missing_date, unresolved_pere = [], [], []

    # sanity: target lot must exist
    if not frappe.db.exists("Lot", IMPORT_LOT):
        print(f"[ABORT] target lot '{IMPORT_LOT}' does not exist.")
        return {"aborted": True}

    # --- 1. placeholder founder mother (must exist before the 99 link to it) ---
    if frappe.db.exists("Animal", PLACEHOLDER_TN):
        ph_state = "exists"
    else:
        ph_state = "create"
        if not dry_run:
            _insert(_placeholder_doc())

    # --- 2. the 99 cows ---
    for tn, naissance, pere in HERD:
        try:
            if frappe.db.exists("Animal", tn):
                skipped += 1
                continue
            if not pere:
                missing_sire.append(tn)
            elif not frappe.db.exists("Taureau", pere):
                unresolved_pere.append((tn, pere))
            if not naissance:
                missing_date.append(tn)

            doc_dict = {
                "doctype": "Animal",
                "identification_tn": tn,
                "nom_metier": tn[-4:],
                "race": "Holstein",
                "categorie": "VACHE",
                "sexe": "F",
                "date_naissance": naissance,
                "est_achat": 0,
                "id_mere": PLACEHOLDER_TN,
                "id_pere": pere,
                "id_lot": IMPORT_LOT,
                "statut": "ACTIF",
                "etat_gestation": "VIDE",
            }
            if not dry_run:
                _insert(doc_dict)
            created += 1
        except Exception as e:
            errors.append({"tn": tn, "error": str(e)})

    # --- 3. real dams recovered from génisses_IA (replace placeholder for these 9) ---
    dam_applied = 0
    if not dry_run:
        for daughter, dam in DAM_LINKS.items():
            if frappe.db.exists("Animal", daughter) and frappe.db.exists("Animal", dam):
                frappe.db.set_value("Animal", daughter, "id_mere", dam)
                dam_applied += 1

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Animal import — current herd into lot '{IMPORT_LOT}'")
    print(f"  placeholder mother {PLACEHOLDER_TN}: {ph_state}")
    print(f"  real dams applied (génisses_IA): {dam_applied}/{len(DAM_LINKS)}")
    print(f"  cows would-create={created}, skipped(existing)={skipped}, errors={len(errors)}")
    print(f"  gap - no sire ({len(missing_sire)}): {missing_sire}")
    print(f"  gap - no birth date ({len(missing_date)}): {missing_date}")
    if unresolved_pere:
        print(f"  WARN - sire not found as Taureau ({len(unresolved_pere)}): {unresolved_pere}")
    for e in errors[:5]:
        print(f"  ERR {e['tn']}: {e['error']}")

    return {
        "placeholder": ph_state,
        "dams_applied": dam_applied,
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "missing_sire": missing_sire,
        "missing_date": missing_date,
        "unresolved_pere": unresolved_pere,
    }
