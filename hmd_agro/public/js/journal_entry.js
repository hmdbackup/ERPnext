// SCRUM-10 — Écriture de journal : bloc « Répartition par atelier » visible dès
// qu'une ligne au débit est imputée à Frais Généraux, total réparti affiché
// sous la table. Toute la logique est dans hmd_agro.js (window.hmd_repartition,
// chargé partout via app_include_js) ; ici on ne fait que la brancher.
// Côté client, une charge est une ligne au débit ; le serveur vérifie en plus
// que le compte est de classe Expense (repartition_charges.lignes_charges).
hmd_repartition.brancher("Journal Entry", {
    table: "accounts",
    child_doctype: "Journal Entry Account",
    est_charge: (ligne) => flt(ligne.debit_in_account_currency) > 0,
});
