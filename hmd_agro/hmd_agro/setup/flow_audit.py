"""
Comprehensive flow audit — exercises every affected surface after the
SLE unification (R1+R2+R3) and ST5-15 Saisie Alimentation:

  1. Aliment table flow (Rapport Mensuel)
  2. Indicateurs (KPIs) flow
  3. Bilan Annuel (Rapport Reproduction) flow
  4. Saisie Alimentation correction → report propagation
  5. Cross-mode consistency (Quotidien vs Quinzaine vs Hebdomadaire)

For each section it both EXPLAINS the data path and VERIFIES the numbers
against raw SLE/Bin/Animal queries so any drift surfaces immediately.

Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.flow_audit.run
"""
import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import (
    _consumption_from_sle, _aliment_data_per_lot, _alimentation, _indicateurs,
    _medicament_cost,
)


# Picked deterministically inside the backfill window (2026-04-16 → present)
TEST_DATE = "2026-05-14"
TEST_MONTH_START = "2026-05-01"
TEST_MONTH_END = "2026-05-15"  # cursor inside May


def hdr(title):
    print("\n" + "═" * 76)
    print(f"  {title}")
    print("═" * 76)


def sub(title):
    print(f"\n  ── {title} " + "─" * (70 - len(title)))


def ok(msg):
    print(f"    ✓ {msg}")


def fail(msg):
    print(f"    ✗ {msg}")


def info(msg):
    print(f"    · {msg}")


def run():
    results = {"pass": 0, "fail": 0}

    # ════════════════════════════════════════════════════════════════════
    # 1. ALIMENT TABLE (Rapport Mensuel → section Alimentation)
    # ════════════════════════════════════════════════════════════════════
    hdr("1. ALIMENT TABLE — flow & accuracy")

    info(f"Date cursor: {TEST_DATE}    Date range: {TEST_MONTH_START} → {TEST_MONTH_END}")

    sub("Step A: raw SLE source")
    raw = frappe.db.sql("""
        SELECT a.name AS aliment, a.type_aliment,
               SUM(-sle.actual_qty) AS kg,
               SUM(-sle.stock_value_difference) AS dt
        FROM `tabStock Ledger Entry` sle
        JOIN `tabStock Entry` se ON se.name = sle.voucher_no
             AND sle.voucher_type = 'Stock Entry'
        JOIN `tabAliment` a ON a.item = sle.item_code
        WHERE sle.is_cancelled = 0
          AND sle.posting_date BETWEEN %s AND %s
          AND sle.item_code LIKE 'ALI-%%'
          AND (se.remarks LIKE 'RATION_DIST_%%'
               OR se.remarks LIKE 'RATION_CORRECTION_%%')
          AND se.id_lot IS NOT NULL
        GROUP BY a.name
        ORDER BY a.name
    """, (TEST_MONTH_START, TEST_MONTH_END), as_dict=True)
    for r in raw:
        info(f"    {r.aliment:25s} [{r.type_aliment:10s}] "
             f"{float(r.kg):>9.1f} kg   {float(r.dt):>9.2f} DT")

    sub("Step B: _consumption_from_sle aggregates the same data")
    sle_data = _consumption_from_sle(TEST_MONTH_START, TEST_MONTH_END)
    for ali, kg in sorted(sle_data["cumulative_qty"].items()):
        dt = sle_data["cumulative_cost_per_aliment"].get(ali, 0)
        info(f"    {ali:25s}                 {kg:>9.1f} kg   {dt:>9.2f} DT")

    sub("Step C: cross-check raw SQL vs primitive")
    raw_by_ali = {r.aliment: (float(r.kg), float(r.dt)) for r in raw}
    drift = 0
    for ali in set(raw_by_ali) | set(sle_data["cumulative_qty"]):
        raw_kg, raw_dt = raw_by_ali.get(ali, (0, 0))
        prim_kg = sle_data["cumulative_qty"].get(ali, 0)
        prim_dt = sle_data["cumulative_cost_per_aliment"].get(ali, 0)
        if abs(raw_kg - prim_kg) > 0.01 or abs(raw_dt - prim_dt) > 0.01:
            fail(f"DRIFT on {ali}: raw=({raw_kg}, {raw_dt}) "
                 f"primitive=({prim_kg}, {prim_dt})")
            drift += 1
    if drift == 0:
        ok(f"Primitive matches raw SQL exactly on {len(raw)} aliment(s)")
        results["pass"] += 1
    else:
        results["fail"] += 1

    sub("Step D: Alimentation report consumes the primitive")
    ctx = {"date_debut": getdate(TEST_MONTH_START),
           "date_filter": getdate(TEST_DATE),
           "date_fin": getdate(TEST_MONTH_END),
           "nb_jours": 31, "mois": 5, "annee": 2026,
           "granularite": "Quotidien"}
    cols, rows = _alimentation(ctx)
    cost_total_row = next(
        (r for r in rows if r.get("aliment") == "Coût Total Distribué (DT)"), None)
    per_aliment_cost_sum = sum(float(r.get("cout_periode") or 0)
                                for r in rows if not r.get("is_total"))
    info(f"    Rows: {len(rows)} ({sum(1 for r in rows if not r.get('is_total'))} aliments + "
         f"{sum(1 for r in rows if r.get('is_total'))} totals)")
    info(f"    Σ per-aliment Coût période: {per_aliment_cost_sum:.2f} DT")
    info(f"    'Coût Total Distribué' row : {cost_total_row['cout_periode'] if cost_total_row else None} DT")

    if cost_total_row and abs(float(cost_total_row.get("cout_periode") or 0) - per_aliment_cost_sum) < 0.5:
        ok("Coût Total Distribué row == Σ per-aliment cells (within rounding)")
        results["pass"] += 1
    else:
        fail("Total row mismatches per-aliment sum")
        results["fail"] += 1


    # ════════════════════════════════════════════════════════════════════
    # 2. INDICATEURS — KPI dashboard
    # ════════════════════════════════════════════════════════════════════
    hdr("2. INDICATEURS (KPIs) — flow & accuracy")

    cols, ind_rows = _indicateurs(ctx)
    def get_kpi(label):
        for r in ind_rows:
            if r["indicateur"].startswith(label):
                return r
        return {}

    prod = get_kpi("Production Totale").get("valeur") or 0
    conc_kg = get_kpi("Concentré Total").get("valeur") or 0
    frais_conc = get_kpi("Frais Concentré").get("valeur") or 0
    frais_four = get_kpi("Frais Fourrage").get("valeur") or 0
    frais_med = get_kpi("Frais Médicaments").get("valeur") or 0
    cout_l = get_kpi("Coût Alimentaire / L").get("valeur") or 0
    lc = get_kpi("L/C").get("valeur") or 0
    eff_alim = get_kpi("Efficacité Alimentaire").get("valeur") or 0

    sub("KPIs published by _indicateurs for cursor 2026-05-15")
    info(f"    Production Totale       = {prod}    L")
    info(f"    Concentré Total         = {conc_kg}    kg")
    info(f"    L/C                     = {lc}    L/kg")
    info(f"    Efficacité Alimentaire  = {eff_alim}    L/kg MS")
    info(f"    Frais Concentré         = {frais_conc}    DT")
    info(f"    Frais Fourrage          = {frais_four}    DT")
    info(f"    Frais Médicaments       = {frais_med}    DT")
    info(f"    Coût Alimentaire / L    = {cout_l}    DT/L")

    sub("Verifying derived ratios against their inputs")

    # L/C = Production / Concentré
    if conc_kg:
        expected_lc = round(prod / conc_kg, 2)
        if abs(lc - expected_lc) < 0.02:
            ok(f"L/C = {lc} matches Prod/Conc = {prod}/{conc_kg} = {expected_lc}")
            results["pass"] += 1
        else:
            fail(f"L/C drift: got {lc}, expected {expected_lc}")
            results["fail"] += 1

    # Frais Médicaments cross-check: re-call the helper directly
    frais_med_direct = _medicament_cost(TEST_MONTH_START, TEST_MONTH_END)
    if abs(frais_med - round(frais_med_direct, 2)) < 0.02:
        ok(f"Frais Médicaments KPI matches _medicament_cost direct call "
           f"({frais_med} == {round(frais_med_direct, 2)})")
        results["pass"] += 1
    else:
        fail(f"Frais Médicaments drift: KPI={frais_med}, direct={frais_med_direct}")
        results["fail"] += 1

    # Coût Alim / L = total aliment cost / Production for the KPI's own window
    # ([date_debut, date_filter] = May 1 → cursor 2026-05-14).
    # Earlier sle_data covered May 1 → May 15 (different end). Re-fetch on
    # the KPI's exact window so the comparison is apples-to-apples.
    sle_kpi_range = _consumption_from_sle(TEST_MONTH_START, TEST_DATE)
    total_aliment_cost = sle_kpi_range["cumulative_aliment_cost"]
    implied_cout_l = round(total_aliment_cost / prod, 3) if prod else 0
    if abs(cout_l - implied_cout_l) < 0.005:
        ok(f"Coût Alim/L = {cout_l} matches total_aliment_cost/Prod "
           f"= {total_aliment_cost:.2f}/{prod} = {implied_cout_l}")
        results["pass"] += 1
    else:
        fail(f"Coût Alim/L drift: KPI={cout_l}, implied={implied_cout_l}")
        results["fail"] += 1


    # ════════════════════════════════════════════════════════════════════
    # 3. RAPPORT REPRODUCTION → BILAN ANNUEL
    # ════════════════════════════════════════════════════════════════════
    hdr("3. RAPPORT REPRODUCTION / BILAN ANNUEL — flow")

    from hmd_agro.hmd_agro.report.rapport_reproduction.rapport_reproduction import (
        _bilan_year_row,
    )
    from hmd_agro.hmd_agro.utils.live_state import effectif_on_date

    sub("2026 partial year row")
    row_2026 = _bilan_year_row(
        2026, getdate("2026-01-01"), getdate("2026-05-15"),
        is_partial=True, effectif_fn=effectif_on_date,
        aliment_fn=_aliment_data_per_lot,
    )
    info(f"    Production Totale  = {row_2026.get('production_totale')}")
    info(f"    Concentré annuel   = {row_2026.get('concentre_total')} kg")
    info(f"    L/C annuel         = {row_2026.get('lc')}")
    info(f"    nb_velages         = {row_2026.get('nb_velages')}")
    info(f"    nb_ia              = {row_2026.get('nb_ia')}")
    info(f"    Note: 2026 row covers Jan-Apr (no SLE → 0 contribution)")
    info(f"          + Apr 16-end + May 1-15 (in backfill → real SLE data)")
    info(f"          So Concentré reflects backfilled days only — production")
    info(f"          stance: honest 0 for pre-backfill, real for what we have.")

    # Cross-check: the backfilled portion should equal what _aliment_data_per_lot
    # reports for that exact range
    bf_d = _aliment_data_per_lot(getdate("2026-04-16"), getdate("2026-05-15"))
    expected_bf_conc = round(bf_d["cumulative_concentre_cheptel"], 1) if bf_d else 0
    info(f"    Cross-check: Apr 16 → May 15 concentré = {expected_bf_conc} kg")
    bilan_conc = row_2026.get('concentre_total') or 0
    if abs(bilan_conc - expected_bf_conc) < 1:
        ok(f"Bilan Annuel 2026 concentré matches backfilled SLE window")
        results["pass"] += 1
    else:
        fail(f"Bilan Annuel drift: bilan={bilan_conc}, expected={expected_bf_conc}")
        results["fail"] += 1


    # ════════════════════════════════════════════════════════════════════
    # 4. CROSS-MODE CONSISTENCY (Quotidien / Quinzaine / Hebdomadaire)
    # ════════════════════════════════════════════════════════════════════
    hdr("4. CROSS-MODE TOTALS — must be IDENTICAL across granularités")

    modes = {}
    for gran in ("Quotidien", "Quinzaine", "Hebdomadaire"):
        ctx2 = {**ctx, "granularite": gran}
        _, rows = _alimentation(ctx2)
        cost_total = next(
            (float(r.get("cout_periode") or 0)
             for r in rows if r.get("aliment") == "Coût Total Distribué (DT)"),
            0,
        )
        modes[gran] = cost_total
        info(f"    {gran:13s} Coût Total Distribué = {cost_total} DT")

    if abs(modes["Quotidien"] - modes["Quinzaine"]) < 0.5 and \
       abs(modes["Quotidien"] - modes["Hebdomadaire"]) < 0.5:
        ok("All three modes report identical total — granularité is purely "
           "presentational, totals are invariant")
        results["pass"] += 1
    else:
        fail(f"Cross-mode drift: {modes}")
        results["fail"] += 1


    # ════════════════════════════════════════════════════════════════════
    # 5. SAISIE ALIMENTATION → REPORT PROPAGATION
    # ════════════════════════════════════════════════════════════════════
    hdr("5. SAISIE ALIMENTATION — correction propagates to reports")

    from hmd_agro.hmd_agro.utils.feed_correction import (
        get_saisie_state, post_correction, cancel_correction,
    )

    sub("Initial state (no correction)")
    state = get_saisie_state(TEST_DATE)
    target_lot = None
    for L in state["lots"]:
        if L["theoretical_total"] >= 10:
            target_lot = L
            break
    if not target_lot:
        info("    No lot with >= 10 kg theoretical; skipping round-trip")
    else:
        info(f"    Target lot: {target_lot['lot']}    theoretical = "
             f"{target_lot['theoretical_total']} kg")

        # Snapshot report cost BEFORE correction
        d0 = _consumption_from_sle(TEST_DATE, TEST_DATE)
        cost_before = d0["cumulative_aliment_cost"]
        info(f"    Day cost before correction: {cost_before:.2f} DT")

        sub("Post +5 kg correction")
        r = post_correction(TEST_DATE, target_lot["lot"],
                            target_lot["theoretical_total"] + 5.0)
        info(f"    Status: {r['status']}, correction_se: {r['correction_se']}")
        d1 = _consumption_from_sle(TEST_DATE, TEST_DATE)
        cost_after = d1["cumulative_aliment_cost"]
        delta_cost = cost_after - cost_before
        info(f"    Day cost after  correction: {cost_after:.2f} DT  "
             f"(Δ = +{delta_cost:.2f})")
        if delta_cost > 0.5:
            ok("Report cost increased after +5kg correction (Material Issue)")
            results["pass"] += 1
        else:
            fail(f"Cost did NOT propagate: Δ={delta_cost:.2f}")
            results["fail"] += 1

        sub("Cancel correction → back to theoretical")
        cancel_correction(TEST_DATE, target_lot["lot"])
        d2 = _consumption_from_sle(TEST_DATE, TEST_DATE)
        cost_restored = d2["cumulative_aliment_cost"]
        info(f"    Day cost after cancel : {cost_restored:.2f} DT")
        if abs(cost_restored - cost_before) < 0.1:
            ok("Cost restored to baseline after cancel_correction")
            results["pass"] += 1
        else:
            fail(f"Restore drift: before={cost_before}, after={cost_restored}")
            results["fail"] += 1

        sub("Post -3 kg correction (Material Receipt direction)")
        r = post_correction(TEST_DATE, target_lot["lot"],
                            target_lot["theoretical_total"] - 3.0)
        d3 = _consumption_from_sle(TEST_DATE, TEST_DATE)
        cost_reduced = d3["cumulative_aliment_cost"]
        info(f"    Status: {r['status']}, correction_se: {r['correction_se']}")
        info(f"    Day cost after -3kg correction: {cost_reduced:.2f} DT  "
             f"(Δ = {cost_reduced - cost_before:+.2f})")
        if cost_reduced < cost_before - 0.1:
            ok("Report cost DECREASED after -3kg correction "
               "(Material Receipt nets in)")
            results["pass"] += 1
        else:
            fail(f"Negative correction did NOT propagate: cost_before="
                 f"{cost_before}, cost_after={cost_reduced}")
            results["fail"] += 1

        # Clean up — leave the day exactly as we found it
        cancel_correction(TEST_DATE, target_lot["lot"])

    # ════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 76)
    total = results["pass"] + results["fail"]
    print(f"  RÉSULTATS: {results['pass']}/{total} contrôles passés, "
          f"{results['fail']} échoués")
    print("═" * 76 + "\n")
    return results
