frappe.ui.form.on("Payment Entry", {
    refresh(frm) {
        if (frm.doc.docstatus > 0) {
            // Replace standard "Ledger" button with Custom General Ledger
            frm.remove_custom_button(__("Ledger"), __("View"));
            frm.add_custom_button(
                __("Ledger"),
                function () {
                    frappe.route_options = {
                        voucher_no: frm.doc.name,
                        from_date: frm.doc.posting_date,
                        to_date: moment(frm.doc.modified).format("YYYY-MM-DD"),
                        company: frm.doc.company,
                        categorize_by: "",
                        show_cancelled_entries: frm.doc.docstatus === 2,
                    };
                    frappe.set_route("query-report", "Custom General Ledger");
                },
                __("View")
            );
        }
    },
});
