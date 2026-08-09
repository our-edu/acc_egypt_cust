(function () {
  const REPORT = "Trial Balance";
  let originalFrappeFormat = null;

  function extractLastNumber(val) {
    if (val == null) return val;
    let s = String(val).replace(/<[^>]*>/g, "");
    const m = s.match(/-?\d[\d,]*\.?\d*/g);
    if (!m) return val;
    let num = m[m.length - 1].replace(/,/g, "");
    let floatVal = parseFloat(num);
    if (isNaN(floatVal)) return val;
    
    // Format number without currency symbol
    // Get currency from report or use default
    const currency = frappe.query_report?.filters?.presentation_currency || 
                     frappe.boot?.sysdefaults?.currency;
    
    // Get number format (similar to frappe's get_number_format logic)
    let sysdefaults = frappe?.boot?.sysdefaults;
    let numberFormat = sysdefaults?.number_format || "#,###.##";
    if (cint(sysdefaults?.use_number_format_from_currency) && currency) {
      const currencyFormat = frappe.model.get_value(":Currency", currency, "number_format");
      if (currencyFormat) numberFormat = currencyFormat;
    }
    
    const decimals = sysdefaults?.currency_precision || 2;
    
    // Use format_number (available globally) to format without currency symbol
    return format_number(floatVal, numberFormat, decimals);
  }

  function apply() {
    const qr = frappe.query_report;
    if (!qr || qr.report_name !== REPORT) return;

    // hide Currency filter (safe to repeat)
    const f = qr.get_filter && qr.get_filter("presentation_currency");
    if (f && f.$wrapper) f.$wrapper.hide();

    // patch once
    if (!frappe.__no_currency_format_patched) {
      frappe.__no_currency_format_patched = true;

      originalFrappeFormat = frappe.format;
      frappe.format = function (value, df, doc, row) {
        if (frappe.query_report && frappe.query_report.report_name === REPORT) {
          // if (typeof value === "string") return extractLastNumber(value);
          if (df && df.fieldtype === "Currency") return extractLastNumber(value);
        }
        return originalFrappeFormat.apply(this, arguments);
      };

      console.log("[qudarat_int] no-currency patch active ✅");

      // refresh ONCE only (after patch)
      setTimeout(() => {
        if (frappe.query_report && frappe.query_report.report_name === REPORT) {
          frappe.query_report.refresh();
        }
      }, 50);
    }
  }

  // run once on load + mild retries (no refresh loops now)
  frappe.after_ajax(() => apply());
  $(document).on("page-change", () => setTimeout(apply, 200));
  setTimeout(apply, 300);
  setTimeout(apply, 1200);

  // ─── Patch: redirect account clicks to Custom General Ledger ──────────────
  // Overrides erpnext.financial_statements.open_general_ledger so that when
  // viewing Trial Balance or Custom Trial Balance, clicking an account opens
  // Custom General Ledger instead of the standard General Ledger report.
  // All other reports (Balance Sheet, P&L, etc.) are unaffected.
  // No standard ERPNext files are modified.

  const TB_REPORTS = ["Trial Balance", "Custom Trial Balance"];

  function patchOpenGeneralLedger() {
    if (!erpnext?.financial_statements?.open_general_ledger) return;
    if (erpnext.financial_statements.__acc_egypt_cust_gl_patched) return;

    const _orig = erpnext.financial_statements.open_general_ledger;

    erpnext.financial_statements.open_general_ledger = function (data) {
      const reportName = frappe.query_report?.report_name;

      if (!TB_REPORTS.includes(reportName)) {
        // Not a Trial Balance report — use the original behaviour unchanged.
        return _orig.apply(this, arguments);
      }

      // ── Custom redirect logic ──────────────────────────────────────────────
      if (!data.account && !data.accounts) return;

      let filters = frappe.query_report.filters;

      let project = $.grep(filters, function (e) {
        return e.df.fieldname == "project";
      });

      let cost_center = $.grep(filters, function (e) {
        return e.df.fieldname == "cost_center";
      });

      frappe.route_options = {
        account: data.account || data.accounts,
        company: frappe.query_report.get_filter_value("company"),
        from_date: data.from_date || data.year_start_date,
        to_date: data.to_date || data.year_end_date,
        project: project && project.length > 0 ? project[0].get_value() : "",
        cost_center:
          cost_center && cost_center.length > 0 ? cost_center[0].get_value() : "",
      };

      // Pass through any other MultiSelectList filters (dimensions, etc.)
      filters.forEach(function (f) {
        if (f.df.fieldtype == "MultiSelectList") {
          if (f.df.fieldname in frappe.route_options) return;
          let val = f.get_value();
          if (val && val.length > 0) {
            frappe.route_options[f.df.fieldname] = val;
          }
        }
      });

      frappe.set_route("query-report", "Custom General Ledger");
    };

    erpnext.financial_statements.__acc_egypt_cust_gl_patched = true;
    console.log("[acc_egypt_cust] open_general_ledger → Custom General Ledger patch active ✅");
  }

  // Apply patch as soon as possible; retry to handle ERPNext async script loading.
  frappe.after_ajax(function () {
    patchOpenGeneralLedger();
    setTimeout(patchOpenGeneralLedger, 500);
    setTimeout(patchOpenGeneralLedger, 1500);
  });
})();