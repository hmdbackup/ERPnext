# Scénario de vérification — la clé de répartition des frais généraux

Pour reprendre avec Aymen le test qu'il a demandé le 03/09 : « saisis une
facture, valide-la, et regarde si les montants apparaissent bien répartis ».
Environnement : site local `hmd.agro` (http://localhost:8080), données
réelles ; jeu de démo `demo_finance/seed_demo_scrum_10_11.py` (`run` / `clear`)
déjà chargé — ou à rejouer à la main comme ci-dessous.

## 0. Les termes

| À l'écran (ERPNext) | Ce que c'est |
|---|---|
| **Centre de coûts** (Cost Center) | l'atelier : Lait, Cultures - Fourrage, Élevage - Génisses, Traction, Frais Généraux |
| **Cost Center Allocation** | la **clé de répartition** : centre principal + date de début + % par centre (= 100 %) |
| **Vue Grand Livre** (Accounting Ledger) | les écritures comptables d'une pièce validée |

## 1. Poser la clé (une fois) — 2 min

Espace **HMD AGRO › Clé de répartition FG** (ou Comptabilité › Cost Center
Allocation) › Nouveau :

- Centre de coûts principal : **Frais Généraux - HMD**
- Valide à partir du : une date **postérieure à la dernière écriture** du
  centre (ERPNext le vérifie et refuse sinon). Sur la copie locale : ≥ 22/08/2026.
- Pourcentages : Lait 60 · Cultures - Fourrage 25 · Élevage - Génisses 15
  (total 100, sinon refus).
- Enregistrer, **Valider**.

À montrer : une clé avec 90 % est refusée ; le centre principal ne peut pas
figurer dans la table ; deux clés à des dates différentes coexistent
(historique).

## 2. Saisir une facture à deux lignes, sans rien répartir — 3 min

Achats › Facture d'achat › Nouveau :

- Fournisseur : STEG (ou « Fournisseur Divers »).
- Date de la pièce : après la date de la clé.
- Centre de coûts (en-tête) : **Frais Généraux - HMD** — il se propage aux lignes.
- Ligne 1 : Électricité, compte 606, 1 200 DT. Ligne 2 : Eau, compte 606, 300 DT.
- **Enregistrer** → l'en-tête affiche en bleu : « Clé de répartition Frais
  Généraux en vigueur au … : **Lait 60 % · Cultures - Fourrage 25 % ·
  Élevage - Génisses 15 %** — les écritures comptables seront réparties ainsi
  à la validation », et un bouton **Clé de répartition** ouvre l'allocation.
- **Valider**.

Contre-exemple à montrer : dater la pièce **avant** la clé → à l'enregistrement,
message orange « aucune clé de répartition en vigueur au … : la charge restera
à Frais Généraux, hors coût du litre ». (En mode strict — Configuration HMD ›
« Clé de répartition obligatoire » — la sauvegarde est refusée, ERR-FIN-11.)

## 3. Regarder les écritures comptables — 2 min

Sur la facture validée : menu **⋯ › Vue Grand Livre**. Attendu pour le compte
606 (1 500 DT au total) :

| Centre de coûts | Débit |
|---|---|
| Lait - HMD | 900,000 |
| Cultures - Fourrage - HMD | 375,000 |
| Élevage - Génisses - HMD | 225,000 |

Aucune ligne sur Frais Généraux. Le fournisseur (401) n'est pas réparti.
C'est la réponse à la remarque 4 d'Aymen : la répartition est **dans le Grand
Livre**, proportionnelle, sur chaque ligne, sans saisie.

## 4. Le rapport — 3 min

HMD AGRO › **Rapport Performance**, Période = Mois, Date = 29/08/2026 :

- Section **Frais Généraux — répartition par centre de coûts** :
  - « Clé Frais Généraux en vigueur au 31/08/2026 : Lait 60 % · … (CC-ALLOC-…, depuis le 01/08/2026) »
  - Électricité 1 200 › « └ Lait 60 % · Cultures - Fourrage 25 % · Élevage - Génisses 15 % »
  - Eau 300 › même ligne ; Assurances 900 › même ligne
  - Total imputé à Frais Généraux — pièces listées : **2 400**
  - Réparti par la clé vers les centres de coûts (écritures comptables) : **2 400**
  - dont part Lait — envoyée par la clé : **1 440**
  - Total resté à Frais Généraux (Grand Livre) : −1 201 → « Autres pièces
    restées à Frais Généraux (stock, avoirs…) » en orange : ce sont les
    mouvements de stock imputés au centre par défaut, **avant** la clé —
    paramétrage à corriger, pas du code.
  - **Contrôle — écritures comptables = clé (aucun écart) : 0**
- Section **Coût du Lait (détail)** : « Quote-part Frais Généraux — envoyée à
  Lait par la clé de répartition (déjà au Grand Livre) » = 1 440 ; le TOTAL
  est le Lait tel qu'il est au Grand Livre.
- Période = **Année** : la « Location bureau — juillet (avant la clé) » 300 DT
  apparaît « └ non répartie — aucune clé au 28/07/2026 », en orange.

## 5. Changer la clé — 1 min

Nouvelle Cost Center Allocation sur Frais Généraux, valide à partir d'une date
ultérieure, autres pourcentages. Les pièces antérieures gardent l'ancienne
clé ; les suivantes prennent la nouvelle. Le rapport nomme la clé en vigueur à
la fin de la période demandée.

## 6. Remise à zéro

```
bench --site hmd.agro execute hmd_agro.demo_scrum_10_11.clear
```
(supprime aussi la clé de démonstration).
