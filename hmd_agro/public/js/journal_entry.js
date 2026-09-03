// SCRUM-10 — Écriture de journal : dès qu'une ligne au débit est imputée à
// Frais Généraux, l'en-tête affiche la clé de répartition (Cost Center
// Allocation) en vigueur à la date de la pièce. Toute la logique est dans
// hmd_agro.js (window.hmd_cle_repartition, chargé partout via app_include_js) ;
// ici on ne fait que la brancher. Côté client, une charge est une ligne au
// débit ; le serveur vérifie en plus que le compte est de classe Expense
// (repartition_charges.lignes_charges).
hmd_cle_repartition.brancher("Journal Entry", {
    table: "accounts",
    child_doctype: "Journal Entry Account",
    est_charge: (ligne) => flt(ligne.debit_in_account_currency) > 0,
});
