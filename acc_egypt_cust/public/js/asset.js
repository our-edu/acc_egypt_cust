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
	available_for_use_date: function (frm) {
		set_default_depreciation_posting_date(frm);
	},
	finance_books_add: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		set_default_depreciation_posting_date_for_row(frm, row);
		set_default_salvage_value_for_row(row);
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

function set_default_salvage_value_for_row(row) {
	if (!row.expected_value_after_useful_life) {
		frappe.model.set_value(row.doctype, row.name, "expected_value_after_useful_life", 1);
	}
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
						set_default_salvage_value_for_row(row);
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
