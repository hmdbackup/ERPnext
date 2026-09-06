# Business Rules (Règles de Gestion) — Authoritative List

Source of the rule statements: the Dossier de Spécification. **The French text is
canonical** (quote it when citing a rule). The English notes record **how/where
it is implemented** and flag **code-vs-spec deltas** — because the implementation
diverged in several places. When a delta exists, the **code wins**.

## Code-vs-spec deltas (scan this first)

| # | Spec says | Code does | Where |
|---|---|---|---|
| RG06 | lactation close status = `TERMINEE` | status = **`TARIE`** | `Lactation.statut` |
| RG09 | sessions `MATIN/MIDI/SOIR` | sessions **`MATIN/SOIR`** only; unique `(animal,date,session)` | `Traite.session`, autoname |
| RG12/IA | `type_semence` `SEXEE_FEMELLE/SEXEE_MALE` | **`CONVENTIONNELLE/SEXEE`** | `Insemination.type_semence` |
| RG14 | semence "indisponible" at qty 0 | ERPNext v15 **blocks batch-negative stock**; depleted batch → IA save warns, stock write skipped | `insemination.py` |
| RG21/RG22 | custom Stock/Inventaire refusal & correction | **ERPNext** Stock Ledger validation + Stock Reconciliation | `stock_utils.py` |
| RG23/RG27 | equipment maintenance + alert | **not built** → ERPNext Asset Maintenance when scoped | — |
| RG24 | vente sets statut VENDU + date_sortie | `Animal.statut` supports it; a **Vente DocType is not built** (use ERPNext Selling) | `Animal` |
| PARAGE | separate entity | **folded** into `Traitement` (type=PARAGE, foot scores) | `traitement.py` |

## Module: Gestion du cheptel

- **RG01** — *Une VELLE devient automatiquement GENISSE lorsque son âge atteint 12 mois.*
  → age = today − `date_naissance` (config could gate; transition driven by category logic).
- **RG02** — *Un VEAU devient automatiquement TAURILLON lorsque son âge atteint 12 mois.*
- **RG03** — *Une GENISSE devient automatiquement VACHE après l'enregistrement de son premier vêlage.*
  → done in `Velage.update_mother` (also RG16); sets `date_premier_velage`.
- **RG04** — *Lors de la sortie d'un animal (vente, mort, réforme), toute lactation active est clôturée avec le statut INTERROMPUE.*
  → `Animal.on_update` exit cascade; also fails pending IA and closes open alerts.

## Module: Lactation

- **RG05** — *Une vache ne peut avoir qu'une seule lactation EN_COURS à un instant donné.*
  → enforced in `Lactation.validate`.
- **RG06** — *Le tarissement d'une vache entraîne la clôture de la lactation (statut = TERMINEE).*
  → **DELTA:** code closes to **`TARIE`** (not `TERMINEE`); auto-fills `date_tarissement`.
- **RG07** — *L'enregistrement d'un vêlage déclenche la création d'une nouvelle lactation EN_COURS.*
  → `Velage.after_insert → create_lactation` (auto-closes any prior `EN_COURS` as `TARIE` first).

## Module: Traite

- **RG08** — *Une traite ne peut être enregistrée que si la lactation associée est EN_COURS.*
  → `Traite.validate` (CF-TRA-01); also requires animal present on `date_traite`.
- **RG09** — *Une seule traite par session (MATIN/MIDI/SOIR) est autorisée par lactation et par jour.*
  → **DELTA:** sessions are **`MATIN/SOIR`**; uniqueness enforced via autoname
  `TRA-{animal}-{date_traite}-{session}` (CF-TRA-03).

## Module: Reproduction / Insémination

- **RG10** — *Une vache doit avoir une lactation EN_COURS pour être inséminée.* (CF-IA-01)
- **RG11** — *Une génisse peut être inséminée sans lactation associée.* (CF-IA-02)
- **RG12** — *Une insémination déclarée RÉUSSIE met automatiquement l'animal à l'état GESTANTE.*
  → `Insemination.update_animal_on_resultat`; also sets `date_velage_prevue = date_ia + periode_velage_jours` (280) and `date_tarissement = date_velage_prevue − tarissement_window_jours` (60).
- **RG13** — *L'enregistrement d'une IA déclenche une sortie de stock (1 dose de semence).*
  → `decrement_semence_stock` posts Material Issue −1 paillette (FIFO batch).
- **RG14** — *Si le stock de semence atteint zéro, la semence devient automatiquement indisponible.*
  → **DELTA — already realized; do NOT add a custom `disponible` boolean or a new
  guard.** This rule is satisfied by the stock layer, not a flag on Semence:
  ERPNext v15 blocks **batch-level** negative stock regardless of
  `Item.allow_negative_stock`, so a depleted semence batch is **refused** — the IA
  still saves but the Material Issue is **skipped** with a red alert telling the
  user to post a Purchase Receipt first (`insemination.py`
  `decrement_semence_stock` / `_pick_semence_batch`). When asked to "implement
  RG14", **describe this existing v15 mechanism** (and only add a pre-save
  `validate` guard if the user explicitly wants to block the IA *before* it saves).
  Full detail: **hmd-agro-dev → `references/erpnext-integration.md`**.
- **RG15** — *Après un vêlage, l'état de gestation de la mère est remis à VIDE.* → `Velage.update_mother`.
- **RG16** — *Si la mère était une GENISSE, sa catégorie devient automatiquement VACHE.* → `Velage.update_mother`.
- **RG17** — *L'enregistrement d'un vêlage crée automatiquement un animal pour chaque veau né.*
  → `Velage.after_insert → create_calves` (categorie VEAU/VELLE from sexe, race from mother, `id_lot` Individuel).
- **RG18** — *Si le poids du veau est renseigné, une pesée de type NAISSANCE est créée automatiquement.*
  → inside `create_calves` when `poids_veauN` set.

> Note: the spec files RG15–RG18 under "reproduction" though they fire on **Vêlage**.
> An **Avortement** also resets gestation to `VIDE` but does **not** promote GENISSE→VACHE.

## Module: Santé animale

- **RG19** — *Un animal doit être actif pour recevoir un traitement médical.* → `Traitement.validate` (CF-TRT-01).
- **RG20** — *L'enregistrement d'un traitement médical déclenche une sortie de stock (médicament utilisé).*
  → `decrement_medicament_stock` (Material Issue per child row, by `qty_consumed`).
  → Milk-withdrawal: `date_fin_attente_lait = date_traitement + Medicament.delai_attente_lait` (RC-TMD-01, CF-TMD-03).

## Module: Gestion des stocks  *(ERPNext core — not custom)*

- **RG21** — *Une sortie de stock est refusée si la quantité demandée est supérieure à la quantité disponible.*
  → ERPNext Stock Ledger validation. Note HMD sets `Item.allow_negative_stock=1` for medicament/aliment so real events still record; semence batches are the exception (RG14).
- **RG22** — *La validation d'un inventaire avec écart crée automatiquement un mouvement de correction.*
  → ERPNext **Stock Reconciliation** (no custom Inventaire DocType).

## Module: Équipement  *(NOT built)*

- **RG23** — *Une intervention de maintenance met à jour la date de dernière maintenance de l'équipement.*
- **RG27** — *Une alerte est générée avant une échéance de maintenance équipement selon le délai paramétrable.*
  → both belong to EPIC 7; implement with **ERPNext Asset / Asset Maintenance** when scoped, not a custom DocType.

## Module: Ventes  *(partial)*

- **RG24** — *La vente d'un animal met son statut à VENDU et enregistre sa date de sortie.*
  → `Animal.statut = VENDU` + `date_sortie` is supported and triggers the exit cascade (RG04). A dedicated **Vente** DocType is not built — use ERPNext **Selling** (Sales Invoice / Delivery Note) for lait/animaux/fumier.

## Module: Alertes (seuils paramétrables)

- **RG25** — *Une alerte est générée pour tout événement critique lié à un animal (vêlage prévu, délai d'attente lait). Les seuils sont paramétrables.*
  → `alerte.generate_alerts` (daily) → types `VELAGE_IMMINENT`, `TARISSEMENT`, `VERIFICATION_J21/J50`, `CHALEUR_*`, `DELVO`. Each lifecycle event closes the alerts it resolves.
- **RG26** — *Une alerte est générée lorsque la quantité en stock atteint le seuil critique paramétrable.*
  → ERPNext reorder (`reorder_sync` mirrors `reorder_level` → `Item.reorder_levels`; native Material Request).

---

## Functional constraints (CF) & calc rules (RC) — condensed

These come from the spec's data dictionary; treat as the **intent** behind the
controllers. Verify exact field names/options from the DocType JSON.

**Animal** — CF-ANI-01/02: `sexe` derived from `categorie` (F: VACHE/GENISSE/VELLE;
M: VEAU/TAURILLON). CF-ANI-03: born on-farm (`est_achat=0`) ⇒ `id_mere` required.
CF-ANI-04: non-`ACTIF` animal can't be traité/inséminé/trait. RC-ANI-01:
`age = today − date_naissance`. RC-ANI-02: `date_premier_velage = MIN(Velage.date_velage)`.

**Lactation** — CF-LAC-01: closed lactation accepts no traite. CF-LAC-02: animal must
be F and VACHE/GENISSE. RC-LAC-01: `jours_lactation = (date_fin or today) − date_debut`.
RC-LAC-02: `production_totale = Σ Traite.quantite_litres`. RC-LAC-04:
`pic_production = MAX(daily total)` within the first `pic_production_jours` (150).
`production_initiale = Σ` first `production_initiale_jours` (60); `lactation_305j = Σ` first 305 DIM.

**Traite** — CF-TRA-01: lactation `EN_COURS`. CF-TRA-02: `date_traite` within lactation.
CF-TRA-03: unique `(lactation/animal, date, session)`. `quantite_litres ≤ traite_max_litres` (60);
`taux_tb ≤ taux_tb_max_pct`, `taux_tp ≤ taux_tp_max_pct` (10).

**Insemination** — CF-IA-01: VACHE ⇒ `lactation` required. CF-IA-02: GENISSE ⇒ no lactation.
CF-IA-03: linked lactation must be `EN_COURS`. CF-IA-05: `resultat=EN_ATTENTE` default.
RC-IA-01: `numero_ia = count(prior IA in lactation/animal) + 1`. RC-IA-02: `date_velage_prevue = date_ia + 280`.

**Velage** — CF-VEL-01: mère F + GENISSE/VACHE. CF-VEL-02: mère `GESTANTE`. CF-VEL-03:
if `id_ia_fecondante` set, that IA must be `REUSSIE`. CF-VEL-05: single birth ⇒ veau2 fields NULL.
(Implementation also validates ≥250 days between IA and birth.)

**Traitement / Médical** — CF-TRT-01: animal `ACTIF`. CF-TRT-02: a Traitement is exactly
one of TRAITEMENT_MEDICAL (child `Traitement Medicale`) **xor** PARAGE (foot scores).
CF-TMD-03: while `date_fin_attente_lait > today`, milk non-collectible. RC-TMD-01:
`date_fin_attente_lait = date_traitement + delai_attente_lait`.

**Ration** — CF-RAT-01: inactive ration can't be assigned to a Lot. RC-RAT-01:
`cout_estime = Σ(composition.quantite × aliment.prix_unitaire)`. Ration is **immutable** after
first save (name + composition frozen).

**Lot** — CF-LOT-01: `nb_animaux ≤ capacite_maximale`. RC-LOT-01:
`nb_animaux = count(Animal where id_lot = this and statut = ACTIF)`.

**Pesee** — RC-PES-01: `age_jours = date_pesee − date_naissance`. RC-PES-02:
`gain_quotidien_moyen (GMQ) = (poids − poids_précédent) / jours_entre_pesées`.
