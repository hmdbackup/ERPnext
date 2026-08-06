"""
EPIC C — Grille de prix qualité du lait (FIN-S24, RG-FIN-13).

Seede UNE grille de démarrage « Grille Centrale — provisoire » pour que le
prix du litre cesse d'être plat, avec :
  • prix de base = config `prix_reference_lait` (aucun littéral) ;
  • paliers TB/TP aux ordres de grandeur des grilles laitières tunisiennes,
    centrés sur les références de la config (`lait_tb_reference` 3.8 %,
    `lait_tp_reference` 3.2 %).

⚠️ Les montants de primes sont **INDICATIFS** : la grille naît en
`statut = PROVISOIRE`. Facture, rapport périodique et contrôle de cohérence le
signalent tant que le statut n'est pas passé à VALIDEE. Dès que la centrale
fournit sa grille contractuelle : ouvrir « Grille Prix Lait », corriger les
paliers, renseigner `source`, passer le statut à VALIDEE. Aucun code à
toucher.

Idempotent — re-run safe (ne réécrit jamais une grille existante, donc les
corrections saisies en UI survivent à un re-run).

Run:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.setup.finance.grille_lait.setup_grille_lait
"""
import frappe

from hmd_agro.hmd_agro.utils.config import get_config

GRILLE_PROVISOIRE = "Grille Centrale — provisoire"
CENTRALE = "Centrale Laitière"

# (critère, borne_min, borne_max, prime TND/L, libellé)
# Bornes en % — même unité que Bilan Lait Journalier. borne_max None = +∞.
PALIERS_INDICATIFS = [
    ("TB", 0.0, 3.2, -0.060, "TB très bas"),
    ("TB", 3.2, 3.5, -0.030, "TB bas"),
    ("TB", 3.5, 3.8, 0.000, "TB sous référence"),
    ("TB", 3.8, 4.1, 0.030, "TB référence"),
    ("TB", 4.1, None, 0.060, "TB élevé"),
    ("TP", 0.0, 2.9, -0.040, "TP très bas"),
    ("TP", 2.9, 3.2, -0.020, "TP bas"),
    ("TP", 3.2, 3.5, 0.000, "TP référence"),
    ("TP", 3.5, None, 0.020, "TP élevé"),
]

SOURCE = (
    "Valeurs INDICATIVES posées au démarrage (ordres de grandeur des grilles "
    "laitières tunisiennes) — à remplacer par la grille contractuelle de la "
    "centrale, puis passer le statut à VALIDEE."
)


@frappe.whitelist()
def setup_grille_lait(active=1):
    print("\n" + "=" * 60)
    print("  EPIC C — Grille de prix qualité du lait (FIN-S24)")
    print("=" * 60)

    if frappe.db.exists("Grille Prix Lait", GRILLE_PROVISOIRE):
        print(f"  [skip]   Grille « {GRILLE_PROVISOIRE} » existe "
              "(les corrections saisies en UI sont préservées)")
        _rappel_statut()
        frappe.db.commit()
        return GRILLE_PROVISOIRE

    prix_base = float(get_config("prix_reference_lait", default=1.6))
    tb_ref = float(get_config("lait_tb_reference", default=3.8))
    tp_ref = float(get_config("lait_tp_reference", default=3.2))

    doc = frappe.get_doc({
        "doctype": "Grille Prix Lait",
        "nom_grille": GRILLE_PROVISOIRE,
        "centrale": CENTRALE if frappe.db.exists("Customer", CENTRALE) else None,
        "statut": "PROVISOIRE",
        "active": int(active),
        "date_debut": _debut_exercice(),
        "prix_base": prix_base,
        "plancher_prix": 0,
        "plafond_prime": 0,
        "tb_reference": tb_ref,
        "tp_reference": tp_ref,
        "prime_tb_par_point": float(get_config("lait_prime_tb_par_point", default=0.0)),
        "prime_tp_par_point": float(get_config("lait_prime_tp_par_point", default=0.0)),
        "source": SOURCE,
        "paliers": [
            {"critere": critere, "borne_min": bmin, "borne_max": bmax,
             "prime": prime, "libelle": libelle}
            for critere, bmin, bmax, prime, libelle in PALIERS_INDICATIFS
        ],
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"  [create] Grille « {GRILLE_PROVISOIRE} » — base {prix_base} TND/L, "
          f"{len(PALIERS_INDICATIFS)} paliers, active={int(active)}")
    _rappel_statut()
    return doc.name


def _debut_exercice():
    """Début de l'exercice courant — la grille couvre l'année en cours."""
    from frappe.utils import getdate, today

    return f"{getdate(today()).year}-01-01"


def _rappel_statut():
    statut = frappe.db.get_value("Grille Prix Lait", GRILLE_PROVISOIRE, "statut")
    if statut == "PROVISOIRE":
        print("\n  ⚠  Grille PROVISOIRE : les primes TB/TP sont indicatives.")
        print("     Saisir la grille réelle de la centrale, puis statut = VALIDEE.")
    print("=" * 60 + "\n")
