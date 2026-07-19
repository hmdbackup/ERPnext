# Livraison Finance — HMD Agro (contrôle de gestion sur ERPNext natif)

Branche : `finance/socle-comptable` (basée sur `origin/main`).
Suite de tests finance : **86/86 verts** (8 modules). Chaque commit référence
ses stories Jira `FIN-S*` (backlog `finance_backlog_jira.csv`).

## Commits ↔ stories

| Commit | Epic | Stories | Contenu |
|---|---|---|---|
| `40d8593` | A — Socle | S01, S02 | Company `hmd-agro` TND/Tunisie, plan SCE 76 comptes, TVA 19/13/7/0, 5 Cost Centers ateliers, dimensions Lot/Batiment (`setup/finance/socle_comptable.py`) |
| `2de4c06` | B — Valorisation | S10–S12 | Consommations valorisées au CMP natif (garde-fou CMP=0 jamais bloquant), restaurations symétriques, DT/L réel + DT/vache (présente & lactante) au rapport mensuel |
| `587d60b` | C — Recettes | S20–S23 | Items LAIT-CRU/FUMIER/ANIMAL-VENTE (701/708/702), facture lait de période idempotente (prix = Item Price + primes TB/TP config), facture auto à la vente d'animal avec annulation compensatoire |
| `6949776` | D+E — Immo & charges | S30, S40, S41 | 5 Asset Categories sur 22x/28x/681, CF `Asset-id_batiment`, amortissement linéaire auto, salaires ventilés par atelier (`post_salaires`), modes de paiement 54/532 |
| `81da51e` | F — Pilotage | S50, S51 | `finance_kpis.gl_sums` : CA lait, produit brut, charges, MO, EBE, résultat, coût complet/L, IOFC (+/VL/j) au rapport mensuel ; seuils `HMD Configuration` (patch `v1_6`) + coloration vert/orange/rouge |
| `5d0e03b` | G — Bascule & droits | S60, S61 | Rôle « Éleveur HMD » (zéro accès comptable — test 8/8), procédure a-nouveaux (`BASCULE.md`), seed démo E2E |

## Démarrage sur une instance (ordre)

```bash
bench --site <site> migrate     # schéma + patch v1_6 (seuils)
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.socle_comptable.setup_socle_comptable
bench --site <site> execute hmd_agro.hmd_agro.setup.stock_foundation.create_stock_foundation
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.recettes.setup_recettes
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.immobilisations.setup_immobilisations
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.roles.setup_roles
# démo complète (optionnel, site de test uniquement) :
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.seed_demo_finance.run
```

Tout est idempotent (re-run = no-op). Les scripts refusent de toucher un
livre non vierge (ERR-FIN-01/02/03).

## Démo (déjà en place sur le site local `hmd.agro`)

Rapport Mensuel → Indicateurs (juillet 2026) affiche avec données réelles :
production 1 109 L, frais concentré/fourrage réels (SLE), **coût
alimentaire 2.88 DT/L (rouge)**, DT/vache présente/lactante, **CA lait
1 650 TND**, EBE, résultat, **IOFC/VL/j (rouge)** — seuils modifiables dans
HMD Configuration → Seuils Finance.

## Décisions client en attente (bloquantes pour la suite)

1. **Grille qualité lait de la centrale** (primes TB/TP) → remplir
   `lait_prime_tb_par_point` / `lait_prime_tp_par_point` (aujourd'hui 0 =
   prix plat) et le prix de référence réel.
2. **FIN-S31 cheptel** : actif biologique amortissable (catégorie « Cheptel
   reproducteur » déjà paramétrée) vs stock — décision comptable.
3. **Facturation lait** : la ferme facture (job mensuel actif) OU import du
   décompte centrale — ne jamais activer les deux (RG-FIN-12).
4. **Date de bascule + balances réelles** pour dérouler `BASCULE.md`.
5. **Backup BD réelle** (demande à Sami) pour valider sur données de prod.

## Tests

```bash
bench --site <site> execute hmd_agro.hmd_agro.tests.test_valorisation_cmp.run   # 7/7
bench --site <site> execute hmd_agro.hmd_agro.tests.test_cost_flow.run          # 9/9
bench --site <site> execute hmd_agro.hmd_agro.tests.test_semence_dual_write.run # 13/13
bench --site <site> execute hmd_agro.hmd_agro.tests.test_stock_integration.run  # 7/7
bench --site <site> execute hmd_agro.hmd_agro.tests.test_recettes.run           # 15/15
bench --site <site> execute hmd_agro.hmd_agro.tests.test_immobilisations.run    # 13/13
bench --site <site> execute hmd_agro.hmd_agro.tests.test_finance_kpis.run       # 14/14
bench --site <site> execute hmd_agro.hmd_agro.tests.test_roles_finance.run      # 8/8
```
