/**
 * Bank Reconciliation Tool – Import Bank Transactions from Excel
 *
 * Adds an "Import Bank Transactions" button to the Bank Reconciliation Tool form.
 * Users can download a pre-formatted template, fill it in, and upload it to
 * create submitted Bank Transaction records in bulk.
 */

frappe.ui.form.on("Bank Reconciliation Tool", {
	refresh(frm) {
		// frappe.msgprint("tst")
		frm.add_custom_button(__("Import Bank Transactions"), () => {
			_show_bt_import_dialog(frm);
		});
	},
});

function _show_bt_import_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Import Bank Transactions from Excel"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "instructions_html",
				options: `
					<div style="margin-bottom:10px; color:#555;">
						Upload an <b>.xlsx</b> file with the following columns:<br>
						<code>Date</code>, <code>Deposit</code>, <code>Withdrawal</code>,
						<code>Description</code>, <code>Reference Number</code>, <code>Bank Account</code>
						<br><br>
						<small>
							• Column names are case-insensitive.<br>
							• <b>Date</b> and at least one of <b>Deposit</b> / <b>Withdrawal</b> are required per row.<br>
							• <b>Bank Account</b> column is optional if a Bank Account is already selected in the form.
						</small>
					</div>
					<button class="btn btn-xs btn-default" id="btn-download-bt-template"
						style="margin-bottom:14px;">
						⬇ Download Template
					</button>
				`,
			},
			{
				fieldtype: "Attach",
				fieldname: "excel_file",
				label: __("Excel File (.xlsx)"),
				reqd: 1,
				options: { restrictions: { allowed_file_types: [".xlsx"] } },
			},
		],
		primary_action_label: __("Import"),
		primary_action(values) {
			if (!values.excel_file) {
				frappe.msgprint(__("Please upload an Excel file first."));
				return;
			}
			dialog.hide();
			_do_import(frm, values.excel_file);
		},
	});

	dialog.show();

	dialog.$wrapper.find("#btn-download-bt-template").on("click", () => {
		window.open(
			"/api/method/acc_egypt_cust.overrides.bank_reconciliation.download_bank_transaction_template",
			"_blank"
		);
	});
}

function _do_import(frm, file_url) {
	frappe.call({
		method: "acc_egypt_cust.overrides.bank_reconciliation.upload_bank_transactions",
		args: {
			file_url: file_url,
			bank_account: frm.doc.bank_account || null,
		},
		freeze: true,
		freeze_message: __("Importing bank transactions…"),
		callback(r) {
			if (r.exc || !r.message) return;

			const { created, errors } = r.message;

			let msg = __(
				"{0} bank transaction(s) created and submitted.",
				[`<b>${created}</b>`]
			);

			if (errors && errors.length) {
				msg +=
					`<br><br><b>${__("Skipped rows / warnings")}:</b><ul style="margin-top:6px;">` +
					errors.map((e) => `<li>${e}</li>`).join("") +
					"</ul>";
			}

			frappe.msgprint({
				title: __("Import Complete"),
				message: msg,
				indicator: created > 0 ? "green" : "orange",
			});

			if (created > 0) {
				frm.trigger("make_reconciliation_tool");
			}
		},
	});
}
