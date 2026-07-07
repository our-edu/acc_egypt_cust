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
})();