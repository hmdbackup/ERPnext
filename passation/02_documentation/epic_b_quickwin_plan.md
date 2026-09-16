# EPIC B — Quick win « coût/litre réel » · plan prêt-à-exécuter

> Couvre **FIN-S10 → FIN-S12**. Objectif : faire passer le coût des consommations
> de **0** à la **valeur réelle (CMP)**, pour que le **DT/L déjà calculé**
> (`rapport_periodique.py:1293`) affiche un vrai chiffre — puis ajouter le **DT/vache**.
> C'est le meilleur retour sur effort de tout le chantier finance : la mécanique
> de coûts est déjà câblée, on ne fait que la brancher sur de vrais prix.

## Pré-requis (avant de toucher au code)
- Dev container qui tourne (`setup_guide` partie A) → `http://hmd.localhost:8000`.
- Idéalement le backup BD (données réelles) ; sinon les **données de démo suffisent**
  pour valider la mécanique.
- Branche dédiée : `git checkout -b epic-b-valorisation` (jamais sur `main`).

---

## Étape 1 — Poser de vrais prix → `valuation_rate` (FIN-S10)
*Dépendance côté code : aucune.*

Deux voies, même effet (`Bin.valuation_rate` devient non nul) :
- **Démo / test** : lancer `hmd_agro/hmd_agro/setup/seed_demo_prices.py` — il poste des
  **Material Receipts** à prix réels (Médicament, Aliment, Semence).
- **Réel / prod** : saisir des **Purchase Invoice / Receipt** sur les Items
  (`ALI-` / `MED-` / `SEM-`). C'est la voie de production (boucle d'achat).

**Vérifier** : `hmd_agro/hmd_agro/setup/verify_native_valuation.py` confirme
`Bin.valuation_rate ≠ 0` et la cohérence des Stock Ledger Entry.

---

## Étape 2 — Valoriser les sorties au CMP (FIN-S11) · *le cœur*
**Fichier :** `hmd_agro/hmd_agro/utils/stock_utils.py` → `create_stock_movement()`
(**lignes ~108-109**).

Aujourd'hui chaque ligne force `basic_rate=0` + `allow_zero_valuation_rate=1`
⇒ `stock_value_difference = 0` (commentaire dans le code : *« cost not tracked
yet — Phase B »*).

**Changement visé :**
- Pour un **Material Issue** (consommation : ration, traitement, IA) : **ne plus
  forcer** `basic_rate=0` ni `allow_zero_valuation_rate=1` → ERPNext valorise
  automatiquement la sortie au `valuation_rate` (CMP) de l'article.
- Pour un **Material Receipt** : le taux vient de l'achat (Purchase). Pour les
  receipts de **restauration** (`restore_*_stock` sur `on_trash`), **garder la
  symétrie de valeur** avec l'issue d'origine (ne pas restaurer à 0 si l'issue
  valait X).

**Approche sûre (recommandée), pour ne rien casser (CF-FIN-31) :**
1. **Conditionner** par `purpose` (issue vs receipt) plutôt qu'un retrait global
   des flags.
2. **Garde-fou** : si `valuation_rate` est encore 0 (article jamais acheté),
   retomber sur l'ancien comportement → la saisie terrain n'est jamais bloquée.
3. Préserver intacts le **refus batch v15** (semence) et `allow_negative_stock`
   (aliment/médicament).

**⚠️ À confirmer sur l'instance** (comportement exact ERPNext v15, à tester, pas à
supposer) :
- qu'une Material Issue **sans** `basic_rate` prend bien le CMP du Bin ;
- que la suppression (`on_trash`) restaure la bonne valeur ;
- que `test_semence_dual_write.py` reste **vert**.

---

## Étape 3 — Faire remonter le coût dans le rapport (FIN-S12)
**Fichier :** `hmd_agro/hmd_agro/report/rapport_periodique/rapport_periodique.py`
(section coût ~ligne 748 ; indicateurs ~ligne 1293).

- Après Étapes 1+2, une nouvelle consommation produit `stock_value_difference ≠ 0`
  → le **DT/L** existant (`:1293`) affiche une **vraie** valeur, **sans nouveau
  calcul**.
- **Ajouter le DT/vache** à côté du DT/L : même numérateur (coût), dénominateur =
  **effectif** (par vache *présente* **et** *lactante*) via `utils/live_state.py`
  (`effectif_on_date` / reconstruction — jamais les champs live). Suivre le pattern
  « deux populations » des autres KPI.

---

## Tests (obligatoire — consigne du boss : ne jamais livrer du demi-fini)
- Unit test type `test_cost_flow.py` : achat (receipt) → consommation (issue) →
  `stock_value_difference` attendu ; suppression → restauration **symétrique**.
- `test_semence_dual_write.py` doit rester vert (FIFO + refus batch).
- Validation manuelle UI : un jour de ration → comparer le coût affiché à un calcul
  à la main.

## Livraison
- Commits au format référençant les stories : `FIN-S10/S11/S12 — valorisation réelle
  des consommations + DT/vache`.
- PR vers `main` **après CI verte + validation Samir**. Jamais de push direct.

---

### Règles maison à respecter (rappel)
`ne rien hardcoder` (prix via Item Price / achat, pas de littéral) · `on_trash`
symétrique · jobs idempotents · indentation Python **4 espaces** · vocabulaire
**français** · codes `RG-FIN- / CF-FIN- / RC-FIN-`. Fixtures pour tout Custom
Field, patch idempotent pour tout seuil `HMD Configuration`.
