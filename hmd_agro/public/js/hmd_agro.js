// HMD Agro global JS

/**
 * Make the first N columns of a query report's datatable sticky (frozen)
 * during horizontal scroll. The cells stay opaque on top of the zebra-striped
 * background defined in hmd_agro.css.
 *
 * Usage from a report's after_datatable_render(datatable):
 *     hmd_make_sticky_columns(datatable, 1);   // freeze nom_metier
 *     hmd_make_sticky_columns(datatable, 2);   // freeze nom_metier + lot
 *
 * Idempotent — won't re-inject style if already present in this datatable.
 */
window.hmd_make_sticky_columns = function (datatable, num_cols) {
    if (!datatable || !datatable.wrapper) return;
    if (datatable.wrapper.querySelector(".hmd-sticky-style")) return;

    let css = "";
    let left = 0;
    for (let i = 0; i < num_cols; i++) {
        const col = datatable.getColumn(i);
        const w = (col && col.width) || 90;
        css += `
            .dt-cell--col-${i}, .dt-cell--header-${i} {
                position: sticky !important; left: ${left}px; z-index: 10;
                background: var(--card-bg) !important;
            }
            .dt-cell--header-${i} { z-index: 11; }
            .dt-row:nth-child(even) .dt-cell--col-${i} {
                background: linear-gradient(rgba(127,127,127,0.15), rgba(127,127,127,0.15)),
                            var(--card-bg) !important;
            }
        `;
        left += w;
    }
    const style = document.createElement("style");
    style.className = "hmd-sticky-style";
    style.textContent = css;
    datatable.wrapper.appendChild(style);
};


/**
 * Shrink the datatable to fit its content's natural width and center it on
 * the page. Useful for small print-out reports (3-4 columns) so the scrollbar
 * and visual gap don't sit awkwardly far from the data.
 *
 * Call from after_datatable_render(datatable):
 *     hmd_fit_table_to_content(datatable);
 */
window.hmd_fit_table_to_content = function (datatable) {
    if (!datatable || !datatable.wrapper) return;
    const cols = (datatable.columnmanager && datatable.columnmanager.columns) || [];
    let total = 0;
    cols.forEach((c) => { total += (c && c.width) || 0; });
    if (!total) return;
    total += 20; // small padding for borders / row-number column

    const dt = datatable.wrapper.querySelector(".datatable");
    if (!dt) return;
    dt.style.maxWidth = total + "px";
    dt.style.marginLeft = "auto";
    dt.style.marginRight = "auto";
};
