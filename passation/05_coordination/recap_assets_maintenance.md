# Assets / Maintenance — ce qui est déjà fait dans `hmd_agro`

*Pour Iheb — préparation du point sur [US-AM-13] Maintenance thresholds and alerts.*
*Branche `finance/socle-comptable`, app `hmd_agro` (Frappe/ERPNext v15).*

---

## 1. En une phrase

Le volet Assets a été fait **par le bas, depuis la finance** : les équipements et le
cheptel sont des `Asset` ERPNext amortis sur un plan comptable SCE, chaque
intervention crée un `Asset Repair` **et** sa charge au compte 615, les heures
d'utilisation valorisent le coût mécanique par atelier, et trois rapports lisent le
tout. Le module ERPNext **Asset / Asset Maintenance / Asset Repair est utilisé tel
quel** — aucun DocType « Équipement » maison n'a été créé.

Ce n'est donc **pas** un module « Asset Management » autonome : c'est le socle
d'actifs nécessaire au coût de revient du litre de lait. C'est important pour
US-AM-13 : les données existent, le déclencheur d'alerte est ce qui manque.

---

## 2. Ce qui existe, fichier par fichier

### 2.1 Référentiel immobilisations — `setup/finance/immobilisations.py` (FIN-S30)

- 5 **Asset Categories** avec durées et comptes SCE :
  Constructions 20 ans (222/282) · Installations & Matériel 10 ans (223/283) ·
  Matériel de transport 5 ans (224/284) · Cheptel reproducteur 5 ans (225/285) ·
  Autres 10 ans (228/288). Dotation → 681, CWIP → 23, linéaire, fréquence 12 mois.
- Location « Ferme HMD », Suppliers, comptes par Mode of Payment (Cash→54, virement→532).
- **Custom Fields sur `Asset`** (DocType core, exportés par nom dans `hooks.py`) :
  - `id_batiment` → Link `Batiment`
  - `id_animal` → Link `Animal` (cheptel)
  - `cout_horaire` → Currency, DT/h
- Booking automatique des dotations (Accounts Settings).

### 2.2 Référentiel maintenance — `setup/finance/maintenance.py` (FIN-S32)

- **Asset Maintenance Team « Maintenance HMD »**, peuplée depuis le registre
  `Personnel` : salariés `ACTIF`, rôle `MAINTENANCE` / `TRACTORISTE`, rattachés à un
  compte utilisateur **activé**. ⚠ Deux niveaux de repli (System User assignable, puis
  `Administrator`) — une équipe peut exister sans aucun vrai salarié dedans.
- **Custom Fields sur `Asset Repair`** : `type_intervention`
  (CURATIVE/PREVENTIVE/REVISION/CONTROLE), `personnel` (Link Personnel),
  `reference_hmd` (marqueur d'idempotence).
- Vérifie l'existence du compte **615 « Entretien et réparations »**.

> Piège v15 documenté dans le code : un `Asset Repair` **non capitalisé ne produit
> aucune écriture comptable**. Sans traitement séparé, on suivrait les pannes sans
> jamais voir leur coût.

### 2.3 Le moteur — `utils/maintenance_utils.py` (FIN-S32 + FIN-S96, 511 lignes)

| Fonction | Rôle |
|---|---|
| `enregistrer_intervention(asset, description, cout, …)` | crée l'`Asset Repair` **et** poste la charge : débit 615 sur l'atelier (argument → équipement → Frais Généraux), crédit 401 / 54 / 532. Idempotent via `reference`. **L'écriture n'est postée que si `cout > 0`.** |
| `annuler_intervention(repair)` | annule le repair **et** son écriture. |
| `planifier_maintenance(asset, taches, equipe, assigne)` | le **préventif** : `Asset Maintenance` + tâches périodiques (Daily → 3 Yearly) ; ERPNext génère les `Asset Maintenance Log` à échéance. |
| `interventions_planifiees(jours=30, equipement, atelier)` | tâches `Planned`/`Overdue` dues dans l'horizon **ou déjà en retard**. |
| `interventions_realisees(debut, fin, equipement, atelier)` | la liste des interventions de la période. |
| `cout_maintenance(debut, fin)` | double lecture : compte 615 du GL **et** somme des `Asset Repair` soumis. |
| `cout_horaire(asset)` | retourne le **taux horaire seul** (`Asset.cout_horaire`, sinon 25 DT/h) — pas un calcul. |
| `cout_utilisation(debut, fin)` | agrège les heures et les coûts **déjà figés à la saisie**, par atelier et par équipement. |

Codes d'erreur `ERR-MNT-01 → 08` (ex. `ERR-MNT-07` équipe absente, `ERR-MNT-08`
aucun compte utilisateur assignable — l'assignation ERPNext casse avec
`Administrator`, dont l'email n'est pas l'identifiant).

### 2.4 Heures d'utilisation — DocType `Utilisation Equipement` (FIN-S96)

Décision réunion 05/08/2026 (« option 2 ») : chaque équipement porte un **coût
horaire forfaitaire** (amortissement + maintenance + mazout, **25 DT/h** par défaut
via `equipement_cout_horaire_defaut`, surchargeable par équipement avec
`Asset.cout_horaire`). On saisit les heures réellement travaillées par atelier.

⚠️ **Ce document ne poste aucune écriture** : amortissement (68x) et entretien (615)
sont déjà au Grand Livre. C'est une **clé de répartition analytique**, pas une charge
de plus — sinon double comptage. Contrôles : heures > 0 (`ERR-UTIL-01`), ≤ 24 h/j
(`02`), équipement **soumis** (`03`), date **non future** (`04`), atelier non-groupe
(`05`). Le blocage vendu / mis au rebut est ailleurs : `ERR-MNT-02`.

### 2.5 Cheptel comme actif — `utils/cheptel_valorisation.py` (FIN-S31)

Une immobilisation par vache (catégorie « Cheptel reproducteur »), mise en service au
**premier vêlage**, valeur d'entrée = prix d'achat réel ou forfait coût d'élevage,
sortie de l'animal → mise au rebut automatique. **Piloté par `cheptel_mode`,
`NON_VALORISE` par défaut** — décision client encore en attente.

### 2.6 Les rapports

| Rapport | Contenu |
|---|---|
| **Rapport Interventions** (SCRUM-11, `report/rapport_interventions/`) | 3 blocs : *Réalisées* (une ligne par intervention + total) · *Préventif* (tâches dues ou **en retard**, horizon 30 j) · *Rapprochement* (écart GL 615 ↔ somme des Asset Repair). Filtres Équipement / Atelier répercutés en SQL sur les 2 premiers blocs ; le Rapprochement ne sait pas filtrer → **il se masque** et affiche la raison. |
| **Tableau Amortissement** (FIN-S90/S91) | durée, mois amortis, cumul, reste à amortir, date de sortie ; actifs sortis inclus par défaut. |
| **Rapport Performance** | « Entretien & Réparations (615) » en DT et « Interventions sur Équipements » en nb — **aucun ratio, aucune couleur**. |
| **Rapport Periodique** | c'est **ici** qu'est le ratio **Entretien / Produit Brut** coloré (`rapport_periodique.py:1621`). |
| **Contrôle Cohérence Finance** (FIN-S70) | 26 contrôles sur base nominale (~24 à ~29 selon les branches), dont *« Tâches de maintenance préventive en retard »* → ALERTE dès qu'une échéance est dépassée, en listant les **4 premiers** équipements (`interventions_planifiees(0)`). |

### 2.7 Tests

`hmd_agro/hmd_agro/tests/test_maintenance.py` (343 lignes, **~42 contrôles** : FIN-S32
sections 1-7 + FIN-S96 sections 8-10) — `bench … execute …tests.test_maintenance.run`.
Le « 26/26 » de `livraison_finance.md` est **périmé** (état d'avant FIN-S96).
Plus `test_immobilisations.py`, `test_tableau_amortissement.py` (19, ou 17 sans le seed
démo « Tracteur Démo »), `test_cheptel.py`.

### 2.8 Commandes d'installation

```bash
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.immobilisations.setup_immobilisations
bench --site <site> execute hmd_agro.hmd_agro.setup.finance.maintenance.setup_maintenance
```

---

## 3. Lecture directe pour **US-AM-13 — Maintenance thresholds and alerts**

### Déjà en place (à réutiliser, pas à refaire)

| Brique | Où |
|---|---|
| Seuil **de coût** entretien / CA, vert-orange-rouge | `HMD Configuration.maintenance_seuil_pct_ca` (3 %) et `maintenance_seuil_alarme_pct_ca` (6 %), lus en `rapport_periodique.py:1357-1358` — ils colorent **une seule cellule**, la ligne « Entretien / Produit Brut » |
| Détection **échéance dépassée** (calendaire) | `interventions_planifiees()` → Rapport Interventions bloc 2 + Contrôle Cohérence |
| Planification périodique | `planifier_maintenance()` → `Asset Maintenance Log` ERPNext |
| **Compteur d'heures** par équipement | DocType `Utilisation Equipement` (la donnée existe, personne ne la surveille) |
| Pattern d'alerte existant dans l'app | DocType `Alerte` + job `daily` `alerte.generate_alerts` (mais **animal uniquement** : chaleur, tarissement, vêlage, délai lait) |

### Ce qui manque — le vrai périmètre d'US-AM-13

1. **Seuil au compteur d'heures** : rien ne compare le cumul d'heures d'un équipement
   à un seuil (« vidange toutes les 250 h »). La périodicité ERPNext est purement
   **calendaire**. C'est le cœur de la story.
2. **Alerte poussée** : aujourd'hui l'information n'existe que si quelqu'un **ouvre**
   un rapport. Pas de `Alerte` d'équipement, pas de notification, pas de job
   `scheduler` maintenance dans `hooks.py`.
3. **`Alerte` n'accepte pas les équipements** : les 7 valeurs de `type_alerte` sont
   toutes animales et le Link `animal` est **`reqd: 1`** — une alerte sans animal est
   structurellement impossible. Il faut étendre le DocType ou en créer un frère.
4. **Horizon préventif non configurable** : `rapport_interventions.py` lit déjà
   `get_config("maintenance_horizon_jours", 30)`, mais **le champ n'existe pas** dans
   `HMD Configuration` → il retombe sur 30. Quick win : ajouter le champ, l'horizon
   devient réglable sans toucher au code.

### Questions ouvertes (à trancher au moment d'attaquer la story)

- Le seuil est-il **heures**, **date**, ou **les deux** (le premier atteint) ?
- Où vit le seuil : Custom Field sur `Asset` (par équipement) ou `HMD Configuration`
  (global par catégorie) ? Ma préférence : sur `Asset`, avec repli sur la config —
  même pattern que `cout_horaire` / `equipement_cout_horaire_defaut`.
- Canal de l'alerte : DocType `Alerte`, Notification ERPNext, ou simple badge dans le
  Rapport Interventions ? Le job `daily` existe déjà, l'accrochage est trivial.
- Qui la reçoit : l'équipe « Maintenance HMD » est déjà constituée depuis `Personnel`.

---

## 4. Le recoupement avec la finance (la question d'Iheb)

Oui, c'est lié — et c'est ce qui contraint la conception : **une intervention n'est
pas qu'un événement de maintenance, c'est une charge**. Toute évolution d'US-AM-13
doit passer par `enregistrer_intervention()` — jamais un `Asset Repair` créé à la main
dans le Desk, qui ne produirait aucune écriture — sinon le compte 615 et le coût de
revient du litre divergent, et le bloc « Rapprochement » du Rapport Interventions
se met à crier. Inversement, une alerte de seuil est **purement de la lecture** :
elle ne poste rien, donc elle est sans risque comptable.

Règle générale du socle finance, valable au-delà d'US-AM-13 : une fonction dans
`utils/` fait le métier **et** la comptabilité, jamais l'un sans l'autre. Le rapport
**Controle Coherence Finance** attrape les écarts quand la règle n'a pas été suivie.
