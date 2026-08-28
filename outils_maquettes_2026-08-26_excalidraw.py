"""Génère les maquettes reprises après la réunion du 26/08/2026 avec M. Samir.

Ce qui change par rapport à `outils_maquettes_validees_excalidraw.py` :

  • Frais généraux — le couple « clé dépenses / clé recettes » et l'écran
    d'arbitrage mensuel disparaissent. Chaque charge porte sa propre
    répartition en pourcentages par atelier, total obligatoirement 100 %,
    saisie une fois sur la charge. Ses trois exemples sont repris tels quels.
  • Un volet SAISIE remplace l'écran d'arbitrage : le parcours du comptable,
    geste par geste — la facture d'achat, la ligne, le bloc répartition,
    l'enregistrement refusé à 80 % ou accepté, le mois suivant par Dupliquer,
    ce que le rapport en lit — puis la facture à plusieurs lignes.
  • La liste des ateliers cesse d'être fermée : Brebis et Fromagerie y figurent.
  • Une case sans valeur affiche un tiret, jamais 0.
  • La période « Année (Year to Date) » apparaît dans les deux écrans.
  • Interventions — trois actions sur une ligne réalisée (dupliquer, planifier,
    supprimer), la règle « ce qui est terminé ne se modifie plus », et la saisie
    geste par geste : la panne, la réparation, la facture rattachée, dupliquer,
    planifier, supprimer, les heures, ce que le rapport en lit.
  • Les colonnes « Nb I » / « Nb É » reprennent leur libellé complet.
  • SCRUM-9 — l'US est annulée : l'écran 3 le dit, avec ce qui lui survit.

Les index de ligne des flèches ne sont plus des nombres écrits à la main :
`idx()` les retrouve par le libellé, pour qu'ajouter une ligne ne décale rien.
"""
import json
import textwrap
from pathlib import Path

SORTIE = Path("/Users/momoslim/Desktop/hmd_agro-main/maquettes_2026-08-26.excalidraw")

ENCRE = "#1e1e1e"
GRIS = "#5c5f66"
VERT = "#2f9e44"
ORANGE = "#e8590c"
ROUGE = "#c92a2a"
JAUNE = "#fff3bf"
VERT_PALE = "#ebfbee"
ROUGE_PALE = "#fff5f5"
BLEU_PALE = "#e7f5ff"
BLEU = "#1971c2"
ETEINT = "#adb5bd"

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


def idx(lignes, motif):
    """Index de la ligne de données dont le libellé contient `motif`."""
    for i, r in enumerate(lignes):
        if motif in r[0]:
            return i
    raise KeyError(f"ligne introuvable : {motif!r}")


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
    """Cadre d'écran. Renvoie le bas de l'en-tête et la position des filtres."""
    rect(x, y, w, h, trait=ENCRE, epaisseur=2)
    rect(x, y, w, 34, fond=BLEU_PALE, trait=ENCRE, arrondi=False)
    texte(x + 14, y + 8, chemin, taille=14, couleur=GRIS)
    texte(x + 24, y + 54, titre, taille=26)
    texte(x + 24, y + 92, sous_titre, taille=15, couleur=GRIS)
    cx, rects = x + 24, {}
    for libelle, valeur in filtres:
        largeur = max(round(len(f"{libelle} : {valeur}") * 9.5) + 24, 96)
        rect(cx, y + 126, largeur, 30, fond="transparent", trait=GRIS)
        texte(cx + 10, y + 133, f"{libelle} : {valeur}", taille=13, couleur=GRIS)
        rects[libelle] = {"x": cx, "y": y + 126, "width": largeur, "height": 30}
        cx += largeur + 12
    return {"bas": y + 178, "filtres": rects}


def panneau(x, y, w, h, titre, chemin, trait=ENCRE):
    """Petit écran secondaire (saisie, fiche). Renvoie le bas de l'en-tête."""
    rect(x, y, w, h, trait=trait, epaisseur=2)
    rect(x, y, w, 30, fond=BLEU_PALE, trait=trait, arrondi=False)
    texte(x + 12, y + 6, chemin, taille=13, couleur=GRIS)
    texte(x + 20, y + 44, titre, taille=18)
    return y + 84


def bouton(x, y, libelle, actif=True, taille=13, couleur=None):
    couleur = couleur or (BLEU if actif else ETEINT)
    w = round(len(libelle) * taille * 0.66) + 30
    rect(x, y, w, 30, fond=(BLEU_PALE if actif else "#f1f3f5"), trait=couleur)
    texte(x + 15, y + 7, libelle, taille=taille, couleur=couleur)
    return {"x": x, "y": y, "width": w, "height": 30}


def champ(x, y, libelle, valeur, largeur, couleur=ENCRE):
    """Champ de formulaire : libellé gris au-dessus, valeur dans sa case."""
    texte(x, y, libelle, taille=11, couleur=GRIS)
    rect(x, y + 18, largeur, 30, fond="#ffffff", trait=GRIS)
    texte(x + 10, y + 25, valeur, taille=13, couleur=couleur)
    return {"x": x, "y": y, "width": largeur, "height": 48, "bas": y + 48}


def liste_deroulante(x, y, options, largeur=250, taille=13, pas=24):
    """Liste ouverte. option = (libellé, marque, couleur)."""
    h = 10 + len(options) * pas + 10
    rect(x, y, largeur, h, fond="#ffffff", trait=GRIS)
    cy = y + 10
    for libelle, marque, couleur in options:
        texte(x + 12, cy + 3, libelle, taille=taille, couleur=couleur)
        if marque:
            texte(x + largeur - 34, cy + 3, marque, taille=taille, couleur=couleur)
        cy += pas
    return {"x": x, "y": y, "width": largeur, "height": h, "bas": y + h}


def cadre(x, y, w, contenu, titre, fond, trait, couleur_titre):
    lignes = contenu.split("\n")
    h = 46 + len(lignes) * 13 * INTERLIGNE + 14
    rect(x, y, w, h, fond=fond, trait=trait, arrondi=False)
    texte(x + 14, y + 12, titre, taille=15, couleur=couleur_titre)
    texte(x + 14, y + 40, contenu, taille=13, couleur=ENCRE)
    return y + h


def valide(x, y, w, contenu, titre="Décidé le 26/08/2026 — M. Samir"):
    return cadre(x, y, w, contenu, titre, VERT_PALE, VERT, "#1b6b34")


def ouvert(x, y, w, contenu, titre="Non tranché — à reprendre"):
    return cadre(x, y, w, contenu, titre, JAUNE, "#f08c00", "#8a5a00")


PERIODES = [("Jour", "", GRIS), ("Semaine", "", GRIS), ("Quinzaine", "", GRIS),
            ("Mois", "✓", ENCRE), ("Année — Year to Date", "★", ORANGE)]
G = -460

# ══════════════════ Écran 1 — SCRUM-10, charges par atelier et coût du litre ══════════════════
Y = 0
texte(0, Y, "SCRUM-10 — Charges par atelier et coût du litre", taille=22, couleur=VERT)
texte(700, Y + 4, "REPRIS APRÈS LA RÉUNION DU 26/08/2026", taille=16, couleur=ORANGE)
texte(0, Y + 30, "La clé unique et le couple « clé dépenses / clé recettes » disparaissent : chaque charge "
                 "générale porte sa propre répartition\nen pourcentages par atelier, dont le total doit faire "
                 "100 %. Saisie une fois, sur la charge, par le comptable.",
      taille=13, couleur=GRIS)
Y += 76
Y1 = Y
H1 = 1120
f1 = fenetre(0, Y, 1460, H1,
             "Rapport de Performance — Charges & Coût du Lait",
             "Les charges ventilées par atelier, puis le coût du lait poste par poste pour rapprochement comptable.",
             "hmd.agro  ›  Rapports  ›  Rapport de Performance",
             [("Date", "30/06/2026"), ("Période", "Mois  ▾"), ("Périmètre coût/L", "LAIT_QUOTE_PART")])
bas = f1["bas"]

LIGNES10 = [
    ["── CHARGES ──", "", "", "", ""],
    ["Ration & Aliments (601)", "41 260.00", "DT", "39 880.00", "+3.5"],
    ["Entretien & Réparations (615)", "2 715.00", "DT", "1 940.00", "+39.9"],
    ["Charges Totales", "112 100.00", "DT", "108 430.00", "+3.4"],
    ["", "", "", "", ""],
    ["── CHARGES PAR ATELIER ──", "", "", "", ""],
    ["Lait — Troupeau Laitier", "63 400.00", "DT", "61 360.00", "+3.3"],
    ["Culture Fourragère & Traction", "21 650.00", "DT", "20 960.00", "+3.3"],
    ["Génisses & Élevage", "12 780.00", "DT", "12 410.00", "+3.0"],
    ["Frais Généraux", "9 840.00", "DT", "9 620.00", "+2.3"],
    ["Frigorifique", "4 430.00", "DT", "4 080.00", "+8.6"],
    ["Brebis — atelier ouvert, aucune charge à ce jour", "–", "DT", "–", "–"],
    ["Fromagerie — atelier ouvert, aucune charge à ce jour", "–", "DT", "–", "–"],
    ["Contrôle — écriture sans atelier ①", "–", "DT", "–", "–"],
    ["TOTAL ventilé = Charges Totales", "112 100.00", "DT", "108 430.00", "+3.4"],
    ["", "", "", "", ""],
    ["── FRAIS GÉNÉRAUX — RÉPARTITION PAR ATELIER, TOTAL 100 % ② ──", "", "", "", ""],
    ["Gardiennage — étable des vaches", "1 400.00", "DT", "1 380.00", "+1.4"],
    ["    └ Lait 100 %", "", "", "", ""],
    ["Gardiennage — troupeau brebis", "900.00", "DT", "890.00", "+1.1"],
    ["    └ Brebis 100 %", "", "", "", ""],
    ["Gardiennage — parc & fromagerie", "900.00", "DT", "880.00", "+2.3"],
    ["    └ Frigorifique 50 % · Fromagerie 50 %", "", "", "", ""],
    ["Électricité & eau", "2 640.00", "DT", "2 560.00", "+3.1"],
    ["    └ Lait 100 %", "", "", "", ""],
    ["Assurances", "1 900.00", "DT", "1 860.00", "+2.2"],
    ["    └ Lait 45 % · Cultures 35 % · Génisses 20 %", "", "", "", ""],
    ["Administratif & direction", "2 100.00", "DT", "2 050.00", "+2.4"],
    ["    └ Lait 30 % · Cultures 35 % · Génisses 35 %", "", "", "", ""],
    ["Total Frais Généraux du mois", "9 840.00", "DT", "9 620.00", "+2.3"],
    ["Contrôle — somme des répartitions = Total FG ③", "9 840.00", "DT", "9 620.00", "+2.3"],
    ["dont part atelier Lait — somme des répartitions", "5 525.00", "DT", "5 392.00", "+2.5"],
    ["", "", "", "", ""],
    ["── COÛT DU LAIT (DÉTAIL) ──", "", "", "", ""],
    ["Ration & Aliments (601)", "41 260.00", "DT", "39 880.00", "+3.5"],
    ["Santé & Vétérinaire (602)", "3 180.00", "DT", "2 940.00", "+8.2"],
    ["Mécanique — Entretien (615)", "620.00", "DT", "480.00", "+29.2"],
    ["Personnel (64x)", "12 900.00", "DT", "12 900.00", "0.0"],
    ["Amortissements (68x)", "3 860.00", "DT", "3 860.00", "0.0"],
    ["Charges financières (66x)", "800.00", "DT", "850.00", "−5.9"],
    ["Autres charges d'exploitation ④", "780.00", "DT", "450.00", "+73.3"],
    ["Sous-total — charges directes Lait", "63 400.00", "DT", "61 360.00", "+3.3"],
    ["Quote-part Frais Gén. — somme des répartitions", "5 525.00", "DT", "5 392.00", "+2.5"],
    ["TOTAL retenu pour le coût du litre", "68 925.00", "DT", "66 752.00", "+3.3"],
    ["", "", "", "", ""],
    ["── COÛTS UNITAIRES ──", "", "", "", ""],
    ["Coût Alimentaire / L", "0.908", "DT/L", "0.895", "+1.5"],
    ["Coût Mécanique / L (vue analytique)", "0.060", "DT/L", "0.044", "+36.4"],
    ["Coût Complet / L (Lait + quote-part) ⑤", "1.517", "DT/L", "1.498", "+1.2"],
    ["Coût du Litre hors Amortissement", "1.432", "DT/L", "1.412", "+1.4"],
    ["IOFC — CA Lait − Coût Alimentaire", "8 682.20", "DT", "8 210.00", "+5.8"],
    ["IOFC / Vache Lactante / Jour", "3.01", "DT/VL/j", "2.87", "+4.9"],
]
t10 = tableau(24, bas, ["Indicateur", "Valeur", "Unité", "M-1", "Δ %"],
              LIGNES10, [61, -12, 7, -12, -7])

# ── La période « Année » : la liste ouverte sous le filtre ──
fp = f1["filtres"]["Période"]
ld = liste_deroulante(960, fp["y"] + 104, PERIODES, largeur=250)
fleche(fp["x"] + fp["width"] - 30, fp["y"] + fp["height"] + 4, ld["x"] - 10, ld["y"] + 34,
       via=(x_fin(t10) + 10, fp["y"] + fp["height"] + 12), couleur=ORANGE)
texte(960, ld["bas"] + 12,
      "★  demandé le 26/08 — Year to Date : du\n     1ᵉʳ janvier à la date choisie, et non\n"
      "     l'année civile entière. Le comparatif\n     devient la même période de l'an dernier.",
      taille=13, couleur=ORANGE)

# ── Notes numérotées, chacune fléchée sur sa ligne ──
n1 = texte(960, Y1 + 464,
      "①  Une case sans valeur affiche un TIRET,\n"
      "    jamais 0. Un montant ici voudrait dire\n"
      "    qu'une écriture est passée sans atelier :\n"
      "    le tiret se remarque, le zéro non.", taille=14)
pointe_g(n1, x_fin(t10) + 10, y_lig(t10, idx(LIGNES10, "écriture sans atelier")))

n2 = texte(960, Y1 + 554,
      "②  Chaque charge porte SA répartition, en\n"
      "    pourcentages par atelier. Autant de lignes\n"
      "    qu'il faut, total obligatoirement 100 %.\n"
      "    Fixée une fois — trois gardiens, trois clés.", taille=14)
pointe_g(n2, x_fin(t10) + 10, y_lig(t10, idx(LIGNES10, "RÉPARTITION PAR ATELIER")))

n3 = texte(960, Y1 + 644,
      "③  La règle des 100 % se vérifie ici : la somme\n"
      "    de toutes les répartitions retombe sur le\n"
      "    total des frais généraux, au dinar près.\n"
      "    Rien ne se perd, rien ne compte deux fois.", taille=14)
pointe_g(n3, x_fin(t10) + 10, y_lig(t10, idx(LIGNES10, "somme des répartitions = Total FG")))

n4 = texte(960, Y1 + 734,
      "④  Les 780 DT autrefois sans atelier sont\n"
      "    désormais imputés au Lait.", taille=14)
pointe_g(n4, x_fin(t10) + 10, y_lig(t10, idx(LIGNES10, "Autres charges d'exploitation")))

n5 = texte(960, Y1 + 789,
      "⑤  Le coût du litre n'est plus le produit d'une\n"
      "    clé calculée : c'est la somme de ce que le\n"
      "    comptable a réparti, charge par charge.\n"
      "    Il s'explique en remontant les lignes.", taille=14)
pointe_g(n5, x_fin(t10) + 10, y_lig(t10, idx(LIGNES10, "Coût Complet / L")))

# ── Explications fléchées, marge de gauche ──
a = annote(G, Y1 - 4, "Le fil d'Ariane : d'où vient l'écran,\net où le retrouver dans le menu.")
pointe(a, 8, Y1 + 16)
a = annote(G, Y1 + 104, "La date, puis la période : jour, semaine,\nquinzaine, mois — et désormais l'année.")
pointe(a, 18, Y1 + 141)
a = annote(G, Y1 + 200, "L'en-tête donne la lecture de chaque ligne :\nvaleur du mois, mois précédent, écart en %.\nEn journalier, M-1 devient la veille.")
pointe(a, 18, t10["y"] + 8)
a = annote(G, Y1 + 300, "Le rapport est fait de blocs — les charges,\nles ateliers, les frais généraux, le détail\ndu lait, les coûts unitaires.")
pointe(a, 18, y_lig(t10, idx(LIGNES10, "── CHARGES PAR ATELIER")))
a = annote(G, Y1 + 400, "La liste des ateliers n'est pas fermée :\nBrebis et Fromagerie y sont déjà, en attente\nde leur première écriture.")
pointe(a, 18, y_lig(t10, idx(LIGNES10, "Brebis — atelier ouvert")))
a = annote(G, Y1 + 500, "Contrôle : la somme des ateliers retombe\nsur les charges totales, au dinar près.")
pointe(a, 18, y_lig(t10, idx(LIGNES10, "TOTAL ventilé")))
a = annote(G, Y1 + 600, "Une ligne par charge, une ligne pour sa\nrépartition. C'est exactement ce que le\ncomptable a saisi sur la facture.")
pointe(a, 18, y_lig(t10, idx(LIGNES10, "Gardiennage — parc")))
a = annote(G, Y1 + 740, "Chaque libellé porte son compte — 601, 615,\n64x — pour que le comptable retrouve\nson écriture.")
pointe(a, 18, y_lig(t10, idx(LIGNES10, "Santé & Vétérinaire")))
a = annote(G, Y1 + 880, "Les quatre lignes du bas sont ce qu'on\nregarde en premier : le coût du litre.")
pointe(a, 18, y_lig(t10, idx(LIGNES10, "── COÛTS UNITAIRES")))

# ── Le volet SAISIE : comment le comptable fait, geste par geste ──
PW, NX = 1000, 1030          # largeur des écrans d'étape ; colonne « ce que l'écran fait »


def etape(n, y, titre):
    """Bande d'étape : pastille numérotée + ce que fait le comptable. Renvoie le haut de l'écran."""
    rect(0, y, 30, 30, fond=VERT_PALE, trait=VERT)
    texte(10, y + 4, str(n), taille=16, couleur=VERT)
    texte(42, y + 5, titre, taille=16)
    return y + 44


def note(y, contenu, largeur=48):
    """Ce que l'écran fait — en noir, à droite de l'écran, un paragraphe par ligne."""
    return texte(NX, y, "\n".join(textwrap.fill(p, largeur) for p in contenu.split("\n")), taille=13)


def chip(x, y, libelle, couleur):
    """Pastille d'état ERPNext : Non enregistré, Brouillon, Non payé."""
    fond = {ROUGE: ROUGE_PALE, VERT: VERT_PALE}.get(couleur, "#f1f3f5")
    w = round(len(libelle) * 13 * 0.66) + 22
    rect(x, y, w, 24, fond=fond, trait=couleur)
    texte(x + 11, y + 4, libelle, taille=13, couleur=couleur)
    return {"x": x, "y": y, "width": w, "height": 24}


def chip_titre(px, py, titre, libelle, couleur):
    """La pastille d'état, à droite du titre d'un panneau."""
    return chip(px + 20 + round(len(titre) * 18 * 0.66) + 16, py + 44, libelle, couleur)


EN_ART = ["#", "Article", "Description", "Qté", "Taux", "Montant (DT)", "Compte de charge", "Centre de coût"]
L_ART = [2, 16, 31, -4, -8, -12, 25, 14]
EN_REP = ["Atelier", "Part (%)", "Montant (DT)"]
L_REP = [30, -8, -12]
REP_OK = [["Lait — Troupeau Laitier", "45.00", "855.00"],
          ["Culture Fourragère & Traction", "35.00", "665.00"],
          ["Génisses & Élevage", "20.00", "380.00"],
          ["─" * 30, "─" * 8, "─" * 12],
          ["Total réparti", "100.00 ✓", "1 900.00"]]
CHEMIN_FAC = "hmd.agro  ›  Comptabilité  ›  Facture d'achat  ›  Nouvelle"

bas_ecran = Y1 + H1 + 34
texte(0, bas_ecran - 30, "LA SAISIE — comment le comptable fait, geste par geste", taille=16, couleur=VERT)
texte(0, bas_ecran + 2,
      "L'exemple suivi de bout en bout : la facture d'assurance de juin — Assurances du Sud SA, 1 900 DT — que l'écran 1 "
      "montre répartie\nLait 45 % · Cultures 35 % · Génisses 20 %. Tout ce qui est en noir existe déjà dans ERPNext ; "
      "le bloc orange est le seul ajout.", taille=13, couleur=GRIS)
a = annote(G, bas_ecran - 30, "L'écran d'arbitrage mensuel présenté le 25/08\nest ABANDONNÉ. « Tu te compliques la tâche. »\n"
                              "Il n'y a plus d'écran à part : la répartition\nvit sur la facture, saisie par le comptable.")
pointe(a, -8, bas_ecran - 22)
y = bas_ecran + 50

# ① Une nouvelle facture, comme toutes les autres
y = etape(1, y, "Il ouvre une nouvelle facture d'achat — comme pour n'importe quelle facture.")
H = 224
p = panneau(0, y, PW, H, "Nouvelle Facture d'achat", "hmd.agro  ›  Comptabilité  ›  Facture d'achat  ›  + Ajouter")
chip_titre(0, y, "Nouvelle Facture d'achat", "Non enregistré", ROUGE)
champ(20, p, "Fournisseur", "Assurances du Sud SA", 250)
champ(290, p, "Date", "30/06/2026", 130)
champ(440, p, "Date d'échéance", "30/07/2026", 130)
champ(590, p, "N° facture fournisseur", "P-2026-06-0418", 180)
champ(790, p, "Date facture fournisseur", "25/06/2026", 190)
r2 = p + 62
champ(20, r2, "Société", "hmd-agro", 130)
champ(170, r2, "Devise", "TND", 90)
champ(280, r2, "Conditions de paiement", "30 jours", 200)
champ(500, r2, "Compte créditeur", "401 — Fournisseurs", 240)
champ(760, r2, "Centre de coût", "Frais Généraux", 220)
note(y + 50, "Rien de nouveau ici. Le fournisseur choisi, ERPNext remplit seul la devise, l'échéance et le "
             "compte 401 — comme aujourd'hui.\nLe centre de coût par défaut de la société est Frais Généraux : "
             "c'est là que la ligne va tomber, sauf si le comptable choisit un atelier.")
y += H + 36

# ② La ligne de charge
y = etape(2, y, "Il saisit la ligne — article, montant. Compte et centre de coût viennent de l'article.")
H = 200
p = panneau(0, y, PW, H, "Articles", CHEMIN_FAC + "  ›  Articles")
t2 = tableau(20, p, EN_ART,
             [["1", "SERV-ASSURANCE", "Assurance multirisque juin 2026", "1", "1 900.00", "1 900.00",
               "616 — Assurances", "Frais Généraux"]], L_ART, taille=12)
rect(x_col(t2, 7) - 5, y_lig(t2, 0) - 10, 14 * car(t2) + 10, 20, trait=ORANGE, epaisseur=2)
bouton(20, t2["bas"] + 14, "+ Ajouter une ligne")
note(y + 50, "Le compte 616 et le centre de coût viennent de l'article, comme aujourd'hui.\n"
             "C'est ce centre de coût — Frais Généraux — qui déclenche l'étape 3. Une ligne mise directement sur "
             "Lait, Génisses ou Cultures n'aura rien de plus à faire : elle est déjà chez elle.")
y += H + 36

# ③ Le bloc apparaît, vide
y = etape(3, y, "Sous les articles, le bloc « Répartition par atelier » apparaît — vide, et obligatoire.")
H = 280
p = panneau(0, y, PW, H, "Répartition par atelier", CHEMIN_FAC + "  ›  Répartition par atelier", trait=ORANGE)
texte(20, p, "La ligne 1 « Assurance multirisque » est imputée aux\nFrais Généraux : indiquez à quels ateliers elle sert.\n"
             "Le total doit faire 100 %.", taille=12, couleur=GRIS)
t3 = tableau(20, p + 54, EN_REP, [["— aucune ligne —", "", ""]], L_REP, taille=12)
texte(20, t3["bas"] + 8, "Total réparti :   0.00 %   — il manque 100 %", taille=12, police=MONO, couleur=ORANGE)
b3 = bouton(20, t3["bas"] + 34, "+ Ajouter un atelier")
rect(12, p - 8, 470, b3["y"] + 30 + 12 - (p - 8), trait=ORANGE, style="dashed")
note(y + 50, "Le même bloc que la répartition d'un salarié dans le registre Personnel — Atelier, Part (%) : "
             "rien de nouveau à apprendre. Le bouton est l'« Ajouter une ligne » d'ERPNext, renommé.\n"
             "Il n'apparaît que si une ligne est sur Frais Généraux. Et tant que le total n'est pas à 100 %, "
             "la facture ne s'enregistre pas (étape 5).")
a = annote(G, y + 60, "Le seul ajout à l'écran d'ERPNext : un\ntableau enfant sur la facture, comme\ncelui du registre Personnel.")
pointe(a, 2, y + 90)
y += H + 36

# ④ Les ateliers, un par un
y = etape(4, y, "Il ajoute les ateliers un par un et tape les pourcentages — 45, 35, 20. Le reste se calcule.")
H = 260
p = panneau(0, y, PW, H, "Répartition par atelier", CHEMIN_FAC + "  ›  Répartition par atelier", trait=ORANGE)
t4 = tableau(20, p, EN_REP, REP_OK, L_REP, taille=12)
rect(x_col(t4, 0) - 5, y_lig(t4, 2) - 9, 30 * car(t4) + 10, 18, trait=BLEU)
l4 = liste_deroulante(x_fin(t4) + 84, t4["y"], [
    ("Lait — Troupeau Laitier", "", GRIS),
    ("Culture Fourragère & Traction", "", GRIS),
    ("Génisses & Élevage", "✓", ENCRE),
    ("Frigorifique", "", ENCRE),
    ("Brebis", "nouv.", ORANGE),
    ("Fromagerie", "nouv.", ORANGE),
], largeur=250, pas=22)
fleche(x_fin_col(t4, 0) + 8, y_lig(t4, 2), l4["x"] - 8, l4["y"] + 10 + 2 * 22 + 8)
b4 = bouton(20, t4["bas"] + 14, "+ Ajouter un atelier")
rect(12, p - 8, 470, b4["y"] + 30 + 12 - (p - 8), trait=ORANGE, style="dashed")
note(y + 50, "Il ne tape que les pourcentages. Le montant en dinars et le total se recalculent à chaque "
             "ligne — 855 + 665 + 380 = 1 900 — il n'a rien à vérifier à la main.\n"
             "La liste propose les centres de coût, Brebis et Fromagerie compris. Frais Généraux n'y est pas : "
             "on ne répartit pas une charge sur elle-même.")
y += H + 36

# ⑤ Enregistrer : refusé à 80 %, accepté à 100 %
y = etape(5, y, "Il enregistre. À 100 %, accepté — puis il soumet. Sinon, ERPNext refuse et dit ce qui manque.")
H = 320
pk = panneau(0, y, 490, H, "S'il avait oublié Génisses — 80 %", CHEMIN_FAC, trait=ROUGE)
tk = tableau(20, pk, EN_REP, [
    ["Lait — Troupeau Laitier", "45.00", "855.00"],
    ["Culture Fourragère & Traction", "35.00", "665.00"],
    ["─" * 30, "─" * 8, "─" * 12],
    ["Total réparti", "80.00 ✗", "1 520.00"]], L_REP, taille=12)
rect(20, tk["bas"] + 12, 450, 66, trait=ROUGE, epaisseur=2)
texte(32, tk["bas"] + 20,
      "✗  Répartition incomplète — ligne 1 : 80 %.\n    Il manque 20 % sur « Assurance multirisque ».\n"
      "    La facture n'est pas enregistrée.  (RG-FIN-40)", taille=12, couleur=ROUGE)
ck = chip(20, tk["bas"] + 92, "Non enregistré", ROUGE)
texte(ck["x"] + ck["width"] + 14, ck["y"] + 5, "il ajoute Génisses 20 %, et enregistre à nouveau.", taille=12, couleur=GRIS)

po = panneau(510, y, 490, H, "À 100 % — enregistrée", "hmd.agro  ›  Comptabilité  ›  Facture d'achat  ›  ACC-PINV-2026-00147", trait=VERT)
chip_titre(510, y, "À 100 % — enregistrée", "Brouillon", GRIS)
texte(530, po, "✓  Répartition à 100 % — la facture est enregistrée\n    sous le numéro ACC-PINV-2026-00147.", taille=13, couleur=VERT)
bs = bouton(530, po + 42, "Soumettre", couleur=VERT)
texte(bs["x"] + bs["width"] + 14, po + 46, "ERPNext demande confirmation, puis l'état\npasse à « Non payé ».", taille=12, couleur=GRIS)
texte(530, po + 96, "AU GRAND LIVRE, APRÈS SOUMETTRE — comme aujourd'hui :", taille=12, couleur=VERT)
tableau(530, po + 116, ["Compte", "Centre de coût", "Débit (DT)", "Crédit (DT)"],
        [["616 — Assurances", "Frais Généraux", "1 900.00", ""],
         ["401 — Fournisseurs", "—", "", "1 900.00"]], [22, 14, -10, -11], taille=11)
note(y + 50, "Le refus est un message — pas un enregistrement silencieux à 80 %.\n"
             "« Soumettre » écrit au Grand Livre exactement comme aujourd'hui : 1 900 DT au compte 616, centre de "
             "coût Frais Généraux. Le comptable ne voit aucune différence dans ses états ; la répartition voyage "
             "avec la facture, et c'est le rapport qui la lit (étape 7).")
a = annote(G, y + 70, "Le blocage se voit : ERPNext refuse\nd'enregistrer et dit quelle ligne manque,\net de combien.")
pointe(a, 2, y + 100)
y += H + 36

# ⑥ Le mois suivant : dupliquer
y = etape(6, y, "Le mois suivant, il duplique la facture de juin : la répartition est déjà là.")
H = 372
TITRE6 = "Facture d'achat ACC-PINV-2026-00147 — juin  ›  Dupliquer"
p = panneau(0, y, PW, H, TITRE6, "hmd.agro  ›  Comptabilité  ›  Facture d'achat  ›  ACC-PINV-2026-00147")
chip_titre(0, y, TITRE6, "Non payé", GRIS)
texte(20, p, "Assurances du Sud SA · 30/06/2026 · 1 900.00 DT", taille=12, couleur=GRIS)
bouton(20, p + 24, "⋯  Menu")
lm = liste_deroulante(20, p + 60, [("Dupliquer", "★", ORANGE), ("Imprimer", "", GRIS), ("E-mail", "", GRIS),
                                   ("Créer › Paiement", "", GRIS), ("Annuler", "", GRIS)], largeur=200, pas=22)
fleche(lm["x"] + lm["width"] + 8, lm["y"] + 21, 470, lm["y"] + 21)
texte(480, p, "Nouvelle Facture d'achat — copie de ACC-PINV-2026-00147", taille=13)
champ(480, p + 24, "Fournisseur", "Assurances du Sud SA", 230, couleur=GRIS)
champ(730, p + 24, "Date", "31/07/2026", 120, couleur=ORANGE)
champ(860, p + 24, "Échéance", "30/08/2026", 120, couleur=GRIS)
r2 = p + 86
champ(480, r2, "N° facture fournisseur", "P-2026-07-0532", 180, couleur=ORANGE)
champ(680, r2, "Date facture fournisseur", "27/07/2026", 150, couleur=ORANGE)
champ(850, r2, "Ligne 1 — montant", "1 900.00", 130, couleur=GRIS)
texte(480, r2 + 62, "RÉPARTITION PAR ATELIER — reprise de juin, rien à ressaisir", taille=12, couleur=ORANGE)
tableau(480, r2 + 80, EN_REP, REP_OK, L_REP, taille=12)
note(y + 50, "Trois champs à changer — en orange : la date, le numéro et la date de la facture du fournisseur — "
             "et le montant s'il a bougé. La clé n'est pas ressaisie : « on le fera une seule fois ».\n"
             "« Dupliquer » existe déjà dans ERPNext (menu ⋯) : rien à développer. L'alternative — pré-remplir "
             "la répartition dès qu'on choisit le fournisseur — est en jaune, à valider.")
a = annote(G, y + 70, "Cinq à dix factures sont concernées, pas plus.\nLa clé se pose une fois — au 31/12, à la\n"
                      "clôture — puis elle suit la facture, de mois\nen mois.")
pointe(a, 2, y + 100)
y += H + 36

# ⑦ Ce que le rapport en fait
y = etape(7, y, "Ce que le rapport en fait — l'écran 1, sans rien saisir d'autre.")
H = 220
p = panneau(0, y, PW, H, "Rapport de Performance — juin 2026, extrait de l'écran 1",
            "hmd.agro  ›  Rapports  ›  Rapport de Performance", trait=VERT)
t7 = tableau(20, p, ["Indicateur", "Valeur", "Unité"], [
    ["── FRAIS GÉNÉRAUX — RÉPARTITION PAR ATELIER ──", "", ""],
    ["Assurances", "1 900.00", "DT"],
    ["    └ Lait 45 % · Cultures 35 % · Génisses 20 %", "", ""],
    ["Total Frais Généraux du mois", "9 840.00", "DT"],
    ["dont part atelier Lait — somme des répartitions", "5 525.00", "DT"]], [48, -10, 5], taille=12)
t7b = tableau(560, p, ["Cette facture, atelier par atelier", "DT"], [
    ["Lait — 45 %", "855.00"], ["Cultures — 35 %", "665.00"], ["Génisses — 20 %", "380.00"],
    ["─" * 34, "─" * 10], ["= la facture", "1 900.00"]], [34, -10], taille=12)
fleche(x_fin(t7) + 10, y_lig(t7, 2), t7b["x"] - 10, y_lig(t7b, 0))
note(y + 50, "Le rapport lit la répartition portée par la facture : 855 DT de cette assurance entrent dans le "
             "coût du litre, 665 chez Cultures, 380 chez Génisses.\n"
             "Le coût du litre n'est plus le produit d'une clé calculée : c'est la somme de ce que le comptable "
             "a saisi, facture par facture — et il s'explique en remontant à chacune.")
a = annote(G, y + 60, "Le Grand Livre du comptable reste sur\nFrais Généraux. C'est le rapport qui fait\n"
                      "la lecture par atelier, à partir de la facture.")
pointe(a, 2, y + 90)
y += H + 36

# Et la facture à plusieurs lignes — ses trois gardiens
texte(0, y + 6, "ET SI LA FACTURE PORTE PLUSIEURS LIGNES ? — ses trois gardiens sur une seule facture", taille=16, couleur=VERT)
y += 44
HV = 360
p = panneau(0, y, PW, HV, "Facture d'achat ACC-PINV-2026-00142 — Sécurité Sud SARL, juin 2026",
            "hmd.agro  ›  Comptabilité  ›  Facture d'achat  ›  ACC-PINV-2026-00142")
texte(20, p, "ARTICLES", taille=12, couleur=VERT)
tv = tableau(20, p + 18, EN_ART, [
    ["1", "SERV-GARDIENNAGE", "Gardiennage — étable des vaches", "1", "1 400.00", "1 400.00", "621 — Personnel extérieur", "Frais Généraux"],
    ["2", "SERV-GARDIENNAGE", "Gardiennage — troupeau brebis", "1", "900.00", "900.00", "621 — Personnel extérieur", "Frais Généraux"],
    ["3", "SERV-GARDIENNAGE", "Gardiennage — parc & fromagerie", "1", "900.00", "900.00", "621 — Personnel extérieur", "Frais Généraux"],
], L_ART, taille=12)
texte(20, tv["bas"] + 16, "RÉPARTITION PAR ATELIER — une par ligne, contrôle des 100 % ligne par ligne", taille=12, couleur=ORANGE)
tv2 = tableau(20, tv["bas"] + 34, ["Ligne", "Charge", "Atelier", "Part (%)", "Montant (DT)"], [
    ["1", "Gardiennage — étable des vaches", "Lait — Troupeau Laitier", "100.00", "1 400.00"],
    ["2", "Gardiennage — troupeau brebis", "Brebis", "100.00", "900.00"],
    ["3", "Gardiennage — parc & fromagerie", "Frigorifique", "50.00", "450.00"],
    ["3", "Gardiennage — parc & fromagerie", "Fromagerie", "50.00", "450.00"],
    ["─" * 5, "─" * 31, "─" * 24, "─" * 8, "─" * 12],
    ["", "Contrôle, ligne par ligne", "100 % · 100 % · 100 %  ✓", "", "3 200.00"],
], [5, 31, 24, -8, -12], taille=12)
rect(12, tv["bas"] + 8, 720, tv2["bas"] + 12 - (tv["bas"] + 8), trait=ORANGE, style="dashed")
note(y + 50, "Quand une facture porte plusieurs lignes sur Frais Généraux, chaque ligne a sa propre répartition : "
             "la colonne « Ligne » dit laquelle, et les 100 % se contrôlent ligne par ligne.\n"
             "Sur une facture à une seule ligne — les étapes 1 à 7 — cette colonne se remplit toute seule.\n"
             "Ce sont ses trois exemples : étable 100 % lait, moutons 100 % brebis, parc et fromagerie 50 / 50.")

bas_ecran = y + HV + 34
gauche = valide(0, bas_ecran, 720,
    "• Frais généraux : UNE RÉPARTITION EN POURCENTAGES, PAR CHARGE.\n"
    "  Plus de clé unique, plus de couple « dépenses / recettes »,\n"
    "  plus d'écran d'arbitrage. Sur chaque charge, autant de lignes\n"
    "  « atelier + % » qu'il faut.\n"
    "\n"
    "• LE TOTAL DOIT FAIRE 100 %. L'enregistrement est bloqué sinon.\n"
    "\n"
    "• QUI, ET QUAND : le comptable, à la saisie. La clé se fixe une\n"
    "  seule fois — au 31/12, à la clôture, on sort le prorata — puis\n"
    "  elle s'applique. Elle n'est pas rearbitrée chaque mois.\n"
    "\n"
    "• LE VOLUME : 5 à 10 factures au grand maximum. Pas de moteur de\n"
    "  règles, pas d'écran de clôture — un champ répétable sur la charge.\n"
    "\n"
    "• LA SAISIE SE FAIT SUR LA FACTURE D'ACHAT, EN CINQ GESTES : ouvrir\n"
    "  la facture, saisir la ligne, répartir par atelier, enregistrer,\n"
    "  soumettre. Un seul bloc nouveau — demandé sur Frais Généraux seulement.\n"
    "\n"
    "• LA LISTE DES ATELIERS EST OUVERTE : Brebis et Fromagerie s'y\n"
    "  ajoutent. C'est de la configuration de centres de coût.\n"
    "\n"
    "• UNE CASE SANS VALEUR AFFICHE UN TIRET, jamais 0.\n"
    "\n"
    "• PÉRIODE : le mois est calendaire — le 15 juillet donne juillet\n"
    "  entier. Ajouter l'année en Year to Date.\n"
    "\n"
    "À construire : un tableau enfant (ligne, atelier, part %) sur la facture\n"
    "d'achat et sur l'écriture de journal — les champs de la répartition\n"
    "d'un salarié, déjà dans Personnel — le total calculé sous le tableau et\n"
    "le contrôle bloquant à 100 % par ligne ; la quote-part devient la somme\n"
    "des répartitions saisies au lieu d'une clé calculée ; la période Année.")
droite = ouvert(760, bas_ecran, 700,
    "• L'année « Year to Date » : du 1ᵉʳ janvier à la date choisie —\n"
    "  et non l'année civile entière. À confirmer d'un mot, car le\n"
    "  comparatif A-1 en dépend.\n"
    "\n"
    "• Nom officiel du centre « frigorifique » (provisoire), et\n"
    "  intitulé des deux nouveaux ateliers Brebis et Fromagerie.\n"
    "\n"
    "• LE MOIS SUIVANT : « Dupliquer », natif dans ERPNext, reprend la\n"
    "  répartition sans rien développer (geste 6). Pré-remplir dès qu'on\n"
    "  choisit le fournisseur est l'alternative — à valider, si le comptable\n"
    "  préfère partir d'une facture vierge.\n"
    "\n"
    "• LE GRAND LIVRE reste sur Frais Généraux, la répartition est une\n"
    "  lecture analytique portée par la facture. L'alternative — ventiler\n"
    "  au Grand Livre par l'allocation de centres de coût native — la\n"
    "  ferait voir dans tous les états, mais viderait l'atelier Frais\n"
    "  Généraux. À trancher avec le comptable.\n"
    "\n"
    "• Les pourcentages affichés ci-dessus sont une ILLUSTRATION.\n"
    "  Ils reprennent vos exemples — gardien de l'étable 100 % lait,\n"
    "  gardien des moutons 100 % brebis, gardien parc + fromagerie\n"
    "  50/50 — mais aucune répartition réelle n'est encore saisie.\n"
    "  Le coût du litre affiché en découle : il bougera.\n"
    "\n"
    "• Les recettes : « après on fera la même chose pour les recettes ».\n"
    "  Noté, hors périmètre de ce sprint.")
BAS1 = max(gauche, droite)

# ══════════════════ Écran 2 — SCRUM-11, parc et interventions ══════════════════
Y = BAS1 + 150
texte(0, Y, "SCRUM-11 — Parc et interventions", taille=22, couleur=VERT)
texte(520, Y + 4, "REPRIS APRÈS LA RÉUNION DU 26/08/2026", taille=16, couleur=ORANGE)
texte(0, Y + 30, "L'écran est validé tel quel. Ce qui s'y ajoute : les trois actions sur une intervention "
                 "déjà faite — dupliquer, planifier,\nsupprimer — la règle « ce qui est terminé ne se "
                 "modifie plus », les libellés de colonnes en clair, et la période Année.",
      taille=13, couleur=GRIS)
Y += 76
Y2 = Y
H2 = 840
f2 = fenetre(0, Y, 1560, H2,
             "Rapport des Interventions",
             "Dans quel état est le matériel, ce qui a été fait, ce qui arrive sous 30 jours, et le rapprochement au compte 615.",
             "hmd.agro  ›  Rapports  ›  Rapport des Interventions",
             [("Date", "30/06/2026"), ("Période", "Mois  ▾"), ("Équipement", "Tous"), ("Atelier", "Tous")])
bas = f2["bas"]

fp2 = f2["filtres"]["Période"]
ld2 = liste_deroulante(1200, Y + 44, PERIODES, largeur=250)
fleche(fp2["x"] + fp2["width"] - 30, fp2["y"] + fp2["height"] + 4, ld2["x"] - 10, ld2["y"] + 130,
       via=(1150, fp2["y"] + fp2["height"] - 4), couleur=ORANGE)
texte(1200, ld2["bas"] + 8, "★  même liste ici, année comprise.", taille=13, couleur=ORANGE)

texte(24, bas, "PARC — ÉTAT DU MATÉRIEL  ⑥", taille=13, couleur=VERT)
LP = [18, 26, 26, 28, 18, -6]
LIGNES_P = [
    ["ACC-ASS-2026-00003", "Tracteur Massey 385", "Prêt", "21/07 — vidange + filtres", "21/10/2026", "412"],
    ["ACC-ASS-2026-00021", "Tracteur John Deere", "En attente de maintenance", "09/07 — courroie alternateur", "05/09/2026", "780"],
    ["ACC-ASS-2026-00019", "Remorque épandeuse", "Prêt", "18/06 — graissage", "18/09/2026", "–"],
    ["ACC-ASS-2026-00016", "Pompe à vide traite", "En panne", "–", "06/08  EN RETARD", "–"],
    ["ACC-ASS-2026-00012", "Groupe électrogène 60 kVA", "Prêt", "23/06 — contrôle 250 h", "23/12/2026", "128"],
    ["ACC-ASS-2026-00007", "Tank à lait 3000 L", "Prêt", "11/06 — sonde température", "11/12/2026", "–"],
]
t_parc = tableau(24, bas + 24,
                 ["Équipement", "Désignation", "État", "Dernière intervention", "Prochaine", "Heures"],
                 LIGNES_P, LP, taille=12)
bas = t_parc["bas"]
resume = texte(24, bas + 8,
               "6 équipements  ·  4 prêts  ·  1 en attente de maintenance  ·  1 en panne  ·  1 échéance dépassée",
               taille=14, couleur=GRIS)
bas = resume["y"] + 26

texte(24, bas + 22, "INTERVENTIONS  ⑦", taille=13, couleur=VERT)
L11 = [13, 10, 18, 25, 10, 33, 18, 17, -9, -9, -9, -10, -9]
LIGNES_I = [
    ["Réalisées ⑧", "06/06/2026", "ACC-ASS-2026-00003", "Tracteur Massey 385", "PRÉVENT.",
     "Vidange moteur + filtres", "Culture Fourragère", "Atelier Ben Salah", "260.00", "80.00", "340.00", "", ""],
    ["Réalisées", "11/06/2026", "ACC-ASS-2026-00007", "Tank à lait 3000 L", "CURATIVE",
     "Remplacement sonde température", "Lait — Troupeau", "Frigotech", "450.00", "170.00", "620.00", "", ""],
    ["Réalisées", "18/06/2026", "ACC-ASS-2026-00012", "Groupe électrogène 60 kVA", "PRÉVENT.",
     "Contrôle 250 h + filtre à air", "Frais Généraux", "Interne", "120.00", "60.00", "180.00", "", ""],
    ["Réalisées", "23/06/2026", "ACC-ASS-2026-00003", "Tracteur Massey 385", "CURATIVE",
     "Réparation circuit hydraulique", "Culture Fourragère", "Atelier Ben Salah", "980.00", "500.00", "1480.00", "", ""],
    ["Réalisées", "27/06/2026", "ACC-ASS-2026-00019", "Remorque épandeuse", "PRÉVENT.",
     "Graissage + contrôle pneus", "Culture Fourragère", "Interne", "45.00", "50.00", "95.00", "", ""],
    ["Réalisées", "", "", "", "", "TOTAL — 5 interv. / 4 équipements", "", "", "1855.00", "860.00", "2715.00", "5", "4"],
    ["", "", "", "", "", "", "", "", "", "", "", "", ""],
    ["Préventif 30j", "28/06/2026", "ACC-ASS-2026-00016", "Pompe à vide traite", "EN RETARD",
     "Contrôle mensuel de dépression", "Lait — Troupeau", "", "", "", "", "", ""],
    ["Préventif 30j", "05/07/2026", "ACC-ASS-2026-00003", "Tracteur Massey 385", "À VENIR ⑨",
     "Vidange 500 h", "Culture Fourragère", "", "", "", "", "", ""],
    ["Préventif 30j", "14/07/2026", "ACC-ASS-2026-00007", "Tank à lait 3000 L", "À VENIR",
     "Nettoyage du condenseur", "Lait — Troupeau", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", "", "", "", ""],
    ["Rapprochem.", "", "", "", "", "Entretien au Grand Livre (615)", "", "", "", "", "2715.00", "", ""],
    ["Rapprochem.", "", "", "", "", "Somme des interventions saisies", "", "", "1855.00", "860.00", "2715.00", "", ""],
    ["Rapprochem.", "", "", "", "", "Écart — aucun : tout est rattaché", "", "", "", "", "0.00", "", ""],
]
t_int = tableau(24, bas + 46,
                ["Section", "Date", "Équipement", "Désignation", "Type", "Libellé", "Atelier",
                 "Intervenant", "Pièces", "M.O.", "Coût", "Nb Interv.", "Nb Équip."],
                LIGNES_I, L11, taille=11)
bas = t_int["bas"]

# ── ⑥ posé à côté du parc, fléché sur la colonne État ──
n6 = texte(1080, t_parc["y"] + 14,
      "⑥  Un seul mot par équipement :\n"
      "     Prêt · En panne · En attente de\n"
      "     maintenance. Pas de champ\n"
      "     « disponible » à côté — « elle roule\n"
      "     encore mais il faut la regarder »\n"
      "     se dit « en attente de maintenance ».", taille=14)
pointe_g(n6, x_fin_col(t_parc, 2) + 8, y_lig(t_parc, 1), via=(900, t_parc["y"] + 34))

a = annote(1080, t_parc["bas"] + 10, "L'échéance dépassée saute aux yeux\nsur la ligne de la machine en panne.")
pointe_g(a, x_fin_col(t_parc, 4) - 12, y_lig(t_parc, 3))

# ── ⑦ les deux colonnes de fin, sa question du 26/08 ──
n7 = texte(24, bas + 26,
      "⑦  Les deux colonnes de fin portent maintenant leur nom entier : Nb Interventions et Nb Équipements. "
      "Elles ne se remplissent que sur\n     la ligne TOTAL — cinq interventions, réparties sur quatre "
      "machines seulement : deux d'entre elles sont passées deux fois à l'atelier.", taille=14)
fleche(x_col(t_int, 11) + 30, n7["y"] - 12, x_col(t_int, 11) + 30, y_lig(t_int, 5))

n8 = texte(24, bas + 92,
      "⑧  Sur une ligne DÉJÀ RÉALISÉE : dupliquer, planifier, supprimer. Ce qui est terminé ne se modifie plus — "
      "on le duplique. Le rapport reste\n     en lecture seule : les trois actions vivent sur la fiche de "
      "l'intervention — gestes 4, 5 et 6 de la saisie, sous l'écran.", taille=14)

n9 = texte(24, bas + 158,
      "⑨  Le préventif reste à 30 jours : trois lignes lundi matin plutôt que neuf, pour que l'urgent ne se "
      "noie pas dans le lointain. C'est ici\n     qu'atterrit une intervention « planifiée » : une date future, "
      "et la ligne reste ouverte jusqu'à ce qu'elle soit faite.", taille=14)


# ── Explications fléchées, marge de gauche ──
a = annote(G, Y2 + 104, "Quatre filtres : on isole un équipement,\nun atelier, une période.")
pointe(a, 18, Y2 + 141)
a = annote(G, Y2 + 210, "Le parc d'abord : dans quel état est chaque\nmachine, et quand elle repasse à l'atelier.")
pointe(a, 18, y_lig(t_parc, 0))
a = annote(G, Y2 + 310, "Le compte du parc en une ligne : combien\nsont prêts, combien attendent.")
pointe(a, 18, resume["y"] + 9)
a = annote(G, Y2 + 410, "Trois blocs dans un seul tableau : ce qui a\nété fait, ce qui arrive sous 30 jours, et le\nrapprochement au compte 615.")
pointe(a, 18, y_lig(t_int, 0))
a = annote(G, Y2 + 510, "Chaque intervention porte son type et son\natelier : c'est par là que le coût remonte\ndans les charges de l'atelier.")
pointe(a, 18, y_lig(t_int, 2))
a = annote(G, Y2 + 610, "Le rapprochement : « la différence entre ce\nqu'on a dépensé et ce dont on n'a pas les\ntraces ». Écart 0,00 — tout est rattaché.")
pointe(a, 18, y_lig(t_int, 13))

# ── La saisie des interventions : le chef de parc, le comptable, le tractoriste — geste par geste ──
CHEMIN_REP = "hmd.agro  ›  Actifs  ›  Réparation d'actif"
MASSEY = "ACC-ASS-2026-00003 — Tracteur Massey 385"

bas_ecran = Y2 + H2 + 34
texte(0, bas_ecran - 30, "LA SAISIE DES INTERVENTIONS — le chef de parc, le comptable, le tractoriste : geste par geste",
      taille=16, couleur=VERT)
texte(0, bas_ecran + 2,
      "Le rapport ne se saisit pas : il lit deux fiches qui existent déjà dans ERPNext — la fiche de l'intervention "
      "(Réparation d'actif),\ntenue par le chef de parc, et la facture du réparateur, saisie par le comptable. "
      "L'exemple suivi : la panne hydraulique du Massey 385,\nréparée le 23/06 par l'Atelier Ben Salah — "
      "980 DT de pièces, 500 DT de main-d'œuvre — telle qu'elle apparaît dans le rapport ci-dessus.",
      taille=13, couleur=GRIS)
a = annote(G, bas_ecran - 30, "Personne ne remplit le rapport. Chaque ligne\nvient d'un geste fait ailleurs — c'est ce que\nmontre le parcours qui suit.")
pointe(a, -8, bas_ecran - 22)
y = bas_ecran + 66

# ① La panne
y = etape(1, y, "La panne : le chef de parc la déclare. La machine passe « En panne » dans le parc.")
H = 260
p = panneau(0, y, PW, H, "Nouvelle Réparation d'actif", CHEMIN_REP + "  ›  + Ajouter")
chip_titre(0, y, "Nouvelle Réparation d'actif", "Non enregistré", ROUGE)
champ(20, p, "Actif", MASSEY, 330)
champ(370, p, "Date de la panne", "22/06/2026 07:30", 170)
champ(560, p, "Type d'intervention", "CURATIVE  ▾", 150)
champ(730, p, "Statut", "En attente  ▾", 150)
r2 = p + 62
champ(20, r2, "Description", "Flexible hydraulique HP éclaté — relevage bloqué, tracteur immobilisé", 600)
champ(640, r2, "Atelier (centre de coût)", "Culture Fourragère & Traction", 300)
b = bouton(20, r2 + 64, "Enregistrer", couleur=VERT)
texte(b["x"] + b["width"] + 16, r2 + 71, "→  dans le PARC : Tracteur Massey 385 — EN PANNE", taille=13, couleur=ROUGE)
note(y + 50, "Quatre choix et une phrase. Le type — curative, préventive, révision, contrôle — et l'atelier sont "
             "déjà sur la fiche (champs HMD existants).\n"
             "Tant que le statut est « En attente », ERPNext met la machine « En panne » : c'est ce que le bloc "
             "PARC affiche, sans rien saisir d'autre.")
y += H + 36

# ② La réparation faite
y = etape(2, y, "La réparation faite : il complète la fiche, enregistre, soumet. La machine repasse « Prêt ».")
H = 330
p = panneau(0, y, PW, H, "Réparation d'actif — ACC-ASR-2026-00021", CHEMIN_REP + "  ›  ACC-ASR-2026-00021")
chip_titre(0, y, "Réparation d'actif — ACC-ASR-2026-00021", "Brouillon", GRIS)
champ(20, p, "Statut", "Terminé  ▾", 150, couleur=ORANGE)
champ(190, p, "Date de fin", "23/06/2026 16:00", 170, couleur=ORANGE)
champ(380, p, "Temps d'arrêt", "33 h", 110)
champ(510, p, "Intervenant", "Atelier Ben Salah — prestataire", 300, couleur=ORANGE)
r2 = p + 62
champ(20, r2, "Ce qui a été fait", "Remplacement du flexible HP + 20 L d'huile hydraulique, purge du circuit", 640)
r3 = r2 + 62
champ(20, r3, "Pièces (DT)", "980.00", 140, couleur=ORANGE)
champ(180, r3, "Main-d'œuvre (DT)", "500.00", 150, couleur=ORANGE)
champ(350, r3, "Coût total (DT) — calculé", "1 480.00", 180, couleur=GRIS)
b = bouton(20, r3 + 64, "Enregistrer")
b2 = bouton(b["x"] + b["width"] + 14, r3 + 64, "Soumettre", couleur=VERT)
texte(b2["x"] + b2["width"] + 16, r3 + 71,
      "→  RÉALISÉES : 23/06 · Massey 385 · CURATIVE · 980 / 500 / 1 480  —  et le PARC : PRÊT", taille=13, couleur=VERT)
note(y + 50, "Deux montants au lieu d'un — pièces, main-d'œuvre — pour pouvoir dire « on paye trop cher la "
             "main-d'œuvre extérieure ». L'intervenant est un salarié du registre Personnel, ou un prestataire.\n"
             "Soumettre fige la fiche : une intervention TERMINÉE ne se modifie plus. Elle entre dans « Réalisées », "
             "la machine repasse « Prêt ».\n"
             "Cette fiche n'écrit rien au Grand Livre. La charge, c'est la facture — geste 3.")
a = annote(G, y + 70, "« Ce qui est terminé, on n'y touche plus » :\nla fiche soumise est figée. Pour refaire,\non duplique (geste 4).")
pointe(a, 2, y + 100)
y += H + 36

# ③ La facture du réparateur
y = etape(3, y, "La facture du réparateur : le comptable la saisit comme toute facture, et la rattache à la fiche.")
H = 290
p = panneau(0, y, PW, H, "Facture d'achat — ACC-PINV-2026-00151", "hmd.agro  ›  Comptabilité  ›  Facture d'achat  ›  ACC-PINV-2026-00151")
chip_titre(0, y, "Facture d'achat — ACC-PINV-2026-00151", "Brouillon", GRIS)
champ(20, p, "Fournisseur", "Atelier Ben Salah", 250)
champ(290, p, "Date", "30/06/2026", 130)
champ(440, p, "N° facture fournisseur", "F-2026-0187", 170)
champ(630, p, "Intervention", "ACC-ASR-2026-00021 — Massey 385, hydraulique 23/06", 360, couleur=ORANGE)
t3 = tableau(20, p + 66, ["#", "Article", "Description", "Qté", "Montant (DT)", "Compte de charge", "Centre de coût"],
             [["1", "SERV-REPARATION", "Réparation circuit hydraulique", "1", "1 480.00",
               "615 — Entretien et réparations", "Culture Fourragère"]], [2, 16, 30, -4, -12, 30, 18], taille=12)
texte(20, t3["bas"] + 8, "TVA 19 % : 281.20   ·   Total général : 1 761.20 DT   ·   Échéance : 30/07/2026", taille=12,
      police=MONO, couleur=GRIS)
b = bouton(20, t3["bas"] + 34, "Enregistrer")
b2 = bouton(b["x"] + b["width"] + 14, t3["bas"] + 34, "Soumettre", couleur=VERT)
texte(b2["x"] + b2["width"] + 16, t3["bas"] + 41,
      "→  au Grand Livre : 615 · Culture Fourragère · 1 480.00  —  le RAPPROCHEMENT retombe juste", taille=13, couleur=VERT)
note(y + 50, "C'est la facture qui écrit au Grand Livre — 615, atelier, TVA, échéance, règlement : le même circuit que "
             "le geste 5 de l'écran 1. Un seul champ nouveau : « Intervention », pour dire à quelle fiche elle se rattache.\n"
             "Le bloc RAPPROCHEMENT du rapport compare les deux : ce que les factures ont mis au 615, et ce que les "
             "fiches disent. Une facture sans fiche, ou une fiche sans facture, fait un écart — « ce dont on n'a "
             "pas exactement les traces ».")
a = annote(G, y + 70, "Le comptable ne change pas d'écran : c'est\nla facture d'achat de l'écran 1, avec un\nchamp de plus.")
pointe(a, 2, y + 100)
y += H + 36

# ④ Dupliquer
y = etape(4, y, "Refaire un graissage : il ouvre le dernier, le duplique, change la date, vérifie, enregistre.")
H = 330
TITRE4 = "Réparation d'actif ACC-ASR-2026-00017 — graissage du 18/06  ›  Dupliquer"
p = panneau(0, y, PW, H, TITRE4, CHEMIN_REP + "  ›  ACC-ASR-2026-00017")
chip_titre(0, y, TITRE4, "Terminée", VERT)
texte(20, p, "Remorque épandeuse · 18/06/2026 · PREVENTIVE · Interne · 95.00 DT", taille=12, couleur=GRIS)
bouton(20, p + 24, "⋯  Menu")
lm = liste_deroulante(20, p + 60, [("Dupliquer", "★", ORANGE), ("Planifier la prochaine", "", ENCRE),
                                   ("Imprimer", "", GRIS), ("Annuler", "", GRIS)], largeur=220, pas=22)
fleche(lm["x"] + lm["width"] + 8, lm["y"] + 21, 470, lm["y"] + 21)
texte(480, p, "Nouvelle Réparation d'actif — copie de ACC-ASR-2026-00017", taille=13)
champ(480, p + 24, "Actif", "Remorque épandeuse", 200, couleur=GRIS)
champ(700, p + 24, "Date", "27/06/2026", 130, couleur=ORANGE)
champ(850, p + 24, "Statut", "Terminé", 130, couleur=GRIS)
r2 = p + 86
champ(480, r2, "Ce qui a été fait", "Graissage + contrôle pneus", 290, couleur=GRIS)
champ(790, r2, "Intervenant", "Interne — K. Brahmi", 190, couleur=GRIS)
r3 = r2 + 62
champ(480, r3, "Pièces (DT)", "45.00", 120, couleur=GRIS)
champ(620, r3, "Main-d'œuvre (DT)", "50.00", 140, couleur=GRIS)
champ(780, r3, "Coût total (DT)", "95.00", 120, couleur=GRIS)
b = bouton(480, r3 + 64, "Enregistrer")
bouton(b["x"] + b["width"] + 14, r3 + 64, "Soumettre", couleur=VERT)
note(y + 50, "Une seule chose à taper : la date. La graisse, l'intervenant, les montants sont repris — il vérifie, "
             "corrige si un prix a bougé, enregistre, soumet. « Lui, ce n'est pas un informaticien » : refaire un "
             "entretien tient en deux clics.\n"
             "« Dupliquer » est natif dans ERPNext (menu ⋯). Rien à développer.")
y += H + 36

# ⑤ Planifier
y = etape(5, y, "Planifier la prochaine : depuis une fiche terminée, une date dans le futur. La fiche reste OUVERTE.")
H = 300
TITRE5 = "Réparation d'actif ACC-ASR-2026-00014 — vidange du 06/06  ›  Planifier"
p = panneau(0, y, PW, H, TITRE5, CHEMIN_REP + "  ›  ACC-ASR-2026-00014")
chip_titre(0, y, TITRE5, "Terminée", VERT)
rect(20, p, 430, 150, fond="#ffffff", trait=ENCRE)
texte(34, p + 10, "Planifier la prochaine intervention", taille=14)
texte(34, p + 34, "Vidange moteur + filtres  ·  Tracteur Massey 385", taille=12, couleur=GRIS)
champ(34, p + 56, "Date prévue", "05/07/2026", 150, couleur=ORANGE)
champ(204, p + 56, "Libellé", "Vidange 500 h", 226)
bouton(34, p + 112, "Planifier", couleur=VERT)
fleche(456, p + 75, 480, p + 75)
texte(490, p, "Réparation d'actif ACC-ASR-2026-00027", taille=13)
chip(770, p - 4, "À venir", ORANGE)
champ(490, p + 24, "Actif", "Tracteur Massey 385", 200, couleur=GRIS)
champ(710, p + 24, "Date prévue", "05/07/2026", 130, couleur=ORANGE)
champ(860, p + 24, "Statut", "À venir", 120, couleur=ORANGE)
r2 = p + 86
champ(490, r2, "Ce qui est prévu", "Vidange 500 h", 240, couleur=GRIS)
champ(750, r2, "Pièces (DT)", "—", 100, couleur=GRIS)
champ(870, r2, "Main-d'œuvre (DT)", "—", 110, couleur=GRIS)
texte(490, r2 + 62, "→  dans le rapport : PRÉVENTIF 30j — 05/07/2026 · Massey 385 · À VENIR · Vidange 500 h.\n"
                    "    Le jour venu : ouvrir la fiche, Terminé, les montants, Soumettre — comme au geste 2.",
      taille=12, couleur=ORANGE)
note(y + 50, "« Planifier, c'est une date dans le futur, elle reste ouverte. » La fiche à venir n'a ni montant ni "
             "date de fin : elle attend. Elle entre dans le bloc Préventif du rapport dès que sa date est à moins "
             "de 30 jours, en rouge si elle est dépassée.\n"
             "Ce que le rapport lit aujourd'hui, ce sont les échéances calendaires d'ERPNext (Asset Maintenance "
             "Log) ; il lira aussi ces fiches à venir — petit ajout.")
a = annote(G, y + 70, "Ce n'est pas un calendrier à part : la\nprochaine intervention est une fiche comme\nles autres, pas encore faite.")
pointe(a, 2, y + 100)
y += H + 36

# ⑥ Supprimer
y = etape(6, y, "Supprimer, en cas d'erreur de saisie : un brouillon s'efface ; une fiche soumise s'annule, et reste en trace.")
H = 210
pk = panneau(0, y, 490, H, "Fiche jamais soumise", CHEMIN_REP + "  ›  ACC-ASR-2026-00029", trait=ROUGE)
chip_titre(0, y, "Fiche jamais soumise", "Brouillon", GRIS)
b = bouton(20, pk, "Supprimer", couleur=ROUGE)
texte(b["x"] + b["width"] + 16, pk + 7, "→  effacée. Elle n'a jamais compté nulle part.", taille=13, couleur=ROUGE)
texte(20, pk + 46, "Saisie sur la mauvaise machine, en double, par erreur :\non l'efface, on ne la corrige pas.", taille=12, couleur=GRIS)
po = panneau(510, y, 490, H, "Fiche soumise", CHEMIN_REP + "  ›  ACC-ASR-2026-00021", trait=ROUGE)
chip_titre(510, y, "Fiche soumise", "Terminée", VERT)
b = bouton(530, po, "Annuler", couleur=ROUGE)
texte(b["x"] + b["width"] + 16, po + 7, "→  reste visible, marquée ANNULÉE ; sort du\n     rapport et du rapprochement.", taille=13, couleur=ROUGE)
texte(530, po + 58, "Une fiche soumise ne s'efface pas : c'est la règle ERPNext.\nSa facture, elle, reste au 615 — au comptable de la\nrattacher à la bonne fiche.", taille=12, couleur=GRIS)
note(y + 50, "Deux cas, et ERPNext les distingue déjà : un brouillon se supprime, un document soumis s'annule et "
             "garde sa trace. La question en jaune : faut-il aussi pouvoir effacer une fiche annulée ?")
y += H + 36

# ⑦ Les heures
y = etape(7, y, "Les heures : le tractoriste, chaque soir — c'est la colonne HEURES du parc, et le coût mécanique par atelier.")
H = 236
p = panneau(0, y, PW, H, "Nouvelle Utilisation Équipement", "hmd.agro  ›  HMD AGRO  ›  Utilisation Équipement  ›  + Ajouter")
chip_titre(0, y, "Nouvelle Utilisation Équipement", "Non enregistré", ROUGE)
champ(20, p, "Équipement", MASSEY, 330)
champ(370, p, "Date", "23/06/2026", 130)
champ(520, p, "Heures d'utilisation", "6.5", 130)
champ(670, p, "Atelier d'imputation", "Culture Fourragère & Traction", 310)
r2 = p + 62
champ(20, r2, "Opérateur", "K. Brahmi — tractoriste", 250)
champ(290, r2, "Coût horaire appliqué (TND/h)", "25.00", 200, couleur=GRIS)
champ(510, r2, "Coût mécanique (TND)", "162.50", 190, couleur=GRIS)
texte(720, r2 + 18, "= 6.5 h × 25.00\nanalytique — rien au Grand Livre", taille=12, couleur=GRIS)
b = bouton(20, r2 + 64, "Enregistrer", couleur=VERT)
texte(b["x"] + b["width"] + 16, r2 + 71, "→  PARC : Massey 385, 412 h  ·  écran 1 : Coût Mécanique / L", taille=13, couleur=VERT)
note(y + 50, "Cet écran existe déjà (FIN-S96), avec ses contrôles : heures > 0, au plus 24 h par jour, date non "
             "future, atelier feuille. Il n'écrit rien au Grand Livre — l'amortissement et l'entretien y sont déjà : "
             "c'est la clé qui répartit la charge mécanique entre les ateliers.\n"
             "À faire avant la démo : le raccourci dans l'espace HMD AGRO (FIN-S102) — aujourd'hui « livré mais "
             "inatteignable ».")
y += H + 36

# ⑧ Ce que le rapport en fait
y = etape(8, y, "Ce que le rapport en fait — l'écran 2, sans rien saisir d'autre.")
H = 330
p = panneau(0, y, PW, H, "Rapport des Interventions — juin 2026, extrait de l'écran 2",
            "hmd.agro  ›  Rapports  ›  Rapport des Interventions", trait=VERT)
texte(20, p, "PARC — geste 1 et 2 pour l'état, geste 7 pour les heures", taille=12, couleur=VERT)
tableau(20, p + 18, ["Équipement", "Désignation", "État", "Dernière intervention", "Prochaine", "Heures"],
        [["ACC-ASS-2026-00003", "Tracteur Massey 385", "Prêt", "23/06 — circuit hydraulique", "05/07/2026", "412"]],
        [18, 20, 8, 28, 12, -6], taille=12)
texte(20, p + 80, "INTERVENTIONS — geste 2 et 4 pour les réalisées, geste 5 pour l'à venir", taille=12, couleur=VERT)
tableau(20, p + 98, ["Date", "Équipement", "Type", "Intervention", "Intervenant", "Pièces", "M.O.", "Coût"],
        [["23/06/2026", "Tracteur Massey 385", "CURATIVE", "Réparation circuit hydraulique", "Atelier Ben Salah", "980.00", "500.00", "1 480.00"],
         ["27/06/2026", "Remorque épandeuse", "PRÉVENT.", "Graissage + contrôle pneus", "Interne", "45.00", "50.00", "95.00"],
         ["05/07/2026", "Tracteur Massey 385", "À VENIR", "Vidange 500 h", "", "", "", ""]],
        [10, 19, 8, 30, 17, -8, -8, -9], taille=12)
texte(20, p + 190, "RAPPROCHEMENT — geste 3 : les factures au 615, face aux fiches", taille=12, couleur=VERT)
texte(20, p + 208, "Entretien au Grand Livre (615)      2 715.00   ·   Somme des fiches saisies   2 715.00   ·   Écart — aucun",
      taille=12, police=MONO)
note(y + 50, "Chaque ligne vient d'un geste : le parc des gestes 1 et 2, la ligne réalisée du geste 2, sa facture "
             "dans le 615 par le geste 3, le graissage du geste 4, la vidange à venir du geste 5, les heures du "
             "geste 7. Personne ne saisit le rapport.")
a = annote(G, y + 70, "Le rapprochement : « la différence entre ce\nqu'on a dépensé et ce dont on n'a pas les\ntraces ». Ici, tout est rattaché.")
pointe(a, 2, y + 100)

bas_ecran = y + H + 34
gauche = valide(0, bas_ecran, 780,
    "• État du matériel : UNE SEULE LISTE.\n"
    "  Prêt · En panne · En attente de maintenance.\n"
    "\n"
    "• Préventif : fenêtre de 30 JOURS.\n"
    "\n"
    "• PIÈCES et MAIN-D'ŒUVRE séparées, plus le type et le coût.\n"
    "  C'est ce qui permettra de dire « on paye trop cher la\n"
    "  main-d'œuvre extérieure ».\n"
    "\n"
    "• TROIS ACTIONS sur une intervention déjà réalisée :\n"
    "  dupliquer, planifier, supprimer.\n"
    "\n"
    "• RÈGLE : ce qui est terminé ne se modifie plus. On duplique.\n"
    "\n"
    "• PLANIFIER = une intervention à date future qui reste ouverte.\n"
    "\n"
    "• Les colonnes portent leur nom entier : Nb Interventions,\n"
    "  Nb Équipements.\n"
    "\n"
    "• RAPPROCHEMENT : « la différence entre ce qu'on a dépensé et\n"
    "  ce dont on n'a pas exactement les traces ». L'écart est\n"
    "  l'information, pas l'erreur.\n"
    "\n"
    "À construire : sur la fiche Réparation d'actif — deux montants\n"
    "(pièces, main-d'œuvre), intervenant salarié ou prestataire, statut\n"
    "À venir / En attente / Terminée, « Planifier la prochaine » ; le\n"
    "champ Intervention sur la ligne de facture d'achat ; le bloc\n"
    "Préventif qui lit aussi les fiches à venir ; un champ État à trois\n"
    "valeurs sur l'équipement ; la période Année.")
droite = ouvert(820, bas_ecran, 740,
    "• QUI ÉCRIT AU 615 : la facture du comptable, rattachée à la fiche\n"
    "  (c'est la maquette) — ou la fiche elle-même à la soumission, par\n"
    "  une écriture automatique 615 / 401 (ce que fait aujourd'hui\n"
    "  enregistrer_intervention) ? Pas les deux. Avec la facture, la TVA\n"
    "  et le règlement suivent le circuit normal. À trancher avec le comptable.\n"
    "\n"
    "• LA MAIN-D'ŒUVRE INTERNE — déjà dans les salaires — compte-t-elle\n"
    "  dans le coût de la fiche ? Si oui, le rapprochement montrera un\n"
    "  écart normal, qu'il expliquera ligne par ligne.\n"
    "\n"
    "• LES PIÈCES DU MAGASIN : la maquette les passe en charge à l'achat\n"
    "  (facture au 615). La sortie de stock ERPNext n'est pas utilisée —\n"
    "  un autre sujet, si le magasin doit être suivi.\n"
    "\n"
    "• Déclencheurs de l'entretien préventif : jours calendaires,\n"
    "  heures de marche, ou fréquence ? La périodicité ERPNext est\n"
    "  purement calendaire ; le seuil au compteur d'heures est à\n"
    "  construire. La réponse peut différer selon l'équipement.\n"
    "\n"
    "• Le parc réel : un seul équipement est aujourd'hui saisi dans\n"
    "  le système. La liste ci-dessus est un exemple — il faut\n"
    "  l'inventaire réel pour que l'écran dise vrai.\n"
    "\n"
    "• SUPPRIMER : un brouillon s'efface, une fiche soumise s'annule et\n"
    "  reste en trace — c'est la règle ERPNext. Faut-il aussi pouvoir\n"
    "  effacer une fiche annulée ?")
BAS2 = max(gauche, droite)

# ══════════════════ Écran 3 — SCRUM-9, annulée le 26/08 ══════════════════
Y = BAS2 + 150
texte(0, Y, "SCRUM-9 — Production laitière", taille=22, couleur="#868e96")
texte(430, Y + 4, "ANNULÉE LE 26/08", taille=16, couleur=ROUGE)
valide(0, Y + 40, 720,
    "• L'USER STORY EST ANNULÉE — « on annule cette User Story ».\n"
    "  L'écran n'a pas été présenté ; il ne sera pas construit.\n"
    "\n"
    "• Le calcul des écarts de production n'a pas de valeur de contrôle :\n"
    "  l'erreur cumulée des lectures manuelles fausse les chiffres.\n"
    "  Les 9 959 L d'écart entre la somme des traites et le bilan de la\n"
    "  ferme ne posent pas de problème au métier — aucune alerte à\n"
    "  construire dessus (acquis dès le 24/08, confirmé le 26/08).\n"
    "\n"
    "• Conséquence : SCRUM-9 se ferme ; le rapport périodique existant\n"
    "  (Jour / Hebdomadaire) reste tel quel, sans évolution prévue.")
ouvert(760, Y + 40, 700,
    "• Quel comptage fait référence : la somme des traites (45 444 L,\n"
    "  vache par vache, 30 j sur 30) ou le bilan de la ferme (35 485 L,\n"
    "  au tank, saisi 26 j sur 30) ? L'écran disparaît, pas la question :\n"
    "  c'est le dénominateur du coût du litre de l'écran 1.\n"
    "\n"
    "• Aucun vêlage n'est saisi sur juin, donc 0 vache lactante : l'IOFC\n"
    "  par vache lactante de l'écran 1 restera vide tant que les vêlages\n"
    "  ne seront pas enregistrés. Bloquant, indépendant de l'US.",
    titre="Ce qui survit à l'annulation — ça n'appartenait pas à l'US")
a = annote(G, Y + 60, "Cet écran ne sera pas construit :\nl'US a été annulée le 26/08.")
pointe(a, -8, Y + 96)

SORTIE.write_text(json.dumps({
    "type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
    "files": {},
}, ensure_ascii=False, indent=1), encoding="utf-8")
print("écrit :", SORTIE, SORTIE.stat().st_size, "octets —", len(elements), "éléments")
