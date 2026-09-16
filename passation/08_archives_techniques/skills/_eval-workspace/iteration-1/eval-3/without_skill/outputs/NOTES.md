# Insemination — two changes

Target controller: `hmd_agro/hmd_agro/doctype/insemination/insemination.py`
(the `Insemination(Document)` class). The proposed implementation lives in
`insemination.py` next to this file. Only the two methods below are new
behaviour; in the real app they would be folded into the existing
`validate()` / `on_update()` hooks rather than replacing the whole file.

## Change 1 — a pregnant cow cannot be inseminated

- Pregnancy is stored on the **Animal** doctype, not the Insemination:
  `Animal.etat_gestation` is a Select with values `GESTANTE` / `VIDE`
  (confirmed in `animal.json`).
- Implemented in `validate_animal_not_pregnant()`, called from `validate()`.
- We read `etat_gestation` for `self.animal` and `frappe.throw` (error code
  `ERR-IA-06`, matching the app's existing error-code convention) when it is
  `GESTANTE`.
- **Guarded with `self.is_new()`**: the check only blocks the *creation* of a
  new IA. This is essential — change 2 flips the cow to `GESTANTE` as a side
  effect of a successful result, so without the `is_new()` guard the very
  record that caused the pregnancy could never be saved again (you could not
  later edit observations, mark it ECHOUEE, etc.). Blocking creation is the
  correct semantic: you can't *start* a new insemination on a pregnant cow.

## Change 2 — on success, compute & store calving + dry-off dates

- Trigger: result (`resultat`, Select `EN_ATTENTE` / `REUSSIE` / `ECHOUEE`)
  becomes `REUSSIE`. Handled in `on_update()` via
  `sync_gestation_dates_on_result()`.
- Gated on `self.has_value_changed("resultat")` so re-saving any other field
  does not re-run the side effects (idempotent w.r.t. unrelated edits).
- Formulas (matching the conventions already used elsewhere in the codebase —
  `utils/velage_prevue_recalc.py`, `update_animal_on_resultat`):
  - `date_velage_prevue = date_ia + periode_velage_jours`
  - `date_tarissement   = date_velage_prevue - tarissement_window_jours`
- Periods come from the **HMD Configuration** Single via the project's
  `get_config(field, default=...)` accessor, with documented defaults
  `periode_velage_jours = 280` (gestation length) and
  `tarissement_window_jours = 60` (dry period before calving). Using
  `get_config` rather than hard-coded literals keeps the herd-wide parameter
  editable and consistent with the rest of the app.
- Results are written onto the **Animal** record (`date_velage_prevue`,
  `date_tarissement`), together with `etat_gestation = "GESTANTE"` and
  `id_ia_fecondante = self.name` so the cow points back to the fecundating IA.
- `animal.flags.ignore_validate = True` before `save()`: this is a
  system-driven projection update; we don't want the Animal's own validation
  to fire on it.

### Rollback on failure (defensive)
`ECHOUEE` clears the three projection fields and resets the cow to `VIDE`,
**only** when `Animal.id_ia_fecondante == self.name`. Without this we could
wipe a valid gestation that a different IA produced. This keeps the
GESTANTE flag (which gates change 1) honest if a result is corrected.

## Key decisions
- State lives on Animal, computation is triggered by Insemination — chosen
  because the rest of the app reads gestation/calving from Animal.
- `is_new()` on the guard and `has_value_changed()` on the trigger are the
  two load-bearing conditions that make the pair of features coexist without
  deadlocking each other.
- `add_days` / config-driven periods reuse existing project utilities rather
  than introducing new constants.
```
