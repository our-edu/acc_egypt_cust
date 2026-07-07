# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
# Custom version: also includes GL entries where custom_party_type = 'Employee'


import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import cint, flt

from erpnext.accounts.report.general_ledger.general_ledger import get_accounts_with_children
from erpnext.accounts.report.trial_balance.trial_balance import validate_filters


def execute(filters=None):
	validate_filters(filters)

	show_party_name = is_party_name_visible(filters)

	columns = get_columns(filters, show_party_name)
	data = get_data(filters, show_party_name)

	return columns, data


def get_data(filters, show_party_name):
	if filters.get("party_type") in ("Customer", "Supplier", "Employee", "Member"):
		party_name_field = "{}_name".format(frappe.scrub(filters.get("party_type")))
	elif filters.get("party_type") == "Shareholder":
		party_name_field = "title"
	else:
		party_name_field = "name"

	party_filters = {"name": filters.get("party")} if filters.get("party") else {}
	parties = frappe.get_all(
		filters.get("party_type"),
		fields=["name", party_name_field],
		filters=party_filters,
		order_by="name",
	)

	# Also include employees referenced via custom_party/custom_party_type on JE account rows
	existing_party_names = {p.name for p in parties}
	if filters.get("party_type") == "Employee":
		JEA = frappe.qb.DocType("Journal Entry Account")
		JE_doc = frappe.qb.DocType("Journal Entry")
		emp_query = (
			frappe.qb.from_(JEA)
			.join(JE_doc)
			.on(JEA.parent == JE_doc.name)
			.select(JEA.custom_party.as_("party"))
			.distinct()
			.where(
				(JE_doc.company == filters.company)
				& (JEA.custom_party_type == "Employee")
				& (JEA.custom_party.isnotnull())
				& (JEA.custom_party != "")
			)
		)
		if filters.get("party"):
			emp_query = emp_query.where(JEA.custom_party == filters.get("party"))

		for ep in emp_query.run(as_dict=True):
			if ep.party not in existing_party_names:
				emp_name = frappe.db.get_value("Employee", ep.party, "employee_name") or ep.party
				parties.append(frappe._dict({"name": ep.party, party_name_field: emp_name}))
				existing_party_names.add(ep.party)

	parties = sorted(parties, key=lambda p: p.name)

	account_filter = []
	if filters.get("account"):
		account_filter = get_accounts_with_children(filters.get("account"))

	company_currency = frappe.get_cached_value("Company", filters.company, "default_currency")
	opening_balances = get_opening_balances(filters, account_filter)
	balances_within_period = get_balances_within_period(filters, account_filter)

	data = []
	total_row = frappe._dict(
		{
			"opening_debit": 0,
			"opening_credit": 0,
			"debit": 0,
			"credit": 0,
			"closing_debit": 0,
			"closing_credit": 0,
		}
	)
	for party in parties:
		row = {"party": party.name}
		if show_party_name:
			row["party_name"] = party.get(party_name_field)

		# opening
		opening_debit, opening_credit = opening_balances.get(party.name, [0, 0])
		row.update({"opening_debit": opening_debit, "opening_credit": opening_credit})

		# within period
		debit, credit = balances_within_period.get(party.name, [0, 0])
		row.update({"debit": debit, "credit": credit})

		# closing
		closing_debit, closing_credit = toggle_debit_credit(opening_debit + debit, opening_credit + credit)
		row.update({"closing_debit": closing_debit, "closing_credit": closing_credit})

		row.update({"currency": company_currency})

		has_value = False
		if opening_debit or opening_credit or debit or credit or closing_debit or closing_credit:
			has_value = True
		# Exclude zero balance parties if filter is set
		if filters.get("exclude_zero_balance_parties") and not closing_debit and not closing_credit:
			continue

		if cint(filters.show_zero_values) or has_value:
			data.append(row)
			# totals
			for col in total_row:
				total_row[col] += row.get(col)

	total_row.update({"party": "'" + _("Totals") + "'", "currency": company_currency})
	data.append(total_row)

	return data


def get_opening_balances(filters, account_filter=None):
	GL_Entry = frappe.qb.DocType("GL Entry")
	JEA = frappe.qb.DocType("Journal Entry Account")

	# Query 1: standard GL entries where party_type matches the filter
	q1 = (
		frappe.qb.from_(GL_Entry)
		.select(
			GL_Entry.party,
			Sum(GL_Entry.debit).as_("opening_debit"),
			Sum(GL_Entry.credit).as_("opening_credit"),
		)
		.where(
			(GL_Entry.company == filters.company)
			& (GL_Entry.is_cancelled == 0)
			& (GL_Entry.party_type == filters.party_type)
			& (GL_Entry.party.isnotnull())
			& (GL_Entry.party != "")
			& (
				(GL_Entry.posting_date < filters.from_date)
				| ((GL_Entry.is_opening == "Yes") & (GL_Entry.posting_date <= filters.to_date))
			)
		)
		.groupby(GL_Entry.party)
	)
	if account_filter:
		q1 = q1.where(GL_Entry.account.isin(account_filter))
	gle1 = q1.run(as_dict=True)

	# Query 2 (Employee only): GL entries whose JEA row carries custom_party_type='Employee'.
	# GL.party is null for these (non-AR/AP accounts), so we join GL to JEA on
	# voucher_no + account and group by JEA.custom_party instead.
	gle2 = []
	if filters.get("party_type") == "Employee":
		q2 = (
			frappe.qb.from_(GL_Entry)
			.join(JEA)
			.on(
				(JEA.parent == GL_Entry.voucher_no)
				& (JEA.account == GL_Entry.account)
			)
			.select(
				JEA.custom_party.as_("party"),
				Sum(GL_Entry.debit).as_("opening_debit"),
				Sum(GL_Entry.credit).as_("opening_credit"),
			)
			.where(
				(GL_Entry.company == filters.company)
				& (GL_Entry.is_cancelled == 0)
				& (GL_Entry.voucher_type == "Journal Entry")
				& (JEA.custom_party_type == "Employee")
				& (JEA.custom_party.isnotnull())
				& (JEA.custom_party != "")
				& (
					(GL_Entry.posting_date < filters.from_date)
					| ((GL_Entry.is_opening == "Yes") & (GL_Entry.posting_date <= filters.to_date))
				)
			)
			.groupby(JEA.custom_party)
		)
		if account_filter:
			q2 = q2.where(GL_Entry.account.isin(account_filter))
		gle2 = q2.run(as_dict=True)

	# Accumulate raw sums before toggling so both sources are merged correctly
	raw = {}
	for d in gle1 + gle2:
		if d.party not in raw:
			raw[d.party] = [0.0, 0.0]
		raw[d.party][0] += flt(d.opening_debit)
		raw[d.party][1] += flt(d.opening_credit)

	opening = frappe._dict()
	for party, (debit, credit) in raw.items():
		opening[party] = toggle_debit_credit(debit, credit)

	return opening


def get_balances_within_period(filters, account_filter=None):
	GL_Entry = frappe.qb.DocType("GL Entry")
	JEA = frappe.qb.DocType("Journal Entry Account")

	# Query 1: standard GL entries where party_type matches the filter
	q1 = (
		frappe.qb.from_(GL_Entry)
		.select(
			GL_Entry.party,
			Sum(GL_Entry.debit).as_("debit"),
			Sum(GL_Entry.credit).as_("credit"),
		)
		.where(
			(GL_Entry.company == filters.company)
			& (GL_Entry.is_cancelled == 0)
			& (GL_Entry.party_type == filters.party_type)
			& (GL_Entry.party.isnotnull())
			& (GL_Entry.party != "")
			& (GL_Entry.posting_date >= filters.from_date)
			& (GL_Entry.posting_date <= filters.to_date)
			& (GL_Entry.is_opening == "No")
		)
		.groupby(GL_Entry.party)
	)
	if account_filter:
		q1 = q1.where(GL_Entry.account.isin(account_filter))
	gle1 = q1.run(as_dict=True)

	# Query 2 (Employee only): GL entries whose JEA row carries custom_party_type='Employee'.
	# GL.party is null for these (non-AR/AP accounts), so we join GL to JEA on
	# voucher_no + account and group by JEA.custom_party instead.
	gle2 = []
	if filters.get("party_type") == "Employee":
		q2 = (
			frappe.qb.from_(GL_Entry)
			.join(JEA)
			.on(
				(JEA.parent == GL_Entry.voucher_no)
				& (JEA.account == GL_Entry.account)
			)
			.select(
				JEA.custom_party.as_("party"),
				Sum(GL_Entry.debit).as_("debit"),
				Sum(GL_Entry.credit).as_("credit"),
			)
			.where(
				(GL_Entry.company == filters.company)
				& (GL_Entry.is_cancelled == 0)
				& (GL_Entry.voucher_type == "Journal Entry")
				& (JEA.custom_party_type == "Employee")
				& (JEA.custom_party.isnotnull())
				& (JEA.custom_party != "")
				& (GL_Entry.posting_date >= filters.from_date)
				& (GL_Entry.posting_date <= filters.to_date)
				& (GL_Entry.is_opening == "No")
			)
			.groupby(JEA.custom_party)
		)
		if account_filter:
			q2 = q2.where(GL_Entry.account.isin(account_filter))
		gle2 = q2.run(as_dict=True)

	# Accumulate raw sums from both sources
	raw = {}
	for d in gle1 + gle2:
		if d.party not in raw:
			raw[d.party] = [0.0, 0.0]
		raw[d.party][0] += flt(d.debit)
		raw[d.party][1] += flt(d.credit)

	return frappe._dict(raw)


def toggle_debit_credit(debit, credit):
	if flt(debit) > flt(credit):
		debit = flt(debit) - flt(credit)
		credit = 0.0
	else:
		credit = flt(credit) - flt(debit)
		debit = 0.0

	return debit, credit


def get_columns(filters, show_party_name):
	columns = [
		{
			"fieldname": "party",
			"label": _(filters.party_type),
			"fieldtype": "Link",
			"options": filters.party_type,
			"width": 200,
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
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
	]

	if show_party_name:
		columns.insert(
			1,
			{
				"fieldname": "party_name",
				"label": _(filters.party_type) + " Name",
				"fieldtype": "Data",
				"width": 200,
			},
		)

	return columns


def is_party_name_visible(filters):
	show_party_name = False

	if filters.get("party_type") in ["Customer", "Supplier"]:
		if filters.get("party_type") == "Customer":
			party_naming_by = frappe.get_single_value("Selling Settings", "cust_master_name")
		else:
			party_naming_by = frappe.db.get_single_value("Buying Settings", "supp_master_name")

		if party_naming_by == "Naming Series":
			show_party_name = True
	else:
		show_party_name = True

	return show_party_name
