/**
 * Bank Reconciliation Statement Report Customization
 * 
 * Hide Bank Transaction entries from the report datatable view.
 * They will still appear in the print format.
 * Adds "Bank Statement Balance" filter for reconciliation.
 */

// Store Bank Transaction data globally for print
window._brs_bank_transactions = [];

(function() {
    // Add custom filter for Bank Statement Balance after report loads
    function addBankBalanceFilter() {
        console.log("tst")
        // Only add when the report instance is ready and has filters
        if (!frappe.query_report) return;
        if (frappe.query_report.report_name !== "Bank Reconciliation Statement") return;
        if (!frappe.query_report.filters || frappe.query_report.filters.length === 0) return;
        if (frappe.query_report._brs_filter_added) return;
        
        frappe.query_report._brs_filter_added = true;
        
        // Check if filter already exists in page fields
        if (frappe.query_report.page.fields_dict.bank_statement_balance) return;
        
        // Add the filter to the page (do NOT push to filters array - it breaks printing)
        frappe.query_report.page.add_field({
            fieldname: "bank_statement_balance",
            label: __("Bank Statement Balance (رصيد كشف البنك)"),
            fieldtype: "Currency",
            default: 0,
        });
    }

    // Intercept frappe.call responses for Bank Reconciliation Statement
    const original_call = frappe.call;
    
    frappe.call = function(opts) {
        // Check if this is the bank reconciliation report call (object format only)
        if (opts && typeof opts === "object" && opts.method === "frappe.desk.query_report.run") {
            const args = opts.args || {};
            if (args.report_name === "Bank Reconciliation Statement") {
                // Wrap the callback to filter data
                const original_callback = opts.callback;
                opts.callback = function(r) {
                    if (r && r.message && r.message.result && Array.isArray(r.message.result)) {
                        // Store Bank Transaction rows for print
                        window._brs_bank_transactions = r.message.result.filter(row => 
                            row && row.payment_document === "Bank Transaction"
                        );
                        
                        // Filter out Bank Transaction rows from report display
                        r.message.result = r.message.result.filter(row => 
                            !row || row.payment_document !== "Bank Transaction"
                        );
                    }
                    
                    if (original_callback) {
                        return original_callback(r);
                    }
                };
            }
        }
        
        // Pass ALL arguments to preserve positional argument calls
        return original_call.apply(this, arguments);
    };
    
    // Patch get_data_for_print when report is ready
    function patchPrintData() {
        if (!frappe.query_report) return;
        if (frappe.query_report.report_name !== "Bank Reconciliation Statement") return;
        if (frappe.query_report._brs_print_patched) return;
        
        frappe.query_report._brs_print_patched = true;
        
        const orig_print = frappe.query_report.get_data_for_print.bind(frappe.query_report);
        frappe.query_report.get_data_for_print = function() {
            let print_data = orig_print();
            if (window._brs_bank_transactions && window._brs_bank_transactions.length > 0) {
                print_data = print_data.concat(window._brs_bank_transactions);
            }
            return print_data;
        };
        
        // Patch get_filter_values to include bank_statement_balance
        const orig_filters = frappe.query_report.get_filter_values.bind(frappe.query_report);
        frappe.query_report.get_filter_values = function() {
            let filters = orig_filters();
            const bal_field = frappe.query_report.page.fields_dict.bank_statement_balance;
            if (bal_field) {
                filters.bank_statement_balance = bal_field.get_value();
            }
            return filters;
        };
        
        // Patch get_filters_html_for_print to handle custom filter fields gracefully
        frappe.query_report.get_filters_html_for_print = function() {
            const applied_filters = this.get_filter_values();
            
            return Object.keys(applied_filters)
                .map((fieldname) => {
                    // Skip custom fields that don't have a proper filter definition
                    const filter = frappe.query_report.get_filter(fieldname);
                    if (!filter || !filter.df) {
                        return null;
                    }
                    
                    const docfield = filter.df;
                    const value = applied_filters[fieldname];
                    
                    if (frappe.utils.is_empty(value) || docfield.hidden_due_to_dependency) {
                        return null;
                    }
                    
                    let display_value = value;
                    if (docfield.fieldtype === "Check") {
                        display_value = frappe.query_report.boolean_labels[cint(value)];
                    } else {
                        display_value = frappe.format(value, docfield);
                    }
                    
                    return `<div><span class="text-muted">${__(docfield.label)}:</span> ${display_value}</div>`;
                })
                .filter(Boolean)
                .join("");
        };
    }
    
    // Global cleanup: Remove broken filter objects from any report
    function cleanupBrokenFilters() {
        if (frappe.query_report && frappe.query_report.filters && Array.isArray(frappe.query_report.filters)) {
            frappe.query_report.filters = frappe.query_report.filters.filter(f => f && f.df);
        }
    }
    
    // Check for report readiness periodically
    setInterval(function() {
        const route = frappe.get_route();
        if (route && route[0] === "query-report") {
            // Always cleanup broken filters on any report
            cleanupBrokenFilters();
            
            if (route[1] === "Bank Reconciliation Statement") {
                patchPrintData();
                addBankBalanceFilter();
            }
        }
    }, 500);
})();
