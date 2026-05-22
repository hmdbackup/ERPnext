"""
Sprint 5 — One-shot cleanup of stock-module misalignment found in the audit:

  A. Set Stock Settings.default_warehouse = 'Magasin Principal - HMD'
     (was 'Stores - HMD' — the ERPNext-default auto-scaffold warehouse,
     which caused new UI Stock Entries / Purchase Receipts to land in the
     wrong warehouse).

  B. Backfill `Item.item_defaults` for every HMD-managed Item (MED-*, ALI-*,
     SEM-*) so each Item explicitly carries its company + default warehouse.
     This is belt-and-suspenders with (A): even if Stock Settings is changed
     later, our Items remember where they live. Implemented by re-running the
     three migration helpers — they're idempotent and now also push item_defaults.

  C. Delete the draft Purchase Receipt MAT-PRE-2026-00001. It was created
     against 'Stores - HMD' (because of bug A) and was never submitted, so
     no Stock Ledger Entry was ever written for it. Removing keeps the
     workspace clean before Step 3 (price seeding).

Idempotent. Re-running is safe.

Run:
    docker exec frappe_docker_devcontainer-frappe-1 bash -lc \\
      "cd /workspace/development/frappe-bench && bench --site hmd.localhost execute \\
       hmd_agro.hmd_agro.setup.apply_stock_fixes.run"
"""
import frappe

from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_WAREHOUSE as TARGET_DEFAULT_WAREHOUSE
DRAFT_PR_TO_DELETE = "MAT-PRE-2026-00001"


def _step_a():
    print("\n  ── A. Stock Settings.default_warehouse ──")
    current = frappe.db.get_single_value("Stock Settings", "default_warehouse")
    print(f"     current: {current!r}")
    if current == TARGET_DEFAULT_WAREHOUSE:
        print(f"     [skip]   déjà aligné sur {TARGET_DEFAULT_WAREHOUSE}")
        return
    frappe.db.set_single_value("Stock Settings", "default_warehouse",
                               TARGET_DEFAULT_WAREHOUSE)
    print(f"     [update] {current!r} → {TARGET_DEFAULT_WAREHOUSE!r}")


def _step_b():
    print("\n  ── B. Backfill Item Defaults via migration re-run ──")
    from hmd_agro.hmd_agro.setup import (
        medicament_migration, aliment_migration, semence_migration,
    )
    print("     (re-run medicament_migration.migrate_medicaments...)")
    medicament_migration.migrate_medicaments()
    print("     (re-run aliment_migration.migrate_aliments...)")
    aliment_migration.migrate_aliments()
    print("     (re-run semence_migration.migrate_semences...)")
    semence_migration.migrate_semences()


def _step_c():
    print("\n  ── C. Suppression du draft Purchase Receipt ──")
    if not frappe.db.exists("Purchase Receipt", DRAFT_PR_TO_DELETE):
        print(f"     [skip]   {DRAFT_PR_TO_DELETE} n'existe pas (déjà supprimé?)")
        return
    pr = frappe.get_doc("Purchase Receipt", DRAFT_PR_TO_DELETE)
    if pr.docstatus == 1:
        print(f"     [STOP]   {DRAFT_PR_TO_DELETE} est SUBMITTED — refus de "
              f"le supprimer automatiquement. Vérifier manuellement.")
        return
    if pr.docstatus == 2:
        print(f"     [skip]   {DRAFT_PR_TO_DELETE} déjà annulé")
        return
    print(f"     [del]    {DRAFT_PR_TO_DELETE} (Draft, "
          f"supplier={pr.supplier}, qty={pr.total_qty}, total={pr.grand_total})")
    frappe.delete_doc("Purchase Receipt", DRAFT_PR_TO_DELETE,
                      ignore_permissions=True)


@frappe.whitelist()
def run():
    print("\n" + "=" * 70)
    print("  Sprint 5 — Apply stock-module fixes (A + B + C)")
    print("=" * 70)

    _step_a()
    _step_c()  # do C before B so the re-run isn't muddied by a stale draft
    _step_b()

    frappe.db.commit()

    print("\n" + "=" * 70)
    print("  Done. Re-run audit_stock_state.run to verify the ⚠ flags cleared.")
    print("=" * 70 + "\n")
