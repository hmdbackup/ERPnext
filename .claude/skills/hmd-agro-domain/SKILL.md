---
name: hmd-agro-domain
description: >-
  Business rules, lifecycle state machines, and domain invariants of the HMD AGRO
  dairy app (`hmd_agro`). Use this WHENEVER implementing or modifying any feature
  that touches herd biology or husbandry workflow: the cattle lifecycle
  (categorie VELLE/VEAU/GENISSE/VACHE/TAURILLON and its transitions), lactation &
  traite, reproduction (insémination, vêlage, avortement, gestation), lots &
  bâtiments / allotement by days-in-milk, santé & traitement (parage, délai
  d'attente lait), or alertes. It tells you the RG/CF business rules, the exact
  state transitions, and the automatic cascades you must preserve (e.g. a Vêlage
  that creates calf Animals + opens a Lactation + promotes GENISSE→VACHE).
  Trigger for tasks like "add validation to Insemination", "change the
  tarissement logic", "implement RG14", "fix the lactation status transition",
  "why does deleting a Velage fail", or any cattle/repro/lot/health behavior
  change. Pair with hmd-agro-dev (conventions, where code lives) and hmd-agro-kpi
  (indicators & reports).
---

# HMD AGRO — Domain Rules & State Machines

This app encodes the husbandry logic of a dairy herd. The behavior is **event
-driven**: DocType controllers fire cascades on `after_insert`/`on_update`/
`on_trash`, and a daily scheduler raises `Alerte`s. Get the **state machines and
cascades** right and the rest follows; get them wrong and herd state silently
drifts. The code is the source of truth — the Drive spec is intent (and diverges;
deltas are flagged in `references/business-rules.md`).

## Non-negotiable invariants

Hold these true in every change:

1. **One `EN_COURS` lactation per animal.** A Vêlage auto-closes any prior open
   lactation as `TARIE` before opening the new one (RG05/RG07).
2. **`Animal.etat_gestation` / `etat_lactation` are read-only and hook-managed.**
   They reject manual edits; only Insemination/Velage/Lactation/Avortement hooks
   write them (via `flags.ignore_validate = True`). Never set them directly from
   new code — go through the owning event.
3. **Cascades must be symmetric.** Whatever an `after_insert` creates/changes, the
   matching `on_trash` must reverse — with guards that block deletion when
   downstream records exist. See `references/state-machines.md`.
4. **Thresholds come from config.** Ages, day-windows, max-litres, gestation
   length — all via `get_config("...", default=...)`. Never hardcode. (Details:
   hmd-agro-dev.)
5. **Historical state is reconstructed, not read.** For any *past* date use
   `utils/live_state.py`; live `Animal.etat_*` is "now" only. (Details:
   hmd-agro-kpi.)

## Cattle lifecycle (Animal)

```
                 (female)                first Velage              tarissement/réforme
   naissance ─▶ VELLE ──(12 mo, RG01)──▶ GENISSE ──(RG03/RG16)──▶ VACHE ──▶ (statut exit)
   naissance ─▶ VEAU  ──(12 mo, RG02)──▶ TAURILLON
```

- `categorie` ∈ `VELLE | VEAU | GENISSE | VACHE | TAURILLON`. `sexe` (read-only)
  is derived: `VACHE/GENISSE/VELLE → F`, `VEAU/TAURILLON → M`.
- `statut` ∈ `ACTIF | VENDU | MORT | REFORME | A_VENDRE`. Leaving `ACTIF`
  (vente/mort/réforme) triggers the **exit cascade** on `Animal.on_update`:
  close the active lactation (`INTERROMPUE`, RG04), fail pending IA, close open
  alerts, refresh lot counts.
- `etat_gestation` ∈ `GESTANTE | VIDE`; `etat_lactation` ∈ `EN_PRODUCTION | TARIE`
  — both protected (invariant 2).
- Genealogy: `id_mere` (Animal) or `id_mere_externe` (Mere Externe, for purchased
  animals), `id_pere` (Taureau). A purchased animal sets `est_achat` + `date_entree`.

## Reproduction cycle (the spine of the app)

```
 GENISSE/VACHE (VIDE) ──Insemination──▶ resultat=EN_ATTENTE
        │                                     │
        │                          REUSSIE ──▶ etat_gestation=GESTANTE
        │                                     │  date_velage_prevue = date_ia + periode_velage_jours (280)
        │                                     │  date_tarissement   = date_velage_prevue − tarissement_window_jours (60)
        │                          ECHOUEE ──▶ reset to VIDE, clear dates, close alerts
        ▼
      Velage (after_insert cascade) ──▶ create calf Animal(s), open new Lactation EN_COURS,
                                        mother GESTANTE→VIDE, GENISSE→VACHE, set date_premier_velage,
                                        close open alerts
```

- **Insemination** (`resultat`: `EN_ATTENTE → REUSSIE | ECHOUEE`; `REUSSIE→ECHOUEE`
  blocked if a Velage depends). `numero_ia` auto-counts IAs in the lactation (or
  per-animal for a génisse). A génisse may be inseminated without a lactation;
  a VACHE requires an `EN_COURS` lactation. Each IA decrements semence stock
  (RG13). **RG14** (semence at zero → unusable) is **already realized by the stock
  layer**, not a flag: ERPNext v15 refuses a depleted batch, so the IA saves but
  the stock write is skipped with a red alert — don't add a custom `disponible`
  boolean. See hmd-agro-dev / `erpnext-integration.md` for both.
- **Avortement** resets gestation to `VIDE` (no promotion), unlike a Velage.
- `type_semence` ∈ `CONVENTIONNELLE | SEXEE`. Verification alerts (J21/J50) and
  chaleur alerts are generated/closed around the IA — see Alertes below.

Exact cascade steps, guards, and field writes: **`references/state-machines.md`**.

## Lactation & traite

- `Lactation.statut` ∈ `EN_COURS | TARIE | INTERROMPUE` (note: the spec said
  *TERMINEE* — the code uses **TARIE**). `EN_COURS ↔ TARIE` toggle is allowed;
  `INTERROMPUE` is terminal (set by the animal-exit cascade). Each transition
  syncs `Animal.etat_lactation`.
- `Traite.session` ∈ `MATIN | SOIR` **only** (the spec's MIDI was dropped).
  Uniqueness `(animal, date_traite, session)` is enforced through the autoname
  `TRA-{animal}-{date_traite}-{session}`. A traite is allowed only while the
  lactation is `EN_COURS` (RG08) and the animal was present on that date.
  `quantite_litres ≤ traite_max_litres` (config, default 60).
- Every Traite insert/update/delete **recomputes** the parent Lactation's
  `production_totale`, `pic_production`, `production_initiale`, `lactation_305j`,
  `moyenne_production` (config windows). Bulk imports set
  `flags.skip_lactation_update = True` and recompute once. (Details:
  state-machines.md.)

## Santé / traitement & délai d'attente lait

- `Traitement.type_traitement` ∈ `TRAITEMENT_MEDICAL | PARAGE`. **PARAGE is folded
  into Traitement** (foot scores `note_pied_ag/ad/arg/ard`, 1→5 by 0.5) — there is
  no separate Parage DocType. Locomotion is scored separately in `Note Mobilite`.
- An animal must be `ACTIF` to be treated (RG19). A medical treatment decrements
  medicament stock (RG20) per child row of `Traitement Medicale`.
- **Milk-withdrawal (délai d'attente lait):** a medical treatment sets
  `Animal.attente_lait_active` and `date_fin_attente_lait =
  date_traitement + Medicament.delai_attente_lait`. While active, that animal's
  milk is non-collectible (food safety, CF-TMD-03); the daily
  `traitement.refresh_attente_lait` job clears expired flags.

## Lots & allotement

Animals live in `Lot`s housed in `Batiment`s; lot membership tracks the
production stage by **days-in-milk (DIM)**. The named stages (FV/Fresh, THP, HP,
MP, plus TARISSEMENT/INFIRMERIE and the young-stock lots) are authoritative; lot
*numbers* are ambiguous across source docs. DIM boundaries are config-driven
(`dim_fv_max_multi 30`, `dim_thp_max 120`, `dim_hp_max 240`, `dim_mp_max 305`,
`dim_primipare_cap 300`). Lot moves are audit-logged (`Allotement History`); the
allotement engine suggests a target lot per cow.

Full lot structure, DIM ranges, barn→lot mapping, and the suggestion engine:
**`references/lots-allotement.md`**.

## Alertes (daily generation)

`alerte.generate_alerts` (daily) raises `Alerte` rows; `type_alerte` ∈
`CHALEUR_GENISSE | CHALEUR_POST_VELAGE | VERIFICATION_J21 | VERIFICATION_J50 |
TARISSEMENT | VELAGE_IMMINENT | DELVO`, each driven by a config lead/threshold
(e.g. `chaleur_genisse_age_mois 14`, `verification_j21_jours 18`,
`tarissement_advance_jours 7`, `velage_advance_jours 15`, `delvo_advance_jours 1`).
Lifecycle events close the alerts they resolve (a Velage closes its mother's open
alerts, an IA closes chaleur alerts). When adding an alert type, also add its
**closure** path so alerts don't pile up. Full rule list:
`references/business-rules.md`.

## Reference files

- `references/business-rules.md` — **the authoritative rule list:** RG01–RG27
  verbatim + CF/RC constraints, grouped by module, with every code-vs-spec delta
  flagged. Cite RG codes from here.
- `references/state-machines.md` — exact state diagrams, cascade step order,
  guards, and the field writes each controller performs (with `file:line`).
- `references/lots-allotement.md` — lot taxonomy, DIM ranges, barn mapping, the
  config DIM windows, and how the allotement suggestion works.
