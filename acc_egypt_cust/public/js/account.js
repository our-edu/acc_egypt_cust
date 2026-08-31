frappe.ui.form.on("Account", {
    refresh(frm) {
        if (cint(frm.doc.is_group) == 0 && frappe.boot.user.can_read.indexOf("GL Entry") !== -1) {
            // Replace standard "General Ledger" button with Custom General Ledger
            frm.remove_custom_button(__("General Ledger"), __("View"));
            frm.add_custom_button(
                __("General Ledger"),
                function () {
                    frappe.route_options = {
                        account: frm.doc.name,
                        from_date: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[1],
                        to_date: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[2],
                        company: frm.doc.company,
                    };
                    frappe.set_route("query-report", "Custom General Ledger");
                },
                __("View")
            );
        }
    },
});
