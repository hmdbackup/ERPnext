# Questions pour M. Samir — suite de la réunion du 05/08/2026

Toutes les demandes de la réunion sont implémentées (voir `livraison_finance.md`,
stories FIN-S80 → S93). Sept décisions restent ouvertes ; pour chacune une
option par défaut est proposée — un simple « OK » par ligne suffit pour avancer.

## 1. Numéros provisoires au vêlage
Les veaux reçoivent automatiquement un numéro temporaire dans la plage
**99999xxxxx** (10 chiffres), remplacé ensuite par la boucle officielle via le
bouton « Enregistrer boucle officielle ».
**Question : peut-on confirmer (auprès de l'autorité d'identification) qu'aucune
boucle officielle tunisienne ne commence par 99999 ?** Sinon, quel préfixe
réserver ?

## 2. Primes et charges sociales
L'attribution groupée de primes est en place (ex. : prime de l'Aïd 50 DT pour
plusieurs salariés en un clic).
- **Q2a :** les primes entrent-elles dans l'assiette des charges patronales
  (30 %) pour les salariés soumis CNSS ? *Défaut actuel : oui.*
- **Q2b :** si une prime est saisie après le postage des salaires du mois, le
  système la refuse (il faut annuler/régulariser l'écriture d'abord). Ce
  comportement convient-il, ou faut-il un flux de régularisation dédié ?

## 3. Heures d'utilisation des équipements
Le coût horaire est prêt (25 DT/h par défaut, réglable par équipement — option 2
retenue en réunion). Pour imputer ce coût, il faut capturer les heures.
**Question : comment saisir les heures ?**
a) relevé périodique du compteur horaire sur la fiche équipement *(recommandé,
le plus simple)* ; b) heures saisies à chaque utilisation/intervention ;
c) saisie journalière par atelier.

## 4. Coût de revient génisse (spec à valider avant implémentation)
Voir `spec_cout_genisse_facturation_interne.md` :
- **Q4a :** prix du lait interne facturé à l'atelier génisses : prix de la
  grille (coût d'opportunité, *recommandé*) ou prix fixe conventionnel ?
- **Q4b :** comptes de cession interne proposés 6061 / 7068x — à valider avec
  l'expert-comptable (hors états officiels).
- **Q4c :** courbe d'allaitement théorique 6,5 L/j sur 90 jours : OK ?
- **Q4d :** prix de marché de référence (velle 3 mois, génisse pleine 18 mois) :
  valeurs de départ et qui les met à jour ?
- **Q4e :** taux de perte initial pour l'aide à la décision (proposition : 8 %) ?

## 5. Ventes de lait multi-acheteurs
Le décompte mensuel figé gère aujourd'hui **un acheteur** (Centrale Laitière).
**Question : la vente simultanée à plusieurs centrales est-elle à prioriser
maintenant** (impacte la saisie du Bilan Lait Journalier) **ou plus tard ?**

## 6. Libellé des assets vaches
Les assets affichent désormais « Vache 0122 » (N° travail) ; l'identification
nationale complète reste visible en colonne. **Ce format convient-il ?**

## 7. Grille de la centrale (rappel, déjà en attente)
La grille active est toujours PROVISOIRE avec des paliers indicatifs — dès
réception de la grille contractuelle : corriger les paliers, renseigner la
source, passer le statut à VALIDEE (aucun code à toucher).
