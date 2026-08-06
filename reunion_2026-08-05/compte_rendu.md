# Réunion finance — 05/08/2026 (~70 min)

> Source : `~/Downloads/Rue Abou Abid el Bakri.m4a`, transcrit avec Whisper large-v3-turbo.
> ⚠️ L'audio mélange français et derja tunisienne : la transcription mot-à-mot (`transcription.txt` / `.srt`) est approximative sur les passages en derja. Ce compte-rendu reconstruit le contenu exploitable, horodaté via le .srt.

## Déroulé de la réunion

### 00:00 – 02:50 — Amortissements / Assets
- La comptabilité officielle reste chez l'expert-comptable ; l'outil sert au pilotage interne.
- Un asset peut être une vache, un tracteur, du matériel de traite, etc. Deux données principales : **valeur initiale (acquisition)** et **durée d'amortissement en mois** (+ date de démarrage).
- Demande de Samir : un **tableau d'amortissement** unique — liste des assets à gauche, date d'acquisition, date d'entrée dans l'actif, date de sortie, durée, amortissements cumulés, valeur restante. Pas besoin de tableaux mensuels séparés.
- Objectif : comparer ce que sort le système avec ce que génèrent les experts-comptables.
- ERPNext a déjà un tableau d'amortissement natif → **à vérifier s'il correspond au besoin** (réponse en séance : « oui, c'est très bien », à confirmer).

### 02:50 – 06:00 — Coût de la ration / rapport journalier
- Indicateurs suivis : coût de la ration, coût du litre, mécanique, ressources humaines, composition des éléments ; coût de la ration rapporté au litre de lait produit.
- Le « rapport journalier » remplace le fichier Excel actuel : snapshot journalier, réunion hebdomadaire, **comparaison semaine vs semaine précédente**, graphes des variations.
- En sortie finale : un **coût du litre hors amortissement** (et avec amortissement).

### 06:00 – 09:00 — Indicateur « sur-concentrés »
- Litres de lait produits **par kg de concentré distribué** = bon indicateur global (le concentré est le coût principal de la ration ; le suivi exact par vache n'existe pas).
- **Seuil : en dessous de 1,8 L/kg de concentré → rouge immédiatement.**

### 09:00 – 15:00 — Recettes / grille qualité lait / atelier génisses
- Avant, le lait était payé sur une **grille de qualité** : bonification sur matière protéique + bonification sur matière grasse.
- Le calcul se faisait **en fin de mois sur la moyenne mensuelle**, pas journalier.
- Le lait est vendu à **plusieurs acheteurs** ; le système permet déjà des profils d'acheteur (prix basique/unique ou par palier) — dans la bonne direction.
- Il existait aussi un **bonus de quantité** (payé plus cher quand on livre plus) → prix variables.
- Besoin d'un **ajustement manuel de bonification pour un mois donné**.
- **Facturation interne** : le lait donné à l'atelier génisses doit être facturé en interne (valeurs « entre parenthèses »).
- Calculer **ce qu'une génisse a coûté pendant sa vie** (élevage jusqu'à ~18 mois ; historiquement fait 1×/an manuellement : ouvrier dédié, mécanique, ration théorique 6–7 L/j les 3 premiers mois, âge de sortie ~18 mois — parfois 3 ans une mauvaise année, problème fécondité lié à la qualité du concentré / guerre en Ukraine).
- Question de gestion à laquelle l'outil doit répondre : **vaut-il mieux vendre la génisse à 18 mois ou à 3 mois** si on perd de l'argent en l'élevant ? → aide à la décision attendue. Mohamed Slim : « je vais essayer de faire ça ».

### 15:00 – 29:00 — Démo / grille de la centrale / configuration seuils / IOFC
- Question sur la « grille de la centrale » = la grille de prix (pas encore de paiement à la qualité aujourd'hui, on y reviendra).
- Prix temporaire le temps de finaliser les prix avec l'acheteur.
- Rapport : **pas nécessairement mensuel** — journalier, hebdomadaire ou par quinzaine, il faut que ce soit **flexible**. Pour le rapport imprimable : plutôt un **export des données vers un template Excel** (rapide, efficace) que de la génération complexe dans l'outil.
- Démo config des seuils (HMD Configuration) avec couleurs ; exemple **IOFC (Income Over Feed Cost) par vache lactante par jour** — Samir ne connaissait pas l'acronyme, à expliciter à l'écran.
- Question : comment sont saisies les configurations (prix du lait, etc.).

### 29:50 – 38:40 — RH / registre des salariés
- Registre des salariés : en cas d'**augmentation de salaire, ne pas perdre l'historique**.
- Salaire brut + **% de charges patronales ~30% par défaut**, configurable dans la page de configuration et éditable manuellement par salarié.
- **Primes** : champ dédié (prime de l'Aïd, prime de performance…) ; pouvoir **sélectionner plusieurs salariés et appliquer une prime en masse** (action groupée). Rester simple — pas des dizaines de types de primes.
- Point important : les salaires/charges **une fois calculés doivent être figés dans le temps** — changer un salaire aujourd'hui ne doit pas altérer les charges déjà calculées dans l'historique.

### 38:45 – 40:00 — Contrôle de cohérence finance
- Montré en démo ; s'exécute pour une période ou une date.

### 40:00 – 56:00 — Assets vaches / lien Animal ↔ Asset / identification
- Dans les assets on doit retrouver équipement, matériel… et les vaches.
- **Problème constaté en démo** : la liste des assets vaches affiche l'**ID technique** et non le **numéro de travail** de la vache. Animal et Asset sont deux objets différents connectés — le nom de l'asset n'est pas l'ID de l'animal → à corriger côté affichage/liaison.
- Confusion sur un numéro (999 0000 122 vs 2122) → la version déployée sur site n'était **pas à jour** (voir avec Aziz, s'assurer que tout le monde a la même version).
- **Identification** : le numéro d'identification ne doit pas être modifiable ; au vêlage, un numéro par défaut est généré ; il y a le **numéro de boucle officiel (identification tunisienne)** — il faut pouvoir **générer vite un ID temporaire** au vêlage puis enregistrer la boucle officielle ensuite.

### 60:00 – 68:00 — Matériel / maintenance / coût horaire
- Équipements (tracteurs…) : amortissement + **coûts de maintenance** (ex. vidange 500 DT) saisis sur l'équipement.
- Imputation des charges : **idéalement à l'utilisation et non à la facturation, mais garder la flexibilité de faire les deux** ; petites factures absorbées immédiatement, grosses factures **étalées sur plusieurs mois**.
- À simuler pour la prochaine fois : une **facture fournisseur**, l'**utilisation de médicaments**, la **TVA**.
- Répercussion sur le coût du litre : oui, obligatoire.
- Répartition du coût tracteur : **coût horaire par utilisation** = amortissement + maintenance + mazot…, ex. **25 DT/h par défaut, configurable par équipement** (tous les tracteurs n'ont pas le même coût horaire). → **Option 2 (la plus simple) retenue.**

### Fin (~68:00) — Fonctionnement
- S'assurer que tout le monde travaille sur la **même version** (site pas à jour).
- Les prochaines remarques seront envoyées **au fil de l'eau par message direct / téléphone**, plutôt que d'attendre la réunion.

## Liste des changements à faire (extraits des remarques de Samir)

1. **Tableau d'amortissement consolidé** (vérifier si celui d'ERPNext suffit) : assets, dates acquisition/entrée/sortie, durée, cumul, restant.
2. **Coût du litre hors amortissement** affiché en sortie du rapport.
3. **Indicateur sur-concentrés** : L de lait / kg concentré, seuil rouge < 1,8.
4. **Grille qualité lait** : bonification MP + MG, calcul sur moyenne mensuelle, bonus quantité, ajustement manuel mensuel, multi-acheteurs.
5. **Facturation interne** du lait vers l'atelier génisses.
6. **Coût de revient d'une génisse** sur sa vie + aide à la décision (vendre à 3 mois vs élever jusqu'à 18 mois).
7. **Rapport flexible** journalier/hebdo/quinzaine + export Excel vers template imprimable.
8. **IOFC** : libeller l'acronyme en clair.
9. **RH** : historique des salaires immuable, charges patronales 30% par défaut configurable, primes en masse (action groupée), valeurs calculées figées dans le temps.
10. **Lien Animal ↔ Asset** : afficher le numéro de travail de la vache (pas l'ID technique) dans les assets.
11. **Identification au vêlage** : ID temporaire rapide → numéro de boucle officiel tunisien ensuite ; numéro non modifiable.
12. **Équipements** : saisie maintenance, coût horaire configurable par équipement (défaut 25 DT/h), imputation au coût du litre.
13. **Charges** : imputation à l'utilisation ou à la facturation (les deux possibles), étalement des grosses factures sur plusieurs mois.
14. **Simulations à préparer** : facture fournisseur, utilisation médicaments, TVA.
15. **Déploiement** : mettre à jour l'instance du site (version obsolète), s'assurer que tout le monde a la même version.
