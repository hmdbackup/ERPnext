app_name = "hmd_agro"
app_title = "HMD AGRO "
app_publisher = "Mouhib Bouzamita"
app_description = "Custom dairy farm management system for HMD AGRO - animal"
app_email = "mouhibbouzamita@gmail.com"
app_license = "mit"

# Fixtures
# --------
# Exported via `bench export-fixtures --app hmd_agro`
# Imported automatically when the app is installed on a fresh site
HMD_DOCTYPES = [
	"Animal", "Lactation", "Traite", "Insemination", "Velage", "Avortement",
	"Alerte", "Lot", "Batiment", "Pesee", "Etat Corporel", "Semence", "Taureau",
	"Mere Externe", "Traitement", "Traitement Medicale", "Medicament",
	"Aliment", "Ration", "Composition Ration",
	# Finance — registre du personnel (FIN-S42) et grille prix lait (FIN-S24)
	"Personnel", "Personnel Repartition",
	# RH (A2) — historique de salaire immuable et primes
	"Personnel Salaire Historique", "Prime Personnel",
	"Grille Prix Lait", "Grille Prix Lait Palier",
	# Finance — historisation stricte des recettes lait (FIN-B1)
	"Decompte Lait Mensuel",
	# Finance — vente du lait à plusieurs acheteurs (FIN-S94)
	"Bilan Lait Journalier", "Bilan Lait Vente",
	# Finance — heures d'utilisation & coût mécanique des équipements (FIN-S96)
	"Utilisation Equipement",
]

# Custom Fields posés par HMD sur des DocTypes ERPNext core (le filtre
# `dt in HMD_DOCTYPES` ne les attrape pas — il faut les nommer).
#   Stock Entry-id_lot                SCRUM-123
#   Asset-id_batiment / -id_animal    FIN-S30 / FIN-S31 (RC-FIN-53/55)
#   Asset-cout_horaire                TASK B3 coût horaire équipement
#   Asset Repair-*                    FIN-S32 (RC-FIN-54) interventions
CORE_CUSTOM_FIELDS = [
	"Stock Entry-id_lot",
	"Asset-id_batiment",
	"Asset-id_animal",
	"Asset-cout_horaire",
	"Asset Repair-type_intervention",
	"Asset Repair-personnel",
	"Asset Repair-reference_hmd",
	# SCRUM-10 — la table « Répartition par atelier » (PI / JE) est retirée
	# depuis le 03/09/2026 : la clé de répartition est une Cost Center
	# Allocation ERPNext (patch v1_10.retirer_repartition_par_ligne).
	# SCRUM-11 — fiche d'intervention : pièces / main-d'œuvre / prestataire
	"Asset Repair-cout_pieces",
	"Asset Repair-cout_main_oeuvre",
	"Asset Repair-prestataire",
]

# Property Setters posés sur des DocTypes ERPNext (même logique que
# CORE_CUSTOM_FIELDS : nommés explicitement pour être exportés/importés).
CORE_PROPERTY_SETTERS = [
	# SCRUM-11 — statut « Planned » : intervention planifiée, à venir. ERPNext
	# passe l'équipement « Out of Order » pour TOUTE fiche « Pending », d'où un
	# statut distinct pour ce qui n'est pas une panne.
	"Asset Repair-repair_status-options",
	# Statut visible dès la création : une fiche dupliquée revient à « Pending »
	# (no_copy) et, le champ masqué sur un document nouveau, l'équipement
	# passait « Out of Order » au premier enregistrement.
	"Asset Repair-repair_status-depends_on",
]

fixtures = [
	{"dt": "Workspace", "filters": [["module", "=", "HMD AGRO"]]},
	{"dt": "Property Setter", "or_filters": [
		["doc_type", "in", HMD_DOCTYPES],
		["name", "in", CORE_PROPERTY_SETTERS],
	]},
	# UNE seule entrée « Custom Field » : `export_fixtures` réécrit
	# fixtures/custom_field.json à chaque entrée du hook portant ce DocType,
	# donc plusieurs entrées s'écrasent les unes les autres et seule la
	# dernière survit à l'export.
	{"dt": "Custom Field", "or_filters": [
		["dt", "in", HMD_DOCTYPES],
		["name", "in", CORE_CUSTOM_FIELDS],
	]},
	# Number Cards + Dashboard Charts — protect UI-created cards from being
	# wiped on `bench migrate`. Filter by module so we only export HMD's, not
	# ERPNext built-ins (Active Suppliers, etc.).
	{"dt": "Number Card", "filters": [["module", "=", "HMD AGRO"]]},
	{"dt": "Dashboard Chart", "filters": [["module", "=", "HMD AGRO"]]},
]

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "hmd_agro",
# 		"logo": "/assets/hmd_agro/logo.png",
# 		"title": "HMD AGRO ",
# 		"route": "/hmd_agro",
# 		"has_permission": "hmd_agro.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/hmd_agro/css/hmd_agro.css"
app_include_js = "/assets/hmd_agro/js/hmd_agro.js"

# Inject HMD Configuration values into bootinfo so report .js can read them via
# `frappe.boot.hmd_config.<field>` without extra HTTP requests.
boot_session = "hmd_agro.boot.boot_session"

# include js, css files in header of web template
# web_include_css = "/assets/hmd_agro/css/hmd_agro.css"
# web_include_js = "/assets/hmd_agro/js/hmd_agro.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "hmd_agro/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	# SCRUM-10 — clé de répartition (Cost Center Allocation) en vigueur affichée
	# en en-tête dès qu'une ligne est imputée à Frais Généraux.
	"Purchase Invoice": "public/js/purchase_invoice.js",
	"Journal Entry": "public/js/journal_entry.js",
	# SCRUM-10 — une nouvelle clé arrive pré-remplie (centre, date, ateliers).
	"Cost Center Allocation": "public/js/cost_center_allocation.js",
	# SCRUM-11 — état de la fiche, bouton « Planifier la prochaine ».
	"Asset Repair": "public/js/asset_repair.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "hmd_agro/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "hmd_agro.utils.jinja_methods",
# 	"filters": "hmd_agro.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "hmd_agro.install.before_install"
# after_install = "hmd_agro.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "hmd_agro.uninstall.before_uninstall"
# after_uninstall = "hmd_agro.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "hmd_agro.utils.before_app_install"
# after_app_install = "hmd_agro.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "hmd_agro.utils.before_app_uninstall"
# after_app_uninstall = "hmd_agro.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "hmd_agro.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	# SCRUM-10 — une charge Frais Généraux sans clé de répartition en vigueur à
	# sa date : avertissement, ou ERR-FIN-11 en mode strict.
	"Purchase Invoice": {
		"validate": "hmd_agro.hmd_agro.utils.repartition_charges.verifier_cle_frais_generaux",
	},
	"Journal Entry": {
		"validate": "hmd_agro.hmd_agro.utils.repartition_charges.verifier_cle_frais_generaux",
	},
	# SCRUM-11 — fiche d'intervention (ERR-MNT-09..13)
	"Asset Repair": {
		"before_validate": "hmd_agro.hmd_agro.utils.maintenance_utils.completer_couts_fiche",
		"validate": "hmd_agro.hmd_agro.utils.maintenance_utils.valider_fiche_intervention",
		"before_submit": "hmd_agro.hmd_agro.utils.maintenance_utils.verifier_fiche_avant_validation",
	},
}
# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
# 	"all": [
# 		"hmd_agro.tasks.all"
# 	],
 	"daily": [
# 		"hmd_agro.tasks.daily"
        "hmd_agro.hmd_agro.doctype.alerte.alerte.generate_alerts",
        "hmd_agro.hmd_agro.doctype.traitement.traitement.refresh_attente_lait",
        "hmd_agro.hmd_agro.utils.feed_distribution.generate_daily_distribution"
 	],
 	"monthly": [
        # FIN-S21 — facture lait du mois précédent (idempotent, marqueur remarks)
        "hmd_agro.hmd_agro.utils.facturation_lait.generate_monthly_milk_invoice",
        # FIN-S42 — masse salariale du mois écoulé depuis le registre Personnel
        # (idempotent, sans effet tant que le registre est vide)
        "hmd_agro.hmd_agro.utils.charges_utils.post_salaires_mois_precedent",
        # FIN-S31 — immobilise les vaches entrées en production dans le mois
        # (no-op tant que cheptel_mode = NON_VALORISE)
        "hmd_agro.hmd_agro.utils.cheptel_valorisation.synchroniser_cheptel"
 	],
 }

# Testing
# -------

# before_tests = "hmd_agro.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "hmd_agro.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "hmd_agro.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["hmd_agro.utils.before_request"]
# after_request = ["hmd_agro.utils.after_request"]

# Job Events
# ----------
# before_job = ["hmd_agro.utils.before_job"]
# after_job = ["hmd_agro.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"hmd_agro.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

