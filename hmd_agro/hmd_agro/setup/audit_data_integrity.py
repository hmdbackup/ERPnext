"""
Data integrity audit (READ ONLY). Cross-references Animal records against
all event tables (Lactation, Velage, Insemination, Avortement, Traite) and
reports anomalies relative to what the production code expects.

Each section reports:
  - total rows checked
  - anomaly count
  - up to 10 example records (name + summary)

Run:
    bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.audit_data_integrity.run

The script makes ZERO writes. Safe to run anytime.
"""
import frappe
from collections import defaultdict


def hdr(t):
    print("\n" + "═" * 76 + "\n  " + t + "\n" + "═" * 76)


def sub(t):
    print(f"\n  ── {t} " + "─" * (70 - len(t)))


def report_examples(rows, fmt, n=10):
    for r in rows[:n]:
        print(f"    · {fmt(r)}")
    if len(rows) > n:
        print(f"    · ... and {len(rows) - n} more")


def run():
    # ─── ANIMAL STATUS COHERENCE ──────────────────────────────────────
    hdr("1. ANIMAL — status / sortie coherence")

    sub("A. statut=ACTIF but date_sortie is set (inconsistent)")
    rows = frappe.db.sql("""
        SELECT name, statut, date_sortie, categorie
        FROM `tabAnimal`
        WHERE statut = 'ACTIF' AND date_sortie IS NOT NULL
        ORDER BY date_sortie DESC
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  cat={r.categorie}  date_sortie={r.date_sortie}")

    sub("B. statut != ACTIF (VENDU/MORT/REFORME) but date_sortie is NULL")
    rows = frappe.db.sql("""
        SELECT name, statut, categorie
        FROM `tabAnimal`
        WHERE statut IN ('VENDU', 'MORT', 'REFORME') AND date_sortie IS NULL
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  statut={r.statut}  cat={r.categorie}")

    sub("C. est_achat=1 but date_entree is NULL (required field missing)")
    rows = frappe.db.sql("""
        SELECT name, categorie, date_naissance
        FROM `tabAnimal`
        WHERE est_achat = 1 AND date_entree IS NULL
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  cat={r.categorie}  naissance={r.date_naissance}")

    # ─── ANIMAL CATEGORIE vs EVENT HISTORY (the strict check) ─────────
    hdr("2. ANIMAL — categorie vs event history (strict reconstruction)")

    sub("A. categorie=VACHE but NO Velage record (production will treat as GENISSE)")
    rows = frappe.db.sql("""
        SELECT a.name, a.statut, a.date_naissance, a.etat_lactation, a.etat_gestation
        FROM `tabAnimal` a
        LEFT JOIN `tabVelage` v ON v.animal = a.name
        WHERE a.categorie = 'VACHE'
          AND a.sexe = 'F'
          AND v.name IS NULL
        GROUP BY a.name
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    print(f"    Impact: these animals will be bucketed as 'Gén. - Vide' (or - Pleine)")
    print(f"    in effectif_on_date / Rapport Mensuel, NOT as Vaches.")
    report_examples(rows, lambda r: f"{r.name}  statut={r.statut}  "
                    f"etat_lact={r.etat_lactation}  etat_gest={r.etat_gestation}")

    sub("B. categorie=GENISSE but HAS Velage record (should be VACHE)")
    rows = frappe.db.sql("""
        SELECT a.name, COUNT(v.name) AS n_velages, MIN(v.date_velage) AS first_vel
        FROM `tabAnimal` a
        JOIN `tabVelage` v ON v.animal = a.name
        WHERE a.categorie = 'GENISSE'
        GROUP BY a.name
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    print(f"    Impact: Velage hook should have promoted to VACHE but didn't.")
    report_examples(rows, lambda r: f"{r.name}  n_velages={r.n_velages}  first={r.first_vel}")

    sub("C. categorie=GENISSE AND etat_lactation=TARIE (illogical — genisse can't be tarie)")
    rows = frappe.db.sql("""
        SELECT name, etat_lactation, statut
        FROM `tabAnimal`
        WHERE categorie = 'GENISSE' AND etat_lactation = 'TARIE'
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  statut={r.statut}  etat_lact={r.etat_lactation}")

    sub("D. categorie=VACHE AND etat_lactation=EN_PRODUCTION but no EN_COURS Lactation")
    rows = frappe.db.sql("""
        SELECT a.name, COUNT(l.name) AS n_en_cours
        FROM `tabAnimal` a
        LEFT JOIN `tabLactation` l ON l.animal = a.name AND l.statut = 'EN_COURS'
        WHERE a.categorie = 'VACHE'
          AND a.etat_lactation = 'EN_PRODUCTION'
          AND a.statut = 'ACTIF'
        GROUP BY a.name
        HAVING n_en_cours = 0
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    print(f"    Impact: report shows in EN_PRODUCTION but no active Lactation record")
    print(f"    means Traites have nothing to attach to.")
    report_examples(rows, lambda r: f"{r.name}  n_en_cours_lactations={r.n_en_cours}")

    sub("E. categorie=VACHE AND etat_lactation=TARIE but most recent Lactation isn't TARIE")
    rows = frappe.db.sql("""
        SELECT a.name, a.etat_lactation,
               (SELECT statut FROM `tabLactation`
                WHERE animal=a.name ORDER BY date_debut DESC LIMIT 1) AS latest_lact_statut
        FROM `tabAnimal` a
        WHERE a.categorie = 'VACHE'
          AND a.etat_lactation = 'TARIE'
          AND a.statut = 'ACTIF'
        HAVING latest_lact_statut != 'TARIE' OR latest_lact_statut IS NULL
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  animal.etat_lact={r.etat_lactation}  "
                    f"latest_lactation_statut={r.latest_lact_statut}")

    # ─── VELAGE INTEGRITY ─────────────────────────────────────────────
    hdr("3. VELAGE — calf records & lactation linkage")

    sub("A. Velage with vivant_veau1=1 but id_veau1 is NULL (calf Animal not created)")
    rows = frappe.db.sql("""
        SELECT name, animal, date_velage, sexe_veau1
        FROM `tabVelage`
        WHERE vivant_veau1 = 1 AND (id_veau1 IS NULL OR id_veau1 = '')
        ORDER BY date_velage DESC
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    print(f"    Impact: the calf-creation hook didn't fire (probably db_insert bypass)")
    report_examples(rows, lambda r: f"{r.name}  mother={r.animal}  date={r.date_velage}  "
                    f"sexe1={r.sexe_veau1}")

    sub("B. Velage with nombre_veaux=2, vivant_veau2=1, but id_veau2 is NULL")
    rows = frappe.db.sql("""
        SELECT name, animal, date_velage
        FROM `tabVelage`
        WHERE nombre_veaux = '2' AND vivant_veau2 = 1
          AND (id_veau2 IS NULL OR id_veau2 = '')
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  mother={r.animal}  date={r.date_velage}")

    sub("C. Velage with id_veau1 set but the calf Animal doesn't exist (broken FK)")
    rows = frappe.db.sql("""
        SELECT v.name, v.animal, v.id_veau1
        FROM `tabVelage` v
        LEFT JOIN `tabAnimal` a ON a.name = v.id_veau1
        WHERE v.id_veau1 IS NOT NULL AND v.id_veau1 != '' AND a.name IS NULL
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  mother={r.animal}  missing_calf={r.id_veau1}")

    sub("D. Velage with `lactation` set but the Lactation doesn't exist (broken FK)")
    rows = frappe.db.sql("""
        SELECT v.name, v.animal, v.lactation
        FROM `tabVelage` v
        LEFT JOIN `tabLactation` l ON l.name = v.lactation
        WHERE v.lactation IS NOT NULL AND v.lactation != '' AND l.name IS NULL
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  mother={r.animal}  missing_lact={r.lactation}")

    # ─── LACTATION INTEGRITY ──────────────────────────────────────────
    hdr("4. LACTATION — status / dates coherence")

    sub("A. statut=TARIE but date_tarissement is NULL")
    rows = frappe.db.sql("""
        SELECT name, animal, date_debut, statut
        FROM `tabLactation`
        WHERE statut = 'TARIE' AND date_tarissement IS NULL
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  animal={r.animal}  date_debut={r.date_debut}")

    sub("B. date_tarissement set but statut=EN_COURS (should be TARIE)")
    rows = frappe.db.sql("""
        SELECT name, animal, statut, date_tarissement
        FROM `tabLactation`
        WHERE date_tarissement IS NOT NULL AND statut = 'EN_COURS'
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  animal={r.animal}  "
                    f"date_tar={r.date_tarissement}  statut={r.statut}")

    sub("C. Multiple EN_COURS Lactations for the same animal (only one should be active)")
    rows = frappe.db.sql("""
        SELECT animal, COUNT(*) AS n_en_cours,
               GROUP_CONCAT(name SEPARATOR ', ') AS names
        FROM `tabLactation`
        WHERE statut = 'EN_COURS'
        GROUP BY animal
        HAVING n_en_cours > 1
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"animal={r.animal}  n={r.n_en_cours}  "
                    f"lactations=[{r.names[:80]}]")

    sub("D. Lactation with velage_debut set but the Velage doesn't exist (broken FK)")
    rows = frappe.db.sql("""
        SELECT l.name, l.animal, l.velage_debut
        FROM `tabLactation` l
        LEFT JOIN `tabVelage` v ON v.name = l.velage_debut
        WHERE l.velage_debut IS NOT NULL AND l.velage_debut != '' AND v.name IS NULL
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  animal={r.animal}  "
                    f"missing_velage={r.velage_debut}")

    # ─── INSEMINATION INTEGRITY ───────────────────────────────────────
    hdr("5. INSEMINATION — gestation outcome coherence")

    sub("A. resultat=REUSSIE on a non-existent or wrong-status Animal")
    rows = frappe.db.sql("""
        SELECT i.name, i.animal, i.date_ia, a.statut, a.etat_gestation
        FROM `tabInsemination` i
        LEFT JOIN `tabAnimal` a ON a.name = i.animal
        WHERE i.resultat = 'REUSSIE' AND a.name IS NULL
    """, as_dict=True)
    print(f"    Found (broken FK): {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  animal={r.animal}")

    sub("B. resultat=REUSSIE older than 320 days with no follow-up Velage / Avortement")
    rows = frappe.db.sql("""
        SELECT i.name, i.animal, i.date_ia, DATEDIFF(CURDATE(), i.date_ia) AS days_ago
        FROM `tabInsemination` i
        LEFT JOIN `tabVelage` v ON v.animal = i.animal AND v.date_velage > i.date_ia
        LEFT JOIN `tabAvortement` av ON av.animal = i.animal AND av.date_avortement > i.date_ia
        WHERE i.resultat = 'REUSSIE'
          AND DATEDIFF(CURDATE(), i.date_ia) > 320
          AND v.name IS NULL AND av.name IS NULL
        GROUP BY i.name
    """, as_dict=True)
    print(f"    Found: {len(rows)} (normal gestation = ~280 days; 320+ = orphan IA)")
    report_examples(rows, lambda r: f"{r.name}  animal={r.animal}  "
                    f"ia={r.date_ia}  days_ago={r.days_ago}")

    # ─── TRAITE INTEGRITY ─────────────────────────────────────────────
    hdr("6. TRAITE — milking record coherence")

    sub("A. Traite with lactation set but Lactation doesn't exist (broken FK)")
    rows = frappe.db.sql("""
        SELECT t.name, t.animal, t.date_traite, t.lactation
        FROM `tabTraite` t
        LEFT JOIN `tabLactation` l ON l.name = t.lactation
        WHERE t.lactation IS NOT NULL AND t.lactation != '' AND l.name IS NULL
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  animal={r.animal}  "
                    f"date={r.date_traite}  missing_lact={r.lactation}")

    sub("B. Traite on an Animal with statut != ACTIF on the date (animal was already gone)")
    rows = frappe.db.sql("""
        SELECT t.name, t.animal, t.date_traite, a.statut, a.date_sortie
        FROM `tabTraite` t
        JOIN `tabAnimal` a ON a.name = t.animal
        WHERE a.statut != 'ACTIF' AND a.date_sortie IS NOT NULL
          AND t.date_traite > a.date_sortie
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  animal={r.animal}  "
                    f"date_traite={r.date_traite}  date_sortie={r.date_sortie}")

    # ─── AVORTEMENT INTEGRITY ─────────────────────────────────────────
    hdr("7. AVORTEMENT — coherence with IA")

    sub("A. Avortement linked to non-existent Insemination (broken FK)")
    rows = frappe.db.sql("""
        SELECT av.name, av.animal, av.insemination
        FROM `tabAvortement` av
        LEFT JOIN `tabInsemination` i ON i.name = av.insemination
        WHERE av.insemination IS NOT NULL AND av.insemination != ''
          AND i.name IS NULL
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  animal={r.animal}  "
                    f"missing_ia={r.insemination}")

    sub("B. date_avortement before linked Insemination's date_ia (illogical)")
    rows = frappe.db.sql("""
        SELECT av.name, av.animal, av.date_avortement, i.date_ia
        FROM `tabAvortement` av
        JOIN `tabInsemination` i ON i.name = av.insemination
        WHERE av.date_avortement < i.date_ia
    """, as_dict=True)
    print(f"    Found: {len(rows)}")
    report_examples(rows, lambda r: f"{r.name}  animal={r.animal}  "
                    f"date_avo={r.date_avortement}  date_ia={r.date_ia}")

    # ─── SUMMARY ──────────────────────────────────────────────────────
    hdr("SUMMARY — population sanity")
    print(f"\n  Total Animals: {frappe.db.count('Animal')}")
    print(f"     statut=ACTIF: {frappe.db.count('Animal', {'statut': 'ACTIF'})}")
    print(f"  Total Velage:    {frappe.db.count('Velage')}")
    print(f"  Total Lactation: {frappe.db.count('Lactation')}")
    print(f"     statut=EN_COURS: {frappe.db.count('Lactation', {'statut': 'EN_COURS'})}")
    print(f"     statut=TARIE:    {frappe.db.count('Lactation', {'statut': 'TARIE'})}")
    print(f"  Total Insemination: {frappe.db.count('Insemination')}")
    print(f"     resultat=REUSSIE: {frappe.db.count('Insemination', {'resultat': 'REUSSIE'})}")
    print(f"  Total Avortement: {frappe.db.count('Avortement')}")
    print(f"  Total Traite:     {frappe.db.count('Traite')}")
    print()
