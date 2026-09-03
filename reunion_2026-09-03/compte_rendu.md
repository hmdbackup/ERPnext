# Compte rendu — revue de la démo « frais généraux » avec Aymen, 03/09/2026

Participants : Aymen (superviseur), Mohamed Slim. Interrompue par une urgence
côté Mohamed ; la dernière remarque d'Aymen n'avait pas été comprise sur le
moment — elle est reprise ici, et **c'est elle qui change le modèle**.

**Décision (prise dans la foulée, livrée le jour même) : la répartition des
frais généraux n'est plus saisie sur la charge. Elle est portée par une
« Cost Center Allocation » ERPNext — la clé — fixée une fois, qui ventile les
écritures comptables à la validation.** Le compte rendu du 26/08 reste valable
sur le fond (une liste « centre de coûts + % » à 100 %, fixée une fois, au
niveau du comptable) ; ce qui change, c'est *où* elle vit et *ce qu'elle fait*.

---

## 1. Ce qu'Aymen a dit, ramené à quatre demandes

1. **Vocabulaire.** « Ça ne s'appelle pas Atelier, ça s'appelle Centre de
   coûts. » L'écran doit parler ERPNext.
2. **Redondance.** Le centre de coûts est déjà choisi sur la facture. Le
   re-saisir dans une table, ligne par ligne, est un doublon : « si tu choisis
   Frais généraux là-haut, pourquoi devoir le refaire ensuite ? ».
3. **Volume.** « Une facture avec deux pages de lignes, une pharmacie, tu vas
   répartir 20 / 80 sur chaque ligne manuellement ? » Le pourcentage se
   configure **une fois, globalement**, puis s'applique à toute la pièce.
4. **Effet comptable — la remarque non comprise.** « Vérifie si, quand on
   valide la facture, cela se reflète correctement dans les écritures
   comptables pour chaque centre de coûts de manière proportionnelle. Fais un
   test : saisis une facture, valide-la, regarde si les montants apparaissent
   bien répartis. » Autrement dit : la répartition doit être **dans le Grand
   Livre**, pas seulement dans un rapport.

Le point 4 contredisait la conception du 28/08 (« la répartition est
analytique, le Grand Livre reste imputé à Frais Généraux »). Les points 2 et 3
contredisaient le modèle « une table par ligne de charge ». Mais le compte
rendu du 26/08 porte déjà la phrase de M. Samir qui tranche : la clé « se fixe
une fois […] puis elle s'applique à chaque saisie ». Aymen demande la même
chose que Samir.

## 2. La solution retenue : Cost Center Allocation (natif ERPNext v15)

ERPNext embarque le DocType **Cost Center Allocation** : un centre de coûts
principal, une date de début de validité, une table de pourcentages vers
d'autres centres de coûts (total 100 % obligatoire). À chaque validation d'une
facture d'achat ou d'une écriture de journal, ERPNext éclate **chaque écriture
du Grand Livre** imputée à ce centre selon ces pourcentages
(`erpnext.accounts.general_ledger.distribute_gl_based_on_cost_center_allocation`).

| Demande d'Aymen | Réponse |
|---|---|
| Vocabulaire | L'écran est celui d'ERPNext : « Centre de coûts », « Cost Center Allocation ». Le rapport dit « répartition par centre de coûts ». |
| Redondance | Le comptable choisit **un seul** centre de coûts (Frais Généraux) en en-tête de facture. Rien d'autre à saisir. |
| Volume | La clé est configurée une fois par l'administrateur ; une facture de deux pages est ventilée ligne par ligne **par ERPNext**, sans saisie. |
| Effet comptable | Les écritures comptables sortent réparties. Le test qu'il demande est dans `test_repartition_charges` (cas 1 à 3) **et** sur le rapport (ligne « Contrôle — écritures comptables = clé »). |

Les exemples de M. Samir (gardien d'étable 100 % Lait, gardien parc +
fromagerie 50 / 50) se modélisent sans code : un second centre de coûts
« clé » (par ex. « Frais Généraux Parc ») avec sa propre allocation, que le
comptable choisit à la saisie. Pour les salaires, le registre du personnel
porte déjà sa répartition par centre de coûts (FIN-S42) : la clé ne concerne
que ce qui est imputé à Frais Généraux.

## 3. Ce qui a changé dans le code (branche `finance/socle-comptable`)

**Retiré** (patch `v1_10.retirer_repartition_par_ligne`, idempotent) :
- la table « Répartition par atelier » sur Facture d'achat et Écriture de
  journal (4 Custom Fields) et le DocType enfant `Repartition Atelier Charge` ;
- les règles ERR-FIN-12 à ERR-FIN-18 (total 100 %, doublon, groupe, bornes,
  ligne déplacée…) : ERPNext les porte sur la clé elle-même ;
- le bloc client `hmd_repartition` (compteur « il manque X % »).

**Ajouté / réécrit** :
- `finance_kpis.cle_repartition(cost_center, date)` : la clé en vigueur à une
  date, **même règle de recherche que le Grand Livre** (dernière allocation
  soumise dont `valid_from` ≤ date) ;
- `finance_kpis.repartitions_frais_generaux` : liste les lignes de charge
  imputées à Frais Généraux (factures + écritures), joint à chacune la clé de
  sa date, et **rejoue la clé contre le Grand Livre** pièce par pièce
  (`controle_gl`) ;
- `finance_kpis.charges_lait` : le total du Lait est **lu tel quel au Grand
  Livre** (la clé y a déjà envoyé la part des frais généraux) ; la quote-part
  est isolée pour information ; `LAIT_SEUL` la retire poste par poste ;
- `repartition_charges.verifier_cle_frais_generaux` (hook `validate`) : une
  charge Frais Généraux à une date **sans clé en vigueur** → avertissement
  orange (elle restera à Frais Généraux, hors coût du litre) ; en mode strict
  (`repartition_fg_obligatoire`, HMD Configuration) → **ERR-FIN-11** bloque ;
- `repartition_charges.cle_en_vigueur` (whitelist) + `hmd_cle_repartition`
  (client) : dès qu'une ligne est imputée à Frais Généraux, l'en-tête de la
  facture / de l'écriture affiche « Clé Frais Généraux en vigueur au … :
  Lait 60 % · Cultures 25 % · Génisses 15 % — les écritures comptables seront
  réparties ainsi à la validation », et un bouton « Clé de répartition » ouvre
  l'allocation ;
- Rapport Performance, section **« Frais Généraux — répartition par centre de
  coûts »** : la clé en vigueur, chaque charge et sa ligne « └ Lait 60 % · … »,
  les charges postées **avant** toute clé nommées en orange, « Réparti par la
  clé », « dont part Lait », « Total resté à Frais Généraux (Grand Livre) »,
  et la ligne de **contrôle écritures = clé** (rouge au moindre écart) ;
- Workspace HMD AGRO : raccourci **« Clé de répartition FG »** (leçon du
  05/08 : un écran inatteignable depuis le menu ne compte pas).

**Tests** (site local hmd.agro, données réelles) : `test_repartition_charges`
45/45 — dont le test demandé par Aymen (facture à deux lignes, rien à saisir,
Grand Livre réparti 855 / 665 / 380 et 45 / 35 / 20) ; `test_ventilation_atelier`
38/38 ; `test_rapport_performance` 61/61 ; `test_finance_kpis` 14/14 ;
`test_cost_flow` 9/9 ; `test_maintenance` 61/61 ; `test_rapport_interventions`
67/67 ; `test_personnel` 54/54 ; `test_immobilisations` 13/13 ;
`test_controle_coherence` 15/15 ; `test_tableau_amortissement` 19/19.

## 4. Ce qu'il faut savoir avant de poser la clé sur le vrai site

- **La date de début doit être postérieure à la dernière écriture du centre.**
  ERPNext refuse une allocation dont `valid_from` ≤ dernière écriture sur
  Frais Généraux (sur la copie locale : 21/08/2026). La clé n'est **pas
  rétroactive** : les frais généraux déjà comptabilisés restent à Frais
  Généraux, le rapport les nomme « non répartis — pièces sans clé à leur
  date ». Pour l'exercice en cours, c'est M. Samir qui dit s'il veut une
  reprise manuelle (écriture de journal) ou un départ à la date de la clé.
- **Le centre de coûts par défaut de la société est Frais Généraux.** Toute
  ligne saisie sans centre de coûts y tombe — donc est répartie par la clé.
  C'est cohérent avec « Frais Généraux = fourre-tout », mais à dire au
  comptable. Les **mouvements de stock** imputés à ce centre par défaut (déjà
  signalés le 29/08 : −1 201 DT sur août) seront eux aussi répartis par la clé
  à partir de sa date : le paramétrage des entrepôts / articles reste à
  corriger, ce n'est pas du code.
- **Changer la clé** = créer une nouvelle allocation avec une nouvelle date ;
  l'ancienne continue de s'appliquer aux pièces antérieures (cas 4 du test).
  C'est exactement le « au 31 décembre, à la clôture » de M. Samir.
- **Les arrondis** : ERPNext arrondit chaque part au millime ; le contrôle du
  rapport tolère un millime par part, pas davantage.

## 5. Points secondaires vus pendant la démo

- « C'est quoi la série ? » — c'est la **série de numérotation** ERPNext de la
  facture (`ACC-PINV-.YYYY.-`), pas le numéro de facture du fournisseur ; ce
  dernier va dans « N° de facture fournisseur » (`bill_no`).
- « Ça dépasse 100 % » quand le centre d'en-tête n'était pas Frais Généraux :
  c'était ERR-FIN-11 de l'ancienne table, au libellé trompeur. Disparu avec la
  table.
- **Dupliquer** existe : menu « ⋯ » en haut à droite de la facture → Dupliquer.
- Les écritures comptables d'une facture se lisent par « ⋯ › Vue Grand Livre »
  (« View › Accounting Ledger »), pas par le lien Journal Entry.

## 6. À faire

- [ ] Reprendre la démo avec Aymen selon `scenario_verification_cle.md` (ce
      dossier) — 10 minutes, sur le site local, données réelles.
- [ ] Faire valider par M. Samir les pourcentages de la clé et sa date de
      début (proposition : le 1er du mois suivant la dernière écriture).
- [ ] Décider avec lui du sort des frais généraux déjà comptabilisés avant la
      clé (reprise ou non).
- [ ] Corriger le paramétrage stock (centre de coûts par défaut) — hors code.
- [ ] Jira : SCRUM-10 — commentaire « répartition portée par Cost Center
      Allocation depuis le 03/09 ; table par ligne retirée ».
