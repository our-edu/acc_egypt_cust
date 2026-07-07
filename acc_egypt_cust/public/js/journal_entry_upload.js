/**
 * Journal Entry – custom party fields + Excel import
 */

frappe.provide("acc_cust.journal_entry");

const PARTY_ACCOUNT_TYPES = ["Receivable", "Payable"];

acc_cust.journal_entry.load_employee_loan_accounts = function (frm) {
    frm._employee_loan_accounts = [];

    if (!frm.doc.company) {
        return;
    }

    frappe.db
        .get_value("OurEdu HR Setting", { company: frm.doc.company }, "employee_loan_account")
        .then((r) => {
            const loan_account = r.message && r.message.employee_loan_account;
            frm._employee_loan_accounts = loan_account ? [loan_account] : [];
        });
};

acc_cust.journal_entry.sync_row_party_fields = function (row, loan_accounts = []) {
    if (!row.account) {
        row.party_type = "";
        row.party = "";
        return;
    }

    const party_type = row.custom_party_type || row.party_type;
    const is_employee_party = party_type === "Employee";
    const account_type = row.account_type;
    const is_loan_account = loan_accounts.includes(row.account);

    if (PARTY_ACCOUNT_TYPES.includes(account_type) || is_loan_account || is_employee_party) {
        row.party_type = row.custom_party_type || row.party_type || "";
        row.party = row.custom_party || row.party || "";
    } else {
        row.party_type = "";
        row.party = "";
    }
};

acc_cust.journal_entry.sync_all_party_fields = function (frm) {
    const loan_accounts = frm._employee_loan_accounts || [];
    (frm.doc.accounts || []).forEach((row) => {
        acc_cust.journal_entry.sync_row_party_fields(row, loan_accounts);
    });
    frm.refresh_field("accounts");
};

acc_cust.journal_entry.backfill_custom_party_fields = function (frm) {
    (frm.doc.accounts || []).forEach((row) => {
        if (!row.custom_party_type && row.party_type) {
            row.custom_party_type = row.party_type;
        }
        if (!row.custom_party && row.party) {
            row.custom_party = row.party;
        }
    });
};

frappe.ui.form.on("Journal Entry", {
    refresh(frm) {
        frm.set_query("custom_party_type", "accounts", () => ({
            filters: {
                name: ["in", Object.keys(frappe.boot.party_account_types || {})],
            },
        }));

        acc_cust.journal_entry.load_employee_loan_accounts(frm);
        acc_cust.journal_entry.backfill_custom_party_fields(frm);
        acc_cust.journal_entry.sync_all_party_fields(frm);

        frm.fields_dict.accounts.grid.add_custom_button(__("Import from Excel"), () => {
            _show_import_dialog(frm);
        });
    },

    company(frm) {
        acc_cust.journal_entry.load_employee_loan_accounts(frm);
        acc_cust.journal_entry.sync_all_party_fields(frm);
    },

    before_save(frm) {
        acc_cust.journal_entry.sync_all_party_fields(frm);
    },
});

frappe.ui.form.on("Journal Entry Account", {
    account(frm, cdt, cdn) {
        // Run after ERPNext sets account_type via get_account_details
        setTimeout(() => {
            const row = locals[cdt][cdn];
            acc_cust.journal_entry.sync_row_party_fields(row, frm._employee_loan_accounts || []);
            frm.refresh_field("accounts");
        }, 400);
    },

    custom_party_type(frm, cdt, cdn) {
        acc_cust.journal_entry.sync_row_party_fields(
            locals[cdt][cdn],
            frm._employee_loan_accounts || []
        );
        frm.refresh_field("accounts");
    },

    custom_party(frm, cdt, cdn) {
        acc_cust.journal_entry.sync_row_party_fields(
            locals[cdt][cdn],
            frm._employee_loan_accounts || []
        );
        frm.refresh_field("accounts");
    },
});

function _show_import_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __("Import Accounts from Excel"),
        fields: [
            {
                fieldtype: "HTML",
                fieldname: "instructions_html",
                options: `
                    <div style="margin-bottom: 10px; color: #555;">
                        Upload an <b>.xlsx</b> file with the following columns:<br>
                        <code>account</code>, <code>debit</code>, <code>credit</code>,
                        <code>custom_party_type</code>, <code>custom_party</code>, <code>cost_center</code>,
                        <code>project</code>, <code>user_remark</code>,
                        <code>reference_no</code>, <code>reference_date</code>
                        <br><small>Only <b>account</b> is required. Column names are case-insensitive.</small>
                    </div>
                    <button class="btn btn-xs btn-default" id="btn-download-template"
                        style="margin-bottom:12px;">
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
            {
                fieldtype: "Select",
                fieldname: "import_mode",
                label: __("Import Mode"),
                options: ["Append to existing rows", "Replace all existing rows"],
                default: "Append to existing rows",
                reqd: 1,
            },
        ],
        primary_action_label: __("Import"),
        primary_action(values) {
            if (!values.excel_file) {
                frappe.msgprint(__("Please upload an Excel file first."));
                return;
            }
            dialog.hide();
            _do_import(frm, values.excel_file, values.import_mode);
        },
    });

    dialog.show();

    dialog.$wrapper.find("#btn-download-template").on("click", () => {
        _download_template();
    });
}

function _do_import(frm, file_url, import_mode) {
    frappe.call({
        method: "acc_cust.overrides.journal_entry.parse_je_accounts_excel",
        args: { file_url: file_url },
        freeze: true,
        freeze_message: __("Importing…"),
        callback(r) {
            if (r.exc || !r.message) return;

            const rows = r.message;
            if (!rows.length) {
                frappe.msgprint(__("No rows were found in the file."));
                return;
            }

            if (import_mode === "Replace all existing rows") {
                frm.clear_table("accounts");
            } else {
                frm.doc.accounts = (frm.doc.accounts || []).filter((row) => row.account);
            }

            rows.forEach((row) => {
                const new_row = frm.add_child("accounts");
                Object.assign(new_row, row);
            });

            acc_cust.journal_entry.sync_all_party_fields(frm);

            frappe.show_alert({
                message: __("{0} row(s) imported successfully.", [rows.length]),
                indicator: "green",
            });
        },
    });
}

function _download_template() {
    window.open(
        "/api/method/acc_cust.overrides.journal_entry.download_je_accounts_template",
        "_blank"
    );
}
