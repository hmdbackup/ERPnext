# Conducteur — présentation des maquettes validées, mardi 25 août 2026

*Pour toi, avant d'entrer. Pas pour l'auditoire.*
Support : les trois blocs ouverts dans Excalidraw + l'écran d'arbitrage.

---

## La différence avec lundi

Lundi tu posais des questions. Aujourd'hui tu montres les réponses **rendues** :
ce que ses décisions donnent une fois appliquées, avec les chiffres qui bougent.

Et une chose de plus, qui change tout : **ils ne savent rien de ce que tu as
fait**. Trois tickets au statut *Idea* depuis le 8 août, aucun message de fin.
Cette réunion est le moment où le travail acquiert un témoin. Ne la traite pas
comme une revue de maquettes.

---

## En une phrase

> « Le coût du litre qu'on affichait était faux. Je l'ai corrigé, et voilà ce que
> tes décisions de lundi donnent une fois appliquées. Il me reste une question. »

Si on te coupe après dix secondes, c'est celle-là qui doit être passée.

---

## Le déroulé — 15 minutes

### 1. Le constat, avant toute maquette (2 min)

Ne commence pas par un écran. Commence par ce que tu as trouvé :

> « Avant, le coût complet au litre divisait TOUTES les charges de la ferme —
>  génisses, cultures, traction, frais généraux — par les seuls litres de lait.
>  Les cinq ateliers existaient, les écritures les portaient : c'est la lecture
>  du Grand Livre qui ne s'en servait pas. Le chiffre était affiché. Personne ne
>  savait de combien il était faux. »

C'est le seul moment où tu parles de toi. Deux phrases, puis tu passes.
Si quelqu'un demande « de combien ? » : le coût complet retenu est aujourd'hui
1,562 DT/L sur le périmètre Lait + quote-part. L'ancien calcul prenait
112 100 DT de charges au lieu de 70 984 — un tiers de trop.

### 2. SCRUM-10 — charges par atelier et coût du litre (4 min)

Montre l'écran, puis **les deux cadres verts** : c'est ce qu'il a décidé.

- « Tu as dit : arbitrage cas par cas, pas de clé unique. Résultat : chaque
  dépense générale porte sa clé, écrite en toutes lettres. »
- « Tu as dit : aucune charge non attribuée. Résultat : la ligne reste, mais à
  zéro — c'est un contrôle, pas une catégorie. »

Le chiffre à faire voir : **9 840 DT de frais généraux, dont 7 583,89 pour le
Lait**, et c'est ce montant qui entre dans le coût du litre.

### 3. SCRUM-11 — parc et interventions (3 min)

Même geste : l'écran, puis le cadre vert.
- un seul mot par équipement : Prêt / En panne / En attente de maintenance ;
- préventif à 30 jours ;
- pièces et main-d'œuvre séparées.

Le chiffre : pièces 1 855 + M.O. 860 = 2 715, et le rapprochement au compte 615
tombe à **écart 0,00**. C'est ça qui prouve que rien n'est perdu.

### 4. SCRUM-9 — celui qui reste ouvert (2 min)

Ne le cache pas, et ne t'en excuse pas. Dis-le comme un fait :

> « Celui-là, tu ne l'as pas validé. Je l'ai quand même remonté en entier pour
>  qu'on voie sur quoi on bute. »

Deux points seulement :
- acquis : l'écart de 9 959 L n'est pas un sujet, aucune alerte à construire ;
- bloquant, et pas de mon fait : aucun vêlage saisi sur juin, donc 0 vache
  lactante et le litres/vache/jour reste vide. Ça ne dépend pas du code.

### 5. La question du jour — l'écran d'arbitrage (3 min)

C'est le seul moment où tu attends une réponse.

> « Le cas par cas, il faut bien que quelqu'un le fasse quelque part. Aujourd'hui
>  ce choix n'a ni champ ni écran. Deux formes possibles. »

Montre l'écran d'arbitrage, puis la variante en dessous :
- **à la clôture** → cet écran, la liste du mois, on coche A ou B par dépense ;
- **à la saisie** → pas d'écran du tout, deux boutons sur la facture.

Puis la question, dans cet ordre : **qui arbitre — le comptable ou toi ?**
La réponse au « qui » donne le « quand », et le « quand » donne la forme.
Ne propose pas ta préférence avant qu'il ait répondu.

### 6. Clôture (1 min)

> « Le développement des deux écrans validés est fait, testé et poussé. Ce qui
>  reste : la relecture par un collègue, et les trois ajouts que vos décisions
>  ont créés. »

---

## Le piège à ne pas tomber dedans

**Les maquettes montrent la cible, pas l'écran d'aujourd'hui.** Trois choses y
figurent qui ne sont PAS dans le code :

| Sur la maquette | Dans le code |
|---|---|
| Pièces et M.O. en deux colonnes | une seule colonne « coût » |
| Colonne État du matériel | n'existe nulle part |
| Une clé par dépense | une seule clé pour tous les frais généraux |

Si quelqu'un ouvre le vrai rapport pendant la réunion et ne les voit pas, tu es
pris en défaut. Donc dis-le **avant** qu'on te le demande, une fois, calmement :

> « Ce que vous voyez là, c'est la cible après vos décisions de lundi. Trois
>  choses sont encore à construire — je les ai listées. »

Ça te coûte dix secondes et ça te protège complètement.

---

## Ce que tu demandes en sortant

1. La réponse sur qui arbitre la clé (M. Samir ou Aymen).
2. Un créneau de code review avec un collègue — c'est la dernière porte
   humaine avant que les deux stories soient Done.
3. L'inventaire réel du parc côté Aziz : un seul équipement est saisi
   aujourd'hui, l'écran ne peut pas dire vrai sans lui.

---

## À faire AVANT d'entrer

Coller les trois commentaires de DoD dans Jira et sortir SCRUM-10 et SCRUM-11
du statut *Idea*. Sinon quelqu'un ouvre le board pendant que tu parles et voit
trois tickets qui n'ont pas bougé depuis dix-sept jours.
