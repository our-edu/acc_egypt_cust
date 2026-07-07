# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from frappe.utils import flt
from erpnext.accounts.report.customer_ledger_summary.customer_ledger_summary import (
	PartyLedgerSummaryReport,
)


def execute(filters=None):
	args = {
		"party_type": "Customer",
		"naming_by": ["Selling Settings", "cust_master_name"],
	}
	columns, data = PartyLedgerSummaryReport(filters).run(args)
	
	# Filter out rows with zero closing balance if hide_zero_balance is enabled
	if filters and filters.get("hide_zero_balance"):
		data = [row for row in data if flt(row.get("closing_balance", 0)) != 0]
	
	return columns, data