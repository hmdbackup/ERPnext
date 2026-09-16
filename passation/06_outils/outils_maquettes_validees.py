"""Assemble le dossier des maquettes validées du 24/08/2026.

Reprend tel quel le gabarit visuel de `maquettes_scrum_9_10_11.html` (même
police, mêmes couleurs, mêmes composants de tableau) et y écrit les deux
écrans validés par M. Samir, décisions appliquées. L'écran production
laitière n'est pas validé : il est rappelé en fin de dossier, sans maquette.
"""
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
GABARIT = RACINE / "maquettes_scrum_9_10_11.html"
SORTIE = RACINE / "passation/03_maquettes/maquettes_validees_2026-08-24.html"

tete = GABARIT.read_text(encoding="utf-8").split("</style>")[0]
tete = tete.replace(
    "<title>Maquettes SCRUM-9/10/11</title>",
    "<title>Maquettes validées — 24/08/2026</title>", 1)

# Le gabarit n'a pas de feuille d'impression : les tableaux larges seraient
# rognés par `overflow-x`. On la pose ici, en dernier, pour qu'elle gagne.
IMPRESSION = """
/* ── Décisions actées ──────────────────────────────────── */
.decide.valide{background:var(--ok-soft); border-color:var(--ok)}
.decide.valide h3{color:var(--ok)}
.decide.valide li::before{
  content:"\\2713"; border-color:var(--ok); background:var(--ok); color:var(--surface);
  display:flex; align-items:center; justify-content:center;
  font-size:10px; font-weight:700; line-height:1; border-radius:2px;
}
.decide.ouvert{background:var(--warn-soft); border-color:var(--warn)}
.decide.ouvert h3{color:var(--warn)}
.decide.ouvert li::before{border-color:var(--warn); border-radius:50%}
.decide .suite{
  margin:2px 0 0; padding-top:12px; border-top:1px solid var(--line-strong);
  font-size:.86rem; color:var(--ink-2);
}
.decide .suite b{color:var(--ink)}

/* ── Impression / PDF ──────────────────────────────────── */
@page{size:A4 landscape; margin:11mm 12mm}
@media print{
  :root{
    --ground:#FFFFFF; --surface:#FFFFFF; --surface-2:#EFF1EC; --surface-3:#E7EBE4;
    --ink:#18201A; --ink-2:#5A665C; --ink-3:#7E8A80;
    --line:#D9DFD7; --line-strong:#B7C1B5;
    --accent:#2E6B4F; --accent-soft:#E2EDE6;
    --warn:#8E6211; --warn-soft:#F6EBD6;
    --crit:#9C2F27; --crit-soft:#F7E2E0;
    --ok:#2E6B4F; --ok-soft:#E2EDE6;
    --shadow:none;
  }
  *{-webkit-print-color-adjust:exact; print-color-adjust:exact}
  body{background:#fff; font-size:13px}
  .page{max-width:none; padding:0; gap:26px}
  .masthead{padding-top:0; gap:14px}
  .masthead h1{font-size:1.9rem}
  .us-head h2{font-size:1.25rem}
  .grid-wrap{overflow:visible}
  table{min-width:0; font-size:8.4px}
  thead th{position:static; font-size:7.6px; padding:5px 6px}
  tbody td{padding:3.5px 6px}
  .num{font-size:8.4px}
  .pill{font-size:7.5px; padding:1px 5px}
  .cx{width:11px; height:11px; font-size:7px}
  .num{white-space:nowrap}
  .notes{background:transparent; border:0; gap:7px}
  .notes .note{border:1px solid var(--line); border-radius:3px}
  .notes .cx{flex:0 0 auto}
  .decide li{display:block}
  .decide li::before{float:left; margin:4px 11px 0 0}
  .decide li b{margin-right:5px}
  .notes .note, .decide{break-inside:avoid}
  section.us{break-before:page}
  section.us:first-of-type{break-before:auto}
}
"""

CORPS = """</style>

<div class="page">

<header class="masthead">
  <p class="eyebrow">HMD AGRO · Sprint Finance · Retour de la validation du 24/08/2026</p>
  <h1>Les deux écrans validés</h1>
  <p class="standfirst">Réunion du lundi 24 août avec M. Samir : huit décisions étaient posées,
    une par question, chacune avec ses deux variantes chiffrées. Voici les deux écrans tels
    qu'ils seront construits, décisions appliquées. Le troisième écran — la production
    laitière — n'est pas validé : il est rappelé en fin de dossier.</p>
  <dl class="meta">
    <div><dt>Validé le</dt><dd>Lundi 24 août 2026</dd></div>
    <div><dt>Par</dt><dd>M. Samir (métier)</dd></div>
    <div><dt>Écrans validés</dt><dd>Charges &amp; coût du litre · Parc &amp; interventions</dd></div>
    <div><dt>Reste à revoir</dt><dd>Production laitière</dd></div>
  </dl>
  <div class="avis">
    <p><strong>Ce qui est réel, ce qui illustre.</strong> Les 45 444 litres de juin et les
      interventions de juin-juillet sont réels. Les montants comptables, la ventilation des
      frais généraux et la répartition pièces / main-d'œuvre sont des illustrations cohérentes
      entre elles : la comptabilité de juin ne contient encore que 340 DT, et le détail
      pièces / main-d'œuvre n'existe pas dans les données d'aujourd'hui — c'est précisément
      ce que la décision ③ demande de saisir désormais. Ce sont les <em>règles d'affichage</em>
      qui sont validées, pas les valeurs.</p>
  </div>
</header>

<!-- ══════════════════ SCRUM-10 ══════════════════ -->
<section class="us" id="scrum-10">
  <div class="us-head">
    <p class="key">SCRUM-10 · VALIDÉ</p>
    <h2>Charges par atelier et coût du litre</h2>
    <p class="lede">Deux décisions changent l'écran : les frais généraux ne sont plus répartis
      par une clé unique mais dépense par dépense, et la catégorie « non imputé » disparaît —
      toute charge reçoit son atelier à la saisie.</p>
  </div>

  <figure class="screen">
    <figcaption class="chrome">
      <span class="path">Rapports <span>›</span> Rapport de Performance</span>
      <span class="chip">Date <b>30/06/2026</b></span>
      <span class="chip">Période <b>Mois</b></span>
      <span class="chip">Périmètre coût du litre <b>LAIT_QUOTE_PART</b></span>
    </figcaption>
    <div class="grid-wrap">
      <table>
        <thead>
          <tr><th style="width:44%">Indicateur</th><th style="width:14%">Valeur</th><th style="width:10%">Unité</th><th style="width:16%">M-1 même période</th><th style="width:16%">Δ %</th></tr>
        </thead>
        <tbody>
          <tr class="rupture"><td colspan="5">Charges</td></tr>
          <tr><td>Ration &amp; Aliments (601)</td><td class="num">41 260,00</td><td>DT</td><td class="num">39 880,00</td><td class="num">+3,5 %</td></tr>
          <tr><td>Entretien &amp; Réparations (615)</td><td class="num">2 715,00</td><td>DT</td><td class="num">1 940,00</td><td class="num">+39,9 %</td></tr>
          <tr><td>Charges Totales</td><td class="num">112 100,00</td><td>DT</td><td class="num">108 430,00</td><td class="num">+3,4 %</td></tr>

          <tr class="rupture"><td colspan="5">Charges par Atelier</td></tr>
          <tr><td>Lait — Troupeau Laitier</td><td class="num">63 400,00</td><td>DT</td><td class="num">61 360,00</td><td class="num">+3,3 %</td></tr>
          <tr><td>Culture Fourragère &amp; Traction</td><td class="num">21 650,00</td><td>DT</td><td class="num">20 960,00</td><td class="num">+3,3 %</td></tr>
          <tr><td>Génisses &amp; Élevage</td><td class="num">12 780,00</td><td>DT</td><td class="num">12 410,00</td><td class="num">+3,0 %</td></tr>
          <tr><td>Frais Généraux</td><td class="num">9 840,00</td><td>DT</td><td class="num">9 620,00</td><td class="num">+2,3 %</td></tr>
          <tr><td>Frigorifique</td><td class="num">4 430,00</td><td>DT</td><td class="num">4 080,00</td><td class="num">+8,6 %</td></tr>
          <tr><td><span class="dot green"></span>Contrôle — écriture sans atelier<span class="cx">1</span></td><td class="num">0,00</td><td>DT</td><td class="num">0,00</td><td class="num vide"></td></tr>
          <tr class="total"><td>Total ventilé — doit égaler « Charges Totales »</td><td class="num">112 100,00</td><td>DT</td><td class="num">108 430,00</td><td class="num">+3,4 %</td></tr>

          <tr class="rupture"><td colspan="5">Frais Généraux — clé arbitrée dépense par dépense<span class="cx">2</span></td></tr>
          <tr><td>Gardiennage &amp; surveillance — clé <b>recettes</b> (90,00 % Lait)</td><td class="num">3 200,00</td><td>DT</td><td class="num">3 150,00</td><td class="num">+1,6 %</td></tr>
          <tr><td>Électricité &amp; eau — clé <b>dépenses</b> (61,98 % Lait)</td><td class="num">2 640,00</td><td>DT</td><td class="num">2 560,00</td><td class="num">+3,1 %</td></tr>
          <tr><td>Assurances — clé <b>dépenses</b> (61,98 % Lait)</td><td class="num">1 900,00</td><td>DT</td><td class="num">1 860,00</td><td class="num">+2,2 %</td></tr>
          <tr><td>Administratif &amp; honoraires — clé <b>recettes</b> (90,00 % Lait)</td><td class="num">2 100,00</td><td>DT</td><td class="num">2 050,00</td><td class="num">+2,4 %</td></tr>
          <tr class="sous"><td>Total Frais Généraux du mois</td><td class="num">9 840,00</td><td>DT</td><td class="num">9 620,00</td><td class="num">+2,3 %</td></tr>
          <tr class="total"><td>dont part de l'atelier Lait — somme des arbitrages</td><td class="num">7 583,89</td><td>DT</td><td class="num">7 419,52</td><td class="num">+2,2 %</td></tr>

          <tr class="rupture"><td colspan="5">Coût du Lait (détail)</td></tr>
          <tr><td>Ration &amp; Aliments (601)</td><td class="num">41 260,00</td><td>DT</td><td class="num">39 880,00</td><td class="num">+3,5 %</td></tr>
          <tr><td>Santé &amp; Vétérinaire (602)</td><td class="num">3 180,00</td><td>DT</td><td class="num">2 940,00</td><td class="num">+8,2 %</td></tr>
          <tr><td>Mécanique — Entretien (615)</td><td class="num">620,00</td><td>DT</td><td class="num">480,00</td><td class="num">+29,2 %</td></tr>
          <tr><td>Personnel (64x)</td><td class="num">12 900,00</td><td>DT</td><td class="num">12 900,00</td><td class="num">0,0 %</td></tr>
          <tr><td>Amortissements (68x)</td><td class="num">3 860,00</td><td>DT</td><td class="num">3 860,00</td><td class="num">0,0 %</td></tr>
          <tr><td>Charges financières (66x)</td><td class="num">800,00</td><td>DT</td><td class="num">850,00</td><td class="num">−5,9 %</td></tr>
          <tr><td>Autres charges d'exploitation<span class="cx">3</span></td><td class="num">780,00</td><td>DT</td><td class="num">450,00</td><td class="num">+73,3 %</td></tr>
          <tr class="sous"><td>Sous-total — charges directes atelier Lait</td><td class="num">63 400,00</td><td>DT</td><td class="num">61 360,00</td><td class="num">+3,3 %</td></tr>
          <tr><td>Quote-part des Frais Généraux — somme des clés arbitrées dépense par dépense</td><td class="num">7 583,89</td><td>DT</td><td class="num">7 419,52</td><td class="num">+2,2 %</td></tr>
          <tr class="total"><td>TOTAL — charges retenues pour le coût du litre</td><td class="num">70 983,89</td><td>DT</td><td class="num">68 779,52</td><td class="num">+3,2 %</td></tr>

          <tr class="rupture"><td colspan="5">Coûts Unitaires</td></tr>
          <tr><td>Coût Alimentaire / L</td><td class="num">0,908</td><td>DT/L</td><td class="num">0,895</td><td class="num">+1,5 %</td></tr>
          <tr><td>Coût Mécanique / L (vue analytique — non additionnable au coût complet)</td><td class="num">0,060</td><td>DT/L</td><td class="num">0,044</td><td class="num">+36,4 %</td></tr>
          <tr class="total"><td>Coût Complet / L (atelier Lait + quote-part arbitrée)<span class="cx">4</span></td><td class="num">1,562</td><td>DT/L</td><td class="num">1,544</td><td class="num">+1,2 %</td></tr>
          <tr><td>Coût du Litre hors Amortissement</td><td class="num">1,477</td><td>DT/L</td><td class="num">1,457</td><td class="num">+1,4 %</td></tr>
          <tr><td>IOFC — CA Lait − Coût Alimentaire</td><td class="num">8 682,20</td><td>DT</td><td class="num">8 210,00</td><td class="num">+5,8 %</td></tr>
          <tr><td>IOFC / Vache Lactante / Jour</td><td class="num">3,01</td><td>DT/VL/j</td><td class="num">2,87</td><td class="num">+4,9 %</td></tr>
        </tbody>
      </table>
    </div>
  </figure>

  <div class="notes">
    <div class="note"><span class="cx">1</span><p><b>La ligne « non imputé » devient une ligne de contrôle à zéro.</b> Plus de catégorie fourre-tout : l'atelier est obligatoire à la saisie. La ligne reste affichée, à 0, pour prouver qu'il n'y a rien d'oublié.</p></div>
    <div class="note"><span class="cx">2</span><p><b>Chaque dépense générale porte sa propre clé.</b> Le rapport dit, dépense par dépense, laquelle a été appliquée — plus de clé unique décidée une fois pour toutes.</p></div>
    <div class="note"><span class="cx">3</span><p><b>Les 780 DT autrefois « sans atelier » sont désormais imputés</b> à l'atelier Lait à la saisie ; ils apparaissent ici, au lieu de rester hors du coût du litre.</p></div>
    <div class="note"><span class="cx">4</span><p><b>Le coût du litre devient la somme d'arbitrages individuels.</b> Il se situe entre les deux extrêmes présentés lundi — c'est le prix du « cas par cas », et il impose de tracer la clé retenue chaque mois.</p></div>
  </div>

  <div class="decide valide">
    <h3>Validé le 24/08/2026</h3>
    <ul>
      <li><b>Frais généraux : arbitrage cas par cas.</b><span>Ni le prorata des dépenses seul, ni le prorata des recettes seul. Chaque dépense générale est décidée individuellement — clé A (ce que dépense chaque atelier) ou clé B (ce que rapporte chaque atelier) — et le rapport affiche la clé retenue.</span></li>
      <li><b>Aucune charge « non attribuée ».</b><span>On ne met pas de catégorie « non imputé ». Toute écriture reçoit son atelier au moment de la saisie ; la ligne subsiste uniquement comme contrôle à zéro.</span></li>
    </ul>
    <p class="suite"><b>Ce que ça change à construire :</b> la clé de répartition passe d'un paramètre unique dans <code>HMD Configuration</code> à un choix porté par chaque dépense ; l'atelier devient obligatoire et bloquant à la saisie d'une charge ; le rapport doit conserver, mois par mois, la clé appliquée à chaque dépense pour que le coût du litre reste explicable.</p>
  </div>

  <div class="decide ouvert">
    <h3>Non tranché — à reprendre</h3>
    <ul>
      <li><b>Qui arbitre, et quand ?</b><span>Le cas par cas suppose quelqu'un qui décide la clé de chaque dépense — à la saisie, ou à la clôture du mois ? Sans réponse, la charge repart en attente et le coût du litre attend avec elle.</span></li>
      <li><b>Nom officiel du centre « frigorifique ».</b><span>Provisoire. La fromagerie annoncée en revue viendra dans la même liste.</span></li>
      <li><b>Périmètre officiel du coût du litre.</b><span>Atelier Lait seul, Lait + quote-part (retenu ici), ou toutes charges ? C'est le chiffre qui sera communiqué.</span></li>
    </ul>
  </div>
</section>

<!-- ══════════════════ SCRUM-11 ══════════════════ -->
<section class="us" id="scrum-11">
  <div class="us-head">
    <p class="key">SCRUM-11 · VALIDÉ</p>
    <h2>Parc et interventions</h2>
    <p class="lede">Dans quel état est le matériel, ce qui a été fait ce mois-ci, ce qui arrive
      sous 30 jours, et le rapprochement avec le compte 615. Le coût d'une intervention se
      saisit désormais en deux parts : pièces et main-d'œuvre.</p>
  </div>

  <figure class="screen">
    <figcaption class="chrome">
      <span class="path">Rapports <span>›</span> Rapport des Interventions</span>
      <span class="chip">Date <b>30/06/2026</b></span>
      <span class="chip">Période <b>Mois</b></span>
      <span class="chip">Équipement <b>Tous</b></span>
      <span class="chip">Atelier <b>Tous</b></span>
    </figcaption>
    <div class="grid-wrap">
      <table>
        <thead>
          <tr><th>Section</th><th>Date</th><th>Équipement</th><th>Désignation</th><th>État / Type</th><th>Libellé</th><th>Atelier</th><th>Intervenant</th><th>Pièces</th><th>Main-d'œuvre</th><th>Coût</th><th>Nb Interv.</th><th>Nb Équip.</th></tr>
        </thead>
        <tbody>
          <tr class="rupture"><td colspan="13">Parc — état du matériel</td></tr>
          <tr><td class="lbl">Parc</td><td class="lbl">21/10/2026</td><td class="lbl">ACC-ASS-2026-00003</td><td>Tracteur Massey 385</td><td><span class="pill green">PRÊT</span><span class="cx">1</span></td><td>Dernière : 21/07 — vidange + filtres · 412 h</td><td class="lbl">Culture Fourragère</td><td class="vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr><td class="lbl">Parc</td><td class="lbl">05/09/2026</td><td class="lbl">ACC-ASS-2026-00021</td><td>Tracteur John Deere</td><td><span class="pill amber">EN ATTENTE DE MAINTENANCE</span></td><td>Dernière : 09/07 — courroie alternateur · 780 h</td><td class="lbl">Culture Fourragère</td><td class="vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr><td class="lbl">Parc</td><td class="lbl">18/09/2026</td><td class="lbl">ACC-ASS-2026-00019</td><td>Remorque épandeuse</td><td><span class="pill green">PRÊT</span></td><td>Dernière : 18/06 — graissage</td><td class="lbl">Culture Fourragère</td><td class="vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr><td class="lbl">Parc</td><td class="lbl">06/08/2026</td><td class="lbl">ACC-ASS-2026-00016</td><td>Pompe à vide salle de traite</td><td><span class="pill red">EN PANNE</span></td><td><span class="dot red"></span>Aucune intervention enregistrée · échéance dépassée</td><td class="lbl">Lait — Troupeau</td><td class="vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr><td class="lbl">Parc</td><td class="lbl">23/12/2026</td><td class="lbl">ACC-ASS-2026-00012</td><td>Groupe électrogène 60 kVA</td><td><span class="pill green">PRÊT</span></td><td>Dernière : 23/06 — contrôle 250 h · 128 h</td><td class="lbl">Frais Généraux</td><td class="vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr><td class="lbl">Parc</td><td class="lbl">11/12/2026</td><td class="lbl">ACC-ASS-2026-00007</td><td>Tank à lait 3 000 L</td><td><span class="pill green">PRÊT</span></td><td>Dernière : 11/06 — sonde de température</td><td class="lbl">Lait — Troupeau</td><td class="vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr class="total"><td class="lbl">Parc</td><td class="vide"></td><td class="vide"></td><td class="vide"></td><td class="vide"></td><td>TOTAL — 4 prêts, 1 en attente de maintenance, 1 en panne</td><td class="vide"></td><td class="vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num">6</td></tr>

          <tr class="rupture"><td colspan="13">Réalisées<span class="cx">2</span></td></tr>
          <tr><td class="lbl">Réalisées</td><td class="lbl">06/06/2026</td><td class="lbl">ACC-ASS-2026-00003</td><td>Tracteur Massey 385</td><td><span class="pill green">PRÉVENTIVE</span></td><td>Vidange moteur + filtres</td><td class="lbl">Culture Fourragère</td><td>Atelier Ben Salah</td><td class="num">260,00</td><td class="num">80,00</td><td class="num">340,00</td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr><td class="lbl">Réalisées</td><td class="lbl">11/06/2026</td><td class="lbl">ACC-ASS-2026-00007</td><td>Tank à lait 3 000 L</td><td><span class="pill amber">CURATIVE</span></td><td>Remplacement sonde de température</td><td class="lbl">Lait — Troupeau</td><td>Frigotech</td><td class="num">450,00</td><td class="num">170,00</td><td class="num">620,00</td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr><td class="lbl">Réalisées</td><td class="lbl">18/06/2026</td><td class="lbl">ACC-ASS-2026-00012</td><td>Groupe électrogène 60 kVA</td><td><span class="pill green">PRÉVENTIVE</span></td><td>Contrôle 250 h + filtre à air</td><td class="lbl">Frais Généraux</td><td>Interne</td><td class="num">120,00</td><td class="num">60,00</td><td class="num">180,00</td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr><td class="lbl">Réalisées</td><td class="lbl">23/06/2026</td><td class="lbl">ACC-ASS-2026-00003</td><td>Tracteur Massey 385</td><td><span class="pill amber">CURATIVE</span></td><td>Réparation circuit hydraulique</td><td class="lbl">Culture Fourragère</td><td>Atelier Ben Salah</td><td class="num">980,00</td><td class="num">500,00</td><td class="num">1 480,00</td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr><td class="lbl">Réalisées</td><td class="lbl">27/06/2026</td><td class="lbl">ACC-ASS-2026-00019</td><td>Remorque épandeuse</td><td><span class="pill green">PRÉVENTIVE</span></td><td>Graissage + contrôle pneus</td><td class="lbl">Culture Fourragère</td><td>Interne</td><td class="num">45,00</td><td class="num">50,00</td><td class="num">95,00</td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr class="total"><td class="lbl">Réalisées</td><td class="vide"></td><td class="vide"></td><td class="vide"></td><td class="vide"></td><td>TOTAL — 5 intervention(s), 4 équipement(s)</td><td class="vide"></td><td class="vide"></td><td class="num">1 855,00</td><td class="num">860,00</td><td class="num">2 715,00</td><td class="num">5</td><td class="num">4</td></tr>

          <tr class="rupture"><td colspan="13">Préventif — 30 prochains jours<span class="cx">3</span></td></tr>
          <tr><td class="lbl">Préventif</td><td class="lbl">28/06/2026</td><td class="lbl">ACC-ASS-2026-00016</td><td>Pompe à vide salle de traite</td><td><span class="pill red">EN RETARD</span></td><td>Contrôle mensuel de dépression</td><td class="lbl">Lait — Troupeau</td><td class="vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr><td class="lbl">Préventif</td><td class="lbl">05/07/2026</td><td class="lbl">ACC-ASS-2026-00003</td><td>Tracteur Massey 385</td><td><span class="pill amber">À VENIR</span></td><td>Vidange 500 h</td><td class="lbl">Culture Fourragère</td><td class="vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr><td class="lbl">Préventif</td><td class="lbl">14/07/2026</td><td class="lbl">ACC-ASS-2026-00007</td><td>Tank à lait 3 000 L</td><td><span class="pill">À VENIR</span></td><td>Nettoyage du condenseur</td><td class="lbl">Lait — Troupeau</td><td class="vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num vide"></td></tr>

          <tr class="rupture"><td colspan="13">Rapprochement</td></tr>
          <tr><td class="lbl">Rapprochement</td><td class="vide"></td><td class="vide"></td><td class="vide"></td><td class="vide"></td><td>Entretien au Grand Livre (compte 615)</td><td class="vide"></td><td class="vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num">2 715,00</td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr><td class="lbl">Rapprochement</td><td class="vide"></td><td class="vide"></td><td class="vide"></td><td class="vide"></td><td>Somme des interventions saisies</td><td class="vide"></td><td class="vide"></td><td class="num">1 855,00</td><td class="num">860,00</td><td class="num">2 715,00</td><td class="num vide"></td><td class="num vide"></td></tr>
          <tr class="total"><td class="lbl">Rapprochement</td><td class="vide"></td><td class="vide"></td><td class="vide"></td><td class="vide"></td><td><span class="dot green"></span>Écart — aucun, chaque dinar d'entretien est rattaché</td><td class="vide"></td><td class="vide"></td><td class="num vide"></td><td class="num vide"></td><td class="num">0,00</td><td class="num vide"></td><td class="num vide"></td></tr>
        </tbody>
      </table>
    </div>
  </figure>

  <div class="notes">
    <div class="note"><span class="cx">1</span><p><b>Un seul mot par équipement.</b> Trois valeurs, une seule liste : <b>Prêt</b>, <b>En panne</b>, <b>En attente de maintenance</b>. Pas de champ « disponible » à côté — « elle roule encore mais il faut la regarder » se dit « en attente de maintenance ».</p></div>
    <div class="note"><span class="cx">2</span><p><b>Chaque ligne est cliquable</b> et ouvre le détail de l'intervention : pièces posées, temps passé, facture de l'atelier extérieur, écriture au 615.</p></div>
    <div class="note"><span class="cx">3</span><p><b>La fenêtre du préventif reste à 30 jours.</b> Trois lignes lundi matin plutôt que neuf : ce qui tombe en octobre n'apparaîtra qu'en septembre, et l'urgent ne se noie pas dans le lointain.</p></div>
  </div>

  <div class="decide valide">
    <h3>Validé le 24/08/2026</h3>
    <ul>
      <li><b>État du matériel : une seule liste.</b><span>Valeurs retenues : Prêt · En panne · En attente de maintenance. Un seul champ, un seul clic à la saisie.</span></li>
      <li><b>Préventif : fenêtre de 30 jours.</b><span>C'est déjà ce que fait le système — la décision le confirme au lieu de le subir.</span></li>
      <li><b>Pièces et main-d'œuvre séparées, plus le type et le coût.</b><span>Chaque intervention porte son type (préventive / curative), le montant des pièces, celui de la main-d'œuvre, et le coût total qui s'en déduit. C'est ce qui permettra de dire « on paye trop cher la main-d'œuvre extérieure ».</span></li>
      <li><b>Chaque intervention mène à son détail.</b><span>La ligne du rapport n'est pas une fin : elle ouvre la fiche complète de l'intervention.</span></li>
    </ul>
    <p class="suite"><b>Ce que ça change à construire :</b> un champ État à trois valeurs sur la fiche équipement (l'état mécanique n'existe nulle part aujourd'hui — ERPNext ne connaît que le statut comptable : en service, cédé, mis au rebut) ; deux montants au lieu d'un sur l'Asset Repair, le total restant calculé ; et le lien de la ligne de rapport vers la fiche.</p>
  </div>

  <div class="decide ouvert">
    <h3>Non tranché — à reprendre</h3>
    <ul>
      <li><b>Déclencheurs de l'entretien préventif.</b><span>Jours calendaires, heures de marche, ou fréquence ? La périodicité ERPNext est purement calendaire ; le seuil au compteur d'heures est à construire. La réponse peut différer d'un équipement à l'autre.</span></li>
      <li><b>Le parc réel.</b><span>Un seul équipement est aujourd'hui saisi dans le système. La liste ci-dessus est un exemple : il faut l'inventaire réel pour que l'écran dise vrai.</span></li>
    </ul>
  </div>
</section>

<!-- ══════════════════ SCRUM-9 ══════════════════ -->
<section class="us" id="scrum-9">
  <div class="us-head">
    <p class="key">SCRUM-9 · NON VALIDÉ</p>
    <h2>Production laitière — l'écran reste à revoir</h2>
    <p class="lede">Le troisième écran n'est pas validé et ne part pas en construction. Il sera
      repris dans une prochaine séance ; ce qui suit est ce qu'il faudra y trancher.</p>
  </div>

  <div class="decide ouvert">
    <h3>À reprendre sur cet écran</h3>
    <ul>
      <li><b>Le point acquis : l'écart n'est pas un sujet.</b><span>Les 9 959 litres d'écart entre la somme des traites et le bilan de la ferme ne posent pas de problème au métier. Aucune alerte n'est donc à construire dessus — c'est autant de moins à développer.</span></li>
      <li><b>Quel comptage fait référence.</b><span>La somme des traites (45 444 L, relevé vache par vache, 30 jours sur 30) ou le bilan de la ferme (35 485 L, ce qu'on retrouve au tank, saisi 26 jours sur 30) ? Le choix décide de tous les litres affichés ailleurs.</span></li>
      <li><b>Les taux TB / TP.</b><span>Rien n'est saisi aujourd'hui sur les 30 jours de juin. D'où viennent ces taux, et à quelle fréquence ?</span></li>
      <li><b>Bloquant, indépendant des arbitrages : les vêlages.</b><span>Le système compte 0 vache lactante parce qu'aucun vêlage n'est enregistré sur juin. Le litres/vache/jour — l'indicateur central de toute la démarche — restera vide tant que les vêlages ne seront pas saisis. Il faut savoir d'où ils viennent.</span></li>
    </ul>
  </div>
</section>

<footer class="pied">
  <h2>Où en est-on</h2>
  <p>Deux écrans sur trois sont validés côté métier : le critère 2 de notre Definition of Ready
    (« maquette partagée et validée avec le métier ») est franchi pour
    <b>Charges &amp; coût du litre</b> et <b>Parc &amp; interventions</b>. Restent les points
    listés en jaune sous chaque écran — ils ne bloquent pas la construction, sauf le premier
    de SCRUM-10 : sans réponse sur <em>qui</em> arbitre la clé de chaque dépense générale, le
    coût du litre reste en attente.</p>
  <p>Les écrans réels sur le site de démonstration :
    <code>Rapport de Performance</code> et <code>Rapport des Interventions</code>,
    période <b>Mois</b>, date au dernier jour du mois.</p>
</footer>

</div>
"""

SORTIE.write_text(tete + IMPRESSION + CORPS, encoding="utf-8")
print("écrit :", SORTIE, SORTIE.stat().st_size, "octets")
