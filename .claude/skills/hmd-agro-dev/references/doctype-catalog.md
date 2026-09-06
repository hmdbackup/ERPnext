# DocType Catalog

29 DocTypes, all in module **HMD AGRO**. Field lists live in each `<slug>/<slug>.json` — this catalog is for navigation. Controller tier is judged by `<slug>.py` line count + lifecycle-hook count: **Rich** = real orchestration (>100 lines or many hooks), **Thin** = small validators/helpers, **Stub** = empty class.

Paths are relative to `hmd_agro/hmd_agro/doctype/`. `*` in the istable/issingle column marks child tables (T) and singles (S).

## Cattle & lifecycle

| DocType | slug | T/S | autoname | controller | Purpose |
|---|---|---|---|---|---|
| Animal | `animal` | — | `field:identification_tn` | **Rich** (385) | Core herd record; status/reproduction field guards, lot tracking, cascade close on exit/trash. |
| Pesee | `pesee` | — | `format:PES-{animal}-{#####}` | Thin (85) | Weight measurement event. |
| Etat Corporel | `etat_corporel` | — | `format:EC-{animal}-{date}-{####}` | Thin (72) | Body condition score (BCS) record. |
| Note Mobilite | `note_mobilite` | — | `format:NM-{animal}-{date}-{####}` | Thin (50) | Locomotion/mobility note. |
| Mere Externe | `mere_externe` | — | `field:nom_mere` | Thin (26) | External (non-herd) dam reference. |

## Lactation & production

| DocType | slug | T/S | autoname | controller | Purpose |
|---|---|---|---|---|---|
| Lactation | `lactation` | — | `format:LAC-{animal}-{#####}` | **Rich** (212) | Lactation cycle; statut transitions, auto-tarissement, syncs animal etat. |
| Traite | `traite` | — | `format:TRA-{animal}-{date_traite}-{session}` | **Rich** (276) | Per-session milking; aggregates into lactation production. |
| Bilan Lait Journalier | `bilan_lait_journalier` | — | `format:BLJ-{date}` | Thin (30) | Daily milk balance / herd-level totals. |
| Snapshot Journalier | `snapshot_journalier` | — | `format:SNAP-{date_snapshot}` | Stub (6) | Daily herd-state snapshot. |
| Rapport Journalier Importe | `rapport_journalier_importe` | — | `format:RAP-IMP-{date}` | Stub (13) | Imported daily report payload. |

## Reproduction

| DocType | slug | T/S | autoname | controller | Purpose |
|---|---|---|---|---|---|
| Insemination | `insemination` | — | `format:INS-{animal}-{#####}` | **Rich** (407) | AI event; resultat transitions, semence stock decrement, gestation/chaleur alerts. |
| Velage | `velage` | — | `format:VEL-{animal}-{#####}` | **Rich** (377) | Calving; creates calves + lactation, updates dam, safe-delete cascades. |
| Avortement | `avortement` | — | `format:AVO-{animal}-{#####}` | Thin (125) | Abortion event. |
| Taureau | `taureau` | — | `field:nom_taureau` | Stub (9) | Bull (sire) master. |
| Semence | `semence` | — | `format:SEM-{taureau}-{####}` | Thin (45) | Semen straw batch + stock. |

## Lots & allotement

| DocType | slug | T/S | autoname | controller | Purpose |
|---|---|---|---|---|---|
| Lot | `lot` | — | `field:nom` | Thin (63) | Animal grouping/pen; ration tracking + animal count. |
| Batiment | `batiment` | — | `field:nom_batiment` | Stub (9) | Building/barn master. |
| Lot Ration History | `lot_ration_history` | — | `format:LRH-{lot}-{#####}` | Thin (112) | Audit trail of ration changes per lot. |
| Allotement History | `allotement_history` | — | `format:ALH-{animal}-{#####}` | Thin (55) | Audit trail of an animal's lot moves. |
| Allotment Session | `allotment_session` | — | `format:ALS-{session_date}-{#####}` | Thin (63) | Batch re-allotment session header. |
| Allotment Session Row | `allotment_session_row` | T | — | Stub (8) | Child row of an Allotment Session. |

## Nutrition

| DocType | slug | T/S | autoname | controller | Purpose |
|---|---|---|---|---|---|
| Aliment | `aliment` | — | `field:nom_aliment` | Thin (42) | Feed ingredient master. |
| Ration | `ration` | — | `field:nom_ration` | Thin (158) | Ration recipe; cost calc, immutability guard, lot assignment helpers. |
| Composition Ration | `composition_ration` | T | — | Stub (8) | Child row (ingredient + qty) of a Ration. |

## Health

| DocType | slug | T/S | autoname | controller | Purpose |
|---|---|---|---|---|---|
| Traitement | `traitement` | — | `format:TRT-{YYYY}-{#####}` | **Rich** (232) | Treatment event; medicament stock decrement, attente-lait window calc. |
| Traitement Medicale | `traitement_medicale` | T | — | Stub (8) | Child row (medicament + dose) of a Traitement. |
| Medicament | `medicament` | — | `field:nom_medicament` | Thin (48) | Drug master + stock + withdrawal periods. |

## Alerts & config

| DocType | slug | T/S | autoname | controller | Purpose |
|---|---|---|---|---|---|
| Alerte | `alerte` | — | `format:ALR-{#####}` | **Rich** (523) | Alert records + the alert-generation/disposition engine (module-level fns). |
| HMD Configuration | `hmd_configuration` | S | — | **Rich** (110) | Single global settings doc; cross-field validation of windows/leads/DIM. |

## Where the heavy logic lives

- **`alerte.py` (523)** — module-level alert engine: `generate_alerts()` + per-domain generators (genisse, post-velage, tarissement, velage, delvo) and disposition actions (delvo, tarir, reporter, a_revoir).
- **`insemination.py` (407)** — AI lifecycle: resultat transitions, `set_lactation`/`set_numero_ia`, semence batch picking + stock decrement/restore, chaleur/gestation alert closure.
- **`animal.py` (385)** — herd-record guardrails: status/reproduction field protection, rename handling, lot-change tracking, cascade-close active records on exit/trash.
- **`velage.py` (377)** — calving orchestration: `create_calves`/`_create_calf`, `create_lactation`, `update_mother`, and safe-delete cascades that restore mother and tear down calves/lactation.
- **`traite.py` (276)** — milking: session validation (lactation en cours, animal present, unique session), taux inheritance from bilan, `update_lactation_production` aggregation.
- **`traitement.py` (232)** — health: `calculate_attente_dates`, `decrement_medicament_stock`/`restore`, `update_animal_attente_lait`; plus `create_bulk_traitement` whitelisted helper.
- **`lactation.py` (212)** — cycle: statut transition validation, eligibility/no-active-lactation guards, auto date_tarissement, `sync_animal_etat`, tarissement alert closure.
- **`ration.py` (158)** — `calculate_cout_estime`, unique-aliment + immutability guards; `affecter_aux_lots` / `lots_using_ration` helpers.
- **`lot.py` (63)** — ration-change tracking + `update_nb_animaux` animal count maintenance.
- **`hmd_configuration.py` (110)** — Single doc; validates periode velage vs tarissement, tarissement advance window, alerte lead cap, and DIM monotonicity.

## Child tables

Three DocTypes have `istable=1` and exist only as grid rows of a parent (no autoname):

- **Composition Ration** → embedded in **Ration** (`composition` field).
- **Traitement Medicale** → embedded in **Traitement** (`medicaments` field).
- **Allotment Session Row** → embedded in **Allotment Session** (`rows` field).
