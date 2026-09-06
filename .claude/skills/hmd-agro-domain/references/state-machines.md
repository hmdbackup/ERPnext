# HMD AGRO — State Machines & Cascades

Behavior a developer MUST preserve when editing these controllers. French domain
terms are verbatim (the DB stores them). All `file:line` cite real controller code.

Config keys (via `get_config(key, default)`, `utils/config.py:12`; reads Single
`HMD Configuration`, falls back to default when unset):
- `periode_velage_jours` default **280** — gestation length (IA → vêlage).
- `tarissement_window_jours` default **60** — dry-off window before vêlage.
- `production_initiale_jours` default **60** — early-lactation production window.
- `pic_production_jours` default **150** — peak-production search window.

---

## 1. Animal lifecycle

### categorie / sexe
`sexe` is DERIVED from `categorie`, never set by hand (`set_sexe_from_categorie`,
`animal.py:36`):
```
categorie ∈ {VACHE, GENISSE, VELLE}  → sexe = F
categorie ∈ {VEAU, TAURILLON}        → sexe = M
```
VELLE/VEAU (calf) vs GENISSE/TAURILLON (juvenile) is a conceptual age grouping for
reporting (`utils/live_state.py:21`) — there is NO controller-driven age promotion.
The ONLY categorie transition a controller performs:
```
GENISSE ──(first Velage)──► VACHE     # velage.py:236 update_mother
```
First vêlage also stamps `date_premier_velage` (`velage.py:238`); both are reversed
on vêlage delete if it was the only vêlage (`velage.py:364-372`).

### statut
```
ACTIF ──► VENDU | MORT | REFORME | A_VENDRE
```
Exit to VENDU/MORT/REFORME requires `date_sortie` (`validate_dates`, `animal.py:64`).
On_update fires an EXIT CASCADE (`_close_active_records_on_exit`, `animal.py:170`),
only when `statut` changed into VENDU/MORT/REFORME:
1. EN_COURS Lactation → INTERROMPUE (+ `date_tarissement`=today, `jours_lactation`);
   etat_lactation → "" (`animal.py:179-196`).
2. EN_ATTENTE Insemination → ECHOUEE via ignore_validate save, which runs
   `update_animal_on_resultat` to reset gestation (`animal.py:199-207`).
3. Else if still GESTANTE: reset gestation fields directly (`animal.py:210-216`).
4. Open Alerte (NOUVELLE/CONFIRMEE/GESTANTE_PROBABLE) → NON_CONFIRMEE (`animal.py:219-227`).

### Read-only, hook-managed fields (PROTECTED against manual edits)
`etat_gestation` (GESTANTE/VIDE), `etat_lactation` (EN_PRODUCTION/TARIE/"") and
reproduction fields are written ONLY by hooks, never by users.
- `protect_status_fields` (`animal.py:83`): throws if etat_gestation/etat_lactation
  changed vs `get_doc_before_save()`. Sole exception: initial "" → VIDE for a new
  female (`set_default_gestation`, `animal.py:72`).
- `protect_reproduction_fields` (`animal.py:98`) guards: `id_ia_fecondante`,
  `date_velage_prevue`, `date_premier_velage`, `date_tarissement`,
  `id_velage_naissance`, `attente_lait_active`, `date_fin_attente_lait`.

**Bypass:** hooks that legitimately write these set `flags.ignore_validate = True`
before `save()`; both guards short-circuit on `is_new()` OR `ignore_validate`
(`animal.py:85,99`). This flag is the ONLY sanctioned write path — see
Insemination/Velage/Avortement.

`_track_lot_change` (`animal.py:149`, on_update audit): if `id_lot` changed, insert
an `Allotement History` row (from_lot/to_lot/moved_by/source from
`flags.lot_change_source`, default "MANUAL"). Captures all paths.

---

## 2. Lactation state machine

```
   EN_COURS ──► TARIE ──► EN_COURS   (TARIE may re-open)
       │
       └───────► INTERROMPUE         (terminal, no exit)
```
Transition table (`validate_statut_transition`, `lactation.py:52`):
- EN_COURS → {TARIE, INTERROMPUE}
- TARIE → {EN_COURS}
- INTERROMPUE → {} (terminal)
Any other transition throws. Skipped when `is_new()`/`ignore_validate`.

Effect on `Animal.etat_lactation` (`sync_animal_etat`, on_update, `lactation.py:113`,
only when statut changed):
```
→ TARIE        : etat_lactation = "TARIE"
→ INTERROMPUE  : etat_lactation = ""
→ EN_COURS     : etat_lactation = "EN_PRODUCTION"
```
- `after_insert` (`lactation.py:96`): manual EN_COURS insert → etat_lactation
  "EN_PRODUCTION".
- `auto_fill_date_tarissement` (`lactation.py:106`): → TARIE without a date stamps today.
- `close_tarissement_alerts` (`lactation.py:126`): → TARIE/INTERROMPUE closes
  NOUVELLE TARISSEMENT alerts → TRAITEE.
- One EN_COURS per animal enforced (`validate_no_active_lactation`, `lactation.py:74`).

**on_trash guards** (`lactation.py:142`) — throws (blocks delete) if ANY of:
- `velage_debut` set ("supprimez le vêlage associé d'abord"),
- a Traite references this lactation,
- an Insemination references this lactation.
Otherwise, if EN_COURS, resets Animal.etat_lactation = "".

---

## 3. Insemination result machine

```
   EN_ATTENTE ──► REUSSIE ──► ECHOUEE   (blocked if a Velage depends)
        │
        └────────► ECHOUEE              (terminal)
```
Transition table (`validate_resultat_transition`, `insemination.py:60`):
- EN_ATTENTE → {REUSSIE, ECHOUEE}
- REUSSIE → {ECHOUEE} — but BLOCKED if `exists Velage{insemination=self}`
  (`insemination.py:73`).
- ECHOUEE → {} (terminal).
One EN_ATTENTE per animal (`validate_no_pending_ia`, `insemination.py:126`).
Only VACHE/GENISSE, not already GESTANTE (`validate_animal_eligible`, `insemination.py:87`).

### On → REUSSIE (gestation sync, `update_animal_on_resultat`, `insemination.py:168`)
```python
animal.id_ia_fecondante  = self.name
periode = get_config("periode_velage_jours", 280)
animal.date_velage_prevue = add_days(self.date_ia, periode)          # IA + 280
window  = get_config("tarissement_window_jours", 60)
animal.date_tarissement   = add_days(date_velage_prevue, -window)    # vêlage - 60
animal.etat_gestation     = "GESTANTE"
animal.flags.ignore_validate = True; animal.save()
```

### On → ECHOUEE (`insemination.py:184`)
Only if `animal.id_ia_fecondante == self.name`: reset id_ia_fecondante,
date_velage_prevue, date_tarissement → None; etat_gestation → "VIDE"
(ignore_validate save). Then close NOUVELLE alerts on this IA → NON_CONFIRMEE,
and TARISSEMENT/VELAGE_IMMINENT alerts via `_close_gestation_alerts`.

### after_insert / on_trash
- `after_insert` (`insemination.py:349`): `decrement_semence_stock` (FIFO batch
  pick, Material Issue −1 paillette) + `close_chaleur_alerts`.
- `on_trash` (`insemination.py:353`): BLOCKS if a Velage depends. If REUSSIE and
  still the fecundating IA, restore animal → VIDE (mirror of ECHOUEE). Delete
  linked alerts, `restore_semence_stock` (+1), recount lactation `nb_inseminations`.

---

## 4. Velage cascade

### after_insert (`velage.py:35`) — runs in this order
Precondition: animal GESTANTE (`validate_animal_gestante`, `velage.py:49`).
1. **create_calves** (`velage.py:110`): per live veau, create an Animal (categorie
   VEAU if M else VELLE; race/id_mere/id_pere; `date_naissance`=date_velage;
   `id_velage_naissance`=self; ignore_validate insert), stamp id_veau1/2. Auto-gen
   10-digit ID if blank; create a NAISSANCE Pesee if `poids` given.
2. **create_lactation** (`velage.py:189`): FIRST auto-close any existing EN_COURS →
   TARIE (`date_tarissement`=date_velage, compute `jours_lactation`). THEN insert a
   NEW Lactation EN_COURS (`velage_debut`=self, `numero_lactation`=count+1,
   `date_debut`=date_velage); stamp `self.lactation`. All ignore_validate.
3. **update_mother** (`velage.py:225`): etat_gestation → "VIDE"; null
   id_ia_fecondante/date_velage_prevue/date_tarissement. If GENISSE →
   categorie="VACHE" + `date_premier_velage`=date_velage. ignore_validate save.
4. **close_open_alerts** (`velage.py:246`): NOUVELLE/CONFIRMEE alerts → TRAITEE.

### on_trash REVERSAL (`velage.py:259`) — symmetric to above
Guards first (throw → block delete):
- `_check_calves_safe_to_delete` (`velage.py:267`): any veau with an Insemination,
  a non-NAISSANCE Pesee, or an Etat Corporel blocks.
- `_check_lactation_safe_to_delete` (`velage.py:301`): any Traite on the lactation blocks.
Then reverse:
- `_delete_calves` (`velage.py:312`): delete birth Pesee(s) then the calf Animal(s).
- `_delete_lactation` (`velage.py:329`): reset Animal.etat_lactation="", null the
  lactation's `velage_debut` back-reference (so Lactation.on_trash guard #1 passes),
  delete the lactation.
- `_restore_mother` (`velage.py:343`): etat_gestation → "GESTANTE"; if linked IA,
  recompute date_velage_prevue/date_tarissement from `date_ia` (same 280/60 math as
  §3). Reverse VACHE→GENISSE only if `date_premier_velage == date_velage` AND no
  other Velage exists; clear date_premier_velage. ignore_validate save.

NOTE: the closed previous lactation (step 2) is NOT re-opened on reversal — only
the lactation this vêlage CREATED is deleted.

---

## 5. Traite → Lactation recalculation

`update_lactation_production` (`traite.py:186`) runs on after_insert, on_update,
AND on_trash — every Traite mutation re-aggregates the parent Lactation from ALL
its traites (SQL SUM/MAX over `tabTraite`). No requirement the lactation be
EN_COURS for recalc, but new traites require EN_COURS (`validate_lactation_en_cours`).

Metrics recomputed:
- `production_totale` = SUM(quantite_litres) over all traites.
- `pic_production` = MAX daily total within first `pic_production_jours` (150) DIM.
- `lactation_305j` = SUM within first 305 DIM (only if `date_debut` set).
- `production_initiale` = SUM within first `production_initiale_jours` (60) DIM.
- `moyenne_production` = total / days-since-date_debut (only if days > 0).

**Escape hatch:** `flags.skip_lactation_update` short-circuits the recalc
(`traite.py:192`). Bulk imports set it per-row and run ONE recalc per affected
lactation at the end — preserve this when adding to the method.

---

## 6. Gestation reset paths (all set etat_gestation = VIDE; differ on promotion)

| Trigger | etat_gestation | Promote GENISSE→VACHE? | Owner |
|---|---|---|---|
| **Velage** after_insert | VIDE + null IA fields | YES (+ date_premier_velage) | `velage.py:225` |
| **Avortement** after_insert | VIDE + null IA fields | NO | `avortement.py:73` |
| **Insemination** → ECHOUEE | VIDE + null IA fields | NO | `insemination.py:184` |

All three null `id_ia_fecondante`/`date_velage_prevue`/`date_tarissement` and save
with `ignore_validate`. Avortement requires GESTANTE (`avortement.py:19`) and closes
gestation alerts → NON_CONFIRMEE. Avortement on_trash restores GESTANTE (recomputes
dates from IA, 280/60) — NO categorie change (`avortement.py:101`).

Milk-withdrawal (parallel, not gestation): Traitement médical computes
`date_fin_attente_lait = date_traitement + delai_attente_lait` per medicament row
(`traitement.py:61`); `update_animal_attente_lait` (`traitement.py:139`) sets
Animal.attente_lait_active + the MAX future end-date across all the animal's
treatments; on_trash recomputes excluding self (`clear=True`) and restores stock.

---

## 7. Invariants to preserve

- **One EN_COURS Lactation per animal** — enforced at validate (`lactation.py:74`)
  AND maintained by velage auto-close (`velage.py:189`). Never create a second.
- **Cascades must be symmetric** — every after_insert effect has a guarded reversal
  in on_trash (Velage §4, Insemination §3, Avortement §6). Adding a forward effect
  means adding its reversal.
- **Protected fields only via hooks** — write etat_gestation/etat_lactation and the
  reproduction/attente_lait fields ONLY after `doc.flags.ignore_validate = True`;
  manual edits throw (`animal.py:83,98`).
- **Gestation math uses get_config** — IA+`periode_velage_jours`(280) for
  date_velage_prevue; minus `tarissement_window_jours`(60) for date_tarissement.
  Same constants in §3, §4 restore, §6 restore — keep them in lockstep.
- **Production windows via get_config** — `pic_production_jours`(150) and
  `production_initiale_jours`(60) route through `get_config`; the 305-day window is
  the sole hardcoded exception. Don't add new inline literals — use `get_config`.
- **Deletion guards before reversal** — block delete when downstream records exist
  (Traite/IA/Pesee/Etat Corporel/Velage) rather than orphaning or cascading blindly.
