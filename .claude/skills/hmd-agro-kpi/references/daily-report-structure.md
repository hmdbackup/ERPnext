# The Daily/Monthly Bilan — "Rapport Journalier de l'élevage"

The farm's Excel **"dispositif"** is the spec for the app's herd report. Title row:
**"Rapport Journalier de l'élevage (HMD Agro S.A.)"**, one block per day. The app's
`Rapport Mensuel` report + the daily operational views must reproduce these column
groups. Each group below is paired with **where the data comes from in the app**.

> The live data is fictitious — real client/aliment names (STIAL, Délice,
> Soprolait, "7 Expert", "Machia Starter") appear here only as faithful examples.

## 1. Évolution de l'effectif / catégorie

Rows: `Effectif Initial` → `Changement de Catégorie` → `Vêlage` → `Naissance` →
`Avortement / Mort-né` → `Vente` → `Mortalité` → `Effectif Final`. Columns by
category: **Vaches** (Lactante, Tarie), **Génisses** (Vide, Pleine), **Mâles**
(Veaux, Engraissement), **Femelles** (Veaux Femelles), **Total** (e.g. 173 têtes).

→ **App:** `utils/live_state.py` — `effectif_on_date` (Effectif Initial/Final),
`count_velages`, `count_naissances`, `count_avortements_mort_nes`, `count_exits`
(Vente/Mortalité/Réforme), `count_changements_cat`. **Reconstructed from events**,
never from live `Animal.etat_*`. Rapport Mensuel exposes this as the **Effectif**
section with `effectif_mode = Jour | Mois`.

## 2. Alimentation & Allaitement

A per-aliment table: each feed (e.g. `7 Expert`, `Machia Genisse`, `Machia
Starter`, `Soja`, `Maïs`, `Drêche de brasserie`, `Ensilage`, `Foin Avoine`, `Foin
de Luzerne`, `Paille`, `Bicarbonate de sodium`…) with **Prix Unitaire (DT)** ×
quantity distributed per category → **Total**.

→ **App:** `Aliment` (prix_unitaire) × `Ration` / `Composition Ration` × population
per lot/day, posted as ERPNext Material Issues by
`utils/feed_distribution.py`. Rapport Mensuel **Alimentation** section
(`granularite = Quotidien | Quinzaine`).

## 3. Production

`Lait Commercialisé` (per client: **STIAL**, **Ben Youssef**, …), `Perte`,
`Auto-consommation`, `Stock Initial`, `Stock Final`, `Production`. Plus **"moyenne
salle de traite"** and per-milking values (the Excel uses three milkings
**05H / 13H / 21H**).

→ **App:** `Traite` records aggregated by date/lot.
> **Delta:** the Excel has **3 milkings** (matin/midi/soir); the app models
> `Traite.session = MATIN | SOIR` only. When reproducing the report, map the third
> milking accordingly (or treat midi as merged) — don't assume three sessions exist
> in the data model. Daily TB/TP come from `Bilan Lait Journalier`.

## 4. Frais et coût

Per category (Vaches Lactantes, Taries, Génisses Vides/Pleines, Veaux,
Engraissement, Veaux Femelles, Total): `Frais du Concentré`, `Frais de Fourrage`,
`Frais Alimentaires`, `Main d'œuvre`, `Traction`, `Total Alim+MO+TRACT`,
`Total Frais`.

→ **App:** feed cost from Aliment prix × distribution; MO/Traction are
operational inputs. `utils/report_format.py` normalizes precision.

## 5. Indicateurs des vaches  *(the KPI block)*

Columns: **Total Concentré (Kg)** · **Concentré/Tête (Kg)** · **Concentré de
Prod/VL** · **Moyenne de Production (L/Tête)** · **L/C (L/Kg)** · **C/L (Kg/L)** ·
**Efficacité Alimentaire (L/kg MS)** — computed in **two rows**: **Vache Présente**
and **Vache Lactante**.

Sample day (illustrative): *Présente* → conc/tête 8.994, moyenne 16.069 L, L/C
1.787, C/L 0.560, eff. 1.032 ; *Lactante* → conc/tête 9.578, conc prod/VL 7.494,
moyenne 18.416 L, L/C 1.923, C/L 0.520, eff. 1.484.

→ **App:** formulas in `references/kpi-formulas.md`; coloring from PFE seuils;
number-card snippets in `utils/dashboard_kpis.py`. Rapport Mensuel **Indicateurs**
section (green/orange/red).

## 6. Production & Moyennes par lot (Contrôle Laitier)

Per lot (Lot 1, Lot 2, …, Infirmerie, Autres): **Effectif** and **Moyenne/lot
(L/tête)**. (Remember: lot **numbers** are ambiguous across docs — see
hmd-agro-domain / lots-allotement.)

→ **App:** `Controle Laitier` report + `live_state.lactantes_per_lot_on_date`
(+ `lot_on_date` for historical lot membership). Rapport Mensuel **Production par
Lot** (`periode = Jour | Hebdomadaire`).

## 7. Ration par lot (MS%)

Each aliment with its **MS%** distributed to **Lot 1:FV, Lot 2:THP, lot 3:HP, Lot
4, Lot 5**; computes **MS Total Distribué**, **MS Distribué/Tête**, **Refus
Brut / MS Refus**, and **Efficacité alimentaire (L/kg MS)** per lot. (Recall MSI =
MS distribuée − refus.)

→ **App:** `Lot Ration History` episodes + `Composition Ration` (with aliment MS%),
population per lot, minus refus. This is the per-lot efficacité source.

## 8. CA, compteur & ambiance

- **Chiffre d'affaires:** Lait, Vente Vache/veaux, Fumier (→ ERPNext Selling when built).
- **Compteur salle de traite** (milking-parlor meter readings).
- **Température / Humidité extérieur** (T °C, H %, **THI**) with comfort bands
  (Zone de confort / Stress thermique modéré / modéré→sévère / sévère). THI formula
  in `kpi-formulas.md`.

## Companion: reproduction sheets

The dispositif also has per-cow and per-génisse reproduction tables tracking
**IA1…IAF**, taureau (indices Izu/Lait), N° lactation, jour de lactation, and the
computed **Intervalle V/IA1, V/IAF, V/V (IVV), Indice coïtal**.

→ **App:** `Rapport Reproduction` report (built from `Insemination` / `Velage` /
`Lactation`); formulas/targets in `kpi-formulas.md`.

---

**When reproducing the bilan:** drive effectif from `live_state` (not live fields),
feed/cost from Ration×distribution, production from Traite, indicators from the
two-population formulas, and color from PFE seuils. Keep the **présente vs
lactante** split visible in every per-cow indicator row.
