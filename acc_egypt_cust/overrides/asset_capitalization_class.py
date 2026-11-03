import frappe
from frappe.utils import cint

from erpnext.assets.doctype.asset.depreciation import get_gl_entries_on_asset_disposal
from erpnext.assets.doctype.asset_capitalization.asset_capitalization import AssetCapitalization


class CustomAssetCapitalization(AssetCapitalization):
	"""On submit, erpnext depreciates every consumed asset marked Calculate
	Depreciation up to the posting date (depreciate_asset) before disposing it.
	custom_depreciate_consumed_assets (set from the confirm dialog in
	public/js/asset_capitalization.js) lets the user skip that: the consumed
	assets are then disposed at their current booked value, with no extra
	depreciation entry. Checked (the default) keeps erpnext's behaviour."""

	def _depreciate_consumed_assets(self):
		return cint(self.get("custom_depreciate_consumed_assets", 1))

	def _skipped_depreciation_assets(self):
		# the consumed assets erpnext would otherwise have depreciated
		if self._depreciate_consumed_assets():
			return []
		return [
			item
			for item in self.asset_items
			if item.asset
			and frappe.db.get_value("Asset", item.asset, "asset_type") != "Composite Component"
			and frappe.db.get_value("Asset", item.asset, "calculate_depreciation")
		]

	def validate(self):
		super().validate()

		# erpnext's set_asset_values values each consumed asset as of the posting
		# date, i.e. including the depreciation it's about to post. Without that
		# depreciation, carry over the current booked value instead, so the
		# disposal posts no gain/loss and the target asset gets the full value.
		items = self._skipped_depreciation_assets()
		if items:
			for item in items:
				item.asset_value = item.current_asset_value
			self.calculate_totals()

	def get_gl_entries_for_consumed_asset_items(self, gl_entries, target_account, target_against, precision):
		if self._depreciate_consumed_assets():
			return super().get_gl_entries_for_consumed_asset_items(
				gl_entries, target_account, target_against, precision
			)

		# same as erpnext's, minus the depreciate_asset() call
		for item in self.asset_items:
			asset = frappe.get_doc("Asset", item.asset)

			if asset.asset_type != "Composite Component":
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
		if self._depreciate_consumed_assets():
			return super().restore_consumed_asset_items()

		# no depreciation entry was made on disposal and the schedule was never
		# touched, so there's nothing to reverse or reschedule on cancel
		for item in self.asset_items:
			asset = frappe.get_doc("Asset", item.asset)
			self.set_consumed_asset_status(asset)
			asset.db_set("disposal_date", None)
