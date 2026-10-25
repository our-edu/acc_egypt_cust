import frappe
from frappe import _


def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 150},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 200},
        {"label": _("Asset ID"), "fieldname": "asset", "fieldtype": "Link", "options": "Asset", "width": 170},
        {"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Data", "width": 220},
        {"label": _("Serial No."), "fieldname": "serial_no", "fieldtype": "Data", "width": 160},
        {"label": _("Date of Movement"), "fieldname": "movement_date", "fieldtype": "Date", "width": 140},
    ]


def get_data(filters):
    # An asset is in an employee's custody when it's submitted, not disposed
    # of, and its custodian is set to that employee.
    conditions = [
        "a.docstatus = 1",
        "a.custodian IS NOT NULL",
        "a.custodian != ''",
        "a.status NOT IN ('Scrapped', 'Sold', 'Capitalized')",
    ]

    if filters.get("company"):
        conditions.append("a.company = %(company)s")

    if filters.get("employee"):
        conditions.append("a.custodian = %(employee)s")

    if filters.get("asset"):
        conditions.append("a.name = %(asset)s")

    where_clause = " AND ".join(conditions)

    # Date of movement = the latest submitted Asset Movement that handed
    # the asset to its current custodian.
    return frappe.db.sql(f"""
        SELECT
            a.custodian AS employee,
            e.employee_name,
            a.name AS asset,
            a.asset_name,
            a.custom_serial_no AS serial_no,
            (
                SELECT MAX(am.transaction_date)
                FROM `tabAsset Movement Item` ami
                INNER JOIN `tabAsset Movement` am ON am.name = ami.parent
                WHERE am.docstatus = 1
                    AND ami.asset = a.name
                    AND ami.to_employee = a.custodian
            ) AS movement_date
        FROM `tabAsset` a
        LEFT JOIN `tabEmployee` e ON e.name = a.custodian
        WHERE {where_clause}
        ORDER BY e.employee_name, a.custodian, a.name
    """, filters, as_dict=True)
