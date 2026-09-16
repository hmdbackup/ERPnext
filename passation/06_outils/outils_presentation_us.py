# -*- coding: utf-8 -*-
"""Injecte les maquettes Excalidraw du 24/08/2026 dans `expliquer_les_us.html`.

Le script ne réécrit que le corps (`<div class="s-body">`) des dix diapositives
qui portent une maquette : 6, 7, 8, 10, 12, 13, 14, 16, 17, 18. Le reste du
fichier — feuille de style, navigation, diapositives de texte — est conservé
tel quel, donc relancer le script est sans danger tant que les retouches se
font ailleurs que dans ces dix corps.

Chaque entrée de MAQ est un recadrage : (x, y, largeur, hauteur) dans les
coordonnées de la scène Excalidraw. Le rendu SVG est fait par
`outils_maquette_svg`, qui traduit les couleurs Excalidraw en classes CSS pour
que la maquette suive le thème clair/sombre de la présentation.
"""
import io, re
from pathlib import Path
RACINE = Path(__file__).resolve().parents[2]
import outils_maquette_svg as M

VALIDEES = M.charger(RACINE / "passation/03_maquettes/maquettes_validees_2026-08-24.excalidraw")
SCRUM9   = M.charger(RACINE / "passation/03_maquettes/maquette_scrum9_annotee_2026-08-24.excalidraw")
ARBI     = M.charger(RACINE / "passation/03_maquettes/maquette_arbitrage_frais_generaux_2026-08-24.excalidraw")

MAQ = {
    # écrans entiers — annotations et flèches comprises
    "s10_ecran":     M.svg(VALIDEES, (0, 66, 1460, 940)),
    "s11_ecran":     M.svg(VALIDEES, (0, 1516, 1560, 810)),
    "s9_ecran":      M.svg(SCRUM9,   (0, 66, 1460, 790)),
    "arb_ecran":     M.svg(ARBI,     (0, 66, 1520, 620)),
    "arb_facture":   M.svg(ARBI,     (0, 1246, 900, 330)),
    # recadrages — le bloc de tableau dont on parle
    "s10_ateliers":  M.svg(VALIDEES, (14, 352, 845, 142), fleches=False, marge=6),
    "s10_fg":        M.svg(VALIDEES, (14, 498, 845, 124), fleches=False, marge=6),
    "s10_unitaires": M.svg(VALIDEES, (14, 823, 845, 126), fleches=False, marge=6),
    "s11_parc":      M.svg(VALIDEES, (14, 1688, 1004, 182), fleches=False, marge=6),
    "s11_interv":    M.svg(VALIDEES, (14, 1888, 1450, 258), fleches=False, marge=6),
    "s9_comptages":  M.svg(SCRUM9,   (14, 518, 923, 252), fleches=False, marge=6),
}

CORPS = {}

CORPS[6] = u"""
      <figure class="maq-frame maq-frame--flush">{{s10_ecran}}</figure>
      <p class="maq-cap">Maquette du 24/08/2026 — Rapport de Performance, juin 2026. Les repères
        ① à ④ marquent les quatre endroits que vos décisions changent.</p>
"""

CORPS[7] = u"""
      <p class="tagline">Zoom 1 — la ventilation</p>
      <h2 class="s-title">Chaque charge est rangée dans son atelier</h2>
      <figure class="maq-frame">{{s10_ateliers}}</figure>
      <div class="under">
        <div>
          <p class="body">Les 112 100 DT du mois se répartissent sur cinq ateliers. Le coût du
            litre ne retiendra que ce qui touche le lait — <b>63 400 DT de charges directes</b>,
            plus une part des frais généraux.</p>
          <p class="body">Le total ventilé doit retomber au dinar près sur les charges totales.
            S'il ne retombe pas, une écriture manque quelque part et l'écran le dit.</p>
        </div>
        <div class="deci">
          <h4>Votre décision — aucune charge « non attribuée »</h4>
          <p>L'atelier devient <b>obligatoire à la saisie</b>. La ligne reste affichée, à zéro :
            c'est un contrôle, pas une catégorie.</p>
          <p>Le jour où elle n'est plus à zéro, une écriture est passée à travers — et on le voit
            sans la chercher.</p>
        </div>
      </div>
"""

CORPS[8] = u"""
      <p class="tagline">Zoom 2 — les frais généraux</p>
      <h2 class="s-title">Une clé par dépense, écrite en toutes lettres</h2>
      <figure class="maq-frame">{{s10_fg}}</figure>
      <div class="under">
        <div>
          <p class="body">Le gardien, l'électricité, l'assurance servent à toute la ferme. Pour en
            donner une part au lait, il faut une règle — et jusqu'ici il n'y en avait qu'une, posée
            une fois pour toutes.</p>
          <p class="body">Le gardiennage et l'administratif suivent désormais ce que l'atelier
            <b>rapporte</b> (90,00 %). L'électricité et l'assurance suivent ce qu'il
            <b>dépense</b> (61,98 %).</p>
        </div>
        <div class="deci">
          <h4>Votre décision — arbitrage cas par cas</h4>
          <p>Ni le prorata des dépenses seul, ni celui des recettes seul. <b>Chaque dépense porte
            sa clé</b>, et le rapport affiche laquelle a été appliquée.</p>
          <p>Conservée mois après mois : le coût du litre d'un mois passé reste explicable.</p>
        </div>
      </div>
"""

CORPS[10] = u"""
      <p class="tagline tagline--warn">Zoom 3 — le coût du litre</p>
      <h2 class="s-title">Une ligne est affichée, et ne doit surtout pas être additionnée</h2>
      <figure class="maq-frame">{{s10_unitaires}}</figure>
      <div class="under under--large">
        <div>
          <p class="body">Le coût mécanique au litre est une <b>vue analytique</b> — utile pour
            comparer deux machines. Le coût horaire d'un tracteur agrège déjà trois choses qui
            sont, chacune, comptées dans les charges du Grand Livre :</p>
          <div class="bricks">
            <div class="brick"><b>Amortissement</b><span>comptes 68x</span></div>
            <div class="plus">+</div>
            <div class="brick"><b>Entretien</b><span>compte 615</span></div>
            <div class="plus">+</div>
            <div class="brick"><b>Mazout</b><span>achats carburant</span></div>
          </div>
          <p class="arrow">↑ déjà dans les 112 100 DT de charges totales</p>
        </div>
        <div>
          <p class="body">L'ajouter au coût complet reviendrait à <b>payer deux fois le même
            tracteur</b>. Le libellé le dit à l'écran — « vue analytique » — et un test automatique
            empêche qu'on le casse par mégarde.</p>
          <p class="body">Le chiffre qui sera communiqué reste le <b>coût complet : 1,562 DT le
            litre</b>, sur le périmètre atelier Lait + quote-part arbitrée.</p>
        </div>
      </div>
"""

CORPS[12] = u"""
      <figure class="maq-frame maq-frame--flush">{{s11_ecran}}</figure>
      <p class="maq-cap">Maquette du 24/08/2026 — Rapport des Interventions, juin 2026. Le parc,
        les interventions réalisées, le préventif à 30 jours, puis le rapprochement au compte 615.</p>
"""

CORPS[13] = u"""
      <p class="tagline">Zoom 1 — l'état du parc</p>
      <h2 class="s-title">Un seul mot par équipement</h2>
      <figure class="maq-frame">{{s11_parc}}</figure>
      <div class="under">
        <div>
          <p class="body">Trois valeurs, une seule liste : <b>Prêt · En panne · En attente de
            maintenance</b>. Pas de champ « disponible » à côté — « elle roule encore mais il faut
            la regarder » se dit <i>en attente de maintenance</i>.</p>
          <p class="body">Un seul champ, un seul clic à la saisie. Et une lecture du parc en trois
            secondes, le lundi matin.</p>
        </div>
        <div class="deci">
          <h4>Votre décision — une seule liste à trois valeurs</h4>
          <p>C'est aussi la seule chose qui n'existe <b>nulle part</b> aujourd'hui : ERPNext ne
            connaît que le statut comptable — en service, cédé, mis au rebut.</p>
          <p>L'état mécanique est à construire. C'est un champ, pas un écran.</p>
        </div>
      </div>
"""

CORPS[14] = u"""
      <p class="tagline tagline--warn">Zoom 2 — le rapprochement</p>
      <h2 class="s-title">L'écart entre les deux sources <em>est</em> l'information</h2>
      <figure class="maq-frame">{{s11_interv}}</figure>
      <div class="under">
        <div>
          <p class="body">Deux sources coexistent et <b>ne peuvent pas toujours coïncider</b>. Une
            facture d'entretien passée en comptabilité sans intervention rattachée gonfle le 615
            sans toucher les interventions ; une intervention faite en interne fait l'inverse.</p>
          <p class="body">L'écart est donc <b>normal</b> — et c'est lui le renseignement utile :
            « 400 DT d'entretien ne sont rattachés à aucune machine ».</p>
        </div>
        <div class="deci">
          <h4>Votre décision — pièces et main-d'œuvre séparées</h4>
          <p>1 855 DT de pièces, 860 DT de main-d'œuvre, et le rapprochement au compte 615 tombe à
            <b>écart 0,00</b> : ce mois-ci, chaque dinar d'entretien est rattaché à une machine.</p>
          <p>C'est ce qui permettra de dire un jour : « on paye trop cher la main-d'œuvre
            extérieure ».</p>
        </div>
      </div>
"""

CORPS[16] = u"""
      <figure class="maq-frame maq-frame--flush">{{s9_ecran}}</figure>
      <p class="maq-cap">Maquette du 24/08/2026 — Rapport Périodique, production jour par jour.
        En bleu ce que l'écran fait, en orange ce qui reste à trancher, en rouge ce qui bloque.</p>
"""

CORPS[17] = u"""
      <p class="tagline tagline--warn">Ce qui reste à trancher</p>
      <h2 class="s-title">Le même lait est compté à deux endroits, et les deux ne disent pas pareil</h2>
      <figure class="maq-frame">{{s9_comptages}}</figure>
      <div class="trio trio--serre">
        <div class="deci">
          <h4>Acquis le 24/08</h4>
          <p>L'écart de 9 959 L <b>n'est pas un sujet</b>. Aucune alerte n'est à construire
            dessus — c'est autant de moins à développer.</p>
        </div>
        <div class="deci deci--warn">
          <h4>À trancher</h4>
          <p><b>Lequel des deux fait référence ?</b> Le choix décide de tous les litres affichés
            ailleurs. Et d'où viennent les taux TB / TP, à quelle fréquence ?</p>
        </div>
        <div class="deci deci--crit">
          <h4>Bloquant — indépendant des arbitrages</h4>
          <p>Aucun vêlage n'est enregistré sur juin : <b>0 vache lactante</b>, donc le
            litres/vache/jour reste vide. Cela ne dépend pas du code.</p>
        </div>
      </div>
"""

CORPS[18] = u"""
      <p class="tagline">Ce qui n'a nulle part où s'inscrire</p>
      <h2 class="s-title">Le cas par cas, il faut bien que quelqu'un le fasse — quelque part</h2>
      <div class="two">
        <div>
          <p class="lead">Variante A — à la clôture du mois</p>
          <h3>Un écran d'arbitrage</h3>
          <figure class="maq-frame maq-frame--mini">{{arb_ecran}}</figure>
          <p class="after">La liste du mois, une clé par ligne. Le contrôle qui compte : <b>tant
            qu'une dépense reste sans clé, le coût du litre du mois ne peut pas être arrêté.</b></p>
        </div>
        <div>
          <p class="lead">Variante B — à la saisie</p>
          <h3>Pas d'écran : un champ sur la dépense</h3>
          <figure class="maq-frame maq-frame--mini">{{arb_facture}}</figure>
          <p class="after">Deux boutons posés sur la facture et sur l'écriture. <b>Rien d'autre à
            construire</b> — mais personne ne revoit le mois en entier avant la clôture.</p>
        </div>
      </div>
      <div class="qbar">
        <b>Qui arbitre — le comptable, ou vous ?</b>
        <span>La réponse au <i>qui</i> donne le <i>quand</i>, et le <i>quand</i> donne la forme.
          C'est la seule décision qui manque pour que le coût du litre parte en construction.</span>
      </div>
"""

# ── réécriture ────────────────────────────────────────────────────────────
src = io.open(RACINE / "passation/04_demonstration/expliquer_les_us.html", encoding="utf-8").read()
morceaux = src.split(u'<section class="slide">')
tete, diapos = morceaux[0], morceaux[1:]
assert len(diapos) == 20, len(diapos)

for n, corps in CORPS.items():
    d = diapos[n - 1]
    deb = d.index(u'<div class="s-body">')
    fin = d.index(u'<div class="s-foot">')
    for cle, val in MAQ.items():
        corps = corps.replace(u"{{%s}}" % cle, val)
    diapos[n - 1] = (d[:deb] + u'<div class="s-body">' + corps + u'    </div>\n    ' + d[fin:])

src = tete + u'<section class="slide">'.join([u""] + diapos)[len(u""):] if False else \
      tete + u"".join(u'<section class="slide">' + d for d in diapos)

io.open(RACINE / "passation/04_demonstration/expliquer_les_us.html", "w", encoding="utf-8").write(src)
print(u"maquettes injectées — %d diapositives réécrites, fichier %.0f Ko"
      % (len(CORPS), len(src) / 1024))
