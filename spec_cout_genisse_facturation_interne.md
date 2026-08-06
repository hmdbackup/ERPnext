# Spécification — Coût de revient génisse & facturation interne du lait

> Phase 3 métier — EPIC I « Atelier Génisses ». Design d'abord, code ensuite.
> Source : réunion du 05/08/2026 (09:00–15:00, points 5–6 de la liste de Samir).
> Statut : **proposition à valider** avant implémentation.

---

## 1. Objectif métier et question de décision

Le lait donné aux veaux/génisses (`lait_veau` du Bilan Lait Journalier) est
aujourd'hui un volume connu mais **jamais chiffré** : l'atelier lait « offre »
du lait à l'atelier génisses sans que ça n'apparaisse nulle part. De même, la
valorisation du cheptel repose sur un **forfait de 2 500 TND** par génisse
élevée (`cheptel_cout_elevage`), estimé une fois par an à la main.

L'outil doit répondre à deux questions :

1. **Combien coûte réellement une génisse** de sa naissance à son entrée en
   production (~18–22 mois, parfois 3 ans une mauvaise année) — lait bu,
   ration, mécanique de sa zone, quote-part main-d'œuvre ?
2. **Vaut-il mieux vendre la velle à 3 mois ou l'élever jusqu'à 18 mois ?**
   Si l'élevage détruit de la valeur, il faut le voir chiffré, par cohorte.

Principe directeur (conforme à la règle spec→implémentation) : **tout est déjà
presque là**. Le Cost Center `Élevage - Génisses` existe (socle FIN-S02), les
Stock Entries de ration par lot existent (SCRUM-123), la ventilation Personnel
par atelier existe (FIN-S42), le prix du lait existe (grille FIN-S24). Il
manque : la **cession interne du lait**, la **cession interne des travaux
mécaniques**, le **rattachement lot→atelier**, et le **rapport** qui agrège.

---

## 2. Modèle proposé

### 2.1 Colonne vertébrale : le Cost Center « Élevage - Génisses »

Toutes les charges de l'atelier convergent vers le Cost Center existant
`Élevage - Génisses - <abbr>`. Le coût de revient se lit alors à deux niveaux :

- **niveau atelier** (exact, comptable) : `gl_sums`-like filtré par
  `cost_center` sur la période ;
- **niveau génisse** (analytique) : deux composantes individualisées (lait bu,
  ration du lot) + le reste mutualisé en **coût par génisse-jour**.

### 2.2 Valorisation du lait interne (« entre parenthèses »)

- **Volume** : `Bilan Lait Journalier.lait_veau`, agrégé au mois (le calcul
  qualité se fait déjà en fin de mois — cohérent avec la facture lait).
- **Prix de référence** : `facturation_lait.compute_milk_rate(tb, tp, date)`
  — **la même grille qualité que la facture de la centrale**, TB/TP moyens
  pondérés du mois. Justification : le lait bu par les veaux est du lait *non
  vendu* ; son vrai coût pour l'atelier lait est le **coût d'opportunité**
  (même posture que `ecart_lait`, FIN-S25 : une seule monnaie pour tout).
  Une config `lait_interne_prix_mode` (`PRIX_GRILLE` défaut / `PRIX_FIXE` avec
  `lait_interne_prix_fixe`) laisse la main à Samir s'il préfère un prix conventionnel.
- **Écriture** : pas de Sales Invoice (pas de tiers, pas de TVA) — un
  **Journal Entry interne mensuel**, pattern maison `charges_utils` :

  ```
  Débit  6061 « Lait d'allaitement (cession interne) »   CC Élevage - Génisses
  Crédit 7068 « Cessions internes de lait »              CC Lait
  ```

  Les deux comptes sont en résultat : au niveau ferme ils se neutralisent
  (les « valeurs entre parenthèses » demandées), mais la marge par atelier
  devient juste. Le compte crédit est **hors préfixe 701** pour ne pas gonfler
  `ca_lait` dans `finance_kpis.gl_sums` (numéros exacts à valider avec
  l'expert-comptable — question ouverte n°2).
- **Idempotence** : marqueur `LAIT_INTERNE_<periode>` dans `user_remark`,
  job mensuel `post_lait_interne` calqué sur `post_salaires` — rejouable.

### 2.3 Coût ration par lot : réutiliser les Stock Entries existants

`feed_distribution` poste déjà **un Material Issue par (lot, jour)** valorisé
au CMP, marqueur `RATION_DIST_<lot>_<date>`, champ `id_lot`. Rien à recréer :

- Ajouter un champ **`atelier`** (Link Cost Center) sur le DocType **Lot** :
  les lots jeunes (velles, génisses, taurillons) pointent vers
  `Élevage - Génisses`, les lots de production vers `Lait`.
- Renseigner ce Cost Center + la dimension analytique `Lot` (déjà déclarée par
  le socle) sur les lignes du Stock Entry, pour que le **Grand Livre** porte
  la charge d'aliment sur le bon atelier (aujourd'hui elle part sans imputation).
- Le coût ration individuel d'une génisse un jour J =
  `coût SE (lot_J, J) / effectif (lot_J, J)` — l'effectif par lot/jour est déjà
  reconstruit par `_populations_on_date` (Allotement History), même logique
  que le backfill.

### 2.4 Lait bu par génisse

Deux sources, réconciliées :

- **Réel agrégé** : `lait_veau` du BLJ — vrai volume, mais non individualisé.
- **Théorique individuel** : courbe d'allaitement config —
  `allaitement_litres_jour` (défaut **6,5 L/j**, la « ration théorique
  6–7 L/j » citée en réunion) × `allaitement_duree_jours` (défaut **90 j**).

Le coût individuel utilise la courbe théorique **normalisée sur le réel** :
`lait_bu(a, J) = lait_veau_J × théorique(a, J) / Σ théorique(animaux buveurs, J)`
(si aucun BLJ saisi ce jour, repli sur le théorique pur). Ainsi la somme
individuelle = le volume facturé en interne — pas de lait fantôme.

### 2.5 Quote-part mécanique : coût horaire équipement

La config `equipement_cout_horaire_defaut` (25 DT/h, réunion 05/08) existe déjà
mais rien ne la consomme. Proposition (« option 2, la plus simple » retenue en
réunion) :

- Custom Field **`cout_horaire`** (Float, DT/h) sur **Asset** — surcharge du
  défaut par équipement.
- Nouveau DocType **`Utilisation Equipement`** (léger) :
  `date_utilisation`, `equipement` (Link Asset), `duree_heures`,
  `atelier` (Link Cost Center), `id_lot` (Link Lot, optionnel),
  `cout_horaire_applique` (calculé, lecture seule), `cout_total` (calculé),
  `notes`.
- À la validation : Journal Entry de cession interne
  (`Débit 614x « Travaux mécaniques internes » CC utilisateur /
  Crédit 7068x « Cessions internes de travaux » CC Traction`) — les vraies
  charges du tracteur (amortissement, gasoil, 615 entretien) restent sur
  Traction, la cession refacture l'usage à 25 DT/h. Symétrie `on_trash` :
  annulation du JE.

### 2.6 Main-d'œuvre : déjà couverte par FIN-S42

`Personnel.repartition` ventile le coût employeur par atelier ; `post_salaires`
poste chaque mois 640/647 **par Cost Center**. L'ouvrier dédié génisses (cité
en réunion) = une fiche Personnel avec `atelier = Élevage - Génisses` (ou une
part en %). **Aucun développement** — juste de la saisie.

### 2.7 Santé

Les Traitements décrémentent le stock médicaments (RG20) ; la charge suivra le
même chemin lot→atelier que la ration (imputation Cost Center sur le mouvement)
— incluse dans le mutualisé au départ, individualisable plus tard.

---

## 3. Doctypes / rapports à créer ou étendre

| Objet | Type | Contenu (champs français) |
|---|---|---|
| `Lot` | **étendre** | + `atelier` (Link Cost Center) — patch de reprise pour les lots existants |
| `Asset` | **Custom Field** | + `cout_horaire` (Float, DT/h ; vide = défaut config). ⚠ à déclarer nommément dans les fixtures `hooks.py` (pattern `Stock Entry-id_lot`) |
| `Utilisation Equipement` | **nouveau DocType** | cf. §2.5 — autoname `format:UTL-{equipement}-{#####}` |
| `HMD Configuration` | **étendre** | + `lait_interne_prix_mode` (Select), `lait_interne_prix_fixe` (Float), `allaitement_litres_jour` (6,5), `allaitement_duree_jours` (90), `age_vente_velle_mois` (3), `age_cible_premier_velage_mois` (24), `prix_marche_velle_3mois`, `prix_marche_genisse_18mois`, `genisse_taux_perte_pct` (mortalité+infécondité) — accès via `get_config`, patch v1_6 de seed |
| `utils/facturation_lait_interne.py` | **nouveau util** | `post_lait_interne(periode)` + job scheduler mensuel, marqueur `LAIT_INTERNE_<periode>` |
| Comptes SCE | **étendre `EXTRA_ACCOUNTS`** | 6061 / 614x / 7068x « cessions internes » (numéros à valider expert-comptable) |
| `Coût de Revient Génisse` | **nouveau Script Report** | par animal et par cohorte — cf. §4 ; colonnes : `identification`, `date_naissance`, `age_jours`, `cout_lait_dt`, `cout_ration_dt`, `cout_mo_dt`, `cout_meca_dt`, `cout_autres_dt`, `cout_total_dt`, `cout_par_jour_dt`, `statut` |
| `cheptel_valorisation` | **étendre (option)** | `valeur_entree()` : mode config pour remplacer le forfait 2 500 par le coût calculé au premier vêlage |

Réutilisation ERPNext maximale : Cost Center, Journal Entry, Stock Entry/SLE,
Asset, Accounting Dimensions — **un seul** nouveau DocType custom.

---

## 4. Formule du coût de revient

**Par génisse `a`, cumulé de la naissance à la date `T` :**

```
C(a, T) = Σ (jours J de présence, naissance → min(T, sortie)) de :

    lait_bu(a, J)      × prix_lait(mois de J)          — §2.4, individualisé
  + coût_SE_ration(lot(a,J), J) / effectif(lot(a,J), J) — §2.3, individualisé
  + CoûtsMutualisés(mois de J) / journées_génisses(mois de J)
```

où `CoûtsMutualisés(mois)` = GL du Cost Center `Élevage - Génisses` sur le mois
**moins** lait interne et ration déjà individualisés = MO (640/647) + cessions
mécaniques (614x) + santé + divers ; et `journées_génisses(mois)` = Σ des jours
de présence de tous les animaux de l'atelier (reconstruction `live_state` /
`_populations_on_date` — jamais les champs vivants de l'Animal pour le passé).

**Par cohorte** (année/semestre de naissance) : moyenne de `C(a, T)` et
**coût par génisse-jour** = `Σ C(a,T) / Σ jours de présence` — l'indicateur
de pilotage le plus robuste (insensible aux dates de sortie individuelles).
Contrôle de cohérence : `Σ individualisé + mutualisé ≈ GL total de l'atelier`
sur la période (à brancher dans le rapport Contrôle Cohérence Finance, FIN-S70).

---

## 5. Aide à la décision : vendre à 3 mois vs élever à 18 mois

Bloc de synthèse en tête du rapport (même pattern seuils colorés `pfe_*`) :

```
Marge vente 3 mois   :  M3  = prix_marche_velle_3mois − C(0 → 3 mois)
Marge élevage 18 mois:  M18 = prix_marche_genisse_18mois × (1 − genisse_taux_perte_pct/100)
                              − C(0 → 18 mois)
Delta décision       :  Δ   = M18 − M3
```

- `Δ > seuil vert` → **élever** (l'élevage crée de la valeur) ;
- `Δ ≈ 0` (orange) → indifférent, arbitrer sur la trésorerie et le renouvellement ;
- `Δ < 0` (rouge) → **vendre à 3 mois** (chaque mois d'élevage détruit de la valeur).

Données nécessaires : les deux prix de marché (saisie config, à rafraîchir —
pas de source automatique en Tunisie), le taux de perte (mortalité +
infécondité, calculable a posteriori depuis `live_state` : sorties MORT /
REFORME avant premier vêlage ÷ effectif cohorte), et les coûts cumulés du §4.
Nuance à afficher : pour une génisse **destinée au renouvellement**, le vrai
comparatif est `C(0→18)` vs **prix d'achat d'une génisse pleine** (coût de
remplacement) — les deux lectures figurent dans le bloc. Le cas « 3 ans au
lieu de 18 mois » (problème fécondité) apparaît naturellement : chaque mois
supplémentaire ajoute ~30 génisse-jours de coût au cumul.

---

## 6. Découpage en stories JIRA (EPIC I — Atelier Génisses)

| Story | Contenu | Est. |
|---|---|---|
| **FIN-S80** | Rattachement analytique des lots : champ `Lot.atelier`, patch de reprise, Cost Center + dimension Lot sur les SE de ration (`feed_distribution`) | 1 j |
| **FIN-S81** | Facturation interne du lait : comptes cession interne, `post_lait_interne` mensuel idempotent + job, configs prix (`lait_interne_prix_mode/fixe`) | 2 j |
| **FIN-S82** | Lait bu par génisse : configs courbe d'allaitement, répartition normalisée sur `lait_veau` | 1,5 j |
| **FIN-S83** | Coût horaire équipement : Custom Field `Asset.cout_horaire` (+ fixture nommée), DocType `Utilisation Equipement`, JE cession interne travaux + symétrie on_trash | 2 j |
| **FIN-S84** | Rapport « Coût de Revient Génisse » (par animal + cohorte, formule §4, contrôle de cohérence GL) | 3 j |
| **FIN-S85** | Bloc aide à la décision 3 mois vs 18 mois : configs prix marché + taux de perte, seuils colorés, lecture « coût de remplacement » | 1,5 j |
| **FIN-S86** | Boucler la valorisation cheptel : option config remplaçant le forfait `cheptel_cout_elevage` (2 500) par `C(a, premier vêlage)` calculé | 1 j |

Ordre : S80 → S81/S82/S83 (parallélisables) → S84 → S85 → S86.
Total ≈ **12 j**. Tests inclus dans chaque story (`tests/test_genisses_*.py`).

---

## 7. Questions ouvertes pour M. Samir

1. **Prix du lait interne** : grille qualité de la centrale (coût
   d'opportunité, recommandé) ou prix conventionnel fixe ?
2. **Comptes de cession interne** (6061 / 7068x proposés) : à valider avec
   l'expert-comptable — ces écritures restent-elles purement internes
   (« entre parenthèses »), exclues des états transmis ?
3. **Lait bu individuel** : courbe théorique 6,5 L/j × 90 j acceptable comme
   clé de répartition du `lait_veau` réel ? Durée d'allaitement effective ?
4. **Prix de marché** velle 3 mois / génisse pleine 18 mois : quelles valeurs
   de départ, et qui les met à jour (et à quelle fréquence) ?
5. **Périmètre de l'atelier** : les mâles (veaux/taurillons engraissés) sont
   dans les mêmes lots — les isoler dans le coût génisse ou assumer un coût
   moyen « jeune bovin » ?
6. **Frais généraux** (gardien, administratif) : inclure une quote-part dans
   le coût génisse, ou s'arrêter aux coûts directs de l'atelier ?
7. **Taux de perte** (mortalité + infécondité) pour l'aide à la décision :
   valeur de départ (ex. 8 %) en attendant assez d'historique ?
8. **Forfait 2 500 TND** : d'accord pour le remplacer, à terme, par le coût
   calculé à l'entrée à l'actif (FIN-S86) — ou le garder comme valeur
   comptable et n'utiliser le calculé qu'en pilotage ?
