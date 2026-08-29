// SCRUM-10 — Facture d'achat : bloc « Répartition par atelier » visible dès
// qu'une ligne d'article est imputée à Frais Généraux, total réparti affiché
// sous la table. Toute la logique est dans hmd_agro.js (window.hmd_repartition,
// chargé partout via app_include_js) ; ici on ne fait que la brancher.
// Toute ligne d'article d'une facture d'achat est une charge.
hmd_repartition.brancher("Purchase Invoice", {
    table: "items",
    child_doctype: "Purchase Invoice Item",
    est_charge: () => true,
});
