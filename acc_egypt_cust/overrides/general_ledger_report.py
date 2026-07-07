import frappe
from frappe.desk.query_report import run as _frappe_run


@frappe.whitelist()
def run(
	report_name,
	filters=None,
	user=None,
	ignore_prepared_report=False,
	custom_columns=None,
	is_tree=False,
	parent_field=None,
	are_default_filters=True,
	js_filters=None,
):
	result = _frappe_run(
		report_name=report_name,
		filters=filters,
		user=user,
		ignore_prepared_report=ignore_prepared_report,
		custom_columns=custom_columns,
		is_tree=is_tree,
		parent_field=parent_field,
		are_default_filters=are_default_filters,
		js_filters=js_filters,
	)

	if report_name == "General Ledger":
		_inject_purchase_invoice_titles(result)

	return result


def _inject_purchase_invoice_titles(result):
	rows = result.get("result") or []

	pi_names = list({
		row.get("voucher_no")
		for row in rows
		if isinstance(row, dict)
		and row.get("voucher_type") == "Purchase Invoice"
		and row.get("voucher_no")
	})

	if not pi_names:
		return

	pi_records = frappe.get_all(
		"Purchase Invoice",
		filters={"name": ("in", pi_names)},
		fields=["name", "title"],
	)
	pi_titles = {r.name: r.title for r in pi_records}

	for row in rows:
		if (
			isinstance(row, dict)
			and row.get("voucher_type") == "Purchase Invoice"
			and row.get("voucher_no")
		):
			title = pi_titles.get(row["voucher_no"])
			if title:
				row["remarks"] = title
