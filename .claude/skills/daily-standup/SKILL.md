---
name: daily-standup
description: Rédige le statut quotidien HMD AGRO à poster sur WhatsApp avant le daily de 10h, à partir de ce qui a réellement été fait — toutes les sessions Claude du projet, les commits git et les dailies précédents. Déclenche dès que Mohamed dit « donne le message daily », « le statut », « mon daily », « statut du jour », « qu'est-ce que j'ai fait hier », « prépare ma journée », « le stand-up », « à poster sur le groupe », ou demande un récapitulatif de la veille / de la semaine sur HMD AGRO. Déclenche aussi quand il demande un point d'avancement à envoyer à Aymen, au boss ou à l'équipe. Ne pas attendre le mot « daily » : « statut » ou « t'as fait quoi hier » suffit.
---

# Daily stand-up — HMD AGRO

## L'obligation

Depuis le 05/08/2026, le boss exige **chaque jour** un statut écrit posté sur
WhatsApp **avant le daily de 10h**. Trois points, pas un de plus : ce qui a été
fait la veille, ce qui sera fait aujourd'hui, les blocages.

Le message est lu par des gens qui ne lisent pas le code : Aymen (lead / Scrum
Master), le boss, l'équipe. Ils veulent savoir ce qui avance, ce qui les
concerne, et qui doit bouger pour débloquer.

## La règle qui gouverne tout : ne rapporter que ce qui est prouvé

Le message engage Mohamed devant son équipe. Une ligne annoncée « faite » qui ne
l'est pas se paie au sprint suivant. Donc chaque affirmation du point 1 doit
s'appuyer sur une **trace** : un commit, un fichier écrit, un test qui est passé,
un commentaire posté sur Jira, un document envoyé.

Ce qui n'est **pas** une preuve de livraison :

- du code écrit mais non commité — c'est « en cours », pas « fait » ;
- des tests écrits mais jamais exécutés — dire « écrits », pas « verts » ;
- une branche non fusionnée — le reste de l'équipe ne l'a pas ;
- un fichier non suivi par git (`??` dans le statut) — un brouillon.

Le vocabulaire suit la preuve : *rédigé / écrit / en cours / commité / testé /
livré*. Ne jamais monter d'un cran par confort.

## Procédure

### 1. Collecter

```bash
python3 .claude/skills/daily-standup/scripts/collect_activity.py
```

Le script balaie **tous** les répertoires de transcripts Claude du projet
(`~/.claude/projects/*hmd*agro*`, y compris les copies ouvertes depuis un autre
dossier), et sort un digest : sessions de la fenêtre avec leur titre, les
demandes de Mohamed, les fichiers écrits, les tickets cités — puis les commits
git, le travail non commité, les commits non poussés, et les dailies déjà postés.

Fenêtre par défaut : hier 00h00 → maintenant. Après un week-end ou une absence,
élargir : `--days 3`, ou `--since 2026-08-04 --until 2026-08-06`.

### 2. Lire les traces, pas seulement les titres

Le digest donne la matière brute ; le travail est de la trier.

- Les **demandes de Mohamed** disent ce qu'il voulait ; les **fichiers écrits**
  et les **commits** disent ce qui est sorti. Quand les deux divergent, c'est le
  second qui compte.
- Une session peut avoir tourné longtemps sans rien produire (exploration,
  configuration, débogage d'environnement) : ça se raconte en une demi-phrase,
  ou pas du tout.
- Si un point reste flou après lecture — un fichier modifié sans qu'on sache si
  ça marche, un test jamais lancé — ouvrir le fichier ou le commit concerné
  plutôt que de deviner. Une question à Mohamed vaut mieux qu'une affirmation
  fausse.
- Rattacher chaque élément à un ticket (`SCRUM-xx`, `FIN-Sxx`) quand il en
  existe un : l'équipe suit le sprint par les tickets. En cas de doute sur
  l'état réel d'un ticket, le lire via l'MCP Atlassian (`getJiraIssue`).

### 3. Vérifier les promesses de la veille

Le digest rappelle les dailies déjà postés. Ce qui a été annoncé hier au point 2
doit apparaître aujourd'hui au point 1 — soit fait, soit explicitement reporté
avec sa raison. Un engagement qui disparaît sans un mot, ça se remarque.

### 4. Composer les trois points

Le format ci-dessous est celui qui a été retenu à l'usage. Bloc de texte brut,
sans markdown (WhatsApp ne le rend pas), prêt à copier :

```
Bonjour à tous — statut du JJ/MM

1) Hier : <ce qui est sorti, rattaché aux tickets, du plus visible au moins visible>

2) Aujourd'hui : <l'intention du jour, concrète et tenable>

3) Blocages : <ce qui bloque + qui peut débloquer ; ou « rien de bloquant » + les attentes>
```

**Point 1 — Hier.** Deux ou trois éléments, pas l'inventaire. Ce qui intéresse
l'équipe passe devant : une fonctionnalité utilisable, un ticket qui change
d'état, un livrable envoyé. La plomberie interne se résume ou se tait.

**Point 2 — Aujourd'hui.** Un engagement, donc calibré sur la journée réelle. Si
Mohamed a cours, un examen, un déplacement, l'annoncer (« journée légère ») vaut
mieux qu'une promesse ratée. **Ne jamais y inscrire une action qui demande un
feu vert non encore donné** — fusion vers `main`, action sur le serveur de la
ferme : ces deux-là se demandent à chaque fois, et n'ont rien à faire dans un
engagement public tant que l'accord n'est pas là.

**Point 3 — Blocages.** Un blocage sans nom ne se résout pas. Nommer la personne
ou la chose attendue : validation métier de M. Samir, export de données d'Aziz,
arbitrage d'Aymen, environnement de démo. Et distinguer *bloquant* (le travail
s'arrête) de *en attente* (ça avance quand même). S'il n'y a rien de bloquant,
le dire — ce n'est pas un aveu de faiblesse.

Ton : première personne, factuel, sobre. Pas d'emoji décoratif, pas
d'auto-félicitation, pas de jargon technique que Samir ou le boss ne peuvent pas
lire. Chaque point tient en une à trois lignes.

### 5. Livrer

Sortir **un seul** bloc prêt à coller, dans un bloc de code pour que la copie
soit propre. Puis, en dehors du bloc et en deux lignes maximum :

- ce qui reste à trancher avant l'envoi (une date, un nom, une décision) ;
- une variante seulement si un choix réel se pose (par exemple : mettre en avant
  une demande de réunion, ou rester en asynchrone).

Ne pas noyer le message sous des options. Un daily, pas un catalogue.

### 6. Archiver

Une fois le message validé par Mohamed, l'écrire dans
`.claude/daily/AAAA-MM-JJ.md` (créer le dossier au besoin). C'est ce que le
script relira demain pour vérifier les promesses tenues et éviter les
répétitions.

## Si Mohamed enchaîne sur « et je fais quoi aujourd'hui ? »

Le digest contient déjà de quoi répondre : tâches non terminées, fichiers
modifiés non commités, tickets non READY, engagements de la veille non tenus.
Proposer trois actions maximum, ordonnées par ce qui débloque le plus de monde —
une action qui libère trois US passe devant un correctif isolé. Le skill
`user-story-workflow` donne les portes DoR/DoD si une story est concernée.
