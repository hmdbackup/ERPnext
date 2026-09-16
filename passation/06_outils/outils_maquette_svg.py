"""Rend une scène Excalidraw (.excalidraw) en SVG inline, thémable et recadrable.

Les maquettes du 24/08/2026 n'emploient que trois primitives — rectangle, texte,
flèche — et deux polices : manuscrite (fontFamily 1) pour les libellés, chasse
fixe (fontFamily 3) pour les tableaux. Le rendu conserve les coordonnées de la
scène : recadrer une région revient à poser un `viewBox`.

Les couleurs de la scène sont traduites en classes CSS pour que la maquette
suive le thème clair / sombre de la présentation au lieu d'imposer le sien.
"""
import json
from pathlib import Path

# ── traduction des couleurs de la scène vers les jetons de la présentation ──
TRAIT = {
    "#1e1e1e": "s-ink", "#5c5f66": "s-ink2", "#2f9e44": "s-ok",
    "#e8590c": "s-warn", "#c92a2a": "s-crit", "#1971c2": "s-info",
}
ENCRE = {
    "#1e1e1e": "t-ink", "#5c5f66": "t-ink2", "#2f9e44": "t-ok",
    "#e8590c": "t-warn", "#c92a2a": "t-crit", "#1971c2": "t-info",
}
FOND = {
    "transparent": "fill-none", "#e7f5ff": "fill-info",
    "#ebfbee": "fill-ok", "#fff3bf": "fill-warn", "#ffffff": "fill-paper",
}
CERCLES = "①②③④⑤⑥⑦⑧⑨"
LARGEUR_CAR_MONO = 0.60          # même hypothèse que les scripts de fabrique


def charger(chemin):
    return json.load(open(chemin, encoding="utf-8"))["elements"]


def cadre(e):
    """Boîte englobante d'un élément, flèches comprises."""
    if e["type"] == "arrow":
        xs = [e["x"] + p[0] for p in e["points"]]
        ys = [e["y"] + p[1] for p in e["points"]]
        return min(xs), min(ys), max(xs), max(ys)
    return e["x"], e["y"], e["x"] + e["width"], e["y"] + e["height"]


def _echappe(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _rect(e, out):
    r = 0
    if e.get("roundness"):
        r = min(32, min(e["width"], e["height"]) * 0.25)
    cl = "%s %s" % (FOND.get(e["backgroundColor"], "fill-none"),
                    TRAIT.get(e["strokeColor"], "s-ink"))
    out.append(
        '<rect class="%s" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" '
        'stroke-width="%s"/>' % (cl, e["x"], e["y"], e["width"], e["height"], r,
                                 e.get("strokeWidth", 1)))


def _texte(e, out):
    fs = e["fontSize"]
    lh = e.get("lineHeight", 1.25)
    mono = e["fontFamily"] == 3
    police = "f-mono" if mono else "f-hand"
    cl = "%s %s" % (ENCRE.get(e["strokeColor"], "t-ink"), police)
    lignes = e["text"].split("\n")
    marqueurs = []
    tspans = []
    for i, ligne in enumerate(lignes):
        base = e["y"] + (i + 1) * lh * fs - 0.30 * fs
        if mono:
            # Les pastilles ① ② ③ sont dessinées : un glyphe de repli casserait
            # l'alignement des colonnes du tableau.
            cw = fs * LARGEUR_CAR_MONO
            propre = []
            for j, c in enumerate(ligne):
                if c in CERCLES:
                    marqueurs.append((e["x"] + j * cw + cw / 2,
                                      base - 0.34 * fs, CERCLES.index(c) + 1, fs))
                    propre.append(" ")
                else:
                    propre.append(c)
            ligne = "".join(propre)
        if ligne.strip() == "":
            continue
        tspans.append('<tspan x="%.1f" y="%.1f">%s</tspan>'
                      % (e["x"], base, _echappe(ligne)))
    if tspans:
        out.append('<text class="%s" font-size="%d" xml:space="preserve">%s</text>'
                   % (cl, fs, "".join(tspans)))
    for cx, cy, n, fs_ in marqueurs:
        out.append('<g class="cx-maq"><circle cx="%.1f" cy="%.1f" r="%.1f"/>'
                   '<text x="%.1f" y="%.1f" font-size="%.1f" text-anchor="middle">%d</text></g>'
                   % (cx, cy, fs_ * 0.46, cx, cy + fs_ * 0.24, fs_ * 0.66, n))


def _fleche(e, out):
    pts = [(e["x"] + p[0], e["y"] + p[1]) for p in e["points"]]
    if len(pts) < 2:
        return
    cl = TRAIT.get(e["strokeColor"], "s-ink")
    if len(pts) == 2:
        d = "M %.1f %.1f L %.1f %.1f" % (pts[0][0], pts[0][1], pts[1][0], pts[1][1])
        ax, ay = pts[0]
    else:
        d = "M %.1f %.1f Q %.1f %.1f %.1f %.1f" % (
            pts[0][0], pts[0][1], pts[1][0], pts[1][1], pts[2][0], pts[2][1])
        ax, ay = pts[-2]
    out.append('<path class="%s fill-none" d="%s" stroke-width="%s"/>'
               % (cl, d, e.get("strokeWidth", 1)))
    if e.get("endArrowhead"):
        bx, by = pts[-1]
        dx, dy = bx - ax, by - ay
        n = (dx * dx + dy * dy) ** 0.5 or 1
        dx, dy = dx / n, dy / n
        L = 13
        for ang in (2.6, -2.6):
            import math
            cs, sn = math.cos(ang), math.sin(ang)
            out.append('<path class="%s fill-none" d="M %.1f %.1f L %.1f %.1f" '
                       'stroke-width="%s"/>'
                       % (cl, bx, by, bx + L * (dx * cs - dy * sn),
                          by + L * (dx * sn + dy * cs), e.get("strokeWidth", 1)))


def svg(elements, boite, fleches=True, papier=True, marge=10):
    """`boite` = (x, y, largeur, hauteur) en coordonnées de scène."""
    bx, by, bw, bh = boite
    bx -= marge; by -= marge; bw += 2 * marge; bh += 2 * marge
    out = []
    if papier:
        out.append('<rect class="fill-paper" x="%.1f" y="%.1f" width="%.1f" height="%.1f"/>'
                   % (bx, by, bw, bh))
    for e in elements:
        if e.get("isDeleted"):
            continue
        x0, y0, x1, y1 = cadre(e)
        if e["type"] == "arrow":
            if not fleches:
                continue
            # une flèche n'est gardée que si elle tient entièrement dans le cadrage :
            # un trait qui entre par le bord sans son commentaire ne veut plus rien dire
            if not (x0 >= bx and x1 <= bx + bw and y0 >= by and y1 <= by + bh):
                continue
        elif x1 < bx or x0 > bx + bw or y1 < by or y0 > by + bh:
            continue
        if e["type"] == "rectangle":
            _rect(e, out)
        elif e["type"] == "text":
            _texte(e, out)
        elif e["type"] == "arrow":
            _fleche(e, out)
    return ('<svg class="maq" viewBox="%.1f %.1f %.1f %.1f" '
            'preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" '
            'role="img">%s</svg>' % (bx, by, bw, bh, "".join(out)))


def union(elements, predicat, marge=0):
    """Boîte englobante des éléments retenus par `predicat`."""
    boites = [cadre(e) for e in elements if predicat(e)]
    x0 = min(b[0] for b in boites); y0 = min(b[1] for b in boites)
    x1 = max(b[2] for b in boites); y1 = max(b[3] for b in boites)
    return (x0 - marge, y0 - marge, x1 - x0 + 2 * marge, y1 - y0 + 2 * marge)


if __name__ == "__main__":
    els = charger(Path(__file__).resolve().parents[2] / "passation/03_maquettes/maquettes_validees_2026-08-24.excalidraw")
    s = svg(els, (0, 66, 1460, 940))
    Path("/tmp/essai_maquette.svg").write_text(
        '<?xml version="1.0"?>' + s.replace('class="maq"', 'class="maq" style="background:#fff"'),
        encoding="utf-8")
    print("essai écrit — %d caractères" % len(s))
