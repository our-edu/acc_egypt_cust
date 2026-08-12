app_name = "acc_egypt_cust"
app_title = "Acc Egypt Cust"
app_publisher = "our-edu"
app_description = "Accounting Egypt Customizations"
app_email = "ezzat.azab@our-edu.net"
app_license = "mit"

# Fixtures
# --------
fixtures = [
    {
        "dt": "Print Format",
        "filters": [
            ["module", "in", [
                "Acc Egypt Cust",
            ]]
        ]
    },
    {
        "dt": "Custom Field",
        "filters": [
            ["module", "in", [
                "Acc Egypt Cust",
            ]]
        ]
    },
    {
        "dt": "Property Setter",
        "filters": [
            ["module", "in", [
                "Acc Egypt Cust",
            ]]
        ]
    },
    {
        "dt": "Workspace",
        "filters": [
            ["module", "in", [
                "Acc Egypt Cust",
            ]]
        ]
    },
    {
        "dt": "Workspace Sidebar",
        "filters": [
            ["module", "in", [
                "Acc Egypt Cust",
            ]]
        ]
    },
    {
        "dt": "Number Card",
        "filters": [
            ["Number Card", "is_standard", "=", 0],
            ["Number Card", "document_type", "in", ["Journal Entry"]]
        ]
    }


]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/acc_egypt_cust/css/acc_egypt_cust.css"
app_include_js = [
    "/assets/acc_egypt_cust/js/trial_balance.js",
    "/assets/acc_egypt_cust/js/gl_ledger_custom.js",
    "/assets/acc_egypt_cust/js/bank_reconciliation_report.js",
    "/assets/acc_egypt_cust/js/ledger_prompt.js",
    # Prevents the sidebar from auto-switching when navigating to DocTypes
    # that belong to other modules (e.g. Stock, Selling).
    # See: acc_egypt_cust/public/js/workspace_sidebar_fix.js
    "/assets/acc_egypt_cust/js/workspace_sidebar_fix.js",
]

# include js in doctype views
doctype_js = {
    "Journal Entry": "public/js/journal_entry_upload.js",
    "Bank Reconciliation Tool": "public/js/bank_transaction_import.js",
    "Asset": "public/js/asset.js",
    "Asset Movement": "public/js/asset_movement.js",
}
doctype_tree_js = {
    # Overrides the "View Ledger" toolbar button in Chart of Accounts
    # so it opens Custom General Ledger instead of General Ledger.
    "Account": "public/js/account_tree.js",
}
doctype_list_js = {
    "Journal Entry": "public/js/journal_entry.js"
}

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

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
    "Journal Entry": "acc_egypt_cust.overrides.journal_entry_class.CustomJournalEntry",
    "Asset Movement": "acc_egypt_cust.overrides.asset_movement_class.CustomAssetMovement",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "GL Entry": {
        "validate": "acc_egypt_cust.overrides.gl_entry.validate",
    },
    # Bank Reconciliation Row-Level Matching: Allow same JE with different rows
    "Bank Transaction": {
        "before_validate": "acc_egypt_cust.overrides.bank_reconciliation.validate_je_row_duplicates",
    },
    "Journal Entry": {
        "before_validate": "acc_egypt_cust.overrides.journal_entry.sync_custom_party_to_party",
        "after_insert": "acc_egypt_cust.overrides.journal_entry.set_title_to_name",
        "on_update": [
            "acc_egypt_cust.overrides.journal_entry.set_title_to_name",
            "acc_egypt_cust.overrides.journal_entry.auto_submit_depreciation_entry",
        ],
    },
    "Asset": {
        "validate": "acc_egypt_cust.overrides.asset.set_salvage_value",
        "before_submit": "acc_egypt_cust.overrides.asset.set_composite_asset_salvage_value_on_submit",
    },
}

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

# Bank Reconciliation Row-Level Matching Overrides
override_whitelisted_methods = {
    # Replace get_linked_payments to handle JE rows separately
    "erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.get_linked_payments":
        "acc_egypt_cust.overrides.bank_reconciliation.custom_get_linked_payments",

    # Replace reconcile_vouchers to store row identifiers
    "erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.reconcile_vouchers":
        "acc_egypt_cust.overrides.bank_reconciliation.custom_reconcile_vouchers",

    # Replace auto_reconcile_vouchers to use our custom matching and reconciliation
    "erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.auto_reconcile_vouchers":
        "acc_egypt_cust.overrides.bank_reconciliation.custom_auto_reconcile_vouchers",

    # Inject Purchase Invoice title into GL report remarks for supplier entries
    "frappe.desk.query_report.run":
        "acc_egypt_cust.overrides.general_ledger_report.run",
}

# Bank Reconciliation Statement Report - Add Bank Transaction entries
get_entries_for_bank_reconciliation_statement = [
    "acc_egypt_cust.overrides.bank_reconciliation.get_bank_transaction_entries_for_reconciliation_statement"
]

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

