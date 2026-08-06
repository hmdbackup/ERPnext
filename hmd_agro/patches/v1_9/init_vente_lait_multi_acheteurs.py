"""FIN-S94 — le lait se vend à plusieurs acheteurs : amorçage de la bascule.

Deux gestes, tous deux idempotents (un patch se rejoue à chaque migrate) :

  1. **`client_lait_defaut`** — le nouveau champ de configuration remplace la
     constante `CUSTOMER_LAIT` codée en dur dans `facturation_lait`. On le
     seede à « Centrale Laitière » (l'acheteur historique) UNIQUEMENT s'il est
     vide : un site qui a déjà nommé son acheteur n'est jamais réécrit.
     Rappel maison : les valeurs par défaut du JSON n'atterrissent pas dans
     `tabSingles`, d'où ce seed.

  2. **`acheteur` des décomptes existants** — depuis FIN-S94 l'acheteur est
     une CLÉ : c'est lui qui scope le contrôle de chevauchement (ERR-DLM-04)
     et la recherche du décompte figé. Un décompte sans acheteur ne protège
     plus rien. On renseigne donc ceux qui n'en ont pas, en priorité depuis le
     client de leur facture (la vérité de ce qui a été encaissé), sinon depuis
     `client_lait_defaut`. Les décomptes déjà nommés ne sont pas touchés.
"""
import frappe

CLIENT_LAIT_FALLBACK = "Centrale Laitière"


def execute():
    client = _seed_client_defaut()
    _backfill_acheteur_decomptes(client)
    frappe.db.commit()


def _seed_client_defaut():
    """Seed the config field while it is still empty; return the effective
    value. Same house pattern as v1_6/v1_8: a Single's JSON default never
    reaches `tabSingles`, so `get_config` would read an empty string."""
    if not frappe.db.exists("DocType", "HMD Configuration"):
        return CLIENT_LAIT_FALLBACK
    doc = frappe.get_single("HMD Configuration")
    if not doc.meta.has_field("client_lait_defaut"):
        # Schema not synced yet (patch replayed on an older DB) — nothing to do.
        return CLIENT_LAIT_FALLBACK
    if doc.get("client_lait_defaut"):
        return doc.get("client_lait_defaut")
    doc.set("client_lait_defaut", CLIENT_LAIT_FALLBACK)
    doc.save(ignore_permissions=True)
    print(f"  [config] client_lait_defaut = « {CLIENT_LAIT_FALLBACK} »")
    return CLIENT_LAIT_FALLBACK


def _backfill_acheteur_decomptes(client_defaut):
    if not frappe.db.table_exists("Decompte Lait Mensuel"):
        return
    orphelins = frappe.db.sql("""
        SELECT name, facture FROM `tabDecompte Lait Mensuel`
        WHERE IFNULL(acheteur, '') = ''
    """, as_dict=True)
    for dlm in orphelins:
        acheteur = None
        if dlm.facture:
            acheteur = frappe.db.get_value("Sales Invoice", dlm.facture, "customer")
        acheteur = acheteur or client_defaut
        if not frappe.db.exists("Customer", acheteur):
            # Never invent a Link target: a dangling acheteur would break every
            # later save of the decompte. Leave it blank and say so.
            print(f"  [skip]   Décompte {dlm.name} : client « {acheteur} » "
                  f"introuvable, acheteur laissé vide")
            continue
        # docstatus 1 decomptes are frozen snapshots: write the key in SQL,
        # without touching `modified` — this is a migration, not an edit.
        frappe.db.set_value("Decompte Lait Mensuel", dlm.name, "acheteur",
                            acheteur, update_modified=False)
        print(f"  [migrate] Décompte {dlm.name} → acheteur « {acheteur} »")
