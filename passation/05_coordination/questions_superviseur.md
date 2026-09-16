# Questions pour mon superviseur — Projet HMD AGRO (`hmd_agro`)

> Stage / PFE — application Frappe/ERPNext de gestion de ferme laitière.
> Questions préparées après une première exploration du code et du MCD.

---

## ⭐ Les 6 questions prioritaires (si la réunion est courte)

1. **Le MCD est-il à jour, ou le code a-t-il volontairement divergé ?** (Plusieurs entités du MCD n'existent pas comme DocType custom — voir §1.)
2. **Quelle est ma première tâche / mon objectif concret de stage ?**
3. **Comment je monte mon environnement de dev** (bench, site local) — y a-t-il un guide ?
4. **Quel est le workflow Git** (branches, pull requests, qui review mon code) ?
5. **Où dois-je mettre la logique métier** — toujours dans la couche `utils/` ?
6. **À qui je m'adresse** pour les questions techniques vs les questions métier (élevage) ?

---

## 🗺️ 1. Écarts entre le MCD et le code

Plusieurs entités du MCD **n'existent pas comme DocType custom** — elles passent par ERPNext ou ne sont pas encore implémentées.

- **PRODUIT / STOCK / MOUVEMENT_STOCK** : passent par ERPNext natif (`Item`, `Bin`, `Stock Entry`) au lieu de DocTypes custom. Choix volontaire ? Si j'ajoute une fonctionnalité de stock, je passe par ERPNext ou je crée du custom ?
- **EQUIPEMENT / INTERVENTION** (famille rouge) : pas implémentés. Prévus plus tard ? Possible tâche pour moi ?
- **COUT / VENTE** (famille jaune, finance) : polymorphes dans le MCD (pointent vers plusieurs tables). Comment la finance est-elle gérée aujourd'hui — comptabilité ERPNext, ou pas encore ?
- **PARAGE** : semble fondu dans **Traitement** plutôt que séparé. Intentionnel ?
- **Le MCD est-il la cible à atteindre, ou une version conceptuelle ancienne ?**

## 🐄 2. Règles métier (domaine laitier)

- Cycle de vie animal (VELLE → GENISSE → VACHE, etc.) : cas particuliers / exceptions à connaître ?
- **Délai d'attente lait** après traitement : la durée vient d'où (réglementation, vétérinaire, config) ?
- **Allotement** par jours en lactation : qui décide des seuils ? Fixes ou configurables ?
- Cascade vêlage (crée veau + ouvre lactation) : des cas où il ne faut PAS la déclencher ?

## 🏗️ 3. Architecture & conventions de dev

- Où mettre la logique métier — toujours `utils/` ?
- Version exacte d'**ERPNext / Frappe** ?
- Workflow **fixtures + patches** : comment déployez-vous une modif de schéma ?
- **Conventions de nommage** (français métier, codes RG/CF/ERR) : à respecter strictement ?
- Niveau d'**exigence sur les tests** : un test par DocType ?

## 💻 4. Mise en route concrète

- Montage de l'**environnement de dev** (bench, site local) — guide existant ?
- **Workflow Git** : branches, PR, reviewer ?
- Accès à des **données de test / staging** ?
- **Première tâche** / ticket simple pour me roder ?
- Interlocuteurs **technique** vs **métier** ?

## 🎯 5. Attentes & objectifs

- **Objectifs concrets** du stage / PFE ?
- **Livrable** attendu à la fin (fonctionnalité, rapport, soutenance) ?
- Comment mon travail sera-t-il **évalué** ?

---
*Préparé avec l'aide de Claude Code — à compléter/ajuster selon ta réunion.*
