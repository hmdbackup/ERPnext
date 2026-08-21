# Definition of Done — SCRUM-9 / 10 / 11 · 21/08/2026

Développement livré sur la branche de sprint `finance/socle-comptable`,
poussé sur `origin` (`3337aa9..7e401e7`). Trois commentaires à coller dans Jira,
un par ticket.

---

## SCRUM-9 — Rapport mensuel sur la production laitière

Commit `dda2790`.

### Critères d'acceptation

1. **Production totale, moyenne par vache lactante et par jour, effectif lactant** — fait.
   La section Production porte désormais 12 colonnes, dont `VL`, `VP`, `Moy/VL (L/j)` et
   `Moy/VP (L/j)`. Les deux dénominateurs demandés en revue reporting sont affichés côte à
   côte ; les effectifs sont reconstitués **jour par jour** depuis les événements du troupeau,
   et la ligne Total en porte la **moyenne sur la période** — pas l'effectif du dernier jour,
   qui aurait fait mentir le L/vache/jour dès le premier vêlage.
2. **Ventilation quotidienne** (commercialisé, auto-consommation, lait veau, écart) — fait,
   lue dans le Bilan Lait Journalier.
3. **Couverture de saisie affichée même complète** — fait, ligne « Couverture des Données (lait) ».
4. **Un mois incomplet ne masque aucune valeur** — fait : avertissement en tête, coloration
   éteinte sur les seuls indicateurs lait, valeurs toujours affichées.
5. **Export** — colonnes typées (Int / Float / Percent), reprises telles quelles par l'export ERPNext.

**Changement de règle à signaler.** `couverture_lait()` exige maintenant **traite ET bilan
lait** sur la journée. Un mois de traites sans bilan n'est plus annoncé complet. Sur juin 2026
la couverture réelle passe de 30/30 à **26/30** — c'est la vérité de la saisie, pas une régression.

### Tests

| module | résultat |
|---|---|
| `test_rapport_production` (nouveau, 9 groupes) | **25/25** |
| `test_rapport_performance` | **34/34** |
| `test_indicateurs_report` | **40/40** |

Cas couverts : mois complet · jour avec traite mais sans bilan (cellules **vides**, jamais 0) ·
mois sans aucune traite · mois en cours (les jours futurs n'entrent pas au dénominateur) ·
moyenne d'effectif VL/VP · couverture exigeant les deux saisies · export des scalaires.

### Reste à faire — portes humaines

- [ ] **Maquette validée par M. Samir** (DoR critère 2, toujours bloquant) — maquette produite
      (`maquettes_scrum_9_10_11.html`, commit `7e401e7`), pas encore montrée.
- [ ] **Code review** avec un collègue.
- [ ] **Test d'acceptation** avec Aymen ou M. Samir.

### Points bloquants pour la démo de lundi

1. **Le troupeau importé n'a pas d'événements de vêlage** : `effectif_on_date()` classe les
   95 vaches actives en « Gén. - Vide », donc **VL = 0** et `Moy/VL` affiche 0 sur les données
   réelles. Ce n'est pas un défaut de cette story, c'est un manque de données d'import. Soit on
   importe les dates de vêlage avant lundi, soit on annonce la colonne comme non représentative.
2. **Dénominateur de référence à trancher** : L/VL ou L/VP pour les comparaisons mensuelles.
3. **Seuil d'alerte sur l'écart** : la revue évoque ~50 L/jour ; à confirmer pour le paramétrer
   dans `HMD Configuration`.

---

## SCRUM-10 — Répartition des charges par atelier et coût du lait

Commit `6456d5e`.

### Ce qui change

Le Grand Livre était lu **sans son centre de coût** : les cinq ateliers existaient, les
écritures les portaient, et le rapport les ignorait. Le coût complet au litre en payait le
prix — il rapportait au lait des charges de culture fourragère et de génisses.

- `gl_sums_par_atelier()` ventile les charges par centre de coût **et** par poste comptable
  (601 ration, 602 santé, 615 mécanique, 64x personnel, 68x amortissements, 66x financier,
  autres).
- Nouvelle section **« Charges par Atelier »** : un atelier par ligne, plus « Non imputé —
  écriture sans atelier » affiché **même à zéro**, plus une ligne de contrôle qui rejoue la
  somme contre les Charges Totales et passe au rouge en cas d'écart.
- Nouvelle section **« Coût du Lait (détail) »** : la demande explicite de la revue — « le
  rapport doit détailler le coût du lait ligne par ligne pour rapprochement comptable ».
  Chaque poste porte son numéro de compte, tous restent affichés même à zéro pour que la forme
  du tableau ne change pas d'un mois sur l'autre.
- `charges_lait()` retient les charges du coût du litre selon un **périmètre configurable** :
  `LAIT_QUOTE_PART` (défaut), `LAIT_SEUL`, `TOUTES_CHARGES`. Le périmètre retenu est écrit dans
  le libellé du coût complet — le même nombre ne veut pas dire la même chose selon ce qu'on y
  a mis. Périmètre inconnu → `ERR-FIN-10`.
- La **clé de quote-part** des Frais Généraux est écrite à l'écran (part du Lait dans les
  charges directes des ateliers, hors Frais Généraux) : un coût de revient dont on ignore la
  clé ne se rapproche de rien.

Deux règles tenues par les tests : les écritures sans centre de coût ne sont **jamais**
réparties d'office, et le coût mécanique reste une vue analytique, **jamais additionné** au
coût complet.

### Tests

| module | résultat |
|---|---|
| `test_ventilation_atelier` (nouveau, 10 groupes) | **33/33** |
| `test_rapport_performance` | **34/34** |
| `test_finance_kpis` | **14/14** |

Cas couverts : mois vierge · classification par atelier et par poste · somme identique à
`gl_sums` · écriture annulée exclue · non-imputé visible · clé et quote-part (1000/500/300 →
clé 66,67 %, quote-part 200,01, total 1200,01) · non-imputé exclu du coût du litre ·
`ERR-FIN-10` · présence des deux sections · coût mécanique toujours exclu.

Rapprochement sur données réelles : ventilation et `gl_sums` retombent sur le même total.

### Reste à faire — portes humaines

- [ ] **Maquette validée par M. Samir** — produite, pas encore montrée.
- [ ] **Code review**.
- [ ] **Test d'acceptation**.

### À trancher

1. **Nom exact du centre de coût « frigénerie »** — « Frigorifique » est provisoire ; la
   fromagerie annoncée en revue viendra s'ajouter à la même liste.
2. **Clé de la quote-part** : prorata des charges directes (implémenté) ou prorata des litres ?
3. **Périmètre de référence** du coût du litre communiqué officiellement.
4. **Saisie d'une charge répartie en % entre ateliers** (demande de la revue, total 100 %) :
   ERPNext le fait nativement via `Cost Center Allocation`. Non activé — hors périmètre de
   cette story, à ouvrir en story séparée si le métier confirme.

---

## SCRUM-11 — Rapport des interventions mécaniques

Commit `ff90ac4`, au-dessus de `366e1b6` et `3337aa9` déjà livrés.

### Ce qui change

- Le nombre d'interventions et d'équipements concernés devient **deux colonnes** (`Nb
  Interventions`, `Nb Équipements`) au lieu d'une phrase dans le libellé du total : ce qui
  s'exporte se compare d'un mois à l'autre.
- Un **mois sans intervention** rend désormais une ligne TOTAL à zéro en plus de la phrase —
  sans quoi l'export d'un mois vide n'a pas la même forme que celui d'un mois plein.
- Quand la **période demandée dépasse aujourd'hui**, le rapport annonce la date d'arrêt réelle
  au lieu de laisser croire que le mois est clos.
- Correction de libellé : « chaque dirham d'entretien » → « chaque **dinar** d'entretien ».
  Le libellé est affiché à l'écran, il sera lu pendant la démo.

Le bloc préventif respecte déjà les filtres Équipement et Atelier (`3337aa9`), et la section
Rapprochement compare la somme des interventions saisies au compte 615 du Grand Livre.

### Tests

| module | résultat |
|---|---|
| `test_rapport_interventions` | **41/41** |
| `test_maintenance` | **42/42** |

Cas couverts : 11 colonnes et leurs types · compteurs numériques sur la ligne TOTAL et `None`
sur les lignes de détail · mois vide affichant un zéro · période en cours annoncée · filtres
Équipement et Atelier sur les trois sections · rapprochement au Grand Livre.

### Reste à faire — portes humaines

- [ ] **Maquette validée par M. Samir** — produite, pas encore montrée.
- [ ] **Code review**.
- [ ] **Test d'acceptation**.

### À trancher

1. **Fenêtre du préventif** : 30 jours, ou un horizon plus long pour anticiper les pièces ?
2. **Déclencheurs d'entretien** : jours / heures de marche / fréquence — lesquels sont
   réellement suivis, équipement par équipement ?
3. **Statuts d'équipement** « prêt à partir / à vérifier / en panne » : à confirmer comme liste
   officielle avant de l'ajouter à la fiche équipement.
4. **Coût des pièces** distinct de la main-d'œuvre ?

---

## Tests de non-régression — les 39 modules

Suite complète relancée sur le site `hmd.agro` (données réelles, sauvegarde
`20260821_011415-hmd_agro-database.sql.gz` prise avant travaux).

**Aucune régression imputable à ces trois stories.** Les échecs restants sont antérieurs,
mesurés à l'identique sur la base sans ces modifications :

| module | échecs | statut |
|---|---|---|
| `test_production_lot_report` | 8 | antérieur |
| `test_effectif_report` | 5 | antérieur |
| `test_velage_prevue_config` | 2 | antérieur |
| `test_aliment_correction` | 1 | antérieur |
| `test_allotement_report` | 1 | antérieur |
| `test_feed_distribution` | 1 | antérieur |

`test_traite_config` a montré 1 échec dans la passe complète et repasse **21/21** relancé
seul : pollution d'état entre modules, pas une régression.

Une régression **a bien été introduite puis corrigée** au cours du travail :
`test_indicateurs_report` est tombé à 9 échecs quand `couverture_lait()` est devenue plus
stricte, parce que son jeu d'essai ne semait que des traites. Les bilans lait sont désormais
semés avec elles — **40/40**.

## Definition of Done — synthèse

| # | Critère | État |
|---|---|---|
| 1 | Chaque fonctionnalité de la description fonctionne | **fait** — vérifié écran par écran sur juin 2026 |
| 2 | Critères d'acceptation atteints | **fait** — détaillés ci-dessus, un par un |
| 3 | Toutes les sous-tâches terminées | **fait** côté développement ; la sous-tâche 1 de SCRUM-9 (« soumettre le rendu à M. Samir ») attend la réunion |
| 4 | Code review avec un collègue | **à faire** — porte humaine, diff prêt sur `finance/socle-comptable` |
| 5 | Tests unitaires écrits et exécutés | **fait** — 2 modules créés, 3 étendus, tous verts |
| 6 | Tests de non-régression passés | **fait** — 39 modules relancés, aucune régression nouvelle |
| 7 | Test d'acceptation avec le lead ou M. Samir | **à faire** — porte humaine |
| 8 | Merge sur la branche du sprint | **fait** — `finance/socle-comptable` |
| 9 | Push / sauvegarde sur le dépôt distant | **fait** — `3337aa9..7e401e7` poussé sur `origin` |

Aucune fusion vers `main` n'a été faite : elle se demande à chaque fois.
