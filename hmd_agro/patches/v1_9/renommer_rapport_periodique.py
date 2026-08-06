"""FIN-S95 — « Rapport Mensuel » devient « Rapport Periodique ».

Réunion du 05/08/2026 : « zid n7i mensuel mena, 7otou rapport » — le rapport
n'est plus mensuel, il se lit au jour, à la semaine ou à la quinzaine. Le
dossier `report/rapport_mensuel` est devenu `report/rapport_periodique` et le
JSON porte désormais `name`/`report_name` = « Rapport Periodique » (nom
technique sans accent, comme « Controle Coherence Finance »).

Reste le document `Report` déjà en base. Deux situations, parce que la
synchronisation des fichiers (`frappe.model.sync.sync_all`) tourne AVANT les
patches `post_model_sync` :

  1. Cas normal d'un `bench migrate` — la synchro a déjà créé
     « Rapport Periodique » à partir du nouveau JSON, et « Rapport Mensuel »
     traîne en orphelin (son dossier n'existe plus). On FUSIONNE l'ancien dans
     le nouveau : `rename_doc(merge=True)` repointe tous les liens (Auto Email
     Report, Prepared Report, rôles) puis supprime l'orphelin. La suppression
     d'un rapport standard est autorisée ici parce que `frappe.flags.in_migrate`
     est levé (cf. `Report.on_trash`).

  2. Patch rejoué seul, sans synchro préalable — le nouveau n'existe pas
     encore : simple renommage.

Idempotent : si « Rapport Mensuel » n'existe plus (site déjà migré, ou site
neuf qui n'a jamais connu l'ancien nom), le patch ne fait rien.
"""
import frappe

ANCIEN = "Rapport Mensuel"
NOUVEAU = "Rapport Periodique"


def execute():
    if not frappe.db.exists("Report", ANCIEN):
        return                              # déjà renommé, ou jamais installé

    fusion = bool(frappe.db.exists("Report", NOUVEAU))
    # `rename_doc` de Frappe v15 n'accepte pas `ignore_permissions` : le patch
    # tourne en Administrator, `force=True` suffit à passer outre les contrôles.
    frappe.rename_doc("Report", ANCIEN, NOUVEAU, merge=fusion, force=True,
                      show_alert=False)
    # `rename_doc` ne réécrit le champ d'autoname (`field:report_name`) que sur
    # un renommage simple ; en fusion le document cible le porte déjà. On le
    # force dans les deux cas : c'est la valeur affichée dans le bureau.
    frappe.db.set_value("Report", NOUVEAU, "report_name", NOUVEAU,
                        update_modified=False)
    _repointer_raccourcis()
    frappe.db.commit()
    frappe.clear_cache()
    print(f"  [migrate] Rapport « {ANCIEN} » → « {NOUVEAU} »"
          + (" (fusion de l'orphelin)" if fusion else ""))


def _repointer_raccourcis():
    """Les raccourcis d'espace de travail pointent le rapport par une chaîne
    (`link_to`) et non par un Link : `rename_doc` ne les suit pas. Le fixture
    `workspace.json` porte déjà le nouveau nom et sera réimporté en fin de
    migrate, mais un espace de travail personnalisé (créé dans l'interface)
    garderait sinon un raccourci mort.

    PIÈGE : le bloc de contenu (`Workspace.content`, du JSON sérialisé) désigne
    le raccourci par son LABEL. Renommer le raccourci sans réécrire le contenu
    ferait disparaître la tuile de la page. Les deux vont donc ensemble.
    """
    if not frappe.db.table_exists("Workspace Shortcut"):
        return
    frappe.db.sql("""
        UPDATE `tabWorkspace Shortcut`
        SET link_to = %s, label = %s
        WHERE type = 'Report' AND link_to = %s
    """, (NOUVEAU, NOUVEAU, ANCIEN))
    frappe.db.sql("""
        UPDATE `tabWorkspace`
        SET content = REPLACE(content, %s, %s)
        WHERE content LIKE %s
    """, (ANCIEN, NOUVEAU, f"%{ANCIEN}%"))
