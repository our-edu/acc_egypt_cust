import frappe


def execute():
    """Journal Entries cancelled from code (e.g. depreciation entries cancelled with their
    Asset) kept their submitted workflow state. Set them to the workflow's cancelled state."""
    workflow = frappe.db.get_value("Workflow", {"document_type": "Journal Entry", "is_active": 1}, "name")
    if not workflow:
        return

    field = frappe.db.get_value("Workflow", workflow, "workflow_state_field")
    cancelled_state = frappe.db.get_value(
        "Workflow Document State", {"parent": workflow, "doc_status": "2"}, "state", order_by="idx asc"
    )
    if not cancelled_state:
        return

    frappe.db.sql(
        f"""update `tabJournal Entry` set `{field}` = %s
        where docstatus = 2 and ifnull(`{field}`, '') != %s""",
        (cancelled_state, cancelled_state),
    )
