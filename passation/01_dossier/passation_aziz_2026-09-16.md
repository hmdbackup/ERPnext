# Passation avec Aziz — module Finance HMD AGRO


L'objectif est qu'Aziz puisse retrouver le travail, en conserver les supports
et transmettre le dossier au futur développeur. Recevoir la passation ne
signifie pas prendre en charge tout le développement restant.

Ce document complète la [passation du 6 septembre](../../passation_2026-09-06.md),
qui conserve le détail fonctionnel et l'historique. Les actions ci-dessous
restent à cocher avec Aziz ; leur préparation ne vaut pas réception.

## 1. État vérifié au 16 septembre

| Point | Constat et portée |
|---|---|
| Code finance | Avant ce regroupement documentaire : branche locale et branche GitHub `finance/socle-comptable` au même commit `b0c33918e2b3e161950d509628c5734a41cb40df`, vérifié avec `git ls-remote`. Ce commit contient la passation du 06/09. |
| Branche `main` distante | `0763bd0c65cf69d22cc0ea2808576ca4c49e9299` ; Avant ce regroupement : 52 commits propres à la branche finance, 4 propres à `main`. La branche finance n'est pas intégrée à `main`. |
| Production | État non contrôlé pendant cette préparation. Le document du 06/09 indique que la finance n'était pas déployée. Aziz doit relever le commit et les versions réellement exécutés. |
| Tests | 41 fichiers `test_*.py` présents, et 5 autres fichiers Python dans le dossier de tests. Aucun test applicatif relancé le 16/09 : ce comptage ne constitue pas un résultat de tests. |
| Backlog local | CSV complet : 9 epics et 61 issues, dont 40 `Done`, 20 `To Do`, 1 `In Progress`. CSV delta : 2 epics et 17 issues. Ces chiffres décrivent les fichiers, pas l'état actuel de Jira. |
| Jira / validations métier | Non consultés en direct pendant cette préparation. Les statuts, affectations et validations du 06/09 doivent être confirmés par l'équipe. |
| Complément actuel | Le PDF et les supports sont regroupés dans `passation/`, destiné à la branche `finance/socle-comptable`. Leur réception par Aziz reste à confirmer. |

## 2. Éléments de la passation

| Élément | Objectif |
|---|---|
| Code source | Retrouver le travail finance sur la branche GitHub `finance/socle-comptable`. |
| Documentation | Identifier l'état du module, les actions restantes et les validations à organiser avec Aymen et M. Samir. |
| Supports et accès | Récupérer les fichiers locaux dans le dossier partagé et confirmer l'accès au code et aux documents. |

Les sections suivantes présentent les procédures de reprise, les supports à transférer et les responsabilités à confirmer avec l'équipe.

## 3. Reprise technique

### Récupérer la bonne branche

Le [guide de développement](../../deploy/DEPLOY.md) partie A installe `main` à
l'étape 5. Pour reprendre le travail finance, remplacer uniquement la
commande de récupération de HMD Agro par :

```bash
bench get-app hmd_agro --branch finance/socle-comptable https://github.com/hmdbackup/ERPnext
```

Cette commande est destinée à un nouveau bench de développement. Dans un
bench existant, vérifier d'abord la branche, les modifications locales et
les versions installées. Les noms de sites diffèrent : le guide crée
`hmd.localhost`, les anciennes commandes de Mohamed ciblent `hmd.agro`.
Adapter les commandes au site effectivement restauré.

### Restaurer et vérifier

- Aziz fournit une sauvegarde complète : base, fichiers publics et privés,
  ainsi que les éléments de configuration nécessaires à la restauration,
  transmis par le canal privé de l'équipe.
- Restaurer sur un environnement de reprise isolé, relever `bench version`
  et le commit de l'app, puis suivre les migrations du guide.
- Faire ouvrir le site et les rapports par la personne qui reçoit le dossier.
  Noter la date de restauration, le commit et les éventuelles erreurs.
- Relancer les modules finance listés dans la passation du 06/09, §7, sur
  cette copie. Conserver les sorties de tests et les anomalies restantes.

### Rejouer une démo cohérente

Le [scénario de la clé FG](../../reunion_2026-09-03/scenario_verification_cle.md)
mélange deux situations : création manuelle d'une clé en septembre, et
lecture d'un jeu préparé en août. Pour une démonstration manuelle, utiliser
une date de facture postérieure à la clé et afficher **le même mois** dans
le rapport. Avec une facture de 1 500 DT et une clé 60/25/15, les montants
attendus sont 900 / 375 / 225 DT. Les pourcentages restent des exemples à
faire valider par M. Samir.

Le [seed de démonstration](../../demo_finance/seed_demo_scrum_10_11.py) appelle
`clear()` dès `run()`. Sa fonction `_supprimer_cles()` supprime les clés FG
du 01/08/2026 sans filtrer sur un marqueur de démo, et certains équipements
sont supprimés par leur nom. **Exécuter ce seed uniquement sur une copie
jetable dédiée à la démo.** Sa procédure nécessite aussi de copier le fichier
dans le package de l'app ; il n'est pas installé automatiquement depuis
`demo_finance/`.

### Préparer la mise en production

Le [runbook d'alignement](../../runbook_alignement_versions.md) et
[`deploy/apps.json`](../../deploy/apps.json) décrivent la livraison via `main`.
La décision de fusion relève d'Aymen, selon la validation métier. L'absence
de conflit indiquée le 06/09 est un constat historique à revérifier au
moment de la fusion. Aziz doit prévoir sauvegarde, reconstruction de l'image,
migrations et vérification des versions selon le runbook.

## 4. Supports regroupés dans le dossier de passation

Les fichiers auparavant non suivis par Git sont regroupés dans `passation/`.
L'index du dossier donne accès aux catégories ; `INVENTAIRE.json` conserve
les anciens et nouveaux chemins. Faire confirmer leur accès par Aziz.

| Support | Disponibilité constatée | Action |
|---|---|---|
| Passation du 06/09, livraison finance, backlog, runbook, conception SCRUM-10/11 | Suivis par Git | Faire retrouver ces documents sur la branche finance. |
| [hmd_agro_codebase_guide.html](../02_documentation/hmd_agro_codebase_guide.html) | Inclus dans le dossier | Transférer : guide utile au futur développeur. |
| [spec_finance.html](../02_documentation/spec_finance.html), [userstories_finance.html](../02_documentation/userstories_finance.html), [plan_finance.html](../02_documentation/plan_finance.html) | Inclus dans le dossier | Transférer les références fonctionnelles citées dans la passation. |
| [presentation_finance.html](../04_demonstration/presentation_finance.html) et [captures/](../04_demonstration/demo_finance/captures) | Inclus dans le dossier | Transférer le deck et les captures nécessaires à sa régénération. |
| [point_assets_aziz.md](../05_coordination/point_assets_aziz.md), [recap_assets_maintenance.md](../05_coordination/recap_assets_maintenance.md), [review_maquettes_fm_iheb.md](../05_coordination/review_maquettes_fm_iheb.md), [questions_superviseur.md](../05_coordination/questions_superviseur.md) | Inclus dans le dossier | Transférer les points de coordination utiles. |
| [validation_samir_rapports_mensuels.md](../05_coordination/validation_samir_rapports_mensuels.md) et [Validation_rapports_mensuels_M_Samir.pdf](../05_coordination/Validation_rapports_mensuels_M_Samir.pdf) | Inclus dans le dossier | Transmettre comme supports ; confirmer leur statut de validation avec l'équipe. |
| [maquettes_validees_2026-08-24.pdf](../03_maquettes/maquettes_validees_2026-08-24.pdf) | Inclus dans le dossier | Transférer si nécessaire pour conserver les arbitrages. |
| `maquettes_2026-08-26.pdf`, `.html`, `.excalidraw` | Suivis par Git | Déjà dans le dépôt ; vérifier séparément les annotations des salons partagés. |
| Vidéos mentionnées dans la passation du 06/09 | Présence non vérifiée dans `Downloads` | Localiser et transmettre si utiles à Aziz. |
| Copie locale de la base et fichiers du site | Restauration / sauvegarde non vérifiées le 16/09 | Convenir avec Aziz de la copie à conserver et vérifier sa restauration avant suppression. |

**Dossier de référence :** [index de la passation](../README.md) sur la branche `finance/socle-comptable`.

## 5. Actions à attribuer pendant la réunion

Les rôles ci-dessous sont proposés à partir de la passation précédente ;
seul Aziz comme interlocuteur de passation est confirmé par Mohamed.

| Action | Responsable proposé | Preuve attendue / état |
|---|---|---|
| Transmettre le lien du dossier et confirmer la réception | Mohamed, réception par Aziz | Liens accessibles à Aziz — à faire. |
| Désigner le développeur qui reprendra le module | Aymen | Nom et date de reprise — à décider. |
| Fournir et faire restaurer une sauvegarde | Aziz, avec la personne chargée de la reprise | Site de reprise ouvert, date et versions notées — à confirmer. |
| Relever le code réellement exécuté en production | Aziz | Commit et sortie `bench version` — à relever. |
| Confirmer les affectations de SCRUM-10, 11, 105, 108, 121, 128 | Aymen / responsable Jira | Responsable identifié dans Jira — à vérifier. |
| Rapprocher les CSV avec Jira avant import | Responsable Jira à désigner | Liste des tickets absents et doublons évités — à faire. Le delta suppose que les stories d'origine ont déjà été importées. |
| Faire valider la clé FG et les décisions métier restantes | Aymen avec M. Samir | Réponses écrites référencées — à confirmer. |
| Décider la fusion et planifier le déploiement | Aymen, puis Aziz pour l'infrastructure | Décision et créneau consignés — à confirmer. |
| Organiser la fermeture des accès de Mohamed | Administrateurs concernés | Date convenue après réception des éléments — à définir. |

La désignation d'un successeur, la validation métier et la mise en production
peuvent rester des actions de l'équipe après le départ de Mohamed. La
passation doit en laisser la responsabilité et l'état explicites.

## 6. Compte rendu à remplir avec Aziz

- [ ] Date de départ et date de réunion renseignées.
- [ ] Aziz accède à la branche finance et retrouve le commit transmis.
- [ ] Dossier de passation reçu ; lien partagé : …
- [ ] Sauvegarde identifiée ; emplacement privé : … ; date : …
- [ ] Restauration vérifiée, ou responsable et échéance convenus : …
- [ ] Questions techniques ouvertes consignées : …
- [ ] Aymen identifié pour la désignation de la relève et les décisions restantes.
- [ ] Transfert des tickets et fermeture des accès attribués à un responsable.
- [ ] Réception du dossier confirmée par Aziz le : …

**Actions restant à l'équipe après le départ :** …

**Disponibilité éventuelle de Mohamed après le départ :** à convenir
explicitement ; aucun engagement n'est présumé.
