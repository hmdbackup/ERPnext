# Les maquettes du 26/08/2026 — ce qui a changé, et ce qui reste

**Sources** : `reunion_2026-08-26/transcription.md` · `reunion_2026-08-26/compte_rendu.md`

| Fichier | Rôle |
|---|---|
| `outils_maquettes_2026-08-26_excalidraw.py` | la fabrique — c'est ici qu'on modifie |
| `maquettes_2026-08-26.excalidraw` | la scène, à ouvrir dans Excalidraw |
| `outils_maquettes_2026-08-26_html.py` | rend la scène en page lisible, paginée : une planche par page A4 paysage, les gestes regroupés tant que la planche tient |
| `maquettes_2026-08-26.html` · `.pdf` | ce qu'on envoie à quelqu'un qui n'a pas Excalidraw — couverture avec sommaire, puis dix planches |

Régénérer : `python3 outils_maquettes_2026-08-26_excalidraw.py && python3 outils_maquettes_2026-08-26_html.py`
puis le PDF : `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --no-pdf-header-footer --virtual-time-budget=8000 --print-to-pdf=maquettes_2026-08-26.pdf file://$PWD/maquettes_2026-08-26.html`

Les maquettes du 24/08 (`maquettes_validees_2026-08-24.*`) sont **conservées telles
quelles** : ce sont celles que M. Samir a vues, ses annotations s'y rapportent.

---

## Ce qu'il a dit, et où c'est rendu

| Sa remarque | Où elle est visible |
|---|---|
| « Tu te compliques la tâche » — plus de clé unique, plus de couple dépenses/recettes | le bloc **FRAIS GÉNÉRAUX — RÉPARTITION PAR ATELIER, TOTAL 100 %**, note ② |
| Autant de lignes « atelier + % » qu'il faut | une ligne par charge, une ligne `└` pour sa répartition |
| Ses trois gardiens : étable 100 % lait · moutons 100 % brebis · parc + fromagerie 50/50 | ce sont les trois premières charges du bloc, mot pour mot |
| « Il ne te laisse pas sauvegarder tant que le total n'est pas à 100 % » | geste 5 du volet saisie : 45 / 35 → **80 % ✗**, refusé avec son message · 45 / 35 / 20 → **100 % ✓**, enregistrée puis soumise |
| Le bouton « ajouter un atelier » | gestes 3 et 4, avec la liste des ateliers ouverte — sans Frais Généraux, on ne répartit pas une charge sur elle-même |
| Brebis et Fromagerie | dans la liste des ateliers, marqués *nouv.*, et deux lignes à tiret dans la ventilation |
| « Ça sera toujours par rapport à ce que le comptable va entrer » | le volet saisie suit le comptable **geste par geste**, sur l'assurance de juin (1 900 DT, 45 / 35 / 20) : ① il ouvre une facture d'achat, ② saisit la ligne (616, Frais Généraux), ③ le bloc « Répartition par atelier » apparaît, ④ il ajoute les ateliers, ⑤ il enregistre — refusé à 80 %, accepté à 100 %, puis Soumettre et le Grand Livre —, ⑥ le mois suivant il **duplique** la facture, ⑦ ce que le rapport en lit. Puis le cas de la facture à plusieurs lignes, ses trois gardiens |
| « Mais on le fera une seule fois » — au 31/12, à la clôture | cadre vert, point QUI ET QUAND |
| « 5 à 10 factures au grand maximum » | cadre vert, point LE VOLUME |
| « Ça devient un tiret pour ne pas mettre 0 » | toutes les cases sans valeur, et la note ① qui en fait un contrôle |
| Le mois calendaire · la période **Année, Year to Date** | la liste déroulante ouverte sur les deux écrans, ★ sur Année |
| « C'est quoi ces deux qui sont à la fin ? » | colonnes **Nb Interv.** / **Nb Équip.**, note ⑦ |
| « Lui, ce n'est pas un informaticien » | le volet **saisie des interventions**, geste par geste, sur la panne hydraulique du Massey 385 : ① le chef de parc déclare la panne (fiche Réparation d'actif, statut En attente → la machine passe EN PANNE dans le parc), ② la réparation faite, il complète pièces / main-d'œuvre / intervenant, enregistre, soumet → la machine repasse PRÊT, ③ le comptable saisit la facture du réparateur comme toute facture (615) et la rattache à la fiche par un champ « Intervention », ④ Dupliquer, ⑤ Planifier, ⑥ Supprimer, ⑦ les heures du tractoriste (Utilisation Équipement, écran existant), ⑧ ce que le rapport en fait |
| Dupliquer · planifier · supprimer une intervention | gestes ④ ⑤ ⑥ de la saisie, repère ⑧ du rapport : Dupliquer est le menu natif d'ERPNext (on change la date, on vérifie, on enregistre) ; Planifier crée une fiche « À venir » à date future ; Supprimer efface un brouillon, annule une fiche soumise |
| « Ce qui est terminé, on n'y touche plus » | geste ② : Soumettre fige la fiche ; geste ⑥ : une fiche soumise ne s'efface pas, elle s'annule et reste en trace ; cadre vert, point RÈGLE |
| « Planifier, c'est une date dans le futur, elle reste ouverte » | geste ⑤, et le repère ⑨ sur la ligne « À VENIR » du préventif |
| « Une différence entre ce qu'on a dépensé et ce dont on n'a pas les traces » | sa définition du rapprochement, reprise mot pour mot |
| « Après on fera la même chose pour les recettes » | cadre jaune, noté hors périmètre |
| « On annule cette User Story » — SCRUM-9 | l'écran 3 : ANNULÉE LE 26/08, cadre vert ; en jaune, les deux questions qui lui survivent |

**L'écran d'arbitrage mensuel n'est pas repris** : il a été montré puis écarté.
`maquette_arbitrage_frais_generaux_2026-08-24.excalidraw` et son générateur ne
servent plus — à supprimer quand on sera sûr de ne plus vouloir les montrer.

---

## Les chiffres, et d'où ils viennent

Le total des frais généraux ne bouge pas : **9 840,00 DT**. C'est sa répartition
qui change, donc la part qui revient au lait.

| | Modèle du 24/08 (deux clés) | Modèle du 26/08 (répartition) |
|---|---|---|
| Quote-part Lait | 7 583,89 DT | **5 525,00 DT** |
| TOTAL retenu pour le coût du litre | 70 983,89 DT | **68 925,00 DT** |
| Coût Complet / L | 1,562 DT/L | **1,517 DT/L** |
| Hors amortissement | 1,477 DT/L | **1,432 DT/L** |

**Écart : 2 058,89 DT sur juin, soit 45,3 millimes par litre** — environ
24 700 DT sur douze mois. Le changement de modèle n'est pas cosmétique.

Les Δ % ne bougent pas (+2,5 · +3,3 · +1,2 · +1,4) : la répartition déplace le
niveau, pas la tendance.

Ce qui se vérifie sur la maquette elle-même :
- 1 400 + 900 + 900 + 2 640 + 1 900 + 2 100 = **9 840,00** ✓
- la ligne **Contrôle — somme des répartitions = Total FG** retombe sur 9 840,00 ✓
- part Lait = 1 400 + 2 640 + 45 % × 1 900 + 30 % × 2 100 = **5 525,00** ✓
- 63 400 + 5 525 = **68 925,00** ; ÷ 45 444 L = **1,517 DT/L** ✓
- (68 925 − 3 860) ÷ 45 444 = **1,432 DT/L** ✓

> ⚠️ **Les pourcentages sont une illustration, pas une donnée.** Ils reprennent
> ses exemples pour rendre le mécanisme visible ; aucune répartition réelle
> n'est saisie. **Le dire à l'oral** — sinon il prendra 1,517 pour le coût du
> litre retenu. C'est écrit dans le cadre jaune de l'écran 1.

---

## Ce qui reste à faire

**Auprès de M. Samir**
1. Rectifier la réponse fausse donnée en séance : le mois est **déjà**
   calendaire (`rapport_performance.py:99`). Il croit avoir demandé une
   correction qui n'a pas lieu d'être.
2. Confirmer que « Année » = *Year to Date* (1ᵉʳ janvier → date choisie), et
   donc que le comparatif devient la même période de l'an dernier.
3. ✅ SCRUM-9 fermé dans Jira le 26/08 — *Terminé(e)* + étiquette `annulee`,
   faute de statut « Annulé » dans le workflow (« on annule cette User Story »,
   phrase perdue par la transcription traduite, voir CR §4).
4. Obtenir les vraies répartitions des 5 à 10 factures concernées.
5. Valider les deux points de la saisie laissés en jaune : « Dupliquer »
   suffit-il pour le mois suivant (ou pré-remplir dès le choix du
   fournisseur), et le Grand Livre inchangé.
6. Avec le comptable, **qui écrit au 615** : la facture du réparateur
   rattachée à la fiche (ce que montre la maquette — la fiche n'écrit rien),
   ou la fiche elle-même à la soumission, par une écriture automatique
   615 / 401 comme le fait aujourd'hui `enregistrer_intervention()`. Pas les
   deux, sinon la charge est comptée deux fois. Et dans la foulée : la
   main-d'œuvre interne, déjà dans les salaires, entre-t-elle dans le coût de
   la fiche ?

**Dans le code** — rien n'est développé, tout est en maquette
1. Un tableau enfant `(ligne, atelier, part %)` sur la facture d'achat **et**
   sur l'écriture de journal (les charges de démo passent en écriture), avec
   les champs de `Personnel Repartition` (`atelier`, `pourcentage`) et un
   contrôle bloquant à 100 % par ligne — demandé seulement quand la ligne est
   sur Frais Généraux, plus le total calculé sous le tableau et le bloc
   masqué tant qu'aucune ligne n'est sur Frais Généraux. Le mois suivant,
   « Dupliquer » (natif) reprend la répartition — le pré-remplissage
   automatique au choix du fournisseur n'est qu'une option, à valider.
   À trancher avec le comptable : Grand Livre
   inchangé (répartition analytique lue par le rapport, ce que montre la
   maquette) ou ventilé via l'allocation de centres de coût native d'ERPNext.
2. `charges_lait()` : la quote-part devient la somme des répartitions saisies au
   lieu d'une clé calculée (`finance_kpis.py:215-225`).
3. La période Année sur les deux rapports restants (`rapport_performance.js:13`,
   `rapport_interventions.js:14`) — `rapport_periodique.js` sort du périmètre
   avec SCRUM-9.
4. La saisie des interventions. Aujourd'hui **aucun écran n'existe** : les
   fiches sont créées par `enregistrer_intervention()` (Python, qui passe
   aussi l'écriture 615 / 401), et la règle du dépôt interdit l'Asset Repair
   créé à la main. À construire, sur la fiche Réparation d'actif : deux
   montants (pièces, main-d'œuvre), intervenant salarié ou prestataire,
   statut À venir / En attente / Terminée, le bouton « Planifier la
   prochaine » ; un champ « Intervention » sur la ligne de facture d'achat ;
   le bloc Préventif du rapport qui lit aussi les fiches à venir ; un champ
   État à trois valeurs sur l'équipement. Dupliquer et Supprimer sont natifs
   (brouillon effacé, fiche soumise annulée) — rien à développer.
5. Les centres de coût Brebis et Fromagerie — configuration, pas code.

Rien à changer pour les libellés `Nb Interventions` / `Nb Équipements` : le code
les nomme déjà correctement (`rapport_interventions.py:79-81`), c'était la
maquette qui abrégeait.

**Ailleurs dans le dépôt**
- `expliquer_les_us.html` porte encore les chiffres du 24/08 (7 583,89 · 1,562 ·
  32,7 millimes) et une diapositive « la question du jour » désormais sans objet.
  À reprendre avant de remontrer le support.
