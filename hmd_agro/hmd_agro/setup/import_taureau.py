"""Import Taureau records used at HMD Agro farm.

Source: Etable HMD 2025 (1).xls, deduplicated across sheets:
- REPRO2025 (Père Nom + IZU + Lait + CD) — adult-cow sires
- velle_2024 (Père Nom + ...) — sires of 2024-born heifers
- génisses_IA (PÈRE NOM + ...) — heifer-IA sires

For sires appearing in multiple rows with conflicting IZU/Lait,
the most-frequent value was chosen (PISCO is the exception — first
real row from REPRO2025 used since automatic picking produced a
phantom combination).

CD (coefficient de détermination) is NOT in the Frappe Taureau
schema, so the Excel CD column is dropped here.

Race defaults to "Holstein" for all sires (farm-wide convention).
code_taureau is set equal to nom_taureau (Excel has no separate code).

Usage:
    bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.import_taureau.run --kwargs '{"dry_run": 1}'

Set dry_run=0 to commit.
"""
import frappe


SIRES = [
    {"nom": "ELASTAR", "izu": 119, "lait": 161},
    {"nom": "FANFANI", "izu": 106, "lait": 88},
    {"nom": "FARAGO", "izu": 96, "lait": 138},
    {"nom": "FORCLAZ", "izu": 120, "lait": 614},
    {"nom": "GARGANO", "izu": 104, "lait": 4},
    {"nom": "GIOVANNI", "izu": 96, "lait": 217},
    {"nom": "GONESSE", "izu": 120, "lait": 424},
    {"nom": "GOODYEAR", "izu": 125, "lait": 875},
    {"nom": "HALLEZ", "izu": 118, "lait": 90},
    {"nom": "HELUX", "izu": 126, "lait": 1102},
    {"nom": "ILANNE", "izu": 146, "lait": 529},
    {"nom": "INTERPOL", "izu": 114, "lait": 751},
    {"nom": "LEBELOR", "izu": 132, "lait": 1250},
    {"nom": "LELABEL", "izu": 137, "lait": 1205},
    {"nom": "LOGIN", "izu": 132, "lait": 1269},
    {"nom": "MACINTOSCH", "izu": 127, "lait": 389},
    {"nom": "MAGIMOND", "izu": 128, "lait": 277},
    {"nom": "MALAVITA", "izu": 148, "lait": 421},
    {"nom": "MALOR", "izu": 124, "lait": 518},
    {"nom": "MALPUECH", "izu": 144, "lait": 881},
    {"nom": "MANHATTAN", "izu": 139, "lait": -75},
    {"nom": "MARADONA", "izu": 81, "lait": 852},
    {"nom": "MARATHON", "izu": 130, "lait": 422},
    {"nom": "MARLEY", "izu": 153, "lait": 561},
    {"nom": "MARMADUC", "izu": 143, "lait": 952},
    {"nom": "MARSHAL", "izu": 103, "lait": 357},
    {"nom": "MAYFLOWER", "izu": 148, "lait": 612},
    {"nom": "MERCHANT", "izu": 134, "lait": 863},
    {"nom": "MERIBEL", "izu": 114, "lait": 881},
    {"nom": "MESSI", "izu": 114, "lait": 113},
    {"nom": "MIGUEL", "izu": 129, "lait": 621},
    {"nom": "MILKYWAY", "izu": 123, "lait": 666},
    {"nom": "MILLENIUM", "izu": 130, "lait": 774},
    {"nom": "MILTON", "izu": 164, "lait": 290},
    {"nom": "MINNESOTA", "izu": 133, "lait": 1044},
    {"nom": "MINSK", "izu": 121, "lait": 1072},
    {"nom": "MOBIDIC", "izu": 128, "lait": 541},
    {"nom": "MORENO", "izu": 133, "lait": 618},
    {"nom": "MORTIMER", "izu": 122, "lait": 885},
    {"nom": "MUSTIK", "izu": 116, "lait": 623},
    {"nom": "NAGUI", "izu": 126, "lait": 638},
    {"nom": "NEKFEU", "izu": 135, "lait": 542},
    {"nom": "NESTRA", "izu": 133, "lait": 387},
    {"nom": "NICKY", "izu": 125, "lait": 407},
    {"nom": "NIRVANAVR", "izu": 123, "lait": 736},
    {"nom": "NOBIN", "izu": 140, "lait": 573},
    {"nom": "NOIRON", "izu": 144, "lait": 2},
    {"nom": "NOKKIL JB", "izu": 140, "lait": 328},
    {"nom": "OATSIO", "izu": 143, "lait": 1225},
    {"nom": "OCHAMPAS", "izu": 130, "lait": 572},
    {"nom": "ODYNO", "izu": 155, "lait": 1190},
    {"nom": "OMALET", "izu": 162, "lait": 969},
    {"nom": "ONDURAS", "izu": 172, "lait": 1018},
    {"nom": "OSUCHAUX", "izu": 145, "lait": 1102},
    {"nom": "OTASIO", "izu": 139, "lait": 1141},
    {"nom": "OUIOUI", "izu": 134, "lait": 724},
    {"nom": "OWINGS", "izu": 166, "lait": 1150},
    {"nom": "PAGNOL", "izu": 138, "lait": 538},
    {"nom": "PANACLOC", "izu": 137, "lait": 927},
    {"nom": "PANDORE", "izu": 153, "lait": 1136},
    {"nom": "PARAGUAY", "izu": 147, "lait": 372},
    {"nom": "PECORINO", "izu": 154, "lait": 1410},
    {"nom": "PIADGIO", "izu": 149, "lait": 294},
    {"nom": "PIAGGIO", "izu": 148, "lait": 151},
    {"nom": "PIKATCHU", "izu": 160, "lait": 1177},
    {"nom": "PISCO", "izu": 141, "lait": 395},
    {"nom": "PITCHOU", "izu": 149, "lait": 1315},
    {"nom": "POTEMKINE", "izu": 147, "lait": 1225},
    {"nom": "PRETTO", "izu": 162, "lait": 1679},
    {"nom": "PRIMO", "izu": 168, "lait": -217},
    {"nom": "STEVENSON", "izu": 154, "lait": 886},
    # --- Current-breeding sires (col64 "Taureau Utilisé"), added 2026-06-03 for
    # the Insemination import. izu/lait set to 0 (placeholder): the Excel's
    # col65/66 indices are unreliable (duplicated across distinct bulls), so the
    # supervisor fills real genetics later. OXIBUL and OBERNAY are the canonical
    # spellings of two misspelled pairs (OXIBUL/OXYBUL, OBERNAY/OBERNEY); the IA
    # import maps the rarer variant to these.
    {"nom": "OGOOD", "izu": 0, "lait": 0},
    {"nom": "REDBOY", "izu": 0, "lait": 0},
    {"nom": "RIMAC", "izu": 0, "lait": 0},
    {"nom": "TOBLERONE", "izu": 0, "lait": 0},
    {"nom": "OXIBUL", "izu": 0, "lait": 0},
    {"nom": "OBERNAY", "izu": 0, "lait": 0},
    # 2026 re-bake: new sires from the current cycle (Repro2026). "X S" sexed
    # variants normalised to the base name at IA generation; izu/lait placeholder.
    {"nom": "THOMSON", "izu": 0, "lait": 0},
    {"nom": "UCCRFAY", "izu": 0, "lait": 0},
]


def run(dry_run=True):
    dry_run = int(dry_run)
    posted, skipped, errors = 0, 0, []

    for sire in SIRES:
        nom = sire["nom"]
        try:
            if frappe.db.exists("Taureau", nom):
                skipped += 1
                continue

            doc = frappe.get_doc({
                "doctype": "Taureau",
                "nom_taureau": nom,
                "code_taureau": nom,
                "race": "Holstein",
                "izu": sire["izu"],
                "lait": sire["lait"],
            })
            if not dry_run:
                doc.insert(ignore_permissions=True)
            posted += 1

        except Exception as e:
            errors.append({"nom": nom, "error": str(e)})

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Taureau import: posted={posted}, skipped={skipped}, errors={len(errors)}")
    if errors:
        print("First 5 errors:")
        for e in errors[:5]:
            print(f"  {e['nom']}: {e['error']}")

    return {"posted": posted, "skipped": skipped, "errors": errors}
