// Client-side coloring for the Efficacité alimentaire KPI cell.
//
// This is the relevant fragment of
//   hmd_agro/hmd_agro/report/rapport_mensuel/rapport_mensuel.js
// It already lives in the app and applies to EVERY Indicateurs row that carries
// an `indicator` field (Green/Orange/Red) — including Efficacité alimentaire.
// Reproduced here to show how the Python `indicator` string becomes a color.
//
// Flow: _indicateurs (Python) sets row.indicator = "Green" | "Orange" | "Red"
//   via _kpi_ind(...). The query-report `formatter` below reads it and wraps
//   the `valeur` cell in a colored <span>. The Δ cell is colored separately by
//   `direction` ("up" = higher-better, so a positive Δ is green).

formatter(value, row, column, data, default_formatter) {
    if (value == null || value === "") {
        return default_formatter(value, row, column, data);
    }
    let html = default_formatter(value, row, column, data);
    if (data && (data.is_total || data.is_header)) {
        html = `<b>${html}</b>`;
    }

    // ── Color the KPI value cell (green / orange / red) ──────────────────
    // data.indicator is the PFE verdict computed server-side against the
    // farm's HMD Configuration thresholds (pfe_efficacite_min /
    // pfe_efficacite_orange_min for Efficacité alimentaire).
    if (column.fieldname === "valeur" && data && data.indicator) {
        const colors = { Green: "green", Orange: "orange", Red: "red" };
        const c = colors[data.indicator];
        if (c) {
            const w = data.indicator === "Red" ? "font-weight:bold;" : "font-weight:600;";
            html = `<span style="color:${c};${w}">${html}</span>`;
        }
    }

    // ── Color the Δ (M-1) cell by trend direction ───────────────────────
    // Efficacité is direction:"up" (higher better) -> improvement is green.
    if (column.fieldname === "delta_pct" && data && data.direction && data.delta_pct) {
        const improving = (data.direction === "up" && data.delta_pct > 0) ||
                          (data.direction === "down" && data.delta_pct < 0);
        const c = improving ? "green" : "red";
        html = `<span style="color:${c};font-weight:600;">${html}</span>`;
    }

    return html;
}
