# Expliquer les trois user stories

*Pour toi. Comment raconter SCRUM-9, 10 et 11 à quelqu'un qui n'en sait rien.*

---

## La forme qui marche, pour n'importe quelle US

Une user story se raconte en quatre temps. Toujours les mêmes, toujours dans
cet ordre. Si tu tiens cet ordre, tu ne peux pas mal l'expliquer.

1. **Le manque** — ce qu'on ne pouvait pas faire, ou ce qu'on faisait faux.
   Jamais « j'ai ajouté un rapport ». Toujours « on ne savait pas X ».
2. **Ce que ça change** — la phrase du gérant, pas celle du développeur.
3. **Le chiffre** — un seul, celui qui rend la chose palpable.
4. **La règle qu'on ne voit pas** — le piège métier que l'écran évite.
   C'est ce quatrième point qui fait la différence entre quelqu'un qui a codé
   un tableau et quelqu'un qui a compris le métier.

Ce qu'il ne faut jamais faire : commencer par les colonnes. Personne ne retient
une liste de colonnes. Tout le monde retient « le coût du litre était faux ».

---

## SCRUM-10 — Rapport mensuel sur les coûts

*C'est la plus importante des trois. Commence toujours par celle-là.*

### Le manque

> « Le coût du litre qu'on affichait était faux. Pas approximatif : faux. »

Il divisait **toutes** les charges de la ferme — génisses, cultures fourragères,
traction, frais généraux, frais financiers — par les **seuls** litres de lait.

Le détail qui fait comprendre : les cinq ateliers existaient déjà, et les
écritures comptables portaient bien leur atelier. C'est la **lecture** du Grand
Livre qui ne s'en servait pas. Le renseignement était là, dans la base, et
personne ne le lisait.

### Ce que ça change

> « Maintenant chaque charge est rangée dans son atelier, et le coût du litre
>  ne retient que ce qui concerne le lait. »

### Le chiffre

Sur juin : **112 100 DT** de charges totales sur la ferme. Le coût du litre
n'en retient plus que **70 984** — le reste appartient aux génisses, aux
cultures et à la traction. On divisait par le lait un tiers de charges de trop.

### La règle qu'on ne voit pas — le double comptage

C'est le point qui prouve que tu as compris.

Le rapport affiche un « coût d'utilisation mécanique ». Il est **volontairement
exclu** du coût complet. Pourquoi : le coût horaire d'un tracteur agrège
l'amortissement, l'entretien et le mazout — or ces trois-là sont **déjà** dans
les charges du Grand Livre (comptes 68x, 615, achats de carburant). Les
additionner compterait deux fois la même dépense.

C'est une vue analytique, pas une charge de plus. Le libellé le dit à l'écran,
et un test automatisé empêche qu'on le casse par mégarde.

**Si quelqu'un demande « pourquoi vous ne l'ajoutez pas au total ? »** — c'est
la question piège, et tu as la réponse : parce qu'on paierait deux fois le même
tracteur.

### La deuxième règle — « non imputé » reste affiché

Une écriture sans atelier n'est **jamais** répartie d'offle fichier d'explication des US, je le veux en fichier HTMLice. Elle apparaît sur
une ligne « non imputé », visible **même à zéro**. Une charge qu'on ne sait pas
ranger doit se voir ; fondue dans un total, elle disparaît du regard.

Après la décision de M. Samir, cette ligne devient un **contrôle** : l'atelier
sera obligatoire à la saisie, donc la ligne doit rester à zéro. Si elle bouge,
c'est qu'une écriture est passée à travers.

### Ce que ça ne fait pas

Ce n'est pas de la comptabilité. Le rapport **lit** le Grand Livre, il n'y écrit
rien. Les charges y entrent par les écrans habituels d'ERPNext — factures
d'achat, écritures diverses, paie.

---

## SCRUM-11 — Rapport mensuel sur les interventions

### Le manque

> « On ne savait pas ce que coûte l'entretien du matériel, machine par machine. »

Et surtout : on ne savait pas si l'entretien payé en comptabilité correspondait
à l'entretien réellement fait sur les machines.

### Ce que ça change

Trois blocs dans un seul écran : ce qui a été fait, ce qui arrive sous 30 jours,
et le rapprochement au compte 615 de la comptabilité.

### Le chiffre

Juin : cinq interventions sur quatre équipements. **1 855 DT de pièces + 860 DT
de main-d'œuvre = 2 715 DT**, et le compte 615 du Grand Livre affiche exactement
2 715. **Écart : 0,00** — tout est rattaché à une machine.

### La règle qu'on ne voit pas — l'écart est l'information

C'est le point le plus contre-intuitif des trois stories, et le plus utile.

Deux sources coexistent et **ne peuvent pas coïncider** :
- une facture d'entretien passée en comptabilité sans intervention rattachée
  gonfle le 615 sans toucher les interventions ;
- une intervention faite en interne (coût 0) fait l'inverse.

Donc l'écart est **normal**. Et c'est lui le renseignement utile : « 400 DT
d'entretien qui ne sont rattachés à aucune machine ». N'afficher qu'un seul des
deux montants transformerait un outil de pilotage en outil rassurant.

**Quand tu dis « écart 0,00 »**, ne dis pas « c'est bon ». Dis : « ce mois-ci
tout est rattaché — et le jour où ça ne l'est pas, on le verra ».

### Ce que ça ne fait pas

Le rapport ne crée pas les interventions. Elles sont saisies dans l'écran
« Asset Repair » d'ERPNext, avec trois champs qu'on a ajoutés : le type
d'intervention, l'intervenant, et la référence HMD.

---

## SCRUM-9 — Rapport mensuel sur la production laitière

*Celle-ci n'est pas validée. Explique-la quand même — le travail est fait, c'est
la décision métier qui manque.*

### Le manque

> « Le même lait est compté à deux endroits, et les deux ne disent pas pareil. »

Les **traites** — ce que la machine relève, matin et soir, vache par vache.
Le **bilan de la ferme** — ce que quelqu'un écrit sur la journée, ce qu'on
retrouve au tank.

### Le chiffre

Juin : **45 444 L** côté traites, saisis 30 jours sur 30. **35 485 L** côté
bilan de la ferme, saisis 26 jours sur 30. Écart : **9 959 L**.

M. Samir a tranché : cet écart n'est pas un sujet, il n'y a aucune alerte à
construire dessus. Ce qui reste à trancher, c'est **lequel des deux fait
référence** — parce que tous les ratios en dépendent.

### La règle qu'on ne voit pas — la couverture est devenue plus sévère

Avant, un jour comptait comme « saisi » s'il portait une traite **ou** un bilan.
Résultat : un mois pouvait afficher « 31 jours sur 31 » alors que la ventilation
vendu / auto-consommé / veaux était entièrement vide — donc que le rapprochement
comptable était impossible.

Maintenant il faut les **deux**. Sur juin, la couverture passe de 30/30 à
**26/30**. Ce n'est pas une régression : c'est la vérité de la saisie, qu'on ne
voyait pas.

**C'est un bon exemple à raconter** : l'indicateur qui rassure est pire que pas
d'indicateur du tout.

### La deuxième règle — vide n'est pas zéro

Un jour non saisi affiche une cellule **vide**, jamais un 0. Un zéro voudrait
dire « ce jour-là on n'a rien produit », ce qui est faux et fait mentir toutes
les moyennes. Vide veut dire « on ne sait pas », et le jour sort du
dénominateur.

### Le bloquant, et il n'est pas de ton fait

Aucun vêlage n'est enregistré sur juin dans les données importées. Sans vêlage,
le système ne sait pas quelles vaches sont en lactation : **VL = 0**, donc le
litres/vache/jour reste vide.

Ça ne dépend pas du code. Tant que les dates de vêlage ne sont pas importées,
cette colonne ne peut rien afficher — quelles que soient les décisions prises
par ailleurs.

---

## La question ouverte — comment la raconter

C'est celle des frais généraux. Voici l'ordre qui la rend limpide.

**1. Le problème.** Le gardien, l'électricité, l'assurance servent à toute la
ferme. Pour en donner une part au lait, il faut une règle.

**2. Ce qui existait.** Une seule règle pour tout : la part du lait dans les
charges directes, soit **62 %**. Posée une fois, appliquée à tout.

**3. Ce que M. Samir a décidé.** Cas par cas. Chaque dépense porte sa propre
clé — soit au prorata de ce que l'atelier **dépense** (62 %), soit au prorata de
ce qu'il **rapporte** (90 %). Le gardiennage et l'administratif suivent les
recettes ; l'électricité et l'assurance suivent les dépenses.

**4. Ce que ça vaut.** Et c'est là que ça devient concret :

| | Quote-part Lait | Coût du litre |
|---|---|---|
| Clé unique (aujourd'hui) | 6 100,68 DT | 1,529 DT/L |
| Cas par cas (sa décision) | 7 584,75 DT | 1,562 DT/L |

**Écart : 32,7 millimes par litre. Sur une année, environ 17 800 DT.**

Sa décision de lundi n'était pas un détail d'affichage : elle déplace le coût de
revient de trois centimes par litre.

**5. Le manque.** Ce choix n'a nulle part où s'inscrire : ni champ sur la
dépense, ni écran pour arbitrer le mois. D'où la question — **qui** arbitre, et
**quand** ? À la saisie, c'est un champ sur la facture. À la clôture, c'est un
écran.

---

## Les trois phrases à savoir par cœur

Si on te demande « c'est quoi ces trois tickets ? » dans un couloir :

> **SCRUM-10** — « Le coût du litre était faux : il divisait toutes les charges
> de la ferme par les seuls litres de lait. Maintenant chaque charge est rangée
> dans son atelier. »

> **SCRUM-11** — « On ne savait pas ce que coûte l'entretien machine par
> machine, ni si la comptabilité et le terrain disaient la même chose.
> Maintenant l'écart entre les deux est affiché. »

> **SCRUM-9** — « Le lait est compté à deux endroits qui ne disent pas pareil.
> L'écran montre les deux au lieu d'en choisir un en silence. »

---

## Les cinq questions qu'on va te poser

**« Ça a pris combien de temps ? »**
Estimé 1 j pour SCRUM-9, 2 j pour SCRUM-10, 1 j 4 h pour SCRUM-11. SCRUM-10
avait d'abord été estimée 4 h — j'ai corrigé l'estimation en cours de grooming
après avoir vérifié que la ventilation par atelier n'existait pas du tout.

**« Comment on sait que c'est juste ? »**
39 modules de test, dont deux écrits pour ces stories. 25/25, 33/33, 41/41.
La suite complète relancée sur les données réelles : aucune régression nouvelle.
Et un test protège spécifiquement la règle du non-double-comptage.

**« C'est utilisable maintenant ? »**
Les deux écrans validés sont développés, testés et poussés sur la branche du
sprint, et leurs raccourcis sont dans le menu HMD AGRO. Il reste la relecture
par un collègue, et les trois ajouts que les décisions de lundi ont créés.

**« Pourquoi trois maquettes si les écrans existent déjà ? »**
Parce que la maquette n'est pas là pour montrer l'écran : elle est là pour
rendre les choix **désignables**. Deux versions côte à côte, on pointe. C'est
plus rapide qu'une réunion où chacun décrit ce qu'il imagine.

**« Qu'est-ce qui reste ? »**
Trois choses, toutes nées des décisions de lundi : la clé par dépense, la
séparation pièces / main-d'œuvre sur les interventions, et le champ État sur la
fiche équipement. Aucune n'existe aujourd'hui dans le code.

---

## Le piège pendant la démonstration

Les maquettes montrent **la cible**, pas l'écran d'aujourd'hui. Trois choses y
figurent qui ne sont pas encore développées :

| Sur la maquette | Dans le code aujourd'hui |
|---|---|
| Pièces et main-d'œuvre en deux colonnes | une seule colonne « coût » |
| Colonne État du matériel | n'existe nulle part |
| Une clé par dépense | une clé unique pour tous les frais généraux |

Dis-le **avant** qu'on te le demande, une fois, calmement. Ça te coûte dix
secondes et ça te protège entièrement.
