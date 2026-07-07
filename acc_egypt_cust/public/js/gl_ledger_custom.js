// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["General Ledger"] = {
    
    onload: function(report) {
    setTimeout(() => {

            let d = new frappe.ui.Dialog({
                title: __("Select Company"),
                fields: [{
                    fieldname: "company",
                    fieldtype: "Link",
                    options: "Company",
                    reqd: 1
                }],
                primary_action(values) {
                    report.set_filter_value("company", values.company);
                    d.hide();
                    report.refresh();
                }
            });

            d.show();
        

        let print_button = report.page.add_inner_button(
            __("Print"),
            function() {
                show_column_selection_dialog();
            }
        );

        print_button.addClass("btn-primary");

    }, 500);
},
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "finance_book",
			label: __("Finance Book"),
			fieldtype: "Link",
			options: "Finance Book",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
			width: "60px",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
			width: "60px",
		},
		{
			fieldname: "account",
			label: __("Account"),
			fieldtype: "MultiSelectList",
			options: "Account",
			get_data: function (txt) {
				return frappe.db.get_link_options("Account", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		{
			fieldname: "voucher_no",
			label: __("Voucher No"),
			fieldtype: "Data",
			on_change: function () {
				frappe.query_report.set_filter_value("categorize_by", "Categorize by Voucher (Consolidated)");
			},
		},
		{
			fieldname: "against_voucher_no",
			label: __("Against Voucher No"),
			fieldtype: "Data",
		},
		{
			fieldtype: "Break",
		},
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Autocomplete",
			options: Object.keys(frappe.boot.party_account_types),
			on_change: function () {
				frappe.query_report.set_filter_value("party", []);
			},
		},
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "MultiSelectList",
			options: "party_type",
			get_data: function (txt) {
				if (!frappe.query_report.filters) return;

				let party_type = frappe.query_report.get_filter_value("party_type");
				if (!party_type) return;

				return frappe.db.get_link_options(party_type, txt);
			},
			on_change: function () {
				var party_type = frappe.query_report.get_filter_value("party_type");
				var parties = frappe.query_report.get_filter_value("party");

				if (!party_type || parties.length === 0 || parties.length > 1) {
					frappe.query_report.set_filter_value("party_name", "");
					frappe.query_report.set_filter_value("tax_id", "");
					return;
				} else {
					var party = parties[0];
					var fieldname = erpnext.utils.get_party_name(party_type) || "name";
					frappe.db.get_value(party_type, party, fieldname, function (value) {
						frappe.query_report.set_filter_value("party_name", value[fieldname]);
					});

					if (party_type === "Customer" || party_type === "Supplier") {
						frappe.db.get_value(party_type, party, "tax_id", function (value) {
							frappe.query_report.set_filter_value("tax_id", value["tax_id"]);
						});
					}
				}
			},
		},
		{
			fieldname: "party_name",
			label: __("Party Name"),
			fieldtype: "Data",
			hidden: 1,
		},
		{
			fieldname: "categorize_by",
			label: __("Categorize by"),
			fieldtype: "Select",
			options: [
				"",
				{
					label: __("Categorize by Voucher"),
					value: "Categorize by Voucher",
				},
				{
					label: __("Categorize by Voucher (Consolidated)"),
					value: "Categorize by Voucher (Consolidated)",
				},
				{
					label: __("Categorize by Account"),
					value: "Categorize by Account",
				},
				{
					label: __("Categorize by Party"),
					value: "Categorize by Party",
				},
			],
			default: "Categorize by Voucher (Consolidated)",
		},
		{
			fieldname: "tax_id",
			label: __("Tax Id"),
			fieldtype: "Data",
			hidden: 1,
		},
		{
			fieldname: "presentation_currency",
			label: __("Currency"),
			fieldtype: "Select",
			options: erpnext.get_presentation_currency_list(),
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "MultiSelectList",
			options: "Cost Center",
			get_data: function (txt) {
				return frappe.db.get_link_options("Cost Center", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "MultiSelectList",
			options: "Project",
			get_data: function (txt) {
				return frappe.db.get_link_options("Project", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		{
			fieldname: "include_dimensions",
			label: __("Consider Accounting Dimensions"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "show_opening_entries",
			label: __("Show Opening Entries"),
			fieldtype: "Check",
		},
		{
			fieldname: "include_default_book_entries",
			label: __("Include Default FB Entries"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "show_cancelled_entries",
			label: __("Show Cancelled Entries"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_net_values_in_party_account",
			label: __("Show Net Values in Party Account"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_amount_in_company_currency",
			label: __("Show Credit / Debit in Company Currency"),
			fieldtype: "Check",
		},
		{
			fieldname: "add_values_in_transaction_currency",
			label: __("Add Columns in Transaction Currency"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_remarks",
			label: __("Show Remarks"),
			fieldtype: "Check",
            default: 1
		},
		{
			fieldname: "ignore_err",
			label: __("Ignore Exchange Rate Revaluation and Gain / Loss Journals"),
			fieldtype: "Check",
		},
		{
			fieldname: "ignore_cr_dr_notes",
			label: __("Ignore System Generated Credit / Debit Notes"),
			fieldtype: "Check",
		},
	],
	collapsible_filters: true,
	seperate_check_filters: true,
};

erpnext.utils.add_dimensions("General Ledger", 15);

// Function to show column selection dialog
function show_column_selection_dialog() {
    // Get current report columns
    let columns = frappe.query_report.columns;
    
    if (!columns || columns.length === 0) {
        frappe.msgprint(__("No columns available to print"));
        return;
    }
    
    // Define the desired column order
    let desired_order = [
        'posting_date',           // Date
        'voucher_no',             // Reference (voucher no)
        // 'against_voucher',      // Against Voucher
        'remarks',                // Remarks
        'debit',                  // Debit
        'credit',                 // Credit
        'balance'                 // Balance
    ];
    
    // Define default checked columns (including against_voucher_no)
    let default_checked = [
        'posting_date',
        'voucher_no',
        // 'against_voucher',
        'remarks',
        'debit',
        'credit',
        'balance'
    ];
    
    // Create dialog
    let dialog = new frappe.ui.Dialog({
        title: __('Select Columns to Print'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'action_buttons'
            },
            {
                fieldtype: 'HTML',
                fieldname: 'column_checkboxes'
            }
        ],
        primary_action_label: __('Print'),
        primary_action: function() {
            let selected_columns = [];
            
            // Get selected columns in the order they appear in the UI
            dialog.$wrapper.find('.column-checkbox:checked').each(function() {
                selected_columns.push($(this).data('fieldname'));
            });
            
            if (selected_columns.length === 0) {
                frappe.msgprint(__('Please select at least one column to print'));
                return;
            }
            
            dialog.hide();
            
            // Reorder selected columns according to desired order
            let ordered_selected = [];
            
            // First add columns from desired order that are selected
            desired_order.forEach(fieldname => {
                if (selected_columns.includes(fieldname)) {
                    ordered_selected.push(fieldname);
                }
            });
            
            // Then add any other selected columns not in desired order
            selected_columns.forEach(fieldname => {
                if (!desired_order.includes(fieldname)) {
                    ordered_selected.push(fieldname);
                }
            });
            
            // Generate print with selected columns
            generate_standard_print(ordered_selected);
        }
    });
    
    // Build action buttons HTML (at the top)
    let action_html = `
        <div style="margin-bottom: 15px; display: flex; gap: 10px; justify-content: flex-start;">
            <button class="btn btn-xs btn-default" id="select-all-btn">
                <i class="fa fa-check-square-o"></i> ${__('Select All')}
            </button>
            <button class="btn btn-xs btn-default" id="deselect-all-btn">
                <i class="fa fa-square-o"></i> ${__('Deselect All')}
            </button>
            <button class="btn btn-xs btn-default" id="reset-default-btn">
                <i class="fa fa-undo"></i> ${__('Reset to Default')}
            </button>
        </div>
    `;
    
    dialog.fields_dict.action_buttons.$wrapper.html(action_html);
    
    // Build checkbox HTML without any titles
    let html = '<div style="max-height: 400px; overflow-y: auto; padding: 10px; border: 1px solid #d1d8dd; border-radius: 3px;">';
    html += '<table class="table table-bordered" style="margin-bottom: 0;">';
    
    // First, add columns in the desired order
    desired_order.forEach(fieldname => {
        let col = columns.find(c => c.fieldname === fieldname);
        if (col && !col.hidden) {
            html += `<tr>
                <td style="width: 30px; vertical-align: middle;">
                    <input type="checkbox" 
                        class="column-checkbox" 
                        data-fieldname="${col.fieldname}"
                        ${default_checked.includes(col.fieldname) ? 'checked' : ''}>
                </td>
                <td style="vertical-align: middle;">${__(col.label)}</td>
            </tr>`;
        }
    });
    
    // Then add all other columns (excluding those already added)
    let other_columns = columns.filter(col => 
        col.fieldname && 
        col.label && 
        !col.hidden && 
        !desired_order.includes(col.fieldname)
    );
    
    // Sort remaining columns alphabetically
    other_columns.sort((a, b) => (a.label || '').localeCompare(b.label || ''));
    
    // Add other columns without any separator or title
    other_columns.forEach(col => {
        html += `<tr>
            <td style="width: 30px; vertical-align: middle;">
                <input type="checkbox" 
                    class="column-checkbox" 
                    data-fieldname="${col.fieldname}"
                    ${default_checked.includes(col.fieldname) ? 'checked' : ''}>
            </td>
            <td style="vertical-align: middle;">${__(col.label)}</td>
        </tr>`;
    });
    
    html += '</table></div>';
    
    dialog.fields_dict.column_checkboxes.$wrapper.html(html);
    
    // Add event handlers for buttons
    dialog.$wrapper.find('#select-all-btn').on('click', function() {
        dialog.$wrapper.find('.column-checkbox').prop('checked', true);
    });
    
    dialog.$wrapper.find('#deselect-all-btn').on('click', function() {
        dialog.$wrapper.find('.column-checkbox').prop('checked', false);
    });
    
    dialog.$wrapper.find('#reset-default-btn').on('click', function() {
        dialog.$wrapper.find('.column-checkbox').each(function() {
            let fieldname = $(this).data('fieldname');
            $(this).prop('checked', default_checked.includes(fieldname));
        });
    });
    
    dialog.show();
}

// Function to generate standard print with your format inside the frame
function generate_standard_print(selected_columns) {
    let report_data = frappe.query_report.data;
    let filters = frappe.query_report.get_filter_values();
    
    if (!report_data || report_data.length === 0) {
        frappe.msgprint(__('No data to print'));
        return;
    }

    // Filter out summary rows (Opening/Total/Closing) and blank separators — they have no posting_date
    let filtered_data = report_data
    
    // The last two rows of report_data are always the global Total and Closing
    // (works regardless of language/translation and grouping mode)
    let erpnext_closing_row = report_data[report_data.length - 1];
    let erpnext_total_row = report_data[report_data.length - 2];

    if (!filtered_data || filtered_data.length === 0) {
        frappe.msgprint(__('No transaction rows found to print.'));
        return;
    }
    
    // Use existing balance from report (includes opening balance); only recalculate if missing
    let running_balance = 0;
    filtered_data.forEach(row => {
        if (row.balance !== undefined && row.balance !== null) {
            running_balance = row.balance;
        } else {
            if (row.debit) running_balance += row.debit;
            if (row.credit) running_balance -= row.credit;
            row.balance = running_balance;
        }
    });
    
    // Get the standard print format HTML
    let letter_head = frappe.boot.letter_heads ? frappe.boot.letter_heads[0] : null;
    
    // Create the print HTML with standard frame
    let html = `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>${__('General Ledger')}</title>
        <style>
            ${frappe.boot.print_css}
            
            /* Your custom styles */
            .title-letter-spacing {
                letter-spacing: .1rem;
            }

            .ledger-table {
                width: 100%;
                font-size: 11px;
                border-collapse: collapse;
                border: 2px solid black;
                margin-top: 10px;
            }

            .ledger-table th, .ledger-table td {
                border: 1px solid black;
                padding: 4px;
            }

            .summary-box {
                margin-top: 20px;
                border: 2px solid black;
                padding: 10px;
                width: 300px;
                float: right;
                text-align: right;
            }
            
            /* Small page number styling */
            .page-number-small {
                text-align: right;
                font-size: 8px;
                color: #999;
                margin-top: 5px;
                margin-bottom: 0;
                padding-right: 5px;
                page-break-after: avoid;
                font-family: Arial, sans-serif;
            }
            
            /* Page break styling */
            .page-break {
                page-break-before: always;
                margin-top: 20px;
            }
            
            /* Ensure header stays on first page only */
            .report-header {
                page-break-after: avoid;
            }
            
            /* Table styling for page breaks */
            .ledger-table {
                page-break-inside: auto;
            }
            
            .ledger-table tr {
                page-break-inside: avoid;
                page-break-after: auto;
            }
            
            .ledger-table thead {
                display: table-header-group;
            }
            
            .ledger-table tfoot {
                display: table-footer-group;
            }
            
            @media print {
                @page {
                    size: A4;
                    margin: 1.5cm;
                }
                
                .page-break {
                    page-break-before: always;
                }
                
                /* Ensure header only on first page */
                .report-header {
                    page-break-after: avoid;
                }
                
                /* Table page break handling */
                .ledger-table {
                    page-break-after: auto;
                }
                
                .ledger-table tr {
                    page-break-inside: avoid;
                }
                
                .ledger-table thead {
                    display: table-header-group;
                }
                
                .ledger-table tfoot {
                    display: table-footer-group;
                }
                
                .print-format {
                    margin: 0 !important;
                    padding: 0 !important;
                }
            }
            
            .print-format {
                padding: 0.5in;
                min-height: 10in;
                position: relative;
            }
        </style>
    </head>
    <body>
        <div class="print-format">
            <!-- Letter Head (only on first page) -->
            ${letter_head ? `
            <div class="letter-head report-header">
                ${letter_head.header || ''}
                <hr>
            </div>` : ''}
            
            <!-- Main Content Container -->
            <div class="report-content">`;
    
    // Build the report content with proper page breaks
    let content = build_report_content_with_page_breaks(filtered_data, filters, selected_columns, erpnext_total_row, erpnext_closing_row);
    html += content;
    
    // Add footer and auto-print script
    html += `
            </div>
            <div style="text-align: center; font-size: 9px; margin-top: 20px; color: #666; page-break-before: avoid;">
                ${__("Printed on")} ${frappe.datetime.str_to_user(frappe.datetime.now_datetime())} 
                ${__("by")} ${frappe.session.user_fullname}
            </div>
        </div>
    </body>
    </html>`;
    
    // Open via hidden iframe — avoids all popup blocking issues
    try {
        let blob = new Blob([html], { type: 'text/html; charset=utf-8' });
        let blobUrl = URL.createObjectURL(blob);
        let iframe = document.createElement('iframe');
        // Must have real dimensions for the browser to render content before printing
        iframe.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:210mm;height:297mm;border:none;';
        let printed = false;
        iframe.onload = function() {
            if (printed) return;
            printed = true;
            setTimeout(() => {
                try {
                    iframe.contentWindow.focus();
                    iframe.contentWindow.print();
                } finally {
                    setTimeout(() => {
                        document.body.removeChild(iframe);
                        URL.revokeObjectURL(blobUrl);
                    }, 3000);
                }
            }, 300);
        };
        document.body.appendChild(iframe);
        iframe.src = blobUrl;
    } catch(e) {
        console.error("Print error:", e);
        frappe.msgprint(__('Error generating print: ') + e.message);
    }
}

// Function to build report content with proper page breaks after table
function build_report_content_with_page_breaks(data, filters, selected_columns, total_row, closing_row) {
    let content = '';
    let items_per_page = 25; // Number of rows per page
    let total_pages = Math.ceil(data.length / items_per_page);
    
    for (let page = 0; page < total_pages; page++) {
        // Add page break before each page except the first
        if (page > 0) {
            content += '<div class="page-break"></div>';
        }
        
        // Get data for current page
        let start = page * items_per_page;
        let end = Math.min(start + items_per_page, data.length);
        let page_data = data.slice(start, end);
        
        // Build page content
        content += build_page_content(page_data, filters, selected_columns, page + 1, total_pages, total_row, closing_row);
    }
    
    return content;
}

// Function to build content for a single page
function build_page_content(page_data, filters, selected_columns, page_number, total_pages, total_row, closing_row) {
    // Map selected columns to their display properties
    let all_columns = frappe.query_report.columns;
    let column_map = {};
    
    selected_columns.forEach(fieldname => {
        let col = all_columns.find(c => c.fieldname === fieldname);
        if (col) {
            column_map[fieldname] = col;
        }
    });
    
    // Get company logo mapping
    let logos = {
        "Taleemna For Commerce": "/files/WhatsApp Image 2026-03-01 at 2.19.06 PM.jpeg",
        "Rawnq": "/private/files/Rawnaq.png",
        "Dar AL-Turath": "/private/files/Dar Al Turath.png",
        "New Home": "/files/WhatsApp Image 2026-03-01 at 2.19.01 PM.jpeg"
    };
    
    let logo = logos[filters.company] || "";
    
    let content = `
        <div style="width:100%;">
            <!-- Header Section (only on first page) -->
            ${page_number === 1 ? `
            <!-- ================= HEADER (LOGO RIGHT) ================= -->
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:10px;">
                <!-- Left Spacer -->
                <div style="width:150px;"></div>

                <!-- Center Title -->
                <div class="title-letter-spacing"
                     style="text-align:center; font-size:18px; text-decoration:underline; flex:1;">
                    <b>${__("STATEMENT OF ACCOUNTS")}</b>
                    ${(filters.party_name || (filters.party && filters.party.length > 0)) ? `
                    <div style="font-size:14px; text-decoration:none; margin-top:4px; font-weight:bold;">
                        ${filters.party_name || (Array.isArray(filters.party) ? filters.party.join(', ') : filters.party)}
                    </div>` : ''}
                </div>

                <!-- Right Logo -->
                <div style="width:150px; text-align:right;">
                    ${logo ? `<img src="${logo}" style="width:150px; height:auto; object-fit:contain;" />` : ''}
                </div>
            </div>

            <!-- ================= ACCOUNTS UNDER HEADER ================= -->
            ${filters.account && filters.account.length > 0 ? `
            <div style="text-align:center; margin-bottom:15px; font-size:13px;">
                <div style="font-weight:bold; margin-bottom:5px;">
                    ${__("Accounts")}:
                </div>
                <div style="display:inline-block; text-align:left;">
                    ${Array.isArray(filters.account) ? 
                        filters.account.map(acc => `
                        <div style="display:flex; margin-bottom:3px;">
                            <span style="width:15px;">•</span>
                            <span>${acc}</span>
                        </div>`).join('') 
                        : `
                        <div style="display:flex;">
                            <span style="width:15px;">•</span>
                            <span>${filters.account}</span>
                        </div>`
                    }
                </div>
            </div>` : (filters.party && filters.party.length > 0) ? `
            
                
            </div>` : ''}

            <!-- ================= DATE + COMPANY + PERIOD ================= -->
            <div style="display:flex; justify-content:space-between; margin-bottom:10px; font-size:12px;">
                <div>
                    <b>${__("Date")}:</b>
                    ${frappe.datetime.str_to_user(frappe.datetime.now_datetime())}<br>
                    <b>${__("Company")}:</b>
                    ${filters.company}
                </div>
                <div style="text-align:right;">
                    <b>${__("From")}:</b>
                    ${frappe.datetime.str_to_user(filters.from_date)}<br>
                    <b>${__("To")}:</b>
                    ${frappe.datetime.str_to_user(filters.to_date)}
                </div>
            </div>
            ` : `
            <!-- Page header for continuation pages -->
            <div style="text-align:center; margin-bottom:10px; font-size:12px; color:#666;">
                ${__("STATEMENT OF ACCOUNTS")} - ${__("Page")} ${page_number} ${__("of")} ${total_pages}
            </div>
            `}
            
            <!-- ================= LEDGER TABLE ================= -->
            <table class="ledger-table">
                <thead>
                    <tr style="text-align:center; font-weight:bold; background-color:#f8f8f8;">`;
    
    // Add table headers based on selected columns
    selected_columns.forEach(fieldname => {
        let col = column_map[fieldname];
        if (col) {
            content += `<td>${__(col.label)}</td>`;
        }
    });
    
    content += `   </tr>
                </thead>
                <tbody>`;

    // Add data rows for this page
    const filtered_page_data = page_data.filter(row => {
    // Remove total rows

    // Keep Opening row even if it has no posting date
    if (row.account === "Opening") return true;
    if (row.account === "'Total'") return false;
    if (row.account === "'Closing (Opening + Total)'") return false;

    // Remove other summary rows (Closing, Total, etc.) that have no posting date

    return true;
});
console.log(filtered_page_data);

filtered_page_data.forEach((row) => {
    content += '<tr>';

    selected_columns.forEach(fieldname => {
        let value = row[fieldname] || '';
        let col = column_map[fieldname];

        if (col) {
            if (col.fieldtype === 'Currency') {
                value = (fieldname === 'balance')
                    ? format_currency(row[fieldname] ?? 0, true)
                    : format_currency(value);
            } else if (col.fieldtype === 'Date' && value) {
                value = frappe.datetime.str_to_user(value);
            }
        }

        if (fieldname === 'voucher_no') {
            if (!row.voucher_type) {
                value = __('Opening');
            } else {
                value = `${row.voucher_type} ${row.voucher_no}`;
                if (row.bill_no) {
                    value += `<br><small>${__("Bill No")}: ${row.bill_no}</small>`;
                }
            }
        }

        if (fieldname === 'remarks' && row.against_voucher) {
            value = (row.remarks || '') +
                `<br><small>${__("Against")}: ${row.against_voucher}</small>`;
        }

        content += `<td>${value}</td>`;
    });

    content += '</tr>';
});

    // Add grand totals row on the last page
    if (page_number === total_pages && total_row) {
        let total_debit = total_row.debit || 0;
        let total_credit = total_row.credit || 0;
        let closing_balance = closing_row ? (closing_row.balance ?? 0) : 0;

        content += `<tr style="background-color:#f0f0f0; font-weight:bold;">`;
        selected_columns.forEach(fieldname => {
            if (fieldname === 'debit') {
                content += `<td style="text-align:right;">${format_currency(total_debit)}</td>`;
            } else if (fieldname === 'credit') {
                content += `<td style="text-align:right;">${format_currency(total_credit)}</td>`;
            } else if (fieldname === 'balance') {
                content += `<td style="text-align:right;">${format_currency(closing_balance, true)} ${closing_balance < 0 ? 'Cr' : 'Dr'}</td>`;
            } else if (fieldname === 'posting_date') {
                content += `<td>${__('Total')}</td>`;
            } else {
                content += `<td></td>`;
            }
        });
        content += `</tr>`;
    }

    content += `   </tbody>
            </table>

            <!-- ================= PAGE NUMBER ================= -->
            <div class="page-number-small">${page_number}</div>
            
            <!-- ================= CLOSING BALANCE (only on last page) ================= -->
            ${page_number === total_pages && closing_row ? `
            <div class="summary-box">
                <span style="font-size:12px; font-weight:bold;">
                    ${__('Closing Balance')}:
                </span>
                <span style="font-size:14px; font-weight:bold; margin-left:10px;">
                    ${format_currency(closing_row.balance ?? 0, true)}
                    ${(closing_row.balance ?? 0) < 0 ? ' Cr' : ' Dr'}
                </span>
            </div>
            ` : ''}

            <div style="clear:both;"></div>
        </div>`;
    
    return content;
}

// Helper function to format currency
function format_currency(value, showZero = false) {
    if (value === undefined || value === null) return '';
    if (value === 0 && !showZero) return '';
    return new Intl.NumberFormat(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value);
}