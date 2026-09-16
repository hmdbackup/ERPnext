# Equipment & Maintenance tracking — proposed DocTypes

Tracks the farm's equipment (the two tractors, the milking machine, the milk
tank) and the maintenance interventions performed on them.

## What was created

Two DocTypes, each in its own folder so they drop straight into
`hmd_agro/hmd_agro/doctype/` without modification:

```
equipement/
  __init__.py
  equipement.json
  equipement.py
  equipement_list.js
intervention_maintenance/
  __init__.py
  intervention_maintenance.json
  intervention_maintenance.py
  intervention_maintenance_list.js
```

### 1. `Equipement` (master)
One row per physical asset. Named by `nom_equipement` (`autoname: field:...`,
unique) — same pattern as the existing `Batiment` and `Medicament` masters.

- `type_equipement` Select: `TRACTEUR / MACHINE_A_TRAIRE / TANK_A_LAIT / AUTRE`
  — covers the four items named (2× tracteur, machine à traire, tank à lait).
- `actif` Check (default 1) — mirrors `Batiment.actif` to retire equipment
  without deleting its history.
- Caractéristiques: `marque`, `modele`, `numero_serie`, `date_acquisition`,
  and a `batiment` Link reusing the existing **Batiment** master for location.
- Maintenance block:
  - `periodicite_maintenance_jours` (Int) — preventive interval.
  - `date_derniere_maintenance` (read_only, no_copy) — stamped by interventions.
  - `date_prochaine_maintenance` (read_only) — derived = last + periodicity,
    in `Equipement.validate()`. This is the field a future maintenance alert
    would read.

### 2. `Intervention Maintenance` (transactional)
One row per maintenance event, `Link`ed to `Equipement`. Named
`format:INT-{YYYY}-{#####}` — the same naming style as the transactional
`Traitement` (`TRT-{YYYY}-{#####}`).

- `type_intervention`: `PREVENTIVE / CORRECTIVE / INSPECTION / REPARATION / AUTRE`.
- `statut`: `PLANIFIEE / EN_COURS / REALISEE / ANNULEE` (coloured list indicator).
- `description` (required), `intervenant`, `cout` (Currency TND), and
  `duree_arret_heures` for downtime.

## Key decisions

- **Followed existing conventions exactly** — observed from `Batiment`,
  `Medicament`, `Pesee`, `Note Mobilite`, `Traitement`: `module: "HMD AGRO"`,
  System Manager permission block, `track_changes: 1`, section/column-break
  layout, French labels, `*_list.js` with `hide_name_column`, and the standard
  copyright header.
- **RG23 implemented** — *"an intervention updates the equipment's
  last-maintenance date."* `intervention_maintenance.py` reuses the
  `Pesee → Animal.dernier_poids` pattern: on `after_insert / on_update /
  on_trash` it recomputes `Equipement.date_derniere_maintenance` from the
  **latest `REALISEE` intervention** rather than blindly stamping `self`, so
  edits and deletes stay consistent. Saving the equipment re-derives
  `date_prochaine_maintenance` (groundwork for the RG27 maintenance alert).
- **Reused `Batiment`** for the location Link instead of a free-text field,
  consistent with how the app links masters.
- **No `bench` run / no schema migration** — JSON + controllers only, as asked.
  Nothing under `hmd_agro/` was touched.

## Architectural alternative (worth flagging before merge)

The Frappe/ERPNext-native route for this is **ERPNext `Asset` (+ `Asset
Category`)** for equipment and **`Asset Maintenance` / `Maintenance Visit`** for
interventions — those modules already provide maintenance schedules, due-date
tracking and cost capture out of the box. If the farm already runs ERPNext,
configuring Asset Maintenance + a couple of Custom Fields avoids reinventing
that machinery and gives finance/depreciation for free.

The custom DocTypes above were built because the task asked explicitly to
"create the DocType(s)", they stay fully self-contained inside the `HMD AGRO`
module, and they match the French-labelled, convention-driven style of the rest
of the app (the team already chose custom DocTypes for domain entities like
`Medicament` and `Batiment`). If ERPNext Asset is preferred, only the two JSON
schemas would be dropped; the RG23 last-maintenance-date logic maps cleanly onto
`Asset Maintenance Log`.

## Not included (out of scope / would confirm first)
- **RG27** maintenance-due alert generation — `date_prochaine_maintenance` is
  computed and ready, but wiring it into the daily `alerte.generate_alerts`
  job (a new `MAINTENANCE_EQUIPEMENT` alert type) is a separate change that
  touches `hmd_agro/` and was left out per the "don't modify the app" rule.
- Tests (`test_equipement.py`, `test_intervention_maintenance.py`) — easy to
  add following `test_pesee.py`; omitted to keep the proposal focused.
