#!/usr/bin/env python3
"""Source unique du backlog Finance HMD AGRO — génère les CSV importables dans Jira.

Règle de tenue : le statut d'une story vit dans la colonne ``Status``, JAMAIS en
prose dans sa description. C'est la prose (« Statut: livré », « DECISION CLIENT »)
qui a fait dériver les anciens fichiers — quatre stories affichaient un état faux.

Usage :
    python3 jira/backlog.py

Produit :
    jira/backlog_finance.csv        — tout (epics + issues), pour un projet Jira vierge
    jira/backlog_finance_delta.csv  — uniquement le nouveau, pour un projet déjà peuplé
"""

import csv
import os

TODO, DOING, DONE = "To Do", "In Progress", "Done"
HIGHEST, HIGH, MEDIUM, LOW = "Highest", "High", "Medium", "Low"

# Vagues de travail (labels, pas des sprints Jira : aucun sprint n'est créé à l'import)
V1 = "vague-1-fiabilisation"   # à faire avant toute démo client
V2 = "vague-2-genisses"        # EPIC I — atelier génisses
V3 = "vague-3-consolidation"   # backlog froid, à planifier

REUNION = "reunion-2026-08-05"
GROOM = "groom-2026-08-07"     # issues nées du grooming du 07/08/2026

# ── Epics ────────────────────────────────────────────────────────────────────
# Pas d'EPIC H : « Epic H » dans livraison_finance.md désigne un LOT DE LIVRAISON
# (S24/S25/S31/S32/S42/S70), pas un epic. Ces stories restent dans leur epic
# métier et portent le label « lot-h ».

EPICS = [
    ("Socle comptable", "EPIC A - Socle comptable", DONE,
     "Socle comptable ERPNext (plan comptable tunisien SCE, exercice, TVA) et analytique "
     "(cost centers par atelier, dimensions Lot / Bâtiment)."),
    ("Valorisation des couts", "EPIC B - Valorisation des coûts", DONE,
     "Brancher de vrais prix sur la mécanique de coûts déjà câblée pour obtenir un coût/litre réel."),
    ("Recettes", "EPIC C - Recettes", DOING,
     "Enregistrer les recettes (lait, animaux, fumier) via Selling / Sales Invoice, "
     "avec grille de prix qualité et décompte mensuel figé."),
    ("Immobilisations", "EPIC D - Immobilisations & cheptel", DOING,
     "Immobilisations, amortissements et maintenance via le module Asset d'ERPNext, "
     "cheptel à l'actif et identification des animaux."),
    ("Charges et main-d'oeuvre", "EPIC E - Charges & main-d'œuvre", DOING,
     "Charges diverses et main-d'œuvre ventilées par atelier (Cost Center), "
     "registre du personnel et masse salariale."),
    ("Pilotage", "EPIC F - Pilotage", DONE,
     "KPI économiques (coût/litre, IOFC, EBE, marge), rapports périodiques et coloration par seuils."),
    ("Bascule", "EPIC G - Bascule & droits", DOING,
     "Bascule comptable : à-nouveaux / balances d'ouverture, droits par rôle, "
     "contrôle de cohérence sur données réelles."),
    ("Atelier Genisses", "EPIC I - Atelier génisses", TODO,
     "Coût de revient d'une génisse de la naissance à 18-22 mois et facturation interne du lait bu, "
     "pour arbitrer entre vendre tôt et élever. Spécification : spec_cout_genisse_facturation_interne.md."),
    ("Exploitation", "EPIC J - Exploitation & déploiement", DOING,
     "Déploiement, versions, langue de l'interface, accès aux écrans, jeux de données et simulations de démo."),
]

# ── Issues ───────────────────────────────────────────────────────────────────
# (type, summary, epic, status, priority, estimate, labels, description)

ISSUES = []


def issue(summary, epic, status, priority, estimate, labels, description,
          kind="Story", new=False):
    ISSUES.append({
        "kind": kind, "summary": summary, "epic": epic, "status": status,
        "priority": priority, "estimate": estimate, "labels": labels,
        "description": description.strip(), "new": new,
    })


# ── EPIC A — Socle comptable ─────────────────────────────────────────────────

issue("FIN-S01 Configurer le référentiel comptable tunisien", "Socle comptable",
      DONE, MEDIUM, "", ["finance", "phase-1"], """
En tant que comptable, je veux un plan comptable, un exercice et la TVA configurés afin de tenir une comptabilité conforme dans ERPNext.

Critères d'acceptation:
- Chart of Accounts tunisien (SCE) chargé sur la Company hmd-agro et validé par le comptable.
- Fiscal Year + devise TND + modèles de TVA (lait / animaux / intrants).
- Bilan et CPC s'ouvrent sans erreur.

Livraison: commit 40d8593 — setup/finance/socle_comptable.py, 77 comptes, TVA 19/13/7/0.
RG: RG-FIN-01
""")

issue("FIN-S02 Créer les centres de coûts et dimensions analytiques", "Socle comptable",
      DONE, MEDIUM, "", ["finance", "phase-1"], """
En tant que gérant, je veux des ateliers et des axes Lot / Bâtiment / Atelier afin de ventiler charges et produits par activité.

Critères d'acceptation:
- Cost Centers : Lait, Élevage/Génisses, Cultures/Fourrage, Traction, Frais Généraux.
- Accounting Dimensions Lot, Bâtiment, Atelier actives sur les écritures.
- Une écriture de test porte bien Cost Center + dimension Lot.

Livraison: commit 40d8593 — 5 Cost Centers, dimensions Lot/Bâtiment.
RG: RG-FIN-40
""")

# ── EPIC B — Valorisation des coûts ──────────────────────────────────────────

issue("FIN-S10 Saisir les achats d'intrants vers valuation_rate", "Valorisation des couts",
      DONE, MEDIUM, "", ["finance", "phase-2"], """
En tant que responsable achats, je veux enregistrer les achats d'aliments / médicaments / semences afin que le CMP de chaque article soit réel.

Critères d'acceptation:
- Une Purchase Invoice / Receipt sur un Item met à jour Bin.valuation_rate (différent de 0).
- Le fournisseur et le compte de charge sont correctement imputés.

Livraison: commit 2de4c06
RG: RG-FIN-30
""")

issue("FIN-S11 Basculer la sortie de stock sur le coût réel", "Valorisation des couts",
      DONE, MEDIUM, "", ["finance", "phase-2"], """
En tant que développeur Finance, je veux que stock_utils valorise les consommations au CMP réel afin que les coûts cessent d'être à zéro.

Critères d'acceptation:
- basic_rate=0 remplacé par la valorisation native (derrière test).
- stock_value_difference devient non nul sur une Material Issue après achat.
- Le refus batch v15 et allow_negative_stock restent intacts.
- Garde-fou : un CMP encore à 0 ne bloque jamais la saisie terrain.

Livraison: commit 2de4c06 — restaurations symétriques on_trash incluses.
RG: RG-FIN-30, CF-FIN-31
""")

issue("FIN-S12 Voir le coût/litre réel dans le rapport périodique", "Valorisation des couts",
      DONE, MEDIUM, "", ["finance", "phase-2"], """
En tant que gérant, je veux le coût alimentaire réel par litre et par vache afin de piloter la rentabilité sans calcul manuel.

Critères d'acceptation:
- Le bloc « Frais et coût » affiche DT/L et DT/vache (présente et lactante) à partir du GL stock.
- Les valeurs concordent avec un calcul manuel de contrôle sur une journée.

Livraison: commit 2de4c06
RG: RC-FIN-50
""")

# ── EPIC C — Recettes ────────────────────────────────────────────────────────

issue("FIN-S20 Définir l'article Lait et le prix-qualité", "Recettes",
      DONE, MEDIUM, "", ["finance", "phase-3"], """
En tant que comptable, je veux un article Lait avec un prix indexé TB/TP afin de facturer au juste prix qualité.

Critères d'acceptation:
- Item Lait + Item Price ; Pricing Rule appliquant primes / pénalités TB/TP.
- Aucun prix en dur dans le code.

Livraison: commit 587d60b — items LAIT-CRU / FUMIER / ANIMAL-VENTE (701/708/702).
RG: RG-FIN-10, RG-FIN-01
""")

issue("FIN-S21 Facturer ou importer la recette lait de la période", "Recettes",
      DONE, MEDIUM, "", ["finance", "phase-3"], """
En tant que comptable, je veux générer la facture lait de la période — ou importer le décompte de la centrale — afin d'enregistrer la recette principale.

Critères d'acceptation:
- Si la ferme facture : job idempotent (marqueur remarks) agrégeant lait_vendu vers une Sales Invoice ; re-run = no-op.
- Si auto-facturation : import du décompte (pattern import_rapport.py), aucune facture concurrente.
- Recette rapprochée du volume saisi.

Livraison: commit 587d60b
Voir aussi: FIN-D03 (choisir lequel des deux modes est actif — ne jamais activer les deux).
RG: RG-FIN-10, RG-FIN-11, RG-FIN-12, RG-FIN-04
""")

issue("FIN-S22 Émettre une facture à la vente d'un animal", "Recettes",
      DONE, MEDIUM, "", ["finance", "phase-3"], """
En tant que gérant, je veux qu'une vente d'animal génère sa facture afin de comptabiliser la recette automatiquement.

Critères d'acceptation:
- Au passage du statut vers VENDU / REFORME, Sales Invoice créée depuis prix_vente (poids via Pesée VENTE si prix/kg).
- count_exits() reste cohérent ; suppression = écriture compensatoire.

Livraison: commit 587d60b
RG: RG-FIN-20, CF-FIN-21
""")

issue("FIN-S23 Vendre fumier et produits divers", "Recettes",
      DONE, LOW, "", ["finance", "phase-3"], """
En tant que gérant, je veux facturer le fumier (et produits annexes) afin de capturer toutes les recettes.

Critères d'acceptation:
- Items dédiés ; Sales Invoice ponctuelle imputée au bon atelier.

Livraison: commit 587d60b
RG: RG-FIN-10
""")

issue("FIN-S24 Grille de prix qualité de la centrale", "Recettes",
      DONE, MEDIUM, "", ["finance", "phase-3", "lot-h"], """
En tant que gérant, je veux que le litre soit payé au barème réel de la centrale afin que le chiffre d'affaires lait reflète la qualité produite et non un prix plat.

Critères d'acceptation:
- DocType Grille Prix Lait : prix de base, période de validité, paliers par critère (TB, TP, germes, cellules), plancher de prix, plafond de prime.
- Une seule grille active peut couvrir une date donnée (refus à la saisie).
- Les paliers priment sur l'indexation linéaire ; un critère sans palier retombe sur la prime par point de la configuration.
- compute_milk_rate lit la grille en vigueur À LA DATE FACTURÉE ; sans grille, repli prix plat documenté.
- La facture trace dans ses remarques la grille utilisée, le prix de base et chaque prime.
- Statut PROVISOIRE tant que la centrale n'a pas confirmé : signalé sur la facture, dans le rapport et dans le contrôle de cohérence.

Livraison: commit 4403f05 — moteur complet. Une grille « Grille Centrale — provisoire » tourne avec des paliers INDICATIFS.
Voir aussi: FIN-D01 (obtenir la grille contractuelle et passer le statut à VALIDEE — aucun code à toucher).
RG: RG-FIN-10, RG-FIN-13 / RC-FIN-13
""")

issue("FIN-S25 Valoriser l'écart lait en dinars", "Recettes",
      DONE, MEDIUM, "", ["finance", "phase-3", "lot-h"], """
En tant que gérant, je veux savoir ce que coûtent les litres qui manquent à l'appel afin d'arbitrer sur les pertes de lait comme je le fais déjà sur l'aliment.

Critères d'acceptation:
- finance_kpis.ecart_lait retourne litres perdus, valeur en dinars, part de la production, prix du litre appliqué.
- Valorisation au prix de la période — la même grille que la facture, pas un prix à part.
- Les écarts négatifs (sur-affectation : vendu + conso interne + veau > production saisie) sont comptés à part et JAMAIS valorisés : c'est une erreur de saisie.
- Bilan Lait Journalier calcule son écart quelle que soit la source (avant : uniquement via la page Saisie Traite).
- Trois lignes au rapport périodique : écart en litres, en % de la production (coloré), en dinars.
- Seuils ecart_lait_seuil_perte_pct (orange) et ecart_lait_seuil_alarme_pct (rouge) en configuration.

Livraison: commit 4403f05
RG: RC-FIN-14
""")

issue("FIN-S85 Décompte lait mensuel figé (historisation des recettes)", "Recettes",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je veux que les recettes lait d'un mois clos soient figées : modifier une grille de prix aujourd'hui ne doit jamais réécrire les chiffres passés.

Critères d'acceptation:
- DocType soumis Decompte Lait Mensuel : volumes, TB/TP pondérés, grille appliquée, décomposition du prix (base, prime qualité, prime quantité, ajustement), facture liée — figé au submit.
- generate_milk_invoice crée / complète le décompte et facture à son prix_final ; idempotence par décompte soumis.
- finance_kpis.ecart_lait lit le décompte soumis des périodes closes (plus de recalcul live).
- Une grille référencée par un décompte soumis devient non modifiable / non supprimable (ERR-GRL-06) — versionner par dates.
- Patch v1_8 backfill : un décompte figé par facture LAIT_FACT existante.

Livraison: commit 84e55ec
Origine: réunion 05/08/2026
""")

issue("FIN-S86 Bonus quantité et ajustement mensuel manuel", "Recettes",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je veux le bonus de quantité (payé plus cher quand on livre plus) et un ajustement manuel de bonification pour un mois donné.

Critères d'acceptation:
- Critère VOLUME dans les paliers de grille (bornes en litres/mois), intégré au calcul du prix du litre.
- Champ ajustement_manuel + motif sur le Decompte Lait Mensuel, répercuté sur la facture.

Livraison: commit 84e55ec
Suite: multi-acheteurs et grille par centrale livrés depuis par FIN-S94. Reste ouvert : le prorata intra-mois (FIN-S103).
Origine: réunion 05/08/2026
""")

issue("FIN-S94 Multi-acheteurs lait avec profil de prix par acheteur", "Recettes",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je vends le lait à plusieurs acheteurs (aujourd'hui 2 acheteurs externes payants + l'atelier génisses en interne) et je veux un profil de prix par acheteur.

Critères d'acceptation:
- N acheteurs configurables ; par acheteur : profil prix unique OU par paliers (bonus quantité), pas de paiement qualité pour l'instant.
- Ventilation du lait vendu par acheteur (évolution Bilan Lait Journalier), un Decompte Lait Mensuel figé PAR acheteur (levée de la contrainte mono-acheteur ERR-DLM-04).
- Règlement en fin de mois sur moyenne mensuelle ; prix temporaire accepté le temps de finaliser avec l'acheteur (statut PROVISOIRE).
- La destination interne « atelier génisses » relève de la facturation interne (FIN-S111), pas d'une facture client.

Livraison: commit 865fde1 — grille par acheteur avec précédence documentée, prix moyen pondéré dans ecart_lait, config client_lait_defaut, patch de reprise v1_9.
Origine: réunion 05/08/2026
""")

issue("FIN-S103 Prorata intra-mois pour la répartition multi-acheteurs", "Recettes",
      TODO, LOW, "1d", ["finance", GROOM, V3], """
En tant que gérant, je veux qu'un changement d'acheteur ou de prix en cours de mois soit pris au prorata des jours afin que le décompte reste juste sans attendre le mois suivant.

Contexte: explicitement mis hors périmètre de FIN-S86 et non traité par FIN-S94, qui règle à la moyenne mensuelle par acheteur.

Critères d'acceptation:
- Un changement de grille ou d'acheteur en cours de mois découpe le décompte en sous-périodes datées.
- Le prix moyen pondéré de finance_kpis.ecart_lait tient compte du découpage.
- Un décompte déjà soumis n'est jamais recalculé (FIN-S85).

Créée au grooming du 07/08/2026.
""", new=True)

# ── EPIC D — Immobilisations & cheptel ───────────────────────────────────────

issue("FIN-S30 Enregistrer les équipements en immobilisation", "Immobilisations",
      DONE, MEDIUM, "", ["finance", "phase-4"], """
En tant que comptable, je veux les équipements en Asset avec amortissement afin que les dotations impactent le résultat.

Critères d'acceptation:
- Asset Categories + durées ; un Asset génère son calendrier et ses Journal Entries de dotation.
- Custom Field Asset-id_batiment reliant l'actif au DocType Batiment (exporté par nom).

Livraison: commit 6949776 — 5 Asset Categories sur 22x/28x/681, amortissement linéaire automatique.
RG: RC-FIN-53
""")

issue("FIN-S31 Décision — valoriser le cheptel comme actif biologique", "Immobilisations",
      TODO, MEDIUM, "4h", ["finance", "phase-4", "lot-h", V3, "decision-client"], """
En tant que comptable, je veux trancher le traitement comptable du cheptel afin de valoriser / amortir correctement le troupeau.

Critères d'acceptation:
- Outil livré et piloté par la configuration cheptel_mode : NON_VALORISE (défaut), ACTIF_BIOLOGIQUE, STOCK.
- En mode ACTIF_BIOLOGIQUE : une immobilisation par vache (catégorie Cheptel reproducteur, comptes 225/285), mise en service au PREMIER VÊLAGE.
- Valeur d'entrée : prix d'achat réel pour un animal acheté, forfait coût d'élevage (configurable) pour un animal né sur la ferme.
- Reprise de l'existant : amortissement déjà couru en ouverture, amortissement du solde sur la durée résiduelle. Vache dont la durée est épuisée : hors périmètre, comptée et signalée.
- Sortie de l'animal (VENDU / MORT / REFORME) : mise au rebut automatique de l'immobilisation, sans jamais bloquer l'enregistrement de la sortie.
- Custom Field Asset-id_animal : une vache, une immobilisation (clé d'idempotence).
- Rapport : effectif immobilisé, valeur brute, valeur nette comptable.
- Job mensuel de synchronisation, sans effet tant que le mode est NON_VALORISE.

L'OUTIL EST LIVRÉ (commit 4403f05). Cette story reste ouverte parce que son livrable est LA DÉCISION : bien amortissable ou stock ? Un seul champ bascule.
Reste à faire une fois la décision prise: passer cheptel_mode, vérifier cheptel_cout_elevage et cheptel_duree_amortissement_ans, lancer synchroniser_cheptel.
RG: RG-FIN-32, RG-FIN-33, CF-FIN-33 / RC-FIN-55
""")

issue("FIN-S32 Interventions et maintenance des équipements", "Immobilisations",
      DONE, MEDIUM, "", ["finance", "phase-4", "lot-h"], """
En tant que gérant, je veux savoir ce que coûte l'entretien de chaque équipement afin de ne plus amortir du matériel sans connaître son coût de fonctionnement.

Critères d'acceptation:
- enregistrer_intervention crée un Asset Repair ERPNext (panne, actions, durée d'arrêt, pièces) ET poste la charge au compte 615 sur l'atelier de l'équipement.
- ATTENTION ERPNext v15 : un Asset Repair non capitalisé ne produit AUCUNE écriture comptable — d'où l'écriture posée séparément.
- Trois modes de règlement : fournisseur (avec tiers), caisse, banque. Coût nul = suivi sans écriture (intervention interne).
- Idempotence par référence ; annulation symétrique.
- planifier_maintenance crée le plan préventif (Asset Maintenance + tâches périodiques) avec des échéances réellement calculées.
- Custom Fields sur Asset Repair : type d'intervention, intervenant (lien Personnel), référence HMD.
- Rapport : frais d'entretien, nombre d'interventions, entretien / produit brut (coloré par seuil).

Livraison: commit 4403f05
RG: RG-FIN-30, RG-FIN-31, CF-FIN-31 / RC-FIN-54
""")

issue("FIN-S80 Afficher le N° travail sur les assets cheptel", "Immobilisations",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant qu'utilisateur, je veux voir le numéro de travail de la vache (ex. 0122) et non l'ID technique (ex. 0000000122) dans la liste des assets afin d'identifier les animaux d'un coup d'œil.

Critères d'acceptation:
- asset_name = « Vache <nom_metier> » à la création de l'actif cheptel.
- Un renommage de l'animal (nouvelle boucle) ou un changement de nom_metier repropage le titre sur l'Asset (frappe.db.set_value, actifs soumis).
- Le champ Asset-id_animal est visible en liste et en filtre standard.
- Patch v1_8 rename_assets_cheptel retitre idempotemment les assets existants.

Livraison: commit 78b7e5b
Origine: réunion 05/08/2026, remarque de M. Samir (40:00-56:00)
""")

issue("FIN-S81 Identification provisoire au vêlage puis boucle officielle", "Immobilisations",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant qu'éleveur, je veux qu'un veau reçoive instantanément un ID provisoire au vêlage puis enregistrer plus tard sa boucle officielle tunisienne, l'identification officielle devenant non modifiable.

Critères d'acceptation:
- Les IDs auto-générés au vêlage sont dans la bande réservée 99xxxxxxxx et flaggés identification_provisoire=1.
- Un ID officiel n'est pas renommable (ERR-ANI-01), sauf System Manager.
- Méthode enregistrer_boucle_officielle + bouton sur la fiche Animal (visible si provisoire) : format 10 chiffres (ERR-ANI-02), unicité (ERR-ANI-03), animal provisoire uniquement (ERR-ANI-04) ; renomme, efface le flag, resynchronise nom_metier et l'asset.

Livraison: commit 78b7e5b
Voir aussi: FIN-D05 (vérification du préfixe 99999 — non bloquante, cf. questions_samir.md v3).
Origine: réunion 05/08/2026
""")

issue("FIN-S90 Tableau d'amortissement consolidé", "Immobilisations",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je veux un tableau unique de tous les actifs (vaches, tracteurs, matériel) comparable aux états de l'expert-comptable.

Critères d'acceptation:
- Script Report Tableau Amortissement en français : ID actif, désignation, catégorie, animal, valeur initiale, dates acquisition / entrée / sortie, durée en mois, mois amortis, amortissement cumulé, reste à amortir, statut ; totaux ; actifs sortis inclus par défaut.
- Compatible v15 (Asset Depreciation Schedule) ; remplace les ledgers natifs supprimés ; Fixed Asset Register reste disponible.

Livraison: commit c770be5
Origine: réunion 05/08/2026 (00:00-02:50)
""")

issue("FIN-S91 Coût horaire par équipement", "Immobilisations",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je veux un coût horaire d'utilisation par équipement (défaut 25 DT/h configurable) pour imputer la mécanique aux ateliers et au coût du litre.

Critères d'acceptation:
- Config equipement_cout_horaire_defaut (25 DT/h, patch v1_8) + champ Asset.cout_horaire surchargeable.
- Résolveur maintenance_utils.cout_horaire(asset).

Livraison: commit c770be5. La saisie des heures, qui manquait à cette story, a été livrée par FIN-S96 — story close.
Origine: réunion 05/08/2026 (60:00-68:00)
""")

issue("FIN-S96 Saisie des heures d'utilisation par équipement", "Immobilisations",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je veux saisir les heures d'utilisation de chaque équipement (« le tracteur a travaillé 1 h ou 5 h dans la journée ») pour imputer un coût horaire forfaitaire aux ateliers et au coût du litre.

Décision de la réunion du 05/08/2026 — option 2 retenue en séance:
- Coût horaire forfaitaire par équipement = amortissement + maintenance + carburant, 25 DT/h par défaut (FIN-S91).
- Saisie par utilisation / journée : DocType Utilisation Equipement (équipement, date, heures, atelier, opérateur) — vue analytique, AUCUNE écriture GL (le 68x et le 615 y sont déjà : éviter le double comptage).
- Imputation : heures x coût horaire ventilé par atelier vers la quote-part mécanique du rapport de performance et du coût du litre.
- Répercussion sur le coût du litre : obligatoire (réunion).

Livraison: commits 1f73bea + 2508504 — taux figé sur la ligne à la saisie, cout_utilisation() agrégé par atelier et par équipement, lignes « Heures d'Équipement », « Coût d'Utilisation Mécanique » et « Coût Mécanique / L ».
Suite: le DocType n'est pas accessible depuis le menu (FIN-S102).
Origine: réunion 05/08/2026
""")

# ── EPIC E — Charges & main-d'œuvre ──────────────────────────────────────────

issue("FIN-S40 Saisir les charges diverses ventilées", "Charges et main-d'oeuvre",
      DONE, MEDIUM, "", ["finance", "phase-5"], """
En tant que comptable, je veux enregistrer énergie / eau / loyer / assurances par atelier afin d'obtenir un coût complet.

Critères d'acceptation:
- Purchase Invoice / Journal Entry imputées au Cost Center selon la clé validée client.

Livraison: commit 6949776
RG: RG-FIN-40
""")

issue("FIN-S41 Intégrer le coût de la main-d'œuvre", "Charges et main-d'oeuvre",
      DONE, MEDIUM, "", ["finance", "phase-5"], """
En tant que gérant, je veux le coût du travail ventilé par atelier afin que le coût/litre inclue la MO.

Critères d'acceptation:
- Écritures de salaire ventilées sur Cost Centers ; la ligne MO apparaît dans le coût total.

Livraison: commit 6949776 — post_salaires, modes de paiement 54/532.
RG: RG-FIN-40
""")

issue("FIN-S42 Registre du personnel et masse salariale", "Charges et main-d'oeuvre",
      DONE, MEDIUM, "", ["finance", "phase-5", "lot-h"], """
En tant que gérant, je veux un registre des salariés (qui, quel rôle, quel salaire, quel atelier) afin que le coût de main-d'œuvre du litre soit une donnée et non un montant tapé à la main.

Critères d'acceptation:
- DocType Personnel : nom, rôle, type de contrat, dates d'embauche et de sortie, salaire brut, taux d'activité, assujettissement aux charges patronales, atelier principal.
- Table de répartition multi-ateliers (somme des parts = 100 %).
- Garde-fous ERR-PERS-01 à 07 : salaire négatif, sortie avant embauche, répartition différente de 100 %, atelier inconnu ou groupe, taux d'activité hors bornes, statut SORTI sans date, atelier en double.
- masse_salariale reconstruit le mois depuis le registre, AU PRORATA des jours pour une entrée ou une sortie en cours de mois.
- post_salaires poste une écriture équilibrée : débit 640 (brut) et 647 (charges patronales) par atelier, crédit 421 et 453. Idempotente par marqueur.
- Le chemin « montants forcés » reste disponible pour la reprise d'historique.
- Compte 453 Organismes sociaux ajouté au plan.
- Job mensuel : masse salariale du mois écoulé.
- Rapport : coût main-d'œuvre par litre et par vache présente.

Livraison: commit 4403f05 (+ d07fead pour l'équilibre au prorata).
Voir aussi: FIN-D02 (salaires réels à saisir avant de poster une vraie paie).
RG: RG-FIN-40, RG-FIN-41 / RC-FIN-41, RC-FIN-42
""")

issue("FIN-S82 Charges patronales 30 % par défaut, surchargeables par salarié",
      "Charges et main-d'oeuvre", DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je veux un taux de charges patronales par défaut de 30 % dans la configuration, applicable à tous mais modifiable sur chaque fiche employé.

Critères d'acceptation:
- HMD Configuration.taux_charges_patronales_pct par défaut à 30 (patch v1_8 : migre l'ancien défaut 16,57 vers 30, respecte toute valeur personnalisée).
- Champ Personnel.taux_charges_patronales_pct (vide = taux global) ; résolveur taux_charges_effectif utilisé partout (coût employeur, masse salariale).

Livraison: commits 77ac89e + f200601. Le correctif f200601 était nécessaire : le gel de l'historique (FIN-S83) avait figé l'ancien taux pour tous les mois, y compris à venir. Le changement de taux est désormais journalisé comme un ÉVÉNEMENT DATÉ (16,57 % jusqu'au 31/07, 30 % à partir du 01/08).
Origine: réunion 05/08/2026 (29:50-38:40)
""")

issue("FIN-S83 Historique de salaire immuable", "Charges et main-d'oeuvre",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je veux qu'une augmentation de salaire aujourd'hui ne modifie jamais les charges déjà calculées des mois passés.

Critères d'acceptation:
- Child table Personnel Salaire Historique : toute modification de rémunération ajoute une ligne datée ; les lignes passées sont non modifiables et non supprimables (ERR-PERS-09).
- masse_salariale(periode) résout la rémunération effective à la fin du mois calculé depuis l'historique (repli valeurs vives si vide).
- Le contrôle de cohérence Registre / Grand Livre 64x ne génère plus de fausse alerte après une augmentation.
- Patch v1_8 : une ligne d'historique initiale par employé existant.

Livraison: commit 77ac89e
Origine: réunion 05/08/2026
""")

issue("FIN-S84 Attribution groupée de primes", "Charges et main-d'oeuvre",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je veux cocher plusieurs employés et leur attribuer une prime commune (ex. prime de l'Aïd 50 DT) en un clic.

Critères d'acceptation:
- DocType Prime Personnel (employé, période YYYY-MM, montant, motif) ; une prime touche uniquement son mois.
- Action de liste « Attribuer une prime » sur Personnel (sélection multiple, dialogue, création en masse via attribuer_prime_bulk).
- Les primes du mois entrent dans la masse salariale et l'écriture 640/647 du mois.
- Une prime sur un mois déjà posté au Grand Livre est refusée (ERR-PRIME-04).

Livraison: commit 77ac89e. Les primes sont traitées comme le salaire (soumises aux charges patronales pour les salariés CNSS) — cf. FIN-D06 si des exonérations existent.
Origine: réunion 05/08/2026
""")

issue("FIN-S105 Étalement des grosses charges sur plusieurs mois",
      "Charges et main-d'oeuvre", TODO, MEDIUM, "2d", ["finance", GROOM, V3], """
En tant que gérant, je veux que les petites factures soient absorbées immédiatement et que les grosses factures soient étalées sur plusieurs mois, afin qu'une réparation exceptionnelle n'écrase pas le coût du litre du mois où elle est facturée.

Verbatim réunion 05/08/2026 (~62:00) : « un tracteur qui a maintenant, on absorbe le coût maintenant, on n'amortit pas sur une durée [...] qui fasse des facturations qui sont plus conséquentes, on les étale sur plusieurs mois ».

Critères d'acceptation:
- Seuil d'étalement configurable (montant à partir duquel une charge est proposée à l'étalement) + durée d'étalement par défaut.
- Sur une Purchase Invoice / une intervention dépassant le seuil : répartition sur N mois (charge constatée d'avance ou écritures mensuelles), imputée au même atelier.
- Le coût du litre et le rapport de performance consomment la quote-part du mois, pas le montant total.
- Idempotence et annulation symétrique, comme le reste des écritures posées par l'app.
- La flexibilité demandée reste entière : on doit pouvoir choisir absorption immédiate OU étalement, facture par facture.

TROU DE BACKLOG : point 13 sur 15 de la liste des changements du compte-rendu du 05/08/2026, jamais transformé en story. La moitié « imputation à l'utilisation » du même point est couverte par FIN-S96 ; l'étalement ne l'est par aucune story.
Créée au grooming du 07/08/2026.
RG: RG-FIN-40
""", new=True)

# ── EPIC F — Pilotage ────────────────────────────────────────────────────────

issue("FIN-S50 Tableau de bord économique", "Pilotage",
      DONE, MEDIUM, "", ["finance", "phase-6"], """
En tant que gérant, je veux coût/litre, IOFC, EBE, produit brut et marge afin de décider vite.

Critères d'acceptation:
- Number Cards / rapport affichant les RC-FIN-50/51/52 (DT/L et DT/vache par poste).
- Intégré au rapport périodique existant (réutilise dashboard_kpis.py / live_state.py).

Livraison: commit 81da51e — finance_kpis.gl_sums : CA lait, produit brut, charges, MO, EBE, résultat, coût complet/L, IOFC.
RG: RC-FIN-50, RC-FIN-51, RC-FIN-52
""")

issue("FIN-S51 Seuils économiques en configuration et coloration", "Pilotage",
      DONE, MEDIUM, "", ["finance", "phase-6"], """
En tant que gérant, je veux colorer les indicateurs selon des seuils paramétrables afin de repérer d'un coup d'œil les alertes.

Critères d'acceptation:
- Champs prix_reference_lait, objectif_cout_litre, pfe_iofc_* dans HMD Configuration (seed par patch).
- Coloration vert / orange / rouge via get_config ; champs JS dans boot.JS_FIELDS.

Livraison: commits 81da51e + 8cc3793 (coloration propagée dans la vue « Tout »).
RG: RG-FIN-60
""")

issue("FIN-S87 Seuils indicateur Lait / Concentré (rouge < 1,8 — cible 2,2)", "Pilotage",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je veux que le ratio litres de lait par kg de concentré s'affiche en rouge sous 1,8 avec une cible affichée à 2,2.

Critères d'acceptation:
- pfe_lc_alarm_min passe à 1,8 (patch v1_8, respecte une valeur personnalisée différente de l'ancien défaut 1,5) ; nouveau pfe_lc_cible = 2,2 seedé.
- Cible affichée dans le libellé de la ligne L/C du rapport ; même coloration sur la Number Card 7 jours.
- Seuils pfe_lc_* exposés au JS via frappe.boot.hmd_config.

Livraison: commit 17f0e4e
Origine: réunion 05/08/2026 (06:00-09:00)
""")

issue("FIN-S88 Coût du litre hors amortissement et libellé IOFC", "Pilotage",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je veux lire le coût du litre hors amortissement en sortie de rapport et comprendre l'acronyme IOFC.

Critères d'acceptation:
- Ligne « Coût du Litre hors Amortissement » = (charges - amortissements) / litres, avec comparaison M-1.
- Libellés « IOFC (Income Over Feed Cost) » partout (rapport, cartes).

Livraison: commit 17f0e4e
Origine: réunion 05/08/2026
""")

issue("FIN-S89 Rapport de performance consolidé hebdo/mensuel exportable", "Pilotage",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je veux une vue unique hebdomadaire ou mensuelle : mouvements du cheptel, production, coût des rations, charges RH et mécanique — avec un export propre vers Excel (pas de PDF complexe).

Critères d'acceptation:
- Script Report Rapport Performance (granularités Jour / Semaine / Quinzaine / Mois + date) avec valeurs numériques typées, export CSV/Excel natif propre pour templates externes (VLOOKUP).
- Sections : mouvements cheptel (naissances, vêlages, achats, ventes qty + DT, morts, réformes, effectif début/fin), production, alimentation (coûts + L/C coloré), charges GL (MO 64x, entretien 615, amortissements 68x, EBE, résultat) + maintenance, coûts unitaires (dont hors amortissement, IOFC).
- Raccourci Workspace exporté après migrate.

Livraison: commit 17f0e4e. Raccourci Workspace vérifié présent dans hmd_agro/fixtures/workspace.json (grooming 07/08/2026) — question fermée.
Origine: réunion 05/08/2026
""")

issue("FIN-S95 Renommer le rapport « mensuel » en rapport périodique", "Pilotage",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant qu'utilisateur, je veux que le rapport ne s'appelle plus « Rapport Mensuel » car il est journalier / hebdomadaire / par quinzaine.

Critères d'acceptation:
- Renommer le rapport (et ses raccourcis Workspace / liens) sans casser les URLs existantes ni les tests.
- Cohérence avec le « Rapport Performance » (Semaine/Mois) pour éviter deux noms proches.

Livraison: commits 2508504 + 9b19dbc — dossier, JSON/JS, imports paresseux, raccourcis workspace (blocs ET raccourcis), documents, patch v1_9 idempotent qui fusionne l'orphelin en base.
Origine: réunion 05/08/2026
""")

issue("FIN-S100 Garde-fou période incomplète dans les rapports", "Pilotage",
      DONE, HIGH, "", ["finance", REUNION], """
En tant que gérant, je ne veux pas qu'un trou de saisie soit affiché comme une alerte troupeau.

Constat: le lait n'était saisi que 10 jours en juillet alors que les rations sont distribuées tous les jours, d'où un L/C affiché à 0,66 en ROUGE et un coût du litre à 3,37 DT. Le calcul est juste, la période est incomplète. En production, la saisie prendra du retard un jour ou l'autre.

Critères d'acceptation:
- Les rapports comptent les jours de la période ayant au moins une traite et affichent « Couverture des données (lait) = X/Y jours ».
- Si la couverture est incomplète : ligne d'avertissement explicite en français et coloration NEUTRALISÉE sur les seuls indicateurs faussés (L/C, coûts au litre, IOFC), sans masquer les valeurs.
- Ne neutralise que s'il y a réellement un écart, pour ne pas perdre les vraies alertes.

Livraison: commits 2508504 + ba9a8dc (création du champ de tolérance manquant).
Origine: réunion 05/08/2026
""")

# ── EPIC G — Bascule & droits ────────────────────────────────────────────────

issue("FIN-S60 À-nouveaux / balances d'ouverture", "Bascule",
      TODO, MEDIUM, "1d", ["finance", "phase-7", V3, "decision-client"], """
En tant que comptable, je veux reprendre les soldes d'ouverture à la date de bascule afin de démarrer sur des comptes justes.

Critères d'acceptation:
- Opening Balance saisis ; balance d'ouverture équilibrée à la date convenue.

État réel: la PROCÉDURE est livrée (commit 5d0e03b, setup/finance/BASCULE.md). L'EXÉCUTION ne l'est pas : elle attend la date de bascule et les balances réelles de la ferme. Le tableau de livraison affichait cette story comme livrée — corrigé au grooming du 07/08/2026.
Bloqué par: date de bascule + balances d'ouverture réelles à obtenir de la ferme / de l'expert-comptable.
""")

issue("FIN-S61 Droits par rôle (comptable ≠ éleveur)", "Bascule",
      DONE, MEDIUM, "", ["finance", "phase-7"], """
En tant qu'administrateur, je veux séparer saisie / validation / consultation afin de respecter la séparation des tâches.

Critères d'acceptation:
- Rôles et permissions (Role Permission Manager) ; un éleveur ne peut pas soumettre une écriture comptable.

Livraison: commit 5d0e03b — rôle « Éleveur HMD », zéro accès comptable.
""")

issue("FIN-S70 Rapport de contrôle de cohérence finance", "Bascule",
      DONE, MEDIUM, "", ["finance", "phase-7", "lot-h"], """
En tant que gérant, je veux pouvoir vérifier que les chiffres tiennent debout afin de ne pas décider sur des données fausses.

Critères d'acceptation:
- Rapport « Controle Coherence Finance » (desk + fonction console pour une restauration de production).
- 26 contrôles sur 7 domaines : socle comptable, Grand Livre, lait, coûts, personnel, immobilisations et maintenance, troupeau.
- Trois issues par contrôle : OK / ALERTE (anomalie probable) / ERREUR (le chiffre publié est faux), avec coloration.
- Contrôles clés : Grand Livre équilibré, charges sans atelier, lait vendu vs lait facturé, bilan lait vs somme des traites, articles en stock sans coût unitaire, registre du personnel vs compte 64x, mois sans écriture de salaires, immobilisations sans amortissement, maintenance en retard, sorties d'animaux non facturées, immobilisations d'animaux sortis.
- Lecture seule, rejouable, aucune écriture.
- Une section qui échoue n'interrompt pas le rapport (journalisée, signalée en ERREUR).

Livraison: commit 4403f05 — l'OUTIL est livré. Son exécution sur une base réelle fait l'objet de FIN-S104.
Correction du grooming 07/08/2026: la mention « EN ATTENTE DU BACKUP » était fausse — cf. FIN-S99, l'engagement a été pris côté développement (commit dba011a).
RG: RG-FIN-70
""")

issue("FIN-S104 Exécuter le contrôle de cohérence sur la base réelle", "Bascule",
      TODO, HIGH, "4h", ["finance", GROOM, V1], """
En tant que gérant, je veux que le contrôle de cohérence soit passé sur des données réelles afin de savoir ce qui casse hors du jeu de démonstration.

Contexte: tous les chiffres validés jusqu'ici viennent du seed. L'outil (FIN-S70) n'a jamais tourné sur autre chose.

Critères d'acceptation:
- Le rapport tourne sur une restauration de la base réelle choisie en FIN-S99.
- Chaque ERREUR est tracée puis corrigée (ou transformée en story) ; chaque ALERTE est arbitrée et documentée.
- Compte-rendu d'exécution joint à la story (nombre de contrôles OK / ALERTE / ERREUR).

Dépend de: FIN-S99 (choix et mise à disposition de la source de données réelles).
Créée au grooming du 07/08/2026 — sépare l'outil (livré) de son exécution (non faite).
""", new=True)

# ── EPIC I — Atelier génisses ────────────────────────────────────────────────

issue("FIN-S93 Spécification coût de revient génisse et facturation interne",
      "Atelier Genisses", DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je veux connaître le coût de revient d'une génisse de la naissance à 18-22 mois pour décider de la vendre tôt ou de l'élever.

Livrable de cette story: LA SPÉCIFICATION (spec_cout_genisse_facturation_interne.md) — modèle analytique, formule du coût de revient, aide à la décision, découpage en stories.

Contenu spécifié: facturation interne du lait bu (lait_veau valorisé vers l'atelier génisses), coûts ration par lot, quote-part mécanique (coût horaire équipement), main-d'œuvre ventilée par atelier, aide à la décision vendre vs élever.

Livraison: commit 7edeaf4.
L'IMPLÉMENTATION est portée par FIN-S110 à FIN-S116. Le découpage interne de la spec (§6) numérotait ces stories S80-S86, en collision frontale avec les stories S80-S86 de la réunion déjà livrées — renumérotées en S110-S116 au grooming du 07/08/2026.
Origine: réunion 05/08/2026 (09:00-15:00)
""")

issue("FIN-S110 Rattachement analytique des lots à un atelier", "Atelier Genisses",
      TODO, MEDIUM, "1d", ["finance", GROOM, V2], """
En tant que contrôleur de gestion, je veux que chaque lot porte son atelier afin que les rations distribuées tombent automatiquement sur le bon centre de coût.

Critères d'acceptation:
- Champ Lot.atelier (Link Cost Center) + patch de reprise idempotent sur les lots existants.
- Les Stock Entries de ration (feed_distribution) portent le Cost Center de l'atelier ET la dimension Lot.
- Aucun impact sur les rations déjà postées (reprise documentée).

Colonne vertébrale de l'EPIC I : sans elle, rien n'est ventilable par atelier.
Spec: §2.1 et §2.3 de spec_cout_genisse_facturation_interne.md
""", new=True)

issue("FIN-S111 Facturation interne du lait bu vers l'atelier génisses",
      "Atelier Genisses", TODO, MEDIUM, "2d", ["finance", GROOM, V2], """
En tant que gérant, je veux que le lait bu par les veaux soit facturé à l'atelier génisses afin que l'atelier lait ne porte plus gratuitement un produit qu'il fournit.

Décision de la réunion 05/08/2026 (TRANCHÉE): valorisation au COÛT DU LITRE (« on estime le coût du litre, donc on multiplie »), coût du litre hors amortissement. Le manque à gagner (prix de la grille) est affiché à titre indicatif.
Comptes de cession interne 6061 / 7068x : non bloquants, hors états officiels (« la comptabilité officielle reste chez l'expert-comptable »).

Critères d'acceptation:
- Configs lait_interne_prix_mode (coût du litre / prix fixe) et lait_interne_prix_fixe.
- post_lait_interne mensuel idempotent + job planifié, écriture équilibrée entre ateliers.
- Le rapport affiche la cession interne et le manque à gagner indicatif.
- Annulation symétrique.

Spec: §2.2 · Dépend de: FIN-S110
""", new=True)

issue("FIN-S112 Répartition du lait bu par génisse", "Atelier Genisses",
      TODO, MEDIUM, "1d 4h", ["finance", GROOM, V2], """
En tant que gérant, je veux savoir combien de lait chaque génisse a bu afin d'imputer un coût d'allaitement individuel et non un forfait de troupeau.

Décision réunion: courbe 6-7 L/jour pendant les 3 premiers mois — le défaut 6,5 L/j x 90 j de la spec est validé de fait.

Critères d'acceptation:
- Configs de courbe d'allaitement (litres/jour, durée) paramétrables.
- Répartition NORMALISÉE du lait_veau réellement saisi sur les veaux présents (la courbe sert de clé, le réel sert de total).
- Aucune génisse ne se voit imputer du lait avant sa naissance ou après son sevrage.

Spec: §2.4 · Dépend de: FIN-S110
""", new=True)

issue("FIN-S113 Brancher la quote-part mécanique sur le coût génisse",
      "Atelier Genisses", TODO, MEDIUM, "4h", ["finance", GROOM, V2], """
En tant que gérant, je veux que les heures de tracteur passées sur l'atelier génisses entrent dans le coût de revient d'une génisse.

Critères d'acceptation:
- cout_utilisation() (FIN-S96) est consommé par le calcul du coût génisse, ventilé par atelier et par période.
- Aucun double comptage avec les 68x / 615 déjà au Grand Livre (vue analytique, comme FIN-S96).

Story RÉDUITE de 2 j à 4 h au grooming du 07/08/2026 : la spec prévoyait de créer le champ Asset.cout_horaire et le DocType Utilisation Equipement, déjà livrés par FIN-S91 et FIN-S96. Ne reste que le branchement.
La spec prévoyait aussi une écriture de cession interne pour les travaux : ABANDONNÉ, FIN-S96 a tranché pour une vue analytique sans écriture GL.
Spec: §2.5 · Dépend de: FIN-S110
""", new=True)

issue("FIN-S114 Rapport « Coût de Revient Génisse »", "Atelier Genisses",
      TODO, MEDIUM, "3d", ["finance", GROOM, V2], """
En tant que gérant, je veux un rapport du coût de revient par génisse et par cohorte afin de suivre en continu ce que coûte l'élevage d'un renouvellement.

Critères d'acceptation:
- Script Report en français, deux lectures : par animal et par cohorte (année de naissance).
- Formule du §4 de la spec : lait bu + ration + santé + main-d'œuvre + mécanique + frais généraux éventuels, cumulés en génisse-jours.
- Rapprochement avec le Grand Livre : la somme des coûts imputés à l'atelier génisses doit se retrouver au GL (contrôle intégré).
- Calcul en continu, consultable à tout moment (la ferme le faisait 1x/an à la main).

Spec: §4 · Dépend de: FIN-S110, FIN-S111, FIN-S112, FIN-S113
""", new=True)

issue("FIN-S115 Aide à la décision : vendre à 5 jours, 3 mois ou élever à 18-22 mois",
      "Atelier Genisses", TODO, MEDIUM, "1d 4h", ["finance", GROOM, V2], """
En tant que gérant, je veux comparer le coût cumulé d'une génisse à son prix de marché à trois âges de sortie afin d'arbitrer sur une base chiffrée.

Justification métier (réunion 05/08/2026): l'écart entre les estimations manuelles du gérant, du vétérinaire et de l'ingénieur atteignait ~3000 DT sur le même animal.

Critères d'acceptation:
- Trois scénarios : vente à ~5 jours, vente à 3 mois, élevage jusqu'à 18-22 mois (l'âge de sortie a atteint 22 mois les mauvaises années).
- Configs de prix de marché : velle ~5 j ≈ 3000-3200 DT, génisse pleine ~2 ans ≈ 3000-3500 DT (valeurs de départ de la réunion, à tenir à jour).
- Config de taux de perte (mortalité + infécondité), 8 % par défaut en attendant l'historique réel.
- Delta de décision affiché et coloré ; lecture « coût de remplacement ».

Spec: §5 · Dépend de: FIN-S114 · Voir aussi: FIN-D04
""", new=True)

issue("FIN-S116 Remplacer le forfait cheptel par le coût d'élevage calculé",
      "Atelier Genisses", TODO, LOW, "1d", ["finance", GROOM, V2], """
En tant que comptable, je veux que la valeur d'entrée à l'actif d'une vache née sur la ferme soit son coût d'élevage réellement calculé plutôt qu'un forfait de 2 500 DT.

Critères d'acceptation:
- Option de configuration : forfait cheptel_cout_elevage (actuel) OU coût calculé C(animal, premier vêlage) issu de FIN-S114.
- La bascule ne réécrit jamais la valeur des immobilisations déjà mises en service.

Dépend de: FIN-S114, FIN-S31 (le mode cheptel doit être tranché) · Voir aussi: FIN-D04
Spec: §6, story S86 d'origine.
""", new=True)

# ── EPIC J — Exploitation & déploiement ──────────────────────────────────────

issue("FIN-S92 Alignement des versions et durcissement du déploiement", "Exploitation",
      DOING, HIGHEST, "4h", ["finance", REUNION, V1], """
En tant qu'équipe, nous devons tous voir la même version (le site affichait une version vieille de 2 mois).

Cause racine: le travail finance vit sur finance/socle-comptable, jamais fusionnée dans main (la branche que construit l'image Docker) ; build avec cache Docker pouvant resservir de vieilles couches ; version d'app figée à 0.0.1 rendant les builds indistinguables.

Critères d'acceptation:
- Version hmd_agro 0.2.0 (bump à chaque déploiement) visible dans Aide > À propos. [FAIT]
- erpnext épinglé au tag v15.95.2 dans deploy/apps.json ; build-hmd.sh en --no-cache par défaut. [FAIT]
- DEPLOY.md : procédure de mise à jour révisée + vérification des versions. [FAIT]
- runbook_alignement_versions.md : étapes serveur (Aziz), utilisateurs (Siwar/Soumaya : hard refresh + capture À propos), benchs dev. [FAIT]
- Fusion finance/socle-comptable vers main. [RESTE À FAIRE]
- Rebuild serveur selon le runbook, versions vérifiées par chacun. [RESTE À FAIRE]

Livraison partielle: commit 593bc01 (côté dépôt).
Bloqué par: accord de Mohamed Slim pour la fusion vers main, puis créneau de rebuild serveur.
Origine: réunion 05/08/2026 (fin)
""")

issue("FIN-S97 Interface entièrement en français", "Exploitation",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant qu'utilisateur, je veux une interface entièrement en français (M. Samir en réunion : « fama onglets b'francais wel chay tkhalet », puis « lezemna nq3dou bel francais »).

Cause racine: la langue du site était « en » et chaque compte utilisateur portait « en » en surcharge, donc toute l'interface ERPNext native (Actif, Écriture de Journal, colonnes de liste, boutons) restait en anglais alors que nos propres DocTypes étaient en français.

Critères d'acceptation:
- System Settings.language = fr et comptes existants bascules (patch v1_8 set_langue_francaise, idempotent, une langue choisie délibérément est respectée).
- Vérifié : « Nom de l'Actif », « Statut », « Catégorie d'Actif », « Lieu », « Vue liste », « Dernière Mise à Jour ».
- Symbole monétaire TND : د.ت remplacé par DT.

Livraison: commit f200601
Origine: réunion 05/08/2026
""")

issue("FIN-S98 Accès finance depuis le tableau de bord HMD AGRO", "Exploitation",
      DONE, MEDIUM, "", ["finance", REUNION], """
En tant qu'utilisateur, je veux atteindre les écrans finance depuis le menu HMD AGRO (en réunion, personne ne retrouvait le registre des salariés : « Personnels c'est devenu où ? »).

Critères d'acceptation:
- Nouvelle section « Finance & Gestion » : Personnel, Prime Personnel, Grille Prix Lait, Decompte Lait Mensuel, Immobilisations, Configuration HMD.
- Section « Rapports » complétée : Rapport Performance, Tableau Amortissement, Controle Coherence Finance.
- Cartes du tableau de bord lisibles : « L_C » vers « Lait / Concentré (L/kg) — cible 2,2 », « PL_VL » vers « Production / Vache Lactante (L) ».

Livraison: commit f200601 (fixture workspace).
Suite: le DocType Utilisation Equipement, créé après, a été oublié — FIN-S102.
Origine: réunion 05/08/2026
""")

issue("FIN-S102 Raccourci « Utilisation Équipement » dans le menu HMD AGRO",
      "Exploitation", TODO, HIGH, "1h", ["finance", GROOM, V1], """
En tant qu'utilisateur, je veux saisir les heures d'utilisation d'un équipement depuis le menu HMD AGRO afin de ne pas avoir à connaître l'URL du DocType.

Constat (grooming 07/08/2026): le DocType Utilisation Equipement livré par FIN-S96 n'apparaît NULLE PART dans hmd_agro/fixtures/workspace.json (0 occurrence). C'est exactement le reproche de la réunion traité par FIN-S98 (« Personnels c'est devenu où ? »), reproduit sur un écran de SAISIE QUOTIDIENNE : sans raccourci, personne ne saisira ses heures et toute la chaîne du coût mécanique restera vide.

Critères d'acceptation:
- Entrée « Utilisation Équipement » dans shortcuts + bloc correspondant dans la section « Finance & Gestion » du content.
- Fixture exportée, vérifiée après bench migrate sur une instance.
- Contrôler au passage qu'aucun autre DocType finance récent ne manque au workspace.

Créée au grooming du 07/08/2026.
""", new=True)

issue("FIN-S99 Jeu de données de démonstration réaliste", "Exploitation",
      TODO, HIGHEST, "1d", ["finance", REUNION, V1, "demo-bloquante"], """
En tant que démonstrateur, je veux que les indicateurs affichés soient crédibles pour un éleveur, sinon la démo décrédibilise l'outil.

Constat sur l'instance de démo (le code est correct, les données sont fausses):
- Les 25 animaux actifs sont dans UN SEUL lot qui reçoit la ration vache laitière (9 kg de concentré/jour chacun), veaux et génisses compris, alors que 6 vaches seulement sont en lactation, d'où L/C 0,66 (rouge), coût alimentaire 2,96 DT/L, coût complet 3,37 DT/L, IOFC négatif.
- Le lait n'est saisi que du 11 au 20 juillet alors que les rations couvrent mai à août : tout rapport compare 10 jours de lait à 31 jours de concentré.
- Deux factures lait se chevauchaient (11 au 17 et 14 au 20 juillet) : la plus ancienne a été annulée.

Critères d'acceptation:
- Allotement par lot (VL en lactation, taries, génisses, velles) avec ration adaptée par lot.
- Saisie lait continue sur la période de démonstration.
- Source des données réelles tranchée : base du site de production, base de Siwar, ou export Excel que le rapport journalier remplace.

ATTENTION: ce n'est PAS une attente externe. L'engagement a été pris côté développement en réunion (« ma3neha mouch sa3ib, n7otoulkom les données réelles li ntab3ouhom »). Aucune demande de backup n'a été adressée à un tiers pendant la réunion du 05/08.
À TRAITER AVANT TOUTE DÉMO CLIENT. Débloque FIN-S104.
Origine: réunion 05/08/2026
""")

issue("FIN-S101 Scénario de simulation facture fournisseur, médicaments et TVA",
      "Exploitation", DONE, MEDIUM, "", ["finance", REUNION], """
En tant que gérant, je veux voir tourner devant moi une facture fournisseur, une utilisation de médicaments et le traitement de la TVA (point 14 du compte-rendu : « à simuler pour la prochaine fois »).

Critères d'acceptation:
- setup_simulations() monte le scénario en une commande bench, idempotent et additif : fournisseur + facture d'aliment avec TVA 19 % déductible et entrée en stock (le CMP bouge à l'écran), facture de service avec TVA, traitement d'un animal consommant du stock de médicament avec délai d'attente lait, TVA collectée côté vente.
- scenario_demo_simulations.md : objectif métier, commande de préparation, chemin de clics exact, montants attendus, impact au Grand Livre et sur le coût du litre, questions probables du client.
- Les pièces sont datées du jour d'exécution (une écriture de stock antidatée mettrait ERPNext en repost différé) : lancer la commande le matin de la réunion.

Livraison: commit 34b4c1b
Origine: réunion 05/08/2026 (point 14)
""")

# ── Décisions / actions externes (Tasks) ─────────────────────────────────────

issue("FIN-D01 Obtenir la grille tarifaire contractuelle de la centrale", "Recettes",
      TODO, HIGH, "", ["finance", GROOM, V1, "decision-client"], """
Obtenir de la centrale le barème contractuel réel du litre afin de sortir du statut PROVISOIRE.

Ce qu'il faut: prix de base, paliers par critère (TB, TP, germes, cellules), plancher de prix, plafond de prime, période de validité, source du document.

Ce que ça débloque: FIN-S24 — le moteur est livré, une grille « Grille Centrale — provisoire » tourne avec des paliers INDICATIFS. Aujourd'hui la facture, le rapport et le contrôle de cohérence signalent tous que le prix est provisoire.
Comment l'appliquer: corriger les paliers dans l'UI, renseigner « source », passer le statut à VALIDEE. AUCUN CODE À TOUCHER.

Créée au grooming du 07/08/2026.
""", kind="Task", new=True)

issue("FIN-D02 Obtenir les salaires réels et compléter le registre Personnel",
      "Charges et main-d'oeuvre", TODO, HIGH, "", ["finance", GROOM, V1, "decision-client"], """
Obtenir de la ferme la liste réelle des salariés et leurs rémunérations afin de poster une vraie paie.

Ce qu'il faut: par salarié — rôle, type de contrat, date d'embauche, salaire brut, taux d'activité, assujettissement CNSS, atelier principal (ou répartition multi-ateliers).

Ce que ça débloque: FIN-S42 — le registre et l'écriture 640/647 par atelier sont livrés, mais le coût MO du litre reste bâti sur des montants de démonstration. Le taux de charges patronales est tranché (30 %, FIN-S82) ; les salaires ne le sont pas.

Créée au grooming du 07/08/2026.
""", kind="Task", new=True)

issue("FIN-D03 Trancher le mode de facturation du lait (la ferme facture ou import du décompte)",
      "Recettes", TODO, MEDIUM, "", ["finance", GROOM, V3, "decision-client"], """
Décider si la ferme émet la facture lait ou si elle importe le décompte de la centrale (auto-facturation).

RG-FIN-12: ne JAMAIS activer les deux, sous peine de recettes comptées deux fois.

Ce que ça détermine: activation du job mensuel de facturation lait vs mise en place de l'import du décompte (pattern import_rapport.py). Les deux chemins sont livrés (FIN-S21).

Créée au grooming du 07/08/2026.
""", kind="Task", new=True)

issue("FIN-D04 Cadrer le périmètre et les paramètres de l'atelier génisses",
      "Atelier Genisses", TODO, MEDIUM, "", ["finance", GROOM, V2, "decision-client"], """
Quatre questions ouvertes de la spec coût génisse, non bloquantes pour démarrer l'EPIC I mais nécessaires avant FIN-S114 / FIN-S115.

1. Périmètre: les mâles (veaux / taurillons engraissés) sont dans les mêmes lots — les isoler du coût génisse ou assumer un coût moyen « jeune bovin » ?
2. Frais généraux (gardien, administratif): inclure une quote-part dans le coût génisse, ou s'arrêter aux coûts directs de l'atelier ?
3. Taux de perte (mortalité + infécondité): 8 % par défaut proposé en attendant l'historique — confirmer ou corriger.
4. Forfait 2 500 DT: le remplacer à terme par le coût calculé (FIN-S116), ou le garder comme valeur comptable et n'utiliser le calculé qu'en pilotage ?

Les autres questions de la spec ont été tranchées par la transcription du 05/08 (prix du lait interne, comptes de cession, courbe d'allaitement, prix de marché, mécanique).
Créée au grooming du 07/08/2026.
""", kind="Task", new=True)

issue("FIN-D05 Vérifier le préfixe 99999 auprès de l'autorité d'identification",
      "Immobilisations", TODO, LOW, "", ["finance", GROOM, V3], """
Confirmer qu'aucune boucle officielle tunisienne réelle ne peut commencer par 99999, la bande réservée aux identifications provisoires (FIN-S81).

NON BLOQUANT (questions_samir.md v3): les boucles réelles commencent par 999 0…, la série n'atteindrait 99999… qu'après environ 10 millions de boucles. C'est une vérification technique, pas une décision client.

Créée au grooming du 07/08/2026.
""", kind="Task", new=True)

issue("FIN-D06 Confirmer d'éventuelles exonérations de charges sur les primes",
      "Charges et main-d'oeuvre", TODO, LOW, "", ["finance", GROOM, V3], """
Signaler si certaines primes doivent être exonérées de charges patronales.

Comportement actuel (FIN-S84): les primes sont traitées comme le salaire — soumises aux charges patronales pour les salariés CNSS. Une prime ajoutée sur un mois déjà posté au Grand Livre est refusée (ERR-PRIME-04) : il faut régulariser l'écriture d'abord.

POINT DE VIGILANCE, pas une question bloquante (questions_samir.md v3).
Créée au grooming du 07/08/2026.
""", kind="Task", new=True)


# ── Émission des CSV ─────────────────────────────────────────────────────────

MAX_LABELS = 5
HEADER = (["Issue Type", "Summary", "Epic Name", "Epic Link", "Status", "Resolution",
           "Priority", "Original Estimate"] + ["Labels"] * MAX_LABELS + ["Description"])


def _row_epic(name, summary, status, description):
    labels = ["finance", "epic"] + [""] * (MAX_LABELS - 2)
    return (["Epic", summary, name, "", status,
             "Done" if status == DONE else "", "Medium", ""] + labels + [description])


def _row_issue(it):
    labels = list(it["labels"])[:MAX_LABELS]
    labels += [""] * (MAX_LABELS - len(labels))
    return ([it["kind"], it["summary"], "", it["epic"], it["status"],
             "Done" if it["status"] == DONE else "", it["priority"], it["estimate"]]
            + labels + [it["description"]])


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writerow(HEADER)
        w.writerows(rows)
    print(f"{path}: {len(rows)} lignes")


def main():
    here = os.path.dirname(os.path.abspath(__file__))

    epics = [_row_epic(*e) for e in EPICS]
    issues = [_row_issue(i) for i in ISSUES]
    write(os.path.join(here, "backlog_finance.csv"), epics + issues)

    new_epic_names = {"Atelier Genisses", "Exploitation"}
    delta_epics = [_row_epic(*e) for e in EPICS if e[0] in new_epic_names]
    delta_issues = [_row_issue(i) for i in ISSUES if i["new"]]
    write(os.path.join(here, "backlog_finance_delta.csv"), delta_epics + delta_issues)

    done = sum(1 for i in ISSUES if i["status"] == DONE)
    doing = sum(1 for i in ISSUES if i["status"] == DOING)
    todo = sum(1 for i in ISSUES if i["status"] == TODO)
    print(f"{len(EPICS)} epics · {len(ISSUES)} issues "
          f"({done} Done, {doing} In Progress, {todo} To Do) "
          f"· {len(delta_issues)} nouvelles")


if __name__ == "__main__":
    main()
