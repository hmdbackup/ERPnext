---
name: user-story-workflow
description: Le passage obligé de toute User Story du projet HMD AGRO — Definition of Ready avant de coder, Definition of Done avant de clôturer, tels qu'actés en réunion d'équipe du 07/08/2026. Utilise ce skill DÈS QU'une user story, une story, une US, un ticket Jira ou une issue SCRUM-xx / FIN-Sxx entre dans la conversation : qu'on la prépare, qu'on la groome, qu'on l'estime, qu'on la découpe en sous-tâches, qu'on l'implémente, qu'on la termine, qu'on la clôture, ou même qu'on demande simplement « par où je commence sur ce ticket ». Déclenche aussi quand l'utilisateur dit « on commence », « je prends cette US », « c'est fini », « je peux fermer le ticket », « prépare le grooming », ou nomme un ticket sans plus de contexte. Ne pas attendre le mot « user story » : un numéro de ticket suffit.
---

# Workflow User Story — HMD AGRO

## Pourquoi ce skill existe

En réunion du 07/08/2026, animée par **Aymen** (lead / Scrum Master), l'équipe a
arrêté ensemble une **Definition of Ready** et une **Definition of Done**. Les
deux portes ci-dessous sont sa consigne, pas une interprétation : quand un doute
surgit sur le processus, c'est lui qui tranche.

La raison est directe : jusque-là, « terminé »
voulait dire des choses différentes selon la personne. Une story était annoncée
livrée alors que son critère d'acceptation n'était pas rempli ; un écran était
livré mais inatteignable depuis le menu ; le site de démo tournait sur une
version vieille de deux mois parce que le merge n'avait jamais eu lieu.

Chacun de ces incidents correspond à une case de checklist qui n'existait pas.
Les listes ci-dessous ne sont donc pas de la bureaucratie : chaque ligne a été
payée une fois.

## Les deux portes

Une story franchit deux portes. **READY** avant qu'une ligne de code soit
écrite, **DONE** avant qu'on la déclare terminée. Le travail entre les deux est
le développement lui-même.

Quand une story arrive dans la conversation, situe-la d'abord : est-elle en
amont de READY, entre les deux, ou devant DONE ? Puis déroule la porte
concernée. Ne saute pas READY parce que la story « a l'air simple » — c'est
précisément sur les stories qui ont l'air simples que l'écart entre l'attendu
et le fait passe inaperçu.

---

## Porte 1 — Definition of Ready

Six critères. Tant qu'ils ne sont pas remplis, coder revient à parier sur ce
que le métier voulait dire.

| # | Critère | Ce que ça veut dire concrètement |
|---|---|---|
| 1 | **Critères d'acceptation définis et clairs** | Écrits, vérifiables un par un. Une story au statut « Idea » n'en a généralement aucun : les rédiger est alors le premier travail, pas un préalable qu'on suppose fait. |
| 2 | **Maquette partagée avec le métier** | Le rendu attendu a été montré à **M. Samir** (métier) ou à **Aymen** (lead), et validé. Pour un écran : une maquette. Pour un rapport qui existe déjà : une capture suffit et tranche l'écart sans réunion. |
| 3 | **Tests définis** | La liste des cas à couvrir est écrite *avant* le code — y compris les cas limites et les cas d'erreur. |
| 4 | **Technical Grooming** | Le responsable de la story réfléchit à *comment* il va l'implémenter, **avant** de commencer, et **partage sa solution avec l'équipe** pour que quelqu'un puisse proposer mieux ou signaler une impasse. C'est le cœur de la porte. |
| 5 | **Découpage en sous-tâches** | La story est fendue en tâches réalisables et cochables. |
| 6 | **Estimation** | Une charge est posée. Si une inconnue rend l'estimation impossible, dis-le et nomme la sous-tâche qui la lèvera — une estimation inventée est pire que pas d'estimation. |

### Ce que tu peux faire, et ce que tu ne peux pas

Les critères **1, 3, 4, 5** sont préparables ici, en autonomie.

Les critères **2** (validation métier) et **6** quand il dépend de 2 sont des
**portes humaines**. Tu peux préparer la maquette et proposer une estimation,
mais tu ne peux pas les valider à la place de M. Samir. Dis-le explicitement
plutôt que de cocher la case : une DoR auto-déclarée complète est exactement
le mécanisme qui a produit les stories « livrées » dont le critère
d'acceptation n'était pas rempli.

### Le Technical Grooming — ce qu'il doit contenir

Ce n'est pas un résumé d'intention, c'est une solution technique lisible par
un collègue qui pourrait la contester :

- **L'état réel du code** — ce qui existe déjà et qu'on ne réécrira pas.
  Vérifie-le dans le dépôt, ne le suppose pas. Sur ce projet, une part
  importante du travail « à faire » se révèle déjà faite ailleurs.
- **L'approche** — quels fichiers, quels modules, quel gabarit on copie.
- **Les pièges** — la règle métier qu'une implémentation naïve casserait.
  Cherche-les activement : ce sont eux qui justifient le grooming.
- **Les sous-tâches** numérotées.
- **L'estimation**, ou l'inconnue qui la bloque.

**Où il va :** dans les **commentaires** de l'issue Jira. Jamais dans la
description. La règle du projet est que le statut et l'historique vivent dans
les champs structurés ; une description qu'on enrichit devient illisible et
personne ne la relit.

### Annonce

Les stories prises sont annoncées sur le **groupe WhatsApp** (clé + titre), pour
que deux personnes ne préparent pas la même. Propose le message prêt à copier.

---

## Porte 2 — Definition of Done

Neuf critères. Une story n'est terminée que lorsque les neuf sont vrais.

| # | Critère | Comment le vérifier |
|---|---|---|
| 1 | **Chaque fonctionnalité de la description fonctionne** | Reprends la description ligne à ligne. |
| 2 | **Critères d'acceptation atteints** | Un par un, en nommant la preuve. |
| 3 | **Toutes les sous-tâches terminées** | Y compris les tâches ingrates (fixture, raccourci de menu, patch de reprise). |
| 4 | **Code review** avec un collègue | Porte humaine. Tu prépares le diff et le résumé ; un collègue relit. |
| 5 | **Tests unitaires** | Écrits **et exécutés**. Voir « Exécuter les tests » ci-dessous. |
| 6 | **Tests de non-régression (TNR)** | La suite existante repasse. Un test qu'on n'a pas lancé n'est pas un test. |
| 7 | **Test d'acceptation** avec Aymen (lead) ou M. Samir (métier) | Porte humaine. |
| 8 | **Merge sur la branche du sprint** | La branche du sprint, pas `main` — voir la règle de branche. |
| 9 | **Push / sauvegarde** | Le travail est poussé sur le dépôt distant. L'historique Git *est* la sauvegarde. |

Et pour finir : **un message sur le groupe** annonçant que c'est terminé.

### Le principe qui gouverne tout : ni plus, ni moins

On implémente ce qui est dans la User Story — **ni plus, ni moins**. Une bonne
idée trouvée en chemin devient une nouvelle story, pas un ajout discret à
celle-ci. Deux raisons : le périmètre livré reste celui qui a été estimé et
validé, et un ajout non demandé n'a par construction aucun critère
d'acceptation pour le juger.

Quand tu repères un manque hors périmètre, signale-le et propose d'ouvrir une
story. N'élargis pas en silence.

### Ne jamais annoncer une porte franchie qui ne l'est pas

Si les tests n'ont pas tourné, dis « non exécutés » et donne la commande. Si
une sous-tâche est bloquée, dis laquelle et pourquoi. Un rapport de DoD
optimiste coûte plus cher que le retard qu'il masque : c'est ainsi qu'une
story a été marquée livrée alors que son critère d'acceptation attendait
encore des données réelles.

---

## Ancrages projet — HMD AGRO

### Exécuter les tests

Les tests vivent dans `hmd_agro/hmd_agro/tests/`, un module par domaine, chacun
exposant un `run()`. Il n'y a pas de lanceur global : les TNR consistent à
relancer les modules touchés par la story.

```
bench --site hmd.agro execute hmd_agro.hmd_agro.tests.<module>.run
```

Après toute modification de fixture (workspace, custom field, property setter) :

```
bench --site hmd.agro migrate
```

Si `bench` n'est pas disponible dans l'environnement courant, dis-le franchement,
donne les commandes à lancer, et ne présente pas le travail comme testé. Une
vérification syntaxique n'est pas un test.

### Règle de branche

Le merge de fin de story va sur **la branche du sprint**. La fusion vers `main`
et toute action sur le serveur de production se demandent **à chaque fois**, sans
exception — même quand ça semble être la suite évidente du travail.

### Avant de groomer, lis le code

Ce projet a un historique dense et plusieurs backlogs qui ont divergé. Le
statut affiché sur un ticket est régulièrement faux dans les deux sens : des
stories « à faire » sont déjà implémentées, des stories « livrées » ne le sont
pas. Vérifie dans le dépôt avant d'écrire un grooming — c'est là que se trouve
la valeur que tu apportes, et c'est ce qui distingue un grooming utile d'une
paraphrase du titre.

**Et un grooming déjà écrit est une piste, pas une preuve** — y compris le tien.
Rouvre le fichier source plutôt que de recopier une note antérieure. Le cas s'est
produit : une story conclue « largement couverte » sur la foi d'un résumé de la
veille cachait une colonne déclarée à l'écran et jamais remplie, que seule une
relecture du code a fait apparaître. Une synthèse est vraie au moment où elle est
écrite ; le code, lui, est vrai maintenant.

Les skills `hmd-agro-dev` (conventions, où vit le code), `hmd-agro-domain`
(règles métier) et `hmd-agro-kpi` (rapports et indicateurs) sont là pour ça —
appelle celui qui correspond au sujet de la story.

---

## Formats de sortie

### Commentaire de Technical Grooming (à coller dans Jira)

```markdown
## Technical Grooming — <CLÉ> <titre>

### État réel du code
<ce qui existe déjà, avec les chemins de fichiers ; « rien » est une réponse valable>

### Approche
<comment on l'implémente, quels fichiers, quel gabarit>

### Pièges
<les règles que l'implémentation naïve casserait>

### Sous-tâches
1. …
2. …

### Estimation
<charge, ou l'inconnue qui la bloque et la sous-tâche qui la lèvera>
```

### Rapport de fin de story

Reprends les neuf critères, chacun avec son état réel et sa preuve. Sépare
nettement ce qui est fait de ce qui reste — notamment les portes humaines
(code review, test d'acceptation) et tout ce qui n'a pas pu être exécuté.

### Checklist DoR (à coller dans Jira)

```markdown
## Definition of Ready — <CLÉ>
- [ ] Critères d'acceptation définis et clairs
- [ ] Maquette partagée avec le métier
- [ ] Tests définis
- [ ] Technical Grooming fait et partagé avec l'équipe
- [ ] Découpage en sous-tâches
- [ ] Estimation
```

### Checklist DoD (à coller dans Jira)

```markdown
## Definition of Done — <CLÉ>
- [ ] Chaque fonctionnalité de la description fonctionne
- [ ] Critères d'acceptation atteints (ni plus, ni moins)
- [ ] Toutes les sous-tâches terminées
- [ ] Code review avec un collègue
- [ ] Tests unitaires écrits et exécutés
- [ ] Tests de non-régression passés
- [ ] Test d'acceptation avec le lead ou M. Samir
- [ ] Merge sur la branche du sprint
- [ ] Push / sauvegarde sur le dépôt distant
- [ ] Message de fin posté sur le groupe
```
