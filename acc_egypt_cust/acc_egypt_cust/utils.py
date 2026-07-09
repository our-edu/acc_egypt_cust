import frappe
from frappe import _
from frappe.utils import flt, getdate, get_time, now


# ---------------------------------------------------------------------------
# HR Settings helpers (copied from hr_cust.hr_cust.utils)
# ---------------------------------------------------------------------------

def get_ouredu_hr_settings(company):
    if settings := frappe.db.exists("OurEdu HR Setting", {"company": company}):
        return frappe.get_doc("OurEdu HR Setting", settings)
    return {}


def create_additional_salary(**kwargs):
    """Create and submit an Additional Salary document."""
    additional_salary = frappe.new_doc("Additional Salary")
    additional_salary.employee = kwargs.get("employee")
    additional_salary.payroll_date = kwargs.get("posting_date", now())
    additional_salary.amount = kwargs.get("amount", 0)
    additional_salary.salary_component = kwargs.get("salary_component")
    additional_salary.ref_doctype = kwargs.get("ref_doctype")
    additional_salary.ref_docname = kwargs.get("ref_docname")
    additional_salary.overwrite_salary_structure_amount = 0
    additional_salary.save(ignore_permissions=True)
    additional_salary.submit()
    return additional_salary


def get_employee_daily_rate_from_salary_structure(employee, date):
    """Return daily_rate from the submitted SSA effective on the given date."""
    if not employee or not date:
        return 0.0

    on_date = getdate(date)
    assignments = frappe.get_all(
        "Salary Structure Assignment",
        filters={
            "employee": employee,
            "docstatus": 1,
            "from_date": ["<=", on_date],
        },
        fields=["name", "daily_rate", "base", "to_date"],
        order_by="from_date desc, creation desc",
    )

    for assignment in assignments:
        if assignment.to_date and getdate(assignment.to_date) < on_date:
            continue
        if assignment.daily_rate:
            return flt(assignment.daily_rate)
        if assignment.base:
            return flt(assignment.base) / 30.0
        return 0.0

    return 0.0


@frappe.whitelist()
def get_daily_employee_rate_components(employee, date, components=None):
    """Returns daily employee rate based on specified salary components."""
    from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip

    salary_structure = frappe.db.get_value(
        "Salary Structure Assignment",
        {"employee": employee, "from_date": ["<=", date]},
        "salary_structure",
    )
    if not salary_structure:
        return 0.0

    salary_slip = make_salary_slip(salary_structure, employee=employee, posting_date=date)

    if components:
        component_amount = sum(
            data.amount
            for data in salary_slip.earnings
            if data.salary_component in components and not data.get("additional_salary")
        )
    else:
        component_amount = sum(
            data.amount
            for data in salary_slip.earnings
            if not data.get("additional_salary")
        )

    payment_days = 30
    return component_amount / payment_days


def get_employee_daily_rate(employee, date, components=None):
    daily_rate = get_employee_daily_rate_from_salary_structure(employee, date)
    if daily_rate:
        return daily_rate
    daily_rate = get_daily_employee_rate_components(employee, date, components)
    if daily_rate:
        return daily_rate
    return 0.0


# ---------------------------------------------------------------------------
# Attendance Exception helper
# (copied from hr_cust.hr_cust.doctype.attendance_exception.attendance_exception)
# ---------------------------------------------------------------------------

def employee_has_attendance_exception_on_date(employee: str, attendance_date) -> bool:
    """True if a non-cancelled Attendance Exception covers attendance_date for this employee."""
    if not employee:
        return False
    d = getdate(attendance_date)
    rows = frappe.get_all(
        "Attendance Exception",
        filters={
            "employee": employee,
            "from_date": ("<=", d),
            "docstatus": ("<", 2),
        },
        or_filters=[["to_date", "is", "not set"], ["to_date", ">=", d]],
        limit=1,
        pluck="name",
    )
    return bool(rows)


# ---------------------------------------------------------------------------
# Shift Type timing helpers
# (copied from hr_cust.override.shift_assignment)
# ---------------------------------------------------------------------------

def _use_shift_schedule_column_available() -> bool:
    """True only when Shift Type has the use_shift_schedule field (DB migrated)."""
    try:
        return bool(frappe.db and frappe.db.has_column("Shift Type", "use_shift_schedule"))
    except Exception:
        return False


def get_shift_type_timing(shift_types, for_date=None):
    """
    Get shift type timing map, supporting weekday-specific times when the
    use_shift_schedule column exists (hr_cust Shift Type Schedule feature).
    Falls back to the standard hrms implementation when the column is absent.
    """
    from hrms.hr.doctype.shift_assignment.shift_assignment import (
        get_shift_type_timing as original_get_shift_type_timing,
    )

    if not _use_shift_schedule_column_available():
        return original_get_shift_type_timing(shift_types)

    shift_timing_map = {}
    data = frappe.get_all(
        "Shift Type",
        filters={"name": ("IN", shift_types)},
        fields=["name", "start_time", "end_time", "use_shift_schedule"],
    )

    schedule_map = {}
    if for_date:
        date_obj = getdate(for_date)
        weekday_name = date_obj.strftime("%A")
        schedules = []
        try:
            if frappe.db.exists("DocType", "Shift Type Schedule"):
                schedules = frappe.get_all(
                    "Shift Type Schedule",
                    filters={
                        "parent": ("IN", shift_types),
                        "parenttype": "Shift Type",
                        "week_day": weekday_name,
                    },
                    fields=["parent", "start_time", "end_time"],
                )
        except Exception:
            pass

        for s in schedules:
            if s.get("start_time") and s.get("end_time"):
                start_time_val = get_time(s["start_time"])
                end_time_val = get_time(s["end_time"])
                if start_time_val != get_time("00:00:00") and end_time_val != get_time("00:00:00"):
                    schedule_map[s["parent"]] = s

    for d in data:
        shift_timing_map[d.name] = d.copy()
        if d.get("use_shift_schedule") and for_date and d.name in schedule_map:
            schedule = schedule_map[d.name]
            shift_timing_map[d.name]["start_time"] = schedule["start_time"]
            shift_timing_map[d.name]["end_time"] = schedule["end_time"]

    return shift_timing_map
