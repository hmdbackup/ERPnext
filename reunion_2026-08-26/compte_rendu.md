# Compte rendu — présentation des maquettes à M. Samir, 26/08/2026

> Source : `transcription.md` (traduite du français/derja).
> Deux écrans sur trois ont été passés en revue. **SCRUM-9 n'a pas été présenté :
> l'US a été annulée en fin de séance**, voir §4.

## En une phrase

Les deux écrans validés le 24/08 sont confirmés dans leur forme, mais **la
décision du 24/08 sur les frais généraux est remplacée** : plus de clé unique,
plus de couple « clé dépenses / clé recettes », plus d'écran d'arbitrage — une
répartition libre en pourcentages par atelier, saisie sur la charge, dont le
total doit faire 100 %. La troisième US, production laitière, est **annulée**.

---

## 1. Frais généraux — la décision du 24/08 est remplacée

**Ce que M. Samir a dit.** « Tu te compliques la tâche. » Le modèle à deux clés
(dépenses 61,98 % / recettes 90,00 %) et l'écran d'arbitrage mensuel sont
écartés. À la place :

- sur chaque charge, une **liste de lignes « atelier + pourcentage »** ;
- un bouton **« ajouter un atelier »**, autant de lignes que nécessaire ;
- **la sauvegarde est bloquée tant que le total ne fait pas 100 %** ;
- ses exemples : un gardien d'étable → 100 % Lait ; un gardien de moutons →
  100 % Brebis ; un gardien parc + fromagerie → 50 / 50.

**La fréquence, qui change tout.** La clé n'est pas rearbitrée chaque mois.
Elle se fixe **une fois** — son exemple : au 31 décembre, à la clôture, on sort
le prorata des recettes de l'année — puis elle s'applique à chaque saisie.
« Mais on le fera une seule fois. »

**Le volume.** « On parle peut-être d'un grand maximum de 5 à 10 factures. »
Donc : ne pas surdimensionner. Pas de moteur de règles, pas d'écran de
clôture — un champ répétable sur la charge.

**Qui arbitre.** Le comptable, à la saisie : « ça sera toujours par rapport à ce
que le comptable va entrer ». **La question ouverte de la présentation est
tranchée** : variante B, sans écran d'arbitrage.

**Ce que ça change dans le code.** `charges_lait()` calcule aujourd'hui une clé
unique — la part du Lait dans les charges directes hors frais généraux — et
l'applique à tout le bloc Frais Généraux
(`hmd_agro/hmd_agro/utils/finance_kpis.py:215-225`). Cette clé calculée
disparaît : la quote-part devient la **somme des pourcentages portés par chaque
charge**. C'est un changement de modèle de données, pas un ajustement de
formule — il faut un champ enfant (atelier, %) sur la ligne de charge.

**Ce que ça change dans les chiffres.** Les 1,562 DT/L, les 7 583,89 DT de
quote-part et l'écart de 32,7 millimes / L reposaient tous sur le couple
61,98 / 90,00. **Ils ne valent plus** — le nouveau montant dépendra des
pourcentages saisis. À ne plus citer tant que la répartition n'est pas saisie.

**Deux ateliers qui n'existent pas encore.** Il cite **Brebis** et
**Fromagerie**, en plus des cinq actuels. Les ateliers sont lus depuis les
centres de coût du Grand Livre (`finance_kpis.py:116`, `gl_sums_par_atelier`),
donc c'est de la configuration, pas du code — mais la maquette doit cesser de
présenter cinq ateliers comme une liste fermée.

---

## 2. Périodes et dates

| Point | Décision | État |
|---|---|---|
| Jour | la journée de la date choisie | ✅ déjà fait |
| Semaine | la semaine ISO qui contient la date | ✅ déjà fait |
| Mois | **le mois calendaire** — le 15 juillet donne juillet entier | ✅ déjà fait |
| Année | **à ajouter** — « l'année 2026, *Year to Date* » | ❌ n'existe pas |
| M-1 | la période précédente de même granularité | ✅ validé tel quel |
| Non imputé | un tiret, jamais un 0 | ✅ validé tel quel |

**⚠️ Une réponse fausse a été donnée en séance.** À sa question « le 15 juillet,
ça donne juillet entier ou du 15 juin au 15 juillet ? », j'ai répondu « du
15 juin au 15 juillet ». **C'est faux** : `period_bounds()` renvoie déjà le mois
calendaire (`hmd_agro/hmd_agro/report/rapport_performance/rapport_performance.py:99`),
et la semaine ISO, et la quinzaine 1-15 / 16-fin. Il a corrigé lui-même vers le
bon comportement, donc la décision est la bonne — mais il croit avoir demandé
un changement qui n'a pas lieu d'être. **À rectifier auprès de lui**, sinon il
attendra une correction qui ne viendra pas.

**La période « Année ».** Les rapports offrent aujourd'hui
`Jour / Semaine / Quinzaine / Mois`
(`rapport_performance.js:13`, `rapport_interventions.js:14`). Il faut y ajouter
Année. Attention : il dit « *Year to Date* », donc **du 1er janvier à la date
choisie**, et non l'année civile complète — ce qui rend le comparatif A-1 égal à
la même période de l'année précédente. À confirmer d'un mot avec lui.

À noter aussi : le rapport périodique (SCRUM-9) n'offre que
`Jour / Hebdomadaire` (`rapport_periodique.js:95`) — il n'a ni Mois ni Année.
Sans objet depuis l'annulation de l'US (§4) : il reste tel quel.

---

## 3. Parc et interventions

**Validé sans réserve** : les trois états (Prêt / En attente de maintenance / En
panne), la dernière intervention, la prochaine, les heures, le type,
l'intervenant, pièces / main-d'œuvre / coût, et la séparation réalisées /
à venir.

**Trois demandes nouvelles**, toutes justifiées par la même phrase — « lui, ce
n'est pas un informaticien » :

1. **Dupliquer une intervention.** Refaire une vidange = ouvrir l'ancienne, la
   dupliquer, changer la date, vérifier, enregistrer. Évite de ressaisir la
   quantité d'huile et les pièces.
2. **Planifier une intervention** : une intervention dont la date est dans le
   futur et qui **reste ouverte**.
3. **Supprimer une intervention** en cas d'erreur de saisie.

**Une règle** : une intervention terminée ne se modifie plus. On la duplique,
on ne la corrige pas.

**Un point d'affichage à corriger dans la maquette.** Il a buté sur les deux
dernières colonnes : « c'est quoi ces deux qui sont à la fin ? ». Ce sont
**Nb Interventions** et **Nb Équipements**
(`rapport_interventions.py:79-81`) — les vrais libellés sont clairs, c'est la
maquette qui les avait abrégés en « Nb I » / « Nb É ». Rien à changer dans le
code, tout à changer dans la maquette.

**Rapprochement — sa définition.** « Il y a une différence entre ce qu'on a
dépensé et ce dont on n'a pas exactement les traces. » C'est bien la lecture
retenue : l'écart est l'information, pas l'erreur.

---

## 4. Ce qui n'a pas été traité

- **SCRUM-9 — production laitière : ANNULÉE.** L'écran n'a pas été
  présenté. La transcription traduite avait perdu la phrase, dans le segment
  abîmé de la fin ; l'audio brut la contient : « Hakka ma3na n'annule la User
  Story hedhi » (« donc on annule cette User Story »), précédée d'un fragment
  coupé qui ressemble à « c'est annulé, c'est ça ? ». Confirmé après la
  réunion : c'est bien SCRUM-9, en entier. Le calcul des écarts de production
  n'a pas de valeur de contrôle — l'erreur cumulée des lectures manuelles
  fausse les chiffres. Rien à construire, ni écran ni alerte.
  Deux questions survivent parce qu'elles n'appartenaient pas à l'US : lequel
  des deux comptages fait référence (c'est le dénominateur du coût du litre de
  l'écran 1), et le bloquant des vêlages non saisis (VL = 0, IOFC par vache
  lactante vide).
- **L'écran d'arbitrage** a été montré puis écarté. Il ne sera pas construit.
- **Les recettes.** Il a lancé « après on fera la même chose mais pour les
  recettes » — noté, pas creusé, hors périmètre du sprint.

---

## 5. Ce que je fais maintenant

1. ✅ Fait le 26/08 : la maquette des frais généraux refaite — lignes
   atelier + %, bouton « ajouter un atelier », total 100 % bloquant — et la
   saisie montrée geste par geste, telle que le comptable la fera dans
   ERPNext (`maquettes_2026-08-26.pdf`, vues « gestes 1 à 4 » et « 5 à 7 »).
   Même traitement pour le parc : la saisie des interventions en huit gestes
   — le chef de parc déclare la panne puis complète la fiche, le comptable
   rattache la facture du réparateur, Dupliquer / Planifier / Supprimer, les
   heures du tractoriste. Aujourd'hui aucun écran de saisie n'existe : les
   fiches naissent en Python (`enregistrer_intervention()`), ce qui explique
   qu'on ne « voyait » pas comment l'utilisateur ferait. Reste à trancher
   avec le comptable qui écrit au 615 — la facture rattachée à la fiche
   (la maquette) ou la fiche elle-même — pas les deux.
2. Retirer de la présentation les deux clés 61,98 / 90,00, l'écran
   d'arbitrage, et les chiffres qui en découlent.
3. Rectifier auprès de M. Samir la réponse sur le mois calendaire.
4. Backlog : période Année (Year to Date) ; dupliquer / planifier / supprimer
   une intervention ; libellés Nb Interventions et Nb Équipements en clair.
5. ✅ Fait le 26/08 : SCRUM-9 fermé dans Jira — *Terminé(e)* faute de statut
   « Annulé » dans le workflow, étiquette `annulee`, commentaire d'annulation
   qui renvoie ici ; l'écran 3 des maquettes est passé en « annulée ».
