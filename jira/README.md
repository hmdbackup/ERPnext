# Backlog Finance — organisation Jira

Groomé le **07/08/2026**. Remplace `finance_backlog_jira.csv`,
`finance_backlog_jira_nouvelles_stories.csv` et
`finance_backlog_jira_reunion_2026-08-05.csv` (déplacés dans `archive/`).

| Fichier | À quoi il sert |
|---|---|
| `backlog_finance.csv` | **Tout** : 9 epics + 61 issues. Pour un projet Jira vierge. |
| `backlog_finance_delta.csv` | **Uniquement le nouveau** : 2 epics + 17 issues. Pour un projet où les 44 stories d'origine sont déjà importées. |
| `backlog.py` | Source unique. On édite **ce fichier**, puis `python3 jira/backlog.py` régénère les deux CSV. |

**9 epics · 61 issues — 40 livrées, 1 en cours, 20 à faire.**

---

## La règle qui change tout

> **Le statut d'une issue vit dans la colonne `Status`. Jamais dans sa description.**

Les anciens fichiers encodaient l'état en prose (`Statut: livré`,
`DECISION CLIENT`, `Reste à…`). Résultat au moment du grooming : **quatre
stories affichaient un état faux**, dont une story marquée livrée dont le
critère d'acceptation n'était pas rempli. Une description ne se relit pas ; une
colonne se filtre.

Les descriptions conservent en revanche la **traçabilité** — `Livraison: commit
<sha>`, `Bloqué par:`, `Dépend de:`, `Origine:` — qui, elle, ne périme pas.

Les compteurs de tests (`42/42`…) ont été **retirés du backlog** : ils
divergeaient déjà entre trois fichiers. Leur place est dans
`livraison_finance.md`, tenu par une exécution réelle de la suite.

---

## Structure des epics

| Epic | Nom Jira (`Epic Name`) | Contenu | État |
|---|---|---|---|
| A | `Socle comptable` | Plan comptable SCE, exercice, TVA, cost centers, dimensions | Done |
| B | `Valorisation des couts` | CMP réel sur les consommations, coût/litre | Done |
| C | `Recettes` | Lait, animaux, fumier, grille qualité, décompte figé, multi-acheteurs | En cours |
| D | `Immobilisations` | Assets, amortissements, maintenance, cheptel, identification | En cours |
| E | `Charges et main-d'oeuvre` | Charges par atelier, registre Personnel, masse salariale, primes | En cours |
| F | `Pilotage` | KPI économiques, seuils, rapports périodique et performance | Done |
| G | `Bascule` | À-nouveaux, droits par rôle, contrôle de cohérence | En cours |
| **I** | `Atelier Genisses` | **Nouveau** — coût de revient génisse, facturation interne du lait | À faire |
| **J** | `Exploitation` | **Nouveau** — déploiement, versions, langue, accès écrans, données de démo | En cours |

### Il n'y a pas d'EPIC H

« Epic H » dans `livraison_finance.md` désigne un **lot de livraison**
(S24/S25/S31/S32/S42/S70), pas un epic. Ces six stories restent dans leur epic
métier et portent le label `lot-h`. Créer un epic H aurait mis la même story
dans deux epics.

### Remappages effectués

Le backlog de réunion utilisait quatre `Epic Link` (`Cheptel`, `Personnel`,
`Exploitation`, `Couts genisses`) **auxquels aucune ligne Epic ne correspondait**
— et ne déclarait aucun epic du tout. À l'import, ces stories seraient arrivées
orphelines.

| Ancien `Epic Link` | Nouveau | Pourquoi |
|---|---|---|
| `Cheptel` (S81) | `Immobilisations` | Le cheptel à l'actif (S31) y vit déjà ; S81 resynchronise l'Asset |
| `Personnel` (S82, S83, S84) | `Charges et main-d'oeuvre` | Extensions directes de S42, déjà dans cet epic |
| `Exploitation` (S92, S97, S98, S99, S101) | `Exploitation` **(epic créé)** | 5 stories : l'epic était légitime, il manquait |
| `Couts genisses` (S93) | `Atelier Genisses` **(epic créé)** | Porte désormais S93 + les 7 stories d'implémentation |

---

## Import dans Jira

1. **Encodage : UTF-8.** Le fichier contient des accents et des guillemets français.
2. *Paramètres > Système > Importation externe > CSV*, ou *Projet > Importer des issues*.
3. Mapper les colonnes :

| Colonne CSV | Champ Jira |
|---|---|
| `Issue Type` | Type de ticket (`Epic`, `Story`, `Task`) |
| `Summary` | Résumé — **contient la clé fonctionnelle** (`FIN-S42 …`) |
| `Epic Name` | Nom de l'epic (lignes `Epic` uniquement) |
| `Epic Link` | Epic parent — rapproché par **nom d'epic** (projet *company-managed*) |
| `Status` / `Resolution` | Statut / Résolution |
| `Priority`, `Original Estimate` | Priorité, estimation initiale |
| `Labels` ×5 | Étiquettes — **5 colonnes portent le même en-tête**, mappez-les toutes sur *Labels* |
| `Description` | Description |

4. **Les lignes `Epic` doivent être importées en premier** — elles sont déjà en
   tête du fichier, ne triez pas.

### Points de vigilance

- **Statuts** : seuls `To Do`, `In Progress`, `Done` sont utilisés — le schéma
  Jira par défaut. Si votre workflow est en français, mappez vers
  `À faire` / `En cours` / `Terminé` au moment de l'import.
- **Blocage** : il n'y a **pas** de statut `Blocked` (non standard, il ferait
  échouer l'import). Une issue bloquée est `To Do` + label `bloque` /
  `decision-client`, et sa description porte une ligne `Bloqué par:`.
- **Résolution** : `Done`. Sur un Jira classique, la valeur peut s'appeler
  `Fixed` — sans elle les issues terminées restent « non résolues ».
- **Projet *team-managed*** : `Epic Link` s'appelle `Parent`. Le mapping reste
  le même, seul le nom du champ change.

---

## Vagues de travail (labels, pas des sprints)

Aucun sprint n'est créé à l'import — un `Sprint` inconnu en crée un à l'aveugle
sur le board. L'ordre est porté par des labels :

| Label | Contenu | Enjeu |
|---|---|---|
| `vague-1-fiabilisation` | S99, S92, S102, S104, D01, D02 | **Avant toute démo client** |
| `vague-2-genisses` | S110 → S116, D04 (≈ 10,5 j) | La demande métier n°1 de la réunion |
| `vague-3-consolidation` | S31, S60, S103, S105, D03, D05, D06 | À planifier |

Autres labels : `finance` (tous), `phase-1..7` (découpage d'origine),
`reunion-2026-08-05`, `groom-2026-08-07` (issues nées du grooming), `lot-h`,
`decision-client`, `bloque`, `demo-bloquante`.

---

## Si les 44 stories d'origine sont **déjà** dans Jira

N'importez **que** `backlog_finance_delta.csv` (sinon vous doublonnez tout),
puis appliquez ces corrections à la main. Ce sont les écarts entre ce que le
backlog affichait et ce que le code fait réellement.

### Statuts à corriger

| Issue | Affiché avant | Correct | Motif |
|---|---|---|---|
| **FIN-S60** | Livré | **To Do** | Seule la *procédure* (`BASCULE.md`) est livrée. Le critère d'acceptation — « Opening Balance saisis, balance équilibrée » — n'est pas rempli : il attend la date de bascule et les balances réelles. |
| **FIN-S91** | « livré partiellement », décision en attente | **Done** | La saisie des heures, qui manquait, a été livrée par FIN-S96. Plus aucune question ouverte. |
| **FIN-S92** | Livré | **In Progress** | Le dépôt est prêt ; la fusion vers `main` et le rebuild serveur ne sont pas faits. |
| **FIN-S93** | À planifier | **Done** (retitrée « Spécification… ») | Son livrable est la spec, qui est livrée. L'implémentation devient S110→S116. |

### Textes à corriger

| Issue | À retirer / remplacer |
|---|---|
| **FIN-S70** | « Reste à l'exécuter sur une copie de production — **EN ATTENTE DU BACKUP** ». Faux : l'engagement a été pris côté développement (commit `dba011a`, cf. S99). L'exécution devient FIN-S104. |
| **FIN-S86** | « Reste hors périmètre : multi-acheteurs, grille par centrale, prorata intra-mois ». Les deux premiers sont livrés par S94. Ne reste que le prorata → FIN-S103. |
| **FIN-S89** | « Question ouverte : raccourci Workspace à exporter après migrate ». Résolu — le raccourci est bien dans `hmd_agro/fixtures/workspace.json` (vérifié). |
| **FIN-S24** | Le compteur de tests `28/28` était périmé. Les compteurs sortent du backlog (voir plus haut). |
| **FIN-S81 / S84** | « DECISION CLIENT ». Déclassés en points de vigilance par `questions_samir.md` v3 → FIN-D05 et FIN-D06, priorité basse. |

### Rattachements d'epic

Les stories S81, S82, S83, S84, S92, S93, S97, S98, S99 et S101 pointent vers
des epics qui n'existent pas dans Jira. Rattachez-les selon le tableau
« Remappages effectués » ci-dessus, après avoir importé le delta (qui crée les
epics `Exploitation` et `Atelier Genisses`).

---

## Ce que le grooming a trouvé, et qui n'était nulle part

| Nouvelle issue | Trouvaille |
|---|---|
| **FIN-S105** | **Point 13 sur 15 de la liste des changements du 05/08 — « les grosses factures, on les étale sur plusieurs mois » — n'a jamais été transformé en story.** La moitié « imputation à l'utilisation » du même point est couverte par S96 ; l'étalement ne l'est par aucune story. |
| **FIN-S102** | Le DocType `Utilisation Equipement` (livré par S96) n'apparaît **nulle part** dans le workspace : 0 occurrence dans la fixture. Un écran de saisie *quotidienne* qu'aucun utilisateur ne peut atteindre depuis le menu — le reproche exact de la réunion, reproduit. Sans lui, toute la chaîne du coût mécanique reste vide. |
| **FIN-S104** | FIN-S70 mélangeait l'outil (livré) et son exécution sur données réelles (jamais faite). Séparées. |
| **FIN-S103** | Le prorata intra-mois, explicitement mis hors périmètre de S86, n'avait été repris par aucune story. |
| **S110 → S116** | Le découpage interne de la spec génisse numérotait ses stories **S80 à S86** — en **collision frontale** avec les S80-S86 de la réunion, déjà livrées. Un import Jira aurait écrasé sept stories. Renumérotées. |
| **FIN-S113** | Réduite de 2 j à 4 h : la spec prévoyait de créer `Asset.cout_horaire` et le DocType `Utilisation Equipement`, déjà livrés par S91 et S96. |
| **FIN-D01 → D06** | Six décisions/actions externes qui vivaient en prose dans des stories « livrées », donc invisibles dans tout suivi. |

---

## Tenue courante

1. On édite `backlog.py`, jamais les CSV à la main.
2. `python3 jira/backlog.py` régénère les deux fichiers.
3. Le statut va dans `Status`, la preuve de livraison (`Livraison: commit …`)
   dans la description.
4. Après chaque réunion client : une issue par point du compte-rendu, **et on
   vérifie que le compte des points correspond** — c'est ce contrôle qui a
   révélé FIN-S105.
