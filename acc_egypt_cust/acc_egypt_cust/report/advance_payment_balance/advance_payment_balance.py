import frappe


def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {"label": "Party Type", "fieldname": "party_type", "fieldtype": "Data", "width": 120},
        {"label": "Party", "fieldname": "party", "fieldtype": "Dynamic Link", "options": "party_type", "width": 180},
        {"label": "Advance Account", "fieldname": "advance_account", "fieldtype": "Link", "options": "Account", "width": 220},
        {"label": "Received / Paid", "fieldname": "received", "fieldtype": "Currency", "width": 150},
        {"label": "Used Advances", "fieldname": "used", "fieldtype": "Currency", "width": 150},
        {"label": "Balance", "fieldname": "balance", "fieldtype": "Currency", "width": 150},
    ]


def get_default_advance_account(company, party_type):
    if not company:
        return None

    if party_type == "Customer":
        return frappe.db.get_value("Company", company, "default_receivable_account")
    else:
        return frappe.db.get_value("Company", company, "default_payable_account")


def get_data(filters):

    conditions = ["pe.docstatus = 1"]

    # -------------------------
    # PARTY TYPE FILTER (IMPORTANT)
    # -------------------------
    if filters.get("party_type"):
        conditions.append("pe.party_type = %(party_type)s")

        if filters.get("party_type") == "Customer":
            conditions.append("pe.payment_type = 'Receive'")
        elif filters.get("party_type") == "Supplier":
            conditions.append("pe.payment_type = 'Pay'")
    else:
        # both types
        conditions.append("(pe.payment_type IN ('Receive', 'Pay'))")

    if filters.get("company"):
        conditions.append("pe.company = %(company)s")

    if filters.get("party"):
        conditions.append("pe.party = %(party)s")

    if filters.get("from_date"):
        conditions.append("pe.posting_date >= %(from_date)s")

    if filters.get("to_date"):
        conditions.append("pe.posting_date <= %(to_date)s")

    where_clause = " AND ".join(conditions)

    # -------------------------
    # 1. ADVANCE RECEIVED / PAID
    # -------------------------
    received_data = frappe.db.sql(f"""
        SELECT
            pe.party_type,
            pe.party,
            SUM(pe.paid_amount) as received
        FROM `tabPayment Entry` pe
        WHERE {where_clause}
        GROUP BY pe.party_type, pe.party
    """, filters, as_dict=True)

    # -------------------------
    # 2. USED ADVANCES
    # -------------------------
    used_data = frappe.db.sql(f"""
        SELECT
            pe.party_type,
            pe.party,
            SUM(per.allocated_amount) as used
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
        WHERE pe.docstatus = 1
        AND {where_clause}
        GROUP BY pe.party_type, pe.party
    """, filters, as_dict=True)

    # -------------------------
    # MAP USED
    # -------------------------
    used_map = {}
    for d in used_data:
        key = (d.party_type, d.party)
        used_map[key] = d.used or 0

    # -------------------------
    # FINAL RESULT
    # -------------------------
    result = []

    for r in received_data:
        key = (r.party_type, r.party)

        received_amt = r.received or 0
        used_amt = used_map.get(key, 0)

        advance_account = get_default_advance_account(
            filters.get("company"),
            r.party_type
        )

        result.append({
            "party_type": r.party_type,
            "party": r.party,
            "advance_account": advance_account,
            "received": received_amt,
            "used": used_amt,
            "balance": received_amt - used_amt
        })

    return result