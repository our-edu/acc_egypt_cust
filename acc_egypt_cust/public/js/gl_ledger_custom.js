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
            // generate_standard_print(ordered_selected);
            print_gl_statement(ordered_selected);
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

// ============================================================
// Print: renders the "Enhance" print format (Statement of Accounts)
// with the current report data and opens the browser print dialog.
// ============================================================
const GL_ENHANCE_PRINT_TEMPLATE = `
<style type="text/css">
    /* ============================================================
       Taleemna - Statement of Accounts (General Ledger)
       Primary color : #1F3A5F (navy)   -> change in all places to rebrand
       Accent color  : #E2A23B (gold)
       Note: wkhtmltopdf does not support CSS variables / flexbox well,
             so layout is done with tables and colors are hard-coded.
       ============================================================ */
    body, html {
        margin: 0;
        padding: 0;
        width: 100%;
        font-family: "Cairo", "Tahoma", Arial, sans-serif;
        color: #2b2b2b;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }

    .tl-wrap { width: 100%; }

    /* ---------- Header ---------- */
    .tl-header {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 0;
    }
    .tl-header td { vertical-align: middle; padding: 0; }
    .tl-logo { width: 150px; max-height: 80px; height: auto; }
    .tl-title {
        text-align: center;
        font-size: 20px;
        font-weight: bold;
        color: #1F3A5F;
        letter-spacing: 2px;
    }
    .tl-title-ar {
        text-align: center;
        font-size: 13px;
        color: #6b7a8c;
        margin-top: 3px;
        letter-spacing: 0;
    }
    .tl-company-right {
        text-align: right;
        font-size: 11px;
        color: #6b7a8c;
        line-height: 1.5;
    }
    .tl-company-right b { color: #1F3A5F; font-size: 13px; }

    .tl-bar {
        height: 5px;
        background-color: #1F3A5F;
        border-bottom: 3px solid #E2A23B;
        margin: 10px 0 14px 0;
    }

    /* ---------- Info cards ---------- */
    .tl-info {
        width: 100%;
        border-collapse: separate;
        border-spacing: 8px 0;
        margin: 0 -8px 12px -8px;
        font-size: 11.5px;
    }
    .tl-info td.tl-card {
        background-color: #F3F6FA;
        border: 1px solid #DCE3EC;
        border-top: 3px solid #1F3A5F;
        border-radius: 4px;
        padding: 8px 10px;
        vertical-align: top;
    }
    .tl-label {
        color: #6b7a8c;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: .5px;
        display: block;
        margin-bottom: 2px;
    }
    .tl-value { color: #1F3A5F; font-weight: bold; font-size: 12px; }
    .tl-acc-item { display: block; color: #1F3A5F; font-weight: bold; font-size: 11.5px; }

    /* ---------- Ledger table ---------- */
    .tl-table {
        width: 100%;
        font-size: 10.5px;
        border-collapse: collapse;
        margin-top: 4px;
    }
    .tl-table thead td {
        background-color: #1F3A5F;
        color: #ffffff;
        font-weight: bold;
        text-align: center;
        padding: 7px 5px;
        border: 1px solid #1F3A5F;
        font-size: 11px;
    }
    .tl-table tbody td {
        padding: 5px 6px;
        border-bottom: 1px solid #E3E8EF;
        border-left: 1px solid #EEF1F5;
        border-right: 1px solid #EEF1F5;
        vertical-align: top;
    }
    .tl-table tbody tr.tl-row-alt td { background-color: #F8FAFC; }
    .tl-table tr { page-break-inside: avoid; }

    .tl-date { text-align: center; white-space: nowrap; color: #44546a; }
    .tl-vtype { color: #6b7a8c; font-size: 9.5px; display: block; }
    .tl-vno   { color: #1F3A5F; font-weight: bold; }
    .tl-sub   { color: #8a96a6; font-size: 9px; display: block; margin-top: 2px; }
    .tl-desc  { font-size: 10px; unicode-bidi: plaintext; text-align: start; }
    .tl-num   { text-align: right; white-space: nowrap; }
    .tl-dr    { color: #1F3A5F; }
    .tl-cr    { color: #B23A3A; }
    .tl-tag {
        display: inline-block;
        font-size: 8.5px;
        font-weight: bold;
        padding: 1px 4px;
        border-radius: 3px;
        margin-left: 3px;
    }
    .tl-tag-dr { background-color: #E4ECF6; color: #1F3A5F; }
    .tl-tag-cr { background-color: #F8E3E3; color: #B23A3A; }

    /* Opening / Total / Closing rows */
    .tl-table tbody tr.tl-opening td {
        background-color: #FFF6E6;
        font-weight: bold;
        color: #8a5a00;
        border-bottom: 2px solid #E2A23B;
    }
    .tl-table tbody tr.tl-total td {
        background-color: #E4ECF6;
        font-weight: bold;
        color: #1F3A5F;
        border-top: 2px solid #1F3A5F;
    }
    .tl-table tbody tr.tl-closing td {
        background-color: #1F3A5F;
        color: #ffffff;
        font-weight: bold;
        font-size: 11.5px;
        border: 1px solid #1F3A5F;
    }
    .tl-table tbody tr.tl-closing td .tl-tag { background-color: #E2A23B; color: #1F3A5F; }

    /* ---------- Summary ---------- */
    .tl-summary {
        width: 100%;
        border-collapse: separate;
        border-spacing: 8px 0;
        margin: 18px -8px 0 -8px;
        page-break-inside: avoid;
    }
    .tl-summary td.tl-sbox {
        width: 33.33%;
        text-align: center;
        padding: 10px 6px;
        border-radius: 5px;
        border: 1px solid #DCE3EC;
        background-color: #F3F6FA;
    }
    .tl-summary .tl-sval { font-size: 15px; font-weight: bold; color: #1F3A5F; display: block; margin-top: 3px; }
    .tl-summary td.tl-sbox-main { background-color: #1F3A5F; border-color: #1F3A5F; }
    .tl-summary td.tl-sbox-main .tl-label { color: #c9d4e3; }
    .tl-summary td.tl-sbox-main .tl-sval { color: #ffffff; }
    .tl-summary td.tl-sbox-main .tl-sval small { color: #E2A23B; }

    /* ---------- Signatures & footer ---------- */
    .tl-sign {
        width: 100%;
        margin-top: 40px;
        font-size: 11px;
        page-break-inside: avoid;
    }
    .tl-sign td { width: 33.33%; text-align: center; padding: 0 15px; color: #6b7a8c; }
    .tl-sign-line { border-top: 1px solid #9aa7b8; margin-bottom: 4px; height: 1px; }

    .tl-footer {
        margin-top: 25px;
        padding-top: 6px;
        border-top: 1px solid #DCE3EC;
        font-size: 9px;
        color: #8a96a6;
        text-align: center;
    }

    @media print {
        @page { size: A4; margin: 10mm; }
        thead { display: table-header-group; }
    }
</style>

{%
    var logos = {
        "Taleemna For Commerce": "/files/WhatsApp Image 2026-03-01 at 2.19.06 PM.jpeg",
        "Company B": "/files/logo_company_b.png",
        "Company C": "/files/logo_company_c.png",
        "Company D": "/files/logo_company_d.png"
    };
    var logo = logos[filters.company];
    var cur = filters.presentation_currency;

    var fmt = function(v) { return format_currency(Math.abs(v || 0), cur); };
    var drcr = function(v) {
        v = v || 0;
        if (v < 0) return '<span class="tl-tag tl-tag-cr">Cr</span>';
        return '<span class="tl-tag tl-tag-dr">Dr</span>';
    };

    var l = data.length;
    var closing = l ? data[l - 1] : {};
    var totals  = l > 1 ? data[l - 2] : {};
    var stripe  = 0;
%}

<div class="tl-wrap">

    <!-- ================= HEADER ================= -->
    <table class="tl-header">
        <tr>
            <td style="width:170px;">
                {% if (logo) { %}
                    <img class="tl-logo" src="{%= encodeURI(logo) %}" />
                {% } %}
            </td>
            <td>
                <div class="tl-title">{%= __("STATEMENT OF ACCOUNTS") %}</div>
                <div class="tl-title-ar">كشف حساب</div>
            </td>
            <td class="tl-company-right" style="width:170px;">
                <b>{%= filters.company %}</b><br>
                {%= __("Printed on") %}: {%= frappe.datetime.str_to_user(frappe.datetime.now_datetime()) %}
            </td>
        </tr>
    </table>
    <div class="tl-bar"></div>

    <!-- ================= INFO CARDS ================= -->
    <table class="tl-info">
        <tr>
            <td class="tl-card" style="width:40%;">
                <span class="tl-label">{%= __("Account") %}</span>
                {% if (filters.account && filters.account.length) { %}
                    {% if (Array.isArray(filters.account)) { %}
                        {% for (var j = 0; j < filters.account.length; j++) { %}
                            <span class="tl-acc-item">{%= filters.account[j] %}</span>
                        {% } %}
                    {% } else { %}
                        <span class="tl-acc-item">{%= filters.account %}</span>
                    {% } %}
                {% } else if (filters.party_name || filters.party) { %}
                    <span class="tl-acc-item">{%= filters.party_name || filters.party %}</span>
                {% } else { %}
                    <span class="tl-acc-item">{%= __("All Accounts") %}</span>
                {% } %}
            </td>
            <td class="tl-card" style="width:30%;">
                <span class="tl-label">{%= __("Period") %}</span>
                <span class="tl-value">
                    {%= frappe.datetime.str_to_user(filters.from_date) %}
                    &nbsp;&rarr;&nbsp;
                    {%= frappe.datetime.str_to_user(filters.to_date) %}
                </span>
            </td>
            <td class="tl-card" style="width:30%;">
                <span class="tl-label">{%= __("Currency") %}</span>
                <span class="tl-value">{%= cur || "" %}</span>
            </td>
        </tr>
    </table>

    <!-- ================= LEDGER TABLE ================= -->
    {%
        var col_width = { posting_date: "7em", voucher_no: "11em", debit: "8.5em", credit: "8.5em", balance: "10em" };
        var amount_cols = ["debit", "credit", "balance"];
        var label_col = -1;
        for (var c = 0; c < columns.length; c++) {
            if (columns[c].fieldname === "voucher_no") { label_col = c; break; }
            if (label_col === -1 && amount_cols.indexOf(columns[c].fieldname) === -1) label_col = c;
        }
    %}
    <table class="tl-table">
        <thead>
            <tr>
            {% for (var c = 0; c < columns.length; c++) { %}
                <td style="{%= col_width[columns[c].fieldname] ? 'width:' + col_width[columns[c].fieldname] + ';' : '' %}">{%= __(columns[c].label) %}</td>
            {% } %}
            </tr>
        </thead>
        <tbody>
        {% for (var i = 0; i < l; i++) { %}
            {% var r = data[i]; %}

            {% if (r.posting_date) { %}
                {% stripe++; %}
                <tr class="{%= stripe % 2 == 0 ? 'tl-row-alt' : '' %}">
                {% for (var c = 0; c < columns.length; c++) { %}
                    {% var col = columns[c], f = col.fieldname; %}
                    {% if (f === "posting_date") { %}
                        <td class="tl-date">{%= frappe.datetime.str_to_user(r.posting_date) %}</td>
                    {% } else if (f === "voucher_no") { %}
                        <td>
                            <span class="tl-vtype">{%= __(r.voucher_type) %}</span>
                            <span class="tl-vno">{%= r.voucher_no %}</span>
                            {% if (r.bill_no) { %}
                                <span class="tl-sub">{%= __("Bill No") %}: {%= r.bill_no %}</span>
                            {% } %}
                        </td>
                    {% } else if (f === "remarks") { %}
                        <td class="tl-desc">
                            {%= r.remarks || "" %}
                            {% if (r.against_voucher) { %}
                                <span class="tl-sub">{%= __("Against") %}: {%= r.against_voucher %}</span>
                            {% } %}
                        </td>
                    {% } else if (f === "debit") { %}
                        <td class="tl-num tl-dr">{%= r.debit ? format_currency(r.debit, cur) : "" %}</td>
                    {% } else if (f === "credit") { %}
                        <td class="tl-num tl-cr">{%= r.credit ? format_currency(r.credit, cur) : "" %}</td>
                    {% } else if (f === "balance") { %}
                        <td class="tl-num">{%= fmt(r.balance) %} {%= drcr(r.balance) %}</td>
                    {% } else if (col.fieldtype === "Currency" || col.fieldtype === "Float") { %}
                        <td class="tl-num">{%= r[f] ? format_currency(r[f], cur) : "" %}</td>
                    {% } else if (col.fieldtype === "Date") { %}
                        <td class="tl-date">{%= r[f] ? frappe.datetime.str_to_user(r[f]) : "" %}</td>
                    {% } else { %}
                        <td class="tl-desc">{%= r[f] == null ? "" : __(String(r[f])) %}</td>
                    {% } %}
                {% } %}
                </tr>

            {% } else { %}
                {%
                    var rowClass = "tl-opening", rowLabel = __("Opening Balance");
                    if (i == l - 1)      { rowClass = "tl-closing"; rowLabel = __("Closing Balance"); }
                    else if (i == l - 2) { rowClass = "tl-total";   rowLabel = __("Total"); }
                %}
                <tr class="{%= rowClass %}">
                {% for (var c = 0; c < columns.length; c++) { %}
                    {% var f = columns[c].fieldname; %}
                    {% if (f === "debit") { %}
                        <td class="tl-num">{%= format_currency(r.debit || 0, cur) %}</td>
                    {% } else if (f === "credit") { %}
                        <td class="tl-num">{%= format_currency(r.credit || 0, cur) %}</td>
                    {% } else if (f === "balance") { %}
                        <td class="tl-num">{%= fmt(r.balance) %} {%= drcr(r.balance) %}</td>
                    {% } else if (c === label_col) { %}
                        <td>{%= rowLabel %}</td>
                    {% } else { %}
                        <td></td>
                    {% } %}
                {% } %}
                </tr>
            {% } %}
        {% } %}
        </tbody>
    </table>

    <!-- ================= SUMMARY ================= -->
    <table class="tl-summary">
        <tr>
            <td class="tl-sbox">
                <span class="tl-label">{%= __("Total Debit") %}</span>
                <span class="tl-sval">{%= format_currency(totals.debit || 0, cur) %}</span>
            </td>
            <td class="tl-sbox">
                <span class="tl-label">{%= __("Total Credit") %}</span>
                <span class="tl-sval" style="color:#B23A3A;">{%= format_currency(totals.credit || 0, cur) %}</span>
            </td>
            <td class="tl-sbox tl-sbox-main">
                <span class="tl-label">{%= __("Closing Balance") %}</span>
                <span class="tl-sval">
                    {%= fmt(closing.balance) %}
                    <small>{%= (closing.balance || 0) < 0 ? "Cr" : "Dr" %}</small>
                </span>
            </td>
        </tr>
    </table>

    <!-- ================= SIGNATURES ================= -->
    <table class="tl-sign">
        <tr>
            <td><div class="tl-sign-line"></div>{%= __("Prepared By") %}</td>
            <td><div class="tl-sign-line"></div>{%= __("Reviewed By") %}</td>
            <td><div class="tl-sign-line"></div>{%= __("Approved By") %}</td>
        </tr>
    </table>

    <div class="tl-footer">
        {%= filters.company %} &nbsp;•&nbsp; {%= __("This statement was generated automatically by the system") %}
    </div>

</div>
`;

function print_gl_statement(selected_columns) {
    let data = frappe.query_report.data;
    if (!data || data.length === 0) {
        frappe.msgprint(__("No data to print"));
        return;
    }
    let filters = frappe.query_report.get_filter_values();

    selected_columns = selected_columns || ["posting_date", "voucher_no", "remarks", "debit", "credit", "balance"];
    let columns = selected_columns
        .map((fieldname) => frappe.query_report.columns.find((c) => c.fieldname === fieldname))
        .filter(Boolean)
        .map((c) => ({ fieldname: c.fieldname, label: c.label, fieldtype: c.fieldtype }));

    let body;
    try {
        body = frappe.render_template(GL_ENHANCE_PRINT_TEMPLATE, { data: data, filters: filters, columns: columns });
    } catch (e) {
        console.error("Print error:", e);
        frappe.msgprint(__("Error generating print: ") + e.message);
        return;
    }

    let html = `<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>${__("General Ledger")}</title>
        <style>
            ${frappe.boot.print_css || ""}
            @media print { .print-format { margin: 0 !important; padding: 0 !important; } }
        </style>
    </head>
    <body>
        <div class="print-format">${body}</div>
    </body>
    </html>`;

    print_html_in_iframe(html);
}

// Open via hidden iframe — avoids all popup blocking issues
function print_html_in_iframe(html) {
    try {
        let blob = new Blob([html], { type: "text/html; charset=utf-8" });
        let blobUrl = URL.createObjectURL(blob);
        let iframe = document.createElement("iframe");
        // Must have real dimensions for the browser to render content before printing
        iframe.style.cssText = "position:fixed;top:-9999px;left:-9999px;width:210mm;height:297mm;border:none;";
        let printed = false;
        iframe.onload = function () {
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
    } catch (e) {
        console.error("Print error:", e);
        frappe.msgprint(__("Error generating print: ") + e.message);
    }
}

// ============================================================
// OLD PRINT CODE (column selection dialog + custom HTML statement).
// Replaced by print_gl_statement() above, which uses the Enhance print format
// (show_column_selection_dialog() is still in use and lives above).
// ============================================================
// // Function to generate standard print with your format inside the frame
// function generate_standard_print(selected_columns) {
//     let report_data = frappe.query_report.data;
//     let filters = frappe.query_report.get_filter_values();
//
//     if (!report_data || report_data.length === 0) {
//         frappe.msgprint(__('No data to print'));
//         return;
//     }
//
//     // Filter out summary rows (Opening/Total/Closing) and blank separators — they have no posting_date
//     let filtered_data = report_data
//
//     // The last two rows of report_data are always the global Total and Closing
//     // (works regardless of language/translation and grouping mode)
//     let erpnext_closing_row = report_data[report_data.length - 1];
//     let erpnext_total_row = report_data[report_data.length - 2];
//
//     if (!filtered_data || filtered_data.length === 0) {
//         frappe.msgprint(__('No transaction rows found to print.'));
//         return;
//     }
//
//     // Use existing balance from report (includes opening balance); only recalculate if missing
//     let running_balance = 0;
//     filtered_data.forEach(row => {
//         if (row.balance !== undefined && row.balance !== null) {
//             running_balance = row.balance;
//         } else {
//             if (row.debit) running_balance += row.debit;
//             if (row.credit) running_balance -= row.credit;
//             row.balance = running_balance;
//         }
//     });
//
//     // Get the standard print format HTML
//     let letter_head = frappe.boot.letter_heads ? frappe.boot.letter_heads[0] : null;
//
//     // Create the print HTML with standard frame
//     let html = `
//     <!DOCTYPE html>
//     <html>
//     <head>
//         <meta charset="utf-8">
//         <title>${__('General Ledger')}</title>
//         <style>
//             ${frappe.boot.print_css}
//
//             /* Your custom styles */
//             .title-letter-spacing {
//                 letter-spacing: .1rem;
//             }
//
//             .ledger-table {
//                 width: 100%;
//                 font-size: 11px;
//                 border-collapse: collapse;
//                 border: 2px solid black;
//                 margin-top: 10px;
//             }
//
//             .ledger-table th, .ledger-table td {
//                 border: 1px solid black;
//                 padding: 4px;
//             }
//
//             .summary-box {
//                 margin-top: 20px;
//                 border: 2px solid black;
//                 padding: 10px;
//                 width: 300px;
//                 float: right;
//                 text-align: right;
//             }
//
//             /* Small page number styling */
//             .page-number-small {
//                 text-align: right;
//                 font-size: 8px;
//                 color: #999;
//                 margin-top: 5px;
//                 margin-bottom: 0;
//                 padding-right: 5px;
//                 page-break-after: avoid;
//                 font-family: Arial, sans-serif;
//             }
//
//             /* Page break styling (own class: Frappe's print_css gives .page-break
//                page-break-after: always, which together with page-break-before
//                produced an empty page between every page) */
//             .gl-page-break {
//                 page-break-before: always;
//                 page-break-after: auto;
//             }
//
//             /* Ensure header stays on first page only */
//             .report-header {
//                 page-break-after: avoid;
//             }
//
//             /* Table styling for page breaks */
//             .ledger-table {
//                 page-break-inside: auto;
//             }
//
//             .ledger-table tr {
//                 page-break-inside: avoid;
//                 page-break-after: auto;
//             }
//
//             .ledger-table thead {
//                 display: table-header-group;
//             }
//
//             .ledger-table tfoot {
//                 display: table-footer-group;
//             }
//
//             @media print {
//                 @page {
//                     size: A4;
//                     margin: 1.5cm;
//
//                     @top-center {
//                         content: "${__("STATEMENT OF ACCOUNTS")} - ${__("Page")} " counter(page) " ${__("of")} " counter(pages);
//                         font-size: 12px;
//                         color: #666;
//                     }
//
//                     @bottom-right {
//                         content: counter(page);
//                         font-size: 8px;
//                         color: #999;
//                         font-family: Arial, sans-serif;
//                     }
//                 }
//
//                 /* First page already has the full report header */
//                 @page :first {
//                     @top-center {
//                         content: none;
//                     }
//                 }
//
//
//                 /* Ensure header only on first page */
//                 .report-header {
//                     page-break-after: avoid;
//                 }
//
//                 /* Table page break handling */
//                 .ledger-table {
//                     page-break-after: auto;
//                 }
//
//                 .ledger-table tr {
//                     page-break-inside: avoid;
//                 }
//
//                 .ledger-table thead {
//                     display: table-header-group;
//                 }
//
//                 .ledger-table tfoot {
//                     display: table-footer-group;
//                 }
//
//                 .print-format {
//                     margin: 0 !important;
//                     padding: 0 !important;
//                 }
//             }
//
//             .print-format {
//                 position: relative;
//             }
//
//             @media screen {
//                 .print-format {
//                     padding: 0.5in;
//                     min-height: 10in;
//                 }
//             }
//         </style>
//     </head>
//     <body>
//         <div class="print-format">
//             <!-- Letter Head (only on first page) -->
//             ${letter_head ? `
//             <div class="letter-head report-header">
//                 ${letter_head.header || ''}
//                 <hr>
//             </div>` : ''}
//
//             <!-- Main Content Container -->
//             <div class="report-content">`;
//
//     // Build the report content with proper page breaks
//     let content = build_report_content_with_page_breaks(filtered_data, filters, selected_columns, erpnext_total_row, erpnext_closing_row);
//     html += content;
//
//     // Add footer and auto-print script
//     html += `
//             </div>
//             <div style="text-align: center; font-size: 9px; margin-top: 20px; color: #666; page-break-before: avoid;">
//                 ${__("Printed on")} ${frappe.datetime.str_to_user(frappe.datetime.now_datetime())} 
//                 ${__("by")} ${frappe.session.user_fullname}
//             </div>
//         </div>
//     </body>
//     </html>`;
//
//     // Open via hidden iframe — avoids all popup blocking issues
//     try {
//         let blob = new Blob([html], { type: 'text/html; charset=utf-8' });
//         let blobUrl = URL.createObjectURL(blob);
//         let iframe = document.createElement('iframe');
//         // Must have real dimensions for the browser to render content before printing
//         iframe.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:210mm;height:297mm;border:none;';
//         let printed = false;
//         iframe.onload = function() {
//             if (printed) return;
//             printed = true;
//             setTimeout(() => {
//                 try {
//                     iframe.contentWindow.focus();
//                     iframe.contentWindow.print();
//                 } finally {
//                     setTimeout(() => {
//                         document.body.removeChild(iframe);
//                         URL.revokeObjectURL(blobUrl);
//                     }, 3000);
//                 }
//             }, 300);
//         };
//         document.body.appendChild(iframe);
//         iframe.src = blobUrl;
//     } catch(e) {
//         console.error("Print error:", e);
//         frappe.msgprint(__('Error generating print: ') + e.message);
//     }
// }
//
// // Function to build report content as one continuous table. The browser breaks
// // pages only when a page is full; thead repeats on every page and page numbers
// // come from the @page margin boxes (fixed row chunks left half-empty pages
// // whenever a chunk overflowed one page).
// function build_report_content_with_page_breaks(data, filters, selected_columns, total_row, closing_row) {
//     return build_page_content(data, filters, selected_columns, 1, 1, total_row, closing_row);
// }
//
// // Function to build content for a single page
// function build_page_content(page_data, filters, selected_columns, page_number, total_pages, total_row, closing_row) {
//     // Map selected columns to their display properties
//     let all_columns = frappe.query_report.columns;
//     let column_map = {};
//
//     selected_columns.forEach(fieldname => {
//         let col = all_columns.find(c => c.fieldname === fieldname);
//         if (col) {
//             column_map[fieldname] = col;
//         }
//     });
//
//     // Get company logo mapping
//     let logos = {
//         "Taleemna For Commerce": "/files/WhatsApp Image 2026-03-01 at 2.19.06 PM.jpeg",
//         "Rawnq": "/private/files/Rawnaq.png",
//         "Dar AL-Turath": "/private/files/Dar Al Turath.png",
//         "New Home": "/files/WhatsApp Image 2026-03-01 at 2.19.01 PM.jpeg"
//     };
//
//     let logo = logos[filters.company] || "";
//
//     let content = `
//         <div style="width:100%;">
//             <!-- Header Section (only on first page) -->
//             ${page_number === 1 ? `
//             <!-- ================= HEADER (LOGO RIGHT) ================= -->
//             <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:10px;">
//                 <!-- Left Spacer -->
//                 <div style="width:150px;"></div>
//
//                 <!-- Center Title -->
//                 <div class="title-letter-spacing"
//                      style="text-align:center; font-size:18px; text-decoration:underline; flex:1;">
//                     <b>${__("STATEMENT OF ACCOUNTS")}</b>
//                     ${(filters.party_name || (filters.party && filters.party.length > 0)) ? `
//                     <div style="font-size:14px; text-decoration:none; margin-top:4px; font-weight:bold;">
//                         ${filters.party_name || (Array.isArray(filters.party) ? filters.party.join(', ') : filters.party)}
//                     </div>` : ''}
//                 </div>
//
//                 <!-- Right Logo -->
//                 <div style="width:150px; text-align:right;">
//                     ${logo ? `<img src="${logo}" style="width:150px; height:auto; object-fit:contain;" />` : ''}
//                 </div>
//             </div>
//
//             <!-- ================= ACCOUNTS UNDER HEADER ================= -->
//             ${filters.account && filters.account.length > 0 ? `
//             <div style="text-align:center; margin-bottom:15px; font-size:13px;">
//                 <div style="font-weight:bold; margin-bottom:5px;">
//                     ${__("Accounts")}:
//                 </div>
//                 <div style="display:inline-block; text-align:left;">
//                     ${Array.isArray(filters.account) ? 
//                         filters.account.map(acc => `
//                         <div style="display:flex; margin-bottom:3px;">
//                             <span style="width:15px;">•</span>
//                             <span>${acc}</span>
//                         </div>`).join('') 
//                         : `
//                         <div style="display:flex;">
//                             <span style="width:15px;">•</span>
//                             <span>${filters.account}</span>
//                         </div>`
//                     }
//                 </div>
//             </div>` : ''}
//
//             <!-- ================= DATE + COMPANY + PERIOD ================= -->
//             <div style="display:flex; justify-content:space-between; margin-bottom:10px; font-size:12px;">
//                 <div>
//                     <b>${__("Date")}:</b>
//                     ${frappe.datetime.str_to_user(frappe.datetime.now_datetime())}<br>
//                     <b>${__("Company")}:</b>
//                     ${filters.company}
//                 </div>
//                 <div style="text-align:right;">
//                     <b>${__("From")}:</b>
//                     ${frappe.datetime.str_to_user(filters.from_date)}<br>
//                     <b>${__("To")}:</b>
//                     ${frappe.datetime.str_to_user(filters.to_date)}
//                 </div>
//             </div>
//             ` : `
//             <!-- Page header for continuation pages -->
//             <div style="text-align:center; margin-bottom:10px; font-size:12px; color:#666;">
//                 ${__("STATEMENT OF ACCOUNTS")} - ${__("Page")} ${page_number} ${__("of")} ${total_pages}
//             </div>
//             `}
//
//             <!-- ================= LEDGER TABLE ================= -->
//             <table class="ledger-table">
//                 <thead>
//                     <tr style="text-align:center; font-weight:bold; background-color:#f8f8f8;">`;
//
//     // Add table headers based on selected columns
//     selected_columns.forEach(fieldname => {
//         let col = column_map[fieldname];
//         if (col) {
//             content += `<td>${__(col.label)}</td>`;
//         }
//     });
//
//     content += `   </tr>
//                 </thead>
//                 <tbody>`;
//
//     // Add data rows for this page
//     const filtered_page_data = page_data.filter(row => {
//     // Remove total rows
//
//     // Keep Opening row even if it has no posting date
//     if (row.account === "Opening") return true;
//     if (row.account === "'Total'") return false;
//     if (row.account === "'Closing (Opening + Total)'") return false;
//
//     // Remove other summary rows (Closing, Total, etc.) that have no posting date
//
//     return true;
// });
// console.log(filtered_page_data);
//
// filtered_page_data.forEach((row) => {
//     content += '<tr>';
//
//     selected_columns.forEach(fieldname => {
//         let value = row[fieldname] || '';
//         let col = column_map[fieldname];
//
//         if (col) {
//             if (col.fieldtype === 'Currency') {
//                 value = (fieldname === 'balance')
//                     ? format_currency(row[fieldname] ?? 0, true)
//                     : format_currency(value);
//             } else if (col.fieldtype === 'Date' && value) {
//                 value = frappe.datetime.str_to_user(value);
//             }
//         }
//
//         if (fieldname === 'voucher_no') {
//             if (!row.voucher_type) {
//                 value = __('Opening');
//             } else {
//                 value = `${row.voucher_type} ${row.voucher_no}`;
//                 if (row.bill_no) {
//                     value += `<br><small>${__("Bill No")}: ${row.bill_no}</small>`;
//                 }
//             }
//         }
//
//         if (fieldname === 'remarks' && row.against_voucher) {
//             value = (row.remarks || '') +
//                 `<br><small>${__("Against")}: ${row.against_voucher}</small>`;
//         }
//
//         content += `<td>${value}</td>`;
//     });
//
//     content += '</tr>';
// });
//
//     // Add grand totals row on the last page
//     if (page_number === total_pages && closing_row) {
//         // Use the last row (Closing = Opening + Total) instead of the Total row
//         let total_debit = closing_row.debit || 0;
//         let total_credit = closing_row.credit || 0;
//         let closing_balance = closing_row ? (closing_row.balance ?? 0) : 0;
//
//         content += `<tr style="background-color:#f0f0f0; font-weight:bold;">`;
//         selected_columns.forEach(fieldname => {
//             if (fieldname === 'debit') {
//                 content += `<td style="text-align:right;">${format_currency(total_debit)}</td>`;
//             } else if (fieldname === 'credit') {
//                 content += `<td style="text-align:right;">${format_currency(total_credit)}</td>`;
//             } else if (fieldname === 'balance') {
//                 content += `<td style="text-align:right;">${format_currency(closing_balance, true)} ${closing_balance < 0 ? 'Cr' : 'Dr'}</td>`;
//             } else if (fieldname === 'posting_date') {
//                 content += `<td>${__('Total')}</td>`;
//             } else {
//                 content += `<td></td>`;
//             }
//         });
//         content += `</tr>`;
//     }
//
//     content += `   </tbody>
//             </table>
//
//             <!-- ================= CLOSING BALANCE (only on last page) ================= -->
//             ${page_number === total_pages && closing_row ? `
//             <div class="summary-box">
//                 <span style="font-size:12px; font-weight:bold;">
//                     ${__('Closing Balance')}:
//                 </span>
//                 <span style="font-size:14px; font-weight:bold; margin-left:10px;">
//                     ${format_currency(closing_row.balance ?? 0, true)}
//                     ${(closing_row.balance ?? 0) < 0 ? ' Cr' : ' Dr'}
//                 </span>
//             </div>
//             ` : ''}
//
//             <div style="clear:both;"></div>
//         </div>`;
//
//     return content;
// }

// Helper function to format currency
function format_currency(value, showZero = false) {
    if (value === undefined || value === null) return '';
    if (value === 0 && !showZero) return '';
    return new Intl.NumberFormat(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value);
}