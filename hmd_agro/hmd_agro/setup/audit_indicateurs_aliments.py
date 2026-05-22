"""
Cross-check the Indicateurs (KPIs) + Alimentation tables against raw SLE
and Traite data. Validates:
  1. ISO week boundaries (Quotidien / Quinzaine / Hebdomadaire)
  2. Indicateurs cells (KPIs) per date — Production, Concentré, Frais, ratios
  3. Aliment table cells — per-lot daily snapshot, period averages, totals
  4. Saisie Alimentation correction propagation — round-trip
  5. Pre-backfill stance — 0 for dates without SLE data

Read-only EXCEPT section 4 which posts + cancels its own correction.
Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.audit_indicateurs_aliments.run
"""
import frappe
from frappe.utils import getdate, add_days

from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import (
    _indicateurs, _alimentation, _build_period_spans,
    _consumption_from_sle, _medicament_cost,
)


def hdr(t):
    print("\n" + "═" * 76 + "\n  " + t + "\n" + "═" * 76)


def sub(t):
    print(f"\n  ── {t} " + "─" * (70 - len(t)))


def _check(cond, msg, results):
    if cond:
        print(f"     ✓ {msg}")
        results["pass"] += 1
    else:
        print(f"     ✗ {msg}")
        results["fail"] += 1


def _close(a, b, tol=0.5):
    return abs(float(a or 0) - float(b or 0)) <= tol


def _ctx(date_str, granularite="Quotidien"):
    d = getdate(date_str)
    return {
        "date_debut": getdate(f"{d.year}-{d.month:02d}-01"),
        "date_filter": d,
        "date_fin": getdate(f"{d.year}-{d.month:02d}-"
                            + str(min(31, 31 if d.month in (1,3,5,7,8,10,12)
                                           else (30 if d.month != 2
                                                 else (29 if d.year % 4 == 0
                                                       else 28))))),
        "nb_jours": 31, "mois": d.month, "annee": d.year,
        "granularite": granularite,
    }


# ════════════════════════════════════════════════════════════════════
# 1. ISO WEEK BOUNDARIES
# ════════════════════════════════════════════════════════════════════
def audit_iso_weeks(results):
    hdr("1. ISO WEEK BOUNDARIES (Hebdomadaire mode)")

    # Spec: ISO weeks (Mon-Sun) intersecting the calendar month, clipped to
    # month boundaries. Labels reset to S1 every 1st of the month.
    cases = [
        # May 2026 — month starts on Friday (May 1 = Fri)
        {
            "month": "May 2026", "date_debut": "2026-05-01", "nb_jours": 31,
            "expected": [
                # (label, start, end, days)
                ("S1", "2026-05-01", "2026-05-03", 3),  # Fri-Sun (clipped)
                ("S2", "2026-05-04", "2026-05-10", 7),  # full week
                ("S3", "2026-05-11", "2026-05-17", 7),
                ("S4", "2026-05-18", "2026-05-24", 7),
                ("S5", "2026-05-25", "2026-05-31", 7),
            ],
        },
        # March 2026 — March 1 = Sunday
        {
            "month": "March 2026", "date_debut": "2026-03-01", "nb_jours": 31,
            "expected": [
                ("S1", "2026-03-01", "2026-03-01", 1),  # Sun only (clipped)
                ("S2", "2026-03-02", "2026-03-08", 7),
                ("S3", "2026-03-09", "2026-03-15", 7),
                ("S4", "2026-03-16", "2026-03-22", 7),
                ("S5", "2026-03-23", "2026-03-29", 7),
                ("S6", "2026-03-30", "2026-03-31", 2),  # Mon-Tue (clipped)
            ],
        },
        # February 2026 — Feb 1 = Sunday, 28 days (not leap)
        {
            "month": "Feb 2026", "date_debut": "2026-02-01", "nb_jours": 28,
            "expected": [
                ("S1", "2026-02-01", "2026-02-01", 1),
                ("S2", "2026-02-02", "2026-02-08", 7),
                ("S3", "2026-02-09", "2026-02-15", 7),
                ("S4", "2026-02-16", "2026-02-22", 7),
                ("S5", "2026-02-23", "2026-02-28", 6),
            ],
        },
    ]

    for case in cases:
        sub(case["month"])
        spans = _build_period_spans(
            "Hebdomadaire", getdate(case["date_debut"]), case["nb_jours"]
        )
        print(f"     Got {len(spans)} spans (expected {len(case['expected'])})")

        for actual, expected in zip(spans, case["expected"]):
            a_label, a_start, a_end = actual
            e_label, e_start, e_end, e_days = expected
            a_days = (a_end - a_start).days + 1
            ok = (a_label == e_label
                  and str(a_start) == e_start
                  and str(a_end) == e_end
                  and a_days == e_days)
            _check(ok, f"{a_label}: {a_start}→{a_end} ({a_days}d) — "
                   f"expected {e_label}: {e_start}→{e_end} ({e_days}d)",
                   results)
        _check(len(spans) == len(case["expected"]),
               f"Span count = {len(case['expected'])}", results)


# ════════════════════════════════════════════════════════════════════
# 2. INDICATEURS KPIs vs raw SQL
# ════════════════════════════════════════════════════════════════════
def audit_indicateurs(results):
    hdr("2. INDICATEURS — cross-check KPIs against raw SQL")

    cases = [
        {"date": "2026-05-15", "label": "Mid-May (in-backfill)"},
        {"date": "2026-04-30", "label": "End-April (in-backfill, full month)"},
    ]

    for case in cases:
        sub(case["label"] + f" ({case['date']})")
        ctx = _ctx(case["date"])
        _, rows = _indicateurs(ctx)
        kpi = {r["indicateur"].split(" (")[0].split(" — ")[0].strip(): r
               for r in rows}

        def get(label, key="valeur"):
            for k, r in kpi.items():
                if k.startswith(label):
                    return r.get(key)
            return None

        # Production Totale — raw sum of Traite
        prod_actual = get("Production Totale")
        prod_expected = float(frappe.db.sql("""
            SELECT COALESCE(SUM(quantite_litres), 0) FROM `tabTraite`
            WHERE date_traite BETWEEN %s AND %s
        """, (ctx["date_debut"], ctx["date_filter"]))[0][0])
        _check(_close(prod_actual, round(prod_expected, 1), tol=0.2),
               f"Production Totale = {prod_expected:.1f} (got {prod_actual})",
               results)

        # Concentré Total — raw sum from SLE
        sle = _consumption_from_sle(ctx["date_debut"], ctx["date_filter"])
        conc_actual = get("Concentré Total")
        _check(_close(conc_actual, round(sle["cumulative_concentre_cheptel"], 1)),
               f"Concentré Total = {sle['cumulative_concentre_cheptel']:.1f} kg",
               results)

        # Frais Concentré
        frais_conc_actual = get("Frais Concentré")
        _check(_close(frais_conc_actual, round(sle["cumulative_concentre_cost"], 2)),
               f"Frais Concentré = {sle['cumulative_concentre_cost']:.2f} DT",
               results)

        # Frais Fourrage
        frais_four_actual = get("Frais Fourrage")
        _check(_close(frais_four_actual, round(sle["cumulative_fourrage_cost"], 2)),
               f"Frais Fourrage = {sle['cumulative_fourrage_cost']:.2f} DT",
               results)

        # Frais Médicaments — separate primitive (different markers)
        frais_med_actual = get("Frais Médicaments")
        frais_med_expected = round(
            _medicament_cost(ctx["date_debut"], ctx["date_filter"]), 2)
        _check(_close(frais_med_actual, frais_med_expected),
               f"Frais Médicaments = {frais_med_expected} DT", results)

        # L/C ratio
        lc_actual = get("L/C")
        lc_expected = (round(prod_actual / conc_actual, 2)
                       if conc_actual else 0)
        _check(_close(lc_actual, lc_expected, tol=0.05),
               f"L/C = Prod/Conc = {prod_actual}/{conc_actual} = "
               f"{lc_expected}", results)

        # Coût Alim/L — total aliment cost ÷ Production
        cout_actual = get("Coût Alimentaire / L")
        cout_expected = (round(sle["cumulative_aliment_cost"] / prod_actual, 3)
                         if prod_actual else 0)
        _check(_close(cout_actual, cout_expected, tol=0.01),
               f"Coût Alim/L = {sle['cumulative_aliment_cost']:.2f}/"
               f"{prod_actual} = {cout_expected}", results)


# ════════════════════════════════════════════════════════════════════
# 3. ALIMENT TABLE CELLS
# ════════════════════════════════════════════════════════════════════
def audit_aliment_cells(results):
    hdr("3. ALIMENT TABLE — cell coverage + Hebdo Sx + totals")

    test_date = "2026-05-15"
    sub(f"Hebdomadaire mode @ {test_date}")
    ctx = _ctx(test_date, granularite="Hebdomadaire")
    cols, rows = _alimentation(ctx)
    col_fields = [c["fieldname"] for c in cols]
    print(f"     Columns: {col_fields}")

    # Ensure expected columns
    for col in ("aliment", "ms_pct", "moy_s1", "moy_s2", "moy_s3",
                "moy_jour_mois", "cout_periode"):
        _check(col in col_fields, f"Column '{col}' present", results)

    # Identify rows
    per_aliment = [r for r in rows if not r.get("is_total")]
    total_rows = [r for r in rows if r.get("is_total")]
    print(f"     Per-aliment rows: {len(per_aliment)}")
    print(f"     Total rows: {len(total_rows)} ({[r.get('aliment') for r in total_rows]})")

    # Expected 4 total rows after Coût Total Distribué addition
    _check(len(total_rows) == 4,
           f"Expected 4 total rows (MS Total + MS/Tête + Efficacité + "
           f"Coût Total), got {len(total_rows)}", results)

    # Per-aliment rows: ms_pct + cout_periode + Moy/jour Sx should be non-null
    for r in per_aliment:
        ali = r["aliment"]
        empty_critical = [k for k in ("ms_pct", "moy_jour_mois")
                          if r.get(k) is None]
        _check(not empty_critical,
               f"Aliment '{ali}': critical cells filled "
               f"(missing: {empty_critical})", results)

    # Coût Total row = sum of per-aliment Coût période
    total_row = next((r for r in total_rows
                      if r["aliment"] == "Coût Total Distribué (DT)"), None)
    if total_row:
        per_aliment_sum = sum(float(r.get("cout_periode") or 0)
                              for r in per_aliment)
        total_value = float(total_row.get("cout_periode") or 0)
        _check(_close(total_value, per_aliment_sum),
               f"Σ per-aliment Coût période ({per_aliment_sum:.2f}) = "
               f"Coût Total row ({total_value:.2f})", results)

        # Cross-mode: same total in Quotidien and Quinzaine
        for gran in ("Quotidien", "Quinzaine"):
            ctx2 = _ctx(test_date, granularite=gran)
            _, rows2 = _alimentation(ctx2)
            other_total = next(
                (float(r.get("cout_periode") or 0) for r in rows2
                 if r.get("aliment") == "Coût Total Distribué (DT)"), 0,
            )
            _check(_close(other_total, total_value),
                   f"{gran} total ({other_total:.2f}) = Hebdo total "
                   f"({total_value:.2f}) — granularity invariant",
                   results)

    # Hebdo Sx: each period sum from SLE should equal Σ per-aliment moy_sX × days
    sub("Hebdomadaire Sx values vs raw SLE")
    spans = _build_period_spans(
        "Hebdomadaire", ctx["date_debut"], ctx["nb_jours"]
    )
    cursor = getdate(test_date)
    for label, start, end in spans:
        # The report walks only up to the cursor in current-month mode, so
        # the effective period is [start, min(end, cursor)]. Query the same
        # window so the SLE comparison is apples-to-apples.
        walk_end = min(end, cursor)
        if walk_end < start:
            continue  # future-only period — nothing walked
        period_data = _consumption_from_sle(start, walk_end)
        sle_kg = sum(period_data["cumulative_qty"].values())

        days = (walk_end - start).days + 1
        report_sum = sum(
            (r.get(f"moy_{label.lower()}") or 0) * days
            for r in per_aliment
        )
        # Compare totals (allow 1 kg drift from rounding)
        _check(_close(report_sum, sle_kg, tol=1.0),
               f"{label} ({start}→{end}, {days}d): "
               f"Σ moy×days = {report_sum:.1f} kg vs SLE = {sle_kg:.1f} kg",
               results)


# ════════════════════════════════════════════════════════════════════
# 4. SAISIE CORRECTION PROPAGATION
# ════════════════════════════════════════════════════════════════════
def audit_saisie_propagation(results):
    hdr("4. SAISIE ALIMENTATION — correction round-trip into the tables")

    from hmd_agro.hmd_agro.utils.feed_correction import (
        get_aliment_state, post_aliment_corrections_batch,
        cancel_aliment_correction,
    )

    test_date = "2026-05-14"
    state = get_aliment_state(test_date)
    target = next(
        (a for a in state["aliments"] if a["theoretical_total"] >= 30), None,
    )
    if not target:
        print("     [skip] no aliment with >= 30 kg theoretical")
        return

    item_code = target["item_code"]
    theo = target["theoretical_total"]
    print(f"     Target aliment: {target['aliment']} ({item_code}), "
          f"theoretical = {theo} kg")

    # Baseline
    cancel_aliment_correction(test_date, item_code)
    ctx = _ctx(test_date)
    _, rows = _alimentation(ctx)
    base_total = next((float(r.get("cout_periode") or 0)
                        for r in rows
                        if r.get("aliment") == "Coût Total Distribué (DT)"), 0)
    _, ind_rows = _indicateurs(ctx)
    base_frais_conc = next(
        (r["valeur"] for r in ind_rows
         if r["indicateur"].startswith("Frais Concentré")), 0,
    )
    print(f"     Baseline Coût Total: {base_total:.2f} DT")
    print(f"     Baseline Frais Concentré: {base_frais_conc:.2f} DT")

    # +20 kg correction (proportionally split across all lots using this aliment)
    sub("+20 kg correction")
    r = post_aliment_corrections_batch(test_date, [
        {"item_code": item_code, "actual_total": theo + 20.0},
    ])
    _check(r["posted"] > 0 and not r["errors"],
           f"+20kg posted ({r['posted']} per-lot SE(s))", results)

    _, rows_after = _alimentation(ctx)
    after_total = next((float(r.get("cout_periode") or 0)
                        for r in rows_after
                        if r.get("aliment") == "Coût Total Distribué (DT)"), 0)
    _, ind_after = _indicateurs(ctx)
    after_frais_conc = next(
        (r["valeur"] for r in ind_after
         if r["indicateur"].startswith("Frais Concentré")), 0,
    )
    delta_total = after_total - base_total
    delta_conc = after_frais_conc - base_frais_conc
    print(f"     After: Coût Total = {after_total:.2f} (Δ +{delta_total:.2f})")
    print(f"     After: Frais Concentré = {after_frais_conc:.2f} (Δ +{delta_conc:.2f})")
    _check(delta_total > 0.5,
           f"Coût Total increased after +20kg (Δ +{delta_total:.2f})", results)
    _check(delta_conc >= 0,
           f"Frais Concentré didn't decrease (Δ +{delta_conc:.2f})", results)

    # Cancel
    cancel_aliment_correction(test_date, item_code)
    _, rows_restored = _alimentation(ctx)
    restored_total = next((float(r.get("cout_periode") or 0)
                            for r in rows_restored
                            if r.get("aliment") == "Coût Total Distribué (DT)"), 0)
    _check(_close(restored_total, base_total),
           f"After cancel: Coût Total restored to baseline "
           f"({restored_total:.2f} ≈ {base_total:.2f})", results)


# ════════════════════════════════════════════════════════════════════
# 5. PRE-BACKFILL STANCE
# ════════════════════════════════════════════════════════════════════
def audit_pre_backfill(results):
    hdr("5. PRE-BACKFILL STANCE — dates before SLE data exist")

    test_date = "2026-01-15"
    sub(f"Date: {test_date} (before backfill window 2026-04-16)")
    ctx = _ctx(test_date)
    _, rows = _alimentation(ctx)
    _, ind_rows = _indicateurs(ctx)

    # Aliment table: per-aliment rows should all have Coût période = None
    per_ali = [r for r in rows if not r.get("is_total")]
    n_with_cost = sum(1 for r in per_ali if r.get("cout_periode"))
    _check(n_with_cost == 0,
           f"Pre-backfill: 0 per-aliment rows have cost "
           f"(got {n_with_cost} with cost)", results)

    # Coût Total row should be None (no SLE → 0 → set to None by the report)
    total_row = next((r for r in rows
                      if r.get("aliment") == "Coût Total Distribué (DT)"), {})
    _check(total_row.get("cout_periode") in (None, 0),
           f"Pre-backfill: Coût Total = None/0 "
           f"(got {total_row.get('cout_periode')})", results)

    # Indicateurs: cost KPIs should be 0 (or None where appropriate)
    for label in ("Frais Concentré", "Frais Fourrage", "Coût Alimentaire / L"):
        kpi = next((r for r in ind_rows
                    if r["indicateur"].startswith(label)), {})
        val = kpi.get("valeur")
        _check(val in (0, 0.0, None),
               f"Pre-backfill: {label} = 0/None (got {val})", results)


def run():
    results = {"pass": 0, "fail": 0}
    audit_iso_weeks(results)
    audit_indicateurs(results)
    audit_aliment_cells(results)
    audit_saisie_propagation(results)
    audit_pre_backfill(results)

    print("\n" + "═" * 76)
    total = results["pass"] + results["fail"]
    print(f"  RÉSULTATS: {results['pass']}/{total} contrôles passés, "
          f"{results['fail']} échoués")
    print("═" * 76 + "\n")
    return results
