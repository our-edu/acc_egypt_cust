frappe.after_ajax(() => {

    if (!frappe.query_reports["General Ledger"]) {
        return;
    }

    let original_onload =
        frappe.query_reports["General Ledger"].onload || function(){};

    frappe.query_reports["General Ledger"].onload = function(report) {

        original_onload(report);

        setTimeout(() => {

            if (report.get_filter_value("company")) {
                return;
            }

            let d = new frappe.ui.Dialog({
                title: __("Select Company"),
                fields: [
                    {
                        fieldname: "company",
                        fieldtype: "Link",
                        options: "Company",
                        reqd: 1
                    }
                ],
                primary_action(values) {

                    report.set_filter_value(
                        "company",
                        values.company
                    );

                    d.hide();

                    report.refresh();
                }
            });

            d.show();

        }, 500);
    };

});