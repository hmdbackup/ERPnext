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
	"Aliment", "Ration", "Composition Ration"
]

fixtures = [
	{"dt": "Workspace", "filters": [["module", "=", "HMD AGRO"]]},
	{"dt": "Property Setter", "filters": [["doc_type", "in", HMD_DOCTYPES]]},
	{"dt": "Custom Field", "filters": [["dt", "in", HMD_DOCTYPES]]},
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
# app_include_css = "/assets/hmd_agro/css/hmd_agro.css"
app_include_js = "/assets/hmd_agro/js/hmd_agro.js"

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
# doctype_js = {"doctype" : "public/js/doctype.js"}
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
        "hmd_agro.hmd_agro.utils.snapshot.freeze_yesterday"
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

