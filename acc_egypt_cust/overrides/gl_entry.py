
import frappe

def validate(doc, method=None):
    if doc.voucher_type == "Journal Entry":
        # Fetch the parent Journal Entry
        je = frappe.get_doc("Journal Entry", doc.voucher_no)
        
        # Find the corresponding account row
        for row in je.accounts:
            # Match by account and amount (debit/credit)
            if (row.account == doc.account and
                ((row.debit and row.debit == doc.debit) or
                 (row.credit and row.credit == doc.credit))):
                
                # Copy the remark from Journal Entry account row
                doc.remarks = row.user_remark or ""
                break  # found the matching row, no need to continue