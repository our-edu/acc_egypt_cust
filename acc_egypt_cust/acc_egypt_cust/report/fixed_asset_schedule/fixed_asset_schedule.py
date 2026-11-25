# Copyright (c) 2026, Custom
# License: GNU General Public License v3. See license.txt

"""Fixed asset register for a period: cost roll-forward and depreciation roll-forward per asset.

Cost at a date = Net Purchase Amount (+ additions) - depreciation booked up to that date:
               Closing Cost = Opening Cost + Additions - Disposals - Period Depreciation
Depreciation:  Opening Accumulated + Period Depreciation - Eliminated on Disposal = Closing Accumulated
Net Book Value = Closing Cost
"""

import frappe
from frappe import _
from frappe.query_builder.functions import IfNull
from frappe.utils import add_days, cint, flt, getdate

# Same grouping as the standard Fixed Asset Register status filter
DISPOSED_STATUSES = ("Sold", "Scrapped", "Capitalized")

CURRENCY = "Company:company:default_currency"

AMOUNT_FIELDS = (
	"opening_cost",
	"additions",
	"disposals",
	"closing_cost",
	"opening_accumulated_depreciation",
	"monthly_depreciation",
	"period_depreciation",
	"depreciation_on_disposals",
	"closing_accumulated_depreciation",
	"net_book_value",
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	data = get_data(filters)
	if data:
		data.append(get_total_row(data))

	return get_columns(filters), data


def validate_filters(filters):
	if not filters.company:
		frappe.throw(_("Please select a Company"))
	if not (filters.from_date and filters.to_date):
		frappe.throw(_("Please set From Date and To Date"))

	filters.from_date = getdate(filters.from_date)
	filters.to_date = getdate(filters.to_date)
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be after To Date"))


def get_data(filters):
	assets = get_assets(filters)
	if not assets:
		return []

	asset_ids = [a.name for a in assets]
	precision = frappe.get_precision("Asset", "value_after_depreciation") or 2

	finance_book_map = get_finance_book_map(asset_ids, filters.finance_book)
	schedule_map = get_schedule_rows(finance_book_map, filters)
	repair_map = get_capitalized_repairs(asset_ids)
	adjustment_map = get_value_adjustments(asset_ids, filters.finance_book)
	account_map = get_category_accounts(filters.company)
	supplier_map = get_reference_suppliers(assets)

	data = []
	for asset in assets:
		fb = finance_book_map.get(asset.name) if asset.calculate_depreciation else None
		row = get_asset_row(asset, fb, account_map, supplier_map)

		set_cost(row, asset, repair_map.get(asset.name, []), adjustment_map.get(asset.name, []), filters)
		set_depreciation(row, asset, fb, schedule_map.get(asset.name, []), filters)
		deduct_prior_depreciation(row, asset, filters)

		row["net_book_value"] = row["closing_cost"]
		for field in AMOUNT_FIELDS:
			row[field] = flt(row[field], precision)

		data.append(row)

	return data


def get_assets(filters):
	asset = frappe.qb.DocType("Asset")
	query = (
		frappe.qb.from_(asset)
		.select(
			asset.name,
			asset.asset_name,
			asset.asset_category,
			asset.status,
			asset.purchase_date,
			asset.available_for_use_date,
			asset.disposal_date,
			asset.purchase_invoice,
			asset.purchase_receipt,
			asset.supplier,
			asset.location,
			asset.department,
			asset.calculate_depreciation,
			asset.net_purchase_amount,
			asset.additional_asset_cost,
			asset.opening_accumulated_depreciation,
		)
		.where(asset.docstatus == 1)
		.where(asset.company == filters.company)
		# Not yet bought at the end of the period
		.where(asset.purchase_date <= filters.to_date)
		# Already gone before the period started
		.where(
			asset.status.notin(DISPOSED_STATUSES)
			| asset.disposal_date.isnull()
			| (asset.disposal_date >= filters.from_date)
		)
		.orderby(asset.asset_category)
		.orderby(asset.name)
	)

	for field in ("asset_category", "location", "department", "cost_center"):
		if filters.get(field):
			query = query.where(asset[field] == filters.get(field))
	if filters.asset:
		query = query.where(asset.name == filters.asset)
	if filters.status:
		query = query.where(asset.status == filters.status)

	return query.run(as_dict=True)


def get_asset_row(asset, fb, account_map, supplier_map):
	accounts = account_map.get(asset.asset_category, {})
	reference_doctype, reference_name = None, None
	if asset.purchase_invoice:
		reference_doctype, reference_name = "Purchase Invoice", asset.purchase_invoice
	elif asset.purchase_receipt:
		reference_doctype, reference_name = "Purchase Receipt", asset.purchase_receipt

	total_months = cint(fb.total_number_of_depreciations) * (cint(fb.frequency_of_depreciation) or 1) if fb else 0

	if not fb:
		method, rate = _("Not Depreciated"), 0.0
	elif fb.depreciation_method in ("Written Down Value", "Double Declining Balance") and flt(
		fb.rate_of_depreciation
	):
		method, rate = fb.depreciation_method, flt(fb.rate_of_depreciation)
	else:
		method, rate = fb.depreciation_method, (1200.0 / total_months if total_months else 0.0)

	return {
		"asset_id": asset.name,
		"fixed_asset_account": accounts.get("fixed_asset_account"),
		"accumulated_depreciation_account": accounts.get("accumulated_depreciation_account"),
		"depreciation_expense_account": accounts.get("depreciation_expense_account"),
		"asset_category": asset.asset_category,
		"asset_name": asset.asset_name,
		"purchase_date": asset.purchase_date,
		"available_for_use_date": asset.available_for_use_date,
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"supplier": asset.supplier or supplier_map.get((reference_doctype, reference_name)),
		"location": asset.location,
		"department": asset.department,
		"depreciation_method": _(method) if method else None,
		"rate_of_depreciation": rate,
		"useful_life_years": flt(total_months / 12, 2) if total_months else None,
		"status": asset.status,
	}


def set_cost(row, asset, repairs, adjustments, filters):
	"""Split the asset's cost into before / within the period, from dated cost movements."""
	movements = [(asset.purchase_date, flt(asset.net_purchase_amount))]

	# Capitalized repairs raise additional_asset_cost on their completion date
	movements += [(getdate(r.completion_date or asset.purchase_date), flt(r.total_repair_cost)) for r in repairs]
	# Any other additional cost (e.g. carried over from an asset split) has no date of its own
	undated_additional = flt(asset.additional_asset_cost) - sum(flt(r.total_repair_cost) for r in repairs)
	if undated_additional:
		movements.append((asset.purchase_date, undated_additional))

	movements += [(getdate(a.date), flt(a.difference_amount)) for a in adjustments]

	opening, additions, disposals = 0.0, 0.0, 0.0
	for date, amount in movements:
		date = getdate(date)
		if date > filters.to_date:
			continue
		if date < filters.from_date:
			opening += amount
		elif amount >= 0:
			additions += amount
		else:
			disposals -= amount

	if is_disposed_in_period(asset, filters):
		disposals = opening + additions

	row["opening_cost"] = opening
	row["additions"] = additions
	row["disposals"] = disposals
	row["closing_cost"] = opening + additions - disposals


def set_depreciation(row, asset, fb, schedule_rows, filters):
	# Only depreciation actually booked (submitted Journal Entry), see get_schedule_rows
	rows = schedule_rows

	before = flt(asset.opening_accumulated_depreciation) + sum(
		flt(r.depreciation_amount) for r in rows if r.schedule_date < filters.from_date
	)
	in_period = [r for r in rows if filters.from_date <= r.schedule_date <= filters.to_date]
	period = sum(flt(r.depreciation_amount) for r in in_period)

	monthly = 0.0
	if in_period and fb:
		monthly = flt(in_period[-1].depreciation_amount) / (cint(fb.frequency_of_depreciation) or 1)

	eliminated = before + period if is_disposed_in_period(asset, filters) else 0.0

	row["opening_accumulated_depreciation"] = before
	row["monthly_depreciation"] = monthly
	row["period_depreciation"] = period
	row["depreciation_on_disposals"] = eliminated
	row["closing_accumulated_depreciation"] = before + period - eliminated


def deduct_prior_depreciation(row, asset, filters):
	"""Show cost at each date net of the depreciation booked up to that date.

	e.g. ACC-ASS-2026-00453: 5,300 - 454.92 = 4,845.08 at 01/01, less the 65.50 of 31/01 = 4,779.58 at 01/02.
	Depreciation before the period comes off the opening cost, or off additions for an asset bought
	within the period (an existing asset entered with opening accumulated depreciation); the period's
	depreciation comes off the closing cost. A disposal removes the book value left at disposal.
	"""
	before = row["opening_accumulated_depreciation"]
	if getdate(asset.purchase_date) < filters.from_date:
		row["opening_cost"] -= before
	else:
		row["additions"] -= before

	if is_disposed_in_period(asset, filters):
		row["disposals"] = row["opening_cost"] + row["additions"] - row["period_depreciation"]
	row["closing_cost"] = row["opening_cost"] + row["additions"] - row["disposals"] - row["period_depreciation"]


def is_disposed_in_period(asset, filters):
	if asset.status not in DISPOSED_STATUSES:
		return False
	# No disposal date recorded: the asset is gone, count it as disposed now
	return not asset.disposal_date or getdate(asset.disposal_date) <= filters.to_date


def get_finance_book_map(asset_ids, finance_book):
	"""One Asset Finance Book row per asset: the filtered book, else the default (blank) one, else the first."""
	rows = frappe.get_all(
		"Asset Finance Book",
		filters={"parent": ["in", asset_ids], "parenttype": "Asset"},
		fields=[
			"parent",
			"finance_book",
			"depreciation_method",
			"rate_of_depreciation",
			"total_number_of_depreciations",
			"frequency_of_depreciation",
		],
		order_by="parent, idx",
	)

	rows_by_asset = {}
	for row in rows:
		rows_by_asset.setdefault(row.parent, []).append(row)

	return {
		asset: (
			next((r for r in asset_rows if finance_book and r.finance_book == finance_book), None)
			or next((r for r in asset_rows if not r.finance_book), None)
			or asset_rows[0]
		)
		for asset, asset_rows in rows_by_asset.items()
	}


def get_schedule_rows(finance_book_map, filters):
	"""Depreciation actually booked up to the end date, per asset, for its selected finance book.

	Rows of each asset's active depreciation schedule whose Journal Entry is submitted, dated by
	the Journal Entry's posting date. Unposted rows and draft / cancelled entries are left out.
	"""
	if not finance_book_map:
		return {}

	ads = frappe.qb.DocType("Asset Depreciation Schedule")
	ds = frappe.qb.DocType("Depreciation Schedule")
	je = frappe.qb.DocType("Journal Entry")

	result = (
		frappe.qb.from_(ads)
		.join(ds)
		.on(ds.parent == ads.name)
		.join(je)
		.on(je.name == ds.journal_entry)
		.select(
			ads.asset,
			IfNull(ads.finance_book, "").as_("finance_book"),
			je.posting_date.as_("schedule_date"),
			ds.depreciation_amount,
			ds.journal_entry,
		)
		.where(ads.docstatus == 1)
		.where(ads.status == "Active")
		.where(ads.asset.isin(list(finance_book_map)))
		.where(je.docstatus == 1)
		.where(je.posting_date <= filters.to_date)
		.orderby(ads.asset)
		.orderby(je.posting_date)
		.orderby(ds.idx)
		.run(as_dict=True)
	)

	schedule_map = {}
	for row in result:
		if row.finance_book == (finance_book_map[row.asset].finance_book or ""):
			row.schedule_date = getdate(row.schedule_date)
			schedule_map.setdefault(row.asset, []).append(row)

	return schedule_map


def get_capitalized_repairs(asset_ids):
	repairs = frappe.get_all(
		"Asset Repair",
		filters={"asset": ["in", asset_ids], "docstatus": 1, "capitalize_repair_cost": 1},
		fields=["asset", "completion_date", "total_repair_cost"],
	)
	repair_map = {}
	for r in repairs:
		repair_map.setdefault(r.asset, []).append(r)
	return repair_map


def get_value_adjustments(asset_ids, finance_book):
	"""Submitted Asset Value Adjustments on the given finance book or on the default (blank) one."""
	ava = frappe.qb.DocType("Asset Value Adjustment")
	result = (
		frappe.qb.from_(ava)
		.select(ava.asset, ava.date, ava.difference_amount)
		.where(ava.docstatus == 1)
		.where(ava.asset.isin(asset_ids))
		.where(IfNull(ava.finance_book, "").isin(list({"", finance_book or ""})))
		.run(as_dict=True)
	)
	adjustment_map = {}
	for row in result:
		adjustment_map.setdefault(row.asset, []).append(row)
	return adjustment_map


def get_category_accounts(company):
	"""Asset Category accounts for the company; depreciation accounts fall back to the company defaults."""
	company_defaults = frappe.get_cached_value(
		"Company", company, ["accumulated_depreciation_account", "depreciation_expense_account"], as_dict=True
	)
	rows = frappe.get_all(
		"Asset Category Account",
		filters={"company_name": company, "parenttype": "Asset Category"},
		fields=["parent", "fixed_asset_account", "accumulated_depreciation_account", "depreciation_expense_account"],
	)
	account_map = {row.parent: row for row in rows}

	categories = frappe.get_all("Asset Category", pluck="name")
	for category in categories:
		accounts = account_map.setdefault(category, frappe._dict())
		for field in ("accumulated_depreciation_account", "depreciation_expense_account"):
			if not accounts.get(field):
				accounts[field] = company_defaults.get(field)

	return account_map


def get_reference_suppliers(assets):
	"""Supplier of the purchase document, for assets without a supplier of their own."""
	supplier_map = {}
	for doctype, field in (("Purchase Invoice", "purchase_invoice"), ("Purchase Receipt", "purchase_receipt")):
		names = list({a[field] for a in assets if a[field] and not a.supplier})
		if not names:
			continue
		for name, supplier in frappe.get_all(
			doctype, filters={"name": ["in", names]}, fields=["name", "supplier"], as_list=True
		):
			supplier_map[(doctype, name)] = supplier
	return supplier_map


def get_total_row(data):
	total = {"asset_id": _("Total"), "asset_name": _("Total Fixed and Intangible Assets"), "is_total_row": 1}
	for field in AMOUNT_FIELDS:
		total[field] = sum(flt(row.get(field)) for row in data)
	return total


def get_columns(filters):
	"""Labels follow the header row of the client's fixed asset register sheet.

	Dates and the year in the labels come from the selected period.
	"""

	def currency(label, fieldname, width=140):
		return {"label": label, "fieldname": fieldname, "fieldtype": "Currency", "options": CURRENCY, "width": width}

	def link(label, fieldname, options, width=160):
		return {"label": label, "fieldname": fieldname, "fieldtype": "Link", "options": options, "width": width}

	def fmt(date):
		return date.strftime("%d/%m/%Y")

	start, end = filters.from_date, filters.to_date
	before_start = add_days(start, -1)
	year = end.year

	return [
		link("كود الأصل", "asset_id", "Asset", 170),
		link("رقم حساب الأصل", "fixed_asset_account", "Account", 200),
		link("حساب مجمع الإهلاك", "accumulated_depreciation_account", "Account", 200),
		link("حساب مصروف الإهلاك", "depreciation_expense_account", "Account", 200),
		link("فئة الأصل", "asset_category", "Asset Category", 180),
		{"label": "اسم الأصل ووصفه التفصيلي", "fieldname": "asset_name", "fieldtype": "Data", "width": 220},
		{"label": "تاريخ الشراء", "fieldname": "purchase_date", "fieldtype": "Date", "width": 110},
		{"label": "تاريخ بدء الإهلاك", "fieldname": "available_for_use_date", "fieldtype": "Date", "width": 110},
		{"label": _("Reference Type"), "fieldname": "reference_doctype", "fieldtype": "Data", "hidden": 1},
		{
			"label": "رقم المستند المرجعي",
			"fieldname": "reference_name",
			"fieldtype": "Dynamic Link",
			"options": "reference_doctype",
			"width": 170,
		},
		link("اسم المورد / المرجع", "supplier", "Supplier", 200),
		link("الموقع / الفرع", "location", "Location", 140),
		link("الإدارة المسؤولة", "department", "Department", 140),
		currency(f"التكلفة في {fmt(start)}", "opening_cost"),
		currency(f"إضافات {year}", "additions", 120),
		currency(f"استبعادات {year}", "disposals", 120),
		currency(f"التكلفة في {fmt(end)}", "closing_cost"),
		{"label": "طريقة الإهلاك", "fieldname": "depreciation_method", "fieldtype": "Data", "width": 130},
		{"label": "نسبة الإهلاك السنوية", "fieldname": "rate_of_depreciation", "fieldtype": "Percent", "width": 110},
		{"label": "العمر الإنتاجي (سنة)", "fieldname": "useful_life_years", "fieldtype": "Float", "precision": 2, "width": 100},
		currency(f"مجمع الإهلاك في {fmt(before_start)}", "opening_accumulated_depreciation", 170),
		currency(f"مصروف الإهلاك الشهري {year}", "monthly_depreciation", 130),
		currency(f"مصروف الإهلاك السنوي {year}", "period_depreciation", 150),
		# Not in the client's sheet; still used for the closing accumulated depreciation
		{**currency(f"إهلاك الاستبعادات {year}", "depreciation_on_disposals", 150), "hidden": 1},
		currency(f"مجمع الإهلاك في {fmt(end)}", "closing_accumulated_depreciation", 170),
		currency(f"صافي القيمة الدفترية في {fmt(end)}", "net_book_value", 160),
		{"label": "حالة الأصل", "fieldname": "status", "fieldtype": "Data", "width": 130},
	]
