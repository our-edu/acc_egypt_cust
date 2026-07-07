app_name = "acc_egypt_cust"
app_title = "Acc Egypt Cust"
app_publisher = "our-edu"
app_description = "Accounting Egypt Customizations"
app_email = "ezzat.azab@our-edu.net"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "acc_egypt_cust",
# 		"logo": "/assets/acc_egypt_cust/logo.png",
# 		"title": "Acc Egypt Cust",
# 		"route": "/acc_egypt_cust",
# 		"has_permission": "acc_egypt_cust.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/acc_egypt_cust/css/acc_egypt_cust.css"
# app_include_js = "/assets/acc_egypt_cust/js/acc_egypt_cust.js"

# include js, css files in header of web template
# web_include_css = "/assets/acc_egypt_cust/css/acc_egypt_cust.css"
# web_include_js = "/assets/acc_egypt_cust/js/acc_egypt_cust.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "acc_egypt_cust/public/scss/website"

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
# app_include_icons = "acc_egypt_cust/public/icons.svg"

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

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "acc_egypt_cust.utils.jinja_methods",
# 	"filters": "acc_egypt_cust.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "acc_egypt_cust.install.before_install"
# after_install = "acc_egypt_cust.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "acc_egypt_cust.uninstall.before_uninstall"
# after_uninstall = "acc_egypt_cust.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "acc_egypt_cust.utils.before_app_install"
# after_app_install = "acc_egypt_cust.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "acc_egypt_cust.utils.before_app_uninstall"
# after_app_uninstall = "acc_egypt_cust.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "acc_egypt_cust.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "acc_egypt_cust.notifications.get_notification_config"

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

# scheduler_events = {
# 	"all": [
# 		"acc_egypt_cust.tasks.all"
# 	],
# 	"daily": [
# 		"acc_egypt_cust.tasks.daily"
# 	],
# 	"hourly": [
# 		"acc_egypt_cust.tasks.hourly"
# 	],
# 	"weekly": [
# 		"acc_egypt_cust.tasks.weekly"
# 	],
# 	"monthly": [
# 		"acc_egypt_cust.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "acc_egypt_cust.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "acc_egypt_cust.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "acc_egypt_cust.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "acc_egypt_cust.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["acc_egypt_cust.utils.before_request"]
# after_request = ["acc_egypt_cust.utils.after_request"]

# Job Events
# ----------
# before_job = ["acc_egypt_cust.utils.before_job"]
# after_job = ["acc_egypt_cust.utils.after_job"]

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
# 	"acc_egypt_cust.auth.validate"
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

