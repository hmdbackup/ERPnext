# KPI Formulas, Targets & Sources

Every indicator with its **exact formula**, **objectif/target**, and **source**.
Sources: the founding PFE study (Nasrallah M. A., INAT, 2024, on HMD AGRO — 91
Montbéliarde, 2023) and the Excel "dispositif". Targets in the reproduction tables
are from **Vallet & Paccard (1984)**. Thresholds that the app uses to **color**
indicators come from `HMD Configuration` `pfe_*` fields (see the table at the end).

> Notation: `Ta` = ambient temp (°C), `HR` = relative humidity (0–1), DIM =
> days-in-milk, MSI = matière sèche ingérée, MS = matière sèche.

## Production

| Indicator | Formula | Target / note |
|---|---|---|
| **Production / vache présente** | Σ lait du troupeau ÷ **nb moyen de vaches présentes** (lactantes + taries) | herd-economics denominator |
| **Production / vache lactante** | Σ lait ÷ **nb de vaches lactantes** | performance denominator |
| **Moyenne L/tête (par lot)** | Σ traites du lot ÷ effectif lactant du lot | daily, per lot |
| **Pic de production** | MAX(production journalière) sur les premiers `pic_production_jours` (150) DIM | 4–6 semaines post-vêlage |
| **Production initiale** | Σ traites sur les premiers `production_initiale_jours` (60) DIM | |
| **Lactation 305 j (P305)** | `>305j`: `Y305 = Y_actuel × 305 / D` (D = durée). `<305j`: régression `Y305 = β0 + Σ βi·Xi` | durée standard fixée à **305 j** |
| **Rendement lactation (Fleischmann)** | `PLT = D1·X1 + Σ ((X(i-1)+Xi)/2)·Δjours + Dn·Xn` (Di = intervalles entre contrôles laitiers, Xi = lait au contrôle) | méthode de référence |
| **Persistance** | `cumul lait (100→200 j) / cumul lait (0→100 j)` | optimal **0.85–0.95** (config) |
| **Durée de tarissement** | date vêlage − date tarissement | idéal **~60 j**; min 40 j; >100 j pénalise la lactation suivante |

## Feed-economic (alimentation)

| Indicator | Formula | Target |
|---|---|---|
| **L/C** (lait / concentré) | Σ lait ÷ Σ concentré consommé (kg) | **optimal 2.0–2.4** (1 kg concentré → 2–2.4 kg lait) |
| **C/L** (concentré / lait) | inverse de L/C (kg/L) | — |
| **Efficacité alimentaire** | `lait ÷ MSI` (kg lait / kg MS ingérée), avec **MSI = MS distribuée − refus** | **optimal 1.4** L/kg MS (Castellani 2014) |
| **Concentré / tête** | Σ concentré ÷ effectif (présente ou lactante) | reported both ways |
| **Concentré de production / VL** | concentré de production ÷ nb vaches lactantes | |

### Cost rows (per category + Total, computed DT/L and DT/vache)

`frais_X = prix_unitaire × quantité distribuée` per category; then divide by litres
(DT/L) or by effectif (DT/vache):

- **Coût du concentré** DT/L, DT/vache
- **Coût du fourrage** DT/L, DT/vache
- **Coût alimentaire** (concentré + fourrage) DT/L, DT/vache
- **Coût (Alim + Main d'œuvre + Traction)** DT/L, DT/vache
- **Coût total (amortissement exclus)** DT/L, DT/vache
- **Marge** = `prix de vente du lait (DT/L) − coût total (DT/L)`. *Worked example:
  prix 1.9 DT/L → gain ≈ 0.361 DT/L ("gestion efficace des coûts").*

## Qualité du lait

- **TB** (taux butyreux, %) and **TP** (taux protéique, %) — entered/averaged per day
  in `Bilan Lait Journalier` (`taux_tb_moyen`, `taux_tp_moyen`), validated
  `≤ taux_tb_max_pct` / `taux_tp_max_pct` (config, default 10). `Bilan.on_update`
  fans the daily rates out to that day's Traite rows. The PFE study gives **no
  formula/target** for TB/TP beyond herd averages.

## Reproduction — fertilité (with targets, Vallet & Paccard 1984)

| Indicator | Formula | Objectif |
|---|---|---|
| **TR1IA** (réussite 1ʳᵉ IA) | `(nb IA1 fécondantes / nb total IA1) × 100` | **> 60 %** |
| **%3IA+** | `(nb vaches nécessitant ≥3 IA pour concevoir / nb vaches inséminées) × 100` | **< 15 %** (≥15 % = problème sérieux) |
| **Indice coïtal (IC)** | `nb total d'inséminations / nb de gestations confirmées` (ratio) | **≤ 1.6** |
| **Taux de conception** | `nb vaches gestantes / nb vaches inséminées` | — |
| **IA fécondante** (nb IA) | nb d'IA jusqu'à fécondation | **< 1.6** |

> An IA is **"fécondante"** if no return-to-heat within ~2 months. *IC is a ratio
> (~1.5–1.6), not a percentage — disregard any "×100" in the source text for IC.*

## Reproduction — fécondité (intervalles, with targets)

| Indicator | Formula | Objectif |
|---|---|---|
| **IVIA1** (intervalle vêlage → 1ʳᵉ IA) | `date 1ʳᵉ IA − date vêlage` | **70 j**; % vaches >80 j doit être **<15 %** |
| **IVIF** (vêlage → IA fécondante) | `date IA fécondante − date vêlage` | **90 j**; % vaches >110 j **<15 %** |
| **IVV** (vêlage → vêlage) | `date dernier vêlage − date vêlage précédent` | **365 j** |
| **Âge au 1ᵉʳ vêlage (I1V)** | `date premier vêlage − date naissance` | **~24 mois** |
| **Taux de réforme** | `(nb vaches réformées / nb moyen vaches présentes) × 100` | **20–30 %** |

## Croissance

- **GMQ** (gain moyen quotidien) = `(poids_kg − poids_kg précédent) / jours entre pesées`
  (from `Pesee`; RC-PES-02).

## Environnement — stress thermique

- **THI** = `1.8 · Ta − (1 − HR) · (Ta − 14.3) + 32` (Johnson 1962; Bouraoui 2002).
- Bands: **confort** < 72 ; **stress modéré 72–79** ; **modéré→sévère** / **sévère**
  above. Drives the dispositif's Température/Humidité block.

## PFE seuils → coloring (config)

The reports color indicators green/orange/red from these `HMD Configuration` fields
(read via `get_config`; the DIM-window subset is also in `frappe.boot.hmd_config`):

| Indicator | green | red alarm | config fields |
|---|---|---|---|
| L/C | 2.0–2.4 | <1.5 or >3.0 | `pfe_lc_optimal_min/max`, `pfe_lc_alarm_min/max` |
| Efficacité | ≥1.4 (orange ≥1.0) | <1.0 | `pfe_efficacite_min`, `pfe_efficacite_orange_min` |
| Persistance | 0.85–0.95 | <0.7 or >1.10 | `pfe_persistance_min/max`, `pfe_persistance_alarm_min/max` |
| %3IA+ | ≤15 (orange ≤25) | >25 | `pfe_3ia_plus_max`, `pfe_3ia_plus_orange_max` |

## Implementation pointers

- Number-card datasources: `utils/dashboard_kpis.py` (`get_pl_vl` = production lait /
  vache lactante; `get_lc_ratio` = L/C — yesterday's values).
- Effectif / per-lot counts: `utils/live_state.py` (reconstruction — never live fields).
- Rounding/format: `utils/report_format.py`.
- The reports that surface these: see `reports-and-cards.md`.

## Reference values (HMD AGRO 2023, for sanity-checking)

Production / vache présente **5 873 L/an**, / lactante **7 383 L/an**, globale
**516 839 L/an**, CA lait **893 615,634 TND**. IVIF moyen **152,67 j** (vs cible 90 —
problème de fertilité). %3IA+ **38,63 %** (vs <15). Indice coïtal génisses **1,52**
(favorable). Use these only as order-of-magnitude checks; the live data is fictitious.
