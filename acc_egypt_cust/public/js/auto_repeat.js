// Adds a button to Auto Repeat to backfill documents for past schedule
// dates that were never generated (e.g. auto repeat was disabled/broken
// for a while and missed one or more of its scheduled dates).
frappe.ui.form.on("Auto Repeat", {
	refresh(frm) {
		if (frm.is_new() || frm.is_dirty() || frm.doc.disabled) {
			return;
		}

		frappe.call({
			method: "acc_egypt_cust.overrides.auto_repeat.get_missed_schedule_dates",
			args: { auto_repeat: frm.doc.name },
			callback: function (r) {
				const missed_dates = r.message || [];
				if (!missed_dates.length) {
					return;
				}

				frm.add_custom_button(
					__("Create Missed Documents ({0})", [missed_dates.length]),
					() => {
						frappe.confirm(
							__(
								"This will create {0} document(s) of type {1} for the following past scheduled date(s) that were never generated:<br><br>{2}",
								[missed_dates.length, `<b>${frappe.utils.escape_html(frm.doc.reference_doctype)}</b>`, missed_dates.join(", ")]
							),
							() => {
								frappe.call({
									method: "acc_egypt_cust.overrides.auto_repeat.create_missed_documents",
									args: {
										auto_repeat: frm.doc.name,
										dates: missed_dates,
									},
									freeze: true,
									freeze_message: __("Creating missed documents..."),
									callback: function (res) {
										const data = res.message || {};
										const created = data.created || [];
										const failed = data.failed || [];

										if (created.length) {
											frappe.msgprint({
												title: __("Documents Created"),
												indicator: "green",
												message: __("Created {0} document(s): {1}", [
													created.length,
													created.join(", "),
												]),
											});
										}

										if (failed.length) {
											frappe.msgprint({
												title: __("Some Documents Failed"),
												indicator: "red",
												message: __(
													"Failed to create documents for: {0}. Check the Error Log for details.",
													[failed.join(", ")]
												),
											});
										}

										frappe.auto_repeat.render_schedule(frm);
										frm.refresh();
									},
								});
							}
						);
					},
					__("Create")
				);
			},
		});
	},
});
