import frappe
import os
import json
from frappe.utils import getdate, today, nowdate


def after_migrate():
    add_general_ledger_total_row()
    sync_custom_fields()


def add_general_ledger_total_row():
    if frappe.db.exists("Report", "General Ledger"):
        frappe.db.set_value("Report", "General Ledger", "add_total_row", 0, update_modified=False)


def sync_custom_fields():
    """Sync custom fields from JSON files in acc_cust/custom/ directory"""
    custom_dir = os.path.join(os.path.dirname(__file__), "acc_cust", "custom")
    
    if not os.path.exists(custom_dir):
        return
    
    for filename in os.listdir(custom_dir):
        if not filename.endswith(".json"):
            continue
        
        filepath = os.path.join(custom_dir, filename)
        
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            
            if not data.get("sync_on_migrate"):
                continue
            
            doctype = data.get("doctype")
            if not doctype:
                continue
            
            # Sync custom fields
            for cf in data.get("custom_fields", []):
                existing = frappe.db.exists("Custom Field", {
                    "dt": doctype,
                    "fieldname": cf.get("fieldname")
                })
                
                if not existing:
                    custom_field = frappe.new_doc("Custom Field")
                    custom_field.dt = doctype
                    custom_field.update(cf)
                    custom_field.insert(ignore_permissions=True)
                    frappe.db.commit()
                    print(f"Created custom field {cf.get('fieldname')} for {doctype}")
            
            # Sync property setters
            for ps in data.get("property_setters", []):
                if ps.get("name"):
                    existing = frappe.db.exists("Property Setter", ps.get("name"))
                    if not existing:
                        property_setter = frappe.new_doc("Property Setter")
                        property_setter.update(ps)
                        property_setter.insert(ignore_permissions=True)
                        frappe.db.commit()
                        
        except Exception as e:
            print(f"Error syncing {filename}: {str(e)}")


def send_renewal_notifications():
    """Daily scheduled task to send notifications for upcoming and overdue renewals."""
    current_date = getdate(today())

    documents = frappe.get_all(
        "Official Document",
        filters={"next_renewal_date": ["is", "set"]},
        fields=["name", "document_name", "next_renewal_date", "notify_days_before", "notify_days_after"],
    )

    for doc in documents:
        next_renewal = getdate(doc.next_renewal_date)
        days_until_renewal = (next_renewal - current_date).days

        notification_users = frappe.get_all(
            "Official Document Notification User",
            filters={"parent": doc.name, "parenttype": "Official Document"},
            fields=["user"],
        )

        if not notification_users:
            continue

        recipients = [row.user for row in notification_users]

        # Notify before renewal
        if doc.notify_days_before and days_until_renewal == doc.notify_days_before:
            subject = f"Upcoming Renewal: {doc.document_name} due in {doc.notify_days_before} days"
            message = (
                f"The document <b>{doc.document_name}</b> ({doc.name}) "
                f"is due for renewal on <b>{doc.next_renewal_date}</b>, "
                f"which is <b>{doc.notify_days_before} day(s)</b> from now. "
                f"Please prepare the necessary renewal documents."
            )
            if not _already_notified_today(doc.name, "Upcoming Renewal"):
                _send_notification(doc.name, subject, message, recipients)

        # Notify after renewal date passed (overdue)
        if doc.notify_days_after and days_until_renewal == -doc.notify_days_after:
            subject = f"Overdue Renewal: {doc.document_name} was due {doc.notify_days_after} days ago"
            message = (
                f"The document <b>{doc.document_name}</b> ({doc.name}) "
                f"was due for renewal on <b>{doc.next_renewal_date}</b>, "
                f"which was <b>{doc.notify_days_after} day(s)</b> ago. "
                f"Please renew it immediately."
            )
            if not _already_notified_today(doc.name, "Overdue Renewal"):
                _send_notification(doc.name, subject, message, recipients)


def _already_notified_today(doc_name, notification_type):
    """Check if a notification of this type was already sent today for this document."""
    return frappe.db.exists("Notification Log", {
        "document_type": "Official Document",
        "document_name": doc_name,
        "subject": ["like", f"{notification_type}:%"],
        "creation": [">=", f"{nowdate()} 00:00:00"],
    })


def _send_notification(doc_name, subject, message, recipients):
    """Send system notification and email to the specified recipients."""
    for user in recipients:
        notification = frappe.new_doc("Notification Log")
        notification.subject = subject
        notification.email_content = message
        notification.for_user = user
        notification.type = "Alert"
        notification.document_type = "Official Document"
        notification.document_name = doc_name
        notification.insert(ignore_permissions=True)

    try:
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=message,
            reference_doctype="Official Document",
            reference_name=doc_name,
        )
    except Exception:
        frappe.log_error("Official Document: Failed to send renewal email")

@frappe.whitelist()
def reopen_cancelled_journal_entries(names):

    if isinstance(names, str):
        import json
        names = json.loads(names)

    if not names:
        return

    # validate all are cancelled
    invalid = frappe.get_all(
        "Journal Entry",
        filters={
            "name": ["in", names],
            "docstatus": ["!=", 2]
        },
        pluck="name"
    )

    if invalid:
        frappe.throw(
            f"These are not cancelled: {', '.join(invalid)}"
        )

    placeholders = ", ".join(["%s"] * len(names))

    frappe.db.sql(f"""
        UPDATE `tabJournal Entry`
        SET docstatus = 0,
        workflow_state = "Pending",
            modified = NOW(),
            modified_by = %s
        WHERE name IN ({placeholders})
    """, [frappe.session.user, *names])

    frappe.db.commit()