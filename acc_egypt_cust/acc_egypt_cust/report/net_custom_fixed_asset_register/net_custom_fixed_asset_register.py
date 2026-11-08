# Copyright (c) 2026, Custom
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.assets.report.fixed_asset_register import fixed_asset_register as base

# Moved from their standard position to the end of the report
TRAILING_COLUMNS = ("cost_center", "department")

# Standard columns removed from this report
HIDDEN_COLUMNS = ("asset_value",)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	group_by = filters.get("group_by") in ("Asset Category", "Location")

	columns = get_columns(filters, group_by)
	data = base.get_data(filters)
	finance_book = get_finance_book(filters)

	if group_by:
		set_group_net_value(data, filters, finance_book)
	else:
		net_value_map = get_net_value_map([row["asset_id"] for row in data], finance_book)
		for row in data:
			row["net_value"] = net_value_map.get(row["asset_id"], 0.0)

		set_custodian(data)

	chart = base.prepare_chart_data(data, filters) if not group_by else {}

	# Strip hidden values from the rows so they are not sent to the client
	for row in data:
		for fieldname in HIDDEN_COLUMNS:
			row.pop(fieldname, None)

	return columns, data, None, chart


def get_finance_book(filters):
	# Same finance book resolution as the standard report
	company_fb = frappe.get_cached_value("Company", filters.company, "default_finance_book")
	if filters.include_default_book_assets and company_fb:
		return company_fb
	return filters.finance_book or None


def get_net_value_map(asset_ids, finance_book):
	"""Net value as shown on the Asset form (Value After Depreciation), current to date."""
	if not asset_ids:
		return {}

	assets = frappe.get_all(
		"Asset",
		filters={"name": ["in", asset_ids]},
		fields=["name", "calculate_depreciation", "value_after_depreciation"],
	)
	finance_books = frappe.get_all(
		"Asset Finance Book",
		filters={"parent": ["in", asset_ids], "parenttype": "Asset"},
		fields=["parent", "finance_book", "value_after_depreciation"],
		order_by="parent, idx",
	)

	rows_by_asset = {}
	for fb in finance_books:
		rows_by_asset.setdefault(fb.parent, []).append(fb)

	net_value_map = {}
	for asset in assets:
		rows = rows_by_asset.get(asset.name)
		if not asset.calculate_depreciation or not rows:
			net_value_map[asset.name] = flt(asset.value_after_depreciation)
			continue

		# Matching finance book, else the blank (default) one, else the first row
		row = (
			next((r for r in rows if finance_book and r.finance_book == finance_book), None)
			or next((r for r in rows if not r.finance_book), None)
			or rows[0]
		)
		net_value_map[asset.name] = flt(row.value_after_depreciation)

	return net_value_map


def set_group_net_value(data, filters, finance_book):
	group_field = frappe.scrub(filters.get("group_by"))
	assets_linked_to_fb = base.get_assets_linked_to_fb(filters)
	assets = frappe.get_all(
		"Asset",
		filters=base.get_conditions(filters),
		fields=["name", "calculate_depreciation", group_field],
	)
	# Same asset selection as the standard grouped data
	assets = [
		a
		for a in assets
		if not (assets_linked_to_fb and a.calculate_depreciation and a.name not in assets_linked_to_fb)
	]
	net_value_map = get_net_value_map([a.name for a in assets], finance_book)

	group_totals = {}
	for a in assets:
		key = a.get(group_field)
		group_totals[key] = group_totals.get(key, 0.0) + net_value_map.get(a.name, 0.0)

	for row in data:
		row["net_value"] = group_totals.get(row.get(group_field), 0.0)


def set_custodian(data):
	asset_ids = [row["asset_id"] for row in data]
	if not asset_ids:
		return

	custodian_map = dict(
		frappe.get_all(
			"Asset", filters={"name": ["in", asset_ids]}, fields=["name", "custodian"], as_list=True
		)
	)
	employees = list({e for e in custodian_map.values() if e})
	employee_name_map = (
		dict(
			frappe.get_all(
				"Employee", filters={"name": ["in", employees]}, fields=["name", "employee_name"], as_list=True
			)
		)
		if employees
		else {}
	)

	for row in data:
		custodian = custodian_map.get(row["asset_id"])
		row["custodian"] = custodian
		row["custodian_name"] = employee_name_map.get(custodian)


def get_columns(filters, group_by):
	columns = [c for c in base.get_columns(filters) if c["fieldname"] not in HIDDEN_COLUMNS]

	net_value_column = {
		"label": _("Net Value"),
		"fieldname": "net_value",
		"fieldtype": "Currency",
		"options": "Company:company:default_currency",
		"width": 120,
	}
	insert_after(columns, "depreciated_amount", [net_value_column])

	if group_by:
		return columns

	custodian_columns = [
		{
			"label": _("Custodian"),
			"fieldtype": "Link",
			"fieldname": "custodian",
			"options": "Employee",
			"width": 100,
		},
		{"label": _("Custodian Name"), "fieldtype": "Data", "fieldname": "custodian_name", "width": 140},
	]
	insert_after(columns, "location", custodian_columns)

	trailing = [c for c in columns if c["fieldname"] in TRAILING_COLUMNS]
	columns = [c for c in columns if c["fieldname"] not in TRAILING_COLUMNS]

	return columns + trailing


def insert_after(columns, fieldname, new_columns):
	idx = next(i for i, c in enumerate(columns) if c["fieldname"] == fieldname)
	columns[idx + 1 : idx + 1] = new_columns
