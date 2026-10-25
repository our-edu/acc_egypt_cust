const DEFAULT_SOURCE_LOCATION = "Head Office";

frappe.ui.form.on("Asset Movement", {
	refresh: function (frm) {
		allow_employee_from_any_company(frm);
		if (frm.is_new()) {
			(frm.doc.assets || []).forEach((row) => set_default_source_location(row));
			frm.refresh_field("assets");
		}
	}
});

frappe.ui.form.on("Asset Movement Item", {
	assets_add: function (frm, cdt, cdn) {
		set_default_source_location(locals[cdt][cdn]);
		frm.refresh_field("assets");
	}
});

// Default the Source Location of new rows to Head Office. erpnext still
// overwrites it with the asset's actual location once an asset is selected.
function set_default_source_location(row) {
	if (!row.source_location) {
		row.source_location = DEFAULT_SOURCE_LOCATION;
	}
}

// erpnext restricts the Employee link queries on the Assets table to the
// Asset Movement's own company. Clear that filter so employees from any
// company can be selected as source/target custodian.
function allow_employee_from_any_company(frm) {
	frm.set_query("to_employee", "assets", function () {
		return {};
	});
	frm.set_query("from_employee", "assets", function () {
		return {};
	});
}
