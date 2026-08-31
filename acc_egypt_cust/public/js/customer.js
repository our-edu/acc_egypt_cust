frappe.ui.form.on("Customer", {
    refresh(frm) {
        if (!frm.doc.__islocal) {
            // Replace standard "Accounting Ledger" button with Custom General Ledger
            frm.remove_custom_button(__("Accounting Ledger"), __("View"));
            frm.add_custom_button(
                __("Accounting Ledger"),
                function () {
                    frappe.set_route("query-report", "Custom General Ledger", {
                        party_type: "Customer",
                        party: frm.doc.name,
                        party_name: frm.doc.customer_name,
                    });
                },
                __("View")
            );
        }
    },
});
