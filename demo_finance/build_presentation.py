#!/usr/bin/env python3
"""Génère presentation_finance.html (deck autonome, images en base64).

Source unique du deck ET de la narration : la même liste NOTES sert aux
« notes du présentateur » dans le HTML et à la piste audio de la vidéo
(voir build_video.sh). Modifier ici, régénérer les deux.

    python3 build_presentation.py
"""
import base64
import pathlib
import re
import json

RACINE = pathlib.Path(__file__).resolve().parent.parent
SHOTS = pathlib.Path(__file__).resolve().parent / "captures"
SORTIE = RACINE / "presentation_finance.html"

# ─── Slides ──────────────────────────────────────────────────────────────────

SLIDES = [
# 1 — titre
"""<section class="slide center">
  <div class="rule" style="margin:0 auto 22px"></div>
  <div class="kicker">HMD Agro · Élevage laitier</div>
  <h1>Pilotage économique de la ferme</h1>
  <p class="lead" style="margin:0 auto">Un outil de <b style="color:var(--ink)">contrôle de gestion</b> sur ERPNext :
  coût de revient du litre, marges et indicateurs, atelier par atelier.</p>
  <p class="foot">Version de travail sur données de test — présentée pour validation · Mohamed Slim</p>
</section>""",

# 2 — périmètre
"""<section class="slide">
  <div class="kicker">De quoi on parle</div>
  <h2>« Finance » ici = piloter, pas tenir la comptabilité</h2>
  <div class="two">
    <div class="col">
      <h3>✓ Ce qu'on a visé — le pilotage</h3>
      <ul>
        <li>Combien me coûte <b>un litre de lait</b>, réellement ?</li>
        <li>Où je gagne, où je perds — <b>par atelier</b></li>
        <li>Mes marges : <b>EBE, IOFC</b>, résultat</li>
        <li>Des <b>alertes visuelles</b> quand un coût dérape</li>
      </ul>
    </div>
    <div class="col">
      <h3 style="color:var(--muted)">✗ Ce qui reste à l'expert-comptable</h3>
      <ul>
        <li class="muted">La comptabilité générale <b class="muted">légale</b></li>
        <li class="muted">TVA et déclarations fiscales</li>
        <li class="muted">Bilan et clôture statutaires</li>
      </ul>
      <p class="muted" style="margin-top:14px;font-size:14px">L'outil s'appuie sur le moteur comptable
      d'ERPNext comme <b class="muted">moyen</b> de calcul — ce n'est pas de la tenue de compta.</p>
    </div>
  </div>
</section>""",

# 3 — vue d'ensemble
"""<section class="slide">
  <div class="kicker">Vue d'ensemble</div>
  <h2>7 chantiers · 22 besoins couverts</h2>
  <div class="grid g4">
    <div class="card"><span class="big">A</span><h3>Socle</h3><p>Le référentiel et l'analytique par atelier.</p></div>
    <div class="card"><span class="big">B</span><h3>Coût du litre</h3><p>Chaque ration valorisée à son coût réel.</p></div>
    <div class="card"><span class="big">C</span><h3>Recettes</h3><p>Lait au prix qualité, animaux, fumier.</p></div>
    <div class="card"><span class="big">D</span><h3>Équipements & cheptel</h3><p>Amortissement, entretien, troupeau au bilan.</p></div>
    <div class="card"><span class="big">E</span><h3>Charges & personnel</h3><p>Frais et salaires ventilés par atelier.</p></div>
    <div class="card"><span class="big">F</span><h3>Tableau de bord</h3><p>EBE, IOFC, coût/L colorés.</p></div>
    <div class="card"><span class="big">G</span><h3>Démarrage & contrôle</h3><p>Droits, bascule, vérification des données.</p></div>
    <div class="card gold"><span class="big">22</span><h3>besoins couverts</h3><p>206 tests automatisés au vert.</p></div>
  </div>
</section>""",

# 4 — A socle
"""<section class="slide">
  <div class="kicker">Épic A · Le socle</div>
  <h2>Un référentiel tunisien, analytique par atelier</h2>
  <div class="two">
    <div class="col uslist">
      <div class="us"><div class="us-h"><span class="usid">FIN-S01</span><span class="ustitle">Un plan comptable tunisien</span><span class="badge ok">Fait</span></div><div class="usbesoin">Disposer d'une base de comptes conforme, en dinars.</div><div class="usdone">Plan tunisien de 77 comptes chargé, avec l'exercice et les taux de TVA.</div></div>
      <div class="us"><div class="us-h"><span class="usid">FIN-S02</span><span class="ustitle">Un découpage par atelier</span><span class="badge ok">Fait</span></div><div class="usbesoin">Pouvoir dire quel atelier coûte quoi et rapporte quoi.</div><div class="usdone">5 ateliers (Lait, Élevage, Cultures, Traction, Frais généraux) + suivi par lot et bâtiment.</div></div>
    </div>
    <div class="col">
      <figure class="shot"><img src="{{IMG:plan_comptable}}" alt="Plan comptable de hmd-agro, en dinars (TND)"><figcaption>Plan comptable de hmd-agro, en dinars (TND)</figcaption></figure>
    </div>
  </div>
</section>""",

# 5 — B coût du litre
"""<section class="slide">
  <div class="kicker">Épic B · Le cœur du pilotage</div>
  <h2>Le coût de revient réel du litre</h2>
  <div class="two">
    <div class="col uslist">
      <div class="us"><div class="us-h"><span class="usid">FIN-S10</span><span class="ustitle">Connaître le vrai prix des intrants</span><span class="badge ok">Fait</span></div><div class="usbesoin">Que chaque aliment ait son coût réel d'achat.</div><div class="usdone">Chaque achat met à jour le coût moyen de l'aliment concerné.</div></div>
      <div class="us"><div class="us-h"><span class="usid">FIN-S11</span><span class="ustitle">Valoriser ce qui est consommé</span><span class="badge ok">Fait</span></div><div class="usbesoin">Que la nourriture distribuée ne compte plus pour zéro.</div><div class="usdone">La ration du jour est chiffrée automatiquement — et la compta ne bloque jamais le terrain.</div></div>
      <div class="us"><div class="us-h"><span class="usid">FIN-S12</span><span class="ustitle">Voir le coût du litre</span><span class="badge ok">Fait</span></div><div class="usbesoin">Piloter la rentabilité sans calcul à la main.</div><div class="usdone">Coût alimentaire affiché par litre et par vache, directement dans le rapport.</div></div>
    </div>
    <div class="col">
      <figure class="shot"><img src="{{IMG:cout_litre}}" alt="Rapport Mensuel — L/C et coût alimentaire signalés en rouge"><figcaption>Rapport Mensuel — L/C et coût alimentaire signalés en rouge</figcaption></figure>
    </div>
  </div>
</section>""",

# 6 — C recettes
"""<section class="slide">
  <div class="kicker">Épic C · Recettes</div>
  <h2>Le lait payé à sa vraie qualité</h2>
  <div class="two">
    <div class="col uslist">
      <div class="us"><div class="us-h"><span class="usid">FIN-S24</span><span class="ustitle">La grille de prix de la centrale</span><span class="badge part">Grille à valider</span></div><div class="usbesoin">Être payé au barème réel : primes et pénalités selon les taux.</div><div class="usdone">Un écran de paliers (matière grasse, protéines) fixe le prix du litre. Les valeurs actuelles sont indicatives — la grille de la centrale les remplacera.</div></div>
      <div class="us"><div class="us-h"><span class="usid">FIN-S21</span><span class="ustitle">La facture de lait du mois</span><span class="badge ok">Fait</span></div><div class="usbesoin">Enregistrer la recette principale sans ressaisie.</div><div class="usdone">Générée pour la centrale au prix de la grille, sans risque de doublon.</div></div>
      <div class="us"><div class="us-h"><span class="usid">FIN-S25</span><span class="ustitle">Ce que coûte le lait perdu</span><span class="badge ok">Fait</span></div><div class="usbesoin">Savoir ce que représentent les litres qui manquent à l'appel.</div><div class="usdone">L'écart entre lait produit et lait affecté est chiffré en dinars, avec un seuil d'alerte.</div></div>
      <div class="us"><div class="us-h"><span class="usid">FIN-S22</span><span class="ustitle">La vente d'un animal</span><span class="badge ok">Fait</span></div><div class="usbesoin">Comptabiliser la vente sans y penser.</div><div class="usdone">Un animal passe en « vendu » → sa facture se crée ; vente annulée → facture annulée.</div></div>
      <div class="us"><div class="us-h"><span class="usid">FIN-S23</span><span class="ustitle">Le fumier et les à-côtés</span><span class="badge ok">Fait</span></div><div class="usbesoin">Ne perdre aucune recette secondaire.</div><div class="usdone">Fumier et produits annexes facturés et rattachés au bon atelier.</div></div>
    </div>
    <div class="col">
      <figure class="shot"><img src="{{IMG:grille_paliers}}" alt="Grille de prix — paliers de matière grasse et de protéines"><figcaption>Grille de prix — paliers de qualité, valeurs provisoires signalées</figcaption></figure>
      <figure class="shot"><img src="{{IMG:facture_lait}}" alt="Facture lait — 954 L à 1,63 TND le litre"><figcaption>Facture lait — 954 L à 1,63 TND/L (prix de base 1,60 + prime qualité)</figcaption></figure>
    </div>
  </div>
</section>""",

# 7 — D1 équipements
"""<section class="slide">
  <div class="kicker">Épic D · Équipements (1/2)</div>
  <h2>Le matériel s'use — et il s'entretient</h2>
  <div class="two">
    <div class="col uslist">
      <div class="us"><div class="us-h"><span class="usid">FIN-S30</span><span class="ustitle">Suivre le matériel dans le temps</span><span class="badge ok">Fait</span></div><div class="usbesoin">Que l'usure des équipements pèse sur le résultat.</div><div class="usdone">Le matériel perd de la valeur automatiquement chaque année, sur sa durée de vie.</div></div>
      <div class="us"><div class="us-h"><span class="usid">FIN-S32</span><span class="ustitle">Les interventions et leur coût</span><span class="badge ok">Fait</span></div><div class="usbesoin">Savoir ce que coûte l'entretien de chaque équipement.</div><div class="usdone">Chaque panne ou révision est enregistrée avec sa durée d'arrêt et son coût, imputé à l'atelier. Le préventif se planifie et rappelle les échéances.</div></div>
    </div>
    <div class="col">
      <figure class="shot"><img src="{{IMG:tracteur_amortissement}}" alt="Tracteur 45 000 TND — 5 dotations annuelles de 9 000 TND"><figcaption>Tracteur 45 000 TND — 5 dotations annuelles de 9 000 TND</figcaption></figure>
      <figure class="shot"><img src="{{IMG:intervention}}" alt="Intervention préventive sur le tracteur — 340 TND"><figcaption>Intervention préventive sur le tracteur — 340 TND, arrêt 4 h</figcaption></figure>
    </div>
  </div>
</section>""",

# 8 — D2 cheptel
"""<section class="slide">
  <div class="kicker">Épic D · Le troupeau (2/2)</div>
  <h2>Votre premier actif entre au bilan</h2>
  <div class="two">
    <div class="col uslist">
      <div class="us"><div class="us-h"><span class="usid">FIN-S31</span><span class="ustitle">Le troupeau : bien ou stock ?</span><span class="badge part">Décision à prendre</span></div><div class="usbesoin">Faire apparaître la valeur du cheptel, et son usure, dans les comptes.</div><div class="usdone">Chaque vache entre à l'actif à son premier vêlage — au prix d'achat si elle a été achetée, au coût d'élevage si elle est née ici — puis s'amortit. Quand elle sort du troupeau, elle sort du bilan toute seule.</div></div>
      <div class="us" style="border-color:var(--gold-dim)"><div class="us-h"><span class="ustitle" style="color:var(--gold)">Ce qui vous revient</span></div><div class="usdone">Traiter le cheptel comme un bien qui s'amortit, ou comme un stock ? Un seul réglage bascule d'un mode à l'autre — l'outil est prêt pour les deux.</div></div>
    </div>
    <div class="col">
      <figure class="shot"><img src="{{IMG:cheptel_assets}}" alt="10 vaches inscrites à l'actif, en cours d'amortissement"><figcaption>10 vaches à l'actif — 25 000 TND de valeur brute, 23 000 TND après amortissement</figcaption></figure>
    </div>
  </div>
</section>""",

# 9 — E charges & personnel
"""<section class="slide">
  <div class="kicker">Épic E · Charges & personnel</div>
  <h2>Chaque dépense — et chaque salaire — à son atelier</h2>
  <div class="two">
    <div class="col uslist">
      <div class="us"><div class="us-h"><span class="usid">FIN-S40</span><span class="ustitle">Les charges par atelier</span><span class="badge ok">Fait</span></div><div class="usbesoin">Obtenir un coût complet, pas seulement l'alimentation.</div><div class="usdone">Électricité, eau, loyer, assurances rattachés à l'atelier concerné.</div></div>
      <div class="us"><div class="us-h"><span class="usid">FIN-S42</span><span class="ustitle">Le registre du personnel</span><span class="badge ok">Fait</span></div><div class="usbesoin">Savoir qui travaille sur la ferme, à quel poste et pour quel salaire.</div><div class="usdone">Une fiche par salarié : rôle, contrat, salaire, atelier — et la possibilité de répartir quelqu'un entre plusieurs ateliers.</div></div>
      <div class="us"><div class="us-h"><span class="usid">FIN-S41</span><span class="ustitle">Le coût du travail</span><span class="badge ok">Fait</span></div><div class="usbesoin">Que le coût du litre inclue aussi la main-d'œuvre.</div><div class="usdone">La paie du mois se calcule depuis le registre, charges patronales comprises, et se ventile toute seule. Plus aucun montant tapé à la main.</div></div>
    </div>
    <div class="col">
      <figure class="shot"><img src="{{IMG:personnel_liste}}" alt="Registre du personnel — 6 salariés avec rôle, salaire et atelier"><figcaption>Registre du personnel — rôle, salaire et atelier de chacun</figcaption></figure>
      <figure class="shot"><img src="{{IMG:salaires_je}}" alt="Paie du mois — 6 470 TND ventilés sur 5 ateliers"><figcaption>Paie du mois — 6 470 TND ventilés sur 5 ateliers, charges comprises</figcaption></figure>
    </div>
  </div>
</section>""",

# 10 — F tableau de bord
"""<section class="slide">
  <div class="kicker">Épic F · Tableau de bord</div>
  <h2>Décider vite : indicateurs colorés par seuils</h2>
  <div class="two">
    <div class="col uslist">
      <div class="us"><div class="us-h"><span class="usid">FIN-S50</span><span class="ustitle">Un tableau de bord économique</span><span class="badge ok">Fait</span></div><div class="usbesoin">Coût/L, marges, EBE, IOFC pour décider vite.</div><div class="usdone">42 indicateurs calculés à partir des écritures — jamais ressaisis, jamais dans un Excel à part. Coût de la main-d'œuvre par litre, valeur du lait perdu, entretien rapporté au chiffre d'affaires, valeur du cheptel.</div></div>
      <div class="us"><div class="us-h"><span class="usid">FIN-S51</span><span class="ustitle">Des seuils réglables et colorés</span><span class="badge ok">Fait</span></div><div class="usbesoin">Repérer les alertes d'un simple coup d'œil.</div><div class="usdone">Vert / orange / rouge selon des seuils que vous réglez vous-même, sans programmer.</div></div>
    </div>
    <div class="col">
      <figure class="shot"><img src="{{IMG:indicateurs}}" alt="Indicateurs — coût MO/L, écart lait valorisé, entretien, cheptel"><figcaption>Coût main-d'œuvre par litre, lait perdu chiffré, entretien, cheptel au bilan</figcaption></figure>
      <figure class="shot"><img src="{{IMG:seuils_config}}" alt="Seuils Finance réglables dans la configuration"><figcaption>Seuils Finance réglables dans la configuration</figcaption></figure>
    </div>
  </div>
</section>""",

# 11 — G démarrage, droits & contrôle
"""<section class="slide">
  <div class="kicker">Épic G · Démarrage, droits & contrôle</div>
  <h2>Prêt à démarrer, sécurisé, vérifiable</h2>
  <div class="two">
    <div class="col uslist">
      <div class="us"><div class="us-h"><span class="usid">FIN-S60</span><span class="ustitle">Démarrer sur des comptes justes</span><span class="badge part">Procédure prête</span></div><div class="usbesoin">Reprendre les soldes existants au jour du démarrage.</div><div class="usdone">La procédure est écrite ; les vrais soldes seront saisis après votre validation.</div></div>
      <div class="us"><div class="us-h"><span class="usid">FIN-S61</span><span class="ustitle">Chacun ses droits</span><span class="badge ok">Fait</span></div><div class="usbesoin">Séparer qui saisit, qui valide, qui consulte.</div><div class="usdone">Un éleveur fait son métier mais ne peut pas toucher aux écritures comptables. Vérifié par test.</div></div>
      <div class="us"><div class="us-h"><span class="usid">FIN-S70</span><span class="ustitle">Vérifier que les chiffres tiennent</span><span class="badge ok">Fait</span></div><div class="usbesoin">Pouvoir faire confiance aux chiffres avant de décider.</div><div class="usdone">26 contrôles automatiques passent la base au crible et signalent en orange ou en rouge tout ce qui cloche — lait produit qui ne colle pas au lait facturé, aliment sans prix, sortie d'animal non facturée.</div></div>
    </div>
    <div class="col">
      <figure class="shot"><img src="{{IMG:controle_coherence}}" alt="Contrôle de cohérence — 26 contrôles, statut par domaine"><figcaption>Contrôle de cohérence — chaque vérification en vert, orange ou rouge</figcaption></figure>
    </div>
  </div>
</section>""",

# 12 — bilan
"""<section class="slide center">
  <div class="kicker">Où on en est</div>
  <h2>22 besoins couverts, 206 tests au vert</h2>
  <div class="grid g3" style="width:100%;max-width:940px">
    <div class="card"><span class="big">22</span><h3>besoins couverts</h3><p>Sur les 7 chantiers.</p></div>
    <div class="card"><span class="big">206 / 206</span><h3>tests au vert</h3><p>Relancés et vérifiés à chaque modification.</p></div>
    <div class="card"><span class="big">2</span><h3>décisions attendues</h3><p>La grille de la centrale · le troupeau : bien ou stock ?</p></div>
  </div>
  <p class="foot">Aucun montant figé dans le code · tout est réglable · la compta ne bloque jamais le terrain.</p>
</section>""",

# 13 — question périmètre
"""<section class="slide">
  <div class="kicker" style="color:var(--orange)">La question la plus importante</div>
  <h2>D'abord : est-ce le bon périmètre ?</h2>
  <div class="q"><b>Attendez-vous un outil de pilotage</b> (coût du litre, marges, IOFC, coûts par atelier)
  — la <b>comptabilité générale</b> (plan statutaire, TVA, déclarations, soldes d'ouverture) restant chez
  l'expert-comptable ? Ou voulez-vous qu'ERPNext tienne <b>aussi la comptabilité</b> ?</div>
  <p class="lead">Selon votre réponse, on garde le cœur « pilotage » et on met de côté quelques volets
  (TVA, soldes d'ouverture), ou on continue vers une comptabilité complète. Dans les deux cas, ce qui est
  construit sert.</p>
</section>""",

# 14 — trois questions
"""<section class="slide">
  <div class="kicker">Votre avis décide de la suite</div>
  <h2>Trois questions pour valider</h2>
  <div class="q"><b>1 — Le fonctionnement</b> correspond-il à la réalité de la ferme ? Le calcul du coût du litre,
  la ventilation par atelier, le choix des indicateurs.</div>
  <div class="q"><b>2 — Les deux décisions.</b> La grille de prix de la centrale, et le traitement comptable
  du troupeau : bien amortissable ou stock ?</div>
  <div class="q"><b>3 — Qu'a-t-on mal compris ?</b> Si un calcul ou un circuit ne colle pas à votre pratique —
  c'est le bon moment pour corriger.</div>
  <p class="foot">Le paramétrage avec les vraies valeurs (prix du lait, primes, salaires, date de démarrage)
  viendra une fois la logique validée.</p>
</section>""",

# 15 — fin
"""<section class="slide center">
  <div class="rule" style="margin:0 auto 22px"></div>
  <h2 style="margin-bottom:14px">Rien n'est figé</h2>
  <p class="lead" style="margin:0 auto">Tout ce que vous venez de voir peut être ajusté, complété ou
  repensé selon vos retours.</p>
  <p class="foot">Merci — j'attends votre avis.</p>
</section>""",
]

# ─── Narration (notes présentateur = piste audio de la vidéo) ─────────────────
# Écrites pour être LUES : nombres en toutes lettres, phrases courtes.

NOTES = [
"Bonjour, et merci de votre temps. Je vais vous présenter ce que j'ai construit sur la partie finance. "
"L'idée directrice : transformer ERPNext en un outil de pilotage — savoir précisément ce que coûte un litre "
"de lait, et où l'exploitation gagne ou perd de l'argent. Tout ce que vous allez voir tourne sur des données "
"de test : les chiffres sont fictifs, ils servent juste à montrer la mécanique. Mon objectif aujourd'hui n'est "
"pas de déployer, mais de valider avec vous que c'est bien ce que vous attendez.",

"Un point important avant de commencer, sur le périmètre. Quand je dis « finance », je ne parle pas de tenir "
"votre comptabilité légale — ça, ça reste chez votre expert-comptable : la TVA, les déclarations fiscales, le "
"bilan de fin d'année. Ce que je vise, c'est le pilotage : combien coûte un litre, quel atelier vous rapporte "
"ou vous coûte, et des voyants qui s'allument quand un coût dérape. L'outil utilise quand même le moteur "
"comptable d'ERPNext par-dessous, mais uniquement comme moyen de calcul — pas pour faire votre comptabilité. "
"C'est justement un des points que j'aimerais vous voir confirmer à la fin.",

"Le travail se découpe en sept chantiers, de A à G, que je vais vous montrer un par un. Chaque chantier répond "
"à des besoins concrets. Dans les écrans qui suivent, chaque besoin porte un petit code, par exemple « FIN-S01 » "
"— c'est juste un numéro de suivi, pour qu'on puisse en reparler précisément ensuite. Sous chaque titre, je mets "
"en italique le besoin exprimé simplement, et en dessous ce qui a été réalisé. Au total, vingt-deux besoins sont "
"couverts, et deux cent six tests automatiques les vérifient. Deux décisions vous reviennent, j'y reviendrai à la fin.",

"Le chantier A, c'est la fondation. Deux besoins. Le premier : avoir un plan comptable tunisien, c'est-à-dire la "
"liste normalisée des comptes, en dinars — à l'écran, vous voyez les grandes familles : actifs, produits, charges. "
"Le deuxième besoin, c'est l'analytique : pouvoir découper chaque dépense et chaque recette par atelier. "
"Concrètement, quand on paiera l'électricité ou les salaires, on saura quelle part revient au lait, quelle part "
"à l'élevage. C'est ce découpage qui rend tout le reste possible.",

"Le chantier B, c'est le cœur du sujet : le coût de revient du litre. Trois étapes. D'abord, on enregistre le prix "
"d'achat des aliments — le concentré, le foin — donc on connaît leur coût réel. Ensuite, quand on distribue la "
"ration à un lot, ce qui est mangé est chiffré automatiquement ; avant, la nourriture consommée comptait pour zéro, "
"on ne pouvait rien calculer. Un point important : même si un prix manque, l'enregistrement de terrain n'est jamais "
"bloqué — la saisie de l'éleveur passe toujours. Enfin, résultat à l'écran : le coût alimentaire par litre s'affiche "
"tout seul. Ici il ressort en rouge parce que la ration de démonstration est volontairement trop riche — c'est "
"justement le genre d'alerte qu'on veut voir.",

"Le chantier C, ce sont les recettes. Je commence par la nouveauté la plus importante : le prix du lait. Jusqu'ici "
"le litre était payé à un prix unique, quelle que soit sa qualité. Maintenant, il y a un écran de barème : "
"vous y saisissez les tranches de matière grasse et de protéines, avec la prime ou la pénalité de chacune, "
"exactement comme sur le contrat de la centrale. Sur la deuxième capture, la facture de la semaine part d'un "
"prix de base d'un dinar soixante, et le lait est payé un dinar soixante-trois grâce à la prime de matière grasse. "
"Attention, et c'est important : les valeurs du barème que vous voyez sont indicatives, ce sont des ordres de "
"grandeur. Il me faut la vraie grille de votre centrale pour les remplacer — c'est la première des deux décisions "
"que je vous demande. Deuxième nouveauté : le lait perdu. Les litres qui manquent à l'appel entre ce qui est trait "
"et ce qui est vendu ou donné aux veaux étaient bien comptés, mais on ne savait pas ce qu'ils coûtaient. "
"Maintenant ils sont chiffrés en dinars, avec un seuil d'alerte. Le reste du chantier n'a pas changé : la facture "
"de lait se génère toute seule, la vente d'un animal crée sa facture, et on capte aussi le fumier.",

"Le chantier D, ce sont les équipements. Un équipement coûte cher et s'use : on veut que cette usure, "
"l'amortissement, pèse un peu chaque année sur le résultat, au lieu de tout imputer à l'achat. À l'écran, en haut : "
"un tracteur de quarante-cinq mille dinars perd automatiquement neuf mille dinars par an pendant cinq ans. "
"Mais il manquait la moitié de l'histoire : on amortissait le matériel sans jamais savoir ce qu'il coûte à "
"entretenir. C'est réglé. Sur la deuxième capture, une intervention sur le tracteur : la nature de la panne, "
"la durée d'arrêt, et le coût — trois cent quarante dinars — qui part directement sur le bon atelier. "
"Et l'entretien préventif se planifie : vidange tous les six mois, contrôle technique tous les ans, l'outil "
"rappelle les échéances.",

"Toujours le chantier D, mais un sujet à part : votre troupeau. C'est votre premier actif, et jusqu'ici il "
"n'apparaissait nulle part dans les comptes. Maintenant, chaque vache entre à l'actif au moment de son premier "
"vêlage, c'est-à-dire quand elle devient productive. Si elle a été achetée, elle entre à son prix d'achat réel ; "
"si elle est née sur la ferme, à son coût d'élevage. Ensuite elle s'amortit comme un équipement, et le jour où "
"elle quitte le troupeau, elle sort du bilan toute seule. À l'écran : dix vaches inscrites, vingt-cinq mille dinars "
"de valeur brute, vingt-trois mille après amortissement. Et c'est ici que se pose la deuxième décision que je vous "
"demande : traiter le cheptel comme un bien qui s'amortit, ou comme un stock ? C'est un choix comptable qui vous "
"appartient. J'ai préparé les deux : un seul réglage bascule d'un mode à l'autre.",

"Le chantier E complète le coût : au-delà de la nourriture, il y a l'électricité, l'eau, les assurances, et bien "
"sûr les salaires. Le gros changement est là. Avant, la masse salariale était un montant global tapé à la main : "
"le coût du travail dans le litre de lait n'était donc pas une vraie donnée. Maintenant il y a un registre du "
"personnel : une fiche par salarié, avec son rôle, son contrat, son salaire et son atelier — et on peut répartir "
"quelqu'un entre plusieurs ateliers, par exemple le tractoriste entre la traction et les cultures. La paie du mois "
"se calcule toute seule à partir de ce registre, charges patronales comprises, et se ventile : à l'écran, "
"six mille quatre cent soixante-dix dinars répartis sur cinq ateliers. Quelqu'un qui arrive ou qui part en cours "
"de mois n'est compté qu'au prorata de ses jours. Résultat : le coût du litre inclut maintenant une vraie part "
"de main-d'œuvre.",

"Le chantier F rassemble tout dans un tableau de bord. Vous y retrouvez les grands indicateurs de gestion : "
"le coût complet du litre, l'excédent brut d'exploitation, et l'IOFC — c'est-à-dire ce que rapporte une vache une "
"fois la nourriture payée. Tout est calculé à partir des écritures, jamais ressaisi à la main. Sur la capture, "
"vous voyez les nouveaux venus : le coût de main-d'œuvre par litre, la valeur du lait perdu, le coût d'entretien "
"rapporté au chiffre d'affaires, et la valeur du cheptel. Deuxième point, et c'est celui que je préfère : les "
"seuils. Vous fixez vous-même un objectif de coût par litre, un seuil d'alarme, et dès qu'un indicateur dépasse, "
"il passe en orange ou en rouge automatiquement. Sans avoir besoin de moi, et sans toucher au code.",

"Dernier chantier, le G. Trois points. Le premier : le jour où on lancera l'outil pour de vrai, il faudra repartir "
"des soldes existants — la procédure est prête, on saisira les vrais chiffres une fois que vous aurez validé. "
"Le deuxième : les droits. Un éleveur doit pouvoir faire son travail, mais pas modifier la comptabilité ; les rôles "
"sont séparés, et c'est vérifié par test. Le troisième est nouveau, et c'est peut-être le plus utile pour vous. "
"Jusqu'ici tous les chiffres venaient de données de démonstration. J'ai donc écrit un contrôle de cohérence : "
"vingt-six vérifications automatiques qui passent la base au crible et signalent en orange ou en rouge tout ce qui "
"cloche. Le lait produit qui ne correspond pas au lait facturé, un aliment sans prix d'achat, une sortie d'animal "
"non facturée, un mois de salaires oublié. C'est ce qui nous permettra, le jour où j'aurai une copie de vos vraies "
"données, de dire en une lecture si les chiffres tiennent debout.",

"Pour résumer où on en est : vingt-deux besoins sont couverts, et deux cent six tests automatiques les vérifient — "
"autrement dit, ce n'est pas juste annoncé, c'est contrôlé à chaque modification. Il reste deux décisions, et "
"elles vous appartiennent : la grille de prix de votre centrale, et le traitement comptable du troupeau. "
"Et je le redis parce que c'est important : aucun prix, aucun salaire, aucun seuil n'est figé dans le programme. "
"Tout se règle dans des écrans de configuration.",

"Avant les questions de détail, la question la plus importante, celle qui oriente toute la suite : est-ce bien un "
"outil de pilotage que vous attendez — le coût du litre, les marges — la comptabilité légale restant chez votre "
"expert-comptable ? Ou souhaitez-vous qu'ERPNext tienne aussi la comptabilité complète ? Je préfère que vous "
"tranchiez plutôt que de deviner. Quelle que soit votre réponse, rien de ce qui est construit n'est perdu.",

"Et pour finir, trois questions sur lesquelles j'attends vos retours. Un : est-ce que le fonctionnement colle à la "
"réalité de la ferme — la façon de calculer le coût, le découpage par atelier, le choix des indicateurs ? "
"Deux : les deux décisions dont je vous ai parlé — la grille de prix de la centrale, et le troupeau, bien ou stock ? "
"Trois : qu'est-ce que j'aurais mal compris ? C'est le meilleur moment pour corriger. Les vraies valeurs — prix du "
"lait, primes, salaires, date de démarrage — on les mettra après, une fois qu'on sera d'accord sur la logique.",

"Voilà, j'en ai terminé. Le message que je veux laisser : rien n'est figé. Tout ce que vous avez vu peut être "
"ajusté, complété ou repensé selon vos retours. Je vous remercie, et je suis à votre écoute.",
]

# ─── Gabarit ─────────────────────────────────────────────────────────────────

CSS = """
  :root{
    --bg:#131110; --card:#1c1915; --line:#2e2921; --gold-dim:#b8923f;
    --gold:#e7b65a; --ink:#efe7d6; --muted:#a99b7e;
    --green:#7fc97f; --orange:#f0a35e; --red:#e57373;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{height:100%}
  body{background:var(--bg);color:var(--ink);
    font:16px/1.55 "Avenir Next","Segoe UI",system-ui,sans-serif;overflow:hidden}
  #bar{position:fixed;top:0;left:0;height:3px;background:var(--gold);width:0;z-index:20;transition:width .3s ease}
  #counter{position:fixed;bottom:16px;right:22px;color:var(--muted);font-size:13px;z-index:20}
  #hint{position:fixed;bottom:16px;left:22px;color:var(--muted);font-size:12px;z-index:20;opacity:.65}
  .deck{height:100vh;width:100vw;position:relative}
  .slide{position:absolute;inset:0;padding:5vh 6vw;overflow-y:auto;
    display:none;flex-direction:column;justify-content:center;opacity:0;transition:opacity .35s ease}
  .slide.on{display:flex;opacity:1}
  .kicker{color:var(--gold);font-weight:700;letter-spacing:.15em;font-size:12.5px;text-transform:uppercase;margin-bottom:12px}
  h1{font-size:min(6vw,52px);line-height:1.08;margin-bottom:16px}
  h2{font-size:min(3.6vw,32px);line-height:1.15;margin-bottom:20px}
  .lead{color:var(--muted);font-size:min(2.4vw,19px);max-width:62ch}
  .rule{width:70px;height:4px;background:var(--gold);margin-bottom:20px}
  ul{list-style:none;max-width:70ch}
  li{position:relative;padding-left:24px;margin:9px 0;font-size:min(2.3vw,17px)}
  li::before{content:"";position:absolute;left:0;top:9px;width:8px;height:8px;background:var(--gold);border-radius:2px;transform:rotate(45deg)}
  li b{color:var(--ink)} .muted{color:var(--muted)} li.muted::before{background:var(--muted)}
  b{color:var(--ink)}
  .q{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--gold-dim);
    border-radius:10px;padding:14px 18px;margin-bottom:14px;max-width:92ch;font-size:min(2.2vw,17px)}
  .grid{display:grid;gap:14px}
  .g4{grid-template-columns:repeat(4,1fr)} .g3{grid-template-columns:repeat(3,1fr)}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
  .card.gold{border-color:var(--gold-dim)}
  .card h3{font-size:16px;margin-bottom:6px} .card p{color:var(--muted);font-size:14px}
  .card .big{font-size:26px;color:var(--gold);font-weight:800;display:block;margin-bottom:2px}
  .two{display:grid;grid-template-columns:1.05fr .95fr;gap:30px;align-items:start;max-width:100%}
  .col h3{font-size:14px;letter-spacing:.05em;text-transform:uppercase;margin-bottom:12px}
  .uslist{display:flex;flex-direction:column;gap:11px}
  .us{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:11px 15px}
  .us-h{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
  .usid{font-family:ui-monospace,monospace;color:var(--gold);font-weight:700;font-size:13px}
  .ustitle{font-weight:700;font-size:min(2vw,16px)}
  .usbesoin{color:var(--muted);font-style:italic;font-size:13.5px;margin:3px 0 4px}
  .usdone{font-size:14px}
  .badge{margin-left:auto;font-size:11.5px;font-weight:700;padding:2px 10px;border-radius:99px;white-space:nowrap}
  .badge.ok{background:rgba(127,201,127,.12);color:var(--green);border:1px solid rgba(127,201,127,.35)}
  .badge.wait{background:rgba(240,163,94,.12);color:var(--orange);border:1px solid rgba(240,163,94,.35)}
  .badge.part{background:rgba(231,182,90,.12);color:var(--gold);border:1px solid rgba(231,182,90,.35)}
  .shot{margin:0} .shot + .shot{margin-top:12px}
  .shot img{width:100%;border-radius:10px;border:1px solid var(--line);box-shadow:0 8px 30px rgba(0,0,0,.4);display:block;cursor:zoom-in;transition:transform .18s ease,box-shadow .18s ease}
  .shot img:hover{transform:translateY(-2px);box-shadow:0 14px 40px rgba(0,0,0,.5)}
  .shot figcaption{color:var(--muted);font-size:12.5px;margin-top:7px;text-align:center}
  /* lightbox */
  #lightbox{position:fixed;inset:0;z-index:100;display:none;align-items:center;justify-content:center;
    padding:4vh 4vw;background:rgba(8,6,4,0);transition:background .35s ease;cursor:zoom-out}
  #lightbox.open{display:flex}
  #lightbox.shown{background:rgba(8,6,4,.93)}
  #lightbox img{max-width:92vw;max-height:92vh;border-radius:10px;
    box-shadow:0 24px 70px rgba(0,0,0,.65);will-change:transform;cursor:zoom-out}
  /* notes présentateur */
  #notesBtn{position:fixed;bottom:14px;left:50%;transform:translateX(-50%);z-index:31;
    background:var(--card);color:var(--muted);border:1px solid var(--line);border-radius:99px;
    padding:5px 16px;font-size:12.5px;cursor:pointer;font-family:inherit}
  #notesBtn:hover{color:var(--gold);border-color:var(--gold-dim)}
  #notes{position:fixed;left:0;right:0;bottom:0;z-index:30;background:#0e0c0a;
    border-top:2px solid var(--gold-dim);padding:18px 8vw 26px;max-height:42vh;overflow-y:auto;
    transform:translateY(101%);transition:transform .32s cubic-bezier(.2,.8,.2,1);box-shadow:0 -12px 44px rgba(0,0,0,.55)}
  #notes.open{transform:translateY(0)}
  #notes .lab{color:var(--gold);font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:9px;font-weight:700}
  #notes p{font-size:min(2.2vw,17px);line-height:1.65;max-width:95ch;color:var(--ink)}
  .center{align-items:center;text-align:center} .center ul{text-align:left}
  .foot{margin-top:22px;color:var(--muted);font-size:13.5px}
  .nav-zone{position:fixed;top:0;bottom:0;width:15%;z-index:10;cursor:pointer}
  #prev{left:0} #next{right:0}
  /* mode capture vidéo : ?clean=1 masque tout le chrome de navigation */
  body.clean #bar,body.clean #counter,body.clean #hint,body.clean #notesBtn,
  body.clean .nav-zone{display:none!important}
  @media (max-width:860px){.g4,.g3{grid-template-columns:repeat(2,1fr)} .two{grid-template-columns:1fr} .slide{justify-content:flex-start}}
"""

JS = """
  const NOTES=__NOTES__;
  const slides=[...document.querySelectorAll('.slide')];
  const bar=document.getElementById('bar'),counter=document.getElementById('counter');
  const notesEl=document.getElementById('notes'),ntext=document.getElementById('ntext'),nnum=document.getElementById('nnum');
  let i=0;
  function show(n){
    i=Math.max(0,Math.min(slides.length-1,n));
    slides.forEach((s,k)=>s.classList.toggle('on',k===i));
    bar.style.width=((i+1)/slides.length*100)+'%';
    counter.textContent=(i+1)+' / '+slides.length;
    ntext.textContent=NOTES[i]||'—'; nnum.textContent=(i+1);
    slides[i].scrollTop=0;
    if(history.replaceState) history.replaceState(null,'','?s='+(i+1)+location.hash);
  }
  document.getElementById('next').onclick=()=>show(i+1);
  document.getElementById('prev').onclick=()=>show(i-1);
  function toggleNotes(){notesEl.classList.toggle('open');}
  document.getElementById('notesBtn').addEventListener('click',e=>{e.stopPropagation();toggleNotes();});

  // ── Lightbox (FLIP)
  const lb=document.getElementById('lightbox'),lbimg=document.getElementById('lbimg');
  let thumb=null;
  function flipTo(r){
    const tr=lbimg.getBoundingClientRect();
    const sx=r.width/tr.width, sy=r.height/tr.height;
    const dx=r.left+r.width/2-(tr.left+tr.width/2);
    const dy=r.top+r.height/2-(tr.top+tr.height/2);
    return `translate(${dx}px,${dy}px) scale(${sx},${sy})`;
  }
  function openLB(el){
    thumb=el; lbimg.src=el.src; lb.classList.add('open');
    lbimg.style.transition='none'; lbimg.style.transform=flipTo(el.getBoundingClientRect());
    lbimg.getBoundingClientRect();
    requestAnimationFrame(()=>{
      lb.classList.add('shown');
      lbimg.style.transition='transform .38s cubic-bezier(.2,.8,.2,1)';
      lbimg.style.transform='none';
    });
  }
  function closeLB(){
    if(!thumb) return;
    lbimg.style.transition='transform .3s cubic-bezier(.4,0,.2,1)';
    lbimg.style.transform=flipTo(thumb.getBoundingClientRect());
    lb.classList.remove('shown');
    setTimeout(()=>{lb.classList.remove('open');lbimg.style.transition='none';
      lbimg.style.transform='none';lbimg.removeAttribute('src');thumb=null;},310);
  }
  document.querySelectorAll('.shot img').forEach(im=>im.addEventListener('click',e=>{e.stopPropagation();openLB(im);}));
  lb.addEventListener('click',closeLB);

  document.addEventListener('keydown',e=>{
    if(lb.classList.contains('open')){ if(e.key==='Escape')closeLB(); return; }
    if(e.key==='n'||e.key==='N'){toggleNotes();return;}
    if(['ArrowRight','ArrowDown',' ','PageDown'].includes(e.key)){e.preventDefault();show(i+1);}
    if(['ArrowLeft','ArrowUp','PageUp'].includes(e.key)){e.preventDefault();show(i-1);}
    if(e.key==='Home')show(0); if(e.key==='End')show(slides.length-1);
  });

  // ?s=N ouvre directement une slide (lien profond + rendu des images de la vidéo)
  // ?clean=1 masque le chrome de navigation pour la capture.
  const params=new URLSearchParams(location.search);
  if(params.get('clean')) document.body.classList.add('clean');
  show(parseInt(params.get('s')||'1',10)-1);
"""

GABARIT = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HMD Agro — Pilotage économique · présentation client</title>
<style>{css}</style>
</head>
<body>
<div id="bar"></div>
<div class="deck" id="deck">
{slides}
</div>
<div class="nav-zone" id="prev"></div>
<div class="nav-zone" id="next"></div>
<div id="counter">1 / {n}</div>
<div id="hint">← → naviguer · clic sur une capture pour l'agrandir · <b style="color:var(--muted)">N</b> = notes du présentateur</div>
<button id="notesBtn">🎤 Notes du présentateur (N)</button>
<div id="notes"><div class="lab">À dire — slide <span id="nnum">1</span></div><p id="ntext"></p></div>
<div id="lightbox"><img id="lbimg" alt=""></div>
<script>{js}</script>
</body>
</html>
"""


def embed(match):
    nom = match.group(1)
    fichier = SHOTS / f"{nom}.jpg"
    if not fichier.exists():
        raise SystemExit(f"capture manquante : {fichier}")
    b64 = base64.b64encode(fichier.read_bytes()).decode()
    return f"data:image/jpeg;base64,{b64}"


def main():
    if len(SLIDES) != len(NOTES):
        raise SystemExit(f"{len(SLIDES)} slides mais {len(NOTES)} notes — il en faut autant.")
    corps = "\n".join(SLIDES)
    corps = re.sub(r"\{\{IMG:([a-z_]+)\}\}", embed, corps)
    html = GABARIT.format(
        css=CSS,
        slides=corps,
        n=len(SLIDES),
        js=JS.replace("__NOTES__", json.dumps(NOTES, ensure_ascii=False)),
    )
    SORTIE.write_text(html, encoding="utf-8")
    print(f"{SORTIE} — {len(SLIDES)} slides, {len(html)//1024} Ko")

    # narration exportée à part : sert à build_video.sh et à la relecture
    script = pathlib.Path(__file__).resolve().parent / "narration.json"
    script.write_text(json.dumps(NOTES, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{script} — {len(NOTES)} notes")


if __name__ == "__main__":
    main()
