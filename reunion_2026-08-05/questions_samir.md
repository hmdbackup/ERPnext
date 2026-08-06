# Décisions appliquées & points de vigilance — réunion du 05/08/2026

Mise à jour du 06/08 (v3) : la relecture complète de la transcription (y
compris la fin de réunion, 56:00–68:00) répond à toutes les questions
initialement listées. **Plus aucune décision bloquante.** Ce document acte les
choix appliqués et les 3 points de vigilance à mentionner passivement.

## A. Décisions tranchées par la réunion (appliquées)

1. **Heures d'utilisation des équipements — « option 2 » retenue en séance** :
   coût horaire forfaitaire par équipement (amortissement + maintenance +
   carburant), 25 DT/h par défaut configurable, **multiplié par les heures
   d'utilisation saisies par utilisation/journée** (« le tracteur a travaillé
   1 h ou 5 h dans la journée ») ; répercussion sur le coût du litre :
   obligatoire. → story FIN-S96 (saisie Utilisation Équipement + imputation).
2. **Valorisation du lait interne (génisses) : au coût du litre** — pratique
   historique explicite (« on estime le coût du litre, donc on multiplie »).
   Le manque à gagner (prix de vente) sera affiché à titre indicatif.
3. **Comptes de cession interne : pas de validation bloquante** — « la
   comptabilité officielle reste chez l'expert-comptable ; l'outil sert au
   pilotage interne », facturation interne « entre parenthèses » → comptes
   analytiques 6061/7068x internes, hors états officiels.
4. **ID provisoire au vêlage** : demandé tel quel par M. Samir (ID temporaire
   immédiat, boucle officielle ensuite, identification non modifiable). Le
   préfixe réservé 99999 est un détail d'implémentation (les boucles réelles
   commencent par 999 0…, la série n'atteindrait 99999… qu'après ~10 M de
   boucles) — vérification technique auprès de l'autorité d'identification,
   pas une décision client.
5. **Multi-acheteurs (FIN-S94)** : besoin actuel — 2 acheteurs externes
   payants + atelier génisses en interne, profil de prix par acheteur (prix
   unique ou paliers), règlement mensuel, prix temporaire accepté. Pas de
   paiement à la qualité aujourd'hui (grille TB/TP prête, non bloquante).
6. **Imputation des charges** : à l'utilisation idéalement, flexibilité de
   faire les deux ; petites factures absorbées immédiatement, grosses
   factures étalées sur plusieurs mois. Simulations à préparer : facture
   fournisseur, utilisation médicaments, TVA.
7. **Coût génisse** : courbe 6–7 L/j × 3 mois (défaut 6,5 × 90 j validé) ;
   scénarios de vente à ~5 jours / 3 mois / 18–22 mois ; prix de départ
   ≈ 3000–3200 DT (velle ~5 j) et 3000–3500 DT (~2 ans) ; calcul en continu.

## B. Points de vigilance (à mentionner, pas à demander)

1. **Primes** : appliquées « simples » (esprit réunion) — soumises aux charges
   patronales comme le salaire pour les salariés CNSS ; une prime sur un mois
   déjà posté au Grand Livre est refusée (régulariser l'écriture d'abord).
   *Signaler si certaines primes doivent être exonérées.*
2. **Taux de perte génisses** : 8 % par défaut (configurable) en attendant
   l'historique réel. *Signaler si un autre chiffre est plus juste.*
3. **Préfixe 99999** : à confirmer opportunément auprès de l'autorité
   d'identification (non bloquant — voir A4).
