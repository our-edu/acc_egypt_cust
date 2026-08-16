import frappe
from frappe import _
from frappe.utils import getdate, today

MAX_MISSED_DATES = 500


@frappe.whitelist()
def get_missed_schedule_dates(auto_repeat):
    """Return past schedule dates for this Auto Repeat that have no document created yet."""
    doc = frappe.get_doc("Auto Repeat", auto_repeat)
    doc.check_permission("write")
    return [d.strftime("%Y-%m-%d") for d in _get_missed_dates(doc)]


@frappe.whitelist()
def create_missed_documents(auto_repeat, dates=None):
    """Create the reference document for past schedule dates that were never generated.

    If `dates` is given (list/JSON list of date strings), only those dates are created,
    otherwise every missed past date is backfilled.
    """
    doc = frappe.get_doc("Auto Repeat", auto_repeat)
    doc.check_permission("write")

    missed_dates = _get_missed_dates(doc)
    if dates:
        selected = {getdate(d) for d in frappe.parse_json(dates)}
        missed_dates = [d for d in missed_dates if d in selected]

    created = []
    failed = []

    for schedule_date in missed_dates:
        try:
            doc.next_schedule_date = schedule_date
            if doc.generate_separate_documents_for_each_assignee and doc.assignee:
                new_docs = doc.make_new_documents()
            else:
                new_docs = doc.make_new_document([assignee.user for assignee in doc.assignee])
            new_docs = new_docs if isinstance(new_docs, list) else [new_docs]
            created.extend(d.name for d in new_docs)
            # commit after every successful document so a later failure only
            # rolls back its own partial work, not previously created documents
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(
                title=_("Auto Repeat {0}: failed to create document for missed schedule date {1}").format(
                    doc.name, schedule_date
                )
            )
            failed.append(str(schedule_date))

    return {"created": created, "failed": failed}


def _get_missed_dates(doc):
    if doc.disabled or not doc.reference_doctype or not doc.reference_document:
        return []

    current_date = getdate(today())
    start_date = getdate(doc.start_date)
    end_date = getdate(doc.end_date) if doc.end_date else None

    past_dates = []
    next_date = doc.get_next_schedule_date(schedule_date=start_date, for_full_schedule=True)
    while getdate(next_date) < current_date:
        if not end_date or getdate(next_date) <= end_date:
            past_dates.append(getdate(next_date))
        if len(past_dates) >= MAX_MISSED_DATES:
            break
        next_date = doc.get_next_schedule_date(schedule_date=next_date, for_full_schedule=True)

    if not past_dates:
        return []

    date_field = _get_reference_date_field(doc.reference_doctype)
    if not date_field:
        return past_dates

    existing = frappe.get_all(
        doc.reference_doctype,
        filters={"auto_repeat": doc.name},
        pluck=date_field,
    )
    existing_dates = {getdate(d) for d in existing if d}

    return [d for d in past_dates if d not in existing_dates]


def _get_reference_date_field(reference_doctype):
    meta = frappe.get_meta(reference_doctype)
    if not meta.get_field("auto_repeat"):
        return None

    for fieldname in ("posting_date", "transaction_date"):
        if meta.get_field(fieldname):
            return fieldname

    for field in meta.fields:
        if field.fieldtype == "Date" and field.reqd:
            return field.fieldname

    return None
