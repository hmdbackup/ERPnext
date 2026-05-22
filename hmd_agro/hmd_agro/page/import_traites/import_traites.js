frappe.pages["import-traites"].on_page_load = function (wrapper) {
    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Import Traites",
        single_column: true,
    });

    page.main.html(`
        <div class="import-traites-container" style="max-width:900px; margin:0 auto; padding:20px;">
            <div class="upload-section" style="border:1px solid var(--border-color); border-radius:8px; padding:20px; background:var(--card-bg);">
                <h5>1. Charger le fichier Excel</h5>
                <p style="color:var(--text-muted); font-size:13px;">
                    Format attendu: Ligne 1 = dates (colonnes B+), Colonne A = nom metier, cellules = production journaliere (litres)
                </p>
                <div class="file-upload-area"></div>
                <div style="margin-top:15px;">
                    <button class="btn btn-primary btn-preview">Analyser le fichier</button>
                </div>
            </div>

            <div class="preview-section" style="display:none; margin-top:20px;">
                <div class="preview-content"></div>
                <div style="margin-top:15px; display:flex; align-items:center; gap:15px;">
                    <button class="btn btn-primary btn-sm btn-import">Lancer l'import</button>
                    <label style="font-size:13px; cursor:pointer; margin:0;">
                        <input type="checkbox" class="chk-keep-original" checked style="margin-right:5px;">
                        Garder les traites existantes
                    </label>
                </div>
            </div>

            <div class="results-section" style="display:none; margin-top:20px;">
                <div class="results-content"></div>
            </div>
        </div>
    `);

    // File upload control
    let file_control = frappe.ui.form.make_control({
        parent: page.main.find(".file-upload-area"),
        df: {
            fieldtype: "Attach",
            fieldname: "import_file",
            label: "Fichier Excel",
            options: { restrictions: { allowed_file_types: [".xlsx", ".xls"] } }
        },
        render_input: true,
    });

    page.file_control = file_control;

    // Preview button
    page.main.find(".btn-preview").on("click", function () {
        let file_url = file_control.get_value();
        if (!file_url) {
            frappe.msgprint("Veuillez charger un fichier Excel.");
            return;
        }

        frappe.call({
            method: "hmd_agro.hmd_agro.page.import_traites.import_traites.preview_import",
            args: { file_url: file_url },
            freeze: true,
            freeze_message: "Analyse du fichier...",
            callback: function (r) {
                if (r.message) {
                    render_preview(page, r.message);
                }
            },
        });
    });

    // Import button
    page.main.find(".btn-import").on("click", function () {
        let file_url = file_control.get_value();
        if (!file_url) {
            frappe.msgprint("Veuillez charger un fichier Excel.");
            return;
        }

        // Collect duplicate-resolution selections
        let resolutions = {};
        page.main.find(".duplicate-resolution-select").each(function () {
            let nom = $(this).data("nom");
            let val = $(this).val();
            if (val) {
                resolutions[nom] = val;
            }
        });

        let keep_original = page.main.find(".chk-keep-original").is(":checked");
        let confirm_msg = "Lancer l'import ? Cette operation va creer les traites pour tous les animaux trouves.";
        if (!keep_original) {
            confirm_msg = "<strong>Attention :</strong> Les traites existantes seront ecrasees par les valeurs du fichier Excel.<br><br>Voulez-vous continuer ?";
        }

        frappe.confirm(
            confirm_msg,
            function () {
                // Show progress section
                let $results = page.main.find(".results-section");
                $results.show();
                $results.find(".results-content").html(`
                    <div style="border:1px solid var(--border-color); border-radius:8px; padding:20px; background:var(--card-bg);">
                        <h5>Import en cours...</h5>
                        <div class="progress" style="margin-top:15px;">
                            <div class="progress-bar progress-bar-striped progress-bar-animated"
                                 role="progressbar" style="width:0%">0%</div>
                        </div>
                        <div class="import-status" style="margin-top:10px; font-size:13px; color:var(--text-muted);"></div>
                    </div>
                `);

                // Disable import button
                page.main.find(".btn-import").prop("disabled", true);

                // Listen for progress
                frappe.realtime.on("import_traites_progress", function (data) {
                    let pct = Math.round((data.current / data.total) * 100);
                    $results.find(".progress-bar").css("width", pct + "%").text(pct + "%");
                    $results.find(".import-status").text(
                        data.current + " / " + data.total + " cellules traitees"
                    );
                });

                // Listen for completion
                frappe.realtime.on("import_traites_complete", function (data) {
                    frappe.realtime.off("import_traites_progress");
                    frappe.realtime.off("import_traites_complete");
                    page.main.find(".btn-import").prop("disabled", false);

                    if (data.success) {
                        render_results(page, data.summary);
                    } else {
                        $results.find(".results-content").html(`
                            <div style="border:1px solid var(--border-color); border-radius:8px; padding:20px; background:var(--alert-bg-danger);">
                                <h5>Erreur</h5>
                                <p>${data.error || "Une erreur est survenue."}</p>
                            </div>
                        `);
                    }
                });

                // Start import
                frappe.call({
                    method: "hmd_agro.hmd_agro.page.import_traites.import_traites.run_import",
                    args: {
                        file_url: file_url,
                        keep_original: keep_original ? 1 : 0,
                        resolutions: JSON.stringify(resolutions)
                    },
                });
            }
        );
    });
};

function render_preview(page, data) {
    let $section = page.main.find(".preview-section");
    $section.show();

    let html = `
    <div style="border:1px solid var(--border-color); border-radius:8px; padding:20px; background:var(--card-bg);">
        <h5>2. Analyse du fichier</h5>

        <div style="display:flex; gap:20px; flex-wrap:wrap; margin-bottom:15px;">
            <div style="flex:1; min-width:150px; padding:10px; border:1px solid var(--border-color); border-radius:6px;">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Periode</div>
                <div style="font-size:16px; font-weight:600;">${data.date_range.start} → ${data.date_range.end}</div>
                <div style="font-size:12px; color:var(--text-muted);">${data.date_range.days} jours</div>
            </div>
            <div style="flex:1; min-width:150px; padding:10px; border:1px solid var(--border-color); border-radius:6px;">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Animaux dans le fichier</div>
                <div style="font-size:16px; font-weight:600;">${data.total_animals_excel}</div>
                <div style="font-size:12px; color:var(--text-muted);">${data.matched} trouves, ${data.unmatched.length} non trouves</div>
            </div>
            <div style="flex:1; min-width:150px; padding:10px; border:1px solid var(--border-color); border-radius:6px;">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Traites estimees</div>
                <div style="font-size:16px; font-weight:600;">${data.estimated_traites}</div>
                <div style="font-size:12px; color:var(--text-muted);">${data.matched} animaux x ${data.date_range.days} jours x 2 sessions</div>
            </div>
        </div>`;

    // Unmatched animals warning
    if (data.unmatched.length > 0) {
        html += `
        <div style="background:var(--alert-bg-warning); border:1px solid var(--alert-text-warning); border-radius:6px; padding:10px; margin-bottom:15px;">
            <strong>Animaux non trouves (${data.unmatched.length}):</strong>
            ${data.unmatched.join(", ")}
        </div>`;
    }

    if (data.duplicates.length > 0) {
        html += `
        <div style="background:var(--alert-bg-warning); border:1px solid var(--alert-text-warning); border-radius:6px; padding:12px; margin-bottom:15px;">
            <strong>N° Travail ambigu (${data.duplicates.length}) — plusieurs animaux partagent ces 4 derniers chiffres :</strong>
            <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
                Choisissez l'animal a utiliser pour chaque ligne. Les noms non resolus seront ignores.
            </div>
            <table style="width:100%; font-size:12px; border-collapse:collapse; margin-top:10px;" class="duplicate-resolution-table">
                <tr style="border-bottom:1px solid var(--border-color);">
                    <th style="padding:6px 4px; text-align:left;">N° Travail</th>
                    <th style="padding:6px 4px; text-align:left;">Animal a utiliser</th>
                </tr>`;

        data.duplicates.forEach(function (nom) {
            let candidates = data.duplicate_candidates[nom] || [];
            let options = `<option value="">-- Ignorer --</option>`;
            candidates.forEach(function (c) {
                let label_parts = [c.name];
                if (c.identification_fr) label_parts.push("FR:" + c.identification_fr);
                if (c.id_lot) label_parts.push("Lot:" + c.id_lot);
                if (c.categorie) label_parts.push(c.categorie);
                if (c.statut && c.statut !== "ACTIF") label_parts.push("[" + c.statut + "]");
                options += `<option value="${c.name}">${label_parts.join(" — ")}</option>`;
            });

            html += `
            <tr style="border-bottom:1px solid var(--light-border-color);">
                <td style="padding:6px 4px; font-weight:600;">${nom}</td>
                <td style="padding:6px 4px;">
                    <select class="form-control input-xs duplicate-resolution-select"
                            data-nom="${nom}"
                            style="font-size:12px; height:28px;">
                        ${options}
                    </select>
                </td>
            </tr>`;
        });

        html += `</table></div>`;
    }

    // Matched animals with lactation info
    if (data.matched > 0) {
        html += `
        <h6>Animaux trouves avec leurs lactations</h6>
        <table style="width:100%; font-size:12px; border-collapse:collapse;">
            <tr style="border-bottom:1px solid var(--border-color);">
                <th style="padding:6px 4px; text-align:left;">N° Travail</th>
                <th style="padding:6px 4px; text-align:left;">ID Animal</th>
                <th style="padding:6px 4px; text-align:center;">Lactations</th>
                <th style="padding:6px 4px; text-align:left;">Periodes</th>
            </tr>`;

        for (let [nom, info] of Object.entries(data.lactation_info)) {
            let lac_details = info.details.map(
                (l) => `L${l.numero} (${l.debut} → ${l.fin})`
            ).join(", ");

            html += `
            <tr style="border-bottom:1px solid var(--light-border-color);">
                <td style="padding:6px 4px;">${nom}</td>
                <td style="padding:6px 4px;">${info.animal}</td>
                <td style="padding:6px 4px; text-align:center;">${info.lactations}</td>
                <td style="padding:6px 4px; font-size:11px;">${lac_details || '<span style="color:var(--text-muted);">Aucune</span>'}</td>
            </tr>`;
        }
        html += `</table>`;
    }

    html += `</div>`;

    $section.find(".preview-content").html(html);

    // Store preview data for import step
    page.__preview_data = data;
}


function render_results(page, data) {
    let $section = page.main.find(".results-section");
    $section.show();

    let html = `
    <div style="border:1px solid var(--border-color); border-radius:8px; padding:20px; background:var(--card-bg);">
        <h5>3. Resultats de l'import</h5>

        <div style="display:flex; gap:20px; flex-wrap:wrap; margin-bottom:15px;">
            <div style="flex:1; min-width:120px; padding:10px; border:1px solid var(--border-color); border-radius:6px; background:var(--alert-bg-success);">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Creees</div>
                <div style="font-size:22px; font-weight:600; color:var(--alert-text-success);">${data.created}</div>
            </div>
            <div style="flex:1; min-width:120px; padding:10px; border:1px solid var(--border-color); border-radius:6px;">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Ignorees (pas de lactation)</div>
                <div style="font-size:22px; font-weight:600;">${data.skipped_no_lactation}</div>
            </div>
            <div style="flex:1; min-width:120px; padding:10px; border:1px solid var(--border-color); border-radius:6px;">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Ignorees (animal inconnu)</div>
                <div style="font-size:22px; font-weight:600;">${data.skipped_no_animal}</div>
            </div>
            <div style="flex:1; min-width:120px; padding:10px; border:1px solid var(--border-color); border-radius:6px;">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Ecrasees</div>
                <div style="font-size:22px; font-weight:600;">${data.overwritten || 0}</div>
            </div>
            <div style="flex:1; min-width:120px; padding:10px; border:1px solid var(--border-color); border-radius:6px;">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Traites deja existantes</div>
                <div style="font-size:22px; font-weight:600;">${data.skipped_duplicate}</div>
            </div>
            <div style="flex:1; min-width:120px; padding:10px; border:1px solid var(--border-color); border-radius:6px;">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Lactations recalculees</div>
                <div style="font-size:22px; font-weight:600;">${data.lactations_updated}</div>
            </div>
        </div>`;

    if (data.errors && data.errors.length > 0) {
        html += `
        <h6>Erreurs (${data.errors.length})</h6>
        <div style="max-height:300px; overflow-y:auto;">
        <table style="width:100%; font-size:12px; border-collapse:collapse;">
            <tr style="border-bottom:1px solid var(--border-color);">
                <th style="padding:4px;">Animal</th>
                <th style="padding:4px;">Date</th>
                <th style="padding:4px;">Raison</th>
            </tr>`;

        data.errors.forEach(function (e) {
            html += `
            <tr style="border-bottom:1px solid var(--light-border-color);">
                <td style="padding:4px;">${e.animal}</td>
                <td style="padding:4px;">${e.date}</td>
                <td style="padding:4px;">${e.reason}</td>
            </tr>`;
        });

        html += `</table></div>`;
    }

    html += `</div>`;
    $section.find(".results-content").html(html);
}
