# 📓 Journal des questions — Superviseur (HMD AGRO)

Petite application autonome (un seul fichier HTML) pour préparer et garder une trace
de tes réunions avec ton superviseur : questions, réponses, dates, recherche.

## Ouvrir l'app
Double-clique sur **`index.html`** (s'ouvre dans ton navigateur). Aucune installation.

## Ce que tu peux faire
- **Noter les réponses** : un champ « Réponse » sous chaque question. Tout est enregistré
  automatiquement (indicateur « ✓ Enregistré » en haut à droite).
- **Nouvelle réunion** : bouton « ＋ Nouvelle réunion » → crée une fiche datée. Les anciennes
  réunions restent conservées.
- **Ajouter une question** : bouton « ＋ Ajouter une question » (choisis le thème + écris).
- **Modifier une question** : clique directement sur le texte (il est éditable).
- **★ Prioritaire / ⚑ À suivre** : repères visuels pour t'organiser.
- **Calendrier** : les jours avec une réunion ont un point doré ; clique un jour pour filtrer.
- **Barre de recherche** : cherche un mot dans **toutes** les questions ET réponses, de toutes
  les réunions passées. Clique un résultat pour ouvrir la réunion concernée.
- **Imprimer / PDF** : bouton dédié (ou Ctrl/Cmd + P).

## Sauvegarde (important)
Les données vivent dans le navigateur (localStorage). Pour ne rien perdre (changement
d'ordinateur, vidage du cache…), clique **« ⤓ Exporter »** de temps en temps : ça télécharge
un fichier `questions_superviseur_AAAA-MM-JJ.json`. **Range-le dans le dossier `archives/`.**
Pour le récupérer : bouton **« ⤒ Importer »**.

## Structure du dossier
```
questions_superviseur/
├── index.html      ← l'application (à ouvrir)
├── README.md       ← ce fichier
└── archives/       ← y déposer les exports JSON (sauvegardes datées)
```
