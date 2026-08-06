# Scénario de démonstration — Simulations

**Point 14 du compte-rendu du 05/08/2026** : « À simuler pour la prochaine fois :
une facture fournisseur, l'utilisation de médicaments, la TVA. »

Ce document se suit **à l'écran, en séance**. Il donne, pour chaque simulation :
l'objectif métier en une phrase, la commande de préparation, le chemin de clics
exact, les montants attendus, et l'endroit où l'on voit l'impact au Grand Livre
et sur le coût du litre.

Durée de la démonstration : **20 à 25 minutes** hors questions.

---

## 0. Préparation (15 minutes avant la réunion, pas devant le client)

### 0.1 Poser le scénario

```bash
bench --site hmd.agro execute \
    hmd_agro.hmd_agro.setup.finance.simulations.setup_simulations
```

La commande est **idempotente** : on peut la relancer autant de fois qu'on veut,
elle ne crée jamais de doublon. Elle est aussi **additive** : elle ne modifie, ne
corrige et ne supprime aucun document déjà en base.

Si elle refuse de démarrer, le message porte un code :

| Code | Ce qu'il faut lancer avant |
|---|---|
| `ERR-SIM-01` / `ERR-SIM-02` / `ERR-SIM-06` | `setup.finance.socle_comptable.setup_socle_comptable` |
| `ERR-SIM-03` | `setup.stock_foundation` |
| `ERR-SIM-04` | `setup.finance.recettes.setup_recettes` |
| `ERR-SIM-05` | Le livre est **arrêté** (exercice gelé ou clôturé) sur la période : rien à faire, c'est le garde-fou qui joue son rôle |
| `ERR-SIM-08` / `ERR-SIM-09` / `ERR-SIM-10` | `setup.finance.seed_demo_finance.run` (troupeau + aliments + médicaments de démonstration) |

### 0.2 Noter les cinq numéros de pièces

La commande se termine par :

```
  Documents de la simulation :
    facture_aliment      : ACC-PINV-2026-000xx
    facture_service      : ACC-PINV-2026-000xx
    facture_medicament   : ACC-PINV-2026-000xx
    traitement           : TRT-2026-0xxxx
    vente_taxable        : ACC-SINV-2026-000xx
```

**Recopier ces cinq numéros** sur un post-it : ce sont les seules choses qu'on
tape à l'écran pendant la démonstration.

### 0.3 Ouvrir les onglets à l'avance

| Onglet | Adresse |
|---|---|
| Factures d'achat | `/app/purchase-invoice` |
| Traitements | `/app/traitement` |
| Grand Livre | `/app/query-report/General Ledger` |
| Balance générale | `/app/query-report/Trial Balance` |
| Rapport Periodique | `/app/query-report/Rapport Periodique` |
| Contrôle de cohérence | `/app/query-report/Controle Coherence Finance` |

> Toutes les pièces sont datées **du jour où la commande a été lancée**. C'est
> voulu : une écriture de stock antidatée met ERPNext en recalcul différé et le
> CMP à l'écran ne bougerait pas devant le client. Il faut donc lancer la
> préparation **le jour même** de la réunion.

---

## 1. Simulation « facture fournisseur » — achat d'aliment avec TVA 19 %

**Objectif métier** — montrer qu'une facture d'aliment saisie une seule fois
alimente à la fois la comptabilité (dette fournisseur + TVA récupérable) et le
stock (quantité + prix de revient qui servira au coût de la ration).

### Montants attendus

| Ligne | Valeur |
|---|---|
| Fournisseur | SCAPCO - Aliments du Bétail |
| N° de pièce fournisseur | FA-2026-0417 |
| Article | Concentré VL Démo — **10 000 kg à 1,350 TND/kg** |
| Total HT | **13 500,000 TND** |
| TVA 19 % | **2 565,000 TND** |
| Total TTC | **16 065,000 TND** |

### Chemin de clics

1. `/app/purchase-invoice` → **Achats → Facture d'achat** → ouvrir la facture
   `facture_aliment`.
2. **Montrer l'en-tête** : le fournisseur, la case *Mettre à jour le stock*
   (cochée) et l'entrepôt `Magasin Principal - HMD`.
   > La phrase à dire : « une seule saisie, la facture *et* la réception. »
3. **Descendre sur la table des taxes** : une seule ligne,
   `4366 - État - TVA déductible - HMD`, taux 19 %, montant 2 565,000.
   > La ligne n'est pas tapée à la main : elle vient du modèle
   > « TVA déductible 19 % » du plan comptable. Le montrer si on veut :
   > `/app/purchase-taxes-and-charges-template`.
4. **Bouton *Voir* (ou menu ⋯) → *Écritures comptables*** — ou l'onglet Grand
   Livre déjà ouvert, filtre *Pièce* = numéro de la facture.

   | Compte | Débit | Crédit |
   |---|---|---|
   | `32 - Autres approvisionnements - Intrants` (entrée en stock) | 13 500,000 | |
   | `4366 - État - TVA déductible` | 2 565,000 | |
   | `401 - Fournisseurs d'exploitation` | | 16 065,000 |

   > ⚠ **Sur le site de démonstration uniquement.** Le stock de concentré y est
   > *négatif* (des rations ont été distribuées sans que les achats
   > correspondants aient été saisis). ERPNext régularise alors l'écart de
   > valorisation de la part négative — ici **558,800 TND sur le compte 605**
   > (= 5 588 kg déjà consommés × l'écart de prix 1,350 − 1,250) — et ne porte
   > que 12 941,200 sur le compte de stock `32`. Le total reste 13 500.
   > **La commande de préparation affiche un `[warn]` explicite** quand ce cas
   > se présente : si le message n'apparaît pas, l'écriture est la table
   > ci-dessus, à trois lignes. Sur une base tenue à jour, la totalité va sur
   > `32`. Réponse à donner si la question vient : § 6, dernière question.

5. **Montrer l'effet stock** : menu ⋯ → *Grand livre des stocks*, ou
   `/app/item/ALI-Concentré VL Démo` → tableau de bord *Stock*.
   Le stock remonte de **+10 000 kg** et le **CMP passe de 1,250 à
   1,350 TND/kg**.

### Où l'on voit l'impact

- **Au Grand Livre** : immédiatement, sur les trois comptes ci-dessus.
- **Sur le coût du litre** : **pas tout de suite, et c'est normal** — acheter de
  l'aliment n'est pas une charge, c'est un stock (bilan). La charge naît quand
  le concentré est *distribué*. À partir de demain, la distribution quotidienne
  sortira le concentré à 1,350 au lieu de 1,250, et on le lira dans
  `/app/query-report/Rapport Periodique` → section **Indicateurs** → lignes
  *Frais Concentré* et *Coût Alimentaire / L*.

---

## 2. Simulation « facture de service » — entretien du tracteur avec TVA

**Objectif métier** — montrer qu'une prestation (vidange, vétérinaire,
transporteur, assurance…) se saisit exactement comme un achat, mais part
directement en charge sur l'atelier concerné, sans passer par le stock.

### Montants attendus

| Ligne | Valeur |
|---|---|
| Fournisseur | Garage Mécanique du Sahel |
| N° de pièce | FS-2026-1183 |
| Prestation | Vidange 500 h tracteur — huile moteur + 3 filtres |
| Total HT | **280,000 TND** |
| TVA 19 % | **53,200 TND** |
| Total TTC | **333,200 TND** |

### Chemin de clics

1. `/app/purchase-invoice` → ouvrir `facture_service`.
2. **Montrer la ligne d'article** : la case *Mettre à jour le stock* est
   **décochée**, et la colonne *Compte de charge* affiche
   `615 - Entretien et réparations - HMD`.
3. **Montrer le centre de coûts** de la ligne : `Traction - HMD`.
   > La phrase à dire : « c'est ça qui fait que l'entretien du tracteur ne
   > pollue pas le coût du lait — il est rangé dans l'atelier Traction. »
4. **Écritures comptables** :

   | Compte | Débit | Crédit |
   |---|---|---|
   | `615 - Entretien et réparations` (atelier Traction) | 280,000 | |
   | `4366 - État - TVA déductible` | 53,200 | |
   | `401 - Fournisseurs d'exploitation` | | 333,200 |

### Où l'on voit l'impact

- **Grand Livre** : compte 615.
- **Rapport Periodique → Indicateurs** :
  - *Frais Entretien & Réparations (615)* : **+ 280 DT**
  - *Entretien / Produit Brut* : le ratio bouge (seuil vert/orange/rouge issu de
    `maintenance_seuil_pct_ca` dans la configuration HMD)
  - *Charges Totales* et *Coût Complet / L* : **+ 280 DT**, donc le coût du
    litre monte, tout de suite cette fois.

---

## 3. Simulation « utilisation de médicaments »

**Objectif métier** — montrer la chaîne complète d'un traitement : le stock de
médicament diminue, la charge part au Grand Livre à sa valeur réelle, et le lait
de la vache traitée est écarté pendant le délai d'attente.

Cette simulation se joue en **deux temps**.

### 3.1 La facture du vétérinaire (TVA 7 %)

| Ligne | Valeur |
|---|---|
| Fournisseur | Pharmacie Vétérinaire Ben Ammar |
| N° de pièce | FV-2026-0092 |
| Article | Amoxicilline Démo — **20 flacons à 25,000 TND** |
| Total HT | **500,000 TND** |
| TVA **7 %** (taux réduit) | **35,000 TND** |
| Total TTC | **535,000 TND** |

**Chemin de clics** : `/app/purchase-invoice` → ouvrir `facture_medicament`.

Le point à montrer : **la table des taxes affiche 7 %, pas 19 %** — même compte
`4366`, taux différent. Le système gère plusieurs taux, on choisit le bon modèle
au moment de la saisie (19 / 13 / 7 / 0 sont tous paramétrés).

Puis `/app/medicament/Amoxicilline Démo` : le champ **Stock courant** est passé
de 10 à **30 flacons**.

### 3.2 Le traitement sur une vache réelle

| Ligne | Valeur |
|---|---|
| Animal | la première vache **ACTIF / EN_PRODUCTION** du troupeau |
| Praticien | Dr. Néjib Karoui |
| Diagnostic | Mammite clinique — quartier arrière gauche |
| Médicament | Amoxicilline Démo, dose 20 ml, voie **INJECTABLE_IM** |
| Quantité stock consommée | **2 flacons** |
| Valeur sortie du stock | **50,000 TND** (2 × CMP 25,000) |
| Délai d'attente lait | **3 jours** |

**Chemin de clics**

1. `/app/traitement` → ouvrir le traitement `TRT-…` de la simulation.
2. **Montrer la table Médicaments** : la colonne *Délai attente lait* (3, en
   lecture seule, récupérée de la fiche médicament) et la colonne
   *Date fin attente lait* (calculée : date du traitement + 3 jours).
   > Insister sur la distinction **dose** (20 ml, information médicale) et
   > **quantité stock consommée** (2 flacons, ce qui sort réellement du magasin).
3. `/app/medicament/Amoxicilline Démo` : le stock est retombé à **28 flacons**.
   Le traitement a généré tout seul une sortie de stock — aucune saisie
   magasin à faire.
4. **La charge** : Grand Livre, filtre *Pièce* = le numéro de la sortie de stock
   (`MAT-STE-…`, visible depuis la liste `/app/stock-entry`, filtre *Remarques*
   contient le numéro du traitement).

   | Compte | Débit | Crédit |
   |---|---|---|
   | `602 - Consommation de médicaments et produits vétérinaires` | 50,000 | |
   | `32 - Autres approvisionnements - Intrants` | | 50,000 |

5. **Le délai d'attente lait, côté terrain** :
   - `/app/animal/<la vache>` : *Attente lait active* = coché,
     *Date fin attente lait* = date du traitement + 3 jours.
   - Ouvrir la **page Saisie Traite** (`/app/saisie-traite`) : la ligne de cette
     vache est signalée — le trayeur voit que son lait ne part pas en cuve.
   - Le compteur **« Animal Sous Traitement »** de l'espace HMD AGRO monte de 1.

### Où l'on voit l'impact

- **Grand Livre** : compte 602 (et non plus 603 « Variation des stocks » — le
  paramétrage posé par la simulation range désormais les sorties d'aliment sur
  601 et les sorties de médicament sur 602).
- **Rapport Periodique → Indicateurs** : ligne *Frais Médicaments* **+ 50 DT**,
  répercutée dans *Charges Totales* et *Coût Complet / L*.

---

## 4. Simulation « TVA » — la position du mois

**Objectif métier** — montrer que le système sait dire, à tout instant, combien
de TVA on a collectée, combien on a payée, et donc ce qu'on doit à la recette
(ou ce qu'elle nous doit).

### 4.1 La TVA collectée : une vente taxable

| Ligne | Valeur |
|---|---|
| Client | Client Divers |
| Article | Fumier — **12 tonnes à 45,000 TND** |
| Total HT | **540,000 TND** |
| TVA collectée 19 % | **102,600 TND** |
| Total TTC | **642,600 TND** |

**Chemin de clics** : `/app/sales-invoice` → ouvrir `vente_taxable`.
Montrer la ligne de taxe : `4367 - État - TVA collectée - HMD`, 19 %.

Écritures : `411 Clients` débit 642,600 / `708 Produits annexes` crédit 540,000 /
`4367 TVA collectée` crédit 102,600.

### 4.2 Le lait, lui, sort sans TVA

Ouvrir la dernière facture de lait (`/app/decompte-lait-mensuel`, puis le lien
*Facture*) : **aucune ligne de taxe**. Le lait cru livré à la centrale n'est pas
taxé. C'est la situation normale d'une ferme laitière — et c'est exactement ce
qui produit le résultat du point suivant.

### 4.3 La position TVA du mois

```bash
bench --site hmd.agro execute \
    hmd_agro.hmd_agro.setup.finance.simulations.apercu_tva \
    --kwargs "{'date_debut': '2026-08-01', 'date_fin': '2026-08-31'}"
```

Sortie attendue **le jour de la simulation** (avant tout autre mouvement du
mois) :

```
    TVA collectée   (4367, ventes)   :      102.600 TND
    TVA déductible  (4366, achats)   :     2653.200 TND
    ----------------------------------------------
    Solde                            :    -2550.600 TND  → CRÉDIT DE TVA REPORTABLE
```

> 2 653,200 = 2 565,000 (aliment) + 53,200 (vidange) + 35,000 (médicament).

**Le message à faire passer** : la ferme achète tout à 19 % et vend du lait non
taxé — elle est **structurellement en crédit de TVA**. Ce crédit se reporte de
mois en mois ; il ne se voit que si la TVA est ventilée correctement à la
saisie, ce que fait le système facture par facture.

### 4.4 La même chose à l'écran, sans terminal

`/app/query-report/Trial Balance` (**Balance générale**), période = le mois :
lire les deux lignes `4366` et `4367`. Le solde débiteur de `4366` moins le
solde créditeur de `4367`, c'est le crédit de TVA.

Pour le détail pièce par pièce : `/app/query-report/General Ledger`
(**Grand Livre**), filtre *Compte* = `4366 - État - TVA déductible - HMD`.

---

## 5. La synthèse : où tout cela se retrouve

### 5.1 Au Grand Livre

`/app/query-report/General Ledger`, période = le jour de la simulation. On
retrouve les 4 factures + la sortie de stock du traitement, et les comptes
suivants ont bougé :

| Compte | Mouvement | D'où il vient |
|---|---|---|
| `32` Stocks intrants | +12 941,200 / +500 / −50 | achats aliment + médicament, sortie traitement |
| `401` Fournisseurs | 16 065,000 + 333,200 + 535,000 | les 3 factures d'achat |
| `4366` TVA déductible | +2 653,200 | les 3 factures d'achat |
| `4367` TVA collectée | +102,600 | la vente de fumier |
| `411` Clients | +642,600 | la vente de fumier |
| `602` Consommation de médicaments | +50,000 | le traitement |
| `605` Coût des marchandises vendues | +558,800 | régularisation du stock négatif — **site de démo seulement**, cf. § 1 |
| `615` Entretien | +280,000 | la vidange |
| `708` Produits annexes | +540,000 | la vente de fumier |

### 5.2 Sur le coût du litre

`/app/query-report/Rapport Periodique` → filtre **Section = Indicateurs**.

| Ligne du rapport | Effet de la simulation |
|---|---|
| *Frais Médicaments* | **+ 50 DT** (le traitement) |
| *Frais Entretien & Réparations (615)* | **+ 280 DT** (la vidange) |
| *Charges Totales* | **+ 330 DT** — plus 558,80 DT de régularisation sur `605` si le stock de concentré était négatif (site de démo, § 1) |
| *Produit Brut (total produits)* | **+ 540 DT** (le fumier) |
| *Coût Complet / L (toutes charges)* | monte des charges ci-dessus ÷ litres produits |
| *Coût du Litre hors Amortissement* | idem (aucun amortissement en jeu ici) |
| *Frais Concentré* / *Coût Alimentaire / L* | **inchangés aujourd'hui**, ils monteront dès la prochaine distribution au nouveau CMP de 1,350 |
| *Résultat de la Période* | **+ 210 DT** (540 de produit − 330 de charges), hors régularisation |

La cellule *Coût Complet / L* se colore toute seule : vert sous
`objectif_cout_litre` (0,65 DT/L), orange jusqu'à `objectif_cout_litre_alarme`
(0,85), rouge au-delà. Ces deux seuils sont dans
`/app/hmd-configuration` — aucune valeur n'est écrite en dur dans le code.

### 5.3 Le contrôle de cohérence

`/app/query-report/Controle Coherence Finance`, période = le mois.
Toutes les lignes doivent rester **OK** après la simulation : le Grand Livre est
équilibré, les comptes requis existent, les coûts sont valorisés. C'est
l'argument de fin : « on ne vous demande pas de nous croire, le système
s'auto-contrôle. »

---

## 6. Questions probables de M. Samir — et où trouver la réponse à l'écran

**« Si j'achète de l'aliment, pourquoi le coût du litre ne bouge pas ? »**
Parce qu'un achat de stock n'est pas une charge : c'est un déplacement d'argent
vers le magasin. Écran : Grand Livre de la facture — le débit est sur `32`
(compte de bilan), pas sur un compte de charge. La charge apparaît à la
distribution, ligne *Frais Concentré* du Rapport Periodique.

**« Et si le fournisseur augmente son prix, je le vois où ? »**
`/app/item/ALI-Concentré VL Démo` → *Grand livre des stocks* : le CMP passe de
1,250 à 1,350 dès la réception. Toutes les distributions suivantes sortent au
nouveau prix — c'est automatique, on ne re-saisit aucun prix nulle part.

**« Pourquoi 7 % sur le médicament et 19 % sur l'aliment ? »**
Ce sont les taux tunisiens, et ils sont **paramétrés, pas codés** :
`/app/purchase-taxes-and-charges-template` contient les modèles 19 / 13 / 7 %,
et `/app/sales-taxes-and-charges-template` les modèles 19 / 7 / 0 %. On choisit
le modèle dans la facture ; si un taux change, on change le modèle, pas le
logiciel.

**« Ma TVA, je la déclare comment ? »**
Balance générale du mois, comptes `4366` et `4367` (§ 4.4), ou la commande
`apercu_tva`. Aujourd'hui le solde est un **crédit** de 2 550,600 TND.

**« Pourquoi je suis toujours en crédit de TVA ? »**
Parce que le lait cru livré à la centrale sort sans TVA alors que les intrants
sont achetés à 19 %. Écran : la facture de lait (aucune ligne de taxe) à côté de
la facture d'aliment (2 565 TND de TVA). Ce n'est pas une anomalie du logiciel,
c'est la structure de l'activité.

**« Le lait de la vache traitée, il part quand même en cuve ? »**
Non. `/app/animal/<la vache>` : *Attente lait active* cochée jusqu'à J+3 ; et
sur la page **Saisie Traite** la vache est signalée au trayeur. Le compteur
« Animal Sous Traitement » de l'espace HMD AGRO le rappelle en permanence.

**« Qui a saisi quoi, et quand ? »**
Chaque document a son onglet **Connexions / Activité** : auteur, horodatage,
versions successives. Rien ne s'efface : une facture erronée s'**annule**
(docstatus 2) et reste en base pour l'audit — le montrer sur n'importe quelle
facture, menu ⋯ → *Annuler*, **sans valider** en séance.

**« Et si je veux entrer une facture d'entretien tracteur, je passe par où ? »**
Deux portes, les deux atterrissent sur le compte `615` :
la **facture d'achat** (§ 2) quand il y a une facture fournisseur, ou la fiche
**Intervention** (`/app/asset-repair`) quand on veut aussi tracer la panne, la
durée d'arrêt et les pièces changées. Le Rapport Periodique additionne les deux
dans *Frais Entretien & Réparations (615)*.

**« Je peux relancer la démonstration ? Ça va faire des doublons ? »**
Non. La commande est idempotente : elle reconnaît ses propres pièces par un
marqueur `SIMU_*` dans les remarques et ne les recrée pas. Le montrer en la
relançant en direct : elle affiche `[skip]` sur les cinq documents.

**« Est-ce que ça peut abîmer mes vraies écritures ? »**
Non. La simulation n'écrit que des documents neufs, et elle **refuse de
démarrer** (`ERR-SIM-05`) si l'exercice concerné est gelé ou clôturé.

**« C'est quoi cette ligne de 558,800 sur le compte 605 dans la facture
d'aliment ? »** *(ne se pose que sur le site de démonstration)*
Le stock de concentré était **négatif** avant l'achat : la base de démonstration
distribue des rations depuis des semaines sans qu'on ait saisi les factures
d'achat correspondantes. Quand la marchandise rentre enfin, à 1,350 au lieu de
1,250, le système doit revaloriser les 5 588 kg déjà sortis : 5 588 × 0,10 =
558,800 DT, qu'il envoie en charge plutôt que de les stocker (on ne peut pas
stocker de la marchandise déjà consommée). **C'est le symptôme du problème, pas
une erreur** : sur une base tenue à jour, où les achats sont saisis quand ils
arrivent, cette ligne n'existe pas et les 13 500 DT vont intégralement au
compte de stock `32`. On peut le vérifier en direct sur la facture du
médicament (§ 3.1) : stock positif → écriture à trois lignes, sans `605`.

---

## 7. Après la réunion

Les pièces de simulation restent en base — elles sont datées du jour et
identifiables par le marqueur `SIMU_` dans leurs remarques. Pour les retirer
d'un site destiné à la production, les **annuler** une par une depuis la liste
(`/app/purchase-invoice`, filtre *Remarques* contient `SIMU_`) : ERPNext
contrepasse alors proprement le stock et le Grand Livre. Ne jamais les supprimer
en base directement.

Le test automatisé
`bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_simulations.run`
fait exactement ce ménage puis repose le scénario ; ne pas le lancer pendant la
réunion.
