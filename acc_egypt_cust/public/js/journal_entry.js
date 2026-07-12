frappe.listview_settings["Journal Entry"] = {
    refresh(listview) {

        // Add button in top toolbar
        listview.page.add_button(
            __("Reopen Cancelled"),
            () => {

                let selected = listview.get_checked_items();

                if (!selected.length) {
                    frappe.msgprint(__("Please select at least one Journal Entry"));
                    return;
                }

                let names = selected.map(d => d.name);

                frappe.confirm(
                    __("Reopen {0} Journal Entries?", [names.length]),
                    () => {
                        frappe.call({
                            method: "acc_egypt_cust.tasks.reopen_cancelled_journal_entries",
                            args: {
                                names: names
                            },
                            freeze: true,
                            freeze_message: __("Processing...")
                        }).then(() => {
                            listview.refresh();
                        });
                    }
                );
            }
        );
    }
};