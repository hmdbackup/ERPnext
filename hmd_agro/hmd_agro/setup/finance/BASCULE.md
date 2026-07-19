# FIN-S60 — Bascule comptable (a-nouveaux / balances d'ouverture)

Procédure de reprise des soldes à la date de bascule convenue avec le
comptable (à faire **une seule fois**, quand les soldes réels sont fournis).

## Pré-requis (déjà en place via `socle_comptable`)

- Plan SCE en TND sur la company `hmd-agro`, exercice ouvert.
- Compte d'attente **`471 - Comptes d'attente - Ouverture`** (type
  *Temporary*) : c'est la contrepartie transitoire des écritures d'ouverture.

## Procédure

1. **Arrêter la date de bascule** avec Samir/le comptable (idéalement un début
   d'exercice). Aucune écriture antérieure à cette date dans ERPNext.
2. **Balances bilan** — une écriture *Journal Entry* de type **Opening Entry**
   (`is_opening = Yes`) datée de la veille de la bascule :
   - débit de chaque compte d'actif (2x/3x/4x/5x) pour son solde,
   - crédit de chaque compte de passif/capitaux (1x/40x/42x…),
   - le déséquilibre transite par **471** puis se solde à zéro une fois
     toutes les lignes saisies.
3. **Encours clients/fournisseurs** — passer par *Opening Invoice Creation
   Tool* (une facture d'ouverture par tiers, contrepartie **471**), pour que
   les lettrages/paiements futurs fonctionnent par tiers.
4. **Stocks** — *Stock Reconciliation* datée de la bascule avec quantités ET
   valorisations réelles (pose le `valuation_rate` initial de chaque intrant).
5. **Immobilisations** — un *Asset* par équipement avec
   `is_existing_asset = 1`, valeur brute, amortissements cumulés
   (`opening_accumulated_depreciation`) et durée restante ; catégories déjà
   mappées sur 22x/28x/681 (`setup_immobilisations`).
6. **Vérification** : Balance Sheet à la date de bascule = balance fournie
   par le comptable ; compte 471 soldé ; `verify_native_valuation` vert.

## Garde-fous

- Les scripts du socle refusent toute bascule si des GL Entries existent
  (ERR-FIN-01/02/03) — la reprise se fait sur un livre vierge.
- Ne jamais antidater d'écritures opérationnelles avant la date de bascule.
