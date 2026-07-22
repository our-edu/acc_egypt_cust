frappe.ui.form.on("Asset", {
	refresh: function (frm) {
		set_sub_category_query(frm);
	},
	asset_category: function (frm) {
		frm.set_value("sub_category", "");
		set_sub_category_query(frm);
	}
});

function set_sub_category_query(frm) {
	frm.set_query("sub_category", function () {
		return {
			filters: {
				parent_category: frm.doc.asset_category || ""
			}
		};
	});
}
