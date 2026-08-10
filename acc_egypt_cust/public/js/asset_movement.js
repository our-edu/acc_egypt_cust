frappe.ui.form.on("Asset Movement", {
	refresh: function (frm) {
		allow_employee_from_any_company(frm);
	}
});

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
