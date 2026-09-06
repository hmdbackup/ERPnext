# Supports de démo — module finance

Le deck client et la vidéo ne sont pas des fichiers à retoucher à la main :
ils se **regénèrent** à partir des sources de ce dossier.

```
build_presentation.py   le deck : slides + narration (source unique)
build_video.sh          les vidéos, à partir du deck + de la narration
captures/               les captures d'écran de l'application
narration.json          la narration exportée (produite par build_presentation.py)
```

Produits, à la racine du dépôt / dans `~/Downloads` :

| Fichier | Quoi |
|---|---|
| `../presentation_finance.html` | deck autonome, 15 slides, images embarquées (1,2 Mo) |
| `~/Downloads/demo_finance_hmd.mp4` | vidéo narrée, 1920×1080, ~10 min |
| `~/Downloads/demo_finance_hmd_muette.mp4` | mêmes slides sans voix, 8 s chacune |

## Régénérer

```bash
python3 demo_finance/build_presentation.py     # deck + narration.json
./demo_finance/build_video.sh                  # les deux vidéos
```

`build_video.sh` rend chaque slide en 1920×1080 avec Chrome headless
(`?s=N&clean=1` ouvre une slide sans le chrome de navigation), lit la
narration avec la synthèse vocale du système, puis assemble.

Variables utiles :

```bash
VOIX="Amélie" ./demo_finance/build_video.sh    # autre voix (défaut : Thomas)
SORTIE=/chemin ./demo_finance/build_video.sh   # autre dossier de sortie
```

⚠️ **Le choix de la voix compte.** Toutes les voix françaises de macOS ne se
valent pas : les voix compactes (Eddy, Sandy, Jacques) articulent mal les
chiffres et les mots techniques. `Thomas` est la meilleure des voix installées
— vérifié en transcrivant le rendu et en comparant au texte source. Si vous
changez de voix, refaites ce contrôle plutôt que de vous fier au nom.

Les versions précédentes des vidéos sont conservées en `*_v1.mp4` et ne sont
jamais écrasées par une reprise.

## Modifier le contenu

Tout est dans `build_presentation.py` :

- `SLIDES` — le HTML de chaque slide. `{{IMG:nom}}` embarque `captures/nom.jpg`.
- `NOTES` — ce qui est **dit** sur chaque slide. Sert à la fois aux notes du
  présentateur (touche `N` dans le deck) et à la piste audio de la vidéo.
  Écrites pour être lues à voix haute : nombres en toutes lettres, phrases
  courtes.

Les deux listes doivent avoir la même longueur — le script refuse de
construire sinon.

## Refaire les captures

Les captures viennent du site de démonstration, après
`setup.finance.seed_demo_finance.run`. Elles sont rognées de leurs marges
blanches (chaque pixel gagné compte à la projection). Une capture doit montrer
un écran **réel** de l'application : si les chiffres du deck ne correspondent
plus à ceux du site, refaites la capture plutôt que de laisser un écran périmé.
