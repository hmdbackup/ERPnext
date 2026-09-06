# HMD AGRO — Code Conventions

Coding standards, naming, message/error-code registry, the HMD Configuration field catalog, scheduler hooks, and test idioms for the `hmd_agro` Frappe app. Read the cited code for exact behavior; this file distills the stable rules. French domain terms are preserved verbatim throughout.

## 1. Code style

| Aspect | Rule | Source |
|---|---|---|
| Python indent | **4 SPACES** in all committed code | verified: `insemination.py` 361 space-indented lines, 0 tab lines |
| ruff `indent-style` | declares `"tab"` — **and** `.editorconfig` declares `indent_style=tab` | `pyproject.toml` `[tool.ruff.format]`, `.editorconfig` |
| Do NOT run | `ruff format` repo-wide | it would reflow the whole tree from spaces → tabs, churning every file |
| Line length | `line-length = 110` (ruff wrap) | `pyproject.toml`. Note `E501` is in ruff's `ignore` list, so over-long lines are not a lint error |
| quote-style | `"double"` | `[tool.ruff.format]` |
| ruff lint select | `F, E, W, I, UP, B, RUF`; many B/E/F rules ignored | `[tool.ruff.lint]` |
| Other `.editorconfig` | `end_of_line = lf`, `insert_final_newline = true`, JSON = 2-space (no final newline) | `.editorconfig` |
| JS / Vue / SCSS | formatted by prettier; linted by eslint (`eslint:recommended`, most stylistic rules off — `indent`, `quotes`, `semi` disabled, prettier owns formatting) | `.eslintrc` |

**Pre-commit hooks** (`.pre-commit-config.yaml`): pre-commit-hooks (`trailing-whitespace`, `check-merge-conflict`, `check-ast`, `check-json`, `check-toml`, `check-yaml`, `debug-statements`); **ruff** import-sorter (`--select=I --fix`); **ruff** linter; **ruff-format**; **prettier** (js/vue/scss); **eslint** (js). `pyupgrade` is covered by ruff's `UP` rules, not a separate hook.

## 2. Naming

| Element | Convention | Example |
|---|---|---|
| DocType name | Title-Case-with-spaces | `Etat Corporel`, `Mere Externe`, `Traitement Medicale`, `HMD Configuration` |
| DocType slug / folder | snake_case | `etat_corporel`, `hmd_configuration` |
| Fieldname | snake_case, French | `date_velage`, `etat_gestation`, `traite_max_litres` |
| Select options | UPPER_SNAKE, French | `EN_COURS`, `GESTANTE`, `TRAITEMENT_MEDICAL`, `VACHE`, `GENISSE` |
| Private helper | leading `_` | `_validate_immutability`, `_try_save_with`, `_build_stock_entry` |
| Module-level constant | UPPER_SNAKE | `LACTATION_RECALC_FIELDS`, `JS_FIELDS`, `DEFAULTS`, `PREFIX_TN` |
| `module` value | exactly `HMD AGRO` (no trailing space) | DocType JSON `"module"`, fixtures filters |
| `app_title` | `HMD AGRO ` (trailing space — distinct from module) | `hooks.py` |

## 3. Code & message conventions

- **Blocking errors:** `frappe.throw("<French message>")`. User-facing text is **French**; comments and docstrings are **English**.
- **Warnings (non-blocking):** `frappe.msgprint(..., indicator="red"|"orange", alert=True)` (e.g. `insemination.py:243`, `traitement.py:100`, `traite.py:149`).
- Codes live in **two places**, not one — do not assume every code rides inside a `throw` string:
  - `ERR-<DT>-<nn>` / `RG<nn>` → prefix is **inside** the French `throw()` message.
  - `CF-<DT>-<nn>` / `RC-<DT>-<nn>` → tag in the **docstring / method comment**; the throw message often carries no code.

**Code registry** (role inferred from observed usage; acronyms not formally defined in code):

| Prefix | Role | Real examples (`file:line`) |
|---|---|---|
| `ERR-` | Blocking validation, code in message | `ERR-IA-01` `insemination.py:94`; `ERR-VEL-01` `velage.py:48`; `ERR-LAC-01` `lactation.py:70`; `ERR-AVO-01` `avortement.py:25` |
| `CF-` | Functional control (docstring tag), message usually code-less | `CF-ANI-01/02` `animal.py:37`; `CF-VEL-01/02` `velage.py:42`; `CF-TRA-01` `traite.py:62`; `CF-CRA-01` `ration.py:31` |
| `RG` | Règle de gestion (business rule), code in message | `RG19` `traitement.py:28`; `RG17` `velage.py:111`; `RG15/RG16` `velage.py:226`; `RG20` `traitement.py:72` |
| `RC-` | Règle de calcul (compute method, docstring tag) | `RC-RAT-01` `ration.py:39`; `RC-TMD-01` `traitement.py:62` |

Note: most validation/derivation logic lives in the doctype controller methods (e.g. `set_sexe_from_categorie`, `validate_date_ia`), grouped by these code tags.

## 4. HMD Configuration field catalog

Single DocType `hmd_configuration.json` (36 stored fields + section/column/HTML breaks). Defaults below = JSON `default` (matches the patches and `test_hmd_config.py` `EXPECTED_DEFAULTS`). **Read pattern (Python):** `get_config("field", default=...)` — `utils/config.py`; the `default` arg is mandatory in spirit (Singles store `0`/`0.0`, not the JSON default, when uninitialized, hence the seed patches). **Read pattern (JS):** `frappe.boot.hmd_config.<field>` — injected by `boot.boot_session` for the 9 `JS_FIELDS` only.

`JS_FIELDS` (9): `dim_fv_max_multi`, `dim_thp_max`, `dim_hp_max`, `dim_mp_max`, `dim_primipare_cap`, `last_third_pct`, `production_drop_alert_pct`, `ecart_lait_seuil_negatif_l`, `ecart_lait_seuil_perte_pct`.

| Group | Field | Default | Purpose |
|---|---|---|---|
| Alertes | `chaleur_genisse_age_mois` | 14 | génisse heat-alert trigger age |
| Alertes | `chaleur_post_velage_jours` | 45 | post-vêlage heat alert delay |
| Alertes | `verification_j21_jours` | 18 | first gestation check delay |
| Alertes | `tarissement_advance_jours` | 7 | tarissement alert lead days |
| Alertes | `velage_advance_jours` | 15 | VELAGE_IMMINENT alert lead |
| Alertes | `delvo_advance_jours` | 1 | DELVO test alert lead |
| Alertes | `chaleur_cycle_jours` | 21 | œstral cycle, reschedule heat |
| Alertes | `alerte_lead_jours` | 2 | gestation-check follow-up lead (cap 7) |
| Lactation | `periode_velage_jours` | 280 | gestation length (Holstein); v1_5 |
| Lactation | `tarissement_window_jours` | 60 | tarissement window before vêlage |
| Lactation | `traite_max_litres` | 60 | max litres accepted per traite |
| Lactation | `production_initiale_jours` | 60 | lactation-start window (recalc) |
| Lactation | `pic_production_jours` | 150 | peak-production search window (recalc) |
| Lactation | `taux_tb_max_pct` | 10 | max taux butyreux validation |
| Lactation | `taux_tp_max_pct` | 10 | max taux protéique validation |
| Lactation | `production_drop_alert_pct` | -15 | daily production-drop highlight |
| Allotement | `dim_fv_max_multi` | 30 | JL max FV (multipare) |
| Allotement | `dim_thp_max` | 120 | JL max THP boundary |
| Allotement | `dim_hp_max` | 240 | JL max HP boundary |
| Allotement | `dim_mp_max` | 305 | JL max MP boundary |
| Allotement | `dim_primipare_cap` | 300 | primipare FV→FP cap |
| Allotement | `last_third_pct` | 66.7 | last-third early-move threshold |
| Bilan Lait | `ecart_lait_seuil_negatif_l` | 1 | red écart négatif threshold (L); JSON-only |
| Bilan Lait | `ecart_lait_seuil_perte_pct` | 5 | orange perte threshold (%); JSON-only |
| PFE seuils | `pfe_lc_optimal_min` | 2.0 | L/C optimal lower (green) |
| PFE seuils | `pfe_lc_optimal_max` | 2.4 | L/C optimal upper (green) |
| PFE seuils | `pfe_lc_alarm_min` | 1.5 | L/C red if below |
| PFE seuils | `pfe_lc_alarm_max` | 3.0 | L/C red if above |
| PFE seuils | `pfe_efficacite_min` | 1.4 | feed efficiency green threshold |
| PFE seuils | `pfe_efficacite_orange_min` | 1.0 | feed efficiency orange/red split |
| PFE seuils | `pfe_persistance_min` | 0.85 | persistance optimal lower (green) |
| PFE seuils | `pfe_persistance_max` | 0.95 | persistance optimal upper (green) |
| PFE seuils | `pfe_persistance_alarm_min` | 0.7 | persistance red if below |
| PFE seuils | `pfe_persistance_alarm_max` | 1.10 | persistance red if above |
| PFE seuils | `pfe_3ia_plus_max` | 15 | %3IA+ green target ceiling |
| PFE seuils | `pfe_3ia_plus_orange_max` | 25 | %3IA+ orange/red split |

Seed-patch attribution: v1_0 → alertes + lactation + allotement core (21 fields); v1_1 → 12 PFE seuils; v1_5 → `periode_velage_jours`; the two `ecart_lait_*` fields have JSON defaults only (no patch). On config save, `on_update` enqueues background recalcs when `pic_production_jours`/`production_initiale_jours` (lactations), `tarissement_window_jours` (tarissement dates), or `periode_velage_jours` (vêlage prévue) change — see `hmd_configuration.py`.

## 5. doc_events & scheduler

`doc_events` is **not used** — the hook block in `hooks.py` is commented out. Most event logic lives in the controllers (`validate`, `on_update`, `after_insert`, `on_trash`), not in centralized `doc_events`.

`scheduler_events` (`hooks.py`) — 3 daily jobs:

```python
scheduler_events = {
    "daily": [
        "hmd_agro.hmd_agro.doctype.alerte.alerte.generate_alerts",
        "hmd_agro.hmd_agro.doctype.traitement.traitement.refresh_attente_lait",
        "hmd_agro.hmd_agro.utils.feed_distribution.generate_daily_distribution",
    ],
}
```

`boot_session = "hmd_agro.boot.boot_session"` injects `frappe.boot.hmd_config` (see §4).

## 6. Tests

Test files (`hmd_agro/hmd_agro/tests/`): `test_alert_system`, `test_alerte_config`, `test_aliment_correction`, `test_alimentation_report`, `test_allotement_report`, `test_cascade_delete`, `test_correction_propagates_to_report`, `test_cost_flow`, `test_effectif_report`, `test_feed_distribution`, `test_full_flow`, `test_hmd_config`, `test_indicateurs_report`, `test_production_lot_report`, `test_reproduction_report`, `test_saisie_reconciliation`, `test_semence_dual_write`, `test_stock_integration`, `test_tarissement_config`, `test_traite_config`, `test_traitement_module`, `test_velage_prevue_config`. Per-doctype tests also exist (e.g. `doctype/velage/test_velage.py`, `doctype/insemination/test_insemination.py`).

Two idioms coexist:
- **FrappeTestCase + `setUp` seeding** — e.g. `test_saisie_reconciliation.py` (`from frappe.tests.utils import FrappeTestCase`, idempotent `setUp` creating Batiment/Lot/Taureau/Animal, asserting `ERR-*` codes via `assertRaises`).
- **Custom `run_all_tests()` runners via `bench execute`** — e.g. `test_hmd_config.py`, `test_full_flow.py` (manual `check`/`assert_test` + results dict; per-run unique IDs to avoid collisions).

Shared fixtures: `tests/seed_data.py` (`seed(n)` additive, `seed_baseline()` deterministic 17-cow set, `cleanup()`); `tests/_sle_seed_helpers.py` posts Stock Ledger Entry fixtures mirroring nightly production (`seed_test_distribution`, `clean_test_stock`). Helpers are idempotent and only touch TEST-/seed-prefixed data.
