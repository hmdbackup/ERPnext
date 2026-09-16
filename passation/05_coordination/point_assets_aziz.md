# Point Assets avec Aziz — fait / reste à faire

*20/08/2026 · branche `finance/socle-comptable` · Aziz porte US-AM-3, US-AM-6, US-AM-7 dans Jira.*
*Détail technique complet : `passation/05_coordination/recap_assets_maintenance.md` (toujours à jour, aucun commit assets depuis le 14/08).*

---

## 1. Le message en 30 secondes

Le volet Assets a été construit **depuis la finance, pas depuis le « chef de parc »** :
les équipements sont des `Asset` ERPNext natifs (aucun DocType « Équipement » maison),
chaque intervention est un `Asset Repair` **plus** son écriture au 615, les heures
d'utilisation valorisent le coût mécanique par atelier, et trois rapports lisent le tout.
Résultat : **la couche données et la couche comptable existent** ; ce qui manque pour les
US-AM, c'est surtout la couche « exploitation » — fiche actif enrichie, statut/condition,
affectation, alertes poussées, dashboard.

Règle à faire respecter par tout le monde : **une intervention passe par
`enregistrer_intervention()`**, jamais un `Asset Repair` créé à la main (pas d'écriture
→ le 615 et le coût du litre divergent, le Rapprochement du Rapport Interventions crie).

---

## 2. Ce qui est livré (sur `finance/socle-comptable`, pas encore sur `main`)

| Brique | Story | Où |
|---|---|---|
| 5 Asset Categories (durées + comptes 22x/28x/681), amortissement linéaire auto | FIN-S30 | `setup/finance/immobilisations.py` |
| Custom Fields `Asset` : `id_batiment`, `id_animal`, `cout_horaire` | FIN-S30/S91 | idem, exportés par nom dans `hooks.py` |
| Équipe « Maintenance HMD » depuis `Personnel` ; Custom Fields `Asset Repair` : `type_intervention`, `personnel`, `reference_hmd` | FIN-S32 | `setup/finance/maintenance.py` |
| Moteur : `enregistrer_intervention`, `annuler_intervention`, `planifier_maintenance` (préventif calendaire), `interventions_planifiees`, `interventions_realisees`, `cout_maintenance`, `cout_horaire`, `cout_utilisation` — erreurs `ERR-MNT-01→08` | FIN-S32/S96 | `utils/maintenance_utils.py` (511 l.) |
| DocType `Utilisation Equipement` (équipement, date, heures, atelier, opérateur) — 25 DT/h par défaut, surchargeable par équipement, **aucune écriture GL** (clé analytique) | FIN-S96 | `doctype/utilisation_equipement/` |
| Cheptel comme actif (1 vache = 1 Asset, mise en service au 1er vêlage, rebut à la sortie) — `cheptel_mode = NON_VALORISE` par défaut, décision client en attente | FIN-S31/S80 | `utils/cheptel_valorisation.py` |
| Rapport Interventions (réalisées · préventif dû/en retard · rapprochement GL 615 ↔ repairs) | SCRUM-11 | `report/rapport_interventions/` |
| Tableau Amortissement (cumul, reste, date de sortie) | FIN-S90/S91 | `report/tableau_amortissement/` |
| Contrôle Cohérence Finance — contrôle « préventif en retard » | FIN-S70 | `report/controle_coherence_finance/` |
| Seuils coût entretien / CA (3 % / 6 %) colorant le Rapport Périodique | — | `HMD Configuration` |
| Tests : `test_maintenance.py` (~42 contrôles), `test_immobilisations.py`, `test_tableau_amortissement.py`, `test_cheptel.py` | — | `tests/` |

---

## 3. Lecture story par story (US-AM-1 → 13)

Légende : ✅ couvert par ERPNext natif ou déjà livré · 🟡 partiel · ❌ à faire

| Story | Jira | Qui | État | Ce qui existe | Ce qui manque |
|---|---|---|---|---|---|
| US-AM-1 Enregistrer un actif (unicité) | SCRUM-64 | — | 🟡 | `Asset` natif : nom, catégorie, fournisseur, coût, location | Pas de contrôle d'unicité n° série / immatriculation / code interne → Custom Field + validation |
| US-AM-2 Catégoriser | SCRUM-65 | Soumaya | ✅ | 5 Asset Categories livrées (NB : la description Jira parle du cheptel, c'est un autre sujet) | — |
| **US-AM-3 Fiche actif complète** | SCRUM-66 | **Aziz** | 🟡 | Identification + finances natives, amortissement, `cout_horaire`, `id_batiment` ; heures via `Utilisation Equipement` ; coût interventions via `cout_maintenance` | **Pas d'agrégats sur la fiche** (heures cumulées, coût total interventions, ratio réparation/valeur) ; pas de condition ; pas d'ha ni carburant ; pas de valeur marché / coût de remplacement. Piste : dashboard de fiche (`*_dashboard.py` + `connections`) ou champs read-only recalculés |
| US-AM-4 Affecter (employé / parcelle / centre de coût) | SCRUM-67 | — | 🟡 | `Asset Movement` natif (location, custodian = Employee) ; `id_batiment` | Affectation à un Lot/parcelle ou à un atelier (Cost Center) ; « une seule affectation active » ; blocage si vendu/rebut |
| US-AM-5 Condition physique | SCRUM-68 | — | ❌ | rien | Custom Field `condition` (Excellent→Hors service), note obligatoire si Hors service, bascule statut, journal |
| **US-AM-6 Usage (heures, ha, carburant)** | SCRUM-69 | **Aziz** | 🟡 | `Utilisation Equipement` = **les heures**, par atelier, avec contrôles (>0, ≤24 h, asset soumis, date non future, atelier feuille) | **Hectares et carburant absents** ; pas de lien à une tâche agricole ; blocage selon statut (Under Repair…) non fait ; agrégats sur fiche non affichés. ⚠ Garder le principe : **aucune écriture GL** depuis ce DocType (sinon double comptage avec 68x/615) |
| **US-AM-7 Valeur dans le temps** | SCRUM-70 | **Aziz** | 🟡 | Amortissement linéaire natif v15 (`Asset Depreciation Schedule`), plancher à 0 natif, `Asset Value Adjustment` natif pour réévaluation, Tableau Amortissement livré | Valeur marché / coût de remplacement (2 Custom Fields), comparaison côte à côte sur la fiche, « Asset Value Log » (réutiliser `Asset Value Adjustment` plutôt qu'un log maison) |
| US-AM-8 Statut opérationnel | SCRUM-71 | — | 🟡 | Statuts natifs `Asset.status` (Submitted, In Maintenance, Out of Order, Sold, Scrapped…) ; `ERR-MNT-02` bloque intervention sur vendu/rebut | Machine à états métier + journal durées (uptime/downtime) ; lien auto statut ↔ intervention en cours |
| US-AM-9 Recherche / filtres | SCRUM-72 | Soumaya | ✅ | ListView Frappe natif (`id_animal` déjà en filtre standard) | (description Jira = animaux, hors périmètre assets) |
| US-AM-10 Dashboard flotte | SCRUM-73 | — | ❌ | Rapport Interventions + Tableau Amortissement = la donnée | Number Cards / Dashboard Charts : actifs par statut/catégorie, coût YTD, dispo, à réparer |
| US-AM-11 Documents joints | SCRUM-74 | Iheb | ✅ | Attachments Frappe natifs sur `Asset` | Éventuellement un type de document (facture / carte grise / manuel / photo) |
| US-AM-12 Timeline | SCRUM-75 | Soumaya | — | (description Jira = animaux, `live_state.py`) | hors périmètre assets |
| US-AM-13 Seuils & alertes maintenance | SCRUM-76 | Iheb | 🟡 | Préventif **calendaire** (`planifier_maintenance` → `Asset Maintenance Log`), détection retard (`interventions_planifiees`), heures par équipement, seuils coût/CA | **Seuil au compteur d'heures** (cœur de la story), job `daily` maintenance dans `hooks.py`, alerte poussée (DocType `Alerte` est animal-only, `animal` reqd), champ `maintenance_horizon_jours` absent de `HMD Configuration` (quick win) |

---

## 4. Points à trancher avec Aziz (ses 3 stories)

1. **US-AM-6** — étendre `Utilisation Equipement` (ajouter `hectares`, `carburant_l`, lien tâche/intervention) **plutôt que créer un « Asset Usage Log » parallèle**. Un seul DocType = un seul point de saisie pour les tractoristes, et `cout_utilisation()` continue de marcher. Le carburant : saisie informative ou consommation de stock (Stock Entry) ? Si stock, ça devient une charge → à cadrer avec la finance.
2. **US-AM-3** — les agrégats (heures, coût interventions, ratio) doivent être **calculés, jamais saisis** : un dashboard de fiche (`asset_dashboard` via `override_doctype_dashboards` dans `hooks.py`) qui appelle `cout_maintenance` / `cout_utilisation`, pas des champs stockés à resynchroniser.
3. **US-AM-7** — ne pas réécrire l'amortissement : ERPNext v15 le fait. Le seul vrai ajout = 2 Custom Fields (valeur marché, coût de remplacement) + affichage. « Asset Value Log » = `Asset Value Adjustment` natif.
4. **Dépendances transverses** : US-AM-5 (condition) et US-AM-8 (statut) conditionnent le « blocage selon statut » de US-AM-6 → à grooming ensemble ; US-AM-13 (Iheb) dépend des heures de US-AM-6.
5. **Périmètre** : 3 stories sur 13 (AM-2, AM-9, AM-12) ont une description *cheptel*, pas *matériel* → à relabelliser ou à sortir de l'épic Asset Management.

---

## 5. À faire côté socle, indépendamment des US-AM

- **Fusion `finance/socle-comptable` → `main`** (avec accord) : tout ce qui précède n'est visible que sur la branche.
- **FIN-S102** (1 h, High) : raccourci `Utilisation Equipement` dans le workspace HMD AGRO — 0 occurrence dans `fixtures/workspace.json`, « livré mais inatteignable ». À faire avant toute démo.
- **FIN-S31** : décision client valoriser ou non le cheptel à l'actif (`cheptel_mode`).
- `livraison_finance.md` annonce encore « 26/26 » tests maintenance — périmé, c'est ~42.
