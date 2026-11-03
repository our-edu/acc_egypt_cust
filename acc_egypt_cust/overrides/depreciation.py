import frappe
from frappe.utils import nowdate

from erpnext.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry
from erpnext.assets.doctype.asset import depreciation


def create_reverse_depreciation_entry(asset_name, journal_entry):
	"""erpnext's version throws "Please disable workflow temporarily for Journal
	Entry None" whenever a Journal Entry workflow is active, which blocks cancelling
	an Asset Capitalization / asset sale / scrap that posted a depreciation entry on
	disposal. Submit the reversal regardless, like auto_submit_depreciation_entry
	does for depreciation entries (overrides/journal_entry.py)."""
	reverse_journal_entry = make_reverse_journal_entry(journal_entry)
	reverse_journal_entry.posting_date = nowdate()

	for account in reverse_journal_entry.accounts:
		account.update(
			{
				"reference_type": "Asset",
				"reference_name": asset_name,
			}
		)

	frappe.flags.is_reverse_depr_entry = True
	reverse_journal_entry.flags.ignore_permissions = True
	reverse_journal_entry.submit()
	return reverse_journal_entry


# reverse_depreciation_entry_made_on_disposal looks this up in the module at call time
depreciation.create_reverse_depreciation_entry = create_reverse_depreciation_entry
