# Questions pour M. Samir — suite de la réunion du 05/08/2026

Mise à jour du 06/08 : la transcription intégrale a répondu à une partie des
questions initiales (§B). Ne restent que les 5 questions du §A.

## A. Questions encore ouvertes (un « OK » par ligne suffit)

### 1. Numéros provisoires au vêlage
Les veaux reçoivent automatiquement un numéro temporaire dans la plage
**99999xxxxx** (10 chiffres), remplacé ensuite par la boucle officielle via le
bouton « Enregistrer boucle officielle ». La transcription confirme que les
boucles réelles commencent par 999 (ex. 999 000 122 = 9990000122) — la plage
99999 ne serait atteinte par la série officielle qu'après ~10 millions de
boucles émises.
**Question : confirmer auprès de l'autorité d'identification qu'aucune boucle
officielle ne commence par 99999.** Sinon, quel préfixe réserver ?

### 2. Primes et charges sociales
- **Q2a :** les primes (Aïd, rendement…) entrent-elles dans l'assiette des
  charges patronales (30 %) pour les salariés soumis CNSS ?
  *Défaut actuel : oui.*
- **Q2b :** une prime saisie après le postage des salaires du mois est refusée
  (il faut annuler/régulariser l'écriture d'abord). Ce comportement
  convient-il, ou faut-il un flux de régularisation dédié ?

### 3. Heures d'utilisation des équipements
Le coût horaire est prêt (25 DT/h par défaut, réglable par équipement —
option 2 retenue en réunion). Pour l'imputer, il faut capturer les heures
(« le Bobcat travaille 1 h ou 2 h dans la zone génisses »).
**Question : comment saisir les heures ?**
a) relevé périodique du compteur horaire sur la fiche équipement *(recommandé,
le plus simple)* ; b) heures saisies à chaque utilisation/intervention ;
c) saisie journalière par atelier.

### 4. Coût génisse — deux points comptables
- **Q4b :** comptes de cession interne proposés 6061 / 7068x — à valider avec
  l'expert-comptable (hors états officiels).
- **Q4e :** taux de perte initial (mortalité + infertilité) pour l'aide à la
  décision (proposition : 8 %), en attendant l'historique réel ?

### 5. Valorisation du lait interne : coût ou marché ?
Historiquement vous valorisiez le lait bu par les génisses au **coût du
litre** (transcription : « on estime le coût du litre, donc on multiplie »).
L'outil peut faire au choix : coût du litre (reflète la dépense réelle) ou
prix de vente moyen (coût d'opportunité — ce que ce lait aurait rapporté).
**Question : lequel retenir par défaut ?** *(proposition : coût du litre hors
amortissement, conforme à votre pratique, avec le manque à gagner affiché à
titre indicatif).*

## B. Répondu par la transcription intégrale (pour validation, pas de blocage)

1. **Multi-acheteurs : besoin ACTUEL, pas futur.** Le lait part vers 3
   destinations : 2 acheteurs externes payants + l'atelier génisses en
   interne ; chaque acheteur doit avoir son profil de prix (prix unique OU
   paliers), règlement en fin de mois, prix temporaire accepté le temps de
   finaliser avec l'acheteur. → passe en priorité (story FIN-S94).
2. **Pas de paiement à la qualité aujourd'hui** (« on fait pas à base de
   qualité, peut-être qu'on y reviendra ») : la grille TB/TP reste prête mais
   n'est pas bloquante ; le besoin immédiat est le prix simple par acheteur
   + bonus quantité + ajustement manuel mensuel (déjà livrés).
3. **Courbe d'allaitement : 6–7 L/j pendant les 3 premiers mois** → le défaut
   de la spec (6,5 L/j × 90 j) est la moyenne exacte de votre pratique.
4. **Prix de marché de départ (aide à la décision génisse)** : velle ~5 jours
   ≈ 3000–3200 DT ; élevée ~2 ans ≈ 3000–3500 DT. Le comparateur doit inclure
   la **vente à ~5 jours** en plus de 3 mois / 18–22 mois. Fréquence de calcul
   du coût génisse : en continu (mensuel), vous le faisiez 1×/an à la main
   avec ±3000 DT d'écart entre estimateurs.
5. **Affichage des assets** : numéro de travail simple (fait — « Vache 0122 »,
   l'identification nationale complète reste en colonne).
6. **Nom du rapport** : retirer « mensuel » (« c'est un rapport hebdomadaire
   wala journalier ») → action FIN-S95.
