# Prompteur invisible — soutenance en ligne

Petite app macOS native : une fenêtre flottante, toujours au premier plan, qui
affiche tout ce que je dois dire (les textes de `passation/07_stage/conducteur_affiche_photos.html`)
dans une seule page qui défile, avec un chronomètre. Le bandeau du haut indique
le bloc en cours de lecture et son minutage prévu. La fenêtre est
**exclue de la capture d'écran et du partage d'écran** (`NSWindow.sharingType =
.none`) : Zoom, Teams, Meet et la capture système ne la voient pas, moi si.

## Lancer

    open outils_affiche/prompteur/Prompteur.app

Ou double-clic sur `Prompteur.app` dans le Finder. Elle peut être glissée dans
`/Applications`, mais elle embarque sa copie de `prompteur.json` : la
reconstruire après un changement de texte (voir plus bas).

## Clavier

| Touche | Action |
|---|---|
| molette · trackpad · ↓ ↑ | défiler le texte |
| espace · page ↓ (⇧ espace · page ↑) | une page |
| → · entrée | sauter au bloc suivant |
| ← | bloc précédent ; début = touche début |
| + / - | taille du texte (la position de lecture est conservée) |
| T | chrono marche / arrêt |
| R | remise à zéro du chrono |
| O | opacité (3 niveaux) |
| H · échap | masquer / afficher la fenêtre |
| ⌘Q | quitter |

L'app n'a ni icône de Dock ni barre de menus (app accessoire) : c'est ce qui
lui permet de rester visible par-dessus une app en plein écran. Si la fenêtre a
été masquée avec H, relancer `open Prompteur.app` la réaffiche.

Le chrono affiche le temps écoulé et l'écart avec le début prévu du bloc
courant : vert = dans les temps, orange = plus d'une minute de retard, rouge =
plus de trois minutes. La fenêtre se déplace en la tirant n'importe où.

## Avant la soutenance : tester le partage

1. Lancer le prompteur, puis ouvrir la réunion (Zoom / Teams / Meet).
2. Partager l'écran entier et regarder l'aperçu du partage : la fenêtre du
   prompteur ne doit pas y apparaître. Vérifié le 05/09/2026 sur macOS 26.5 avec
   la capture système (`screencapture`), pas encore avec chaque logiciel de visio.
3. Garder le prompteur à un endroit qui ne cache pas ce qu'on regarde soi-même
   sur l'affiche.

Plan B si un logiciel de visio la montrait quand même : partager **la fenêtre
du PDF** de l'affiche plutôt que l'écran entier, le prompteur reste alors
naturellement hors du partage.

## Régénérer après un changement de texte

    python3 outils_affiche/build_guide_photos.py   # réécrit le HTML et prompteur.json
    outils_affiche/prompteur/build_app.sh            # recompile l'app avec le nouveau JSON

Mode répétition où la fenêtre reste capturable (pour la montrer ou la filmer) :

    outils_affiche/prompteur/Prompteur.app/Contents/MacOS/Prompteur --visible

Un autre fichier de blocs peut être passé en argument (même format JSON).
