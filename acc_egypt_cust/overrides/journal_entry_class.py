import frappe
from frappe import _

from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry


class CustomJournalEntry(JournalEntry):
	def validate_party(self):
		for d in self.get("accounts"):
			account_type = frappe.get_cached_value("Account", d.account, "account_type")
			party_type = getattr(d, "custom_party_type", None) or d.party_type

			if account_type not in ("Receivable", "Payable"):
				continue

			has_party = (d.party_type and d.party) or (
				party_type == "Employee" and getattr(d, "custom_party", None)
			)
			if not has_party and not self.party_not_required:
				frappe.throw(
					_(
						"Row {0}: Party Type and Party is required for Receivable / Payable account {1}"
					).format(d.idx, d.account)
				)

			# Employee party is allowed regardless of account type mapping.
			if party_type == "Employee":
				continue

			if (
				d.party_type
				and frappe.db.get_value("Party Type", d.party_type, "account_type") != account_type
			):
				frappe.throw(
					_("Row {0}: Account {1} and Party Type {2} have different account types").format(
						d.idx, d.account, d.party_type
					)
				)
