// SCRUM-10 — Facture d'achat : dès qu'une ligne est imputée à Frais Généraux,
// l'en-tête affiche la clé de répartition (Cost Center Allocation) en vigueur
// à la date de la pièce — c'est elle qui répartira les écritures à la
// validation. Toute la logique est dans hmd_agro.js (window.hmd_cle_repartition,
// chargé partout via app_include_js) ; ici on ne fait que la brancher.
// Toute ligne d'article d'une facture d'achat est une charge.
hmd_cle_repartition.brancher("Purchase Invoice", {
    table: "items",
    child_doctype: "Purchase Invoice Item",
    est_charge: () => true,
});
