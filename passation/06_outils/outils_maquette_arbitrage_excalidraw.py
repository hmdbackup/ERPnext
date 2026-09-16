"""Génère la maquette de l'écran manquant : l'arbitrage des frais généraux.

L'écran où chaque dépense générale reçoit sa clé de répartition — le seul geste
qui n'a aujourd'hui ni champ ni écran dans le système. Deux formes possibles y
sont maquettées : l'écran d'arbitrage à la clôture, et la variante « un champ
sur la dépense » à la saisie.
"""
import json
from pathlib import Path

SORTIE = Path(__file__).resolve().parents[2] / "passation/03_maquettes/maquette_arbitrage_frais_generaux_2026-08-24.excalidraw"

ENCRE = "#1e1e1e"
GRIS = "#5c5f66"
VERT = "#2f9e44"
ORANGE = "#e8590c"
ROUGE = "#c92a2a"
JAUNE = "#fff3bf"
VERT_PALE = "#ebfbee"
BLEU_PALE = "#e7f5ff"
BLEU = "#1971c2"

MANUSCRITE, MONO = 1, 3
LARGEUR_CAR = 0.60
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


def rect(x, y, w, h, fond="transparent", trait=ENCRE, epaisseur=1, arrondi=True, style="solid"):
    e = _base(x, y, w, h, type="rectangle", backgroundColor=fond, strokeColor=trait,
              strokeWidth=epaisseur, strokeStyle=style)
    if fond != "transparent":
        e["fillStyle"] = "solid"
    if arrondi:
        e["roundness"] = {"type": 3}
    elements.append(e)
    return e


def texte(x, y, contenu, taille=16, police=MANUSCRITE, couleur=ENCRE, align="left"):
    lignes = contenu.split("\n")
    w = max(len(l) for l in lignes) * taille * (LARGEUR_CAR if police == MONO else 0.66)
    h = len(lignes) * taille * INTERLIGNE
    e = _base(x, y, w, h, type="text", strokeColor=couleur, text=contenu,
              fontSize=taille, fontFamily=police, textAlign=align,
              verticalAlign="top", containerId=None, originalText=contenu,
              lineHeight=INTERLIGNE, autoResize=True)
    elements.append(e)
    return e


def fleche(x1, y1, x2, y2, via=None, couleur=BLEU):
    """Flèche d'annotation. `via` insère un point intermédiaire (courbe)."""
    pts = [[0, 0]]
    if via:
        pts.append([via[0] - x1, via[1] - y1])
    pts.append([x2 - x1, y2 - y1])
    e = _base(x1, y1, abs(x2 - x1), abs(y2 - y1), type="arrow", strokeColor=couleur,
              points=pts, startBinding=None, endBinding=None, startArrowhead=None,
              endArrowhead="arrow", lastCommittedPoint=None, roundness={"type": 2})
    elements.append(e)
    return e


def annote(x, y, contenu, taille=13):
    return texte(x, y, contenu, taille=taille, couleur=BLEU)


def pointe(lab, cx, cy, marge=14, via=None):
    """Flèche du bord droit d'un libellé vers une cible."""
    return fleche(lab["x"] + lab["width"] + marge, lab["y"] + lab["height"] / 2, cx, cy, via=via)


def pointe_g(lab, cx, cy, marge=14, via=None):
    """Flèche du bord gauche d'un libellé vers une cible."""
    return fleche(lab["x"] - marge, lab["y"] + lab["height"] / 2, cx, cy, via=via)


def car(t):
    return t["taille"] * LARGEUR_CAR


def y_lig(t, i):
    """Milieu de la ligne de données i (0 = première ligne après le séparateur)."""
    return t["y"] + (i + 2.5) * t["taille"] * INTERLIGNE


def x_col(t, j):
    return t["x"] + (sum(abs(l) for l in t["largeurs"][:j]) + 3 * j) * car(t)


def x_fin_col(t, j):
    return x_col(t, j) + abs(t["largeurs"][j]) * car(t)


def x_fin(t):
    return x_fin_col(t, len(t["largeurs"]) - 1)


def _ligne(cellules, largeurs, sep=" │ "):
    """Une ligne de tableau calée au caractère. Négatif = aligné à droite."""
    out = []
    for valeur, largeur in zip(cellules, largeurs):
        s = str(valeur)
        if len(s) > abs(largeur):
            print(f"  ⚠ DÉBORDEMENT ({len(s)} > {abs(largeur)}) : {s!r}")
        out.append(s.rjust(-largeur) if largeur < 0 else s.ljust(largeur))
    return sep.join(out)


def tableau(x, y, entetes, lignes_data, largeurs, taille=13, tracer=True):
    """Rend un tableau et renvoie l'ordonnée du bas."""
    corps = [_ligne(entetes, [abs(l) for l in largeurs])]
    corps.append("─┼─".join("─" * abs(l) for l in largeurs))
    for r in lignes_data:
        corps.append(_ligne(r, largeurs))
    bloc = "\n".join(corps)
    if tracer:
        print(bloc, "\n")
    e = texte(x, y, bloc, taille=taille, police=MONO)
    return {"x": x, "y": y, "taille": taille, "largeurs": largeurs,
            "bas": y + e["height"], "n": len(lignes_data)}


def fenetre(x, y, w, h, titre, sous_titre, chemin, filtres):
    rect(x, y, w, h, trait=ENCRE, epaisseur=2)
    rect(x, y, w, 34, fond=BLEU_PALE, trait=ENCRE, arrondi=False)
    texte(x + 14, y + 8, chemin, taille=14, couleur=GRIS)
    texte(x + 24, y + 54, titre, taille=26)
    texte(x + 24, y + 92, sous_titre, taille=15, couleur=GRIS)
    cx = x + 24
    for libelle, valeur in filtres:
        largeur = max(round(len(f"{libelle} : {valeur}") * 9.5) + 24, 96)
        rect(cx, y + 126, largeur, 30, fond="transparent", trait=GRIS)
        texte(cx + 10, y + 133, f"{libelle} : {valeur}", taille=13, couleur=GRIS)
        cx += largeur + 12
    return y + 178


def cadre(x, y, w, contenu, titre, fond, trait, couleur_titre):
    lignes = contenu.split("\n")
    h = 46 + len(lignes) * 13 * INTERLIGNE + 14
    rect(x, y, w, h, fond=fond, trait=trait, arrondi=False)
    texte(x + 14, y + 12, titre, taille=15, couleur=couleur_titre)
    texte(x + 14, y + 40, contenu, taille=13, couleur=ENCRE)
    return y + h


def valide(x, y, w, contenu, titre="Validé le 24/08/2026 — M. Samir"):
    return cadre(x, y, w, contenu, titre, VERT_PALE, VERT, "#1b6b34")


def ouvert(x, y, w, contenu, titre="Non tranché — à reprendre"):
    return cadre(x, y, w, contenu, titre, JAUNE, "#f08c00", "#8a5a00")




# ══════════ Écran manquant — arbitrage des frais généraux ══════════
G = -450

Y = 0
texte(0, Y, "Arbitrage des frais généraux — l'écran qui manque", taille=22, couleur=VERT)
texte(760, Y + 4, "À MAQUETTER  ·  24/08/2026", taille=16, couleur=ORANGE)
texte(0, Y + 30, "Chaque dépense générale reçoit sa clé, dépense par dépense — la décision "
                 "de M. Samir n'a aujourd'hui ni champ ni écran où s'inscrire.",
      taille=13, couleur=GRIS)
Y += 66
Y1 = Y
bas = fenetre(0, Y, 1520, 620,
              "Arbitrage des frais généraux — juin 2026",
              "Une ligne par dépense générale. Tant qu'une ligne n'a pas sa clé, le coût du litre du mois n'est pas arrêté.",
              "hmd.agro  ›  Finance  ›  Arbitrage des frais généraux",
              [("Mois", "06/2026"), ("Atelier bénéficiaire", "Lait"), ("Statut", "Tous")])

texte(24, bas, "DÉPENSES GÉNÉRALES DU MOIS — une clé par dépense", taille=13, couleur=VERT)
LA = [10, 15, 22, 20, -10, 14, -6, -10, 8]
tA = tableau(24, bas + 24,
    ["Date", "Pièce", "Libellé", "Compte", "Montant", "Clé retenue", "%", "Part Lait", "Statut"],
    [["05/06/2026", "PINV-2026-0142", "Gardiennage", "621 Services ext.", "3 200.00",
      "B — recettes", "90.00", "2 880.00", "Arbitré"],
     ["08/06/2026", "PINV-2026-0151", "Électricité & eau", "606 Achats non stk.", "2 640.00",
      "A — dépenses", "61.98", "1 636.27", "Arbitré"],
     ["12/06/2026", "JV-2026-0088", "Assurances", "616 Assurances", "1 900.00",
      "A — dépenses", "61.98", "1 177.62", "Arbitré"],
     ["30/06/2026", "JV-2026-0093", "Frais administratifs", "628 Divers", "2 100.00",
      "B — recettes", "90.00", "1 890.00", "Arbitré"],
     ["", "", "", "", "", "", "", "", ""],
     ["", "", "TOTAL DU MOIS", "", "9 840.00", "", "", "7 583.89", ""]],
    LA, taille=12)

texte(24, tA["bas"] + 28, "LES DEUX CLÉS", taille=13, couleur=VERT)
tB = tableau(24, tA["bas"] + 52,
    ["Clé", "Base de calcul", "Juin 2026", "Ce qu'elle dit"],
    [["A — dépenses", "part des dépenses de l'atelier dans le total", "61.98 %",
      "ce que l'atelier consomme"],
     ["B — recettes", "part du CA de l'atelier dans le CA total", "90.00 %",
      "ce que l'atelier rapporte"]],
    [14, 44, -9, 26], taille=12)

texte(24, tB["bas"] + 28, "CONTRÔLE AVANT CLÔTURE", taille=13, couleur=VERT)
tC = tableau(24, tB["bas"] + 52,
    ["Contrôle", "Valeur", "État"],
    [["Frais généraux du mois", "9 840.00 DT", "4 dépenses"],
     ["Dépenses en attente d'arbitrage", "0", "le mois peut être arrêté"],
     ["Part atelier Lait — reprise dans le coût/L", "7 583.89 DT", "reportée au rapport"]],
    [42, -14, 26], taille=12)

# ── Ce que l'écran fait ──
n1 = texte(1060, Y1 + 202,
      "①  Une ligne par dépense générale du mois,\n"
      "    reprise telle quelle de la comptabilité :\n"
      "    pièce, compte et montant compris.", taille=14)
pointe_g(n1, x_fin(tA) + 10, y_lig(tA, 0))

n2 = texte(1060, Y1 + 274,
      "②  La clé se choisit ici, dépense par dépense.\n"
      "    C'est le seul geste que l'écran demande.", taille=14)
pointe_g(n2, x_fin(tA) + 10, y_lig(tA, 1))

n3 = texte(1060, Y1 + 334,
      "③  La part atelier n'est jamais saisie :\n"
      "    elle est calculée, montant × clé.", taille=14)
pointe_g(n3, x_fin(tA) + 10, y_lig(tA, 2))

n4 = texte(1060, Y1 + 394,
      "④  Le total des parts est exactement ce qui\n"
      "    entre dans le coût du litre — 7 583,89 DT.", taille=14)
pointe_g(n4, x_fin(tA) + 10, y_lig(tA, 5))

n5 = texte(1060, Y1 + 460,
      "⑤  La clé appliquée reste écrite sur la ligne,\n"
      "    mois après mois : le coût du litre d'un\n"
      "    mois passé reste explicable.", taille=14)
pointe_g(n5, x_fin(tB) + 10, y_lig(tB, 0))

# ── Explications en marge ──
a = annote(G, Y1 - 4, "Le fil d'Ariane : un écran de finance,\npas un écran de troupeau.")
pointe(a, 8, Y1 + 16)
a = annote(G, Y1 + 100, "Un mois à la fois, et l'atelier qui reçoit\nla quote-part.")
pointe(a, 18, Y1 + 141)
a = annote(G, Y1 + 176, "Le compte reste affiché : le comptable\nretrouve son écriture sans quitter l'écran.")
pointe(a, 18, y_lig(tA, 0))
a = annote(G, Y1 + 248, "Les deux clés sont écrites en toutes\nlettres, avec leur base de calcul. Plus de\npourcentage posé une fois pour toutes.")
pointe(a, 18, y_lig(tB, 0))
a = annote(G, Y1 + 350, "Le contrôle qui compte : tant qu'une\ndépense reste sans clé, le coût du litre\ndu mois ne peut pas être arrêté.")
pointe(a, 18, y_lig(tC, 1))

# ── Ce qui est acquis / ce qui reste à décider ──
bas_ecran = Y1 + 620 + 26
valide(0, bas_ecran, 720,
    "• Frais généraux : arbitrage CAS PAR CAS. Chaque dépense\n"
    "  porte sa clé — A (ce que l'atelier dépense) ou B (ce\n"
    "  qu'il rapporte). Plus de clé unique pour tout le mois.\n"
    "\n"
    "• La clé appliquée est conservée ligne par ligne, pour que\n"
    "  le coût d'un mois passé reste explicable.",
    titre="Acquis le 24/08/2026 — M. Samir")
ouvert(760, bas_ecran, 760,
    "• QUI arbitre : le comptable au moment de la saisie, ou\n"
    "  M. Samir à la clôture du mois ?\n"
    "\n"
    "• C'est cette réponse qui décide de la forme :\n"
    "  – à la saisie → pas d'écran, un simple champ sur la\n"
    "    facture ou l'écriture (variante ci-dessous) ;\n"
    "  – à la clôture → cet écran, la liste du mois à arbitrer.\n"
    "\n"
    "• Une dépense peut-elle être ré-arbitrée après clôture ?",
    titre="À décider avant de construire")

# ══════════ Variante — pas d'écran, un champ sur la dépense ══════════
Y = 1180
texte(0, Y, "Variante — pas d'écran : un champ sur la dépense", taille=22, couleur="#495057")
texte(0, Y + 30, "Si la clé se choisit à la saisie, il n'y a pas d'écran à construire : "
                 "un champ suffit, posé sur la facture et sur l'écriture.",
      taille=13, couleur=GRIS)
Y += 66
Y2 = Y
bas = fenetre(0, Y, 900, 330,
              "Facture d'achat — PINV-2026-0151",
              "Électricité & eau — juin 2026",
              "hmd.agro  ›  Comptabilité  ›  Facture d'achat",
              [("Fournisseur", "STEG"), ("Date", "08/06/2026")])
tD = tableau(24, bas,
    ["Champ", "Valeur"],
    [["Compte de charge", "606 — Achats non stockés"],
     ["Montant", "2 640.00 DT"],
     ["Centre de coût (atelier)", "Frais Généraux"],
     ["Clé de répartition  ⑥", "( ) A — dépenses      (•) B — recettes"]],
    [26, 40], taille=13)

a = annote(G, Y2 + 60, "Le champ nouveau : deux boutons, posés sur\nla facture et sur l'écriture. Rien d'autre\nà construire.")
pointe(a, 18, y_lig(tD, 3))

n6 = texte(940, Y2 + 96,
      "⑥  Choisi à la saisie, par celui qui passe\n"
      "    l'écriture. L'écran d'arbitrage devient\n"
      "    inutile — mais personne ne revoit le mois\n"
      "    en entier avant la clôture.", taille=14, couleur=ORANGE)
pointe_g(n6, x_fin(tD) + 10, y_lig(tD, 3), marge=10)

SORTIE.write_text(json.dumps({
    "type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
    "files": {},
}, ensure_ascii=False, indent=1), encoding="utf-8")
print("écrit :", SORTIE, SORTIE.stat().st_size, "octets —", len(elements), "éléments")
