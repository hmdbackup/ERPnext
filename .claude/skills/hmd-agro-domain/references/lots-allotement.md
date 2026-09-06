# Lots & Allotement

Animals are grouped into **`Lot`s** (pens) housed in **`Batiment`s** (barns). For
cows in production, the lot reflects the **production stage by days-in-milk
(DIM)**; for young stock and dry cows it reflects age / proximity to calving. Lot
membership drives feed distribution (each lot runs a `Ration`) and the daily
reports (per-lot production & cost).

## ⚠️ Lot numbering is ambiguous — trust the named stage, not the number

The lot **number** ("Lot 1", "Lot 2"…) maps to different stages across the source
documents, so **numbers are display-only**. Always key logic off the **named
stage** (FV/Fresh, THP, HP, MP, TARISSEMENT, INFIRMERIE) — that is stable. In code
the stage tag is `Lot.lot_type`; `Lot.nom` (e.g. `LOT1`, `TARISSEMENT`, `TARIE`,
`INFIRMERIE`) is just the identifier.

| Source | Lot 1 | Lot 2 | Lot 3 | Lot 4 | Lot 5 |
|---|---|---|---|---|---|
| LISTE_DES_OBJETS | THP | HP | Fresh | MP | 305+ |
| Excel "Production & Moyennes" | HP | MP | — | — | — |
| Excel "Ration" | FV | THP | HP | — | — |

## Production-stage taxonomy (DIM ranges — from LISTE_DES_OBJETS, verbatim)

Cows in production (post-vêlage):

| Stage | Name(s) | DIM range | Meaning |
|---|---|---|---|
| **FV / Fresh** | Lot 3 - Fresh | **0–30 j** | toutes vaches post-vêlage; primipares restent ~300 j |
| **THP** | Lot 1 - THP | **30–120 j** | Très Haute Production |
| **HP** | Lot 2 - HP | **120–240 j** | Haute Production |
| **MP** | Lot 4 - MP | **241–305 j** | Moyenne Production |
| **(fin)** | Lot 5 | **305+ j** | fin de lactation |
| **INFIRMERIE** | Lot Infirmerie | n/a | malades / isolement |
| **TARISSEMENT** | Lot Tarissement | ~1 semaine avant vêlage | repos, arrêt traite |

Young stock & génisses:

| Stage | Name | Range | Note |
|---|---|---|---|
| Individuel | Lot Individuel | 0–3 mois | alimentation au seau |
| Collectif | Lot Collectif | 3–6 mois | sevrage progressif |
| Velle | Lot Velle | 6–12 mois | |
| Génisse | Lot Génisse | 12+ mois | jusqu'à gestation confirmée |
| Vêlage | Lot Vêlage | 20 j avant vêlage | toutes catégories de vache |

## Config-driven DIM boundaries (the engine reads these — never hardcode)

The allotement engine maps a cow's DIM to a target stage using `HMD Configuration`
(all via `get_config`, also mirrored to `frappe.boot.hmd_config` for the JS):

| Config field | Default | Boundary |
|---|---|---|
| `dim_fv_max_multi` | 30 | FV/Fresh upper bound (multipare) |
| `dim_thp_max` | 120 | THP upper bound |
| `dim_hp_max` | 240 | HP upper bound |
| `dim_mp_max` | 305 | MP upper bound |
| `dim_primipare_cap` | 300 | primipares stay in the early lots up to this DIM |
| `last_third_pct` | 66.7 | "last third" early-move threshold (gestation-based) |

The engine `_get_suggestion` (`report/allotement_animaux/allotement_animaux.py:229`)
emits a target **`lot_type` tag** in this priority order — verify against the code,
this is the authoritative logic:

1. `etat_lactation == "TARIE"` → **`TARIE`** lot.
2. `etat_gestation == "GESTANTE"` and `0 < (date_velage_prevue − today) ≤ tarissement_window_jours` (60) → **`TARISSEMENT`**.
3. Otherwise, by DIM:
   - **Primipare** (`numero_lactation == 1`): **`FV`** while `dim ≤ dim_primipare_cap` (300), else **`FP`**. A primipare stays in **FV for the whole lactation** — it does NOT progress through THP→HP→MP (this is the "primipares restent ~300 jours" rule).
   - **Multipare:**
     ```
     dim ≤ dim_fv_max_multi (30)  → FV
     dim ≤ dim_thp_max     (120)  → THP
     dim ≤ dim_hp_max      (240)  → HP
     dim ≤ dim_mp_max      (305)  → MP
     dim >  dim_mp_max            → FP   (fin de production)
     ```

Stage tags the engine returns: **`TARIE, TARISSEMENT, FV, THP, HP, MP, FP`**
(`find_lot(tag)` resolves a tag to a concrete `Lot`). Note the terminal tag is
**`FP`** (fin de production), which is the engine's name for the `>305 j` / "Lot 5"
stage in the taxonomy table above. The dry-off/TARISSEMENT move is driven by
`date_velage_prevue` vs the 60-day window — not by a fixed "20 days before" rule
(that figure is the farm's manual practice in LISTE_DES_OBJETS, not the engine).

## Barn → Lot mapping (from LISTE_DES_OBJETS, verbatim)

```
Barn 1 : LOTS 1, 2, 3          (production: THP / HP / Fresh)
Barn 2 : LOTS velle, genisse
Barn 3 : LOTS individuel, collectif
Barn 4 : LOTS velage, tarissement
Barn 5 : LOTS 4, 5             (production: MP / fin)
```

`Batiment.type_batiment` ∈ `ELEVAGE | PRODUCTION | ADMINISTRATIF | STOCKAGE`.

## The allotement engine & audit layer

- **Suggestion engine:** the `Allotement Animaux` report (`report/allotement_animaux/`)
  computes, per active cow, its current lot, DIM, gestation days, recent production
  (J / J-1 / J-2 + 3-day average), and a `suggestion` stage from the DIM windows
  above. This is the "where should each cow be?" view.
- **Reallocation session:** `Allotment Session` (+ child `Allotment Session Row`)
  snapshots a (e.g. weekly) reallocation decision — each row records
  `lot_before`/`lot_after`, `moved`, and the metrics that justified the move.
  `confirm_session(...)` persists it after the moves are applied.
- **Per-animal history:** every `Animal.id_lot` change writes an `Allotement
  History` row (`Animal._track_lot_change`). `lot_on_date(animal, date)` resolves a
  cow's lot on **any past date** by the most recent history row with
  `creation ≤ date` (falls back to `Animal.id_lot` if no history). Reports use this
  so per-lot history is correct even after a cow moves.
- **Per-lot ration history:** `Lot.id_ration_actuelle` changes are logged as
  episodes `[date_debut, date_fin)` in `Lot Ration History`; `Ration.affecter_aux_lots`
  bulk-assigns and opens/closes episodes. Feed distribution reads
  `ration_on_date(lot, date)` from these episodes.
- **Lot ordering:** `utils/lot_utils.lot_sort_key(nom)` sorts lots in production
  order: `LOT1..LOTn` (numeric) → `TARISSEMENT` → `TARIE` → `INFIRMERIE` → others.

## When you change allotement logic

- Read DIM boundaries from config; don't inline 30/120/240/305.
- Keep `nb_animaux` accurate (`Lot.update_nb_animaux` counts `ACTIF` animals).
- Any lot move must leave an `Allotement History` trail (go through the Animal
  controller, don't bulk-update `id_lot` silently) or historical reports break.
- Per-lot production/cost in reports relies on `lot_on_date` + `ration_on_date` —
  preserve both when refactoring.
