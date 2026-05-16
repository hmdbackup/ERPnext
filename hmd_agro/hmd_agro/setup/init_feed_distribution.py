"""
Sprint 5 — SCRUM-123 — Step 1: one-shot setup for the feed-distribution generator.

Three idempotent actions:

  1. Enable per-Item `allow_negative_stock = 1` on every ALI-* Item.
     Why: feed receipts are sporadic (truckload deliveries) but daily
     distribution is constant. Aliment stock will frequently go negative
     between deliveries. ERPNext's default is to refuse Material Issues
     that would push Bin below 0 — we override that for Aliment ONLY.
     Médicament + Semence stay strict (you can't issue stock you don't have).

  2. Add Custom Field `id_lot` (Link → Lot) on Stock Entry. This lets the
     daily distribution generator stamp each Stock Entry with the Lot that
     consumed the feed, so ST5-09 / ST5-10 reports can filter by lot.
     Created programmatically (NOT via fixtures) so the Custom Field is
     idempotent without touching hooks.py's existing fixture filters.

  3. Sanity-check that `Stock Settings.allow_negative_stock` is still 0.
     The global flag is intentionally OFF — we only allow negatives per-Item.
     If this is non-zero, log a warning (we don't reset it; that's a
     deliberate operator decision).

Idempotent: safe to re-run.

Run:
    docker exec frappe_docker_devcontainer-frappe-1 bash -lc \\
      "cd /workspace/development/frappe-bench && bench --site hmd.localhost execute \\
       hmd_agro.hmd_agro.setup.init_feed_distribution.run"
"""
import frappe


CUSTOM_FIELD_FIELDNAME = "id_lot"
CUSTOM_FIELD_DT = "Stock Entry"


def _enable_aliment_negative_stock():
    print("\n  ── 1. Item.allow_negative_stock on ALI-* ──")
    items = frappe.get_all(
        "Item",
        filters={"item_code": ["like", "ALI-%"]},
        fields=["name", "item_code", "allow_negative_stock"],
        order_by="item_code",
    )
    if not items:
        print("     (aucun Item ALI-* trouvé)")
        return {"enabled": 0, "already": 0}

    enabled = 0
    already = 0
    for it in items:
        if it.allow_negative_stock:
            print(f"     [skip]   {it.item_code} (déjà = 1)")
            already += 1
            continue
        frappe.db.set_value("Item", it.name, "allow_negative_stock", 1)
        print(f"     [update] {it.item_code} 0 → 1")
        enabled += 1
    return {"enabled": enabled, "already": already}


def _ensure_id_lot_custom_field():
    print(f"\n  ── 2. Custom Field {CUSTOM_FIELD_DT}.{CUSTOM_FIELD_FIELDNAME} ──")
    existing = frappe.db.get_value(
        "Custom Field",
        {"dt": CUSTOM_FIELD_DT, "fieldname": CUSTOM_FIELD_FIELDNAME},
        "name",
    )
    if existing:
        print(f"     [skip]   déjà existant ({existing})")
        return {"created": 0}

    # insert_after = posting_time: places id_lot just below posting date/time,
    # near the top of the form where workflow-relevant fields live.
    cf = frappe.get_doc({
        "doctype": "Custom Field",
        "dt": CUSTOM_FIELD_DT,
        "fieldname": CUSTOM_FIELD_FIELDNAME,
        "label": "Lot HMD",
        "fieldtype": "Link",
        "options": "Lot",
        "insert_after": "posting_time",
        "read_only": 0,
        "print_hide": 0,
        "description": (
            "Rempli automatiquement par feed_distribution.py quand le "
            "Stock Entry représente la consommation quotidienne d'un Lot. "
            "Vide pour les autres Stock Entries."
        ),
    })
    cf.insert(ignore_permissions=True)
    print(f"     [create] {cf.name}")
    return {"created": 1}


def _check_global_negative_stock():
    print("\n  ── 3. Stock Settings.allow_negative_stock (sanity) ──")
    val = frappe.db.get_single_value("Stock Settings", "allow_negative_stock")
    if val:
        print(f"     ⚠ flag global = {val} (devrait être 0 pour notre approche per-Item)")
    else:
        print(f"     ✓ flag global = 0 (per-Item override actif sur ALI-* seulement)")
    return {"global_flag": val}


@frappe.whitelist()
def run():
    print("\n" + "=" * 70)
    print("  Sprint 5 — SCRUM-123 — Setup feed distribution")
    print("=" * 70)

    r1 = _enable_aliment_negative_stock()
    r2 = _ensure_id_lot_custom_field()
    r3 = _check_global_negative_stock()

    frappe.db.commit()

    print("\n" + "=" * 70)
    print(f"  ALI-* allow_negative_stock: enabled={r1['enabled']}, "
          f"already={r1['already']}")
    print(f"  Custom Field id_lot:        created={r2['created']}")
    print(f"  Global negative flag:       {r3['global_flag']}")
    print("=" * 70)
    print("  Prochaine étape: écrire utils/feed_distribution.py et faire un dry-run.")
    print("=" * 70 + "\n")
    return {"aliment_flags": r1, "custom_field": r2, "global": r3}
