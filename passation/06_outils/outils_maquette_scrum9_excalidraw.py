"""Génère l'écran SCRUM-9 — Production laitière, non validé, entièrement annoté.

Même fabrique que les maquettes validées. Ici l'écran est repris tel qu'il
serait rendu, et chaque élément porte sa flèche : en bleu ce que l'écran fait,
en orange ce qui reste à trancher, en rouge ce qui bloque.
"""
import json
from pathlib import Path

SORTIE = Path(__file__).resolve().parents[2] / "passation/03_maquettes/maquette_scrum9_annotee_2026-08-24.excalidraw"

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



# ══════════════════ SCRUM-9 — Production laitière, non validé ══════════════════
G = -440          # colonne des explications, à gauche de l'écran

Y = 0
texte(0, Y, "SCRUM-9 — Production laitière par vache", taille=22, couleur="#495057")
texte(640, Y + 4, "NON VALIDÉ  ·  reste à revoir", taille=16, couleur=ROUGE)
texte(0, Y + 30, "L'écran tel qu'il serait rendu, entièrement annoté : en bleu ce qu'il fait, "
                 "en orange ce qui reste à trancher, en rouge ce qui bloque.",
      taille=13, couleur=GRIS)
Y += 66
Y1 = Y
bas = fenetre(0, Y, 1460, 790,
              "Rapport Périodique — Production",
              "Production jour par jour, avec les deux dénominateurs : VL (vaches en lactation) et VP (vaches présentes).",
              "hmd.agro  ›  Rapports  ›  Rapport Périodique",
              [("Date", "30/06/2026"), ("Période", "Mois"), ("Section", "Production"),
               ("Granularité", "Quinzaine"), ("Effectif", "Jour")])

texte(24, bas, "PRODUCTION JOUR PAR JOUR — somme des traites", taille=13, couleur="#495057")
L9 = [-19, -3, -3, -8, -6, -6, -5, -5, -9, -7, -6, -6]
tA = tableau(24, bas + 24,
    ["Jour / Période", "VL", "VP", "Prod. L", "Moy/VL", "Moy/VP", "TB", "TP",
     "Commerc.", "Auto-c.", "Veau", "Écart"],
    [["1", "97", "119", "1643.0", "16.9", "13.8", "–", "–", "1571.0", "32.0", "35.0", "5.0"],
     ["2", "97", "119", "1626.0", "16.8", "13.7", "–", "–", "1554.0", "30.0", "35.0", "7.0"],
     ["3", "96", "118", "1587.0", "16.5", "13.5", "–", "–", "1518.0", "30.0", "35.0", "4.0"],
     ["4", "96", "118", "1569.0", "16.3", "13.3", "–", "–", "1502.0", "28.0", "35.0", "4.0"],
     ["5", "96", "118", "1511.0", "15.7", "12.8", "3.68", "3.15", "1394.0", "30.0", "35.0", "52.0"],
     ["⋮", "", "", "", "", "", "", "", "", "", "", ""],
     ["Q1  (1 → 15)", "–", "–", "23197.0", "–", "–", "–", "–", "22164.0", "445.0", "525.0", "63.0"],
     ["16", "95", "117", "1502.0", "15.8", "12.8", "–", "–", "1436.0", "29.0", "35.0", "2.0"],
     ["17", "95", "117", "1483.0", "15.6", "12.7", "–", "–", "", "", "", ""],
     ["⋮", "", "", "", "", "", "", "", "", "", "", ""],
     ["Q2  (16 → 30)", "–", "–", "22247.0", "–", "–", "–", "–", "21264.0", "445.0", "525.0", "13.0"],
     ["TOTAL (VL/VP moy.)", "96", "118", "45444.0", "15.8", "12.8", "3.68", "3.15", "43428.0", "890.0", "1050.0", "76.0"]],
    L9)

texte(24, tA["bas"] + 28, "LES DEUX COMPTAGES DU MOIS", taille=13, couleur="#495057")
tB = tableau(24, tA["bas"] + 52,
    ["Source du chiffre", "Litres", "Jours saisis", "Ce que c'est"],
    [["Somme des traites — vache par vache", "45 444.0", "30 / 30", "ce que donnent les traites"],
     ["Bilan de la ferme — au tank", "35 485.0", "26 / 30", "ce qu'on retrouve au tank"],
     ["Écart entre les deux", "9 959.0", "—", "acquis : ce n'est pas un sujet"]],
    [36, -9, -12, 32])

texte(24, tB["bas"] + 28, "SUR LES DONNÉES RÉELLES DE JUIN 2026", taille=13, couleur=ROUGE)
tC = tableau(24, tB["bas"] + 52,
    ["Indicateur", "Valeur", "Unité", "Pourquoi"],
    [["Vaches en lactation (VL) — moyenne du mois", "0", "VL", "aucun vêlage enregistré"],
     ["Litres / vache lactante / jour", "—", "L/VL/j", "sans VL, pas de dénominateur"],
     ["Litres / vache présente / jour", "12.8", "L/VP/j", "VP vient de l'effectif présent"]],
    [42, -6, -7, 30])

# ── Ce que l'écran fait : notes numérotées, fléchées sur leur ligne ──
n1 = texte(1000, Y1 + 202,
      "①  VL et VP sont recalculés chaque jour depuis\n"
      "    les vêlages, les tarissements et les sorties.\n"
      "    Les deux dénominateurs restent affichés.", taille=14)
pointe_g(n1, x_fin(tA) + 10, y_lig(tA, 0))

n2 = texte(1000, Y1 + 284,
      "②  Jour 5 — l'écart de 52 L est affiché tel quel.\n"
      "    L'anomalie se voit ; elle n'est pas corrigée\n"
      "    en silence.", taille=14)
pointe_g(n2, x_fin(tA) + 10, y_lig(tA, 4))

n3 = texte(1000, Y1 + 366,
      "③  Jour 17 — bilan lait non saisi : les cellules\n"
      "    restent VIDES, jamais des zéros.", taille=14)
pointe_g(n3, x_fin(tA) + 10, y_lig(tA, 8))

n4 = texte(1000, Y1 + 424,
      "④  Ligne TOTAL — moyennes pour VL et VP, sommes\n"
      "    pour les litres, sur les seuls jours saisis.", taille=14)
pointe_g(n4, x_fin(tA) + 10, y_lig(tA, 11))

# ── Ce que l'écran fait : explications en marge ──
a = annote(G, Y1 - 4, "Le fil d'Ariane : d'où vient l'écran,\net où le retrouver dans le menu.")
pointe(a, 8, Y1 + 16)
a = annote(G, Y1 + 100, "Cinq filtres. « Granularité : Quinzaine »\najoute les lignes Q1 et Q2 ; « Effectif : Jour »\nrecompte le troupeau chaque jour.")
pointe(a, 18, Y1 + 141)
a = annote(G, Y1 + 190, "VL = vaches en lactation, VP = vaches\nprésentes. Les deux sont affichés : c'est\njustement le dénominateur à trancher.")
pointe(a, 18, y_lig(tA, 0))
a = annote(G, Y1 + 268, "Commerc. · Auto-c. · Veau : où part le lait\nune fois trait.")
pointe(a, 18, y_lig(tA, 2))
a = annote(G, Y1 + 330, "Écart = ce qui manque entre la traite et\nles destinations, jour par jour.")
pointe(a, 18, y_lig(tA, 4))
a = annote(G, Y1 + 392, "Une ligne par jour, puis une ligne par\nquinzaine : Q1 et Q2 se lisent sans calcul.")
pointe(a, 18, y_lig(tA, 6))
a = annote(G, Y1 + 500, "Les deux comptages côte à côte, avec le\nnombre de jours réellement saisis derrière\nchacun. C'est ce qui explique l'écart.")
pointe(a, 18, y_lig(tB, 0))
a = annote(G, Y1 + 620, "Le chiffre que tu regardes en premier.\nIl restera vide tant que les vêlages ne\nseront pas saisis.")
pointe(a, 18, y_lig(tC, 1))

# ── Ce qui reste à trancher ──
a = annote(560, Y1 + 178, "TB / TP : rien n'est saisi sur les 30 jours de juin.", taille=13)
a["strokeColor"] = ORANGE
fleche(566, a["y"] + 22, x_col(tA, 6) + 12, tA["y"] + 6, couleur=ORANGE)

q1 = texte(1000, Y1 + 500,
      "⑤  Lequel des deux fait référence ? La somme\n"
      "    des traites (30 j sur 30) ou le bilan de la\n"
      "    ferme (26 j sur 30) ? Le litres/vache/jour\n"
      "    change de valeur selon la réponse.", taille=14, couleur=ORANGE)
pointe_g(q1, x_fin(tB) + 10, y_lig(tB, 0), marge=10)

q2 = texte(1000, Y1 + 590,
      "⑥  L'écart de 9 959 L est un point acquis :\n"
      "    ce n'est pas un sujet, aucune alerte à\n"
      "    construire dessus.", taille=14, couleur=VERT)
pointe_g(q2, x_fin(tB) + 10, y_lig(tB, 2), marge=10)

q3 = texte(1000, Y1 + 660,
      "⑦  BLOQUANT — aucun vêlage n'est enregistré\n"
      "    sur juin, donc 0 vache lactante. Tant que\n"
      "    les vêlages ne sont pas saisis, la ligne\n"
      "    reste vide, quels que soient les arbitrages.", taille=14, couleur=ROUGE)
pointe_g(q3, x_fin(tC) + 10, y_lig(tC, 0), marge=10)

# ── Ce qui est acquis / ce qui reste ouvert ──
bas_ecran = Y1 + 790 + 26
valide(0, bas_ecran, 700,
    "• L'ÉCART N'EST PAS UN SUJET. Les 9 959 L entre la somme\n"
    "  des traites et le bilan de la ferme ne posent pas de\n"
    "  problème au métier — aucune alerte à construire dessus.\n"
    "\n"
    "• Les cellules non saisies restent vides, jamais des zéros :\n"
    "  un jour non saisi ne doit pas peser comme un jour à zéro.",
    titre="Point acquis le 24/08/2026 — M. Samir")
ouvert(740, bas_ecran, 720,
    "• Quel comptage fait référence : la somme des traites\n"
    "  (45 444 L, vache par vache, 30 j sur 30) ou le bilan de la\n"
    "  ferme (35 485 L, ce qu'on retrouve au tank, 26 j sur 30) ?\n"
    "\n"
    "• Les taux TB / TP : d'où viennent-ils, à quelle fréquence ?\n"
    "  Rien n'est saisi sur les 30 jours de juin.\n"
    "\n"
    "• BLOQUANT, indépendant des arbitrages : sans vêlage saisi,\n"
    "  0 vache lactante, et le litres/vache/jour reste vide.",
    titre="Non tranché — à reprendre avec M. Samir")

SORTIE.write_text(json.dumps({
    "type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
    "files": {},
}, ensure_ascii=False, indent=1), encoding="utf-8")
print("écrit :", SORTIE, SORTIE.stat().st_size, "octets —", len(elements), "éléments")
