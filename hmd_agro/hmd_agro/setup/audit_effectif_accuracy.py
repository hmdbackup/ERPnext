"""
Cross-check the Effectif report against actual events in the system.

For each sampled event date, we:
  1. Query the raw event tables (Velage / Avortement / Animal exit / Lactation
     tarissement) to know what SHOULD show up.
  2. Run `_effectif(ctx)` in Jour mode for that date.
  3. Compare row-by-row.

Read-only. Run:
    bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.audit_effectif_accuracy.run
"""
import random

import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import _effectif


# Hard caps so the audit stays under ~30s
N_VELAGE_SAMPLES = 8
N_TARISSEMENT_SAMPLES = 5
N_AVORTEMENT_SAMPLES = 3
N_EXIT_SAMPLES = 5


def hdr(t):
    print("\n" + "═" * 76 + "\n  " + t + "\n" + "═" * 76)


def sub(t):
    print(f"\n  ── {t} " + "─" * (70 - len(t)))


def _run_effectif(date):
    """Run Effectif in Jour mode, return rows keyed by ligne for easy lookup."""
    ctx = {
        "date_filter": getdate(date),
        "date_debut": getdate(date),
        "date_fin": getdate(date),
        "nb_jours": 1,
        "effectif_mode": "Jour",
    }
    _, rows = _effectif(ctx)
    return {r.get("ligne"): r for r in rows}


def _check(cond, msg, results):
    if cond:
        print(f"     ✓ {msg}")
        results["pass"] += 1
    else:
        print(f"     ✗ {msg}")
        results["fail"] += 1


def run():
    results = {"pass": 0, "fail": 0}
    random.seed(42)  # reproducible sample selection

    # ─── 1. VELAGES — check Vêlage + Naissance counts ─────────────────
    hdr("1. VELAGE cross-check (Vêlage + Naissance + cat+/cat- effects)")

    velage_dates = frappe.db.sql_list("""
        SELECT DISTINCT date_velage FROM `tabVelage`
        WHERE date_velage IS NOT NULL
          AND date_velage <= CURDATE()
        ORDER BY date_velage DESC LIMIT 50
    """)
    sample = random.sample(velage_dates, min(N_VELAGE_SAMPLES, len(velage_dates)))
    print(f"  Sampling {len(sample)} velage dates")

    for d in sorted(sample):
        sub(f"Date: {d}")
        # Raw count of velages that day
        velages = frappe.db.sql("""
            SELECT name, animal, nombre_veaux,
                   sexe_veau1, vivant_veau1, sexe_veau2, vivant_veau2
            FROM `tabVelage` WHERE date_velage = %s
        """, d, as_dict=True)
        n_velages_expected = len(velages)

        # Expected live births: count vivant veau1 + vivant veau2 (twin) per row
        veaux_alive, velles_alive = 0, 0
        veaux_dead, velles_dead = 0, 0  # for Mort-né count
        for v in velages:
            if v.vivant_veau1:
                if v.sexe_veau1 == "M":
                    veaux_alive += 1
                else:
                    velles_alive += 1
            else:
                if v.sexe_veau1 == "M":
                    veaux_dead += 1
                else:
                    velles_dead += 1
            if v.nombre_veaux == "2":
                if v.vivant_veau2:
                    if v.sexe_veau2 == "M":
                        veaux_alive += 1
                    else:
                        velles_alive += 1
                else:
                    if v.sexe_veau2 == "M":
                        veaux_dead += 1
                    else:
                        velles_dead += 1
        naissance_total_expected = veaux_alive + velles_alive
        mort_ne_total_expected = veaux_dead + velles_dead

        rows = _run_effectif(d)

        # Vêlage row
        vrow = rows.get("Vêlage", {})
        v_total = vrow.get("Total", 0)
        print(f"     Velages in DB: {n_velages_expected}  |  "
              f"Report Vêlage.Total: {v_total}")
        _check(v_total == n_velages_expected,
               f"Vêlage Total = {n_velages_expected}",
               results)

        # Naissance row
        nrow = rows.get("Naissance", {})
        n_total = nrow.get("Total", 0)
        n_veaux = nrow.get("Veaux", 0)
        n_velles = nrow.get("Velles", 0)
        print(f"     Live births in DB: M={veaux_alive} F={velles_alive} "
              f"total={naissance_total_expected}  |  "
              f"Report Naissance: Veaux={n_veaux} Velles={n_velles} "
              f"Total={n_total}")
        _check(n_total == naissance_total_expected,
               f"Naissance Total = {naissance_total_expected}", results)
        _check(n_veaux == veaux_alive and n_velles == velles_alive,
               f"Naissance Veaux/Velles split = {veaux_alive}/{velles_alive}",
               results)

        # Mort-né row (joined in count_avortements_mort_nes)
        morow = rows.get("Avortement / Mort-né", {})
        if mort_ne_total_expected > 0:
            mo_total = morow.get("Total", 0)
            # Mort-né is included in Avortement total along with avortements
            # that day. Check it's at least the mort-né count.
            print(f"     Stillborns in DB: {mort_ne_total_expected}  |  "
                  f"Report Avortement+Mort-né.Total: {mo_total}")
            _check(mo_total >= mort_ne_total_expected,
                   f"Avortement+Mort-né Total >= {mort_ne_total_expected}",
                   results)

    # ─── 2. TARISSEMENTS — check Vaches Lact→Tarie transition ─────────
    hdr("2. TARISSEMENT cross-check (Vaches Lact → Tarie on tar date)")

    # A Lactation whose date_tarissement is the cursor date should result in
    # the mother showing as Tarie on that day (and being Lact the day before,
    # for live recomputed mode — Jour mode only shows imports/today's events,
    # so we'll check effectif_on_date directly instead).
    tar_dates = frappe.db.sql_list("""
        SELECT DISTINCT date_tarissement FROM `tabLactation`
        WHERE date_tarissement IS NOT NULL
          AND date_tarissement <= CURDATE()
        ORDER BY date_tarissement DESC LIMIT 30
    """)
    sample = random.sample(tar_dates, min(N_TARISSEMENT_SAMPLES, len(tar_dates)))
    print(f"  Sampling {len(sample)} tarissement dates")

    from hmd_agro.hmd_agro.utils.live_state import effectif_on_date
    from frappe.utils import add_days
    for d in sorted(sample):
        sub(f"Date: {d}")
        # Cows whose Lactation became TARIE on this exact date.
        cows_tariees_today = frappe.db.sql_list("""
            SELECT DISTINCT animal FROM `tabLactation`
            WHERE date_tarissement = %s AND statut = 'TARIE'
        """, d)
        print(f"     Lactations TARIE on this date: {len(cows_tariees_today)}")
        if not cows_tariees_today:
            print("     (skip — no tarissement that exact date)")
            continue

        # The day BEFORE should have all of them in Lact; the day OF tarissement
        # should have them in Tarie.
        eff_before = effectif_on_date(add_days(d, -1))
        eff_on = effectif_on_date(d)
        delta_lact = eff_on["Vaches - Lact."] - eff_before["Vaches - Lact."]
        delta_tar = eff_on["Vaches - Tarie"] - eff_before["Vaches - Tarie"]
        print(f"     Lact: {eff_before['Vaches - Lact.']} → "
              f"{eff_on['Vaches - Lact.']}  (Δ {delta_lact:+d})")
        print(f"     Tarie: {eff_before['Vaches - Tarie']} → "
              f"{eff_on['Vaches - Tarie']}  (Δ {delta_tar:+d})")
        # We can't assert exact equality if other events happen the same day
        # (velage closing a lactation also creates a new Lact), so just check
        # the Tarie delta is at least 0 and the Lact delta is at most 0 — the
        # tarissement events should NOT reduce the Tarie count or increase
        # the Lact count.
        _check(delta_tar >= 0, f"Vaches Tarie didn't decrease on tarissement date",
               results)
        _check(delta_lact <= 0, f"Vaches Lact didn't increase from tarissement",
               results)

    # ─── 3. AVORTEMENTS — check counts ────────────────────────────────
    hdr("3. AVORTEMENT cross-check")

    avo_dates = frappe.db.sql_list("""
        SELECT DISTINCT date_avortement FROM `tabAvortement`
        WHERE date_avortement IS NOT NULL
        ORDER BY date_avortement DESC LIMIT 20
    """)
    sample = random.sample(avo_dates, min(N_AVORTEMENT_SAMPLES, len(avo_dates)))
    print(f"  Sampling {len(sample)} avortement dates")

    for d in sorted(sample):
        sub(f"Date: {d}")
        n_avo = frappe.db.count("Avortement", {"date_avortement": d})
        # Mort-né counted with avortements
        velages_with_mort_ne = frappe.db.sql("""
            SELECT
              SUM(CASE WHEN vivant_veau1 = 0 THEN 1 ELSE 0 END
                + CASE WHEN nombre_veaux='2' AND vivant_veau2=0 THEN 1 ELSE 0 END) AS n
            FROM `tabVelage` WHERE date_velage = %s
        """, d)[0][0] or 0
        expected = n_avo + int(velages_with_mort_ne)

        rows = _run_effectif(d)
        morow = rows.get("Avortement / Mort-né", {})
        actual = morow.get("Total", 0)
        print(f"     Avortements: {n_avo}  Mort-nés: {velages_with_mort_ne}  "
              f"Expected Total: {expected}  |  Report: {actual}")
        _check(actual == expected,
               f"Avortement+Mort-né Total = {expected}", results)

    # ─── 4. ANIMAL EXITS (vente/mort/réforme) ─────────────────────────
    hdr("4. EXIT cross-check (Vente / Mortalité / Réforme)")

    exit_dates = frappe.db.sql_list("""
        SELECT DISTINCT date_sortie FROM `tabAnimal`
        WHERE date_sortie IS NOT NULL AND date_sortie <= CURDATE()
        ORDER BY date_sortie DESC LIMIT 30
    """)
    sample = random.sample(exit_dates, min(N_EXIT_SAMPLES, len(exit_dates)))
    print(f"  Sampling {len(sample)} exit dates")

    for d in sorted(sample):
        sub(f"Date: {d}")
        by_statut = {row.statut: row.n for row in frappe.db.sql("""
            SELECT statut, COUNT(*) AS n FROM `tabAnimal`
            WHERE date_sortie = %s GROUP BY statut
        """, d, as_dict=True)}

        rows = _run_effectif(d)
        # Vente qty
        vente_row = rows.get("Vente (Quantité)", {})
        v_actual = vente_row.get("Total", 0)
        v_expected = by_statut.get("VENDU", 0)
        print(f"     Vente DB: {v_expected}  |  Report: {v_actual}")
        _check(v_actual == v_expected, f"Vente Total = {v_expected}", results)

        # Mortalité
        m_actual = rows.get("Mortalité", {}).get("Total", 0)
        m_expected = by_statut.get("MORT", 0)
        print(f"     Mort DB: {m_expected}  |  Report: {m_actual}")
        _check(m_actual == m_expected, f"Mortalité Total = {m_expected}", results)

        # Réforme
        r_actual = rows.get("Réforme", {}).get("Total", 0)
        r_expected = by_statut.get("REFORME", 0)
        print(f"     Réforme DB: {r_expected}  |  Report: {r_actual}")
        _check(r_actual == r_expected, f"Réforme Total = {r_expected}", results)

    # ─── 5. ACHATS (purchased animals) ────────────────────────────────
    hdr("5. ACHAT cross-check")

    purchase_dates = frappe.db.sql_list("""
        SELECT DISTINCT date_entree FROM `tabAnimal`
        WHERE est_achat = 1 AND date_entree IS NOT NULL
        ORDER BY date_entree DESC LIMIT 20
    """)
    sample = random.sample(purchase_dates,
                            min(N_EXIT_SAMPLES, len(purchase_dates)))
    print(f"  Sampling {len(sample)} purchase dates")

    for d in sorted(sample):
        sub(f"Date: {d}")
        n_achats = frappe.db.count("Animal",
            {"est_achat": 1, "date_entree": d})
        rows = _run_effectif(d)
        a_actual = rows.get("Achat", {}).get("Total", 0)
        print(f"     Achats DB: {n_achats}  |  Report: {a_actual}")
        _check(a_actual == n_achats, f"Achat Total = {n_achats}", results)

    # ─── SUMMARY ──────────────────────────────────────────────────────
    print("\n" + "═" * 76)
    total = results["pass"] + results["fail"]
    print(f"  RÉSULTATS: {results['pass']}/{total} contrôles passés, "
          f"{results['fail']} échoués")
    print("═" * 76 + "\n")
    return results
