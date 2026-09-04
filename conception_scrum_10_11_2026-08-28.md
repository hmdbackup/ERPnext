# Conception technique — SCRUM-10 & SCRUM-11 (dev du 28/08/2026)

> **Révisé le 03/09/2026** — la section 1.1 (table « Répartition par atelier »
> sur PI / JE, ERR-FIN-11..18, répartition analytique) est **remplacée** : la
> clé est une **Cost Center Allocation** ERPNext qui répartit le Grand Livre à
> la validation ; la table, le DocType enfant et les règles 12..18 sont retirés
> (patch `v1_10.retirer_repartition_par_ligne`). Voir
> `reunion_2026-09-03/compte_rendu.md`. Le reste du document (1.2 à 2.3) reste
> valable, avec `charges_lait` lisant désormais le Lait tel quel au Grand Livre.
>
> Révisé le 04/09/2026 : les mouvements de stock (rations, médicaments, paillettes) portent le centre de coûts de l'atelier de l'animal (RG-FIN-40), posé par l'app ; une nouvelle clé arrive pré-remplie.

Source fonctionnelle : `reunion_2026-08-26/compte_rendu.md` + `plan_maquettes_2026-08-26.md`
(maquettes reprises, en attente de validation par M. Samir). Ce document fixe
**comment** on code ce qui a été décidé le 26/08, ni plus ni moins.

Conventions : `.claude/skills/hmd-agro-dev/references/conventions.md` (Python 4 espaces,
vocabulaire métier FR, commentaires/docstrings EN, `get_config()` pour tout seuil,
codes `ERR-<DT>-<nn>` dans les messages `frappe.throw` en français, jamais un
`except: pass`, tests = runners `run()` exécutés par `bench execute`).

---

## 0. Socle partagé (écrit avant le fan-out, à ne PAS retoucher sans raison)

| Élément | Fichier | Contenu |
|---|---|---|
| DocType enfant | `doctype/repartition_atelier_charge/` | `ligne` Int · `libelle` Data RO · `atelier` Link Cost Center · `pourcentage` Percent (défaut 100) · `montant` Currency RO |
| Custom Fields | `fixtures/custom_field.json` | PI + JE : `section_repartition_atelier` (Section Break après `items` / `accounts`) + `repartition_atelier` (Table) ; Asset Repair : `cout_pieces`, `cout_main_oeuvre` (Currency après `repair_cost`), `prestataire` (Link Supplier après `reference_hmd`) |
| Property Setter | `fixtures/property_setter.json` | `Asset Repair-repair_status-options` = `Pending\nCompleted\nCancelled\nPlanned` |
| hooks.py | `CORE_CUSTOM_FIELDS`, `CORE_PROPERTY_SETTERS`, `doc_events`, `doctype_js` | voir fichier |
| HMD Configuration | `repartition_fg_obligatoire` (Check, défaut 0) | mode strict : une ligne Frais Généraux sans répartition bloque la sauvegarde |
| public/ | `public/js/hmd_agro.js`, `public/css/hmd_agro.css` | récupérés du conteneur — ils manquaient au dépôt alors que `app_include_js/css` les référencent |

---

## 1. SCRUM-10 — Répartition des frais généraux par charge (agent A)

### 1.1 Saisie (Purchase Invoice + Journal Entry)

Module **nouveau** `utils/repartition_charges.py` — hook `validate` (déclaré dans hooks.py) :

- `lignes_charges(doc)` → liste des lignes de **charge** du parent :
  - PI : `doc.items` (idx, `item_name`, `expense_account`, `cost_center`, montant = `base_net_amount`)
  - JE : `doc.accounts` (idx, `account`, `cost_center`, montant = `debit - credit` en devise société) — seules les lignes dont le compte est de `root_type = Expense` et dont le montant est > 0 sont des charges.
- `est_frais_generaux(cost_center)` → `_nom_court(cc) == ATELIER_FRAIS_GENERAUX` (réutiliser `finance_kpis._nom_court`, ne pas dupliquer).
- Règles (une ligne = une ligne de charge FG, groupée par `ligne`) :
  - **ERR-FIN-11** `ligne` inexistante ou qui n'est pas une charge imputée à Frais Généraux (on ne répartit que du FG).
  - **ERR-FIN-12** total des parts d'une ligne ≠ 100 % (tolérance `TOLERANCE_PCT` = même constante que Personnel, 0,01) → message « Répartition incomplète — ligne N : X % ».
  - **ERR-FIN-13** atelier = Frais Généraux (répartir sur soi-même).
  - **ERR-FIN-14** même atelier deux fois sur une même ligne.
  - **ERR-FIN-15** atelier inexistant ou groupe (non feuille) ou d'une autre société.
  - **ERR-FIN-16** pourcentage hors ]0 ; 100].
  - **ERR-FIN-17** (mode strict, `get_config("repartition_fg_obligatoire", default=0)`) : une ligne FG sans aucune répartition bloque. Par défaut OFF : une ligne FG sans répartition reste autorisée (les écritures automatiques `enregistrer_intervention` / `post_salaires` imputent à FG sans répartition) et apparaît dans le rapport comme « non répartie ».
- À chaque `validate`, recalculer sur chaque ligne enfant `libelle` (= item_name ou compte de la ligne) et `montant` = montant de la ligne × pct / 100 (dérivés, jamais saisis).
- Pas d'écriture comptable supplémentaire : la répartition est **analytique**, le GL reste imputé à Frais Généraux. (Décision 26/08 : Samir confirme, 5 à 10 factures/mois.)

Client `public/js/purchase_invoice.js` + `public/js/journal_entry.js` (`doctype_js`) :
- Afficher la section `section_repartition_atelier` uniquement si au moins une ligne a un centre de coût Frais Généraux (`frm.toggle_display`), recalculé sur `refresh`, sur changement de `cost_center` d'une ligne, ajout/suppression de ligne.
- Sous la table, texte dynamique via `frm.set_df_property("repartition_atelier","description", …)` : « Ligne N — total réparti X % — il manque Y % » par ligne FG (vert si 100 %).
- Filtrer `atelier` sur les centres feuilles de la société, hors Frais Généraux (`set_query`).
- Pré-remplir `ligne` avec le numéro de la première ligne FG quand on ajoute une ligne enfant.

### 1.2 Lecture (`utils/finance_kpis.py`)

- Nouvelle fonction `repartitions_frais_generaux(date_debut, date_fin)` : lit PI (docstatus 1, `posting_date` dans la période, `is_return` 0) items sur FG et JE (docstatus 1) accounts de charge sur FG, joints à leurs lignes `Repartition Atelier Charge` (`parent`, `ligne` = idx). Retourne
  `{"charges": [ {voucher_type, voucher, ligne, libelle, compte (numéro), poste, montant, repartition: [{atelier (nom court), pct, montant}]} ],
    "par_atelier": {atelier: montant}, "par_atelier_postes": {atelier: {poste: montant}},
    "total_reparti": x, "total_fg": y (= gl_sums_par_atelier FG), "non_reparti": y - x}`.
  Le poste d'une charge = même mapping `POSTES_CHARGES` que le reste du module (fonction utilitaire commune, ne pas dupliquer la table).
- `charges_lait(...)` : périmètre `LAIT_QUOTE_PART` → `quote_part = par_atelier["Lait"]`, postes += `par_atelier_postes["Lait"]`. **Supprimer `cle_pct`** (clé de répartition calculée = décision retirée le 26/08). Ajouter `fg_total`, `fg_reparti`, `fg_non_reparti` au dictionnaire retourné.

### 1.3 Rapport Performance (`report/rapport_performance/`)

- **Nouvelle section « Frais Généraux — répartition par atelier »**, entre « Charges par atelier » et « Coût du lait — détail » : une ligne par charge FG (indicateur = `libellé — compte`, valeur = montant) suivie d'une ligne `└ Lait 45 % · Cultures 35 % · Brebis 20 %` (valeur vide → tiret), puis `Total Frais Généraux (Grand Livre)`, `Contrôle — somme des répartitions = Total FG` (indicateur Red si écart > 0,01 et mode strict, Orange sinon), `dont part atelier Lait — somme des répartitions`, et si `non_reparti > 0` : `Frais généraux non répartis — hors coût du litre` (Orange).
- `_cout_lait_detail` : libellé de la quote-part = « Quote-part Frais Généraux — somme des répartitions saisies ».
- **Colonnes comparatives** (maquette validée 24/08 + 26/08) : `valeur`, `precedent` (label selon période : Jour → « Veille », Semaine → « S-1 », Quinzaine → « Q-1 », Mois → « M-1 », Année → « A-1 (même période) »), `ecart_pct` (Percent, « Écart % » = (valeur − précédent) / |précédent| × 100, vide si précédent nul/absent), `unite`. Implémentation : factoriser `execute` en `_construire_lignes(debut, fin, filters)` appelée deux fois, fusion par clé `(section, indicateur)` dans l'ordre de la période courante ; lignes INFO/Avertissement sans comparatif. `neutraliser_indicateurs_lait` doit neutraliser aussi `precedent`.
- **Période « Année »** = du 1er janvier à la date choisie (YTD) : `period_bounds` + `previous_period_bounds(periode, debut, fin)` (Jour → veille ; Semaine/Quinzaine/Mois → période précédente de même granularité ; Année → même intervalle un an plus tôt) + option `Année` dans `rapport_performance.js` **et** `rapport_interventions.js` (l'agent B ne touche pas `period_bounds`).
- Formatter JS : `valeur`/`precedent` `null` → « – » ; `ecart_pct` affiché signé (« +12,5 % »).

### 1.4 Tests (agent A)

- `tests/test_repartition_charges.py` (nouveau, préfixe `ZZTEST_RFG`, mois vierge d'un exercice ACTIF — vérifier qu'aucune donnée réelle n'y tombe) : 100 % OK · 80 % → ERR-FIN-12 · ligne non FG → ERR-FIN-11 · atelier FG → ERR-FIN-13 · doublon → ERR-FIN-14 · groupe → ERR-FIN-15 · montant/libellé dérivés · `repartitions_frais_generaux` (montants par atelier et par poste, document annulé exclu) · `charges_lait` quote-part = Σ Lait · mode strict ON bloque une ligne FG nue, OFF la laisse passer (remettre la config à sa valeur initiale en `finally`).
- `tests/test_ventilation_atelier.py` : cas 6 réécrit (sans répartition → quote-part 0 et FG non réparti visible ; avec répartition → quote-part exacte), plus aucune référence à `cle_pct`.
- `tests/test_rapport_performance.py` : `period_bounds` Année, `previous_period_bounds`, colonnes comparatives présentes, Δ % sur un couple connu, section FG présente.

---

## 2. SCRUM-11 — Parc et interventions (agent B)

### 2.1 Fiche d'intervention (Asset Repair)

- Hooks (`maintenance_utils.py`) :
  - `before_validate` → `completer_couts_fiche(doc, method)` : si `cout_pieces` ou `cout_main_oeuvre` renseigné **et** pas de `purchase_invoice` (ERPNext calcule alors `repair_cost` depuis la facture) → `repair_cost = cout_pieces + cout_main_oeuvre` ; ERPNext recalcule `total_repair_cost` ensuite dans son propre `validate`.
  - `validate` → `valider_fiche_intervention(doc, method)` : **ERR-MNT-09** intervenant salarié ET prestataire renseignés (un seul des deux) ; **ERR-MNT-10** coût négatif ; **ERR-MNT-11** statut `Planned` avec `failure_date` passée (une intervention planifiée est dans le futur) ; **ERR-MNT-12** statut `Planned` avec `completion_date` ou coût renseigné.
  - `before_submit` → `verifier_fiche_avant_validation(doc, method)` : **ERR-MNT-13** une fiche `Planned` ne se valide pas — passer le statut à Terminée d'abord (ERPNext ne bloque que `Pending`).
- États dérivés (`etat_fiche(repair)` → `A_VENIR` / `EN_ATTENTE` / `TERMINEE` / `ANNULEE`) : `Planned` → À venir ; `Pending` → En attente (= panne déclarée, ERPNext met l'équipement « Out of Order ») ; `Completed` → Terminée ; `Cancelled` ou docstatus 2 → Annulée. Pourquoi `Planned` et non `Pending` + date future : ERPNext `update_status` passe l'équipement en panne pour **toute** fiche `Pending` (`asset_repair.py::update_status`).
- `@frappe.whitelist() planifier_intervention(source, date_prevue, description=None)` : crée un brouillon `Planned` copiant `asset`, `type_intervention` (défaut PREVENTIVE), `cost_center`, `personnel`/`prestataire`, `description` (défaut « Prochaine : {description source} »), `failure_date = date_prevue 08:00` ; date ≤ aujourd'hui → ERR-MNT-11 ; retourne le nom. Dupliquer/Supprimer = natif (rien à coder).
- Client `public/js/asset_repair.js` : indicateur d'état dans l'en-tête (`frm.page.set_indicator`) ; bouton « Planifier la prochaine » (fiche validée & Terminée) → dialog date + libellé → appel `planifier_intervention` → `frappe.set_route` vers la nouvelle fiche ; `set_query` prestataire (fournisseurs non désactivés) ; `prestataire`/`personnel` : vider l'autre quand l'un est saisi ; recalcul affiché de `repair_cost` quand pièces/M.O. changent (miroir du hook serveur, pas de logique métier différente).
- Workspace HMD AGRO : raccourci « Interventions (fiches) » → DocType Asset Repair (leçon 05/08 : un écran inatteignable depuis le menu ne compte pas).

### 2.2 Rapport Interventions (`report/rapport_interventions/`)

- Colonnes : ajouter `pieces` (Currency « Pièces (DT) »), `main_oeuvre` (Currency « M.O. (DT) ») avant `cout` (= `total_repair_cost`), `heures` (Float « Heures ») ; `intervenant` devient **Data** : prestataire → `supplier_name` ; salarié → « Interne — {nom_complet} » ; aucun → « Interne ».
- `interventions_realisees` : sélectionner aussi `cout_pieces`, `cout_main_oeuvre`, `prestataire`.
- **Nouvelle section « Parc — état du matériel »** en tête (respecte les filtres équipement/atelier) : une ligne par équipement (Asset docstatus 1, hors animaux `id_animal`, hors Sold/Scrapped) : `equipement`, `designation`, `type_` = état (`PRÊT` / `EN ATTENTE DE MAINTENANCE` / `EN PANNE`), `libelle` = « Dernière : jj/mm — description » (dernière fiche Terminée validée), `date` = prochaine échéance (fiche `Planned` la plus proche ou Asset Maintenance Log Planned/Overdue, suffixe « EN RETARD » dans le libellé si dépassée), `heures` = Σ heures Utilisation Equipement sur la période (réutiliser `cout_utilisation`), `atelier`. Ligne de synthèse : « N équipements · a prêts · b en attente · c en panne · d échéances dépassées ».
  - `EN PANNE` = fiche `Pending` ouverte (docstatus 0) sur l'équipement — c'est la fiche qui fait foi, pas un bouton.
  - `EN ATTENTE DE MAINTENANCE` = pas de panne, mais une échéance (fiche `Planned` ou log) ≤ aujourd'hui + `get_config("maintenance_horizon_jours", default=30)` — même horizon que le bloc Préventif.
  - `PRÊT` sinon.
- Bloc « Préventif » : ajouter les fiches `Planned` comme lignes `À VENIR` (`EN RETARD` si date dépassée) à côté des logs existants ; `interventions_planifiees` s'enrichit plutôt que d'ajouter une deuxième requête dans le rapport.
- Rapprochement : inchangé.
- Option `Année` dans `rapport_interventions.js` (Python : `period_bounds` fourni par l'agent A ; le rapport importe déjà la fonction).

### 2.3 Tests (agent B)

- `tests/test_rapport_interventions.py` : colonnes 14 typées ; pièces/M.O. remontent et `cout` = somme ; intervenant salarié/prestataire/aucun ; parc : équipement PRÊT, EN PANNE (fiche Pending brouillon), EN ATTENTE (fiche Planned dans l'horizon) ; fiche Planned en `À VENIR` dans Préventif et **absente** des réalisées ; ligne de synthèse.
- `tests/test_maintenance.py` (ajouts) : `planifier_intervention` crée un brouillon Planned copiant l'équipement/type ; date passée → ERR-MNT-11 ; salarié + prestataire → ERR-MNT-09 ; `repair_cost` = pièces + M.O. ; fiche Planned : submit → ERR-MNT-13 ; l'équipement ne passe PAS « Out of Order » pour une fiche Planned.

---

## 3. Hors périmètre aujourd'hui (à dire dans le CR / Jira)

- Lien facture d'achat ↔ fiche : ERPNext porte déjà `Asset Repair.purchase_invoice` (sens fiche → facture, `repair_cost` tiré de la facture). Le champ « Intervention » sur la ligne de facture dépend de la décision « qui écrit au 615 » (non tranchée le 26/08).
- Centres de coût Brebis / Fromagerie : configuration (plan analytique), pas du code.
- Mode strict de répartition : livré désactivé, à activer par l'administrateur quand Samir l'aura confirmé.

## 4. Environnement de test

Docker local `~/Desktop/hmd_agro_local_deploy/frappe_docker` (conteneur `frappe_docker-backend-1`, site `hmd.agro`, copie de données réelles). L'app dans le conteneur n'est pas un dépôt git : synchronisation par
`docker cp ~/Desktop/hmd_agro-main/hmd_agro/. frappe_docker-backend-1:/home/frappe/frappe-bench/apps/hmd_agro/hmd_agro/`
(la cible est le **paquet** `apps/hmd_agro/hmd_agro/`, pas la racine de l'app) puis
`docker exec -u root frappe_docker-backend-1 chown -R frappe:frappe /home/frappe/frappe-bench/apps/hmd_agro`,
puis `bench --site hmd.agro migrate` (DocType + fixtures), `bench build --app hmd_agro` (JS), tests :
`bench --site hmd.agro execute hmd_agro.hmd_agro.tests.<module>.run`.
Un seul processus à la fois sur le conteneur (base partagée).
