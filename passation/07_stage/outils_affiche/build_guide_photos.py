"""Guide oral de l'affiche de stage, partie par partie (10 min de parole,
questions du jury en plus, hors chrono). Une partie = une zone de l'affiche ;
chaque bloc de la partie a son temps, son texte à dire, quoi montrer, la
question probable. Écrit conducteur_affiche_photos.html à la racine du dépôt."""
import base64
import html
from pathlib import Path

HERE = Path(__file__).parent
PHOTOS = HERE / "photos"
OUT = HERE.parent / "conducteur_affiche_photos.html"


def b64(name):
    if not name:
        return None
    mime = "image/png" if name.endswith("png") else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode((PHOTOS / name).read_bytes()).decode()


# PARTIES : (titre de la partie, où sur l'affiche, [blocs])
# bloc : (photo, minutes, bloc de l'affiche, texte à dire, montrer, question probable)
PARTIES = [
    ("En-tête", "Bandeau du haut : titre, nom, dates, superviseur", [
        (None, 0.5, "Titre et bandeau",
         """Bonjour à tous. Moi c'est Mohamed Slim, étudiant au bac en informatique à l'Université Laval. Cet été, j'ai fait mon premier stage en informatique, trois mois chez HMD AGRO, une ferme laitière tunisienne, comme développeur ERP, sous la supervision d'Aymen Zarrad. En dix minutes, je vais suivre l'affiche dans l'ordre : le contexte à gauche, le système en images à droite, et ce que j'en retiens à la fin.""",
         "Le titre, ton nom, les dates.",
         "« C'est quoi un ERP ? » — « Un logiciel de gestion intégré : comptabilité, stock, paie, actifs dans une seule base. Ici, adapté à une ferme. »"),
    ]),

    ("1. Introduction", "Colonne gauche, en haut : Étudiant / Entreprise", [
        (None, 1.0, "Étudiant et entreprise",
         """Ce qui me plaît en informatique, c'est de prendre un vrai métier et de le traduire en modèle de données — et la comptabilité d'un élevage laitier, je n'y connaissais rien en arrivant. HMD AGRO, c'est la ferme Borj Essebai, à Mateur, près de Bizerte, avec un troupeau laitier réparti en cinq ateliers comptables : lait, cultures et fourrage, génisses, traction, frais généraux. Avant mon arrivée, tout se gérait sur Excel, des fichiers qui ne se croisaient jamais — impossible de répondre à « combien coûte un litre de lait ? ». La ferme a donc choisi de passer sur ERPNext, un ERP open source bâti sur Frappe, un framework web en Python.""",
         "Compter les cinq ateliers sur les doigts, puis les logos ERPNext / Frappe.",
         "« Pourquoi ERPNext plutôt qu'un logiciel agricole ? » — « Open source, complet côté comptabilité, extensible en Python. »"),
    ]),

    ("2. Mandats et objectifs", "Colonne gauche, deuxième cadre", [
        (None, 0.75, "Mandats et objectifs",
         """Mon mandat, c'était tout le volet finance : la comptabilité analytique avec un plan tunisien, chaque écriture rattachée à un atelier, la facturation du lait, la paie, les amortissements, la répartition des frais généraux, et les indicateurs de pilotage pour le gérant. Le fil rouge : tout doit découler des saisies quotidiennes, sans ressaisie. Côté objectifs personnels : maîtriser Frappe et ERPNext, pratiquer le Scrum avec un vrai client, et livrer quelque chose de fiable, testé, utilisé chaque jour par la ferme — pas un prototype qui finit dans un tiroir.""",
         "Les bullets « Mandats » puis « Objectifs ».",
         "« Objectif atteint ? » — « Le module finance est en production à la ferme. »"),
    ]),

    ("3. Travail réalisé", "Colonne gauche, grand cadre du bas : bullets, plan comptable, cheptel", [
        (None, 0.75, "Les neuf lignes du travail réalisé",
         """Voilà ce que j'ai livré, en résumé. Le socle comptable tunisien : 77 comptes, cinq centres de coûts. Les consommations d'aliments valorisées au coût moyen pondéré. La facturation du lait selon une grille de qualité. Le cheptel et le matériel immobilisés, avec leurs amortissements. La paie ventilée par atelier. Les frais généraux répartis au Grand Livre par une clé. Et les rapports de pilotage : coût du litre, excédent brut, marge sur coût alimentaire. Le tout couvert par 521 tests automatisés, tous verts.""",
         "Parcourir les bullets du doigt, s'arrêter sur « 521 tests ».",
         "« Tout ça en trois mois ? » — « Avec un ERP qui fait déjà beaucoup. Mon travail, c'est le métier de la ferme par-dessus. »"),
        ("108.jpg", 0.75, "Capture : plan comptable tunisien dans ERPNext",
         """On commence par le socle : le plan comptable tunisien, 77 comptes, les classes 6 et 7 — charges et produits — et cinq centres de coûts, un par atelier. Chaque écriture porte son atelier, ce qui permet un coût par atelier, et donc un coût par litre. Tout est versionné dans le dépôt, en fixtures et migrations : on peut réinstaller le site de zéro et retrouver exactement le même plan, construit avec le comptable de la ferme.""",
         "Les classes de comptes dans l'arbre.",
         "« C'est standard ERPNext ? » — « Le mécanisme oui, le plan tunisien et les centres de coûts, c'est moi. »"),
        ("121.jpg", 0.75, "Capture : le cheptel immobilisé, vache par vache",
         """Ma capture préférée : chaque vache est une immobilisation à l'actif comptable, individuellement. Une vache vaut plusieurs milliers de dinars, produit pendant quatre ou cinq lactations, puis est réformée — donc elle s'amortit sur sa carrière laitière, et cet amortissement entre dans le coût du litre. Une génisse, elle, capitalise ce qu'elle coûte à élever, et bascule à l'actif comme vache à son premier vêlage. Le vacher saisit un vêlage, le comptable retrouve une immobilisation — automatiquement.""",
         "La liste des vaches, le statut d'amortissement.",
         "« Le vacher sait que ça fait de la comptabilité ? » — « Non, et c'est le but. »"),
    ]),

    ("Le système en images", "Colonne droite, les quatre rangées de captures", [
        ("114.jpg", 1.25, "Indicateurs colorés et coût de revient du litre",
         """Là, c'est le rapport que le gérant ouvre chaque mois : chaque indicateur est comparé à un seuil configurable — vert, orange, rouge — et c'est le gérant lui-même qui ajuste ces seuils, sans développeur. À côté, le chiffre central du stage : le coût réel d'un litre de lait. Il se construit par étages — l'aliment au coût moyen pondéré, la paie et les charges patronales, les soins vétérinaires, l'amortissement des vaches et du matériel, une part des frais généraux — le tout divisé par les litres produits. On en tire aussi l'excédent brut d'exploitation et la marge sur coût alimentaire, celle que les éleveurs regardent en premier.""",
         "Une valeur rouge puis verte ; puis la ligne du coût complet.",
         "« Il est fiable ? » — « Recalculé à partir des saisies, chaque règle testée. »"),
        ("118.jpg", 0.75, "Facturation du lait et amortissement du matériel",
         """Le lait est facturé à la laiterie selon une grille de prix — taux de matière grasse, taux de protéines — directement à partir des livraisons, sans ressaisie. Côté matériel, chaque tracteur est une immobilisation avec son plan d'amortissement, qui alimente automatiquement le coût du litre. Ce module est natif d'ERPNext ; ce que j'ai écrit, c'est le lien avec le parc — interventions, pièces, heures — pour que le coût du matériel soit complet.""",
         "La ligne « Lait cru » et le tableau d'amortissement.",
         "« Pourquoi ne pas tout coder ? » — « Un ERP existe pour ça. Mon travail, c'est de savoir quand configurer et quand développer. »"),
        ("123.png", 1.0, "La clé de répartition 60 / 25 / 15 — livrée le 3 septembre",
         """Ma dernière livraison, cette semaine, et celle dont je suis le plus fier. Les frais généraux — électricité, eau, assurances — n'appartiennent à aucun atelier, mais il faut les répartir, sinon le coût du litre est faux. Après une revue avec mon superviseur, j'ai remplacé ma première version, une table à remplir à la main, par un écran natif d'ERPNext : la Cost Center Allocation. Une clé fixée une fois — 60 % lait, 25 % cultures, 15 % génisses — et l'application éclate elle-même chaque facture dans le Grand Livre, avec un contrôle qui vérifie zéro écart entre les écritures et la clé.""",
         "Les pourcentages, puis la ligne « Contrôle » du rapport.",
         "« Et si la clé change ? » — « Nouvelle clé à une nouvelle date ; l'historique ne bouge pas. »"),
    ]),

    ("4. Développement des compétences", "Colonne droite, sous les images : Techniques / Scientifiques / Communication", [
        (None, 1.5, "Techniques, domaine et méthode",
         """Côté technique, j'ai approfondi Frappe et ERPNext — DocTypes, hooks, fixtures, migrations —, Python et SQL sur MariaDB, Git et Docker au quotidien, sur une copie des données réelles de la ferme. Et surtout les tests : en comptabilité, un calcul faux, c'est une décision fausse pour le gérant — 521 tests, 19 modules, tous verts. Côté domaine, la vraie difficulté, c'était d'apprendre l'élevage laitier et la comptabilité agricole en confrontant sans cesse mes calculs aux données réelles. Et côté méthode, on a travaillé en Scrum : daily, backlog Jira, maquettes validées avant chaque écran, et des revues régulières avec le client — la revue du 3 septembre, où j'ai reçu quatre remarques le matin et livré un modèle repris le jour même, en est le meilleur exemple.""",
         "521 tests verts, puis « revue du 03/09 ».",
         "« Vous avez fait ça seul ? » — « Le développement, oui. Encadré : chaque livraison passait en revue. »"),
    ]),

    ("5. Conclusion", "Colonne droite, en bas : Résultat / Points forts / Suggestions / Remerciements", [
        (None, 1.0, "Résultat et conclusion",
         """Aujourd'hui, le module finance tourne à la ferme : comptabilité, coûts, facturation, paie, frais généraux répartis avec zéro écart. Chaque mois, le gérant voit son coût du litre, son excédent brut, sa marge sur coût alimentaire, calculés à partir des saisies quotidiennes. Ce que je retiens : la responsabilité de bout en bout, du besoin jusqu'à la production, avec un vrai client et de vraies données — et savoir reprendre une conception après une revue plutôt que s'y accrocher. Je remercie toute l'équipe de HMD AGRO, en particulier Aymen Zarrad, mon superviseur, et M. Samir, le gérant, pour leur confiance. Merci de votre attention, je suis là pour vos questions.""",
         "Les bullets Résultat, puis Remerciements en regardant le jury.",
         "Silence ? Lance toi-même : « vous voulez voir le détail du coût du litre ? »"),
    ]),
]

RESERVE = [
    ("« C'est quoi ERPNext, concrètement ? »",
     "Un ERP open source complet, comptabilité, stock, actifs, paie, bâti sur Frappe, un framework web en Python. Je configure et j'étends : DocTypes personnalisés, hooks, rapports, fixtures."),
    ("« Pourquoi pas rester sur Excel ? »",
     "Excel ne croisait rien : impossible de relier le lait produit, l'aliment consommé et la paie pour un coût du litre fiable. L'ERP le fait automatiquement et garde l'historique."),
    ("« La clé de répartition, c'est du code à vous ? »",
     "Non, et c'est le point : la clé est native ERPNext. Ce que j'ai écrit, c'est autour : le bandeau qui prévient le comptable, l'avertissement si une charge n'a aucune clé à sa date, la section du rapport qui rejoue la clé contre le Grand Livre, et le centre de coûts posé automatiquement sur chaque mouvement de stock."),
    ("« Vous avez une démo ? »",
     "Oui, sur mon portable : dix minutes sur le site local avec les données réelles. Poser la clé, saisir une facture à deux lignes, valider, ouvrir le Grand Livre, lire le rapport."),
    ("« Le plus dur ? »",
     "Le domaine métier. Et accepter de jeter une conception : la table par ligne m'avait pris deux jours, la clé native m'en a pris un, et elle est meilleure."),
]


def bloc(pi, bi, ph, minutes, titre, dire, montrer, question):
    img = b64(ph)
    img_html = f'<div class="img"><img src="{img}" alt="{html.escape(titre)}"></div>' if img else ""
    cls = "card" if img else "card solo"
    return f"""
<section class="{cls}" id="p{pi}b{bi}">
  {img_html}
  <div class="txt">
    <div class="num"><span class="t">{minutes:g} min</span> {html.escape(titre)}</div>
    <p class="dire">{html.escape(dire)}</p>
    <p class="montrer"><b>Montrer :</b> {html.escape(montrer)}</p>
    <p class="question"><b>Si on demande —</b> {html.escape(question)}</p>
  </div>
</section>"""


parts_html, sommaire, total, cumul = [], [], 0.0, 0.0
for pi, (titre, zone, blocs) in enumerate(PARTIES, 1):
    dur = sum(b[1] for b in blocs)
    debut = cumul
    cumul += dur
    total += dur
    sommaire.append(
        f'<li><a href="#p{pi}"><span class="t">{debut:g}–{cumul:g}</span> {html.escape(titre)}'
        f' <span class="d">({dur:g} min)</span></a></li>'
    )
    cards = "".join(bloc(pi, bi, *b) for bi, b in enumerate(blocs, 1))
    parts_html.append(f"""
<h2 class="partie" id="p{pi}"><span class="t">{debut:g}–{cumul:g} min</span>{html.escape(titre)}<small>{html.escape(zone)}</small></h2>{cards}""")

reserve = "".join(f'<p class="question"><b>{html.escape(q)}</b><br>{html.escape(r)}</p>' for q, r in RESERVE)
q_start = total

page = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Affiche de stage — que dire, partie par partie</title>
<style>
:root{{--ink:#1c1c1c;--muted:#5d5d5d;--accent:#2b3a8f;--line:#d9d9d9;--bg:#fafaf8;--card:#fff;--gold:#c9a227}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif}}
header{{padding:28px 32px 10px;max-width:1100px;margin:0 auto}}
header h1{{font-size:26px;margin:0 0 6px;color:var(--accent)}}
header p{{margin:0 0 6px;color:var(--muted)}}
.plan{{max-width:1100px;margin:0 auto;padding:0 32px}}
.plan ol{{margin:6px 0 0;padding-left:22px;font-size:15px;list-style:none}}
.plan li{{margin:3px 0}}
.plan a{{color:var(--ink);text-decoration:none}}
.plan a:hover{{color:var(--accent)}}
.plan .d{{color:var(--muted)}}
.t{{display:inline-block;min-width:4.6em;color:var(--accent);font-weight:700;font-variant-numeric:tabular-nums}}
main{{max-width:1100px;margin:0 auto;padding:8px 32px 48px}}
h2.partie{{font-size:22px;margin:34px 0 6px;padding-bottom:6px;border-bottom:2px solid var(--accent);color:var(--accent)}}
h2.partie .t{{background:var(--accent);color:#fff;border-radius:4px;padding:2px 8px;margin-right:10px;font-size:14px;min-width:0;vertical-align:middle}}
h2.partie small{{display:block;font-size:14px;font-weight:400;color:var(--muted);margin-top:2px}}
.card{{display:grid;grid-template-columns:minmax(260px,40%) 1fr;gap:22px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px;margin:14px 0;page-break-inside:avoid}}
.card.solo{{grid-template-columns:1fr}}
.img img{{width:100%;height:auto;border:1px solid var(--line);border-radius:6px;display:block}}
.num{{font-size:15px;color:var(--accent);font-weight:600;margin-bottom:8px}}
.num .t{{background:var(--accent);color:#fff;border-radius:4px;padding:1px 6px;margin-right:8px;min-width:0;font-size:13px}}
.dire{{font-size:17px;line-height:1.6;margin:0 0 10px}}
.montrer,.question{{font-size:14.5px;color:var(--muted);margin:0 0 6px;padding-left:12px;border-left:3px solid var(--line)}}
.question{{border-left-color:var(--gold)}}
@media (max-width:760px){{.card{{grid-template-columns:1fr}}}}
@media print{{body{{background:#fff}}.card{{border-color:#bbb;margin:10px 0}}header{{padding-top:8px}}h2.partie{{page-break-before:always}}}}
</style></head>
<body>
<header>
  <h1>Affiche de stage — que dire, partie par partie</h1>
  <p>Mohamed Slim · HMD AGRO · les parties suivent l'affiche dans l'ordre : colonne gauche de haut en bas, puis colonne droite. Chaque bloc donne son temps, le texte à dire, quoi montrer du doigt, et la question probable.</p>
  <p><b>{total:g} minutes de parole</b>, puis les questions du jury (durée libre, hors chrono). Le chiffre à placer à voix haute : <b>521 tests verts</b>.</p>
</header>
<div class="plan"><ol>{"".join(sommaire)}<li><a href="#questions"><span class="t">{q_start:g}+</span> Questions</a></li></ol></div>
<main>{"".join(parts_html)}
<h2 class="partie" id="questions"><span class="t">{q_start:g} min +</span>Questions<small>Réponses en réserve. Si la salle est silencieuse, lance toi-même une question.</small></h2>
<section class="card solo"><div class="txt">{reserve}</div></section>
</main></body></html>"""
OUT.write_text(page)

# Export pour le prompteur (outils_affiche/prompteur/prompteur.json)
import json
blocs, debut = [], 0.0
for titre, zone, bs in PARTIES:
    for ph, minutes, btitre, dire, montrer, question in bs:
        blocs.append({"partie": titre, "zone": zone, "bloc": btitre, "minutes": minutes,
                      "debut": debut, "dire": dire, "montrer": montrer, "question": question})
        debut += minutes
blocs.append({"partie": "Questions", "zone": "", "bloc": "Réponses en réserve", "minutes": 5.0,
              "debut": debut, "dire": "\n\n".join(f"{q}\n{r}" for q, r in RESERVE), "montrer": "", "question": ""})
PJ = HERE / "prompteur" / "prompteur.json"
PJ.parent.mkdir(exist_ok=True)
PJ.write_text(json.dumps(blocs, ensure_ascii=False, indent=1))
print(f"{total:g} min de parole ({len(PARTIES)} parties), puis questions à partir de {q_start:g} min → {OUT} ({OUT.stat().st_size // 1024} Ko)")
