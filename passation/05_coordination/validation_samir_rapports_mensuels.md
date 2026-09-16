# Validation des trois rapports mensuels — à relire et annoter

**Pour :** M. Samir
**Date :** 8 août 2026
**Temps de lecture et de réponse estimé :** 10 minutes
**Réponse attendue :** par écrit, directement dans ce document

---

## Comment répondre

Chaque section se termine par des questions numérotées. Sous chaque question, une ligne **« Réponse : »**. Écrivez sur cette ligne, en un mot ou une phrase. Si un choix est proposé, entourez ou recopiez l'option retenue.

Si un point vous paraît mal formulé ou si vous n'êtes pas d'accord avec ce qui a été prévu, écrivez-le à côté. Une annotation en marge vaut validation ou correction : il n'y a pas besoin de réunion.

Ce document ne demande pas votre avis sur la technique. Il demande votre avis sur **ce que les rapports doivent afficher** et **avec quelle définition**.

---

## Vue d'ensemble

Une vérification a été faite sur les trois rapports, critère par critère. Voici l'état réel :

| Rapport | Ce qui fonctionne déjà | Ce qui manque |
|---|---|---|
| **Lait** | Le total du mois, le taux de remplissage des saisies, l'alerte en cas de mois incomplet, l'export Excel | La ventilation jour par jour du lait (vendu / consommé sur la ferme / bu par les veaux / écart) |
| **Coûts** | Les coûts au litre, le coût mécanique affiché à part sans double comptage, un mois vide qui affiche zéro | La répartition des charges par atelier (lait, génisses, cultures, traction, frais généraux) |
| **Interventions mécaniques** | La liste des interventions, les entretiens à venir ou en retard, l'écart entre la comptabilité et les interventions saisies | Un mois sans intervention n'affiche pas « 0 », et les compteurs ne sont pas des chiffres exploitables |

L'essentiel de votre validation porte donc sur **deux manques** (ventilation du lait, répartition des charges par atelier) et sur **des définitions de calcul** qu'il faut trancher avant de coder.

---

# 1. Rapport mensuel — Production laitière

## Ce que vous verriez aujourd'hui

Un tableau avec une ligne par jour du mois, et en bas une ligne de synthèse qui donne :

- la **production totale du mois en litres** ;
- la **moyenne par vache laitière et par jour** ;
- le **nombre de vaches laitières**.

Une ligne indique aussi combien de jours du mois ont été saisis, par exemple « 28 jours sur 31 ». Elle s'affiche toujours, y compris quand le mois est complet (« 31 sur 31 »), pour que vous sachiez que le chiffre est fiable.

Si le mois est incomplet, un avertissement chiffré s'affiche **en haut du tableau**, et les codes couleur (vert / orange / rouge) sont éteints sur les indicateurs laitiers — mais **les valeurs restent affichées**, rien n'est masqué. Le rapport s'exporte en Excel.

## Ce qui manque ou qui doit être tranché

**a) La ventilation quotidienne du lait n'existe pas.** C'est le vrai trou. Une colonne « Commercialisé » est affichée à l'écran mais elle est **toujours vide**, et il n'y a aucune colonne pour l'auto-consommation, le lait bu par les veaux, ni l'écart. Concrètement : vous ne pouvez pas voir, un jour donné, où est parti le lait — vous avez seulement un cumul du mois, sur un autre écran. Toutes ces données existent pourtant déjà dans le bilan lait journalier : il s'agit de les remonter dans le tableau.

**b) Sur le mois en cours, la moyenne par vache est sous-estimée.** Le calcul compte les vaches sur les 31 jours du mois, y compris les jours pas encore arrivés — des jours sans lait. Résultat : plus vous consultez le rapport tôt dans le mois, plus la moyenne paraît basse. Sur un mois terminé, le chiffre est juste.

**c) Le nombre de vaches laitières affiché n'est pas une moyenne.** C'est l'effectif **au dernier jour du mois**. Sur le mois en cours, c'est donc une date future. Sur un troupeau qui bouge (vêlages, taries, réformes), l'effectif de fin de mois et l'effectif moyen du mois ne donnent pas le même résultat.

**d) Deux écrans, deux unités différentes, sous le même nom.** Un écran affiche la production par vache **et par jour** (de l'ordre de 25 L). L'autre affiche la production par vache **sur tout le mois** (de l'ordre de 750 L). L'écart est d'un facteur 30 environ, et rien ne l'explique à l'écran. Il faut choisir une unité de référence.

**e) « Jours saisis » ne veut pas dire « journée complète ».** Un jour est compté comme saisi dès qu'il porte **une seule traite d'une seule vache**, ou un bilan journalier. Conséquence : un mois peut afficher « 31 jours sur 31 » alors que la ventilation vendu / consommé / veaux est entièrement vide, ou qu'une seule vache a été traite. L'indicateur rassure plus qu'il ne devrait.

## Questions — Rapport Lait

**1. La ventilation quotidienne : quels postes voulez-vous voir jour par jour ?**
(a) Vendu uniquement — (b) Vendu + auto-consommation + lait veaux + écart — (c) autre, précisez.

> Réponse : ..............................................................................

**2. Consultez-vous ce rapport sur le mois en cours, ou seulement sur un mois terminé ?**
(a) Uniquement mois terminé — (b) Aussi en cours de mois, il faut donc que les chiffres s'arrêtent à la date du jour.

> Réponse : ..............................................................................

**3. Le nombre de vaches laitières du mois, ce doit être :**
(a) l'effectif moyen du mois — (b) l'effectif à une date précise, à indiquer clairement à l'écran (« VL au 31/07 ») — (c) les deux, en deux colonnes.

> Réponse : ..............................................................................

**4. L'unité de référence pour la production par vache :**
(a) litres par vache et par jour — (b) litres par vache et par mois — (c) les deux, affichées côte à côte.

> Réponse : ..............................................................................

**5. Un jour doit être compté comme « saisi » quand :**
(a) il y a au moins une traite — (b) il y a un bilan lait journalier complet (vendu / consommé / veaux) — (c) les deux sont exigés.

> Réponse : ..............................................................................

---

# 2. Rapport mensuel — Coûts

## Ce que vous verriez aujourd'hui

Un tableau qui reprend les charges du mois **lues directement dans la comptabilité** (pas ressaisies ailleurs), regroupées par grande famille, avec le total des charges.

Puis une section de coûts unitaires :

- **coût complet au litre** ;
- **coût alimentaire au litre** ;
- **coût du litre hors amortissement**.

Le **coût mécanique** (tracteurs, matériel) est affiché sur une ligne séparée, avec la mention explicite qu'il est **déjà compris dans les charges et ne doit pas être additionné** au coût complet. Cette règle est vérifiée automatiquement à chaque livraison : personne ne peut la casser sans que ça se voie. Un mois sans écriture affiche des zéros, pas un message d'erreur.

## Ce qui manque ou qui doit être tranché

**a) Les charges ne sont pas réparties par atelier.** Les cinq ateliers existent (Lait, Génisses, Cultures/Fourrage, Traction, Frais Généraux) et les écritures portent bien leur atelier. Mais le rapport de coûts ne les lit pas : il affiche un total unique pour toute l'exploitation.

**Ce que ça change pour vous, concrètement :** le « coût complet au litre » divise aujourd'hui **la totalité des charges de la ferme** — y compris les génisses, les cultures, la traction, les frais généraux et les frais financiers — par les **seuls litres de lait**. Ce n'est pas un coût de revient du lait : c'est structurellement **surestimé**. C'est le point le plus important de ce document.

**b) Il faudra décider du sort des charges non affectées.** Certaines écritures peuvent ne porter aucun atelier. Soit on les affiche dans une ligne « Non imputé » bien visible, soit on les fond dans un total — auquel cas elles disparaissent du regard.

**c) Le coût alimentaire et le coût complet ne viennent pas de la même source.** Le coût alimentaire est calculé à partir des **sorties de stock** (ce qui est réellement distribué aux animaux). Le coût complet vient de la **comptabilité** (ce qui est facturé). Selon le paramétrage, un achat d'aliment peut peser sur le mois de l'achat côté comptabilité et sur le mois de la distribution côté stock. Les deux chiffres du même tableau peuvent alors ne pas parler du même mois. Le coût alimentaire n'est donc pas un sous-ensemble arithmétique du coût complet.

**d) Le mois de clôture annuelle peut fausser le rapport.** Les écritures de clôture d'exercice annulent produits et charges. Le mois qui contient la clôture pourrait afficher un coût du litre proche de zéro, sans alerte. Il faut savoir quel mois est concerné pour le neutraliser.

## Questions — Rapport Coûts

**1. La répartition des charges par atelier, vous la voulez sous quelle forme ?**
(a) Une colonne « Atelier » sur chaque ligne de charge — (b) un filtre pour n'afficher qu'un atelier à la fois — (c) des sous-totaux par atelier les uns sous les autres — (d) plusieurs de ces formes.

> Réponse : ..............................................................................

**2. Le « coût complet au litre » doit-il ne retenir que les charges de l'atelier Lait, ou toutes les charges de la ferme ?**
(a) Atelier Lait seul — (b) Atelier Lait + une quote-part des frais généraux (préciser la clé : par exemple au prorata du chiffre d'affaires) — (c) toutes charges confondues, comme aujourd'hui.

> Réponse : ..............................................................................

**3. Les charges sans atelier renseigné :**
(a) ligne « Non imputé » visible dans le rapport — (b) réparties automatiquement — (c) ignorées.

> Réponse : ..............................................................................

**4. Quel mois porte votre clôture d'exercice ?** (pour que ce mois ne fausse pas le coût du litre)

> Réponse : ..............................................................................

---

# 3. Rapport mensuel — Interventions mécaniques

## Ce que vous verriez aujourd'hui

Trois blocs :

1. **Les interventions réalisées du mois** : équipement, date, description, type d'intervention, atelier, intervenant, coût. Les sept informations sont bien présentes, aucune colonne n'est vide. En bas, une ligne TOTAL avec le coût total, et un libellé du type « TOTAL — 3 interventions, 2 équipements ».
2. **Les entretiens préventifs dus ou en retard**, sur les 30 jours à venir. Les retards sont en rouge.
3. **L'écart entre le compte d'entretien de la comptabilité et la somme des interventions saisies**, avec l'explication du sens de l'écart : écart positif = une facture n'a pas été rattachée à une intervention ; écart négatif = une intervention a été saisie sans écriture comptable.

## Ce qui manque ou qui doit être tranché

**a) Un mois sans intervention n'affiche pas « 0 ».** Il affiche une phrase (« Aucune intervention saisie sur la période ») et une cellule de coût vide, sans ligne TOTAL. Concrètement : vous ne pouvez pas distinguer d'un coup d'œil « aucune intervention ce mois-ci » de « le rapport n'a pas tourné ».

**b) Le nombre d'interventions et le nombre d'équipements sont du texte, pas des chiffres.** Ils sont écrits dans un libellé. Vous ne pouvez ni les trier, ni les récupérer proprement dans Excel, ni les suivre d'un mois sur l'autre. Seul le coût est un vrai chiffre.

**c) Sur le mois en cours, la liste s'arrête à aujourd'hui, sans le dire.** Une intervention enregistrée à l'avance pour la fin du mois n'apparaît pas, ni dans la liste ni dans l'écart avec la comptabilité.

**d) L'écart avec la comptabilité disparaît dès qu'on filtre.** Si vous filtrez sur un tracteur ou sur un atelier, le bloc de rapprochement est remplacé par un message. Aujourd'hui, l'écart n'existe qu'au niveau global.

**e) Les entretiens préventifs suivent désormais les filtres.** C'était un défaut — filtrer sur un tracteur affichait quand même les échéances de tout le parc — il a été corrigé. Reste à confirmer que c'est bien le comportement que vous attendez (question 3).

**f) Deux informations sont enregistrées mais jamais affichées :** la **durée d'immobilisation** de l'équipement (elle est bien saisie), et le lien pour ouvrir directement la fiche de l'intervention depuis le rapport.

## Questions — Rapport Interventions

**1. Un mois sans aucune intervention doit afficher :**
(a) une ligne TOTAL à 0 (0 intervention, 0 équipement, coût 0) — (b) une phrase « aucune intervention » — (c) les deux.

> Réponse : ..............................................................................

**2. L'écart entre la comptabilité et les interventions saisies, vous le voulez :**
(a) au niveau global uniquement, comme aujourd'hui — (b) aussi par atelier — (c) aussi par équipement.

> Réponse : ..............................................................................

**3. Le bloc « entretiens préventifs » est aujourd'hui sur 30 jours et suit le filtre équipement. Cela vous convient-il ?**
(a) Oui, tel quel — (b) Oui pour le filtre, mais autre durée : précisez — (c) Non, je veux voir tout le parc même en filtrant.

> Réponse : ..............................................................................

**4. Faut-il ajouter la durée d'immobilisation de l'équipement en colonne ?**
(a) Oui — (b) Non, l'information ne vous sert pas.

> Réponse : ..............................................................................

---

# 4. Trois questions transverses

**1. À l'export Excel, les codes couleur (vert / orange / rouge) et le graphique ne sont pas conservés — seuls les chiffres le sont. Est-ce acceptable ?**
(a) Oui, les chiffres suffisent — (b) Non, il faut retrouver les alertes dans le fichier exporté (sous forme de colonne texte, par exemple).

> Réponse : ..............................................................................

**2. Sur quel mois voulez-vous que la recette soit faite** (le mois de référence sur lequel vous vérifierez les chiffres avant de valider) ?

> Réponse : ..............................................................................

**3. Si les trois manques ne peuvent pas être livrés en même temps, dans quel ordre les traitez-vous ?**
Numérotez de 1 à 3 : ventilation quotidienne du lait ___ / répartition des charges par atelier ___ / totaux du rapport interventions ___

> Réponse : ..............................................................................

---

## Remarques libres

Écrivez ici tout ce qui n'entre pas dans les questions ci-dessus : une définition qui vous paraît fausse, un chiffre que vous calculez autrement aujourd'hui, un indicateur qui manque.

>
>
>
>

---

**Merci de renvoyer ce document annoté.** Les développements ne démarrent pas tant que les questions 1 du rapport Lait, 1 et 2 du rapport Coûts, et 1 du rapport Interventions n'ont pas de réponse.
