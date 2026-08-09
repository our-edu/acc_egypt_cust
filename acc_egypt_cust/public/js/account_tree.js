// Override the "View Ledger" button in Account tree to open Custom General Ledger
(function () {
    const settings = frappe.treeview_settings["Account"];
    if (settings && settings.toolbar) {
        const btn = settings.toolbar.find((b) => b.label === __("View Ledger"));
        if (btn) {
            btn.click = function (node) {
                frappe.route_options = {
                    from_date: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[1],
                    to_date: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[2],
                    company:
                        frappe.treeview_settings["Account"].treeview.page.fields_dict.company.get_value(),
                };
                if (node.parent_label) {
                    frappe.route_options["account"] = node.label;
                }
                frappe.set_route("query-report", "Custom General Ledger");
            };
        }
    }
})();
