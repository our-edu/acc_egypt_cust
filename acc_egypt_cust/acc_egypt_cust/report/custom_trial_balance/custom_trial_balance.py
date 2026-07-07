# Copyright (c) 2026, Custom
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import cstr, flt

import erpnext
from erpnext.accounts.report.financial_statements import (
	filter_accounts,
	filter_out_zero_value_rows,
	set_gl_entries_by_account,
)
from erpnext.accounts.report.trial_balance.trial_balance import (
	accumulate_values_into_parents,
	calculate_total_row,
	calculate_values,
	get_opening_balances,
	hide_group_accounts,
	prepare_opening_closing,
	validate_filters,
	value_fields,
)
from erpnext.accounts.utils import get_zero_cutoff


def execute(filters=None):
	validate_filters(filters)
	data = get_data(filters)
	columns = get_columns()
	return columns, data


def get_data(filters):
	accounts = frappe.db.sql(
		"""select name, account_number, parent_account, account_name, root_type, report_type, is_group, lft, rgt
		from `tabAccount` where company=%s order by lft""",
		filters.company,
		as_dict=True,
	)
	company_currency = filters.presentation_currency or erpnext.get_company_currency(filters.company)

	ignore_is_opening = frappe.get_single_value("Accounts Settings", "ignore_is_opening_check_for_reporting")

	if not accounts:
		return None

	accounts, accounts_by_name, parent_children_map = filter_accounts(accounts)

	levels = _compute_account_levels(accounts_by_name, parent_children_map)

	gl_entries_by_account = {}

	opening_balances = get_opening_balances(filters, ignore_is_opening)

	set_gl_entries_by_account(
		filters.company,
		filters.from_date,
		filters.to_date,
		filters,
		gl_entries_by_account,
		root_lft=None,
		root_rgt=None,
		ignore_closing_entries=not flt(filters.with_period_closing_entry_for_current_period),
		ignore_opening_entries=True,
		group_by_account=True,
	)

	calculate_values(
		accounts,
		gl_entries_by_account,
		opening_balances,
		filters.get("show_net_values"),
		ignore_is_opening=ignore_is_opening,
	)
	accumulate_values_into_parents(accounts, accounts_by_name)

	data = _prepare_data(accounts, filters, parent_children_map, company_currency, levels)
	data = filter_out_zero_value_rows(
		data, parent_children_map, show_zero_values=filters.get("show_zero_values")
	)

	return data


def _compute_account_levels(accounts_by_name, parent_children_map):
	"""
	Compute bottom-up account levels:
	  - Leaf account (no children)  -> level 0
	  - Parent of leaves            -> level 1
	  - Grandparent                 -> level 2
	  - ...
	"""
	levels = {}

	def _get_level(account_name):
		if account_name in levels:
			return levels[account_name]
		children = parent_children_map.get(account_name, [])
		if not children:
			levels[account_name] = 0
		else:
			levels[account_name] = max(_get_level(c.name) for c in children) + 1
		return levels[account_name]

	for acc_name in accounts_by_name:
		_get_level(acc_name)

	return levels


def _prepare_data(accounts, filters, parent_children_map, company_currency, levels):
	data = []

	for d in accounts:
		if parent_children_map.get(d.account) and filters.get("show_net_values"):
			prepare_opening_closing(d)

		has_value = False
		row = {
			"account": d.name,
			"parent_account": d.parent_account,
			"indent": d.indent,
			"from_date": filters.from_date,
			"to_date": filters.to_date,
			"currency": company_currency,
			"is_group_account": d.is_group,
			"acc_name": d.account_name,
			"acc_number": d.account_number,
			"account_name": (
				f"{d.account_number} - {d.account_name}" if d.account_number else d.account_name
			),
			"account_level": levels.get(d.name, 0),
		}

		for key in value_fields:
			row[key] = flt(d.get(key, 0.0))

			if abs(row[key]) >= get_zero_cutoff(company_currency):
				has_value = True

		row["has_value"] = has_value
		data.append(row)

	if not filters.get("show_group_accounts"):
		data = hide_group_accounts(data)

	total_row = calculate_total_row(
		data, company_currency, show_group_accounts=filters.get("show_group_accounts")
	)

	data.extend([{}, total_row])

	return data


def get_columns():
	return [
		{
			"fieldname": "account",
			"label": _("Account"),
			"fieldtype": "Link",
			"options": "Account",
			"width": 300,
		},
		{
			"fieldname": "acc_name",
			"label": _("Account Name"),
			"fieldtype": "Data",
			"hidden": 1,
			"width": 250,
		},
		{
			"fieldname": "acc_number",
			"label": _("Account Number"),
			"fieldtype": "Data",
			"hidden": 1,
			"width": 120,
		},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
		{
			"fieldname": "account_level",
			"label": _("Level"),
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"fieldname": "opening_debit",
			"label": _("Opening (Dr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "opening_credit",
			"label": _("Opening (Cr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "debit",
			"label": _("Debit"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "credit",
			"label": _("Credit"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "closing_debit",
			"label": _("Closing (Dr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "closing_credit",
			"label": _("Closing (Cr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
	]


def get_xlsx_styles(metadata):
	from frappe.utils.xlsxutils import XLSXStyleBuilder

	builder = XLSXStyleBuilder(metadata)

	for row_idx, row in metadata.row_map.items():
		if isinstance(row, dict) and row.get("is_group_account"):
			builder.style_row(row_idx, builder.bold_style_id)

	return builder.result
