"""Génère les deux maquettes validées du 24/08/2026 au format Excalidraw.

Même fabrique que `outils_maquettes_excalidraw.py` : tableaux en chasse fixe
(fontFamily 3), une ligne = une ligne de texte, colonnes calées au caractère.
Ce qui change ici : les décisions de M. Samir sont appliquées, et le cadre
jaune « À trancher » laisse place à un cadre vert « Validé ».
"""
import json
from pathlib import Path

SORTIE = Path(__file__).resolve().parents[2] / "passation/03_maquettes/maquettes_validees_2026-08-24.excalidraw"

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


# ══════════════════ Écran 1 — SCRUM-10, validé ══════════════════
Y = 0
texte(0, Y, "SCRUM-10 — Charges par atelier et coût du litre", taille=22, couleur=VERT)
texte(700, Y + 4, "VALIDÉ  ·  24/08/2026", taille=16, couleur=VERT)
texte(0, Y + 30, "Deux décisions changent l'écran : la clé des frais généraux devient un arbitrage "
                 "dépense par dépense, et la catégorie « non imputé » disparaît.",
      taille=13, couleur=GRIS)
Y += 66
Y1 = Y
bas = fenetre(0, Y, 1460, 940,
              "Rapport de Performance — Charges & Coût du Lait",
              "Les charges ventilées par atelier, puis le coût du lait poste par poste pour rapprochement comptable.",
              "hmd.agro  ›  Rapports  ›  Rapport de Performance",
              [("Date", "30/06/2026"), ("Période", "Mois"), ("Périmètre coût/L", "LAIT_QUOTE_PART")])
L10 = [56, -12, 7, -12, -7]
t10 = tableau(24, bas,
    ["Indicateur", "Valeur", "Unité", "M-1", "Δ %"],
    [["── CHARGES ──", "", "", "", ""],
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
     ["Contrôle — écriture sans atelier ①", "0.00", "DT", "0.00", "–"],
     ["TOTAL ventilé = Charges Totales", "112 100.00", "DT", "108 430.00", "+3.4"],
     ["", "", "", "", ""],
     ["── FRAIS GÉNÉRAUX — UNE CLÉ PAR DÉPENSE ② ──", "", "", "", ""],
     ["Gardiennage — clé RECETTES (90.00 %)", "3 200.00", "DT", "3 150.00", "+1.6"],
     ["Électricité & eau — clé DÉPENSES (61.98 %)", "2 640.00", "DT", "2 560.00", "+3.1"],
     ["Assurances — clé DÉPENSES (61.98 %)", "1 900.00", "DT", "1 860.00", "+2.2"],
     ["Administratif — clé RECETTES (90.00 %)", "2 100.00", "DT", "2 050.00", "+2.4"],
     ["Total Frais Généraux du mois", "9 840.00", "DT", "9 620.00", "+2.3"],
     ["dont part atelier Lait — somme des arbitrages", "7 583.89", "DT", "7 419.52", "+2.2"],
     ["", "", "", "", ""],
     ["── COÛT DU LAIT (DÉTAIL) ──", "", "", "", ""],
     ["Ration & Aliments (601)", "41 260.00", "DT", "39 880.00", "+3.5"],
     ["Santé & Vétérinaire (602)", "3 180.00", "DT", "2 940.00", "+8.2"],
     ["Mécanique — Entretien (615)", "620.00", "DT", "480.00", "+29.2"],
     ["Personnel (64x)", "12 900.00", "DT", "12 900.00", "0.0"],
     ["Amortissements (68x)", "3 860.00", "DT", "3 860.00", "0.0"],
     ["Charges financières (66x)", "800.00", "DT", "850.00", "−5.9"],
     ["Autres charges d'exploitation ③", "780.00", "DT", "450.00", "+73.3"],
     ["Sous-total — charges directes Lait", "63 400.00", "DT", "61 360.00", "+3.3"],
     ["Quote-part Frais Gén. — clés arbitrées", "7 583.89", "DT", "7 419.52", "+2.2"],
     ["TOTAL retenu pour le coût du litre", "70 983.89", "DT", "68 779.52", "+3.2"],
     ["", "", "", "", ""],
     ["── COÛTS UNITAIRES ──", "", "", "", ""],
     ["Coût Alimentaire / L", "0.908", "DT/L", "0.895", "+1.5"],
     ["Coût Mécanique / L (vue analytique)", "0.060", "DT/L", "0.044", "+36.4"],
     ["Coût Complet / L (Lait + quote-part) ④", "1.562", "DT/L", "1.544", "+1.2"],
     ["Coût du Litre hors Amortissement", "1.477", "DT/L", "1.457", "+1.4"],
     ["IOFC — CA Lait − Coût Alimentaire", "8 682.20", "DT", "8 210.00", "+5.8"],
     ["IOFC / Vache Lactante / Jour", "3.01", "DT/VL/j", "2.87", "+4.9"]],
    L10)
bas = t10["bas"]

# ── Notes numérotées, chacune fléchée vers sa ligne ──
n1 = texte(1010, Y1 + 234,
      "①  « Non imputé » devient une ligne de\n"
      "    contrôle à zéro : l'atelier est obligatoire\n"
      "    à la saisie. La ligne reste affichée pour\n"
      "    prouver qu'il n'y a rien d'oublié.", taille=14)
pointe_g(n1, x_fin(t10) + 10, y_lig(t10, 11))

n2 = texte(1010, Y1 + 334,
      "②  Chaque dépense générale porte sa propre\n"
      "    clé, écrite en toutes lettres. Plus de clé\n"
      "    unique décidée une fois pour toutes.", taille=14)
pointe_g(n2, x_fin(t10) + 10, y_lig(t10, 14))

n3 = texte(1010, Y1 + 434,
      "③  Les 780 DT autrefois sans atelier sont\n"
      "    désormais imputés au Lait.", taille=14)
pointe_g(n3, x_fin(t10) + 10, y_lig(t10, 29))

n4 = texte(1010, Y1 + 524,
      "④  Le coût du litre devient la somme\n"
      "    d'arbitrages individuels : il tombe entre\n"
      "    les deux extrêmes présentés lundi\n"
      "    (0,878 et 0,926 sur la planche).", taille=14)
pointe_g(n4, x_fin(t10) + 10, y_lig(t10, 37))

# ── Explications fléchées, marge de gauche ──
G = -440
a = annote(G, Y1 - 4, "Le fil d'Ariane : d'où vient l'écran,\net où le retrouver dans le menu.")
pointe(a, 8, Y1 + 16)
a = annote(G, Y1 + 104, "Trois filtres seulement. Le périmètre du\ncoût/L est celui qu'on a tranché lundi.")
pointe(a, 18, Y1 + 141)
a = annote(G, Y1 + 188, "L'en-tête donne la lecture de chaque ligne :\nvaleur du mois, mois précédent, écart en %.")
pointe(a, 18, t10["y"] + 8)
a = annote(G, Y1 + 274, "Le rapport est fait de blocs — les charges,\nles ateliers, les frais généraux, le détail\ndu lait, les coûts unitaires.")
pointe(a, 18, y_lig(t10, 5))
a = annote(G, Y1 + 400, "Contrôle : la somme des ateliers retombe\nsur les charges totales, au dinar près.")
pointe(a, 18, y_lig(t10, 12))
a = annote(G, Y1 + 560, "Chaque libellé porte son compte — 601, 615,\n64x — pour que le comptable retrouve\nson écriture.")
pointe(a, 18, y_lig(t10, 23))
a = annote(G, Y1 + 760, "Les quatre lignes du bas sont ce qu'on\nregarde en premier : le coût du litre.")
pointe(a, 18, y_lig(t10, 35))

bas_ecran = Y + 940 + 26
gauche = valide(0, bas_ecran, 720,
    "• Frais généraux : arbitrage CAS PAR CAS.\n"
    "  Ni le prorata des dépenses seul, ni celui des recettes.\n"
    "  Chaque dépense est décidée individuellement — clé A\n"
    "  (ce que dépense l'atelier) ou clé B (ce qu'il rapporte).\n"
    "\n"
    "• AUCUNE charge « non attribuée ».\n"
    "  Toute écriture reçoit son atelier à la saisie ; la ligne\n"
    "  ne subsiste que comme contrôle à zéro.\n"
    "\n"
    "À construire : une clé portée par chaque dépense au lieu\n"
    "d'un paramètre unique dans HMD Configuration ; l'atelier\n"
    "obligatoire et bloquant à la saisie ; la clé appliquée\n"
    "conservée mois par mois, pour que le coût reste explicable.")
ouvert(760, bas_ecran, 700,
    "• Qui arbitre la clé de chaque dépense, et quand —\n"
    "  à la saisie, ou à la clôture du mois ?\n"
    "  Sans réponse, la charge repart en attente et le coût\n"
    "  du litre attend avec elle.\n"
    "\n"
    "• Nom officiel du centre « frigorifique » (provisoire).\n"
    "  La fromagerie viendra dans la même liste.\n"
    "\n"
    "• Périmètre officiel du coût du litre : Lait seul,\n"
    "  Lait + quote-part (retenu ici), ou toutes charges ?")

# ══════════════════ Écran 2 — SCRUM-11, validé ══════════════════
Y = 1450
texte(0, Y, "SCRUM-11 — Parc et interventions", taille=22, couleur=VERT)
texte(520, Y + 4, "VALIDÉ  ·  24/08/2026", taille=16, couleur=VERT)
texte(0, Y + 30, "Un seul champ d'état, une fenêtre de préventif à 30 jours, et le coût d'une "
                 "intervention saisi en deux parts : pièces et main-d'œuvre.",
      taille=13, couleur=GRIS)
Y += 66
Y2 = Y
bas = fenetre(0, Y, 1560, 810,
              "Rapport des Interventions",
              "Dans quel état est le matériel, ce qui a été fait, ce qui arrive sous 30 jours, et le rapprochement au compte 615.",
              "hmd.agro  ›  Rapports  ›  Rapport des Interventions",
              [("Date", "30/06/2026"), ("Période", "Mois"), ("Équipement", "Tous"), ("Atelier", "Tous")])

texte(24, bas, "PARC — ÉTAT DU MATÉRIEL  ⑤", taille=13, couleur=VERT)
LP = [18, 26, 26, 28, 18, -6]
t_parc = tableau(24, bas + 24,
    ["Équipement", "Désignation", "État", "Dernière intervention", "Prochaine", "Heures"],
    [["ACC-ASS-2026-00003", "Tracteur Massey 385", "Prêt", "21/07 — vidange + filtres", "21/10/2026", "412"],
     ["ACC-ASS-2026-00021", "Tracteur John Deere", "En attente de maintenance", "09/07 — courroie alternateur", "05/09/2026", "780"],
     ["ACC-ASS-2026-00019", "Remorque épandeuse", "Prêt", "18/06 — graissage", "18/09/2026", "—"],
     ["ACC-ASS-2026-00016", "Pompe à vide traite", "En panne", "—", "06/08  EN RETARD", "—"],
     ["ACC-ASS-2026-00012", "Groupe électrogène 60 kVA", "Prêt", "23/06 — contrôle 250 h", "23/12/2026", "128"],
     ["ACC-ASS-2026-00007", "Tank à lait 3000 L", "Prêt", "11/06 — sonde température", "11/12/2026", "—"]],
    LP, taille=12)
bas = t_parc["bas"]
resume = texte(24, bas + 8,
            "6 équipements  ·  4 prêts  ·  1 en attente de maintenance  ·  1 en panne  ·  1 échéance dépassée",
            taille=14, couleur=GRIS)
bas = resume["y"] + 26

texte(24, bas + 22, "INTERVENTIONS  ⑥", taille=13, couleur=VERT)
L11 = [13, 10, 18, 25, 10, 33, 18, 17, -9, -9, -9, -5, -5]
t_int = tableau(24, bas + 46,
    ["Section", "Date", "Équipement", "Désignation", "Type", "Libellé", "Atelier",
     "Intervenant", "Pièces", "M.O.", "Coût", "Nb I", "Nb É"],
    [["Réalisées", "06/06/2026", "ACC-ASS-2026-00003", "Tracteur Massey 385", "PRÉVENT.",
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
     ["Préventif 30j", "05/07/2026", "ACC-ASS-2026-00003", "Tracteur Massey 385", "À VENIR",
      "Vidange 500 h", "Culture Fourragère", "", "", "", "", "", ""],
     ["Préventif 30j", "14/07/2026", "ACC-ASS-2026-00007", "Tank à lait 3000 L", "À VENIR",
      "Nettoyage du condenseur", "Lait — Troupeau", "", "", "", "", "", ""],
     ["", "", "", "", "", "", "", "", "", "", "", "", ""],
     ["Rapprochem.", "", "", "", "", "Entretien au Grand Livre (615)", "", "", "", "", "2715.00", "", ""],
     ["Rapprochem.", "", "", "", "", "Somme des interventions saisies", "", "", "1855.00", "860.00", "2715.00", "", ""],
     ["Rapprochem.", "", "", "", "", "Écart — aucun : tout est rattaché", "", "", "", "", "0.00", "", ""]],
    L11, taille=11)
bas = t_int["bas"]

# ── ⑤ posé à côté du parc, fléché sur la colonne État ──
n5 = texte(1030, t_parc["y"] + 14,
      "⑤  Un seul mot par équipement :\n"
      "     Prêt · En panne · En attente de\n"
      "     maintenance. Pas de champ\n"
      "     « disponible » à côté — « elle roule\n"
      "     encore mais il faut la regarder »\n"
      "     se dit « en attente de maintenance ».", taille=14)
pointe_g(n5, x_fin_col(t_parc, 2) + 8, y_lig(t_parc, 1),
         via=(860, t_parc["y"] + 34))

a = annote(1030, t_parc["bas"] + 10, "L'échéance dépassée saute aux yeux\nsur la ligne de la machine en panne.")
pointe_g(a, x_fin_col(t_parc, 4) - 12, y_lig(t_parc, 3))

# ── ⑥ et ⑦ sous le tableau ──
note6 = texte(24, bas + 26,
      "⑥  Chaque ligne est cliquable : elle ouvre le détail de l'intervention — pièces posées, "
      "temps passé, facture, écriture au 615.", taille=14)
note7 = texte(24, bas + 56,
      "⑦  Le préventif reste à 30 jours : trois lignes lundi matin plutôt que neuf, pour que "
      "l'urgent ne se noie pas dans le lointain.", taille=14)
fleche(300, note7["y"] - 8, 208, y_lig(t_int, 9))

a = annote(1160, note7["y"] + 34, "Trois montants par intervention :\npièces, main-d'œuvre, et le total\nqui s'en déduit.")
fleche(1230, a["y"] - 8, x_col(t_int, 10) + 22, t_int["y"] + 8, via=(1442, 2020))

# ── Explications fléchées, marge de gauche ──
a = annote(G, Y2 + 104, "Quatre filtres : on isole un équipement,\nun atelier, une période.")
pointe(a, 18, Y2 + 141)
a = annote(G, Y2 + 196, "Le parc d'abord : dans quel état est chaque\nmachine, et quand elle repasse à l'atelier.")
pointe(a, 18, y_lig(t_parc, 0))
a = annote(G, Y2 + 300, "Le compte du parc en une ligne : combien\nsont prêts, combien attendent.")
pointe(a, 18, resume["y"] + 9)
a = annote(G, Y2 + 404, "Trois blocs dans un seul tableau : ce qui a\nété fait, ce qui arrive sous 30 jours, et le\nrapprochement au compte 615.")
pointe(a, 18, y_lig(t_int, 0))
a = annote(G, Y2 + 494, "Chaque intervention porte son type et son\natelier : c'est par là que le coût remonte\ndans les charges de l'atelier.")
pointe(a, 18, y_lig(t_int, 2))
a = annote(G, Y2 + 590, "Le contrôle : les interventions saisies\ndoivent égaler le compte 615.\nÉcart 0,00 — tout est rattaché.")
pointe(a, 18, y_lig(t_int, 13))

bas_ecran = Y + 810 + 26
valide(0, bas_ecran, 780,
    "• État du matériel : UNE SEULE LISTE.\n"
    "  Prêt · En panne · En attente de maintenance.\n"
    "\n"
    "• Préventif : fenêtre de 30 JOURS.\n"
    "\n"
    "• PIÈCES et MAIN-D'ŒUVRE séparées, plus le type et le coût.\n"
    "  Trois montants par intervention ; le total s'en déduit.\n"
    "  C'est ce qui permettra de dire « on paye trop cher la\n"
    "  main-d'œuvre extérieure ».\n"
    "\n"
    "• Chaque intervention MÈNE À SON DÉTAIL.\n"
    "\n"
    "À construire : un champ État à trois valeurs sur la fiche\n"
    "équipement — l'état mécanique n'existe nulle part aujourd'hui,\n"
    "ERPNext ne connaît que le statut comptable (en service, cédé,\n"
    "mis au rebut) ; deux montants au lieu d'un sur l'Asset Repair ;\n"
    "et le lien de la ligne de rapport vers la fiche.")
ouvert(820, bas_ecran, 740,
    "• Déclencheurs de l'entretien préventif : jours calendaires,\n"
    "  heures de marche, ou fréquence ? La périodicité ERPNext est\n"
    "  purement calendaire ; le seuil au compteur d'heures est à\n"
    "  construire. La réponse peut différer selon l'équipement.\n"
    "\n"
    "• Le parc réel : un seul équipement est aujourd'hui saisi dans\n"
    "  le système. La liste ci-dessus est un exemple — il faut\n"
    "  l'inventaire réel pour que l'écran dise vrai.")

# ══════════════════ Écran 3 — SCRUM-9, non validé ══════════════════
Y = 2790
texte(0, Y, "SCRUM-9 — Production laitière", taille=22, couleur="#868e96")
texte(430, Y + 4, "NON VALIDÉ  ·  reste à revoir", taille=16, couleur=ROUGE)
ouvert(0, Y + 40, 1460,
    "• Point acquis : L'ÉCART N'EST PAS UN SUJET. Les 9 959 L d'écart entre la somme des traites et le\n"
    "  bilan de la ferme ne posent pas de problème au métier — aucune alerte à construire dessus.\n"
    "\n"
    "• Quel comptage fait référence : la somme des traites (45 444 L, vache par vache, 30 j sur 30)\n"
    "  ou le bilan de la ferme (35 485 L, ce qu'on retrouve au tank, saisi 26 j sur 30) ?\n"
    "\n"
    "• Les taux TB / TP : rien n'est saisi sur les 30 jours de juin. D'où viennent-ils, à quelle fréquence ?\n"
    "\n"
    "• BLOQUANT, indépendant des arbitrages : aucun vêlage n'est enregistré sur juin, donc 0 vache\n"
    "  lactante. Le litres/vache/jour restera vide tant que les vêlages ne seront pas saisis.",
    titre="L'écran n'est pas validé — ce qu'il faudra y trancher")
a = annote(G, Y + 60, "Cet écran ne part pas au groupe :\nil reste à revoir avec M. Samir.")
pointe(a, -8, Y + 96)

SORTIE.write_text(json.dumps({
    "type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
    "files": {},
}, ensure_ascii=False, indent=1), encoding="utf-8")
print("écrit :", SORTIE, SORTIE.stat().st_size, "octets —", len(elements), "éléments")
