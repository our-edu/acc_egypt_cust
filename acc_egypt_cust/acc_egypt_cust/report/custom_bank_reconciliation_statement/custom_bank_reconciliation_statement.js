// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt
// Modified: Custom Bank Reconciliation Statement — added From Date / To Date filters

frappe.query_reports["Custom Bank Reconciliation Statement"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "account",
			label: __("Bank Account"),
			fieldtype: "Link",
			options: "Account",
			default: frappe.defaults.get_user_default("Company")
				? locals[":Company"][frappe.defaults.get_user_default("Company")]["default_bank_account"]
				: "",
			reqd: 1,
			get_query: function () {
				var company = frappe.query_report.get_filter_value("company");
				return {
					query: "erpnext.controllers.queries.get_account_list",
					filters: [
						["Account", "account_type", "in", "Bank, Cash"],
						["Account", "is_group", "=", 0],
						["Account", "disabled", "=", 0],
						["Account", "company", "=", company],
					],
				};
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "include_pos_transactions",
			label: __("Include POS Transactions"),
			fieldtype: "Check",
		},
	],
	formatter: function (value, row, column, data, default_formatter, filter) {
		if (column.fieldname == "payment_entry" && value == __("Cheques and Deposits incorrectly cleared")) {
			column.link_onclick =
				"frappe.query_reports['Custom Bank Reconciliation Statement'].open_utility_report()";
		}
		return default_formatter(value, row, column, data);
	},
	open_utility_report: function () {
		frappe.route_options = {
			company: frappe.query_report.get_filter_value("company"),
			account: frappe.query_report.get_filter_value("account"),
			report_date: frappe.query_report.get_filter_value("to_date"),
		};
		frappe.open_in_new_tab = true;
		frappe.set_route("query-report", "Cheques and Deposits Incorrectly cleared");
	},
};
