# Copyright (c) 2026, our-edu and contributors
# For license information, please see license.txt

"""
Bank Reconciliation Customization - Row-Level Journal Entry Matching

This module provides custom bank reconciliation logic that allows matching
bank transactions to specific Journal Entry Account rows instead of the
whole Journal Entry document.

Key features:
- Each JE Account row can have its own reference number (custom_reference_no)
- Bank transactions match against individual JE rows
- Allocation tracking at row level
"""

import io
import json

import frappe
from frappe import _


def _custom_get_journal_entries(filters):
    """
    Custom override of get_journal_entries.

    Changes vs stock ERPNext:
    - Includes jvd.user_remark as description
    - Uses row-level reference (custom_reference_no) falling back to jv.cheque_no
    - Subtracts already-reconciled amounts per JE Account row (via Bank Transaction
      Payments rows that carry custom_je_row_name) so that:
        * Unreconciled rows appear at full amount
        * Partially reconciled rows appear at the remaining unreconciled amount
        * Fully reconciled rows are excluded entirely
    - Old-style clearance (jv.clearance_date set directly) is still handled by the
      existing IFNULL filter, unchanged.
    """
    return frappe.db.sql(
        """
        SELECT
            'Journal Entry'                                                         AS payment_document,
            jv.posting_date,
            jv.name                                                                 AS payment_entry,
            GREATEST(0, jvd.debit_in_account_currency  - COALESCE(row_alloc.allocated, 0)) AS debit,
            GREATEST(0, jvd.credit_in_account_currency - COALESCE(row_alloc.allocated, 0)) AS credit,
            jvd.against_account,
            COALESCE(NULLIF(jvd.custom_reference_no, ''), jv.cheque_no)             AS reference_no,
            jv.cheque_date                                                          AS ref_date,
            jv.clearance_date,
            jvd.account_currency,
            jvd.user_remark                                                         AS description
        FROM `tabJournal Entry Account` jvd
        JOIN `tabJournal Entry` jv ON jvd.parent = jv.name
        LEFT JOIN (
            SELECT
                btp.payment_entry,
                btp.custom_je_row_name,
                SUM(btp.allocated_amount) AS allocated
            FROM `tabBank Transaction Payments` btp
            JOIN `tabBank Transaction` bt ON bt.name = btp.parent
            WHERE bt.docstatus = 1
                AND bt.date <= %(report_date)s
                AND btp.payment_document = 'Journal Entry'
                AND btp.custom_je_row_name IS NOT NULL
                AND btp.custom_je_row_name != ''
            GROUP BY btp.payment_entry, btp.custom_je_row_name
        ) row_alloc ON row_alloc.payment_entry = jv.name
                   AND row_alloc.custom_je_row_name = jvd.name
        WHERE jv.docstatus = 1
            AND jvd.account = %(account)s
            AND jv.posting_date <= %(report_date)s
            AND IFNULL(jv.clearance_date, '4000-01-01') > %(report_date)s
            AND IFNULL(jv.is_opening, 'No') = 'No'
            AND jv.company = %(company)s
            AND (
                jvd.debit_in_account_currency  - COALESCE(row_alloc.allocated, 0) > 0
                OR
                jvd.credit_in_account_currency - COALESCE(row_alloc.allocated, 0) > 0
            )
        ORDER BY jv.posting_date, jv.name DESC
        """,
        filters,
        as_dict=1,
    )


# Apply patch immediately when module loads
try:
    import erpnext.accounts.report.bank_reconciliation_statement.bank_reconciliation_statement as brs_module
    brs_module.get_journal_entries = _custom_get_journal_entries
except Exception:
    pass  # Silently fail if ERPNext not fully loaded yet
from frappe.query_builder.custom import ConstantColumn
from frappe.query_builder.functions import Coalesce
from frappe.utils import cint, flt, getdate


@frappe.whitelist()
def custom_get_linked_payments(
    bank_transaction_name,
    document_types=None,
    from_date=None,
    to_date=None,
    filter_by_reference_date=None,
    from_reference_date=None,
    to_reference_date=None,
):
    """
    Custom version of get_linked_payments that handles JE row-level matching.
    
    Flow:
    1. Remove "journal_entry" from document_types (we handle it separately)
    2. Call original check_matching for other document types (PE, SI, PI, etc.)
    3. Add our custom JE row matching
    4. Apply row-level allocation subtraction for JEs
    5. Return combined results
    """
    transaction = frappe.get_doc("Bank Transaction", bank_transaction_name)
    bank_account_data = frappe.db.get_values(
        "Bank Account", transaction.bank_account, ["account", "company"], as_dict=True
    )[0]
    gl_account = bank_account_data.account
    company = bank_account_data.company
    
    # Parse document_types if string
    if isinstance(document_types, str):
        document_types = json.loads(document_types)
    
    if document_types is None:
        document_types = []
    
    # Separate JE from other document types
    has_journal_entry = "journal_entry" in document_types
    other_doc_types = [dt for dt in document_types if dt != "journal_entry"]
    
    matching = []
    
    # Step 1: Get matches for non-JE documents using standard logic
    if other_doc_types:
        from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
            check_matching,
            subtract_allocations,
        )
        
        other_matches = check_matching(
            gl_account,
            company,
            transaction,
            other_doc_types,
            from_date,
            to_date,
            filter_by_reference_date,
            from_reference_date,
            to_reference_date,
        )
        # Standard allocation subtraction for non-JE
        other_matches = subtract_allocations(gl_account, other_matches)
        matching.extend(other_matches)
    
    # Step 2: Get JE row-level matches using our custom query
    if has_journal_entry:
        je_row_matches = get_je_row_matches(
            gl_account,
            company,
            transaction,
            from_date,
            to_date,
            filter_by_reference_date,
            from_reference_date,
            to_reference_date,
        )
        # Custom row-level allocation subtraction
        je_row_matches = subtract_je_row_allocations(gl_account, je_row_matches)
        matching.extend(je_row_matches)
    
    # Sort by rank (highest first)
    return sorted(matching, key=lambda x: x.get("rank", 0), reverse=True)


def get_je_row_matches(
    gl_account,
    company,
    transaction,
    from_date,
    to_date,
    filter_by_reference_date,
    from_reference_date,
    to_reference_date,
):
    """
    Returns JE rows as individual matchable entries.
    
    Key difference from standard:
    - Standard groups by JE name → one entry per JE
    - This returns one entry per JE Account row
    
    Uses COALESCE to prefer row-level reference (custom_reference_no),
    falling back to JE header reference (cheque_no) if row reference is empty.
    """
    cr_or_dr = "credit" if transaction.withdrawal > 0.0 else "debit"
    je = frappe.qb.DocType("Journal Entry")
    jea = frappe.qb.DocType("Journal Entry Account")
    
    amount_field = f"{cr_or_dr}_in_account_currency"
    
    # Date filter
    if from_date and to_date:
        filter_by_date = je.posting_date.between(from_date, to_date)
        if cint(filter_by_reference_date):
            filter_by_date = je.cheque_date.between(from_reference_date, to_reference_date)
    else:
        filter_by_date = je.posting_date.isnotnull()
    
    # Use row reference if available, fallback to JE cheque_no
    # COALESCE returns first non-null value
    row_reference = Coalesce(jea.custom_reference_no, je.cheque_no)
    
    # Build query - returns each row separately
    query = (
        frappe.qb.from_(jea)
        .join(je)
        .on(jea.parent == je.name)
        .select(
            getattr(jea, amount_field).as_("paid_amount"),
            ConstantColumn("Journal Entry").as_("doctype"),
            je.name.as_("name"),
            jea.name.as_("jea_row_name"),           # Row identifier (standard Frappe field)
            row_reference.as_("reference_no"),      # Row-level or header reference
            je.cheque_date.as_("reference_date"),
            je.pay_to_recd_from.as_("party"),
            jea.party_type,
            je.posting_date,
            jea.account_currency.as_("currency"),
        )
        .where(je.docstatus == 1)
        .where(je.voucher_type != "Opening Entry")
        .where(je.clearance_date.isnull())
        .where(jea.account == gl_account)
        .where(getattr(jea, amount_field) > 0)
        .where(filter_by_date)
        .orderby(je.cheque_date if cint(filter_by_reference_date) else je.posting_date)
    )
    
    # For auto-reconcile: require reference match
    if frappe.flags.auto_reconcile_vouchers is True:
        query = query.where(row_reference == transaction.reference_number)
    
    results = query.run(as_dict=True)
    
    # Calculate ranking for each result
    for row in results:
        rank = 1  # Base rank
        
        # +1 if reference matches
        if row.get("reference_no") == transaction.reference_number:
            rank += 1
        
        # +1 if amount matches
        if flt(row.get("paid_amount")) == flt(transaction.unallocated_amount):
            rank += 1
        
        # +1 if party matches
        if (row.get("party_type") == transaction.party_type and 
            row.get("party") == transaction.party and 
            transaction.party):
            rank += 1
            
        row["rank"] = rank
    
    return results


def subtract_je_row_allocations(gl_account, vouchers):
    """
    Subtract already-allocated amounts at ROW level for JE entries.
    
    Standard function subtracts at document level:
        JE-001 has $15,000 allocated → subtract from total
    
    This subtracts at row level:
        JE-001, Row abc123 has $5,000 allocated → subtract only from that row
        JE-001, Row def456 has $0 allocated → full amount available
    """
    if not vouchers:
        return []
    
    # Get all JE row identifiers to check
    je_row_names = [v.get("jea_row_name") for v in vouchers if v.get("jea_row_name")]
    je_names = list(set(v.get("name") for v in vouchers))
    
    # Query existing allocations BY ROW (where custom_je_row_name is set)
    row_allocations = {}
    if je_row_names:
        allocations = frappe.db.sql(
            """
            SELECT 
                btp.payment_entry,
                btp.custom_je_row_name,
                SUM(btp.allocated_amount) as total_allocated,
                ba.account as gl_account
            FROM `tabBank Transaction Payments` btp
            JOIN `tabBank Transaction` bt ON bt.name = btp.parent
            JOIN `tabBank Account` ba ON ba.name = bt.bank_account
            WHERE 
                btp.payment_document = 'Journal Entry'
                AND btp.custom_je_row_name IS NOT NULL
                AND btp.custom_je_row_name != ''
                AND bt.docstatus = 1
            GROUP BY btp.payment_entry, btp.custom_je_row_name, ba.account
            """,
            as_dict=True
        )
        
        for alloc in allocations:
            key = (alloc.payment_entry, alloc.custom_je_row_name, alloc.gl_account)
            row_allocations[key] = flt(alloc.total_allocated)
    
    # Also get document-level allocations for JEs WITHOUT row tracking
    # (for backward compatibility with old reconciliations)
    doc_allocations = {}
    if je_names:
        doc_allocs = frappe.db.sql(
            """
            SELECT 
                btp.payment_entry,
                SUM(btp.allocated_amount) as total_allocated,
                ba.account as gl_account
            FROM `tabBank Transaction Payments` btp
            JOIN `tabBank Transaction` bt ON bt.name = btp.parent
            JOIN `tabBank Account` ba ON ba.name = bt.bank_account
            WHERE 
                btp.payment_document = 'Journal Entry'
                AND (btp.custom_je_row_name IS NULL OR btp.custom_je_row_name = '')
                AND btp.payment_entry IN %(je_names)s
                AND bt.docstatus = 1
            GROUP BY btp.payment_entry, ba.account
            """,
            {"je_names": je_names},
            as_dict=True
        )
        
        for alloc in doc_allocs:
            key = (alloc.payment_entry, alloc.gl_account)
            doc_allocations[key] = flt(alloc.total_allocated)
    
    # Subtract allocations from each voucher
    result = []
    for voucher in vouchers:
        je_name = voucher.get("name")
        row_name = voucher.get("jea_row_name")
        paid_amount = flt(voucher.get("paid_amount"))
        
        # Check for row-level allocation first
        row_key = (je_name, row_name, gl_account)
        if row_key in row_allocations:
            paid_amount -= flt(row_allocations[row_key])
        
        # Note: We don't subtract document-level allocations from row-level entries
        # because that would double-count. Document-level allocations are for
        # JEs reconciled before this customization was applied.
        
        voucher["paid_amount"] = paid_amount
        
        # Only include if there's remaining amount
        if paid_amount > 0:
            result.append(voucher)
    
    return result


@frappe.whitelist()
def custom_reconcile_vouchers(bank_transaction_name, vouchers):
    """
    Custom reconcile that stores JE row identifier.
    
    Voucher format expected:
    {
        "payment_doctype": "Journal Entry",
        "payment_name": "JE-PAYROLL-001",
        "amount": 5000,
        "jea_row_name": "abc123xyz"  ← Row identifier (optional)
    }
    """
    vouchers = json.loads(vouchers)
    transaction = frappe.get_doc("Bank Transaction", bank_transaction_name)
    
    if 0.0 >= transaction.unallocated_amount:
        frappe.throw(_("Bank Transaction {0} is already fully reconciled").format(transaction.name))
    
    # Track how much remains to allocate across pre-set JE rows
    remaining = flt(transaction.unallocated_amount)

    # Add payment entries with row tracking
    for voucher in vouchers:
        entry_data = {
            "payment_document": voucher.get("payment_doctype"),
            "payment_entry": voucher.get("payment_name"),
            "allocated_amount": 0.0,
        }
        
        if voucher.get("payment_doctype") == "Journal Entry" and voucher.get("jea_row_name"):
            entry_data["custom_je_row_name"] = voucher.get("jea_row_name")
            # Pre-set allocated_amount for row-tracked JE entries.
            #
            # Standard allocate_payment_entries() calls get_clearance_details() which
            # does gl_entries.pop(bank_account) on the inner dict returned by
            # get_related_bank_gl_entries().  That inner dict is the SAME object for
            # every row of the same JE, so the first call empties it and the second
            # call sees an empty dict → "not affecting bank account" error.
            #
            # allocate_payment_entries() skips rows where allocated_amount != 0,
            # so pre-setting the amount here bypasses the broken path entirely.
            # This also correctly handles the "split" case where two rows of the
            # same JE sum to the bank transaction amount.
            row_amount = flt(voucher.get("amount", 0))
            entry_data["allocated_amount"] = min(row_amount, remaining)
            remaining = flt(remaining - entry_data["allocated_amount"])
        
        transaction.append("payment_entries", entry_data)
    
    # Validate no duplicate (doctype, name, row) tuples
    # NOTE: validate_je_row_duplicates is also a before_validate hook which
    # replaces doc.validate_duplicate_references on the instance, so the
    # standard ERPNext validate() will use our row-aware version automatically.
    # We call it here explicitly to get early feedback before allocate_payment_entries.
    validate_je_row_duplicates(transaction)
    # Handles any non-JE entries (allocated_amount == 0) via standard logic;
    # pre-set JE rows are skipped by allocate_payment_entries.
    transaction.allocate_payment_entries()
    transaction.update_allocated_amount()
    transaction.set_status()
    transaction.save()
    
    return transaction


def validate_je_row_duplicates(doc, method=None):
    """
    Override duplicate check to allow same JE with different rows.

    Registered as a `before_validate` hook on Bank Transaction.

    The standard ERPNext `validate_duplicate_references` uses (doctype, name) as
    the key, so two rows for the same JE (even with different jea_row_names) would
    fail.  We replace that method on the doc *instance* here so that when the
    standard `validate()` calls `self.validate_duplicate_references()` it runs our
    row-aware version instead.
    """
    def _row_aware_duplicate_check():
        if not doc.payment_entries:
            return

        references = set()
        for row in doc.payment_entries:
            if row.payment_document == "Journal Entry" and row.get("custom_je_row_name"):
                # For JE with row tracking: use (doctype, name, row)
                reference = (row.payment_document, row.payment_entry, row.custom_je_row_name)
            else:
                # For other documents: use standard (doctype, name)
                reference = (row.payment_document, row.payment_entry, None)

            if reference in references:
                if reference[2]:  # Has row name
                    frappe.throw(
                        _("{0} {1} (Row {2}) is allocated twice in this Bank Transaction").format(
                            row.payment_document, row.payment_entry, row.custom_je_row_name
                        )
                    )
                else:
                    frappe.throw(
                        _("{0} {1} is allocated twice in this Bank Transaction").format(
                            row.payment_document, row.payment_entry
                        )
                    )
            references.add(reference)

    # Replace the standard method on this instance so the standard validate()
    # calls our row-aware version instead of the (doctype, name)-only version.
    doc.validate_duplicate_references = _row_aware_duplicate_check


@frappe.whitelist()
def custom_auto_reconcile_vouchers(
    bank_account,
    from_date=None,
    to_date=None,
    filter_by_reference_date=None,
    from_reference_date=None,
    to_reference_date=None,
):
    """
    Custom auto-reconcile that uses row-level JE matching.
    
    This replaces the standard auto_reconcile_vouchers to use our custom
    get_linked_payments and reconcile_vouchers functions.
    """
    from frappe.utils import create_batch
    from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
        get_bank_transactions,
    )
    
    bank_transactions = get_bank_transactions(bank_account)

    if len(bank_transactions) > 10:
        for bank_transaction_batch in create_batch(bank_transactions, 1000):
            frappe.enqueue(
                method="acc_egypt_cust.overrides.bank_reconciliation.custom_start_auto_reconcile",
                queue="long",
                bank_transactions=bank_transaction_batch,
                from_date=from_date,
                to_date=to_date,
                filter_by_reference_date=filter_by_reference_date,
                from_reference_date=from_reference_date,
                to_reference_date=to_reference_date,
            )
        frappe.msgprint(_("Auto Reconciliation has started in the background"))
    else:
        custom_start_auto_reconcile(
            bank_transactions,
            from_date,
            to_date,
            filter_by_reference_date,
            from_reference_date,
            to_reference_date,
        )


def custom_start_auto_reconcile(
    bank_transactions, from_date, to_date, filter_by_reference_date, from_reference_date, to_reference_date
):
    """
    Custom auto-reconcile loop that:
    1. Uses our custom_get_linked_payments (with row-level JE matching)
    2. Includes jea_row_name in voucher data
    3. Calls our custom_reconcile_vouchers
    """
    from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
        get_auto_reconcile_message,
    )
    
    frappe.flags.auto_reconcile_vouchers = True

    reconciled, partially_reconciled = set(), set()
    for transaction in bank_transactions:
        # Use our custom function instead of standard get_linked_payments
        linked_payments = custom_get_linked_payments(
            transaction.name,
            ["payment_entry", "journal_entry", "sales_invoice"],
            from_date,
            to_date,
            filter_by_reference_date,
            from_reference_date,
            to_reference_date,
        )

        if not linked_payments:
            continue

        # Include jea_row_name for JE entries (this is the key difference!)
        vouchers = list(
            map(
                lambda entry: {
                    "payment_doctype": entry.get("doctype"),
                    "payment_name": entry.get("name"),
                    "amount": entry.get("paid_amount"),
                    "jea_row_name": entry.get("jea_row_name"),  # Include row identifier
                },
                linked_payments,
            )
        )

        # Use our custom reconcile function
        updated_transaction = custom_reconcile_vouchers(transaction.name, json.dumps(vouchers))

        if updated_transaction.status == "Reconciled":
            reconciled.add(updated_transaction.name)
        elif flt(transaction.unallocated_amount) != flt(updated_transaction.unallocated_amount):
            # Partially reconciled (status = Unreconciled & unallocated amount changed)
            partially_reconciled.add(updated_transaction.name)

    alert_message, indicator = get_auto_reconcile_message(partially_reconciled, reconciled)
    frappe.msgprint(title=_("Auto Reconciliation"), msg=alert_message, indicator=indicator)

    frappe.flags.auto_reconcile_vouchers = False


@frappe.whitelist(allow_guest=False)
def download_bank_transaction_template():
    """Return an xlsx template file for Bank Transaction import."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        frappe.throw(_("openpyxl is required. Run: bench pip install openpyxl"))

    columns = ["Date", "Deposit", "Withdraw", "Description", "Reference Number", "Bank Account"]
    col_widths = [15, 15, 15, 35, 25, 35]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Bank Transactions"
    ws.append(columns)

    header_font = Font(bold=True)
    header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    for col_idx, cell in enumerate(ws[1], start=1):
        cell.font = header_font
        cell.fill = header_fill
        ws.column_dimensions[cell.column_letter].width = col_widths[col_idx - 1]

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    frappe.local.response.filename = "bank_transaction_template.xlsx"
    frappe.local.response.filecontent = buf.read()
    frappe.local.response.type = "download"
    frappe.local.response.content_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@frappe.whitelist(allow_guest=False)
def upload_bank_transactions(file_url, bank_account=None):
    """
    Parse an xlsx file and create submitted Bank Transaction docs.

    Expected columns (case-insensitive):
        Date, Deposit, Withdraw, Description, Reference Number, Bank Account
    """
    try:
        import openpyxl
    except ImportError:
        frappe.throw(_("openpyxl is required. Run: bench pip install openpyxl"))

    import datetime

    file_doc = frappe.get_doc("File", {"file_url": file_url})
    file_path = frappe.get_site_path(file_doc.file_url.lstrip("/"))

    with open(file_path, "rb") as f:
        content = f.read()

    wb = openpyxl.load_workbook(filename=io.BytesIO(content), data_only=True)
    ws = wb.active

    # Read header row — normalise to lower-case with no extra spaces
    headers = [
        str(cell.value).strip().lower() if cell.value is not None else ""
        for cell in ws[1]
    ]

    # Flexible column aliases
    col_aliases = {
        "date": ["date"],
        "deposit": ["deposit"],
        "withdrawal": ["withdraw", "withdrawal"],
        "description": ["description", "desc"],
        "reference_number": [
            "reference number", "reference_number",
            "reference no", "reference_no",
            "ref no", "ref_no", "ref",
        ],
        "bank_account": ["bank account", "bank_account"],
    }

    col_indices = {}
    for field, aliases in col_aliases.items():
        for i, h in enumerate(headers):
            if h in aliases:
                col_indices[field] = i
                break

    if "date" not in col_indices:
        frappe.throw(_("Required column 'Date' not found in the uploaded file."))

    created = 0
    errors = []

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(v is not None and str(v).strip() != "" for v in row):
            continue

        def get_col(field):
            idx = col_indices.get(field)
            return row[idx] if idx is not None and idx < len(row) else None

        # --- Date ---
        date_val = get_col("date")
        if not date_val:
            errors.append(_("Row {0}: Date is missing — skipped.").format(row_idx))
            continue

        if isinstance(date_val, (datetime.datetime, datetime.date)):
            posting_date = date_val.date() if isinstance(date_val, datetime.datetime) else date_val
        else:
            try:
                posting_date = getdate(str(date_val).strip())
            except Exception:
                errors.append(_("Row {0}: Invalid date '{1}' — skipped.").format(row_idx, date_val))
                continue

        # --- Amounts ---
        deposit = flt(get_col("deposit") or 0)
        withdrawal = flt(get_col("withdrawal") or 0)

        if deposit == 0 and withdrawal == 0:
            errors.append(
                _("Row {0}: Both Deposit and Withdraw are zero or empty — skipped.").format(row_idx)
            )
            continue

        # --- Other fields ---
        description = str(get_col("description") or "").strip()
        reference_number = str(get_col("reference_number") or "").strip()
        row_bank_account = str(get_col("bank_account") or "").strip()
        final_bank_account = row_bank_account or bank_account

        if not final_bank_account:
            errors.append(
                _("Row {0}: Bank Account is missing — skipped.").format(row_idx)
            )
            continue

        try:
            bt = frappe.new_doc("Bank Transaction")
            bt.date = posting_date
            bt.deposit = deposit
            bt.withdrawal = withdrawal
            bt.description = description
            bt.reference_number = reference_number
            bt.bank_account = final_bank_account
            bt.insert(ignore_permissions=True)
            bt.submit()
            created += 1
        except Exception as e:
            errors.append(_("Row {0}: {1}").format(row_idx, str(e)))

    return {"created": created, "errors": errors}


def get_bank_transaction_entries_for_reconciliation_statement(filters):
    """
    Get unreconciled Bank Transaction entries for Bank Reconciliation Statement report.
    
    This function is called via hook: get_entries_for_bank_reconciliation_statement
    
    Returns Bank Transactions that:
    - Are submitted (docstatus=1)
    - Have status 'Pending' or 'Unreconciled'
    - Have date <= report_date
    - Have unallocated_amount > 0
    """
    import frappe
    frappe.logger().info(f"HOOK CALLED: get_bank_transaction_entries_for_reconciliation_statement with filters: {filters}")
    
    # Find the Bank Account linked to this GL Account
    bank_account = frappe.db.get_value(
        "Bank Account",
        {"account": filters.get("account"), "is_company_account": 1},
        "name"
    )
    
    frappe.logger().info(f"HOOK: bank_account = {bank_account}")
    
    if not bank_account:
        frappe.logger().info("HOOK: No bank_account found, returning []")
        return []
    
    result = frappe.db.sql(
        """
        SELECT
            'Bank Transaction' as payment_document,
            bt.date as posting_date,
            bt.name as payment_entry,
            bt.deposit as debit,
            bt.withdrawal as credit,
            bt.description as against_account,
            bt.reference_number as reference_no,
            bt.date as ref_date,
            bt.description as description,
            NULL as clearance_date,
            bt.currency as account_currency
        FROM `tabBank Transaction` bt
        WHERE bt.bank_account = %(bank_account)s
            AND bt.docstatus = 1
            AND bt.status IN ('Pending', 'Unreconciled')
            AND bt.date <= %(report_date)s
            AND bt.unallocated_amount > 0
        ORDER BY bt.date ASC
        """,
        {"bank_account": bank_account, "report_date": filters.get("report_date")},
        as_dict=1,
    )
    
    frappe.logger().info(f"HOOK: Returning {len(result)} Bank Transaction entries")
    return result
