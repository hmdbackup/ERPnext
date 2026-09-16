# Review — Maquettes Farm Management (Mohamed Iheb Gouia)

**Périmètre relu :** `Maquette-Farm_Management` (9 PNG) + `MAQUETTE_BUSINESS.pdf` + `Definition of Ready (DoR)-FM.pdf`
**US concernées :** US-FM-1 (exploitations & parcelles) · US-FM-2 (cultures & variétés) · US-FM-3 (interventions)
**Date de la review :** 22/08/2026
**Relecteur :** Mohamed Slim

---

## 1. Verdict en une phrase

Le squelette métier est juste et la chaîne **Exploitation → Parcelle → Culture → Intervention** est
lisible d'un écran à l'autre ; mais **US-FM-3 n'a aucun écran**, **US-FM-2 n'est couverte qu'à moitié**,
et la question de coût que la DoR elle-même signale comme à trancher (§4-a) reste ouverte. En l'état
la DoR d'équipe n'est pas franchie — il manque des écrans, pas de la mise en forme.

## 2. Ce qui est livré

| Fichier | N° à l'écran | Écran | US |
|---|---|---|---|
| FM-1 | 1 | Dashboard | transverse |
| FM-2 | 2 | Liste exploitations | FM-1 |
| FM-3 | 3 | Création exploitation — informations générales | FM-1 |
| FM-4 | 4 | Création exploitation — localisation | FM-1 |
| FM-5 | 5 | Liste parcelles | FM-1 |
| FM-6 | 6 | Création parcelle | FM-1 |
| FM-7 | 7 | Association d'une culture à la parcelle | FM-2 |
| FM-8 | **9** | Fiche parcelle (consulter) | FM-1 / FM-2 |
| FM-9 | — | États d'écran (vide / succès / erreur / confirmation suppression) | transverse |

> **La numérotation saute de 7 à 9 : l'écran n° 8 n'est pas dans le zip.** Première question à poser —
> s'agit-il de la *fiche exploitation* (annoncée à l'écran 2 de la maquette business) ou d'un écran
> intervention ? Il manque peut-être simplement à l'export.

## 3. Ce qui est bien — à garder tel quel

- **L'architecture métier est respectée bout en bout.** Chaque écran rattache l'information à la bonne
  unité ; la parcelle est bien traitée comme l'unité opérationnelle de référence (maquette business §12).
- **L'encart d'aide de l'écran 6** : « cette superficie sera utilisée pour tous les calculs agricoles
  (coûts/ha, rendements) ». Rendre une invariante visible au moment de la saisie, c'est exactement
  ce qui évite les données fausses en production. À généraliser.
- **L'écran 9 (états vide / succès / erreur / confirmation)** est rare dans une première passe de
  maquettes et il vaut cher : il dit ce que l'utilisateur voit quand ça se passe mal, pas seulement
  quand tout va bien.
- **La fiche parcelle à onglets (FM-8)** est la bonne cible : Résumé / Cultures / Interventions / Coûts,
  c'est là que l'historique prend son sens.
- **Les créations sont découpées en étapes** (exploitation → localisation, parcelle → culture),
  ce qui limite le formulaire-fleuve sur le terrain.

## 4. Bloquants — à traiter avant de dire « Ready »

### B1. US-FM-3 « Plan and record Interventions » : zéro écran

Aucune maquette de création d'intervention, d'affectation multi-parcelles (UC-FM-3.3), de saisie de
quantité/unité, de coût, ni d'historique des interventions. Or l'intervention est **présente partout
ailleurs** : entrée « Interventions » dans le menu, blocs « Interventions récentes » et « Coûts récents »
du dashboard, onglets « Interventions » et « Coûts » de la fiche parcelle, colonne « Dernière
intervention » dans la liste des parcelles. On maquette donc les conséquences d'un écran qui n'existe pas.

Sa propre DoR §4 exige « wireframes disponibles au moins pour les écrans de création : exploitation,
parcelle, culture, **intervention** » et « parcours multi-parcelles couvert (UC-FM-3.3) ». **Non satisfait.**

### B2. La règle de répartition du coût multi-parcelles n'est pas tranchée (DoR §4-a)

La DoR pose elle-même la question au PO : *coût total saisi une fois puis réparti au prorata de la
superficie, OU coût/ha saisi une fois et multiplié par la superficie de chaque parcelle ?* Aucune
maquette n'y répond, et la réponse **change l'écran** :

- *Variante A (coût total réparti)* : un champ « Coût total (TND) » + un tableau en lecture seule
  montrant la quote-part calculée par parcelle. L'utilisateur voit la répartition avant d'enregistrer.
- *Variante B (coût/ha)* : un champ « Coût / ha (TND) » + un total calculé par parcelle et un total
  général. Pas de répartition, une multiplication.

**Proposition :** maquetter les deux variantes côte à côte, une planche chacune, et les faire arbitrer.
C'est la question à emmener en premier chez le PO / M. Samir — tout le calcul de coût en dépend.

### B3. US-FM-2 : la moitié des règles métier n'a pas d'écran

L'écran 7 ne porte que **Culture / Variété / Campagne-Année**. Manquent, alors qu'ils sont des
fonctionnalités explicites de la maquette business §5 :

- **date de début et date de fin** — pourtant la fiche parcelle (FM-8) *affiche* « Début 15/03/2026,
  Fin prévue 15/07/2026 ». Ces dates sont saisies où ?
- **durée calculée automatiquement** — règle annoncée (§5 et §8), invisible dans l'UI ;
- **culture permanente / arboricole** — aucune case, aucun mode. Or l'écran 5 liste « Olivier » à côté
  de Tomate, Blé, Orge : le cas est déjà dans le jeu de données de démo mais pas dans le formulaire.
  Une culture permanente « sans cycle annuel classique » (§8) ne peut pas se saisir avec les seuls
  champs de l'écran 7 ;
- **informations spécifiques à la culture** — les champs « flexibles/optionnels » de la DoR §3 ;
- **l'écran 4 « Cultures »** de la maquette business (liste : parcelle, culture, variété, début, fin,
  durée, statut actif/terminé) n'existe pas.

**Et un conflit de modèle :** le champ « Campagne / Année » suggère une clé *(parcelle, culture, année)*.
Si deux cultures successives de tomate ont lieu la même année sur la même parcelle — cas nominal
revendiqué par la règle métier §5 — elles se télescopent. À trancher : un cycle de culture est
identifié par ses **dates**, pas par une année. La « campagne » devient alors un simple attribut de
regroupement pour les rapports.

### B4. Frappe standard ou UI sur mesure ? — la question qui pilote l'estimation

HMD AGRO tourne sur **Frappe/ERPNext v15**. Dans le Desk, les listes, les formulaires, la recherche,
la pagination, les actions par ligne (voir / modifier / supprimer), la confirmation de suppression,
l'état vide et la validation des champs obligatoires sont **fournis par le framework**. Les écrans
2, 3, 5, 6 et 9 redessinent, pour l'essentiel, l'existant standard.

Ce n'est pas un reproche à la maquette : c'est une décision à prendre **avant d'estimer**.

- Si FM est construit en **DocTypes Frappe avec le Desk standard**, ces maquettes deviennent une
  spécification de champs, de libellés, d'obligatoires et de permissions — et la charge s'effondre.
- Si FM est un **portail / des pages sur mesure**, il faut réécrire liste, tri, filtres, pagination et
  états — et la charge est d'un autre ordre.

C'est le critère n° 4 de notre DoR d'équipe (Technical Grooming) : à écrire et à partager avant de coder.

Deux vérifications à faire dans ce cadre :

1. **ERPNext a historiquement livré un module Agriculture** (Land Unit, Crop, Crop Cycle, Agriculture
   Task) sorti du cœur vers la v14 et maintenu comme application séparée. À vérifier avant de
   remodéliser Parcelle / Culture / Cycle à partir de zéro.
2. **Le coût d'une intervention est aussi une écriture.** C'est la leçon déjà tirée côté Assets : les
   interventions n'ont pas de DocType maison, ce sont des Asset Repair *plus* leur écriture au compte
   615. Une intervention agricole porte un coût et une quantité d'intrant (engrais, semence) — donc
   potentiellement un mouvement de stock et une charge. Si la maquette la traite comme un simple
   nombre saisi à la main, le module divergera de la comptabilité. Question ouverte, à poser tôt.

## 5. Incohérences à corriger dans les maquettes

Ces chiffres sont lus comme des règles par le métier ; il faut qu'ils tombent juste.

| # | Écran | Constat | Correction |
|---|---|---|---|
| I1 | FM-1 vs FM-2 | Dashboard : **27 parcelles / 500 ha**. Liste : 9+8+8 = **25 parcelles**, 145+82+100 = **327 ha**. | Aligner le jeu de données de démo. |
| I2 | FM-1 | « Vue d'ensemble de votre **exploitation** » (singulier) alors que la carte affiche 3 exploitations. | Choisir : mono ou multi-exploitation par utilisateur ? Ça change le menu et les filtres. |
| I3 | FM-5 | **P01 répété 4 fois**, même exploitation, même 100 ha, 4 « cultures actives » différentes. | Soit c'est un copier-coller, soit la liste affiche en réalité des couples (parcelle × culture) — auquel cas ce n'est plus une liste de parcelles et « culture active » ne peut pas être multiple. À clarifier : c'est la manifestation visible de la règle multi-cultures. |
| I4 | FM-5 vs FM-2 | 4 × 100 ha sur Ferme Borj Essebai, annoncée à 145 ha pour 9 parcelles. | Idem I1. |
| I5 | FM-8 | Trois dates contradictoires sur le même écran : bandeau « Début culture 15/04/2026 », panneau « Début 15/03/2026 » ; bandeau « Dernière intervention 15/04/2026 », panneau « fongicide 15/05/2026 ». | Une seule source par donnée. |
| I6 | FM-8 vs FM-2 | Fiche P01 « Localisation : Tunis » alors que Ferme Borj Essebai est à Bizerte-Mateur. | Aligner. Et préciser : la parcelle a-t-elle sa propre localisation, ou hérite-t-elle de l'exploitation ? |
| I7 | FM-1 vs FM-5 | Deux conventions de nommage de parcelle : « Kairouan P02 » / « Mateur P03 » d'un côté, code « P01 » + colonne exploitation de l'autre. | Fixer la règle : le code est-il unique par exploitation ou global ? C'est une règle de nommage, donc du modèle de données. |
| I8 | FM-1 | Coûts récents = « **X TND** » (placeholder). | Décider le format d'affichage : montant total ou coût/ha, nombre de décimales, position de la devise. Renvoie à B2. |
| I9 | FM-3 vs FM-6 | Obligatoires incohérents : « Description * » obligatoire sur l'exploitation (inhabituel, et absent de la maquette business), mais **« Superficie de la parcelle » non marquée obligatoire** — alors que le même écran dit qu'elle sert à tous les calculs et que l'écran 9 affiche l'erreur « la superficie doit être supérieure à 0 ». | Reprendre la liste obligatoire/optionnel champ par champ (DoR §3) et la faire valider. |
| I10 | FM-6 | La superficie a un **sélecteur d'unité** alors que la DoR §2 fixe l'unité à l'hectare. | Soit on assume les autres unités (m² ? are ?) et il faut la règle de conversion, soit on fige « ha » en libellé. |
| I11 | FM-4 | **Latitude et longitude obligatoires et saisies à la main**, carte apparemment statique. | Sur le terrain, personne ne tape 36.8065. Prévoir : point posé sur la carte, ou capture GPS, ou géocodage de l'adresse — et rendre lat/long optionnelles sinon. La DoR §3 demande d'identifier l'intégration (UC-FM-1.2) : à nommer. |
| I12 | FM-4 | « Région » et « Gouvernorat » cohabitent sans hiérarchie définie. En Tunisie le découpage est Gouvernorat → Délégation. | Vocabulaire métier sans ambiguïté = DoR §1. Choisir les termes, dire lequel contient l'autre, et prévoir la liste de référence (24 gouvernorats). |

## 6. Écrans à demander

1. **Fiche exploitation** — annoncée dans la maquette business (écran 2 : informations générales,
   localisation, liste des parcelles) ; c'est la cible de l'icône œil de FM-2. Possiblement l'écran 8 manquant.
2. **Liste des cultures** — écran 4 de la maquette business.
3. **Création / édition d'une intervention** — écran 5, avec quantité + unité, coût, et le cas multi-parcelles.
4. **Historique des interventions d'une parcelle** — cible du lien « Voir toutes les interventions » de FM-8.
5. **Les écrans de modification** — toutes les maquettes de formulaire sont des créations ; l'icône
   crayon des listes n'a pas de destination. Préciser au minimum ce qui est modifiable après coup
   (la superficie d'une parcelle déjà exploitée, par exemple, a des conséquences sur les coûts/ha déjà calculés).
6. **L'écran 8 manquant.**

## 7. Questions ouvertes — à trancher, et par qui

**Pour le PO / M. Samir (métier)**

1. Répartition du coût multi-parcelles : coût total réparti au prorata, ou coût/ha multiplié ? *(B2)*
2. Une visite de terrain est-elle une intervention comme les autres, avec quantité et coût à zéro, ou
   un type d'événement distinct ? *(maquette business §6 et §8)*
3. Que devient une exploitation supprimée qui porte des parcelles, des cultures et des interventions —
   suppression en cascade, blocage, ou archivage ? La règle n'existe ni dans le document ni à l'écran,
   alors que l'icône poubelle est offerte sur chaque ligne.
4. Un utilisateur voit-il une seule exploitation ou toutes ? *(I2)*
5. Les onglets **Observations** et **Documents** de la fiche parcelle sont hors du périmètre MVP §10
   (de même que « Rapports » et « Paramètres » dans le menu) — MVP ou plus tard ? À décider maintenant,
   sinon ils entrent dans l'estimation sans avoir de critère d'acceptation. *Ni plus, ni moins.*

**Pour Aymen (lead) — technique**

6. Desk Frappe standard ou UI sur mesure ? *(B4)* — c'est ce qui conditionne l'estimation.
7. L'intervention génère-t-elle une écriture comptable et/ou un mouvement de stock d'intrant, comme
   côté Assets ? *(B4.2)*
8. Rôles et permissions : qui crée, modifie, supprime une exploitation / une parcelle / une
   intervention ? *(DoR §5, non couvert par les maquettes)*

**Pour Iheb**

9. Où est l'écran 8 ?
10. Les dates de culture sont saisies sur quel écran ? *(B3)*
11. P01 répété quatre fois dans la liste des parcelles : quelle est l'intention ? *(I3)*

## 8. Confrontation à la DoR d'équipe du 07/08/2026

| # | Critère | État | Ce qui manque |
|---|---|---|---|
| 1 | Critères d'acceptation définis et clairs | ❌ | Le dossier liste des fonctionnalités et des règles, pas de critères testables. La DoR d'Iheb elle-même (§2) exige « au moins 1 critère d'acceptation testable par UC » : à écrire, en Given/When/Then. |
| 2 | Maquette partagée avec le métier | 🟡 | C'est précisément l'objet de cette review. Porte humaine : la validation par M. Samir / Aymen n'a pas eu lieu et ne peut pas être auto-déclarée. |
| 3 | Tests définis | ❌ | Aucune liste de cas. Les cas limites sont pourtant déjà identifiables : cultures successives la même année, culture permanente, intervention sur N parcelles, superficie à 0, suppression d'une exploitation peuplée. |
| 4 | Technical Grooming | ❌ | La décision Frappe standard vs sur mesure, le modèle de données, et le lien coût/comptabilité. C'est le cœur de la porte. |
| 5 | Découpage en sous-tâches | ❌ | À faire une fois 4 tranché. |
| 6 | Estimation | ⛔ | Bloquée par 4. Une estimation posée avant cet arbitrage serait inventée. |

**Conclusion de porte : US-FM-1 est proche du Ready, US-FM-2 est incomplète, US-FM-3 n'est pas maquettée.**
Le découpage naturel est d'ailleurs là : faire passer FM-1 en premier plutôt que d'attendre les trois.

## 9. Déroulé proposé pour la réunion de review (45 min)

| Temps | Sujet |
|---|---|
| 5 min | Ce qui est bien : la chaîne métier, la fiche parcelle, les états d'écran. On part de là. |
| 10 min | Les trois bloquants : couverture FM-3, cultures incomplètes, coût multi-parcelles. |
| 10 min | Arbitrage coût multi-parcelles avec les deux variantes sous les yeux *(B2)*. |
| 10 min | La question technique : Desk Frappe ou sur mesure, et le lien intervention → coût → comptabilité. |
| 5 min | Les incohérences de données de démo (liste I1–I12, à traiter hors réunion). |
| 5 min | Suite : écrans manquants, critères d'acceptation à écrire, prochaine date. |

---

*Review préparée à partir de : `Maquette-Farm_Management/FM-1..9.png`, `MAQUETTE_BUSINESS.pdf`
(M. I. Gouia), `Definition of Ready (DoR)-FM.pdf`, et de la DoR/DoD d'équipe actée le 07/08/2026.*
