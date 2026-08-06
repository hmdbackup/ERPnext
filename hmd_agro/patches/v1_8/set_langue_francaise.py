"""Passe l'interface en français (décision réunion du 05/08/2026).

M. Samir a constaté en démo des écrans mi-français mi-anglais : nos DocTypes
sont en français, mais toute l'interface ERPNext native (Actif, Écriture de
Journal, colonnes de liste, boutons) restait en anglais parce que la langue du
site était « en ». Frappe et ERPNext embarquent les traductions françaises —
il suffit de déclarer la langue.

Trois réglages, tous purement d'affichage :
  1. System Settings.language  → « fr » (défaut de tous les nouveaux comptes)
  2. User.language             → « fr » pour les comptes restés sur « en »,
     sinon la préférence utilisateur continue de forcer l'anglais (c'est
     exactement ce qui s'est produit en démo). Réversible en un clic par
     l'utilisateur : Utilisateur → Langue.
  3. Currency TND.symbol       → « DT » au lieu de « د.ت » : la ferme parle et
     écrit en dinars « DT », et nos rapports libellent déjà les unités en DT.

Idempotent : chaque valeur n'est écrite que si elle porte encore l'ancien
défaut ; une valeur choisie délibérément (autre langue, autre symbole) est
respectée.
"""
import frappe

ANCIENNE_LANGUE = ("", "en")
SYMBOLE_ARABE = "د.ت"


def execute():
    _langue_systeme()
    _langue_utilisateurs()
    _symbole_dinar()
    frappe.db.commit()
    frappe.clear_cache()


def _langue_systeme():
    courante = frappe.db.get_single_value("System Settings", "language")
    if (courante or "") in ANCIENNE_LANGUE:
        frappe.db.set_single_value("System Settings", "language", "fr")
        print(f"  [langue] System Settings.language {courante or 'vide'} -> fr")


def _langue_utilisateurs():
    noms = frappe.db.sql_list(
        """SELECT name FROM `tabUser`
           WHERE IFNULL(language, '') IN ('', 'en') AND name != 'Guest'"""
    )
    if not noms:
        return
    frappe.db.sql(
        """UPDATE `tabUser` SET language = 'fr'
           WHERE IFNULL(language, '') IN ('', 'en') AND name != 'Guest'"""
    )
    print(f"  [langue] {len(noms)} compte(s) passé(s) en français : {', '.join(noms)}")


def _symbole_dinar():
    if not frappe.db.exists("Currency", "TND"):
        return
    symbole = frappe.db.get_value("Currency", "TND", "symbol")
    if symbole == SYMBOLE_ARABE:
        frappe.db.set_value("Currency", "TND", "symbol", "DT", update_modified=False)
        print("  [langue] Symbole TND د.ت -> DT")
