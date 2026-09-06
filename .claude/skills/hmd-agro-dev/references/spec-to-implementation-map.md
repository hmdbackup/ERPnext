# Spec → Implementation Map

The Drive spec (Dossier de Spécification / MCD) is a **relational design**. The
shipped app **deliberately diverged** from it: some spec entities became custom
DocTypes, several are **ERPNext core**, a few are **folded** into another
DocType, and some are **not built yet**. Read this before "implementing" any spec
entity — it is the map that stops you from rebuilding what already exists.

## How the model was translated (read once)

- **Integer-FK relational model → Frappe name-based Links.** Spec `ANIMAL.id_animal`
  (int PK) → DocType `Animal` named by `identification_tn`; FKs like
  `id_lactation` → `Link` fields by document name.
- **Super-type/sub-type → ERPNext Item + a thin custom DocType.** Spec `PRODUIT`
  super-type with `MEDICAMENT/ALIMENT/SEMENCE` sub-types → ERPNext **`Item`** plus
  a custom `Medicament`/`Aliment`/`Semence` DocType that each link to an `Item`.
- **Derived/aggregate tables are not stored.** `PRODUCTION_LAITIERE` is computed
  on the fly (`utils/live_state.py` + `Bilan Lait Journalier`), never persisted as
  a daily table.
- **Enum drift is real — trust the JSON, not the spec.** e.g. spec
  `LACTATION.statut = TERMINEE` but code = `TARIE`; spec Traite sessions
  `MATIN/MIDI/SOIR` but code = `MATIN/SOIR`; spec `SEXEE_FEMELLE/SEXEE_MALE` but
  code = `SEXEE`. Confirm options from `doctype/<slug>/<slug>.json`.

## 1. Spec entities realized as custom DocTypes

| Spec entity | Custom DocType | Notes / divergences |
|---|---|---|
| ANIMAL | **Animal** | `etat_lactation = EN_PRODUCTION\|TARIE`; `statut` adds `A_VENDRE`; genealogy via `id_mere`, `id_mere_externe`, `id_pere`. |
| PESEE | **Pesee** | `type_pesee = NAISSANCE\|MENSUELLE\|SEVRAGE\|VENTE`. |
| BARN | **Batiment** | Renamed FR. `type_batiment = ELEVAGE\|PRODUCTION\|ADMINISTRATIF\|STOCKAGE`. |
| LOT | **Lot** (+ Lot Ration History, Allotement History) | Capacity + current ration; lot moves & ration episodes are audit-logged in companion DocTypes. |
| LACTATION | **Lactation** | `statut = EN_COURS\|TARIE\|INTERROMPUE` (spec said TERMINEE). |
| TRAITE | **Traite** | `session = MATIN\|SOIR` only. Uniqueness via autoname `TRA-{animal}-{date_traite}-{session}`. |
| INSEMINATION | **Insemination** | `type_semence = CONVENTIONNELLE\|SEXEE`; `resultat = EN_ATTENTE\|REUSSIE\|ECHOUEE`. |
| VELAGE | **Velage** | `type_velage = FACILE\|DIFFICILE\|CESARIENNE`; creates calves + opens lactation. |
| TAUREAU | **Taureau** | Sire master + genetic indices. |
| SEMENCE | **Semence** (+ ERPNext `Batch`/`Item`) | Stock tracked through ERPNext batches. |
| MEDICAMENT | **Medicament** (+ ERPNext `Item`) | `delai_attente_lait` drives milk-withdrawal. |
| TRAITEMENT | **Traitement** | `type_traitement = TRAITEMENT_MEDICAL\|PARAGE`. |
| TRAITEMENT_MEDICALE | **Traitement Medicale** (child, `istable=1`) | dose + route + withdrawal end date. |
| ALIMENT | **Aliment** (+ ERPNext `Item`) | `type_aliment = CONCENTRE\|FOURRAGE\|MINERAL\|ENSILAGE\|PAILLE\|SUPPLEMENT`. |
| RATION | **Ration** | Immutable after first save; intentionally **not** an ERPNext BOM. |
| COMPOSITION_RATION | **Composition Ration** (child, `istable=1`) | aliment × quantite; `sous_total` auto. |

## 2. Spec entities delegated to ERPNext core (do NOT build custom)

| Spec entity | ERPNext realization | How HMD uses it |
|---|---|---|
| PRODUIT | **Item** (+ Item Group) | `Medicament`/`Aliment`/`Semence` link to an `Item`. `type_produit` ≈ Item Group. |
| STOCK | **Bin** (Item × Warehouse) | `quantite_actuelle = Bin.actual_qty`; CMP = `valuation_rate`. Per-lot warehouses. |
| MOVEMENT_STOCK | **Stock Entry** (Material Issue/Receipt) + Stock Ledger | Posted by `utils/stock_utils.py` for medicament/semence/aliment consumption. |
| INVENTAIRE | **Stock Reconciliation** | Physical count / écart correction. |
| UTILISATEUR | **User + Role + Role Permission Manager** | Spec roles (MANAGER, PROPRIETAIRE, VETERINAIRE…) map to Frappe Roles, not a custom table. |

→ Details and code entry points in `erpnext-integration.md`.

## 3. Spec entities NOT built yet (greenfield — confirm scope before building)

These belong to later EPICs. ERPNext has native modules for all of them; prefer
**configuring ERPNext** over inventing custom DocTypes.

| Spec entity | Build using (preferred) | EPIC |
|---|---|---|
| EQUIPMENT | ERPNext **Asset** (+ Asset Category) | 7 — Infrastructures |
| INTERVENTION | ERPNext **Asset Maintenance** / **Maintenance Visit** | 7 |
| DEPENSE | ERPNext **Purchase Invoice / Journal Entry / Expense Claim** | Finance |
| VENTE | ERPNext **Selling** (Sales Invoice / Delivery Note) — lait, animaux, fumier | 8 / Finance |
| Pâturages (EPIC 6) | `frappe/agriculture` app (Land Unit, Crop Cycle) | 6 — future |

If asked to "add equipment/sales/expense tracking", scope it as ERPNext
configuration + a few Custom Fields, not a new dairy DocType — that was the whole
reason ERPNext was chosen over closed dairy SaaS.

## 4. Implementation-only DocTypes (no direct spec entity)

These exist in code but not as spec entities — they implement behavior the spec
described as rules/automation, or add operational tooling:

| DocType | Role |
|---|---|
| **Alerte** | Realizes the spec "module Alertes" — rows generated daily by `alerte.generate_alerts`. `type_alerte` ∈ CHALEUR_GENISSE, CHALEUR_POST_VELAGE, VERIFICATION_J21, VERIFICATION_J50, TARISSEMENT, VELAGE_IMMINENT, DELVO. |
| **Avortement** | Abortion event (resets gestation). `cause ∈ INCONNUE\|MALADIE\|ACCIDENT\|STRESS\|ALIMENTATION\|AUTRE`. |
| **HMD Configuration** | `issingle=1`. The 37-field tunables store (thresholds, DIM windows, PFE seuils). |
| **Etat Corporel** | Body-condition score (BCS), 1→5 by 0.5. |
| **Note Mobilite** | Locomotion/lameness score, 1→5 by 0.5 (operationalizes "boiterie"; complements PARAGE foot-scores). |
| **Mere Externe** | External dam for purchased animals with unknown pedigree (`Animal.id_mere_externe`). |
| **Lot Ration History** | Episode log `[date_debut, date_fin)` of which Ration a Lot ran (drives feed distribution & reports). |
| **Allotement History** | Audit of animal lot moves; `lot_on_date(animal, date)` resolves a cow's lot on any past date. |
| **Allotment Session / Allotment Session Row** | Snapshot of a (weekly) lot-reallocation decision with per-cow DIM/production metrics + engine suggestion. |
| **Bilan Lait Journalier** | Daily herd TB/TP + total production; `on_update` fans the daily rates out to that day's Traite rows. |
| **Snapshot Journalier** | Daily frozen operational snapshot (`frozen` flag). |
| **Rapport Journalier Importe** | Container for daily reports imported from an external milking system (e.g. LELY); parsed by `utils/import_rapport.py`. |

## 5. Folded spec entities (no separate DocType)

| Spec entity | Folded into |
|---|---|
| **PARAGE** | `Traitement` with `type_traitement = PARAGE` and foot-score fields `note_pied_ag / note_pied_ad / note_pied_arg / note_pied_ard` (Select 1→5 by 0.5). There is **no** `Parage` DocType. |
| **PRODUCTION_LAITIERE** | Not stored. Computed via `utils/live_state.py` + `Bilan Lait Journalier` + the reports. |

---

**Rule of thumb:** if a spec entity is about **stock, items, purchases, sales,
assets, or users**, it's ERPNext core — extend with Custom Fields. If it's about
**cattle, lactation, reproduction, rations, treatments, lots, alerts**, it's a
custom HMD DocType. When unsure, grep `hmd_agro/hmd_agro/doctype/` and check this
table before creating anything.
