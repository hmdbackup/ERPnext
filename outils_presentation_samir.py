"""Assemble la présentation du lundi pour M. Samir, au format Excalidraw.

Pourquoi ce script existe
──────────────────────────
Deux scènes avaient été construites séparément, et aucune ne se suffit :

  • `maquettes_scrum_9_10_11.excalidraw` montre les trois écrans construits,
    mais chacun se termine par un pense-bête « À trancher avec M. Samir »
    posé à plat — la forme de question à laquelle il n'a jamais répondu.
  • `planches_arbitrage_samir.excalidraw` reprend ces mêmes questions en deux
    versions désignables, mais sans jamais montrer l'écran complet auquel
    elles se rapportent.

Présentées l'une après l'autre, elles se répètent sans se répondre. Assemblées
dans le bon ordre, elles racontent une seule chose : voilà ce qui est fait,
voilà ce qui manque, voilà ce qu'il me faut de toi.

Ce que l'assemblage change au contenu d'origine
────────────────────────────────────────────────
Trois retouches, et rien d'autre — les deux scènes sources restent maîtresses
de leur propre contenu, et se regénèrent sans toucher à ce fichier :

  1. Les titres sont renommés en langage métier. « SCRUM-9 » ne dit rien à
     personne autour de la table ; « Écran 1 » se retient.
  2. L'ordre des planches est inversé (lait, charges, parc) pour suivre celui
     des écrans. Une décision se présente juste après l'écran qu'elle décide.
  3. Le pense-bête « À trancher avec M. Samir » de chaque écran est remplacé
     par un renvoi vers les décisions correspondantes. Le laisser tel quel
     ferait lire les questions à plat avant qu'on arrive aux planches — c'est
     exactement ce qu'on cherche à éviter.

Les identifiants des deux scènes se recoupent (57 collisions) : ils sont
renumérotés à la volée, sinon Excalidraw n'affiche qu'un élément sur deux.
"""
import json
from pathlib import Path

RACINE = Path("/Users/momoslim/Desktop/hmd_agro-main")
ECRANS = RACINE / "maquettes_scrum_9_10_11.excalidraw"
PLANCHES = RACINE / "planches_arbitrage_samir.excalidraw"
SORTIE = RACINE / "presentation_samir.excalidraw"

ENCRE = "#1e1e1e"
GRIS = "#5c5f66"
VERT = "#2f9e44"
ORANGE = "#e8590c"
JAUNE = "#fff3bf"
BANDE = "#f1f3f5"

MANUSCRITE, MONO = 1, 3
LARGEUR_CAR = 0.60
LARGEUR_MAN = 0.62
INTERLIGNE = 1.25

LARGE = 1560
AXE = LARGE / 2          # tous les blocs sont centrés sur le même axe
RESPIRE = 150            # écart entre deux blocs : la couture doit se voir

elements = []
_n = [0]


def _base(x, y, w, h, **kw):
    _n[0] += 1
    e = {
        "id": f"pr{_n[0]}", "x": x, "y": y, "width": w, "height": h, "angle": 0,
        "strokeColor": ENCRE, "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
        "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
        "roundness": None, "seed": 9000 + _n[0], "version": 1,
        "versionNonce": 9500 + _n[0], "isDeleted": False, "boundElements": None,
        "updated": 1, "link": None, "locked": False,
    }
    e.update(kw)
    return e


def rect(x, y, w, h, fond="transparent", trait=ENCRE, epaisseur=1, arrondi=True):
    e = _base(x, y, w, h, type="rectangle", backgroundColor=fond,
              strokeColor=trait, strokeWidth=epaisseur)
    if arrondi:
        e["roundness"] = {"type": 3}
    elements.append(e)
    return e


def texte(x, y, contenu, taille=16, couleur=ENCRE, police=MANUSCRITE):
    lignes = contenu.split("\n")
    facteur = LARGEUR_CAR if police == MONO else LARGEUR_MAN
    e = _base(x, y,
              max(len(l) for l in lignes) * taille * facteur,
              len(lignes) * taille * INTERLIGNE,
              type="text", strokeColor=couleur, text=contenu, fontSize=taille,
              fontFamily=police, textAlign="left", verticalAlign="top",
              containerId=None, originalText=contenu, lineHeight=INTERLIGNE,
              autoResize=True)
    elements.append(e)
    return e


def _mesure(contenu, taille):
    """Dimensions qu'Excalidraw donnera à ce texte. Sert à recadrer un cadre
    dont on vient de remplacer le contenu."""
    lignes = contenu.split("\n")
    return (max(len(l) for l in lignes) * taille * LARGEUR_MAN,
            len(lignes) * taille * INTERLIGNE)


# ── Lecture et découpe des deux scènes sources ───────────────────────────────

def _charge(chemin):
    return json.loads(chemin.read_text())["elements"]


def _decoupe(els, taille_titre, prefixe):
    """Rend les blocs délimités par les titres de la scène, dans l'ordre.

    Un bloc va de son titre au titre suivant. La marge haute évite de laisser
    derrière un élément posé quelques pixels au-dessus du titre.
    """
    bornes = sorted(e["y"] for e in els
                    if e["type"] == "text" and e.get("fontSize") == taille_titre
                    and e["text"].startswith(prefixe))
    assert len(bornes) == 3, f"{prefixe} : {len(bornes)} titres trouvés, 3 attendus"
    bornes = [b - 40 for b in bornes] + [float("inf")]
    return [[e for e in els if bornes[i] <= e["y"] < bornes[i + 1]]
            for i in range(3)]


def _pose(bloc, y_cible):
    """Recopie un bloc à l'ordonnée voulue, centré sur l'axe, ids renumérotés.

    Les deux scènes ont été générées par des scripts qui numérotent leurs
    éléments de la même façon : sans renumérotation, Excalidraw ne garde qu'un
    élément par identifiant et la moitié de la planche disparaît.
    """
    haut = min(e["y"] for e in bloc)
    gauche = min(e["x"] for e in bloc)
    largeur = max(e["x"] + e["width"] for e in bloc) - gauche
    dy = y_cible - haut
    dx = AXE - largeur / 2 - gauche
    for e in bloc:
        _n[0] += 1
        copie = dict(e, id=f"pr{_n[0]}", x=e["x"] + dx, y=e["y"] + dy)
        elements.append(copie)
    return max(e["y"] + e["height"] for e in elements[-len(bloc):])


def _renomme(bloc, taille, ancien_prefixe, nouveau):
    """Remplace le titre d'un bloc. Les libellés d'origine sont des clés de
    ticket : ils servent au dépôt, pas à la personne assise en face."""
    for e in bloc:
        if e["type"] == "text" and e.get("fontSize") == taille \
                and e["text"].startswith(ancien_prefixe):
            e["text"] = e["originalText"] = nouveau
            e["width"], e["height"] = _mesure(nouveau, taille)
            return
    raise AssertionError(f"titre « {ancien_prefixe}… » introuvable")


def _renvoi(bloc, corps):
    """Remplace le pense-bête « À trancher avec M. Samir » par un renvoi.

    Ses puces sont les questions posées à plat, celles auxquelles il n'a jamais
    répondu. Les laisser à l'écran, c'est l'inviter à y répondre à plat avant
    même qu'on arrive aux planches qui les rendent désignables.
    """
    titre = next(e for e in bloc if e["type"] == "text"
                 and e["text"] == "À trancher avec M. Samir")
    titre["text"] = titre["originalText"] = "Ce qui reste à décider"
    titre["width"], titre["height"] = _mesure(titre["text"], titre["fontSize"])

    puces = min((e for e in bloc if e["type"] == "text"
                 and e["y"] > titre["y"] and e["x"] == titre["x"]),
                key=lambda e: e["y"])
    puces["text"] = puces["originalText"] = corps
    puces["width"], puces["height"] = _mesure(corps, puces["fontSize"])

    # Le pense-bête se reconnaît à son fond jaune, pas à sa position : chercher
    # « le plus petit rectangle au-dessus du titre » attrapait la barre de
    # chemin, qui court sur toute la largeur, et l'étirait sur tout l'écran.
    cadre = next(e for e in bloc if e["type"] == "rectangle"
                 and e["backgroundColor"] == JAUNE
                 and e["y"] <= titre["y"]
                 and e["y"] + e["height"] >= titre["y"] + titre["height"])

    # Le cadre de l'écran garde la même retombée sous le pense-bête qu'avant,
    # sinon rétrécir celui-ci laisse un fond de fenêtre vide.
    fenetre = max((e for e in bloc if e["type"] == "rectangle"
                   and e["backgroundColor"] == "transparent"
                   and e["width"] > cadre["width"]),
                  key=lambda e: e["width"] * e["height"])
    retombee = (fenetre["y"] + fenetre["height"]) - (cadre["y"] + cadre["height"])

    cadre["height"] = puces["y"] + puces["height"] - cadre["y"] + 18
    fenetre["height"] = cadre["y"] + cadre["height"] + retombee - fenetre["y"]


# ── Planches ajoutées par la présentation elle-même ──────────────────────────

def bandeau(y, numero, libelle, detail):
    """Une couture entre deux parties. Neutre de couleur : le vert, l'orange et
    le rouge sont déjà pris par le code de provenance des planches."""
    rect(0, y, LARGE, 74, fond=BANDE, trait=BANDE)
    texte(28, y + 16, f"{numero}   {libelle}", taille=24, couleur=ENCRE)
    texte(28, y + 50, detail, taille=14, couleur=GRIS)
    return y + 74


def carte_texte(y, titre, corps, sommaire=None, note=None, trait=ENCRE):
    """Un panneau de texte : titre, corps, sommaire calé, ligne détachée.

    Le sommaire passe en chasse fixe : ses colonnes sont calées à l'espace, et
    la police manuscrite étant proportionnelle, elles ne caleraient rien.
    """
    dedans = 30
    h_corps = _mesure(corps, 16)[1]
    h = dedans + 26 * INTERLIGNE + 16 + h_corps + dedans
    if sommaire:
        h += 22 + len(sommaire.split("\n")) * 15 * INTERLIGNE
    if note:
        h += 20 + _mesure(note, 15)[1]
    rect(0, y, LARGE, h, trait=trait)
    yy = y + dedans
    texte(dedans, yy, titre, taille=26, couleur=trait)
    yy += 26 * INTERLIGNE + 16
    texte(dedans, yy, corps, taille=16)
    yy += h_corps
    if sommaire:
        texte(dedans + 40, yy + 22, sommaire, taille=15, police=MONO)
        yy += 22 + len(sommaire.split("\n")) * 15 * INTERLIGNE
    if note:
        texte(dedans, yy + 20, note, taille=15, couleur=GRIS)
    return y + h


# ── Montage ──────────────────────────────────────────────────────────────────

ecrans = _decoupe(_charge(ECRANS), 22, "SCRUM-")
# Les planches sont générées dans l'ordre parc → charges → lait ; la
# présentation les suit dans l'ordre des écrans, donc à l'envers.
planches = _decoupe(_charge(PLANCHES), 24, "Planche ")[::-1]

_renomme(ecrans[0], 22, "SCRUM-9", "Écran 1 — La production laitière, jour par jour")
_renomme(ecrans[1], 22, "SCRUM-10", "Écran 2 — Les charges par atelier et le coût du litre")
_renomme(ecrans[2], 22, "SCRUM-11", "Écran 3 — Le parc et les interventions")

_renvoi(ecrans[0], "Trois choix, en partie 2 :\n"
                   "① quelle source fait foi\n"
                   "② à partir de quel écart on t'alerte\n"
                   "③ TB/TP : afficher ou reporter")
_renvoi(ecrans[1], "Deux choix, en partie 2 :\n"
                   "① la clé de quote-part\n"
                   "② les charges sans atelier")
_renvoi(ecrans[2], "Trois choix, en partie 2 :\n"
                   "① l'état d'un équipement\n"
                   "② la fenêtre du préventif\n"
                   "③ pièces et main-d'œuvre séparées ?")

_renomme(planches[0], 24, "Planche ", "Décisions sur l'écran 1 — La production laitière")
_renomme(planches[1], 24, "Planche ", "Décisions sur l'écran 2 — Les charges et le coût du litre")
_renomme(planches[2], 24, "Planche ", "Décisions sur l'écran 3 — Le parc et les interventions")

Y = carte_texte(
    0,
    "Validation des maquettes — lundi 24 août 2026",
    "Ce que je te montre : trois écrans, déjà construits, qui lisent les données de la ferme.\n"
    "Ce que je te demande : huit choix que je ne peux pas faire à ta place.\n"
    "\n"
    "Chaque choix est posé en deux versions, A et B, côte à côte, avec le chiffre que chacune\n"
    "produit. Tu pointes, je note dans le cadre jaune. La planche annotée est le compte rendu :\n"
    "il n'y a rien à rédiger après.",
    sommaire="Écran 1  —  La production laitière, jour par jour              3 choix\n"
             "Écran 2  —  Les charges par atelier et le coût du litre        2 choix\n"
             "Écran 3  —  Le parc et les interventions                       3 choix",
    note="Le cadre marqué PAR DÉFAUT est ce que le système fait déjà. "
         "Si personne ne tranche, c'est ce qui restera.")

Y = bandeau(Y + RESPIRE, "Partie 1", "Ce qui est déjà construit",
            "Trois écrans. Ce sont des maquettes : la disposition et les colonnes sont "
            "arrêtées, les chiffres illustrent.")
for bloc in ecrans:
    Y = _pose(bloc, Y + RESPIRE)

Y = bandeau(Y + RESPIRE, "Partie 2", "Ce que je ne peux pas décider seul",
            "Huit décisions, chacune en deux versions avec son chiffre. "
            "Elles suivent l'ordre des écrans.")
for bloc in planches:
    Y = _pose(bloc, Y + RESPIRE)

Y = bandeau(Y + RESPIRE, "Partie 3", "Ce dont j'ai besoin pour continuer",
            "Les écrans sont prêts ; ce sont les données qui manquent.")

Y = carte_texte(
    Y + RESPIRE,
    "Ce qu'il me faut de la ferme pour que ces écrans disent vrai",
    "Les vêlages ne sont pas dans le système. Tant qu'ils n'y sont pas, VL = 0 : « litres par\n"
    "vache lactante » ne peut pas s'afficher, et le coût du litre non plus.\n"
    "\n"
    "TB et TP : 0 jour renseigné sur 30 en juin. La colonne existe, elle reste vide.\n"
    "\n"
    "Bilan lait des 27, 28, 29 et 30 juin : les vaches ont été traites, aucun bilan n'a été\n"
    "rempli. 5 814 litres ne sont dans aucun bilan.\n"
    "\n"
    "Comptabilité de juin : 340 DT enregistrés dans le système. Un coût du litre crédible\n"
    "demande la totalité des écritures.\n"
    "\n"
    "Le parc : un seul équipement est saisi. Les six lignes de l'écran 3 sont un exemple ;\n"
    "les trois interventions du bas, elles, sont réelles.",
    trait=ORANGE)

Y = carte_texte(
    Y + RESPIRE,
    "En sortant d'ici",
    "Huit réponses notées dans les cadres jaunes — c'est le compte rendu, rien à rédiger après.\n"
    "\n"
    "Ce qui est tranché part en développement cette semaine.\n"
    "Ce qui reste ouvert reste sur la version marquée PAR DÉFAUT, et je le redemande.\n"
    "\n"
    "Ensuite : la démonstration du système en vrai, partie Parc comprise, dès que les données\n"
    "ci-dessus sont là.",
    trait=VERT)

SORTIE.write_text(json.dumps({
    "type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
    "elements": elements, "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
    "files": {},
}, ensure_ascii=False, indent=1))

print(f"{len(elements)} éléments · hauteur {Y:.0f} px — {SORTIE}")
