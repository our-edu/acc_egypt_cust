frappe.ui.form.on("Asset", {
	refresh: function (frm) {
		set_sub_category_query(frm);
		disable_salvage_value_recalculation();
		override_set_finance_book();
	},
	asset_category: function (frm) {
		frm.set_value("sub_category", "");
		set_sub_category_query(frm);
	},
	// erpnext's own asset_type handler never re-runs toggle_reference_doc, so
	// purchase_receipt/purchase_invoice can be left stuck reqd=1 (set before a
	// type was picked) even after switching to Existing Asset/Composite Asset,
	// where those fields are hidden via depends_on but still checked as mandatory.
	asset_type: function (frm) {
		frm.trigger("toggle_reference_doc");
		// Mirror overrides/asset.py: Calculate Depreciation defaults on for every
		// type except Composite Asset, which stays off until it's capitalized.
<<<<<<< Updated upstream
		if (frm.doc.docstatus === 0 && frm.doc.asset_type !== "Composite Asset") {
			frm.set_value("calculate_depreciation", 1);
		}
		if (frm.doc.docstatus === 0 && frm.doc.asset_type == "Composite Asset") {
=======
		// Skip entirely when custom_stop_auto_calculate_depreciation is checked or
		// the asset category is non-depreciable (see set_non_depreciable_category_flag).
		if (frm.doc.docstatus === 0 && !is_auto_calculate_depreciation_stopped(frm)) {
			frm.set_value("calculate_depreciation", frm.doc.asset_type === "Composite Asset" ? 0 : 1);
		}
		// else{
		// 	frm.set_value("calculate_depreciation", 0);
		// }
	},
	custom_stop_auto_calculate_depreciation: function (frm) {
		frm.set_value("calculate_depreciation", 0);
		if (frm.doc.docstatus === 0 && !is_auto_calculate_depreciation_stopped(frm)) {
			frm.trigger("asset_type");
		}
	},
	// Safety net: reacts to the field's own change event, so it catches
	// calculate_depreciation being turned on by ANY code path - ours, erpnext
	// core's, another app's, or something async that runs after onload/refresh
	// - as long as it happened without asset_type being chosen yet, which is
	// the one case that should never legitimately mark it on a new Asset.
	calculate_depreciation: function (frm) {
		if (frm.is_new() && !frm.doc.asset_type && frm.doc.calculate_depreciation) {
>>>>>>> Stashed changes
			frm.set_value("calculate_depreciation", 0);
		}
	},
	available_for_use_date: function (frm) {
		set_default_depreciation_posting_date(frm);
	},
	finance_books_add: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		set_default_depreciation_posting_date_for_row(frm, row);
	}
});

// Asset Finance Book: erpnext keeps Salvage Value (expected_value_after_useful_life)
// and Salvage Value Percentage in sync with each other, and resets Salvage Value to 0
// whenever Rate of Depreciation changes. Remove those handlers so the Salvage Value
// entered by the user is never recalculated/overwritten by erpnext.
function disable_salvage_value_recalculation() {
	frappe.ui.form.off("Asset Finance Book", "expected_value_after_useful_life");
	frappe.ui.form.off("Asset Finance Book", "salvage_value_percentage");
	frappe.ui.form.off("Asset Finance Book", "rate_of_depreciation");
}

// erpnext auto-populates Finance Books from the Asset Category by replacing
// the whole table (frm.set_value("finance_books", [...])) when "Calculate
// Depreciation" is checked. That bulk replace bypasses the grid's row-add
// event, so finance_books_add never fires for these rows. Replace erpnext's
// "set_finance_book" trigger with our own copy that applies our defaults
// right after the table is populated.
function override_set_finance_book() {
	frappe.ui.form.off("Asset", "set_finance_book");
	frappe.ui.form.on("Asset", "set_finance_book", function (frm) {
		frappe.call({
			method: "erpnext.assets.doctype.asset.asset.get_item_details",
			args: {
				item_code: frm.doc.item_code,
				asset_category: frm.doc.asset_category,
				net_purchase_amount: frm.doc.net_purchase_amount,
			},
			callback: function (r) {
				if (r.message) {
					frm.set_value("finance_books", r.message);
					(frm.doc.finance_books || []).forEach(function (row) {
						set_default_depreciation_posting_date_for_row(frm, row);
					});
					frm.refresh_field("finance_books");
				}
			},
		});
	});
}

function set_sub_category_query(frm) {
	frm.set_query("sub_category", function () {
		return {
			filters: {
				parent_category: frm.doc.asset_category || ""
			}
		};
	});
}

function set_default_depreciation_posting_date(frm) {
	(frm.doc.finance_books || []).forEach(function (row) {
		set_default_depreciation_posting_date_for_row(frm, row);
	});
	frm.refresh_field("finance_books");
}

function set_default_depreciation_posting_date_for_row(frm, row) {
	if (!frm.doc.available_for_use_date) {
		return;
	}
	var end_of_month = moment(frm.doc.available_for_use_date).endOf("month").format("YYYY-MM-DD");
	frappe.model.set_value(row.doctype, row.name, "depreciation_start_date", end_of_month);
}
