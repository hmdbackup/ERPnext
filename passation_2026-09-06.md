# Passation — module Finance HMD AGRO

**De :** Mohamed Slim (stagiaire, Université Laval, 26/05 → 28/08/2026 ; derniers
commits le 04/09/2026)
**À :** Aymen Zarrad (superviseur / lead), Aziz (serveur de production), et la
personne qui reprendra le module finance.
**Date :** 06/09/2026.
**Dépôt :** `https://github.com/hmdbackup/ERPnext` — branche `finance/socle-comptable`.
**Jira :** `https://hmdagrobackup.atlassian.net` — projet SCRUM.

Ce document est le point d'entrée. Il dit où est le travail, dans quel état,
ce qui manque, et par où reprendre. Les détails vivent dans les documents
qu'il cite ; il ne les recopie pas.

---

## 1. En une page

- **Tout le module finance (Epics A → G + les corrections de la réunion du
  05/08 + SCRUM-10 / SCRUM-11) est sur la branche `finance/socle-comptable`,
  poussée sur GitHub le 06/09/2026.** Rien n'est perdu sur mon Mac.
- **Rien de tout cela n'est en production.** `main` date du 30/06/2026 côté
  code applicatif (les 4 commits suivants sur `main` ne touchent que le
  README). La production tourne donc sur un code de deux mois en retard.
  La fusion vers `main` **n'a jamais été autorisée** (elle suppose la
  validation fonctionnelle de M. Samir) : c'est la première décision à
  prendre. La fusion est propre — seul `README.md` diffère, aucun conflit.
- **Dernier chantier livré (04/09) : la clé de répartition des frais
  généraux** portée par une « Cost Center Allocation » ERPNext, et le centre
  de coûts des mouvements de stock posé par l'app (RG-FIN-40). Il reste à
  **faire valider les pourcentages de la clé par M. Samir** et à **rejouer la
  démo de 10 minutes avec Aymen** (`reunion_2026-09-03/scenario_verification_cle.md`).
- **Deux tickets restent « En cours » à mon nom dans Jira** : SCRUM-10 et
  SCRUM-11. Le code est livré ; ce qui manque est la validation métier et la
  mise en production. Un commentaire de passation a été posé sur chacun.
- **Mon environnement local disparaît avec moi.** La stack Docker avec la copie
  des données réelles (site `hmd.agro`, ≈220 animaux, ≈1 200 écritures) est
  sur mon Mac. Le successeur la reconstruit avec `deploy/DEPLOY.md` partie A
  et une sauvegarde fournie par Aziz (§6).

---

## 2. Qui fait quoi

| Personne | Rôle dans le projet | Ce qu'il/elle attend de la passation |
|---|---|---|
| **M. Samir** | Client / décideur métier (ferme Borj Essebai, Mateur) | Valider les pourcentages de la clé FG ; trancher les décisions FIN-D01 → D06 |
| **Aymen Zarrad** | Superviseur de stage, lead technique | Reprendre la revue de SCRUM-10, décider de la fusion vers `main` |
| **Aziz** (Mohamed Aziz Zarrad) | Serveur de production, sauvegardes, infra (SCRUM-3, 5 → 8) | Fournir une sauvegarde au successeur ; exécuter `runbook_alignement_versions.md` après la fusion |
| **Iheb** (mohamediheb gouia) | Développeur, Farm Management (SCRUM-78, 79, 87) et assets | Aucun blocage croisé connu ; voir `review_maquettes_fm_iheb.md` et `point_assets_aziz.md` |
| **Siwar, Soumaya** | Utilisatrices sur la ferme | Après déploiement : vérifier « Aide › À propos » = HMD Agro 0.2.0 (runbook §2) |

Le rituel : statut WhatsApp de 3 phrases posté **avant** le daily de 10 h
(modèle dans `.claude/skills/daily-standup/`, archives dans `.claude/daily/`).

---

## 3. Le code : où, quel état

### 3.1 Branches

| Branche | Rôle | État au 06/09/2026 |
|---|---|---|
| `finance/socle-comptable` | **Tout le travail finance** (51 commits depuis `main`) | À jour sur `origin`, HEAD = `b645b5f` + le commit de passation |
| `main` | Ce que l'image Docker de production construit (`deploy/apps.json`) | Code applicatif du 30/06/2026 ; 4 commits README d'Aziz depuis |
| `finance/socle-comptable-zip` | Ancien instantané local (`aef84cf`) | Obsolète, à supprimer |
| `develop`, `sprint2 → sprint6`, `feature/FM-farm-management` | Branches des autres développeurs | Pas de mon ressort |

**Règle observée pendant tout le stage** : commits et pushs uniquement sur
`finance/socle-comptable`. **Jamais de fusion ni de push sur `main` sans accord
explicite, renouvelé à chaque fois** (le 06/08 une fusion non demandée a dû
être annulée par force-push de `main` sur `2d9efc8`).

### 3.2 Fusionner vers `main` (quand l'équipe l'aura décidé)

```bash
git fetch origin
git checkout main && git pull origin main
git merge --no-ff finance/socle-comptable -m "Merge finance/socle-comptable (Epics A-G, réunions 05/08 et 26/08, SCRUM-10/11)"
git push origin main
```

Aperçu fait le 06/09 : `git merge-tree` ne trouve **aucun conflit** (seul
`README.md` a changé côté `main`). Ensuite : `runbook_alignement_versions.md`
étapes 1 à 3 (Aziz reconstruit l'image **sans cache**, migre, vérifie
`bench version` = erpnext 15.95.2 + hmd_agro 0.2.0).

### 3.3 Migrations à l'arrivée du code en production

`bench --site hmd.agro migrate` joue les patches `v1_6 → v1_10` listés dans
`hmd_agro/patches.txt`. Deux d'entre eux changent des données réelles et
doivent être connus d'Aziz :

- `v1_8.set_langue_francaise` : passe le site et les comptes en français,
  symbole TND → « DT ».
- `v1_8.appliquer_taux_charges_30` : charges patronales 30 % à partir du
  01/08/2026, recalcule le coût employeur des fiches Personnel.
- `v1_10.retirer_repartition_par_ligne` : supprime la table « Répartition par
  atelier » (remplacée par la Cost Center Allocation) — idempotent.

**Sauvegarde complète avant `migrate`** (runbook §1.2).

---

## 4. Ce qui est livré

Référence complète, commit par commit et story par story :
**`livraison_finance.md`**. Résumé :

| Lot | Contenu | Jira |
|---|---|---|
| Epic A — Socle | Plan comptable SCE (77 comptes), TVA, 5 centres de coûts ateliers, dimensions Lot / Bâtiment | SCRUM-102, S01–S02 ✅ |
| Epic B — Valorisation | Consommations au CMP réel, coût/litre au rapport | SCRUM-103, S10–S12 ✅ |
| Epic C — Recettes | Facture lait de période, vente d'animal, fumier, grille qualité, décompte mensuel figé, multi-acheteurs | SCRUM-104 ✅ (S103 prorata intra-mois à faire) |
| Epic D — Immobilisations | Assets, amortissement linéaire, maintenance / interventions, cheptel à l'actif | SCRUM-105 **en cours** (S31 = décision client) |
| Epic E — Charges & MO | Charges par atelier, registre Personnel, masse salariale, primes, heures d'utilisation équipement | SCRUM-106 ✅ (S105 étalement à faire) |
| Epic F — Pilotage | KPI économiques, seuils HMD Configuration, Rapport Périodique + Rapport Performance | SCRUM-107 ✅ |
| Epic G — Bascule & droits | Rôle « Éleveur HMD », procédure à-nouveaux `BASCULE.md` | SCRUM-108 **en cours** (S60 attend les balances réelles) |
| Réunion 05/08 | 20 corrections de M. Samir (S80 → S101) | ✅ sauf S92 (fusion `main`) |
| SCRUM-10 | Répartition des frais généraux par **Cost Center Allocation**, section FG du Rapport Performance, période Année, colonnes M-1 / écart %, centre de coûts des stocks posé par l'app | **En cours** — code livré, validation métier à faire |
| SCRUM-11 | Fiche d'intervention (pièces / MO / prestataire / planifiée), actions dupliquer-planifier-supprimer, Rapport Interventions avec état du parc | **En cours** — code livré 29/08, revue faite |
| SCRUM-9 | Production laitière par vache | **Annulée** par M. Samir le 26/08, fermée |

Suite de tests : 46 modules dans `hmd_agro/hmd_agro/tests/`. Dernière
exécution complète le 04/09 sur le site local (voir §7).

---

## 5. Ce qui n'est pas terminé

### 5.1 À faire tout de suite (avant toute démo ou mise en production)

1. **Valider les pourcentages de la clé FG avec M. Samir.** L'app propose
   60 Lait · 25 Cultures-Fourrage · 15 Élevage-Génisses (chiffres de la démo).
   La date et les lignes sont pré-remplies, seuls les % sont sa décision.
2. **Rejouer la démo avec Aymen** : `reunion_2026-09-03/scenario_verification_cle.md`
   (10 min, jeu de démo `demo_finance/seed_demo_scrum_10_11.py`).
3. **Décider la fusion vers `main`** puis dérouler le runbook (§3.2).
4. **Vague 1 « fiabilisation »** du backlog (`jira/README.md`) : FIN-S99
   (jeu de données réaliste), FIN-S92 (= la fusion), FIN-S102 (raccourci
   « Utilisation Équipement » dans le menu, 1 h), FIN-S104 (contrôle de
   cohérence sur la base réelle), FIN-D01, FIN-D02.

### 5.2 Backlog restant (`jira/backlog_finance.csv`, 20 issues)

| Vague | Issues | Charge |
|---|---|---|
| 1 — fiabilisation | S99, S92, S102, S104, D01, D02 | ≈ 2 j |
| 2 — atelier génisses | S110 → S116, D04 (spec : `spec_cout_genisse_facturation_interne.md`) | ≈ 10,5 j |
| 3 — consolidation | S31, S60, S103, S105, D03, D05, D06 | ≈ 5 j |

Le backlog Jira **n'est pas synchronisé** avec ce CSV : Jira ne contient que
les 22 stories d'origine (SCRUM-109 → 130) et les 7 epics (SCRUM-102 → 108).
Les 17 issues nées du grooming du 07/08 (S94 → S116, D01 → D06, epics I et J)
sont **uniquement dans `jira/backlog_finance_delta.csv`**, prêt à importer
(procédure dans `jira/README.md`). Quatre statuts Jira sont faux et listés
dans ce README (S60, S91, S92, S93).

### 5.3 Décisions qui attendent M. Samir

| Décision | Ce qu'elle débloque | Où c'est expliqué |
|---|---|---|
| FIN-D01 grille tarifaire réelle de la centrale | La facture lait exacte (grille « provisoire » aujourd'hui) | `livraison_finance.md` § Décisions |
| FIN-D02 salaires réels | Une vraie paie et un vrai coût MO | idem |
| FIN-D03 qui facture le lait (ferme ou import du décompte) | Ne jamais activer les deux (RG-FIN-12) | idem |
| FIN-S31 cheptel à l'actif ou non | Amortissement du cheptel | idem + `BASCULE.md` |
| FIN-S60 date de bascule + balances | Les à-nouveaux | `hmd_agro/hmd_agro/setup/finance/BASCULE.md` |
| FIN-D04 paramètres de l'atelier génisses | Vague 2 | `spec_cout_genisse_facturation_interne.md` §7 |
| Pourcentages de la clé FG | SCRUM-10 définitif | `reunion_2026-09-03/compte_rendu.md` §4 |

### 5.4 Dettes et pièges connus

- **Deux tests échouent déjà sur HEAD, avant mes derniers commits** :
  `test_feed_distribution` 11/12 et `test_aliment_correction` 33/34. Ils ne
  viennent pas du module finance ; à regarder par qui reprend l'alimentation.
- **`livraison_finance.md` § Tests** : les compteurs (« 18 modules / 408 »)
  sont périmés, le fichier le dit lui-même. Ne pas les recopier ; relancer la
  suite.
- **`hmd_agro/public/`** (`hmd_agro.js`, `hmd_agro.css`) manquait au dépôt
  jusqu'au 29/08 alors que `hooks.py` les référence. Il y est maintenant.
- **Frais généraux antérieurs à la clé** : non repris, affichés en orange
  « non répartis » dans le Rapport Performance. Décision du 04/09, pas un bug.
- **Mouvements de stock saisis à la main** dans ERPNext sans centre de coûts :
  ils tombent sur Frais Généraux et seront répartis par la clé. À dire au
  comptable.
- `demo.hmd.agro` (site de démo sur ma stack locale) a des identifiants de
  base cassés ; le seul site utile en local était `hmd.agro`.

---

## 6. Environnements

| Environnement | Où | Qui | Comment y accéder |
|---|---|---|---|
| **Production** | Serveur de la ferme, `frappe_docker` | Aziz | Accès géré par Aziz. Procédure : `deploy/DEPLOY.md` partie B + `runbook_alignement_versions.md` |
| **Local (à reconstruire)** | Mac de Mohamed — disparaît | — | `deploy/DEPLOY.md` partie A (dev container VS Code) **ou** `frappe_docker` classique. Restaurer une sauvegarde d'Aziz : `bench --site hmd.agro restore <fichier.sql.gz>` |
| **Copies de données** | Exports Google Drive (SCRUM-133, 135), sauvegardes SFTP (README) | Aziz | Demander à Aziz |

Commandes que j'utilisais tous les jours (stack Docker `frappe_docker`, le
dossier de l'app **n'est pas monté**, il est copié) :

```bash
# pousser le code dans les conteneurs (backend ET frontend : nginx a sa copie de public/)
docker cp hmd_agro/. frappe_docker-backend-1:/home/frappe/frappe-bench/apps/hmd_agro/hmd_agro/
docker cp hmd_agro/public/. frappe_docker-frontend-1:/home/frappe/frappe-bench/apps/hmd_agro/hmd_agro/public/
docker exec -u root frappe_docker-backend-1 chown -R frappe:frappe /home/frappe/frappe-bench/apps/hmd_agro
docker exec frappe_docker-backend-1 bash -lc "cd /home/frappe/frappe-bench && bench --site hmd.agro migrate"
docker exec frappe_docker-backend-1 bash -lc "cd /home/frappe/frappe-bench && bench build --app hmd_agro"
```

Piège : le navigateur cache `hmd_agro.js` (pas de `?ver`). Symptôme
« `ReferenceError: hmd_… is not defined` », formulaire blanc → `Ctrl+Shift+R`.

---

## 7. Lancer les tests

```bash
# un module
docker exec frappe_docker-backend-1 bash -lc \
  "cd /home/frappe/frappe-bench && bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_repartition_charges.run"
```

Les runners s'appellent tous `run()` et s'exécutent par `bench execute`
(convention du projet, pas `bench run-tests`). Liste dans
`hmd_agro/hmd_agro/tests/`. Modules finance à relancer avant toute livraison :
`test_repartition_charges`, `test_atelier_stock`, `test_ventilation_atelier`,
`test_rapport_performance`, `test_finance_kpis`, `test_cost_flow`,
`test_maintenance`, `test_rapport_interventions`, `test_personnel`,
`test_immobilisations`, `test_controle_coherence`, `test_tableau_amortissement`,
`test_decompte_lait`, `test_grille_lait`, `test_recettes`, `test_roles_finance`,
`test_full_flow` (E2E).

Pièges : **sauvegarder avant** (`bench --site hmd.agro backup`) ; les fixtures
doivent tomber dans un exercice comptable **actif** (sinon `FiscalYearError`) et
dans un mois **vierge de données réelles** (l'activité réelle est concentrée
sur juin-août 2026) ; une Cost Center Allocation de test se crée avec
`_skip_from_date_validation` et se supprime dans un `finally`, sinon elle
ventile les vraies écritures.

---

## 8. Carte des documents

Tout est à la racine du dépôt sauf mention.

| Pour… | Lire |
|---|---|
| Comprendre l'app et ses conventions | `.claude/skills/hmd-agro-dev/SKILL.md` (+ `references/conventions.md`), `hmd_agro_codebase_guide.html` |
| Les règles métier (RG-*, cycle de vie, cascades) | `.claude/skills/hmd-agro-domain/SKILL.md` |
| Les KPI, rapports, seuils | `.claude/skills/hmd-agro-kpi/SKILL.md` |
| Le passage obligé d'une User Story (DoR / DoD, réunion du 07/08) | `.claude/skills/user-story-workflow/SKILL.md`, `dod_scrum_9_10_11.md` |
| Ce qui est livré, commit par commit | `livraison_finance.md` |
| Le backlog et comment le tenir | `jira/README.md`, `jira/backlog.py` (source unique → régénère les CSV) |
| La spec fonctionnelle finance d'origine | `spec_finance.html`, `userstories_finance.html`, `plan_finance.html` |
| La spec de l'atelier génisses (vague 2) | `spec_cout_genisse_facturation_interne.md` |
| Les réunions client | `reunion_2026-08-05/`, `reunion_2026-08-26/`, `reunion_2026-09-03/` (compte rendu + transcription) |
| Les maquettes validées | `maquettes_2026-08-26.{excalidraw,html,pdf}`, `plan_maquettes_2026-08-26.md` ; les annotations de M. Samir sont dans les **salons Excalidraw partagés** (liens dans le groupe WhatsApp), pas dans le dépôt |
| La conception de SCRUM-10 / 11 | `conception_scrum_10_11_2026-08-28.md` (révisée 03/09 et 04/09) |
| Déployer / aligner les versions | `deploy/DEPLOY.md`, `runbook_alignement_versions.md`, `deploy/apps.json` |
| La bascule comptable | `hmd_agro/hmd_agro/setup/finance/BASCULE.md` |
| Présenter au client | `presentation_finance.html` (15 slides, `N` = notes), `demo_finance/` (sources du deck et de la vidéo), `demo_finance/DEMO_scrum_10_11_2026-08-29.md` |
| Les points faits avec les collègues | `point_assets_aziz.md`, `recap_assets_maintenance.md`, `review_maquettes_fm_iheb.md`, `questions_superviseur.md` |

---

## 9. Fichiers hors dépôt et ce que j'en ai fait

Le 06/09, j'ai **versionné** ce qui est du travail durable et textuel :

- `jira/` (backlog source + CSV d'import), référencé par `livraison_finance.md`
  mais absent de git jusque-là ;
- `demo_finance/` sources (seed de démo, générateur du deck, narration) ;
- `.claude/skills/hmd-agro-dev`, `hmd-agro-domain`, `hmd-agro-kpi`,
  `daily-standup` (le savoir du projet sous forme de skills) ;
- `.claude/daily/2026-08-25 → 27` ;
- les deux documents modifiés (`livraison_finance.md`, `spec_cout_genisse…`) ;
- ce document.

**Non versionné, volontairement** (binaire, volumineux ou personnel) — à
récupérer sur mon Mac ou sur Drive **avant mon départ** si l'équipe les veut :

| Fichier(s) | Quoi | Recommandation |
|---|---|---|
| `*.pdf`, `*.png`, `*.excalidraw`, `*.bmpr` | Maquettes, planches d'arbitrage, aperçus | Drive « HMD AGRO / maquettes » — les PDF ont déjà été envoyés dans le groupe |
| `~/Downloads/demo_finance_hmd*.mp4` | Vidéos de démo (10 min) | Drive ; se régénèrent avec `demo_finance/build_video.sh` |
| `outils_affiche/`, `conducteur_affiche_*`, `~/Downloads/Affiche_stage_*` | Mon affiche et mes textes de soutenance | Personnel, hors projet |
| `outils_maquette*.py`, `outils_planches*.py`, `outils_presentation*.py` | Générateurs Python des maquettes / planches | Jetables ; les résultats sont dans les `.excalidraw` |
| `reunion_2026-08-05/transcription.*`, `reunion_2026-08-26/transcription.md` | Transcriptions brutes | Contiennent la voix de M. Samir : ne pas versionner, garder sur Drive privé |
| `message_*.txt`, `reponse_aumen_ecrans_couts.txt`, `dossier_lundi.html` | Messages déjà envoyés | Jetables |
| `.claude/skills/_eval-workspace/`, `_packaged/` | Résidus d'outillage | Jetables |

---

## 10. Accès à transférer ou révoquer

| Accès | Compte | Action |
|---|---|---|
| GitHub `hmdbackup/ERPnext` | `MOSLI6@ulaval.ca` (auteur des commits) | Retirer mes droits d'écriture après la fusion, ou les garder jusqu'à ce que le successeur soit opérationnel |
| Jira `hmdagrobackup.atlassian.net` | idem | Réassigner SCRUM-10, SCRUM-11, SCRUM-105, SCRUM-108, SCRUM-121, SCRUM-128 ; puis désactiver |
| Site ERPNext de production | mon compte utilisateur | Aziz désactive |
| Groupe WhatsApp | mon numéro | Me retirer après le message de passation (annexe A) |
| Salons Excalidraw des maquettes | liens dans le groupe | Rien à faire, les liens restent valides ; exporter en `.excalidraw` si on veut les figer |
| Google Drive exports | dossier d'Aziz | Rien à faire de mon côté |

Je n'ai **aucun secret** dans le dépôt : `deploy/.env` est ignoré par git,
`.env.hmd` n'est qu'un modèle.

---

## 11. Liste de passation (à cocher)

**Fait le 06/09/2026 (Mohamed)**
- [x] Tout le travail commité et poussé sur `origin/finance/socle-comptable`.
- [x] Ce document écrit et versionné.
- [x] Commentaire de passation posé sur SCRUM-10 et SCRUM-11.
- [x] Aperçu de fusion `main` : aucun conflit.

**À faire par Aymen**
- [ ] Rejouer la démo clé FG (`scenario_verification_cle.md`), 10 min.
- [ ] Décider la fusion `finance/socle-comptable` → `main`.
- [ ] Réassigner les tickets Jira (§10).
- [ ] Importer `jira/backlog_finance_delta.csv` et corriger les 4 statuts (§5.2).

**À faire par Aziz**
- [ ] Fournir une sauvegarde `hmd.agro` (`.sql.gz` + fichiers) au successeur.
- [ ] Après fusion : runbook étapes 1.1 → 1.8, poster « avant / après » dans le groupe.

**À faire par le successeur**
- [ ] Reconstruire un bench local (`deploy/DEPLOY.md` A) et restaurer la sauvegarde.
- [ ] Relancer la suite finance (§7) et corriger les compteurs de `livraison_finance.md`.
- [ ] Reprendre la vague 1 (§5.1 point 4).

**À faire par M. Samir** (via Aymen)
- [ ] Pourcentages de la clé FG.
- [ ] FIN-D01, D02, D03, S31, S60 (§5.3).

---

## Annexe A — message de passation pour le groupe WhatsApp

> Bonjour à tous — mon stage se termine, voici la passation du module finance.
>
> Tout le code est sur la branche `finance/socle-comptable`, poussée aujourd'hui
> (Epics A → G, corrections du 05/08, SCRUM-10 et SCRUM-11, clé de répartition
> des frais généraux du 04/09). Rien n'est encore fusionné sur `main` ni déployé :
> c'est la première décision à prendre, la fusion se fait sans conflit.
>
> Le document `passation_2026-09-06.md` à la racine du dépôt dit où est chaque
> chose, ce qui reste à faire (validation des pourcentages de la clé par M. Samir,
> démo de 10 min avec Aymen, vague 1 du backlog) et qui fait quoi. Les tickets
> SCRUM-10 et SCRUM-11 portent un commentaire de passation.
>
> Aziz : le successeur aura besoin d'une sauvegarde de `hmd.agro` pour
> reconstruire un bench local, ma copie disparaît avec mon Mac.
>
> Je reste joignable jusqu'au <date à confirmer> pour les questions. Merci à
> tous pour ces trois mois.

## Annexe B — trame de mail à Aymen

Objet : Passation module finance HMD AGRO — 06/09/2026

Aymen,

Mon stage étant terminé, je te transmets l'état du module finance. Le point
d'entrée est `passation_2026-09-06.md` sur la branche `finance/socle-comptable`
(poussée ce jour). En résumé :

1. Le code de SCRUM-10 et SCRUM-11 est livré et testé sur la copie des données
   réelles ; il reste la validation des pourcentages de la clé par M. Samir et
   la démo de 10 minutes que tu avais demandée le 03/09 (scénario dans
   `reunion_2026-09-03/`).
2. Rien n'est sur `main`. La fusion est propre (aucun conflit) ; je ne l'ai pas
   faite, conformément à la règle convenue le 06/08. Le runbook d'alignement
   des versions est prêt pour Aziz.
3. Le backlog restant est de 20 issues (≈ 17,5 j), dont 6 décisions client. Le
   delta Jira du grooming du 07/08 n'a jamais été importé : le CSV est dans
   `jira/`.
4. Les tickets SCRUM-10, 11, 105, 108, 121, 128 sont encore à mon nom.

Je reste disponible jusqu'au <date à confirmer> pour un appel de passation d'une
heure si tu le souhaites.

Mohamed
