# Conducteur — présentation de l'affiche de stage (version courte, 3 à 4 minutes)

> Version longue pour la soutenance de 25 minutes (18 min de parole, 7 min de
> questions, partie par partie de l'affiche) : `passation/07_stage/conducteur_affiche_photos.html`,
> régénéré par `python3 outils_affiche/build_guide_photos.py`.

À dire tel quel, en pointant les zones de l'affiche. Les crochets = gestes.

## Version 30 secondes (si la personne ne fait que passer)

« J'ai passé mon stage chez HMD AGRO, une ferme laitière en Tunisie. Mon
mandat : construire leur système de gestion sur ERPNext, un ERP open source.
J'ai livré tout le volet finance — comptabilité, coût du litre de lait, paie,
amortissements — testé par 521 tests automatisés, et c'est en production à la
ferme aujourd'hui. »

## Version complète

### 1. Accroche (~20 s) — [devant l'en-tête]

« Bonjour, je suis Mohamed Slim, étudiant au baccalauréat en informatique.
Cet été, j'ai fait mon stage comme développeur ERP chez HMD AGRO — c'est une
ferme laitière située à Mateur, dans le nord de la Tunisie. »

### 2. Le contexte et le mandat (~40 s) — [section 1 puis 2]

« La ferme gère un troupeau de vaches laitières : la production de lait, la
reproduction, la santé animale, le matériel agricole. Tout ça se pilotait sur
Excel. Mon mandat, c'était de développer leur application de gestion sur
ERPNext, un ERP open source, avec le framework Python qui est derrière,
Frappe. [montre les deux logos]

Concrètement, on m'a confié le volet finance : mettre en place la
comptabilité, calculer ce que coûte réellement un litre de lait, automatiser
la paie et les amortissements, et sortir les indicateurs économiques pour le
gérant. »

### 3. Ce que j'ai construit (~60 s) — [section 3, puis les captures à droite]

« En trois mois, j'ai livré le socle comptable tunisien — 77 comptes, la TVA,
cinq centres de coûts, un par atelier de la ferme. Ensuite, toute la chaîne :
les consommations d'aliments valorisées au coût moyen pondéré, la facturation
du lait avec une grille de prix selon la qualité, la paie ventilée par
atelier, et les amortissements du matériel.

[passe aux captures] Là vous voyez le système réel : le rapport d'indicateurs,
qui se colore en vert, orange ou rouge selon des seuils configurables ; le
coût de revient du litre ; une facture de lait ; l'amortissement du matériel.

[troisième rangée] Et la dernière livraison, cette semaine : les frais
généraux — électricité, eau, assurances — sont ventilés entre les ateliers par
une clé de répartition fixée une fois : 60 % lait, 25 % cultures, 15 %
génisses. Quand le comptable valide une facture, il n'a rien à saisir :
ERPNext éclate lui-même les écritures — 900, 375, 225 sur 1 500 — et le
rapport vérifie que les écritures égalent la clé, zéro écart. [montre la clé,
puis le Grand Livre, puis la ligne « Contrôle » du rapport]

[en bas à gauche] Et ici, ce que je trouve le plus parlant : chaque vache du
troupeau est immobilisée à l'actif comptable, individuellement, avec son
numéro de travail. [montre la capture du cheptel]

Le tout est couvert par 521 tests automatisés, tous verts, et déployé en
Docker sur le serveur de la ferme. »

### 4. Comment j'ai travaillé (~30 s) — [section 4]

« J'ai travaillé en Scrum : un daily chaque matin, un backlog Jira, et des
revues régulières avec le client. Je faisais les maquettes des écrans, je les
faisais valider, puis je développais. Ça m'a appris à traduire un besoin
métier réel — la comptabilité d'un élevage, un domaine que je ne connaissais
pas — en fonctionnalités livrées et testées.

Un exemple : pour les frais généraux, j'avais d'abord construit une table de
répartition à remplir sur chaque ligne de facture. À la revue du 3 septembre,
mon superviseur m'a fait quatre remarques — le vocabulaire, la redondance, le
volume de saisie, et surtout : « est-ce que ça se retrouve dans les écritures
comptables ? ». J'ai jeté ma table et je me suis appuyé sur une fonction
native d'ERPNext, la Cost Center Allocation. Livré le jour même, 45 tests. »

### 5. Résultat et conclusion (~30 s) — [section 5]

« Aujourd'hui le module finance est opérationnel : le gérant voit chaque
période son coût du litre, son excédent brut d'exploitation, sa marge sur coût
alimentaire — calculés automatiquement à partir des saisies quotidiennes.

Ce que je retiens du stage : la responsabilité de bout en bout, du besoin
jusqu'à la mise en production, sur des données réelles, avec un vrai client.
Merci ! »

## Questions probables — réponses courtes

**« C'est quoi ERPNext ? »**
« Un ERP open source complet — comptabilité, stock, actifs — bâti sur Frappe,
un framework web en Python. Plutôt que tout coder de zéro, je configure et
j'étends : je crée des DocTypes personnalisés, des hooks, des rapports. »

**« Vous avez fait ça seul ? »**
« Le développement du volet finance, oui. Mais encadré : mon superviseur
Aymen Zarrad, et le client, M. Samir, qui validait chaque livraison en revue.
Les corrections sortaient de ces revues. »

**« La plus grosse difficulté ? »**
« Le domaine métier. Un exemple : les charges patronales sont passées de
16,57 % à 30 % en cours de stage. Ma première version figeait l'ancien taux
partout. Je l'ai détecté moi-même en audit avant la revue client, et j'ai
repris le modèle : le changement de taux est un événement daté, et chaque
fiche de paie se recalcule. C'est le genre de subtilité qu'on n'apprend qu'avec
des données réelles. »

**« La clé de répartition, c'est du code à vous ? »**
« Non, et c'est le point : la clé elle-même est native ERPNext. Ce que j'ai
écrit, c'est autour : le bandeau qui prévient le comptable de la clé en
vigueur, l'avertissement si une charge n'a aucune clé à sa date, la section
du rapport qui rejoue la clé contre le Grand Livre pièce par pièce, et le
centre de coûts posé automatiquement sur chaque mouvement de stock — une
ration de vaches va au Lait, pas aux frais généraux. »

**« Pourquoi 521 tests ? »**
« Parce que c'est de la comptabilité : un calcul faux, c'est une décision
fausse pour le gérant. Chaque règle de gestion a ses tests, plus un test de
bout en bout qui rejoue une période complète de la ferme. »

**« Pourquoi pas Excel ? »**
« C'est ce qu'ils avaient. Ça ne croisait pas les données : impossible de
relier le lait produit, l'aliment consommé et la paie pour sortir un coût du
litre fiable. L'ERP le fait automatiquement. »

## Conseils

- Le chiffre à placer à voix haute au moins une fois : **521 tests verts**.
- L'anecdote des 30 % de charges patronales est ta meilleure histoire — garde-la
  pour les questions, elle montre la rigueur.
- La seconde histoire, c'est la revue du 03/09 : savoir jeter sa conception
  pour le natif. Elle est déjà dans la version complète (section 4) ; en 30
  secondes, ne la raconte que si on te demande « le plus dur ».
- Régénérer l'affiche : `python3 outils_affiche/build_affiche.py` (part de
  `affiche_v1_sauvegarde.pptx`, écrit dans ~/Downloads), aperçu via Keynote :
  `open -a Keynote` puis export PDF du document au premier plan.
- Si un évaluateur technique insiste : DocTypes, hooks `validate`/`on_submit`,
  fixtures, patches de migration, MariaDB — tu as tout pratiqué.
