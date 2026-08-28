"""Rend `maquettes_2026-08-26.excalidraw` en une page HTML lisible sans Excalidraw,
paginée pour le PDF : une planche par page A4 paysage, rien de coupé.

Les découpes ne sont pas écrites à la main : elles se déduisent des repères de
la scène — les titres d'écran (taille 22), les intertitres « LA SAISIE » et les
pastilles numérotées des gestes (taille 16). Les gestes sont regroupés par page
tant que la planche tient dans la hauteur imprimable. Régénérer la maquette
suffit ; la page suit.

PDF : "Google Chrome" --headless=new --no-pdf-header-footer
      --print-to-pdf=maquettes_2026-08-26.pdf maquettes_2026-08-26.html
"""
import sys
from pathlib import Path

RACINE = Path("/Users/momoslim/Desktop/hmd_agro-main")
sys.path.insert(0, str(RACINE))
import outils_maquette_svg as M                                    # noqa: E402

SCENE = RACINE / "maquettes_2026-08-26.excalidraw"
SORTIE = RACINE / "maquettes_2026-08-26.html"
E = M.charger(SCENE)

X0 = min(M.cadre(e)[0] for e in E) - 16
X1 = max(M.cadre(e)[2] for e in E) + 16
FIN = max(M.cadre(e)[3] for e in E) + 24

# ── La page imprimée : A4 paysage, en millimètres ──
PAGE_L, PAGE_H = 297, 210
MARGE = 8                       # marge d'impression
BANDEAU = 22                    # titre + légende au-dessus de la planche
FIG_L = PAGE_L - 2 * MARGE      # 281 mm de large pour la planche
FIG_H = PAGE_H - 2 * MARGE - BANDEAU   # 172 mm de haut
TOLERANCE = 0.87                # on remplit la page tant que la planche garde ≥ 87 % de la pleine largeur
                                # (assez pour que les cadres décidé / ouvert rejoignent la dernière planche de gestes)


def repere(debut, k=1):
    """Ordonnée du k-ième texte commençant par `debut`."""
    vus = 0
    for e in E:
        if e["type"] == "text" and e["text"].startswith(debut):
            vus += 1
            if vus == k:
                return e["y"]
    raise KeyError((debut, k))


def geste(n, apres=0):
    """Ordonnée de la première pastille numérotée n située sous `apres`."""
    ys = sorted(e["y"] for e in E
                if e["type"] == "text" and e["text"] == str(n) and e["fontSize"] == 16 and e["y"] > apres)
    if not ys:
        raise KeyError((n, apres))
    return ys[0]


def etendue(y0, y1):
    """Bornes horizontales réelles de ce qui se trouve entre y0 et y1."""
    boites = [M.cadre(e) for e in E if M.cadre(e)[3] > y0 and M.cadre(e)[1] < y1]
    return min(b[0] for b in boites) - 16, max(b[2] for b in boites) + 16


s10, s11, s9 = repere("SCRUM-10"), repere("SCRUM-11"), repere("SCRUM-9")
saisie, saisie2 = repere("LA SAISIE —"), repere("LA SAISIE DES INTERVENTIONS")
variante = repere("ET SI LA FACTURE")
decide, decide2 = repere("Décidé le 26/08/2026"), repere("Décidé le 26/08/2026", 2)


def paginer(blocs, largeur):
    """Regroupe des blocs consécutifs (y0, y1, numéro, résumé) tant que la planche tient."""
    hmax = FIG_H / (TOLERANCE * FIG_L / largeur)
    pages, courante = [], []
    for b in blocs:
        if courante and sum(x[1] - x[0] for x in courante) + (b[1] - b[0]) > hmax:
            pages.append(courante)
            courante = []
        courante.append(b)
    if courante:
        pages.append(courante)
    return pages


def planches_saisie(ecran, debut, gestes, fin, exemple, suites=()):
    """Les pages du volet saisie d'un écran : un titre et une légende déduits des gestes présents.

    `suites` : les blocs qui suivent les gestes — (y, résumé, complément de titre, titre s'il est seul) —
    par exemple la variante à plusieurs lignes, puis les cadres décidé / ouvert. Ils rejoignent la
    dernière planche de gestes quand elle a la place, sinon ils font leur propre page.
    """
    bornes = [geste(n, debut) - 14 for n in range(1, len(gestes) + 1)]
    bornes += [s[0] for s in suites] + [fin]
    blocs = [(debut, bornes[0], None, None, None, None)]
    for i, (n, resume) in enumerate(gestes):
        blocs.append((bornes[i], bornes[i + 1], n, resume, None, None))
    for j, (y, resume, complement, seul) in enumerate(suites):
        k = len(gestes) + j
        blocs.append((bornes[k], bornes[k + 1], None, resume, complement, seul))
    x0, x1 = etendue(debut, fin)
    pages = []
    for grp in paginer(blocs, x1 - x0):
        nums = [b[2] for b in grp if b[2] is not None]
        complements = [b[4] for b in grp if b[4]]
        if nums:
            titre = "Écran %d — la saisie, geste %d" % (ecran, nums[0]) if len(nums) == 1 \
                else "Écran %d — la saisie, gestes %d à %d" % (ecran, nums[0], nums[-1])
            if complements:
                titre += ", " + ", ".join(complements[:-1]) + (", " if len(complements) > 1 else "") \
                    + "et " + complements[-1]
        else:
            suite = [b for b in grp if b[5]]
            parts = [suite[0][5]] + [b[4] for b in suite[1:]]
            titre = "Écran %d — %s" % (ecran, parts[0] if len(parts) == 1
                                       else ", ".join(parts[:-1]) + ", et " + parts[-1])
        legende = " ; ".join(("%s %s" % (CHIFFRES[b[2]], b[3])) if b[2] is not None else b[3]
                             for b in grp if b[3])
        legende = legende[0].upper() + legende[1:] + "."
        if grp[0][2] is None and grp[0][3] is None:
            legende += " " + exemple
        pages.append((titre, legende, grp[0][0], grp[-1][1], (x0, x1)))
    return pages


CHIFFRES = {1: "①", 2: "②", 3: "③", 4: "④", 5: "⑤", 6: "⑥", 7: "⑦", 8: "⑧"}

GESTES_1 = [
    (1, "il ouvre une facture d'achat"),
    (2, "il saisit la ligne — 616, centre de coût Frais Généraux"),
    (3, "le bloc « Répartition par atelier » apparaît, vide"),
    (4, "il ajoute les ateliers et leurs pourcentages"),
    (5, "il enregistre — refusé à 80 %, accepté à 100 %, puis Soumettre et le Grand Livre"),
    (6, "le mois suivant, il duplique la facture : la répartition est déjà là"),
    (7, "le rapport lit la répartition"),
]
GESTES_2 = [
    (1, "le chef de parc déclare la panne — la machine passe « En panne »"),
    (2, "la réparation faite, il complète la fiche et la soumet — la machine repasse « Prêt »"),
    (3, "le comptable saisit la facture du réparateur et la rattache à la fiche"),
    (4, "refaire un graissage tient en un Dupliquer"),
    (5, "planifier la prochaine vidange : une fiche « À venir »"),
    (6, "supprimer une erreur : le brouillon s'efface, la fiche soumise s'annule"),
    (7, "les heures du tractoriste, chaque soir"),
    (8, "ce que le rapport en fait, ligne par ligne"),
]


def planche(titre, legende, y0, y1):
    return (titre, legende, y0, y1, etendue(y0, y1))


VUES = [
    planche("Écran 1 — SCRUM-10, le rapport",
            "Les charges rangées par atelier, les frais généraux répartis charge par charge, "
            "et le coût du litre qui en découle.",
            s10 - 12, saisie - 2),
    *planches_saisie(1, saisie - 2, GESTES_1, s11 - 120,
                     "L'exemple suivi : l'assurance de juin, 1 900 DT — 45 % Lait, 35 % Cultures, 20 % Génisses.",
                     suites=[(variante - 14, "le cas de la facture à plusieurs lignes — ses trois gardiens",
                              "la facture à plusieurs lignes", "la facture à plusieurs lignes"),
                             (decide - 14, "enfin le cadre vert, décidé le 26/08, et le jaune, à trancher",
                              "ce qui reste ouvert", "ce qui a été décidé, ce qui reste ouvert")]),
    planche("Écran 2 — SCRUM-11, le rapport",
            "L'état du parc, les interventions faites, celles qui arrivent sous 30 jours, "
            "et le rapprochement au compte 615.",
            s11 - 12, saisie2 - 2),
    *planches_saisie(2, saisie2 - 2, GESTES_2, s9 - 120,
                     "L'exemple suivi : la panne hydraulique du Massey 385, réparée le 23/06.",
                     suites=[(decide2 - 14, "enfin le cadre vert, décidé le 26/08, et le jaune, à trancher — "
                              "d'abord : qui écrit au 615, la facture ou la fiche",
                              "ce qui reste ouvert", "ce qui a été décidé, ce qui reste ouvert")]),
    planche("Écran 3 — SCRUM-9, annulée",
            "La production laitière ne sera pas construite : l'US a été annulée le 26/08. "
            "À droite, les deux questions qui lui survivent.",
            s9 - 12, FIN),
]

TETE = """<title>Maquettes reprises — 26/08/2026</title>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root{
  --ground:#F6F7F4; --surface:#FFFFFF; --ink:#18201A; --ink-2:#5A665C; --ink-3:#7E8A80;
  --line:#D9DFD7; --accent:#2E6B4F; --warn:#8E6211; --crit:#9C2F27; --info:#1F5C8C;
  --paper:#FFFFFF;
  --shadow:0 1px 2px rgba(24,32,26,.06), 0 10px 30px -20px rgba(24,32,26,.35);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#121613; --surface:#191F1B; --ink:#E6EDE6; --ink-2:#9BA89D; --ink-3:#7C887F;
    --line:#2B342E; --accent:#7BC49E; --warn:#D5A257; --crit:#E08B81; --info:#7FB4DE;
    --paper:#F8F9F6;
  }
}
:root[data-theme="dark"]{
  --ground:#121613; --surface:#191F1B; --ink:#E6EDE6; --ink-2:#9BA89D; --ink-3:#7C887F;
  --line:#2B342E; --accent:#7BC49E; --warn:#D5A257; --crit:#E08B81; --info:#7FB4DE;
  --paper:#F8F9F6;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
     font:400 16px/1.6 "IBM Plex Sans",system-ui,sans-serif;
     -webkit-font-smoothing:antialiased}
.wrap{max-width:1360px;margin:0 auto;padding:56px 24px 96px}
header{border-bottom:1px solid var(--line);padding-bottom:28px;margin-bottom:28px}
h1{font:600 34px/1.2 Fraunces,Georgia,serif;margin:0 0 10px;letter-spacing:-.01em}
.sous{color:var(--ink-2);max-width:74ch;margin:0}
.date{font:500 12px/1 "IBM Plex Mono",monospace;letter-spacing:.09em;
      text-transform:uppercase;color:var(--accent);margin:0 0 14px}
.couverture{margin:0 0 52px}
.sommaire{margin:0 0 24px;padding:0;list-style:none;columns:2;column-gap:40px;max-width:1100px}
.sommaire li{break-inside:avoid;display:flex;justify-content:space-between;gap:12px;
             padding:5px 0;border-bottom:1px dotted var(--line);font-size:14.5px}
.sommaire a{color:var(--ink);text-decoration:none}
.sommaire .no{font-family:"IBM Plex Mono",monospace;color:var(--ink-3);font-size:12.5px}
.sommaire h3{column-span:all;font:600 12px/1 "IBM Plex Mono",monospace;letter-spacing:.09em;
             text-transform:uppercase;color:var(--ink-3);margin:0 0 10px}
.note{color:var(--ink-3);font-size:13.5px;max-width:90ch;margin:0}
section.page{margin:0 0 52px;position:relative}
h2{font:600 21px/1.3 Fraunces,Georgia,serif;margin:0 0 6px}
.leg{color:var(--ink-2);font-size:14.5px;margin:0 0 16px;max-width:110ch}
figure{margin:0;background:var(--paper);border:1px solid var(--line);border-radius:10px;
       box-shadow:var(--shadow);overflow:hidden}
svg.maq{display:block;width:100%;height:auto}
.folio{display:none}
.f-hand{font-family:Fraunces,Georgia,serif}
.f-mono{font-family:"IBM Plex Mono",ui-monospace,monospace}
text{white-space:pre}
.t-ink{fill:#18201A}.t-ink2{fill:#5A665C}.t-ok{fill:#2E6B4F}
.t-warn{fill:#B4650F}.t-crit{fill:#9C2F27}.t-info{fill:#1F5C8C}
.s-ink{stroke:#18201A}.s-ink2{stroke:#8A968C}.s-ok{stroke:#2E6B4F}
.s-warn{stroke:#B4650F}.s-crit{stroke:#9C2F27}.s-info{stroke:#1F5C8C}
.fill-none{fill:none}.fill-paper{fill:#FFFFFF}.fill-info{fill:#E8F0F7}
.fill-ok{fill:#E2EDE6}.fill-warn{fill:#F7EEDA}
rect{stroke-linejoin:round}path{stroke-linecap:round;fill:none}
.cx-maq circle{fill:none;stroke:#18201A;stroke-width:1}
.cx-maq text{fill:#18201A;font-family:"IBM Plex Sans",sans-serif}
footer{border-top:1px solid var(--line);padding-top:22px;color:var(--ink-3);font-size:13.5px}
@page{size:@@PL@@mm @@PH@@mm;margin:@@MARGE@@mm}
@media print{
  html,body{background:#fff;color:#18201A}
  .wrap{max-width:none;padding:0;margin:0}
  .couverture,section.page{height:@@HP@@mm;overflow:hidden;margin:0;
                           break-after:page;page-break-after:always}
  section.page:last-of-type{break-after:auto;page-break-after:auto}
  .couverture{padding-top:18mm}
  header{border:0;padding:0;margin:0 0 10mm}
  h1{font-size:26pt}
  .sous{font-size:11.5pt;max-width:150mm}
  .sommaire li{font-size:10.5pt;padding:1.6mm 0}
  .note{font-size:9.5pt;position:absolute;bottom:0;left:0}
  h2{font-size:15pt;margin:0 0 1.5mm}
  .leg{font-size:10.5pt;line-height:1.35;margin:0 0 3mm;max-width:none}
  figure{border:1px solid #D9DFD7;border-radius:0;box-shadow:none;width:fit-content;margin:0 auto}
  svg.maq{width:var(--pw);height:var(--ph)}
  .folio{display:block;position:absolute;bottom:0;right:0;font:400 8.5pt/1 "IBM Plex Mono",monospace;
         color:#7E8A80;letter-spacing:.04em}
  footer{display:none}
  a{color:inherit}
}
</style>
""".replace("@@PL@@", str(PAGE_L)).replace("@@PH@@", str(PAGE_H)) \
       .replace("@@MARGE@@", str(MARGE)).replace("@@HP@@", str(PAGE_H - 2 * MARGE - 2))


def dimensions(v):
    """Taille imprimée de la planche : elle tient dans FIG_L × FIG_H sans déformation."""
    _, _, y0, y1, (x0, x1) = v
    k = min(FIG_L / (x1 - x0), FIG_H / (y1 - y0))
    return (x1 - x0) * k, (y1 - y0) * k


N = len(VUES) + 1
corps = ['<div class="wrap"><section class="couverture" id="p1"><header>',
         '<p class="date">Maquettes · 26 août 2026</p>',
         '<h1>Ce que la réunion du 26/08 a changé</h1>',
         '<p class="sous">Deux écrans repris point par point d\'après vos remarques, '
         'et la troisième User Story annulée. '
         'Le changement principal porte sur les frais généraux : plus de clé unique ni de '
         'couple « dépenses / recettes », mais une répartition en pourcentages par atelier, '
         'saisie une fois sur la charge, dont le total doit faire 100 %. '
         'Les cadres verts rappellent ce qui est décidé, les jaunes ce qui reste ouvert.</p>',
         '</header><ol class="sommaire"><h3>Sommaire</h3>']
for i, v in enumerate(VUES, start=2):
    corps.append('<li><a href="#p%d">%s</a><span class="no">p. %d</span></li>' % (i, v[0], i))
corps.append('</ol><p class="note">Les pourcentages de répartition sont une illustration '
             'reprenant vos exemples, pas encore une donnée saisie. Généré depuis '
             '<code>maquettes_2026-08-26.excalidraw</code> — la scène Excalidraw reste la source.</p>'
             '<span class="folio">page 1 / %d</span></section>' % N)
for i, v in enumerate(VUES, start=2):
    titre, legende, y0, y1, (x0, x1) = v
    pw, ph = dimensions(v)
    corps.append('<section class="page" id="p%d"><h2>%s</h2><p class="leg">%s</p>'
                 '<figure style="--pw:%.1fmm;--ph:%.1fmm">%s</figure>'
                 '<span class="folio">page %d / %d</span></section>'
                 % (i, titre, legende, pw, ph, M.svg(E, (x0, y0, x1 - x0, y1 - y0), marge=0), i, N))
corps.append('<footer>Généré depuis <code>maquettes_2026-08-26.excalidraw</code> — '
             'la scène Excalidraw reste la source. Les pourcentages de répartition sont '
             'une illustration reprenant vos exemples, pas encore une donnée saisie.</footer></div>')

SORTIE.write_text(TETE + "".join(corps), encoding="utf-8")
print("écrit :", SORTIE, SORTIE.stat().st_size, "octets —", N, "pages")
for i, v in enumerate(VUES, start=2):
    pw, ph = dimensions(v)
    print("  p.%2d  %-62s  %4d × %4d  →  %3.0f × %3.0f mm" % (i, v[0], v[4][1] - v[4][0], v[3] - v[2], pw, ph))
