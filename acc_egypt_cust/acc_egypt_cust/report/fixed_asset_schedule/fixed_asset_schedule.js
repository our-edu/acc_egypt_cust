// Copyright (c) 2026, Custom
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Fixed Asset Schedule"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today()),
			on_change: (query_report) => {
				const fiscal_year = query_report.get_values().fiscal_year;
				if (!fiscal_year) return;
				frappe.model.with_doc("Fiscal Year", fiscal_year, () => {
					const fy = frappe.model.get_doc("Fiscal Year", fiscal_year);
					frappe.query_report.set_filter_value({
						from_date: fy.year_start_date,
						to_date: fy.year_end_date,
					});
				});
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: (erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true) || [])[1],
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: (erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true) || [])[2],
			reqd: 1,
		},
		{
			fieldname: "asset",
			label: __("Asset"),
			fieldtype: "Link",
			options: "Asset",
			get_query: () => ({
				filters: { company: frappe.query_report.get_filter_value("company"), docstatus: 1 },
			}),
		},
		{
			fieldname: "asset_category",
			label: __("Asset Category"),
			fieldtype: "Link",
			options: "Asset Category",
		},
		{
			fieldname: "location",
			label: __("Location"),
			fieldtype: "Link",
			options: "Location",
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "Link",
			options: "Cost Center",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: [
				"",
				"Submitted",
				"Partially Depreciated",
				"Fully Depreciated",
				"Sold",
				"Scrapped",
				"In Maintenance",
				"Out of Order",
				"Issue",
				"Receipt",
				"Capitalized",
				"Work In Progress",
			],
		},
		{
			fieldname: "finance_book",
			label: __("Finance Book"),
			fieldtype: "Link",
			options: "Finance Book",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		if (data && data.is_total_row) {
			if (["asset_id", "asset_name"].includes(column.fieldname)) {
				return `<b>${frappe.utils.escape_html(data[column.fieldname] || "")}</b>`;
			}
			return `<b>${default_formatter(value, row, column, data)}</b>`;
		}
		return default_formatter(value, row, column, data);
	},
};
