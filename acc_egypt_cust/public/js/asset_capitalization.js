frappe.ui.form.on("Asset Capitalization", {
	// erpnext depreciates every consumed asset marked Calculate Depreciation up
	// to the posting date when this is submitted. Ask first; the answer goes in
	// custom_depreciate_consumed_assets, which overrides/asset_capitalization_class.py
	// reads to skip that depreciation when unchecked.
	before_submit: function (frm) {
		return get_depreciable_consumed_assets(frm).then((assets) => {
			if (!assets.length) {
				return;
			}
			return confirm_consumed_assets_depreciation(frm, assets);
		});
	},
});

function get_depreciable_consumed_assets(frm) {
	let names = (frm.doc.asset_items || []).map((row) => row.asset).filter(Boolean);
	if (!names.length) {
		return Promise.resolve([]);
	}
	return frappe.db
		.get_list("Asset", {
			filters: {
				name: ["in", names],
				calculate_depreciation: 1,
				asset_type: ["!=", "Composite Component"],
			},
			fields: ["name", "asset_name"],
			limit: names.length,
		})
		.then((assets) => assets || []);
}

function confirm_consumed_assets_depreciation(frm, assets) {
	return new Promise((resolve) => {
		let confirmed = false;
		let asset_list = assets
			.map((a) => `<li>${frappe.utils.escape_html(a.name)}: ${frappe.utils.escape_html(a.asset_name || "")}</li>`)
			.join("");

		let dialog = new frappe.ui.Dialog({
			title: __("Depreciate Consumed Assets?"),
			fields: [
				{
					fieldtype: "HTML",
					options: `<p>${__(
						"These consumed assets are marked Calculate Depreciation. Should they be depreciated up to the posting date before being capitalized?"
					)}</p><ul>${asset_list}</ul>`,
				},
				{
					fieldname: "depreciate",
					fieldtype: "Check",
					label: __("Depreciate consumed assets"),
					default: 1,
					description: __(
						"Unchecked: no depreciation entry is made; the assets are capitalized at their current booked value."
					),
				},
			],
			primary_action_label: __("Confirm"),
			primary_action: function (values) {
				confirmed = true;
				frm.doc.custom_depreciate_consumed_assets = values.depreciate ? 1 : 0;
				dialog.hide();
				resolve();
			},
		});

		// closing the dialog without confirming cancels the submit
		dialog.onhide = function () {
			if (!confirmed) {
				frappe.validated = false;
				resolve();
			}
		};

		dialog.show();
	});
}
