# Technical Grooming — SCRUM-9, SCRUM-10, SCRUM-11

Préparé le 07/08/2026 par Mohamed Slim, suite à la réunion process du jour
(Definition of Done / Definition of Ready).

Chaque bloc « Technical Grooming » ci-dessous est destiné à être **collé en
commentaire de l'issue Jira correspondante**, pas dans sa description.

---

## Constat transverse — à lire avant les trois fiches

Les trois stories sont au statut **« Idea »** : aucune n'a de critères
d'acceptation écrits. Le premier travail de préparation n'est donc pas
technique, il est de **les rédiger**, faute de quoi la DoR ne peut pas être
atteinte et la DoD (« les critères d'acceptation ont été atteints ») n'a rien
à vérifier.

Second constat, plus important : **deux des trois sont en grande partie déjà
implémentées** sur la branche `finance/socle-comptable`. Le grooming ci-dessous
le documente précisément, pour deux raisons :

1. éviter que quelqu'un les redéveloppe ;
2. faire apparaître que la vraie valeur restante n'est pas dans le code mais
   dans **la fusion vers `main` et la validation métier** — le sujet de la
   version obsolète vue en démo du 05/08.

---

# SCRUM-9 — Rapport mensuel sur la production laitière

## Definition of Ready

| Critère | État | Reste à faire |
|---|---|---|
| Critères d'acceptation définis et clairs | ❌ | À rédiger (proposition ci-dessous) |
| Maquette partagée avec le métier | ⚠️ | Le rapport **existe** : partager une capture à M. Samir vaut maquette, et tranche l'écart en une réunion |
| Tests définis | ⚠️ | Suite existante à recenser, cas manquants à lister |
| Technical Grooming | ✅ | Ce document |
| Découpage en sous-tâches | ✅ | Ci-dessous |
| Estimation | ⚠️ | Dépend entièrement de l'écart constaté à l'étape 1 |

## Critères d'acceptation proposés

- Le rapport présente, pour un mois donné : production totale (kg et litres),
  moyenne par vache lactante et par jour, effectif lactant moyen.
- La **couverture de saisie** du mois est affichée (ex. « 28/31 jours saisis »),
  y compris quand elle est complète.
- Un mois incomplet ne fait disparaître aucune valeur : il désactive la
  coloration des ratios faussés et l'annonce en tête de tableau.
- Le rapport est exportable.

## Technical Grooming

**L'essentiel est livré.** Deux rapports couvrent déjà le besoin :

- `hmd_agro/hmd_agro/report/rapport_periodique/rapport_periodique.py` (1678 l.)
  — la fonction `_production` produit kg, L/VL/jour, agrégats par quinzaine et
  par semaine, avec **reconstruction historique du nombre de vaches lactantes
  jour par jour** (elle ne lit pas l'effectif courant, elle le rejoue depuis les
  événements — c'est ce qui rend un historique juste).
- `hmd_agro/hmd_agro/report/rapport_performance/rapport_performance.py` (308 l.)
  — filtre `periode` dont la valeur par défaut est déjà **`Mois`**, `_production`
  pour la période, et le garde-fou « période incomplète » (FIN-S95) qui affiche
  la couverture de saisie.

**Approche retenue :** ne rien réécrire. Comparer l'attendu métier au rendu
actuel, et ne combler que l'écart. Le risque n'est pas technique, il est de
recréer un troisième rapport là où deux se recouvrent déjà.

**Point d'attention :** `rapport_performance` importe des helpers de
`rapport_periodique` en *lazy import* (bornes de semaine, couverture de saisie).
`rapport_periodique` détient la **lecture canonique** de ces notions. Toute
règle de calendrier ou de couverture se corrige là, jamais en double.

**⚠ Le trou réel, trouvé en seconde lecture — une colonne morte.**
`rapport_periodique._production` déclare la colonne « Commercialisé (L) »
(`rapport_periodique.py:256`) puis écrit `"commercialise": None` sur **chaque
ligne** (`:295`). Aucune autre occurrence dans le fichier : la colonne est
affichée à l'utilisateur et **n'est jamais remplie**.

Or la donnée existe, au jour près : `Bilan Lait Journalier` porte `lait_vendu`,
`consommation_interne`, `lait_veau` et `ecart_litres` — `rapport_performance`
les lit déjà, mais seulement en cumul de période.

C'est très probablement le cœur de SCRUM-9 : le dispositif Excel ventile la
production en commercialisé / auto-consommation / perte, et c'est exactement
cette ventilation quotidienne qui manque. Le travail n'est donc pas « relire un
rapport existant » mais **câbler une colonne déjà promise à l'écran**.

## Sous-tâches

1. Capturer le rendu actuel (`Rapport Performance`, période = Mois) et le
   soumettre à M. Samir → **liste d'écarts factuelle**.
2. Rédiger les critères d'acceptation à partir de cette liste.
3. Combler les écarts (probablement : libellés, colonnes, ordre).
4. Vérifier l'export.
5. Tests : mois complet, mois avec trou de saisie, mois sans aucune traite.

## Estimation

**À déterminer après la sous-tâche 1.** Toute estimation posée avant cette
comparaison serait inventée. Fourchette honnête : 4 h si l'écart est cosmétique,
2 j s'il faut une maille mensuelle dédiée.

---

# SCRUM-10 — Rapport mensuel sur les coûts

## Definition of Ready

| Critère | État | Reste à faire |
|---|---|---|
| Critères d'acceptation définis | ❌ | À rédiger |
| Maquette partagée avec le métier | ⚠️ | Idem SCRUM-9 : capture du rapport existant |
| Tests définis | ⚠️ | À compléter |
| Technical Grooming | ✅ | Ce document |
| Découpage / estimation | ✅ / ⚠️ | Ci-dessous |

## Critères d'acceptation proposés

- Charges du mois lues au **Grand Livre**, ventilées par atelier (cost center).
- Coûts unitaires : coût complet au litre, coût alimentaire au litre.
- Le **coût mécanique** est affiché séparément et **n'est pas additionné** au
  coût complet au litre.
- Un mois sans écriture affiche zéro, pas une erreur.

## Technical Grooming

**Livré** dans `rapport_performance.py` : `_charges` (lecture GL) et
`_couts_unitaires` (coût complet / coût alimentaire au litre).

**⚠️ Le piège de cette story — à ne pas défaire.** Le commentaire aux lignes
275-278 de `rapport_performance.py` porte une règle non négociable :

> le coût mécanique au litre est une **clé de répartition** ; il n'entre **pas**
> dans `cout_complet_l`, car amortissement et entretien y figurent déjà via les
> charges du Grand Livre.

Toute demande du type « ajoutez le coût mécanique au coût total » produirait un
**double comptage** et un coût du litre faux. Si le métier le demande, c'est une
discussion à ouvrir, pas une modification à faire. Même règle côté
`maintenance_utils.cout_utilisation`, dont la docstring la répète.

**Sources de données :** `GL Entry` filtré par `company` et `is_cancelled = 0`,
compte d'entretien `615` (constante `COMPTE_ENTRETIEN`), cost centers par atelier.

## Sous-tâches

1. Capture du rendu actuel → validation métier, liste d'écarts.
2. Rédaction des critères d'acceptation.
3. Vérifier la ventilation par atelier sur un mois réel (pas le jeu de démo).
4. Combler l'écart.
5. Tests : mois sans écriture, mois avec écriture annulée (`is_cancelled`),
   charge sans cost center → doit tomber sur `Frais Généraux`.

## Estimation

**À déterminer après la sous-tâche 1.** Fourchette : 4 h à 1 j 4 h.

---

# SCRUM-11 — Rapport mensuel sur les interventions mécaniques

## Definition of Ready

| Critère | État | Reste à faire |
|---|---|---|
| Critères d'acceptation définis | ❌ | À rédiger |
| Maquette partagée avec le métier | ❌ | **Rien à montrer** — le rapport n'existe pas. Maquette à produire |
| Tests définis | ❌ | À écrire intégralement |
| Technical Grooming | ✅ | Ce document |
| Découpage / estimation | ✅ | Ci-dessous |

## Critères d'acceptation proposés

- Un Script Report en français liste les interventions du mois : équipement,
  date, description, coût, atelier imputé.
- Totaux : nombre d'interventions, nombre d'équipements concernés, coût total.
- Les interventions **préventives dues ou en retard** sont visibles.
- L'**écart** entre le compte 615 du Grand Livre et la somme des interventions
  saisies est affiché explicitement.
- Un mois sans intervention affiche zéro, pas une erreur.

## Technical Grooming

**C'est la seule des trois avec du vrai travail de développement.** La couche
données est prête, la couche restitution n'existe pas.

Disponible dans `hmd_agro/hmd_agro/utils/maintenance_utils.py` :

| Fonction | Retour |
|---|---|
| `cout_maintenance(date_debut, date_fin)` | `{cout, interventions, equipements, par_equipement}` |
| `interventions_planifiees(jours=30)` | lignes `Asset Maintenance Log` en `Planned` / `Overdue` |
| `cout_utilisation(date_debut, date_fin)` | `{total, heures, par_atelier, par_equipement}` |
| `enregistrer_intervention(...)` / `annuler_intervention(...)` | écriture + contrepartie comptable |

Aucun rapport ne les expose sous forme de **liste d'interventions** :
`rapport_performance` n'en consomme que le montant agrégé.

**Approche :** nouveau Script Report `rapport_interventions`, sur le modèle de
`rapport_performance` (le plus court des existants, 308 lignes — c'est le
gabarit à copier, pas `rapport_periodique`). Il **consomme `maintenance_utils`**
et ne requête jamais `Asset Repair` directement : c'est la règle déjà tenue par
les autres rapports (« ils n'ont pas à connaître le DocType »).

**Le point délicat — deux sources qui ne s'accordent pas.**
`cout_maintenance` lit **deux choses différentes** et retourne les deux :

- `cout` vient du **Grand Livre** (compte 615, `SUM(debit - credit)`) ;
- `par_equipement` vient des **`Asset Repair`** (`total_repair_cost`, sur
  `COALESCE(completion_date, failure_date)`).

Ces deux montants **divergeront** : une facture d'entretien passée directement
en comptabilité sans `Asset Repair` gonfle le premier sans toucher le second.
La tentation sera d'en afficher un seul. **Il faut afficher les deux et leur
écart** — c'est précisément l'information utile au gérant (« 400 DT d'entretien
non rattachés à un équipement »). Masquer l'écart transformerait un rapport de
pilotage en rapport rassurant.

**Vigilances :**

- Filtrer `docstatus = 1` sur `Asset Repair` (un brouillon n'est pas une
  intervention) et `is_cancelled = 0` sur le GL.
- Les statuts `Sold` / `Scrapped` sont bloquants côté saisie
  (`STATUTS_ASSET_BLOQUANTS`) : un équipement cédé en cours de mois doit tout de
  même apparaître pour ses interventions antérieures.
- Sans cost center, l'imputation tombe sur `Frais Généraux` (`ATELIER_DEFAUT`) —
  à rendre visible plutôt qu'à laisser deviner.

## Sous-tâches

1. Maquette du tableau (colonnes, totaux, bloc écart GL/interventions) →
   validation M. Samir. **Bloquant DoR.**
2. Rédaction des critères d'acceptation.
3. Squelette du Script Report (`.json` / `.py` / `.js`) sur le gabarit
   `rapport_performance`, filtres mois + équipement + atelier.
4. Section « interventions réalisées » via `cout_maintenance`.
5. Section « préventif dû / en retard » via `interventions_planifiees`.
6. Bloc « écart Grand Livre ↔ interventions saisies ».
7. Tests : mois sans intervention · intervention en brouillon (exclue) ·
   écriture 615 sans `Asset Repair` (écart non nul) · équipement `Scrapped`
   avec intervention antérieure · intervention sans atelier.
8. Ajout du raccourci dans `hmd_agro/fixtures/workspace.json` — **le reproche
   exact de la réunion du 05/08** : un écran livré mais inatteignable depuis le
   menu ne compte pas comme livré.

## Estimation

**1 j 4 h.** Le gabarit et la couche données existent ; le coût réel est dans
la maquette (sous-tâche 1), le bloc d'écart (6) et les cas de test (7).

---

## Definition of Done retenue pour ces trois stories

Rappel des critères actés en réunion, à cocher avant clôture :

- [ ] Critères d'acceptation atteints — ni plus, ni moins que la description
- [ ] Toutes les sous-tâches terminées
- [ ] Code review avec un collègue
- [ ] Tests unitaires
- [ ] Tests de non-régression (TNR)
- [ ] Test d'acceptation avec le lead ou M. Samir
- [ ] Merge sur la branche du sprint
- [ ] Push / sauvegarde sur GitHub
- [ ] Message de fin posté sur le groupe
