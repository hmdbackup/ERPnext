"""Génère les planches d'arbitrage pour M. Samir, au format Excalidraw.

Pourquoi ces planches existent
───────────────────────────────
Les questions posées à plat (« quelle clé de répartition ? », « quel seuil
d'alerte ? ») sont restées sans réponse : le métier ne voit ni ce qu'on lui
demande, ni pourquoi ça compte. Une question à laquelle on DÉSIGNE une réponse
est infiniment plus facile qu'une question à laquelle on doit en FORMULER une.

Chaque arbitrage est donc rendu sous la même forme : la même maquette en deux
versions, côte à côte, avec le chiffre que chacune produit. Il pointe, on note
dans le cadre jaune. La planche annotée est le compte rendu — il n'y a rien à
rédiger après.

Provenance des chiffres — la règle qui protège la confiance
─────────────────────────────────────────────────────────────
Un chiffre faux fait douter de tous les autres. Chaque planche porte donc une
pastille qui dit d'où viennent ses nombres :

  • Planche 3 — 100 % réels, juin 2026, extraits du site hmd.agro.
  • Planche 1 — parc d'exemple : un seul équipement est saisi dans le système.
    Les trois interventions affichées, elles, sont réelles.
  • Planche 2 — chiffres reconstitués : la comptabilité de juin ne contient que
    340 DT. Les proportions sont plausibles, les montants ne sont pas les siens.

Les tableaux sont composés en police à chasse fixe (fontFamily 3) : Excalidraw
n'a pas de contrôle « tableau », c'est la seule façon d'aligner des colonnes.
"""
import json
from pathlib import Path

SORTIE = Path("/Users/momoslim/Desktop/hmd_agro-main/planches_arbitrage_samir.excalidraw")

ENCRE = "#1e1e1e"
GRIS = "#5c5f66"
VERT = "#2f9e44"
ORANGE = "#e8590c"
ROUGE = "#c92a2a"
JAUNE = "#fff3bf"
BLEU_PALE = "#e7f5ff"
VERT_PALE = "#ebfbee"
ORANGE_PALE = "#fff4e6"
ROUGE_PALE = "#fff5f5"

MANUSCRITE, MONO = 1, 3
LARGEUR_CAR = 0.60      # chasse fixe, en fraction de la taille de police
LARGEUR_MAN = 0.62      # manuscrite, mesurée sur le rendu réel
INTERLIGNE = 1.25

elements = []
_n = [0]


def _base(x, y, w, h, **kw):
    _n[0] += 1
    e = {
        "id": f"el{_n[0]}", "x": x, "y": y, "width": w, "height": h, "angle": 0,
        "strokeColor": ENCRE, "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
        "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
        "roundness": None, "seed": 1000 + _n[0], "version": 1,
        "versionNonce": 2000 + _n[0], "isDeleted": False, "boundElements": None,
        "updated": 1, "link": None, "locked": False,
    }
    e.update(kw)
    return e


def rect(x, y, w, h, fond="transparent", trait=ENCRE, epaisseur=1,
         arrondi=True, style="solid"):
    e = _base(x, y, w, h, type="rectangle", backgroundColor=fond, strokeColor=trait,
              strokeWidth=epaisseur, strokeStyle=style)
    if arrondi:
        e["roundness"] = {"type": 3}
    elements.append(e)
    return e


def ligne(x1, y1, x2, y2, trait=GRIS):
    e = _base(x1, y1, abs(x2 - x1), abs(y2 - y1), type="line", strokeColor=trait,
              points=[[0, 0], [x2 - x1, y2 - y1]], lastCommittedPoint=None,
              startBinding=None, endBinding=None, startArrowhead=None,
              endArrowhead=None)
    elements.append(e)
    return e


def texte(x, y, contenu, taille=16, police=MANUSCRITE, couleur=ENCRE, align="left"):
    lignes = contenu.split("\n")
    facteur = LARGEUR_CAR if police == MONO else LARGEUR_MAN
    w = max(len(l) for l in lignes) * taille * facteur
    h = len(lignes) * taille * INTERLIGNE
    e = _base(x, y, w, h, type="text", strokeColor=couleur, text=contenu,
              fontSize=taille, fontFamily=police, textAlign=align,
              verticalAlign="top", containerId=None, originalText=contenu,
              lineHeight=INTERLIGNE, autoResize=True)
    elements.append(e)
    return e


def _cellules(valeurs, largeurs, sep=" │ "):
    """Une ligne de tableau calée au caractère. Largeur négative = à droite."""
    out = []
    for valeur, largeur in zip(valeurs, largeurs):
        s = str(valeur)
        out.append(s.rjust(-largeur) if largeur < 0 else s.ljust(largeur))
    return sep.join(out)


def tableau(x, y, entetes, lignes_data, largeurs, taille=13):
    """Rend un tableau à chasse fixe et renvoie l'ordonnée du bas."""
    corps = [_cellules(entetes, [abs(l) for l in largeurs])]
    corps.append("─┼─".join("─" * abs(l) for l in largeurs))
    corps.extend(_cellules(r, largeurs) for r in lignes_data)
    e = texte(x, y, "\n".join(corps), taille=taille, police=MONO)
    return y + e["height"]


def fenetre(x, y, w, h, titre, sous_titre, chemin, filtres):
    """Cadre d'écran : barre de chemin, titre, sous-titre, pastilles de filtre."""
    rect(x, y, w, h, trait=ENCRE, epaisseur=2)
    rect(x, y, w, 34, fond=BLEU_PALE, trait=ENCRE, arrondi=False)
    texte(x + 14, y + 8, chemin, taille=14, couleur=GRIS)
    texte(x + 24, y + 54, titre, taille=26)
    texte(x + 24, y + 92, sous_titre, taille=15, couleur=GRIS)
    cx = x + 24
    for libelle, valeur in filtres:
        etiquette = f"{libelle} : {valeur}"
        largeur = max(round(len(etiquette) * 9.5) + 24, 96)
        rect(cx, y + 126, largeur, 30, trait=GRIS)
        texte(cx + 10, y + 133, etiquette, taille=13, couleur=GRIS)
        cx += largeur + 12
    return y + 178


def pastille_provenance(x, y, contenu, reel):
    """Dit d'où viennent les chiffres. Sans elle, un chiffre d'exemple pris pour
    un chiffre réel détruit la confiance dans toute la planche."""
    fond, trait = (VERT_PALE, VERT) if reel else (ORANGE_PALE, ORANGE)
    largeur = round(len(contenu) * 13 * LARGEUR_MAN) + 34
    rect(x, y, largeur, 30, fond=fond, trait=trait)
    texte(x + 16, y + 7, contenu, taille=13, couleur=trait)
    return y + 30


def bandeau_alerte(x, y, w, titre, contenu):
    """Un fait qui n'est pas un choix : on l'annonce, on ne le fait pas voter."""
    lignes = contenu.split("\n")
    h = 40 + len(lignes) * 14 * INTERLIGNE + 14
    rect(x, y, w, h, fond=ROUGE_PALE, trait=ROUGE)
    texte(x + 16, y + 11, titre, taille=15, couleur=ROUGE)
    texte(x + 16, y + 38, contenu, taille=14, couleur=ENCRE)
    return y + h


def titre_arbitrage(x, y, numero, libelle):
    texte(x, y, f"{numero}  {libelle}", taille=20, couleur=ORANGE)
    return y + 20 * INTERLIGNE + 10


def _hauteur_carte(corps=None, chiffre=None, note=None, **_):
    h = 60
    if corps:
        h += len(corps.split("\n")) * 13 * INTERLIGNE + 14
    if chiffre:
        h += 28 * INTERLIGNE + 12
    if note:
        h += len(note.split("\n")) * 13 * INTERLIGNE
    return h


def carte(x, y, w, lettre, titre, corps=None, chiffre=None, note=None,
          hauteur=None, defaut=False):
    """Une des deux versions proposées. Le chiffre est ce qu'on désigne.

    `defaut` marque celle que le système applique DÉJÀ. Sans elle, les deux
    cartes se valent et il faut trancher pour que quoi que ce soit avance ;
    avec elle, ne rien dire reste une réponse — et il sait laquelle.
    """
    lignes = corps.split("\n") if corps else []
    lignes_note = note.split("\n") if note else []
    h = hauteur or _hauteur_carte(corps, chiffre, note)
    rect(x, y, w, h, trait=GRIS)
    rect(x, y, 34, 30, fond=BLEU_PALE, trait=GRIS, arrondi=False)
    texte(x + 12, y + 6, lettre, taille=16)
    texte(x + 48, y + 6, titre, taille=16)
    if defaut:
        largeur = round(len("PAR DÉFAUT") * 12 * LARGEUR_MAN) + 22
        rect(x + w - largeur - 10, y + 5, largeur, 24, fond=VERT_PALE, trait=VERT)
        texte(x + w - largeur, y + 10, "PAR DÉFAUT", taille=12, couleur=VERT)
    yy = y + 44
    if lignes:
        texte(x + 16, yy, corps, taille=13, police=MONO)
        yy += len(lignes) * 13 * INTERLIGNE + 14
    if chiffre:
        texte(x + 16, yy, chiffre, taille=28, couleur=VERT)
        yy += 28 * INTERLIGNE + 12
    if lignes_note:
        texte(x + 16, yy, note, taille=13, couleur=GRIS)
    return y + h


def egaliser_paires():
    """Aligne la hauteur des deux cartes d'un même arbitrage.

    Deux cadres de tailles différentes suggèrent que l'un pèse plus que
    l'autre — ce n'est pas le message : les deux versions sont à égalité, c'est
    lui qui tranche. On agrandit le plus court vers le bas ; aucun texte ne
    bouge, ils sont tous positionnés depuis le haut de leur carte.
    """
    par_y = {}
    for e in elements:
        if e["type"] == "rectangle" and e["width"] == COL and e["strokeColor"] == GRIS:
            par_y.setdefault(round(e["y"]), []).append(e)
    for cartes_du_rang in par_y.values():
        haute = max(c["height"] for c in cartes_du_rang)
        for c in cartes_du_rang:
            c["height"] = haute


def etat_actuel(x, y, contenu, largeur=960):
    """Aucune des deux versions n'est en place : la valeur par défaut est
    « rien ». Le taire laisserait croire qu'un des deux cadres tourne déjà.

    Le texte est replié dans la colonne de gauche : au-delà, il passerait
    sous la question, qui occupe la colonne de droite au même niveau.
    """
    mots, lignes, courante = f"Aujourd'hui : {contenu}".split(), [], ""
    for mot in mots:
        essai = f"{courante} {mot}".strip()
        if len(essai) * 14 * LARGEUR_MAN > largeur and courante:
            lignes.append(courante)
            courante = mot
        else:
            courante = essai
    lignes.append(courante)
    texte(x, y, "\n".join(lignes), taille=14, couleur=GRIS)
    return y + len(lignes) * 14 * INTERLIGNE


def legende_defaut(x, y):
    texte(x, y, "Le cadre marqué PAR DÉFAUT est ce que le système fait "
                "aujourd'hui — si personne ne tranche, c'est ce qui restera.",
          taille=13, couleur=GRIS)
    return y + 13 * INTERLIGNE


def question(x, y, w, contenu, hauteur_reponse=96):
    """La question, puis le cadre vide où Mohamed note ce qu'il a répondu."""
    lignes = contenu.split("\n")
    texte(x, y, contenu, taille=17)
    yy = y + len(lignes) * 17 * INTERLIGNE + 14
    rect(x, yy, w, hauteur_reponse, fond=JAUNE, trait="#f08c00",
         arrondi=False, style="dashed")
    texte(x + 14, yy + 12, "Ce qu'il a répondu :", taille=13, couleur="#8a5a00")
    return yy + hauteur_reponse


LARGE = 1560
COL = 470          # largeur d'une carte de version
COL2 = 1000        # abscisse de la colonne « question »
LARGEUR_Q = 560


# ══════════════════════════════════════════════════════════════════════════════
# PLANCHE 1 — Parc & interventions
# Parc d'exemple (un seul équipement est saisi dans le système), interventions
# réelles (les trois du tracteur, juin-juillet 2026).
# ══════════════════════════════════════════════════════════════════════════════
Y = 0
texte(0, Y, "Planche 1 — Le parc et les interventions", taille=24, couleur=VERT)
Y += 24 * INTERLIGNE + 12
Y = pastille_provenance(
    0, Y,
    "Liste d'équipements donnée en exemple — un seul équipement est aujourd'hui "
    "saisi dans le système. Les trois interventions du bas sont réelles.",
    reel=False) + 8
Y = legende_defaut(0, Y) + 14

haut_fenetre = Y
bas = fenetre(0, Y, LARGE, 380,
              "Parc & interventions",
              "Ce qui a été fait, ce qui arrive, et dans quel état est le matériel.",
              "hmd.agro  ›  Rapports  ›  Rapport des Interventions",
              [("Date", "31/08/2026"), ("Période", "Mois"), ("Atelier", "Tous")])

bas = tableau(
    24, bas,
    ["Équipement", "État", "Dispo.", "Dernière intervention", "Prochaine", "Heures"],
    [
        ["Tracteur Massey 385", "Bon", "oui", "21/07 — vidange + filtres", "21/10", 412],
        ["Tracteur John Deere", "À vérifier", "oui", "09/07 — courroie alternat.", "05/09", 780],
        ["Remorque épandeuse", "Bon", "oui", "18/06 — graissage", "18/09", "—"],
        ["Pompe à vide traite", "En panne", "non", "—", "06/08  EN RETARD", "—"],
        ["Groupe électrogène", "Bon", "non", "23/06 — contrôle 250 h", "23/12", 128],
        ["Tank à lait 3000 L", "Bon", "oui", "11/06 — sonde température", "11/12", "—"],
    ],
    [21, 11, 6, 26, 16, -6]) + 18
texte(24, bas, "6 équipements  ·  2 indisponibles  ·  1 échéance dépassée", taille=14, couleur=GRIS)

Y = haut_fenetre + 380 + 40

# ── 1.1 — les statuts ────────────────────────────────────────────────────────
Y = titre_arbitrage(0, Y, "①", "Dans quel état est un équipement ?")
a = carte(0, Y, COL, "A", "Une seule liste",
          corps="État ▾\n  ┌───────────────────────┐\n"
                "  │ Prêt à fonctionner    │\n"
                "  │ En panne              │\n"
                "  │ En attente de mainten.│\n"
                "  └───────────────────────┘",
          note="Simple. Mais un seul mot doit tout dire :\n"
               "« en attente de maintenance » ne dit pas\nsi la machine roule encore.")
b = carte(500, Y, COL, "B", "Deux questions séparées",
          corps="Disponible ?  ( ) oui   (•) non\n\n"
                "État ▾\n  ┌───────────────────────┐\n"
                "  │ Bon                   │\n"
                "  │ À vérifier            │\n"
                "  │ Hors service          │\n"
                "  └───────────────────────┘",
          note="Deux clics au lieu d'un. En échange,\n"
               "on sait dire « elle marche encore mais\nil faut la regarder ».")
q = question(COL2, Y, LARGEUR_Q,
             "Le tracteur Massey tousse au démarrage,\n"
             "mais il roule encore et il part demain.\n\n"
             "Tu le mets où ?")
Y = etat_actuel(0, max(a, b) + 12,
                "aucune des deux — le système ne connaît que le statut "
                "comptable d'ERPNext (en service, cédé, mis au rebut). "
                "L'état mécanique n'existe nulle part.")
Y = max(Y, q) + 44

# ── 1.2 — fenêtre du préventif ───────────────────────────────────────────────
Y = titre_arbitrage(0, Y, "②", "Jusqu'où on regarde devant ?")
a = carte(0, Y, COL, "A", "Les 30 prochains jours", defaut=True,
          corps="06/08  Pompe à vide   EN RETARD\n"
                "05/09  John Deere     à venir\n"
                "10/09  Tank à lait    à venir",
          chiffre="3 lignes",
          note="Court. Ce qui tombe en octobre\nn'apparaît qu'en septembre.")
b = carte(500, Y, COL, "B", "Les 60 prochains jours",
          corps="06/08  Pompe à vide   EN RETARD\n"
                "05/09  John Deere     à venir\n"
                "10/09  Tank à lait    à venir\n"
                "18/09  Remorque       à venir\n"
                "21/09  Massey 385     à venir\n"
                "  …et 4 autres",
          chiffre="9 lignes",
          note="On voit venir. Mais l'écran se remplit,\net l'urgent se noie dans le lointain.")
q = question(COL2, Y, LARGEUR_Q,
             "Lundi matin, tu ouvres l'écran.\n\n"
             "Tu veux voir 3 lignes ou 9 lignes ?")
Y = max(a, b, q) + 44

# ── 1.3 — main-d'œuvre et pièces ─────────────────────────────────────────────
Y = titre_arbitrage(0, Y, "③", "Faut-il séparer les pièces de la main-d'œuvre ?")
a = carte(0, Y, COL, "A", "Un seul montant", defaut=True,
          corps="06/06  Vidange moteur + filtres\n"
                "       Tracteur              340,00\n"
                "09/07  Courroie alternateur  185,00\n"
                "21/07  Vidange + filtres     340,00",
          chiffre="1 champ à saisir",
          note="Interventions réelles, juin-juillet 2026.\n"
               "On sait ce que ça coûte, pas pourquoi.")
b = carte(500, Y, COL, "B", "Pièces et main-d'œuvre",
          corps="06/06  Vidange moteur + filtres\n"
                "       pièces                260,00\n"
                "       main-d'œuvre           80,00\n"
                "09/07  Courroie   150,00 + 35,00\n"
                "21/07  Vidange    260,00 + 80,00",
          chiffre="3 champs à saisir",
          note="On peut dire « on paye trop cher la\n"
               "main-d'œuvre extérieure ». À condition\nque quelqu'un saisisse les deux.")
q = question(COL2, Y, LARGEUR_Q,
             "Chaque intervention demandera un montant\n"
             "ou trois, tous les jours, par celui qui saisit.\n\n"
             "Ça vaut le coup ?")
Y = max(a, b, q) + 90


# ══════════════════════════════════════════════════════════════════════════════
# PLANCHE 2 — Charges par atelier et coût du litre
# Montants reconstitués : la comptabilité de juin ne contient que 340 DT. Seule
# la production (45 444 L) est réelle — c'est elle qui rend le coût crédible.
# ══════════════════════════════════════════════════════════════════════════════
texte(0, Y, "Planche 2 — Les charges par atelier et le coût du litre",
      taille=24, couleur=VERT)
Y += 24 * INTERLIGNE + 12
Y = pastille_provenance(
    0, Y,
    "Montants donnés en exemple — la comptabilité de juin ne contient encore que "
    "340 DT. Seuls les 45 444 litres produits sont réels.",
    reel=False) + 8
Y = legende_defaut(0, Y) + 14

haut_fenetre = Y
bas = fenetre(0, Y, LARGE, 420,
              "Charges par atelier",
              "Où part chaque dinar, et ce que coûte un litre de lait.",
              "hmd.agro  ›  Rapports  ›  Rapport de Performance",
              [("Date", "30/06/2026"), ("Période", "Mois")])

bas = tableau(
    24, bas,
    ["Atelier", "Charges", "dont ration", "dont personnel", "dont mécanique", "dont amort."],
    [
        ["Lait", "34 000,00", "21 400,00", "7 200,00", "2 300,00", "3 100,00"],
        ["Élevage - Génisses", "6 500,00", "4 800,00", "1 300,00", "400,00", "0,00"],
        ["Cultures - Fourrage", "8 200,00", "2 100,00", "1 800,00", "3 400,00", "900,00"],
        ["Traction", "3 300,00", "0,00", "400,00", "2 900,00", "0,00"],
        ["Frais Généraux", "9 000,00", "0,00", "5 200,00", "600,00", "3 200,00"],
        ["Autre — en attente", "1 850,00", "à ventiler", "à ventiler", "à ventiler", "à ventiler"],
        ["Non imputé", "0,00", "—", "—", "—", "—"],
        ["TOTAL", "62 850,00", "28 300,00", "15 900,00", "9 600,00", "7 200,00"],
    ],
    [20, -11, -12, -14, -14, -12]) + 20
texte(24, bas, "Production du mois : 45 444 L  ·  Coût complet du litre : "
               "dépend de la clé retenue — voir ① ci-dessous",
      taille=14, couleur=GRIS)

Y = haut_fenetre + 420 + 40

# ── 2.1 — la clé de répartition des frais généraux ───────────────────────────
Y = titre_arbitrage(0, Y, "①", "Le gardien et l'électricité, le lait en porte combien ?")
a = carte(0, Y, COL, "A", "Au prorata de ce que dépense\n     chaque atelier",
          defaut=True,
          corps="Frais généraux du mois     9 000,00\n"
                "Le lait dépense 65 % du total\n"
                "  → le lait en porte        5 885,00\n"
                "Charges du lait            39 885,00\n"
                "Litres produits              45 444",
          chiffre="0,878 DT le litre")
b = carte(500, Y, COL, "B", "Au prorata de ce que rapporte\n     chaque atelier",
          corps="Frais généraux du mois     9 000,00\n"
                "Le lait rapporte 90 % des recettes\n"
                "  → le lait en porte        8 100,00\n"
                "Charges du lait            42 100,00\n"
                "Litres produits              45 444",
          chiffre="0,926 DT le litre")
q = question(COL2, Y, LARGEUR_Q,
             "48 millimes d'écart le litre — 2 181 DT sur le mois.\n\n"
             "Et le mois où les génisses coûtent le double :\n"
             "avec A ton coût du lait DESCEND à 0,863,\n"
             "alors que rien n'a changé au lait.\n"
             "Avec B il ne bouge pas.\n\n"
             "Laquelle des deux te paraît juste ?",
             hauteur_reponse=90)
Y = max(a, b, q) + 44

# ── 2.2 — l'atelier « Autre » ────────────────────────────────────────────────
Y = titre_arbitrage(0, Y, "②", "Les charges que personne n'a encore attribuées")
a = carte(0, Y, COL, "A", "Mises de côté", defaut=True,
          corps="Autre — en attente         1 850,00\n"
                "  ⤷ exclues du coût du litre\n\n"
                "Charges du lait            39 885,00",
          chiffre="0,878 DT le litre",
          note="Le coût du litre ne ment pas :\nil ne compte que ce qu'on a rattaché.\n"
               "Mais 1 850 DT ne pèsent nulle part.")
b = carte(500, Y, COL, "B", "Réparties comme les frais généraux",
          corps="Autre — en attente         1 850,00\n"
                "  ⤷ le lait en porte 65 %   1 210,00\n\n"
                "Charges du lait            41 095,00",
          chiffre="0,904 DT le litre",
          note="Tout est compté. Mais on impute au lait\n"
               "des charges dont on ignore encore\nà quel atelier elles appartiennent.")
q = question(COL2, Y, LARGEUR_Q,
             "Trois charges attendent un arbitrage\ndepuis 12 jours.\n\n"
             "Qui les tranche — et au bout de combien\nde temps on te relance ?",
             hauteur_reponse=90)
Y = max(a, b, q) + 90


# ══════════════════════════════════════════════════════════════════════════════
# PLANCHE 3 — Le lait au quotidien
# Tous les chiffres viennent du site hmd.agro, juin 2026. Rien n'est inventé :
# c'est ce qui rend les trois questions ci-dessous incontestables.
# ══════════════════════════════════════════════════════════════════════════════
JOURS_ECART = (6, 8, 10, 12, 14, 17, 19, 21, 23, 25)   # relevés dans le système

texte(0, Y, "Planche 3 — Le lait au quotidien", taille=24, couleur=VERT)
Y += 24 * INTERLIGNE + 12
Y = pastille_provenance(
    0, Y,
    "Chiffres réels — juin 2026, extraits du site hmd.agro. Aucun nombre de cette "
    "planche n'a été inventé.",
    reel=True) + 8
Y = legende_defaut(0, Y) + 14

haut_fenetre = Y
bas = fenetre(0, Y, LARGE, 430,
              "Production laitière",
              "Le même lait, compté à deux endroits — et ce qui reste entre les deux.",
              "hmd.agro  ›  Rapports  ›  Rapport Périodique  ›  Production",
              [("Date", "30/06/2026"), ("Section", "Production"),
               ("Granularité", "Quotidien"), ("Période", "Jour")])

bas = tableau(
    24, bas,
    ["Jour", "Somme des traites", "Bilan ferme", "Lait vendu", "Lait veau",
     "Conso int.", "Écart déclaré"],
    [
        ["01/06", "1 643", "1 471", "1 436", "35", "0", "0"],
        ["06/06", "1 500", "1 336", "1 501", "35", "0", "-200"],
        ["09/06", "1 569", "1 328", "1 267", "35", "26", "0"],
        ["12/06", "1 562", "1 380", "1 550", "30", "0", "-200"],
        ["20/06", "1 418", "1 261", "1 226", "35", "0", "0"],
        ["26/06", "1 533", "1 393", "1 338", "35", "20", "0"],
        ["27/06", "1 494", "—", "—", "—", "—", "—"],
        ["28/06", "1 448", "—", "—", "—", "—", "—"],
        ["TOTAL", "45 444", "35 485", "36 519", "920", "46", "-2 000"],
    ],
    [8, -17, -11, -10, -9, -10, -13]) + 20
texte(24, bas, "Bilan saisi 26 jours sur 30  ·  les 27, 28, 29 et 30 juin, "
               "les vaches ont été traites mais aucun bilan n'a été rempli",
      taille=14, couleur=GRIS)

Y = haut_fenetre + 430 + 30
Y = bandeau_alerte(
    0, Y, LARGE,
    "Ce point-là n'est pas un choix — c'est une donnée qui manque",
    "Le litres/vache/jour ne peut pas s'afficher : le système compte 0 vache "
    "lactante, parce qu'aucun vêlage n'est enregistré sur juin.\n"
    "L'indicateur central de toute la démarche restera vide tant que les vêlages "
    "ne seront pas saisis. Il faut savoir d'où ils viennent.") + 40

# ── 3.1 — quelle source fait foi ─────────────────────────────────────────────
Y = titre_arbitrage(0, Y, "①", "Deux comptages du même lait, 9 959 litres d'écart")
a = carte(0, Y, COL, "A", "La somme des traites", defaut=True,
          corps="Relevé vache par vache, matin et soir\n"
                "30 jours sur 30\n\n"
                "Juin                        45 444 L\n"
                "Moyenne                   1 515 L/jour",
          chiffre="45 444 L",
          note="Détaillé : on sait quelle vache baisse.\n"
               "Mais c'est une somme d'estimations\nfaites au seau.")
b = carte(500, Y, COL, "B", "Le bilan de la ferme",
          corps="Un total déclaré par jour\n"
                "26 jours sur 30\n\n"
                "Juin                        35 485 L\n"
                "Moyenne                   1 365 L/jour",
          chiffre="35 485 L",
          note="C'est le lait qu'on retrouve au tank.\n"
               "Mais aucun détail : impossible de dire\nd'où vient une baisse.")
q = question(COL2, Y, LARGEUR_Q,
             "L'écart fait 9 959 L, soit 28 %.\n"
             "5 814 L viennent des 4 jours sans bilan.\n"
             "Les 4 145 L restants sont étalés sur tout\n"
             "le mois — environ 160 L chaque jour,\n"
             "toujours dans le même sens.\n\n"
             "Quand les deux ne disent pas la même chose,\n"
             "on affiche lequel ?",
             hauteur_reponse=90)
Y = max(a, b, q) + 44

# ── 3.2 — l'écart déclaré et son seuil d'alerte ──────────────────────────────
frise = "".join("▼" if j in JOURS_ECART else "·" for j in range(1, 31))
Y = titre_arbitrage(0, Y, "②", "Les −200 litres qui reviennent dix fois dans le mois")
a = carte(0, Y, COL, "A", "On alerte au-dessus de 100 L",
          corps=f"1 {frise} 30\n"
                "  ▼ = écart déclaré de -200 L\n\n"
                "Juin : 10 jours dépassent le seuil",
          chiffre="10 alertes ce mois",
          note="Tu es prévenu à chaque fois.\nUn jour sur trois.")
b = carte(500, Y, COL, "B", "On alerte au-dessus de 250 L",
          corps=f"1 {frise} 30\n"
                "  ▼ = écart déclaré de -200 L\n\n"
                "Juin : aucun jour ne dépasse le seuil",
          chiffre="0 alerte ce mois",
          note="Silence complet — alors que 2 000 L\nsont partis quelque part.")
q = question(COL2, Y, LARGEUR_Q,
             "Dix fois dans le mois, toujours exactement\n"
             "−200 L, jamais 190 ni 215.\n\n"
             "Un chiffre aussi rond, dix fois de suite,\n"
             "ça vient d'où ?\n\n"
             "Et à partir de combien tu veux qu'on t'appelle ?",
             hauteur_reponse=90)
Y = etat_actuel(0, max(a, b) + 12,
                "aucune des deux — l'écart est affiché dans le tableau, "
                "il n'a jamais déclenché la moindre alerte.")
Y = max(Y, q) + 44

# ── 3.3 — TB / TP ────────────────────────────────────────────────────────────
Y = titre_arbitrage(0, Y, "③", "Le taux de matière grasse : rien n'est saisi")
a = carte(0, Y, COL, "A", "Affiché seulement les jours mesurés", defaut=True,
          corps="12/06   TB 3,72   TP 3,15\n"
                "13/06     —         —\n"
                "14/06     —         —\n"
                "…\n"
                "26/06   TB 3,68   TP 3,12",
          note="Honnête : on ne montre que ce qu'on sait.\n"
               "Mais la colonne est vide presque partout.")
b = carte(500, Y, COL, "B", "La dernière valeur connue est reportée",
          corps="12/06   TB 3,72   TP 3,15\n"
                "13/06   TB 3,72   TP 3,15   (reporté)\n"
                "14/06   TB 3,72   TP 3,15   (reporté)\n"
                "…\n"
                "26/06   TB 3,68   TP 3,12",
          note="La colonne est toujours remplie.\n"
               "Mais on affiche une mesure du 12 comme\nsi elle valait le 25.")
q = question(COL2, Y, LARGEUR_Q,
             "Aujourd'hui la colonne est vide sur les\n"
             "30 jours de juin — rien n'a jamais été saisi.\n\n"
             "Ces taux viennent d'où, et tu les reçois\n"
             "tous les combien ?",
             hauteur_reponse=90)
Y = max(a, b, q)

egaliser_paires()
SORTIE.write_text(json.dumps({
    "type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
    "files": {},
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(elements)} éléments — {SORTIE}")
