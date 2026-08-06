# Livraison Finance — HMD Agro (contrôle de gestion sur ERPNext natif)

Branche : `finance/socle-comptable` (basée sur `origin/main`).
Suite de tests : **408/408 verts** (18 modules — 336 tests finance + 72 tests
du flux E2E `test_full_flow`), exécutés sur bench le 06/08/2026. Chaque commit
référence ses stories Jira `FIN-S*` (backlogs `finance_backlog_jira.csv` et
`finance_backlog_jira_reunion_2026-08-05.csv`).

## Commits ↔ stories

| Commit | Epic | Stories | Contenu |
|---|---|---|---|
| `40d8593` | A — Socle | S01, S02 | Company `hmd-agro` TND/Tunisie, plan SCE 77 comptes, TVA 19/13/7/0, 5 Cost Centers ateliers, dimensions Lot/Batiment (`setup/finance/socle_comptable.py`) |
| `2de4c06` | B — Valorisation | S10–S12 | Consommations valorisées au CMP natif (garde-fou CMP=0 jamais bloquant), restaurations symétriques, DT/L réel + DT/vache (présente & lactante) au rapport mensuel |
| `587d60b` | C — Recettes | S20–S23 | Items LAIT-CRU/FUMIER/ANIMAL-VENTE (701/708/702), facture lait de période idempotente, facture auto à la vente d'animal avec annulation compensatoire |
| `6949776` | D+E — Immo & charges | S30, S40, S41 | 5 Asset Categories sur 22x/28x/681, CF `Asset-id_batiment`, amortissement linéaire auto, salaires ventilés par atelier (`post_salaires`), modes de paiement 54/532 |
| `81da51e` | F — Pilotage | S50, S51 | `finance_kpis.gl_sums` : CA lait, produit brut, charges, MO, EBE, résultat, coût complet/L, IOFC (+/VL/j) au rapport mensuel ; seuils `HMD Configuration` (patch `v1_6`) + coloration vert/orange/rouge |
| `5d0e03b` | G — Bascule & droits | S60, S61 | Rôle « Éleveur HMD » (zéro accès comptable — test 8/8), procédure a-nouveaux (`BASCULE.md`), seed démo E2E |
| `4403f05` | H — Données manquantes | S24, S25, S31, S32, S42, S70 | Les six trous restants : registre Personnel, interventions équipements, écart lait valorisé, grille prix qualité, cheptel à l'actif, contrôle de cohérence (détail ci-dessous) |

## Réunion 05/08/2026 — corrections M. Samir (stories S80–S93)

Backlog dédié : `finance_backlog_jira_reunion_2026-08-05.csv` ; compte-rendu :
`reunion_2026-08-05/compte_rendu.md`. Patches `v1_8` appliqués par
`bench migrate`.

| Commit | Stories | Contenu |
|---|---|---|
| `a3ff762` | S80–S91 (socle) | Config v1_8 : charges patronales 30 %, `pfe_lc_cible` 2,2, alarme L/C 1,8, coût horaire équipement 25 DT/h ; registre des 5 patches ; fixtures partagées |
| `78b7e5b` | S80, S81 | Assets cheptel titrés au **N° travail** (+ patch de reprise, resync au renommage) ; ID provisoire `99999xxxxx` au vêlage → `enregistrer_boucle_officielle`, ID officiel verrouillé (ERR-ANI-01..04) |
| `77ac89e` | S82, S83, S84 | Taux charges surchargeable par salarié ; **historique de salaire immuable** (taux effectif figé par ligne, `masse_salariale` datée) ; DocType `Prime Personnel` + action groupée « Attribuer une prime » (refus mois posté ERR-PRIME-04) |
| `84e55ec` | S85, S86 | **Décompte Lait Mensuel** soumis = recettes figées par période (ERR-DLM-04..06), grille verrouillée après règlement (ERR-GRL-06), backfill des factures existantes ; palier VOLUME + ajustement manuel motivé |
| `17f0e4e` | S87, S88, S89 | L/C rouge < 1,8 · cible 2,2 (rapport + Number Card + boot JS) ; « Coût du Litre hors Amortissement » ; IOFC explicité ; rapport **Rapport Performance** (Semaine/Mois, export Excel propre) |
| `c770be5` | S90, S91 | Rapport **Tableau Amortissement** (durée/mois amortis/cumul/restant, sortis inclus) ; champ `Asset.cout_horaire` + résolveur |
| `593bc01` | S92 | Version 0.2.0, erpnext épinglé v15.95.2, build `--no-cache`, DEPLOY.md révisé, `runbook_alignement_versions.md` (cause racine du site obsolète) |
| *(ce commit)* | S93 | Spécification coût de revient génisse + facturation interne (`spec_cout_genisse_facturation_interne.md`) — implémentation après validation |

### Audit avant revue client (06/08/2026)

Une vérification adversariale (revue de code + exécution réelle sur bench) a
trouvé **trois défauts que M. Samir aurait vus**, tous corrigés :

| Défaut trouvé | Correction |
|---|---|
| **Les 30 % de charges patronales ne s'appliquaient jamais.** Le gel de l'historique (S83) avait figé l'ancien taux 16,57 % pour *tous* les mois, y compris à venir : août calculait encore 936 DT au lieu de 1 695 DT. | Patch `v1_8/appliquer_taux_charges_30` : le changement de taux est journalisé comme un **événement daté** (16,57 % jusqu'au 31/07, 30 % à partir du 01/08) et le coût employeur de chaque fiche est recalculé. Vérifié : juin/juillet 16,57 %, août/septembre 30 %. |
| **Interface mi-française mi-anglaise** — le reproche exact de la réunion : la langue du site était `en`, donc tout l'écran ERPNext natif (Actif, Écriture de Journal, colonnes, boutons) restait en anglais. | Patch `v1_8/set_langue_francaise` : langue du site et des comptes en français, symbole TND `د.ت` → `DT`. Vérifié à l'écran : « Nom de l'Actif », « Statut », « Lieu », « Vue liste ». |
| **Aucun écran finance dans le menu HMD AGRO** — ni Personnel, ni les nouveaux rapports : il fallait connaître l'URL (en réunion : « Personnels c'est devenu où ? »). | Section **Finance & Gestion** ajoutée au workspace + les 3 rapports finance dans « Rapports » ; cartes `L_C` / `PL_VL` renommées en clair. |

Également corrigé : granularités **Jour / Semaine / Quinzaine / Mois** sur le
Rapport Performance (demande « il faut que ce soit flexible »), libellé
« cible 2,2 » en écriture française, paie de juillet postée (la Main d'Œuvre
n'apparaissait nulle part), facture lait en double annulée (11→17 et 14→20
juillet se chevauchaient).

⚠️ **À traiter avant toute démo** (`FIN-S99`) : le jeu de données de
démonstration fausse les indicateurs — les 25 animaux sont dans un seul lot
nourri à la ration vache laitière (9 kg de concentré/jour chacun) alors que
6 vaches seulement produisent, d'où L/C 0,66 et coût du litre 3,37 DT. Le
calcul est juste, les données ne le sont pas : allotir par lot ou charger le
backup de la base réelle.

Décisions client en attente (réunion 05/08) : bande provisoire `99999` à
confirmer auprès de l'autorité d'identification ; primes soumises CNSS ou
non ; saisie des heures d'utilisation des équipements ; questions ouvertes de
la spec génisse ; rebuild du serveur selon le runbook.

## Epic H — ce qui manquait encore

| Story | Trou comblé | Où ça vit |
|---|---|---|
| **FIN-S42** | La MO se postait avec un montant global tapé à la main : aucun registre du personnel, donc le coût MO du litre n'était pas une donnée. | DocType **`Personnel`** (rôle, salaire, contrat, atelier + table de répartition multi-ateliers) → `charges_utils.masse_salariale()` reconstruit l'écriture mensuelle **640 / 647 ↔ 421 / 453** ventilée par atelier, au prorata des jours d'entrée/sortie. Job mensuel `post_salaires_mois_precedent`. Nouveaux KPI : *Coût MO / L* et *Coût MO / vache*. |
| **FIN-S32** | On amortissait le matériel sans jamais savoir ce qu'il coûte à entretenir. | `utils/maintenance_utils.py` : `enregistrer_intervention()` crée l'**Asset Repair** ERPNext *et* poste la charge **615** sur l'atelier de l'équipement (⚠ en v15 un Asset Repair non capitalisé ne produit aucune écriture) ; `planifier_maintenance()` pose le préventif (Asset Maintenance + échéances datées). KPI : *Frais entretien*, *nb interventions*, *Entretien / produit brut* (coloré). |
| **FIN-S25** | Les litres écartés étaient saisis mais jamais convertis en dinars. | `finance_kpis.ecart_lait()` — litres perdus, valeur au prix du litre de la période, % de la production. `Bilan Lait Journalier` calcule désormais son écart **quelle que soit la source** (avant : seulement via la page Saisie Traite). Les écarts négatifs (sur-affectation) sont comptés à part et jamais valorisés. |
| **FIN-S24** | Le prix du lait était plat (`lait_prime_tb/tp_par_point = 0`). | DocType **`Grille Prix Lait`** (+ paliers) : prix de base, paliers TB/TP/germes/cellules, plancher et plafond, période de validité, une seule grille active à la fois. `compute_milk_rate()` lit la grille en vigueur **à la date facturée**, avec repli « prix plat » documenté si aucune grille. La facture trace l'origine du prix dans ses remarques. |
| **FIN-S31** | Le cheptel — premier actif de la ferme — était absent du bilan. | `utils/cheptel_valorisation.py` : une immobilisation par vache (catégorie « Cheptel reproducteur », 225/285), mise en service au **premier vêlage**, valeur d'entrée = prix d'achat réel ou forfait coût d'élevage, reprise de l'existant avec l'amortissement déjà couru. Sortie de l'animal → mise au rebut automatique. **Piloté par `cheptel_mode`, `NON_VALORISE` par défaut** (voir décisions). |
| **FIN-S70** | Tous les chiffres venaient du seed ; rien ne permettait de valider une base réelle. | Rapport **« Controle Coherence Finance »** (+ `run()` console) : 26 contrôles sur 7 domaines — socle, Grand Livre équilibré et imputé, lait produit ↔ facturé, CMP à 0, masse salariale registre ↔ GL, immobilisations amorties, maintenance en retard, sorties d'animaux facturées. Trois issues : OK / ALERTE / ERREUR. |

## Démarrage sur une instance (ordre)

```bash
bench --site <site> migrate     # schéma + patches v1_6 / v1_7 (seuils, personnel, cheptel)
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.socle_comptable.setup_socle_comptable
bench --site <site> execute hmd_agro.hmd_agro.setup.stock_foundation.create_stock_foundation
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.recettes.setup_recettes
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.immobilisations.setup_immobilisations
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.maintenance.setup_maintenance
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.grille_lait.setup_grille_lait
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.roles.setup_roles
# démo complète (optionnel, site de test uniquement) :
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.seed_demo_finance.run
```

Tout est idempotent (re-run = no-op). Les scripts refusent de toucher un
livre non vierge (ERR-FIN-01/02/03).

## Exploitation courante

```bash
# Aperçu de la masse salariale avant de poster (aucune écriture créée)
bench --site <site> execute hmd_agro.hmd_agro.utils.charges_utils.apercu_masse_salariale
# Poster la paie du mois depuis le registre Personnel
bench --site <site> execute hmd_agro.hmd_agro.utils.charges_utils.post_salaires \
  --kwargs "{'periode': '2026-07'}"
# Saisir une intervention sur un équipement (Asset Repair + charge 615)
bench --site <site> execute hmd_agro.hmd_agro.utils.maintenance_utils.enregistrer_intervention \
  --kwargs "{'asset': 'ACC-ASS-2026-00003', 'description': 'Vidange', 'cout': 340}"
# Mettre le cheptel à l'actif (après bascule de cheptel_mode)
bench --site <site> execute hmd_agro.hmd_agro.utils.cheptel_valorisation.synchroniser_cheptel
# Contrôler la cohérence d'une base (typiquement une restauration de prod)
bench --site <site> execute \
  hmd_agro.hmd_agro.report.controle_coherence_finance.controle_coherence_finance.run \
  --kwargs "{'date_debut': '2026-01-01', 'date_fin': '2026-12-31'}"
```

Jobs mensuels automatiques (`hooks.py`) : facture lait du mois écoulé, masse
salariale du mois écoulé, synchronisation du cheptel — tous idempotents et
sans effet tant que les données correspondantes n'existent pas.

## Supports de démo

Regénérables depuis `demo_finance/` (voir son README) — ne pas retoucher les
fichiers produits à la main :

| Support | Contenu |
|---|---|
| `presentation_finance.html` | Deck client, 15 slides, captures réelles du site. `N` = notes du présentateur, `?s=N` ouvre une slide directement. |
| `~/Downloads/demo_finance_hmd.mp4` | Vidéo narrée 1920×1080, ~10 min — une séquence par slide. |
| `~/Downloads/demo_finance_hmd_muette.mp4` | Mêmes slides sans voix (8 s chacune), pour commenter en direct. |
| `finance_backlog_jira.csv` | Backlog complet : 7 epics, 22 stories. |
| `finance_backlog_jira_nouvelles_stories.csv` | Les 5 stories de l'epic H seules — import Jira sans doublon. |

## Décisions client en attente (et ce qui les débloque)

1. **Grille qualité de la centrale** — le moteur est en place, une grille
   « Grille Centrale — provisoire » est active avec des paliers TB/TP
   **indicatifs**. Statut = `PROVISOIRE` : la facture, le rapport et le
   contrôle de cohérence le signalent. Dès réception de la grille
   contractuelle : corriger les paliers dans l'UI, renseigner `source`,
   passer le statut à `VALIDEE`. Aucun code à toucher.
2. **FIN-S31 cheptel : actif biologique ou stock ?** — `cheptel_mode` vaut
   `NON_VALORISE` par défaut (comportement historique, rien n'entre au
   bilan). Passer à `ACTIF_BIOLOGIQUE` dans HMD Configuration →
   *Personnel & Cheptel*, vérifier `cheptel_cout_elevage` et
   `cheptel_duree_amortissement_ans`, puis lancer `synchroniser_cheptel`.
   Le site de démo est déjà en `ACTIF_BIOLOGIQUE`.
3. **Facturation lait** : la ferme facture (job mensuel actif) OU import du
   décompte centrale — ne jamais activer les deux (RG-FIN-12).
4. **Date de bascule + balances réelles** pour dérouler `BASCULE.md`.
5. **Données réelles** — ⚠️ ce n'est PAS une attente externe. En réunion du
   05/08/2026, l'engagement a été pris **côté développement** : « *ma3neha
   mouch sa3ib, n7otoulkom les données réelles li ntab3ouhom* » (« ce n'est
   pas difficile, on vous met les données réelles que vous suivez »). Aucune
   demande de backup n'a été adressée à qui que ce soit pendant cette
   réunion — la mention « demande à Sami » de la livraison du 19/07 relève
   d'un contexte antérieur. Question ouverte à trancher : **quelle source
   réelle est accessible** (base du site de production, base sur laquelle
   travaille Siwar, ou l'export Excel que le rapport journalier remplace).
   L'outil de validation existe : restaurer, lancer le contrôle de
   cohérence, traiter les ERREUR puis les ALERTE.
6. **Taux de charges patronales** — tranché en réunion 05/08/2026 : 30 %
   par défaut (`taux_charges_patronales_pct`, patch v1_8), surchargeable par
   salarié sur la fiche Personnel. Les **salaires réels** restent à confirmer
   avec la ferme avant de poster une vraie paie.

## Tests

```bash
# 18 modules — 408 tests, tous verts au 06/08/2026
bench --site <site> execute hmd_agro.hmd_agro.tests.test_valorisation_cmp.run       #  7/7
bench --site <site> execute hmd_agro.hmd_agro.tests.test_cost_flow.run              #  9/9
bench --site <site> execute hmd_agro.hmd_agro.tests.test_semence_dual_write.run     # 13/13
bench --site <site> execute hmd_agro.hmd_agro.tests.test_stock_integration.run      #  7/7
bench --site <site> execute hmd_agro.hmd_agro.tests.test_recettes.run               # 16/16
bench --site <site> execute hmd_agro.hmd_agro.tests.test_immobilisations.run        # 13/13
bench --site <site> execute hmd_agro.hmd_agro.tests.test_finance_kpis.run           # 14/14
bench --site <site> execute hmd_agro.hmd_agro.tests.test_roles_finance.run          #  8/8
bench --site <site> execute hmd_agro.hmd_agro.tests.test_personnel.run              # 54/54
bench --site <site> execute hmd_agro.hmd_agro.tests.test_maintenance.run            # 26/26
bench --site <site> execute hmd_agro.hmd_agro.tests.test_grille_lait.run            # 35/35
bench --site <site> execute hmd_agro.hmd_agro.tests.test_cheptel.run                # 25/25
bench --site <site> execute hmd_agro.hmd_agro.tests.test_controle_coherence.run     # 15/15
bench --site <site> execute hmd_agro.hmd_agro.tests.test_decompte_lait.run          # 37/37
bench --site <site> execute hmd_agro.hmd_agro.tests.test_rapport_performance.run    # 17/17
bench --site <site> execute hmd_agro.hmd_agro.tests.test_tableau_amortissement.run  # 19/19
bench --site <site> execute hmd_agro.hmd_agro.tests.test_indicateurs_report.run_all_tests  # 21/21
bench --site <site> execute hmd_agro.hmd_agro.tests.test_full_flow.run_all_tests    # 72/72
```
