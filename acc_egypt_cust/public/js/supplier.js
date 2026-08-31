frappe.ui.form.on("Supplier", {
    refresh(frm) {
        if (!frm.doc.__islocal) {
            // Replace standard "Accounting Ledger" button with Custom General Ledger
            frm.remove_custom_button(__("Accounting Ledger"), __("View"));
            frm.add_custom_button(
                __("Accounting Ledger"),
                function () {
                    frappe.set_route("query-report", "Custom General Ledger", {
                        party_type: "Supplier",
                        party: frm.doc.name,
                        party_name: frm.doc.supplier_name,
                    });
                },
                __("View")
            );
        }
    },
});
