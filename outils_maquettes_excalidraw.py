"""Génère les maquettes SCRUM-9/10/11 au format Excalidraw.

Les tableaux sont composés en police à chasse fixe (fontFamily 3) : c'est la
seule façon d'aligner des colonnes dans Excalidraw, qui n'a pas de contrôle
« tableau ». Une ligne = une ligne de texte, les colonnes sont calées au
caractère par `_ligne()`.
"""
import json
from pathlib import Path

SORTIE = Path("/Users/momoslim/Desktop/hmd_agro-main/maquettes_scrum_9_10_11.excalidraw")

ENCRE = "#1e1e1e"
GRIS = "#5c5f66"
VERT = "#2f9e44"
ORANGE = "#e8590c"
ROUGE = "#c92a2a"
JAUNE = "#fff3bf"
BLEU_PALE = "#e7f5ff"

MANUSCRITE, MONO = 1, 3
LARGEUR_CAR = 0.60      # largeur d'un caractère en fraction de la taille de police
INTERLIGNE = 1.25

elements = []
_n = [0]


def _id():
    _n[0] += 1
    return f"el{_n[0]}"


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


def ligne(x1, y1, x2, y2, trait=GRIS):
    e = _base(x1, y1, abs(x2 - x1), abs(y2 - y1), type="line", strokeColor=trait,
              points=[[0, 0], [x2 - x1, y2 - y1]], lastCommittedPoint=None,
              startBinding=None, endBinding=None, startArrowhead=None, endArrowhead=None)
    elements.append(e)
    return e


def texte(x, y, contenu, taille=16, police=MANUSCRITE, couleur=ENCRE, align="left"):
    lignes = contenu.split("\n")
    w = max(len(l) for l in lignes) * taille * (LARGEUR_CAR if police == MONO else 0.55)
    h = len(lignes) * taille * INTERLIGNE
    e = _base(x, y, w, h, type="text", strokeColor=couleur, text=contenu,
              fontSize=taille, fontFamily=police, textAlign=align,
              verticalAlign="top", containerId=None, originalText=contenu,
              lineHeight=INTERLIGNE, autoResize=True)
    elements.append(e)
    return e


def _ligne(cellules, largeurs, sep=" │ "):
    """Une ligne de tableau calée au caractère. Négatif = aligné à droite."""
    out = []
    for valeur, largeur in zip(cellules, largeurs):
        s = str(valeur)
        out.append(s.rjust(-largeur) if largeur < 0 else s.ljust(largeur))
    return sep.join(out)


def tableau(x, y, entetes, lignes_data, largeurs, taille=13):
    """Rend un tableau et renvoie l'ordonnée du bas."""
    corps = [_ligne(entetes, [abs(l) for l in largeurs])]
    corps.append("─┼─".join("─" * abs(l) for l in largeurs))
    for r in lignes_data:
        corps.append(_ligne(r, largeurs))
    bloc = "\n".join(corps)
    e = texte(x, y, bloc, taille=taille, police=MONO)
    return y + e["height"]


def fenetre(x, y, w, h, titre, sous_titre, chemin, filtres):
    """Cadre d'écran : barre de titre, chemin, chips de filtre."""
    rect(x, y, w, h, trait=ENCRE, epaisseur=2)
    rect(x, y, w, 34, fond=BLEU_PALE, trait=ENCRE, arrondi=False)
    texte(x + 14, y + 8, chemin, taille=14, couleur=GRIS)
    texte(x + 24, y + 54, titre, taille=26)
    texte(x + 24, y + 92, sous_titre, taille=15, couleur=GRIS)
    cx = x + 24
    for libelle, valeur in filtres:
        largeur = max(len(f"{libelle} : {valeur}") * 8 + 20, 90)
        rect(cx, y + 126, largeur, 30, fond="transparent", trait=GRIS)
        texte(cx + 10, y + 133, f"{libelle} : {valeur}", taille=13, couleur=GRIS)
        cx += largeur + 12
    return y + 178


def pense_bete(x, y, w, contenu, titre="À trancher avec M. Samir"):
    lignes = contenu.split("\n")
    h = 46 + len(lignes) * 13 * INTERLIGNE + 14
    rect(x, y, w, h, fond=JAUNE, trait="#f08c00", arrondi=False)
    texte(x + 14, y + 12, titre, taille=15, couleur="#8a5a00")
    texte(x + 14, y + 40, contenu, taille=13, couleur=ENCRE)
    return y + h


# ══════════════════ Écran 1 — SCRUM-9 ══════════════════
Y = 0
texte(0, Y, "SCRUM-9 — Production laitière par vache", taille=22, couleur=VERT)
Y += 44
bas = fenetre(0, Y, 1180, 700,
              "Rapport Périodique — Production",
              "Production jour par jour, avec les deux dénominateurs : VL (vaches en lactation) et VP (vaches présentes).",
              "hmd.agro  ›  Rapports  ›  Rapport Périodique",
              [("Date", "30/06/2026"), ("Période", "Mois"), ("Section", "Production"),
               ("Granularité", "Quinzaine"), ("Effectif", "Jour")])
L9 = [-19, -3, -3, -8, -6, -6, -5, -5, -9, -7, -6, -6]
bas = tableau(24, bas, 
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
note = texte(24, bas + 26,
      "①  VL et VP recalculés chaque jour depuis les vêlages, tarissements et sorties.\n"
      "②  Jour 5 — écart de 52 L affiché tel quel : l'anomalie se voit, elle n'est pas corrigée en silence.\n"
      "③  Jour 17 — bilan lait non saisi : cellules VIDES, jamais des zéros.\n"
      "④  Ligne TOTAL — moyennes pour VL/VP, sommes pour les litres, sur les seuls jours saisis.",
      taille=14)
pense_bete(24, note["y"] + note["height"] + 18, 640,
           "• Dénominateur de référence : L/VL ou L/VP ?\n"
           "• TB/TP : jours de contrôle laitier seulement ?\n"
           "• Seuil d'alerte sur l'écart : 50 L/jour ?\n"
           "• BLOQUANT — sans vêlage importé, VL = 0\n"
           "  sur les données réelles.")

# ══════════════════ Écran 2 — SCRUM-10 ══════════════════
Y = 900
texte(0, Y, "SCRUM-10 — Charges par atelier et coût du litre", taille=22, couleur=VERT)
Y += 44
bas = fenetre(0, Y, 1180, 900,
              "Rapport de Performance — Charges & Coût du Lait",
              "Les charges ventilées par atelier, puis le coût du lait poste par poste pour rapprochement comptable.",
              "hmd.agro  ›  Rapports  ›  Rapport de Performance",
              [("Date", "30/06/2026"), ("Période", "Mois"), ("Périmètre coût/L", "LAIT_QUOTE_PART")])
L10 = [-42, -12, -8, -12, -8]
bas = tableau(24, bas,
    ["Indicateur", "Valeur", "Unité", "M-1", "Δ %"],
    [["── CHARGES PAR ATELIER ──", "", "", "", ""],
     ["Lait — Troupeau Laitier", "62 620.00", "DT", "60 910.00", "+2.8"],
     ["Culture Fourragère & Traction", "21 350.00", "DT", "20 780.00", "+2.7"],
     ["Génisses & Élevage", "12 780.00", "DT", "12 410.00", "+3.0"],
     ["Frais Généraux", "9 840.00", "DT", "9 620.00", "+2.3"],
     ["Frigorifique", "4 260.00", "DT", "3 990.00", "+6.8"],
     ["Non imputé — écriture sans atelier ⚠", "1 250.00", "DT", "720.00", "+73.6"],
     ["TOTAL ventilé = Charges Totales", "112 100.00", "DT", "108 430.00", "+3.4"],
     ["", "", "", "", ""],
     ["── COÛT DU LAIT (DÉTAIL) ──", "", "", "", ""],
     ["Ration & Aliments (601)", "41 260.00", "DT", "39 880.00", "+3.5"],
     ["Santé & Vétérinaire (602)", "3 180.00", "DT", "2 940.00", "+8.2"],
     ["Mécanique — Entretien (615)", "620.00", "DT", "480.00", "+29.2"],
     ["Personnel (64x)", "12 900.00", "DT", "12 900.00", "0.0"],
     ["Amortissements (68x)", "3 860.00", "DT", "3 860.00", "0.0"],
     ["Charges financières (66x)", "800.00", "DT", "850.00", "−5.9"],
     ["Autres charges d'exploitation", "0.00", "DT", "0.00", "–"],
     ["Sous-total — charges directes Lait", "62 620.00", "DT", "60 910.00", "+2.8"],
     ["Quote-part Frais Gén. — clé 61.98 %", "6 099.23", "DT", "5 962.40", "+2.3"],
     ["TOTAL retenu pour le coût du litre", "68 719.23", "DT", "66 872.40", "+2.8"],
     ["Rappel — non imputé exclu du coût/L ⚠", "1 250.00", "DT", "720.00", "+73.6"],
     ["", "", "", "", ""],
     ["── COÛTS UNITAIRES ──", "", "", "", ""],
     ["Coût Alimentaire / L", "0.908", "DT/L", "0.895", "+1.5"],
     ["Coût Mécanique / L (vue analytique)", "0.060", "DT/L", "0.044", "+36.4"],
     ["Coût Complet / L (Lait + quote-part)", "1.512", "DT/L", "1.501", "+0.7"],
     ["Coût du Litre hors Amortissement", "1.427", "DT/L", "1.414", "+0.9"],
     ["IOFC — CA Lait − Coût Alimentaire", "8 682.20", "DT", "8 210.00", "+5.8"],
     ["IOFC / Vache Lactante / Jour", "3.01", "DT/VL/j", "2.87", "+4.9"]],
    L10)
texte(780, Y + 178,
      "①  Les écritures sont enfin lues avec leur\n    centre de coût.\n\n"
      "②  « Non imputé » s'affiche même à zéro :\n    une ligne absente se lit « rien à signaler »,\n"
      "    une ligne à 0 se lit « vérifié ».\n\n"
      "③  Le total se recompte à l'écran et passe\n    au rouge s'il diverge.\n\n"
      "④  La clé de quote-part est écrite en\n    toutes lettres.",
      taille=14)
pense_bete(780, Y + 470, 380,
           "• Nom exact du centre « frigénerie »\n"
           "• Clé de quote-part : charges directes ou litres ?\n"
           "• Périmètre officiel du coût du litre\n"
           "• Saisie d'une charge répartie en % entre ateliers\n"
           "  (Cost Center Allocation — natif ERPNext, non activé)")

# ══════════════════ Écran 3 — SCRUM-11 ══════════════════
Y = 2000
texte(0, Y, "SCRUM-11 — Interventions mécaniques et entretien préventif", taille=22, couleur=VERT)
Y += 44
bas = fenetre(0, Y, 1500, 660,
              "Rapport des Interventions",
              "Ce qui a été fait sur le mois, ce qui arrive sous 30 jours, et le rapprochement avec le compte 615.",
              "hmd.agro  ›  Rapports  ›  Rapport des Interventions",
              [("Date", "30/06/2026"), ("Période", "Mois"), ("Équipement", "Tous"), ("Atelier", "Tous")])
L11 = [-14, -10, -18, -25, -10, -33, -18, -17, -9, -6, -6]
bas = tableau(24, bas,
    ["Section", "Date", "Équipement", "Désignation", "Type", "Libellé", "Atelier",
     "Intervenant", "Coût", "Nb I.", "Nb É."],
    [["Réalisées", "06/06/2026", "ACC-ASS-2026-00003", "Tracteur Massey 385", "PRÉVENT.",
      "Vidange moteur + filtres", "Culture Fourragère", "Atelier Ben Salah", "340.00", "", ""],
     ["Réalisées", "11/06/2026", "ACC-ASS-2026-00007", "Tank à lait 3000 L", "CURATIVE",
      "Remplacement sonde température", "Lait — Troupeau", "Frigotech", "620.00", "", ""],
     ["Réalisées", "18/06/2026", "ACC-ASS-2026-00012", "Groupe électrogène 60 kVA", "PRÉVENT.",
      "Contrôle 250 h + filtre à air", "Frais Généraux", "Interne", "180.00", "", ""],
     ["Réalisées", "23/06/2026", "ACC-ASS-2026-00003", "Tracteur Massey 385", "CURATIVE",
      "Réparation circuit hydraulique", "Culture Fourragère", "Atelier Ben Salah", "1480.00", "", ""],
     ["Réalisées", "27/06/2026", "ACC-ASS-2026-00019", "Remorque épandeuse", "PRÉVENT.",
      "Graissage + contrôle pneus", "Culture Fourragère", "Interne", "95.00", "", ""],
     ["Réalisées", "", "", "", "", "TOTAL — 5 interv. / 4 équipements", "", "", "2715.00", "5", "4"],
     ["", "", "", "", "", "", "", "", "", "", ""],
     ["Préventif 30j", "28/06/2026", "ACC-ASS-2026-00016", "Pompe à vide traite", "EN RETARD",
      "Contrôle mensuel de dépression", "Lait — Troupeau", "", "", "", ""],
     ["Préventif 30j", "05/07/2026", "ACC-ASS-2026-00003", "Tracteur Massey 385", "À VENIR",
      "Vidange 500 h", "Culture Fourragère", "", "", "", ""],
     ["Préventif 30j", "14/07/2026", "ACC-ASS-2026-00007", "Tank à lait 3000 L", "À VENIR",
      "Nettoyage du condenseur", "Lait — Troupeau", "", "", "", ""],
     ["", "", "", "", "", "", "", "", "", "", ""],
     ["Rapprochem.", "", "", "", "", "Entretien au Grand Livre (615)", "", "", "2715.00", "", ""],
     ["Rapprochem.", "", "", "", "", "Somme des interventions saisies", "", "", "2715.00", "", ""],
     ["Rapprochem.", "", "", "", "", "Écart — aucun : tout est rattaché", "", "", "0.00", "", ""]],
    L11, taille=11)
note = texte(24, bas + 24,
      "①  Nb Interventions et Nb Équipements sont des COLONNES, pas une phrase dans le libellé : ce qui s'exporte se compare.\n"
      "②  Une échéance dépassée s'affiche en rouge et reste dans la liste — c'est celle-là qu'il faut voir.\n"
      "③  Le rapprochement au compte 615 est fait par le rapport, pas découvert à la clôture.",
      taille=14)
pense_bete(24, note["y"] + note["height"] + 18, 640,
           "• Fenêtre du préventif : 30 jours ?\n"
           "• Déclencheurs : jours / heures de marche /\n  fréquence ?\n"
           "• Statuts : prêt à partir / à vérifier / en panne\n"
           "• Distinguer main-d'œuvre et pièces ?")

SORTIE.write_text(json.dumps({
    "type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
    "files": {},
}, ensure_ascii=False, indent=1), encoding="utf-8")
print("écrit :", SORTIE, SORTIE.stat().st_size, "octets —", len(elements), "éléments")
