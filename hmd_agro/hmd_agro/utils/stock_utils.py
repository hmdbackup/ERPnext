"""
ERPNext Stock module helpers — used by Traitement (Médicament), Insémination
(Semence), and future Aliment integrations.
"""
import frappe
from frappe.utils import getdate, today

DEFAULT_COMPANY = "hmd-agro"
DEFAULT_WAREHOUSE = "Magasin Principal - HMD"
DEFAULT_UOM = "Unit"


# ─── Atelier d'un animal (RG-FIN-40) ─────────────────────────────────────────
#
# Un mouvement de stock déclenché par un animal — médicament d'un Traitement,
# paillette d'une Insémination, ration d'un lot — porte le centre de coûts de
# SON atelier : vaches → Lait ; velles, veaux, génisses, taurillons →
# Élevage - Génisses. Sans cela ERPNext impute la ligne au centre de coûts par
# défaut de la société, Frais Généraux, et depuis la clé de répartition (Cost
# Center Allocation, décision du 03/09/2026) une ration de vaches serait
# éclatée par la clé au lieu d'aller à 100 % au Lait. Rien à paramétrer :
# l'app pose le centre elle-même, comme elle le fait déjà pour la vente d'un
# animal (`vente_animal`).
ATELIER_VACHES = "Lait"
ATELIER_JEUNES = "Élevage - Génisses"


def atelier_categorie(categorie):
    """Nom court de l'atelier d'une catégorie d'animal (RG-FIN-40)."""
    return ATELIER_VACHES if categorie == "VACHE" else ATELIER_JEUNES


def cost_center_atelier(nom_court, company=DEFAULT_COMPANY):
    """« Lait » → « Lait - HMD », ou None si le socle comptable (Cost
    Centers ateliers) n'est pas posé — ERPNext retombe alors sur le centre
    par défaut de la société."""
    abbr = frappe.db.get_value("Company", company, "abbr")
    nom = f"{nom_court} - {abbr}"
    return nom if frappe.db.exists("Cost Center", nom) else None


def cost_center_categorie(categorie, company=DEFAULT_COMPANY):
    """Centre de coûts de l'atelier d'une catégorie d'animal."""
    return cost_center_atelier(atelier_categorie(categorie), company)


def categories_a_la_date(animaux, date=None):
    """{animal: catégorie} à `date`. Aujourd'hui (ou sans date) : la fiche.
    À une date passée : reconstruite depuis les événements (`live_state`),
    jamais lue sur la fiche — une génisse vêlée depuis est une vache
    aujourd'hui, pas à la date du soin. Une nuance : `live_state` rétrograde
    en génisse toute vache SANS vêlage enregistré ; or les vaches importées
    n'ont pas d'historique de vêlage. Une vache dont aucun vêlage n'est connu
    reste donc une vache à toute date ; seule un premier vêlage postérieur à
    la date la rend génisse ce jour-là."""
    animaux = [a for a in animaux if a]
    if not animaux:
        return {}
    fiche = {r.name: r.categorie for r in frappe.get_all(
        "Animal", filters={"name": ["in", animaux]}, fields=["name", "categorie"])}
    if not date or getdate(date) >= getdate(today()):
        return fiche
    from hmd_agro.hmd_agro.utils.live_state import states_on_date
    etats = states_on_date(animaux, date)
    vaches_sans_velage = {
        nom for nom, cat in fiche.items() if cat == "VACHE"
    } - {r[0] for r in frappe.db.sql(
        "SELECT DISTINCT animal FROM `tabVelage` WHERE animal IN %s", (animaux,))}
    categories = {}
    for nom in animaux:
        categorie = etats.get(nom, (None,))[0] or fiche.get(nom)
        if categorie == "GENISSE" and nom in vaches_sans_velage:
            categorie = "VACHE"
        if categorie:
            categories[nom] = categorie
    return categories


def cost_center_animal(animal, date=None, company=DEFAULT_COMPANY):
    """Centre de coûts de l'atelier d'un animal à `date` (voir
    `categories_a_la_date`)."""
    categorie = categories_a_la_date([animal], date).get(animal)
    return cost_center_categorie(categorie, company) if categorie else None


def cost_center_mouvement(remark):
    """Centre de coûts porté par un mouvement déjà validé, repéré par sa
    remarque. Le mouvement de compensation d'une suppression reprend le même,
    pour que l'annulation soit symétrique au Grand Livre."""
    ligne = frappe.db.sql("""
        SELECT sed.cost_center FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.remarks = %s AND se.docstatus = 1
        ORDER BY se.creation DESC LIMIT 1
    """, (remark,))
    return ligne[0][0] if ligne else None


def ensure_item_default(item_code, company=DEFAULT_COMPANY, warehouse=DEFAULT_WAREHOUSE):
    """Make sure `Item.item_defaults` has a row for `company` pointing at
    `warehouse`. Idempotent: no-op if already correct, updates if mismatched,
    appends if missing. Returns True iff a write happened.

    Why: without this row, ERPNext falls back to `Stock Settings.default_warehouse`
    when a user creates a Stock Entry / Purchase Receipt via UI. That fallback
    used to be `Stores - HMD`, causing a draft PR to silently land stock in the
    wrong warehouse. Per-Item defaults make the warehouse choice explicit and
    survive a future change to Stock Settings.

    Implementation note (ST5-13): writes go through child-table SQL/db_insert
    rather than `Item.save()`. The full save cycle re-runs ERPNext's Item
    validate, which on repeated saves duplicates the stock_uom row in the
    `Item.uoms` table — broke test_stock_integration during Phase C. db ops
    bypass that lifecycle and produce identical visible state."""
    existing = frappe.db.get_value(
        "Item Default",
        {"parent": item_code, "company": company},
        ["name", "default_warehouse"],
        as_dict=True,
    )
    if existing:
        if existing.default_warehouse == warehouse:
            return False
        frappe.db.set_value("Item Default", existing.name,
                            "default_warehouse", warehouse, update_modified=False)
        return True
    max_idx = (frappe.db.sql(
        "SELECT COALESCE(MAX(idx), 0) FROM `tabItem Default` WHERE parent=%s",
        item_code,
    )[0][0]) or 0
    new_doc = frappe.new_doc("Item Default")
    new_doc.parent = item_code
    new_doc.parenttype = "Item"
    new_doc.parentfield = "item_defaults"
    new_doc.company = company
    new_doc.default_warehouse = warehouse
    new_doc.idx = (max_idx or 0) + 1
    new_doc.db_insert()
    return True


def ensure_item_allow_negative_stock(item_code):
    """Set `Item.allow_negative_stock = 1` if not already. Idempotent.
    Returns True iff a write happened.

    Why: production stance — Traitement and Insémination represent real-world
    events that already happened. The system must record them even if our
    Bin count is stale (forgot to enter a Purchase Receipt, miscount, etc.).
    Refusing the operation would force the user to fudge the data. Instead,
    let Bin go negative; the native reorder Material Request (wired via
    ST5-08 + utils/reorder_sync.py) handles replenishment proactively when
    stock falls to reorder_level. Applies uniformly to ALI-, MED-, SEM-.
    """
    current = frappe.db.get_value("Item", item_code, "allow_negative_stock")
    if current:
        return False
    frappe.db.set_value("Item", item_code, "allow_negative_stock", 1)
    return True


def get_valuation_rate(item_code, warehouse):
    """Current CMP (moving average) of (item, warehouse) from Bin. 0 if the
    item was never received at a real price."""
    return float(frappe.db.get_value(
        "Bin", {"item_code": item_code, "warehouse": warehouse}, "valuation_rate"
    ) or 0)


def create_stock_movement(item_code, qty, purpose, warehouse, remark,
                          posting_date=None, company=None, uom=None, batch_no=None,
                          basic_rate=None, cost_center=None):
    """
    Submit a single-line Stock Entry.

    Args:
        item_code:    ERPNext Item code (e.g., "MED-Amoxicilline")
        qty:          quantity (positive number)
        purpose:      "Material Issue" (consumption) or "Material Receipt" (intake)
        warehouse:    warehouse name (e.g., "Magasin Principal - HMD")
        remark:       human-readable trace (e.g., "Traitement TRT-2026-00931")
        posting_date: defaults to today
        company:      defaults to "hmd-agro"
        uom:          defaults to "Unit"
        batch_no:     optional batch ID (required for Items with has_batch_no=1, e.g., Semence)
        basic_rate:   Material Receipt only — explicit unit price (e.g., from a
                      purchase). Default: current CMP so restoration receipts
                      (on_trash mirrors) stay value-symmetric with the issue
                      they compensate instead of diluting the CMP at 0.
        cost_center:  centre de coûts de l'atelier (`cost_center_animal`).
                      Sans lui ERPNext prend le centre par défaut de la
                      société — Frais Généraux, que la clé de répartition
                      éclate entre les ateliers.

    Returns:
        the submitted Stock Entry name (e.g., "MAT-STE-2026-00006")

    Notes (FIN-S11, RG-FIN-30 / CF-FIN-31):
        - Material Issue: no rate is forced — ERPNext values the outgoing
          line at the item's CMP, so SLE.stock_value_difference is real.
        - Garde-fou: while the item has no valuation yet (CMP = 0, never
          purchased), fall back to the legacy zero-valuation flags so field
          entry (Traitement/IA/ration) is never blocked.
        - Stock Entry is submitted (not draft) so Bin updates immediately.
    """
    company = company or DEFAULT_COMPANY
    uom = uom or DEFAULT_UOM

    item_line = {
        "item_code": item_code,
        "qty": qty,
        "uom": uom,
        "stock_uom": uom,
        "conversion_factor": 1,
    }
    cmp_rate = get_valuation_rate(item_code, warehouse)
    if batch_no:
        item_line["batch_no"] = batch_no
    if cost_center:
        item_line["cost_center"] = cost_center
    if purpose == "Material Issue":
        item_line["s_warehouse"] = warehouse
        if not cmp_rate:
            # legacy behavior — item never valued, don't block the operation
            item_line["basic_rate"] = 0
            item_line["allow_zero_valuation_rate"] = 1
    elif purpose == "Material Receipt":
        item_line["t_warehouse"] = warehouse
        rate = basic_rate if basic_rate is not None else cmp_rate
        if rate:
            item_line["basic_rate"] = rate
        else:
            item_line["basic_rate"] = 0
            item_line["allow_zero_valuation_rate"] = 1
    else:
        frappe.throw(f"create_stock_movement: purpose '{purpose}' inconnu")

    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": purpose,
        "company": company,
        "posting_date": posting_date or today(),
        "items": [item_line],
        "remarks": remark,
    })
    se.insert(ignore_permissions=True)
    se.submit()
    return se.name
