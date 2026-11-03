import frappe
from frappe import _
from frappe.utils import add_days, flt, get_link_to_form, getdate

import erpnext
from erpnext.assets.doctype.asset.asset import get_asset_value_after_depreciation
from erpnext.assets.doctype.asset.depreciation import (
	depreciate_asset,
	get_gl_entries_on_asset_disposal,
	get_value_after_depreciation_on_disposal_date,
	reset_depreciation_schedule,
	reverse_depreciation_entry_made_on_disposal,
)
from erpnext.assets.doctype.asset_capitalization.asset_capitalization import (
	AssetCapitalization,
	get_consumed_asset_details as erpnext_get_consumed_asset_details,
)
from erpnext.stock.get_item_details import ItemDetailsCtx


# erpnext depreciates a consumed asset up to and including the capitalization's
# posting date (from 1-1 to a capitalization on 25-1 = 25 days). Here the posting
# date itself is excluded: depreciation runs up to the day before (24 days), and an
# asset available for use on the posting date itself gets no depreciation at all
# (an empty depreciation schedule).


def _depreciation_end_date(posting_date):
	return add_days(getdate(posting_date), -1)


def _is_depreciated_on_capitalization(asset_name, posting_date):
	"""Whether at least one day of depreciation falls before posting_date."""
	asset = frappe.db.get_value(
		"Asset",
		asset_name,
		["asset_type", "calculate_depreciation", "available_for_use_date"],
		as_dict=True,
	)
	return (
		asset
		and asset.asset_type != "Composite Component"
		and asset.calculate_depreciation
		and asset.available_for_use_date
		and getdate(asset.available_for_use_date) < getdate(posting_date)
	)


def get_value_on_capitalization(asset_name, posting_date, finance_book=None):
	# erpnext's function is whitelisted, so in a request its disposal_date must be a str
	if not _is_depreciated_on_capitalization(asset_name, posting_date):
		# erpnext returns the undepreciated value when the asset is available on
		# the posting date itself (and validates a posting date before that)
		return get_value_after_depreciation_on_disposal_date(asset_name, str(posting_date), finance_book)
	return get_value_after_depreciation_on_disposal_date(
		asset_name, str(_depreciation_end_date(posting_date)), finance_book
	)


@frappe.whitelist()
@erpnext.normalize_ctx_input(ItemDetailsCtx)
def get_consumed_asset_details(ctx):
	out = erpnext_get_consumed_asset_details(ctx)
	if ctx.asset:
		out.asset_value = get_value_on_capitalization(ctx.asset, ctx.posting_date, ctx.finance_book)
	return out


class CustomAssetCapitalization(AssetCapitalization):
	@frappe.whitelist()
	def set_asset_values(self):
		for d in self.get("asset_items"):
			if d.asset:
				finance_book = d.get("finance_book") or self.get("finance_book")
				d.current_asset_value = flt(get_asset_value_after_depreciation(d.asset, finance_book=finance_book))
				d.asset_value = get_value_on_capitalization(d.asset, self.posting_date, finance_book)

	def get_gl_entries_for_consumed_asset_items(self, gl_entries, target_account, target_against, precision):
		# same as erpnext's, except depreciation runs up to the day before the posting date
		for item in self.asset_items:
			asset = frappe.get_doc("Asset", item.asset)

			if asset.asset_type != "Composite Component":
				if asset.calculate_depreciation:
					# An asset available for use on the posting date itself gets 0 days
					# here, so it ends with an empty schedule and no depreciation entry.
					notes = _(
						"This schedule was created when Asset {0} was consumed through Asset Capitalization {1}."
					).format(
						get_link_to_form(asset.doctype, asset.name),
						get_link_to_form(self.doctype, self.get("name")),
					)
					depreciate_asset(asset, _depreciation_end_date(self.posting_date), notes)
					asset.reload()

				fixed_asset_gl_entries = get_gl_entries_on_asset_disposal(
					asset,
					item.asset_value,
					item.get("finance_book") or self.get("finance_book"),
					self.get("doctype"),
					self.get("name"),
					self.get("posting_date"),
				)

				for gle in fixed_asset_gl_entries:
					gle["against"] = target_account
					gl_entries.append(self.get_gl_dict(gle, item=item))
					target_against.add(gle["account"])

			asset.db_set("disposal_date", self.posting_date)
			self.set_consumed_asset_status(asset)

	def restore_consumed_asset_items(self):
		for item in self.asset_items:
			asset = frappe.get_doc("Asset", item.asset)
			self.set_consumed_asset_status(asset)

			if asset.calculate_depreciation:
				# erpnext only reverses a depreciation entry dated on asset.disposal_date
				# (the posting date). Ours is dated the day before; capitalizations
				# submitted before this change still have theirs on the posting date.
				for date in (getdate(self.posting_date), _depreciation_end_date(self.posting_date)):
					asset.disposal_date = date
					reverse_depreciation_entry_made_on_disposal(asset)
				notes = _(
					"This schedule was created when Asset {0} was restored on Asset Capitalization {1}'s cancellation."
				).format(
					get_link_to_form(asset.doctype, asset.name), get_link_to_form(self.doctype, self.name)
				)
				reset_depreciation_schedule(asset, notes)
			asset.db_set("disposal_date", None)
