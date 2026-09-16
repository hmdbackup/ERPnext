# Insemination — two changes

Deliverable: proposed controller in `insemination.py` (this folder). Nothing under
`hmd_agro/` was modified — this is an evaluation artifact only.

## What was asked

1. A cow that is already pregnant must not be able to be inseminated.
2. When an insemination's result is set to successful (`resultat = REUSSIE`),
   automatically compute and store the cow's **expected calving date**
   (`date_velage_prevue`) and her **dry-off / tarissement date**
   (`date_tarissement`).

## Key finding

Both behaviors are **already implemented** in the real controller at
`hmd_agro/hmd_agro/doctype/insemination/insemination.py`:

- Change 1 lives in `validate_animal_eligible()` — `ERR-IA-06` throws when
  `Animal.etat_gestation == "GESTANTE"`.
- Change 2 lives in `update_animal_on_resultat()` (fired from `on_update`) — on
  `REUSSIE` it sets `date_velage_prevue` and `date_tarissement` on the Animal.

The proposed file therefore shows the two methods as they should be, faithful to
the codebase's conventions, with one deliberate hardening (see below).

## Where each change lives (and why)

### Change 1 — pregnancy guard: `validate_animal_eligible()` (runs in `validate`)

- Reads `categorie` + `etat_gestation` from the `Animal` in one `get_value`.
- Rejects non-`VACHE`/`GENISSE` (`ERR-IA-01`) and, on creation, any animal
  already `GESTANTE` (`ERR-IA-06`). Throwing in `validate` blocks the save
  before the IA row is committed.
- `etat_gestation` is only **read** here, never written — it is a protected,
  hook-managed field (see invariant 2 below).

The GESTANTE check is gated on `self.is_new()` **on purpose** — this matches the
existing controller and the gate is load-bearing:

- On creation, a new IA targeting a pregnant cow is rejected. ✓
- The `animal` link is immutable after creation — `lock_identity_fields` throws
  on any change to `animal` — so an existing IA can never be re-pointed onto a
  pregnant cow. The only way to target a GESTANTE animal is a brand-new IA,
  which `is_new()` already covers.
- Critically, a `REUSSIE` IA sets **its own** animal to `GESTANTE`. The allowed
  `REUSSIE → ECHOUEE` transition (`state-machines.md` §3) re-saves this same IA
  while the animal is still `GESTANTE` (the rollback to `VIDE` happens later, in
  `on_update`). An **un**-gated check would see that `GESTANTE` state and throw
  `ERR-IA-06`, self-blocking the legal transition and rendering the `ECHOUEE`
  rollback branch unreachable. Gating on `is_new()` is exactly what prevents this
  self-block.

### Change 2 — calving + dry-off dates: `update_animal_on_resultat()` (runs in `on_update`)

On `resultat` transitioning to `REUSSIE`:

```
date_velage_prevue = date_ia + periode_velage_jours        # default 280
date_tarissement   = date_velage_prevue - tarissement_window_jours  # default 60
etat_gestation     = "GESTANTE"
id_ia_fecondante   = self.name
```

written to the `Animal` via an `ignore_validate` save. On `ECHOUEE` the same
fields are reset to `VIDE`/`None` (only when this IA is still the fecundating
one), preserving the existing rollback.

## Rules / conventions applied (cited)

- **RG12** (`references/business-rules.md`): *"Une insémination déclarée RÉUSSIE
  met automatiquement l'animal à l'état GESTANTE"* — and sets
  `date_velage_prevue = date_ia + periode_velage_jours` (280) and
  `date_tarissement = date_velage_prevue − tarissement_window_jours` (60). This
  is exactly Change 2.
- **CF-ANI-04 / CF-IA** (`references/business-rules.md`): only an `ACTIF`,
  female `VACHE`/`GENISSE` is repro-eligible; the reproduction spine in
  `SKILL.md` shows an IA targets an animal in the **VIDE** state — a `GESTANTE`
  animal is excluded. This is Change 1.
- **Domain invariant 2 — protected, hook-managed fields** (`SKILL.md`,
  `state-machines.md` §1): `etat_gestation`, `date_velage_prevue`,
  `date_tarissement`, `id_ia_fecondante` reject manual edits. Change 1 only
  reads `etat_gestation`; Change 2 writes the protected fields exclusively
  through the **sanctioned bypass** — `animal.flags.ignore_validate = True`
  before `animal.save()` (the only allowed write path, per `state-machines.md`
  §1 and §3).
- **Domain invariant 4 — thresholds come from config** (`SKILL.md`): both
  day-windows are read via `get_config("periode_velage_jours", default=280)` and
  `get_config("tarissement_window_jours", default=60)` — never hardcoded
  (`utils/config.py`).
- **Lockstep constants** (`state-machines.md` §3/§4/§6, "Invariants to
  preserve"): the same 280/60 gestation math is mirrored in the Velage and
  Avortement *restore* paths; if these constants change they must change
  together. Routing both through `get_config` keeps them in lockstep.
- **Cascade symmetry** (invariant 3): the forward effect of Change 2 (set
  GESTANTE + dates) already has its reversal in the `ECHOUEE` branch and in
  `on_trash` (both reset to `VIDE` + clear dates). No new forward effect is
  added that lacks a reversal.

## Why the change sits in the controller (not client JS)

The pregnancy guard and the date computation are domain invariants that must
hold for every write path (UI, API, imports, other hooks), so they belong in the
server-side DocType controller — consistent with how the rest of the
reproduction spine is enforced.
