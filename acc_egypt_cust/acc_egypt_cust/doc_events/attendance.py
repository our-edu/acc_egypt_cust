import frappe
from frappe import _
from datetime import datetime, time, timedelta
from frappe.utils import cint, get_datetime, get_link_to_form, getdate, flt, get_time, time_diff_in_hours, add_days
from hrms.hr.doctype.employee_checkin.employee_checkin import (
	mark_attendance_and_link_log,
	update_attendance_in_checkins,
)
from acc_egypt_cust.acc_egypt_cust.utils import (
	employee_has_attendance_exception_on_date,
	get_shift_type_timing,
	create_additional_salary,
	get_employee_daily_rate,
	get_ouredu_hr_settings,
)


def update_submitted_attendance_from_shift_checkins(doc):
	"""
	If submitted Attendance already exists for this check-in's day, recompute
	in_time / out_time / working_hours / flags from all Employee Checkins on that
	calendar day (including offshift and other shifts) and relink them.

	This fixes HRMS behaviour where later check-ins stay ``attendance`` = NULL and get
	``skip_auto_attendance`` when ``mark_attendance_and_link_log`` hits a duplicate
	Attendance validation error.

	Uses ``Shift Type.get_attendance`` (overridden in hr_cust) so
	``get_flexible_minutes_for_attendance`` is applied for late_entry thresholds.
	"""
	if getattr(frappe.flags, "in_install", False) or getattr(frappe.flags, "in_migrate", False):
		return
	if getattr(doc.flags, "skip_sync_attendance_from_checkins", False):
		return
	if not doc.employee or not doc.time:
		return

	attendance_date = (
		getdate(get_datetime(doc.shift_start))
		if doc.shift_start
		else getdate(get_datetime(doc.time))
	)
	if employee_has_attendance_exception_on_date(doc.employee, attendance_date):
		return

	attendance_filters = {
		"employee": doc.employee,
		"attendance_date": attendance_date,
		"docstatus": 1,
	}
	if doc.shift:
		attendance_filters["shift"] = doc.shift
	existing_name = frappe.db.get_value("Attendance", attendance_filters, "name")
	if not existing_name:
		existing_name = frappe.db.get_value(
			"Attendance",
			{"employee": doc.employee, "attendance_date": attendance_date, "docstatus": 1},
			"name",
			order_by="modified desc",
		)
	if not existing_name:
		return

	try:
		attendance_doc = frappe.get_doc("Attendance", existing_name)
		before_snapshot = _attendance_penalty_snapshot(attendance_doc)
		resolved_shift = (
			doc.shift
			or attendance_doc.shift
			or _resolve_checkin_shift(doc.employee, doc.shift)
		)
		shift_doc = (
			frappe.get_doc("Shift Type", attendance_doc.shift)
			if attendance_doc.shift
			else None
		)
		if (
			shift_doc
			and hasattr(shift_doc, "should_mark_attendance")
			and not shift_doc.should_mark_attendance(doc.employee, attendance_date)
		):
			return

		if attendance_doc.status == "Absent":
			ok, _reason = _apply_present_from_checkins_to_attendance(
				attendance_doc,
				force_present=True,
				checkin_shift=resolved_shift,
				add_comment=False,
				ignore_should_mark=True,
			)
			if ok:
				attendance_doc.reload()
				_refresh_attendance_penalties_after_checkin_sync(
					before_snapshot, attendance_doc, "checkin_sync"
				)
				frappe.db.commit()
			return

		log_rows = _get_checkin_rows_for_attendance(
			attendance_doc,
			checkin_shift=resolved_shift,
			include_all_shifts_on_day=True,
		)
		if not log_rows:
			return

		attendance_shift = attendance_doc.shift or resolved_shift
		if not attendance_shift:
			return
		if not shift_doc:
			shift_doc = frappe.get_doc("Shift Type", attendance_shift)

		log_rows = _checkin_logs_for_attendance_shift(
			log_rows, attendance_shift, attendance_doc.attendance_date
		)
		checkin_names = [r.name for r in log_rows]

		(
			attendance_status,
			working_hours,
			late_entry,
			early_exit,
			in_time,
			out_time,
		) = shift_doc.get_attendance(log_rows)

		leave_info = (
			shift_doc._check_leave_record(doc.employee, attendance_date)
			if hasattr(shift_doc, "_check_leave_record")
			else None
		)
		if leave_info:
			attendance_status = leave_info["status"]

		update_fields = {
			"working_hours": working_hours,
			"late_entry": cint(late_entry),
			"early_exit": cint(early_exit),
			"in_time": in_time,
			"out_time": out_time,
			"status": attendance_status,
		}
		if leave_info:
			update_fields["leave_type"] = leave_info.get("leave_type")
			update_fields["leave_application"] = leave_info.get("leave_application")
			if attendance_status == "Half Day":
				update_fields["half_day_status"] = "Present"
				update_fields["modify_half_day_status"] = 0

		frappe.db.set_value("Attendance", existing_name, update_fields, update_modified=False)
		update_attendance_in_checkins(checkin_names, existing_name)

		EmployeeCheckin = frappe.qb.DocType("Employee Checkin")
		(
			frappe.qb.update(EmployeeCheckin)
			.set("skip_auto_attendance", 0)
			.where(EmployeeCheckin.name.isin(checkin_names))
		).run()

		attendance_doc = frappe.get_doc("Attendance", existing_name)
		_refresh_attendance_penalties_after_checkin_sync(
			before_snapshot, attendance_doc, "checkin_sync"
		)
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(
			title=_("Failed to sync Attendance from Employee Checkin"),
			message=f"{doc.name}: {e!s}",
		)


def get_flexible_minutes_for_attendance(doc) -> int:
	"""Active Shift Assignment flexible window for this employee, shift type, and date (0–60)."""
	if not doc.get("employee") or not doc.get("shift") or not doc.get("attendance_date"):
		return 0
	if not frappe.db.has_column("Shift Assignment", "flexible_minutes"):
		return 0
	d = getdate(doc.get("attendance_date"))
	assignments = frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": doc.get("employee"),
			"shift_type": doc.get("shift"),
			"docstatus": 1,
			"status": "Active",
			"start_date": ["<=", d],
		},
		or_filters=[
			["end_date", ">=", d],
			["end_date", "is", "not set"],
		],
		fields=["flexible_minutes"],
		order_by="modified desc",
		limit=1,
	)
	if not assignments:
		return 0
	try:
		return max(0, min(60, int(assignments[0].get("flexible_minutes") or 0)))
	except (TypeError, ValueError):
		return 0


def _shift_span_timedelta(start_dt: datetime, end_dt: datetime) -> timedelta:
	span = end_dt - start_dt
	if span.total_seconds() < 0:
		span += timedelta(days=1)
	return span


def _required_shift_end_datetime(
	converted_in_time: datetime,
	converted_shift_start_time: datetime,
	converted_shift_end_time: datetime,
) -> datetime:
	"""Latest checkout that still counts as full shift hours from actual check-in (compensated flexible arrival)."""
	span = _shift_span_timedelta(converted_shift_start_time, converted_shift_end_time)
	return max(converted_shift_end_time, converted_in_time + span)


def _get_shift_grace_settings(shift_name):
	"""Shift Type late/early marking flags and grace minutes."""
	if not shift_name:
		return {}
	return frappe.db.get_value(
		"Shift Type",
		shift_name,
		(
			"enable_late_entry_marking",
			"late_entry_grace_period",
			"enable_early_exit_marking",
			"early_exit_grace_period",
		),
		as_dict=True,
	) or {}


def _effective_late_grace_minutes(shift_name, flexible_minutes=0):
	"""Grace before late check-in penalties: assignment flexible minutes + Shift Type late grace."""
	grace = cint(flexible_minutes)
	st = _get_shift_grace_settings(shift_name)
	if cint(st.get("enable_late_entry_marking")):
		grace += cint(st.get("late_entry_grace_period"))
	return grace


def _allowed_earliest_checkout(shift_end_time: datetime, shift_name):
	"""Earliest checkout time before early-exit penalty (shift end minus grace when enabled)."""
	st = _get_shift_grace_settings(shift_name)
	if not cint(st.get("enable_early_exit_marking")):
		return shift_end_time
	return shift_end_time - timedelta(minutes=cint(st.get("early_exit_grace_period")))


def _late_penalty_minutes(in_time, shift_start_time, shift_name, flexible_minutes=0):
	"""Minutes late used for penalty tiers: full lateness once grace is exceeded."""
	late_raw = max(0, (in_time - shift_start_time).total_seconds() / 60)
	grace = _effective_late_grace_minutes(shift_name, flexible_minutes)
	if late_raw <= grace:
		return 0
	return late_raw


def _early_penalty_minutes(out_time, shift_end_time, shift_name):
	"""Minutes early used for penalty tiers: full early departure once grace is exceeded."""
	early_raw = max(0, (shift_end_time - out_time).total_seconds() / 60)
	st = _get_shift_grace_settings(shift_name)
	if cint(st.get("enable_early_exit_marking")):
		grace = cint(st.get("early_exit_grace_period"))
		if early_raw <= grace:
			return 0
	return early_raw


def _attendance_additional_salary_exists(attendance_name, salary_component=None):
    """True if a non-cancelled Additional Salary is already linked to this Attendance."""
    filters = {
        "ref_doctype": "Attendance",
        "ref_docname": attendance_name,
        "docstatus": ("<", 2),
    }
    if salary_component:
        filters["salary_component"] = salary_component
    return bool(frappe.db.exists("Additional Salary", filters))


def _has_only_checkin_or_checkout(doc):
    """True when the attendance day has check-in or check-out, but not both."""
    return _has_incomplete_punch(doc)


def _employee_day_checkin_punch_state(employee, attendance_date, shift=None):
	"""Return whether the employee has IN and/or OUT Employee Checkins on the calendar day."""
	if not employee or not attendance_date:
		return False, False

	start_dt = datetime.combine(getdate(attendance_date), time.min)
	end_dt = datetime.combine(getdate(attendance_date), time.max)
	filters = {
		"employee": employee,
		"time": ["between", [start_dt, end_dt]],
	}
	if shift:
		filters["shift"] = shift

	rows = frappe.get_all("Employee Checkin", filters=filters, fields=["log_type"])
	has_in = any(row.log_type == "IN" for row in rows)
	has_out = any(row.log_type == "OUT" for row in rows)
	return has_in, has_out


def _has_incomplete_punch(doc):
	"""True when only check-in or only check-out exists on Attendance or linked Employee Checkins."""
	effective_in = doc.get("in_time") or doc.get("manual_in_time")
	effective_out = doc.get("out_time") or doc.get("manual_out_time")

	if effective_in and effective_out:
		return False
	if effective_in or effective_out:
		return True

	if doc.get("employee") and doc.get("attendance_date"):
		has_in, has_out = _employee_day_checkin_punch_state(
			doc.employee, doc.attendance_date
		)
		return bool(has_in) ^ bool(has_out)

	return False


def _incomplete_punch_deduction_enabled(hr_cust_settings):
	"""Full-day (100%) deduction is available when a default deduction component is configured."""
	return bool(_get_default_deduction_salary_component(hr_cust_settings))


def _get_salary_components_for_attendance_penalties(hr_cust_settings):
    employee_salary = hr_cust_settings.get("employee_salary") or []
    return [s.salary_component for s in employee_salary if s.get("salary_component")]


def _attendance_deductions_enabled(hr_cust_settings, doc):
    if hr_cust_settings.get("enable_shift_duration"):
        shift_type_exists = list(
            filter(
                lambda x: x.get("shift_type") == doc.shift,
                hr_cust_settings.get("enable_shift_types") or [],
            )
        )
        if shift_type_exists and hr_cust_settings.get("default_salary_component_for_deduction"):
            return True

    if hr_cust_settings.get("enable_standard_shift"):
        has_component = bool(
            hr_cust_settings.get("default_salary_component_for_deduction")
            or hr_cust_settings.get("default_salary_component_for_check_in_late")
            or hr_cust_settings.get("default_salary_component_for_check_out_early")
        )
        if has_component and (
            hr_cust_settings.get("enable_add_deduction_for_checkin_late")
            or hr_cust_settings.get("enable_add_deduction_for_checkout_early")
        ):
            return True

    return False


def _get_default_deduction_salary_component(hr_cust_settings):
    return (
        hr_cust_settings.get("default_salary_component_for_deduction")
        or hr_cust_settings.get("default_salary_component_for_check_in_late")
        or hr_cust_settings.get("default_salary_component_for_check_out_early")
    )


def apply_full_day_deduction_for_incomplete_punch(doc, hr_cust_settings, components=None):
    """
    Create a deduction Additional Salary for the full daily rate when the employee
    recorded only check-in or only check-out on the attendance day.
    """
    components = components or []
    salary_component = _get_default_deduction_salary_component(hr_cust_settings)
    if not doc.get("employee") or not doc.get("shift") or not salary_component:
        return

    if _attendance_additional_salary_exists(doc.name, salary_component):
        return

    daily_rate = get_employee_daily_rate(doc.employee, doc.attendance_date, components)
    if not daily_rate:
        frappe.log_error(
            title="Error in apply_full_day_deduction_for_incomplete_punch",
            message=f"Daily rate not found for employee={doc.employee}, date={doc.attendance_date}",
        )
        return

    try:
        create_additional_salary(
            employee=doc.employee,
            posting_date=doc.attendance_date,
            amount=flt(daily_rate),
            salary_component=salary_component,
            ref_doctype=doc.doctype,
            ref_docname=doc.name,
        )
    except Exception as e:
        frappe.log_error(
            title="Error in apply_full_day_deduction_for_incomplete_punch",
            message=f"Error creating Additional Salary: {e!s}",
        )


def _apply_attendance_penalty_or_earning(
    doc,
    total_minutes,
    parentfield,
    salary_component,
    *,
    use_overtime_filters=False,
    components: list = None,
):
    """
    Look up Auto Attendance Settings for the given shift/parentfield and minute range,
    compute amount from daily rate and value%, create Additional Salary.
    Used for: deduction (late check-in, early checkout, short shift) and earning (overtime).
    """
    components = components or []

    if not doc.get("employee") or not doc.get("shift") or not salary_component:
        frappe.log_error(
            title=f"Error in _apply_attendance_penalty_or_earning ({parentfield})",
            message=(
                f"Missing required input. Employee: {doc.get('employee')}, "
                f"Shift: {doc.get('shift')}, Salary Component: {salary_component}"
            ),
        )
        return
    daily_rate = get_employee_daily_rate(doc.employee, doc.attendance_date, components)
    if not daily_rate or daily_rate == 0:
        frappe.log_error(
            title=f"Error in _apply_attendance_penalty_or_earning ({parentfield})",
            message=f"Daily Rate: {daily_rate}",
        )
        return

    total_minute = int(round(total_minutes))
    if use_overtime_filters:
        filters = {"parentfield": parentfield, "parent": doc.shift, "from": ["<=", total_minute], "to": [">=", total_minute]}
        or_filters = {"parentfield": parentfield, "parent": doc.shift, "from": ["<=", total_minute], "to": ["=", 0]}
    else:
        # Include boundary values so exact minute matches are not skipped.
        filters = {"parentfield": parentfield, "parent": doc.shift, "from": ["<=", total_minute], "to": [">=", total_minute]}
        or_filters = {"parentfield": parentfield, "parent": doc.shift, "from": ["<=", total_minute], "to": ["=", 0]}

    row = frappe.db.get_all(
        "Auto Attendance Settings",
        filters=filters,
        or_filters=or_filters,
        fields=["value"],
        limit=1,
    )
    if not row:
        frappe.log_error(
            title=f"Error in _apply_attendance_penalty_or_earning ({parentfield})",
            message=(
                f"No Auto Attendance Settings row found for shift={doc.shift}, "
                f"parentfield={parentfield}, total_minutes={total_minute}"
            ),
        )
        return
    try:
        penalty_percent = row[0].get("value", 0) / 100
        amount = daily_rate * penalty_percent
        if amount <= 0:
            frappe.log_error(
                title=f"Error in _apply_attendance_penalty_or_earning ({parentfield})",
                message=f"Amount: {amount}",
            )
            return
        
        if _attendance_additional_salary_exists(doc.name, salary_component):
            return

        try:
            create_additional_salary(
                employee=doc.employee,
                posting_date=doc.attendance_date,
                amount=amount,
                salary_component=salary_component,
                ref_doctype=doc.doctype,
                ref_docname=doc.name,
            )
        except Exception as e:
            frappe.log_error(
                title=f"Error in _apply_attendance_penalty_or_earning ({parentfield})",
                message=f"Error in creating Additional Salary: {str(e)}",
            )
    except Exception as e:
        frappe.log_error(
            title=f"Error in _apply_attendance_penalty_or_earning ({parentfield})",
            message=f"Error in _apply_attendance_penalty_or_earning ({parentfield}): {str(e)}",
        )


def validate_employee_status(doc, method):
    """
    Prevent marking attendance for "Inactive", "Out of Country", and "On Long Leave" employees
    """
    if doc.employee:
        employee_status = frappe.db.get_value("Employee", doc.employee, "status")
        if employee_status in ["Inactive", "Out of Country", "On Long Leave"]:
            frappe.throw(
                _("Cannot mark attendance for an {0} employee {1}").format(
                    employee_status, 
                    get_link_to_form("Employee", doc.employee)
                )
            )


def validate_manual_attendance_dates(doc, method):
    """
    Manual In Time and Manual Out Time must be on the same date as Attendance Date.
    When both manual times are set, calculate and set working_hours.
    """
    if not doc.attendance_date:
        return
    attendance_date = getdate(doc.attendance_date)
    if doc.get("manual_in_time"):
        manual_in_date = getdate(doc.manual_in_time)
        if manual_in_date != attendance_date:
            frappe.throw(
                _("Manual In Time date ({0}) must be the same as Attendance Date ({1}).").format(
                    manual_in_date.strftime("%Y-%m-%d"),
                    attendance_date.strftime("%Y-%m-%d"),
                )
            )
    if doc.get("manual_out_time"):
        manual_out_date = getdate(doc.manual_out_time)
        if manual_out_date != attendance_date:
            frappe.throw(
                _("Manual Out Time date ({0}) must be the same as Attendance Date ({1}).").format(
                    manual_out_date.strftime("%Y-%m-%d"),
                    attendance_date.strftime("%Y-%m-%d"),
                )
            )
    # Calculate working_hours when both manual times are set
    if doc.get("manual_in_time") and doc.get("manual_out_time"):
        doc.working_hours = time_diff_in_hours(doc.manual_out_time, doc.manual_in_time)


def attendance_on_submit(doc:dict={} , event:str=""):
    """_
        Attendance Calculating By Two Way
            1 - By One Shift
            2 - By Shift Type ( Standard Shift )

        For manual attendance (no check-in/check-out), use Manual In Time and Manual Out Time.
    """
    if not doc.shift:
        return

    if employee_has_attendance_exception_on_date(doc.employee, doc.attendance_date):
        return

    hr_cust_settings = get_ouredu_hr_settings(doc.company)
    components = _get_salary_components_for_attendance_penalties(hr_cust_settings)

    if _has_incomplete_punch(doc):
        if _incomplete_punch_deduction_enabled(hr_cust_settings):
            apply_full_day_deduction_for_incomplete_punch(doc, hr_cust_settings, components)
        return

    # Use manual times when in_time/out_time are not set (manual attendance)
    effective_in = doc.get("in_time") or doc.get("manual_in_time")
    effective_out = doc.get("out_time") or doc.get("manual_out_time")

    if effective_in and effective_out:
        # Temporarily set for calculation so downstream code works unchanged
        orig_in, orig_out = doc.get("in_time"), doc.get("out_time")
        doc.in_time, doc.out_time = effective_in, effective_out
        try:
            # Run only one calculation path to avoid duplicate Additional Salaries
            if hr_cust_settings.get("enable_shift_duration"):
                calculate_auto_attendance_by_one_shift(doc, hr_cust_settings, components)
            elif hr_cust_settings.get("enable_standard_shift"):
                calculate_auto_attendance_by_shift_type(doc, hr_cust_settings, components)
        finally:
            doc.in_time, doc.out_time = orig_in, orig_out
        

def _get_converted_times_and_shift_bounds(doc):
    """Get in/out as datetime and shift start/end as datetime on the same date(s). Returns (converted_in_time, converted_out_time, converted_shift_start_time, converted_shift_end_time) or None if missing."""
    if not doc.shift or not doc.get("in_time") or not doc.get("out_time"):
        return None
    timing_map = get_shift_type_timing([doc.shift], for_date=doc.attendance_date)
    timing = timing_map.get(doc.shift) or {}
    shift_start_time = timing.get("start_time")
    shift_end_time = timing.get("end_time")
    if shift_start_time is None or shift_end_time is None:
        shift_start_time, shift_end_time = frappe.db.get_value(
            "Shift Type", doc.shift, ["start_time", "end_time"]
        )
    if isinstance(doc.in_time, str):
        converted_in_time = datetime.strptime(doc.in_time, "%Y-%m-%d %H:%M:%S")
        converted_out_time = datetime.strptime(doc.out_time, "%Y-%m-%d %H:%M:%S")
    else:
        converted_in_time, converted_out_time = doc.in_time, doc.out_time
    converted_shift_start_time = datetime.combine(
        converted_in_time.date(),
        datetime.strptime(str(shift_start_time), "%H:%M:%S").time(),
    )
    converted_shift_end_time = datetime.combine(
        converted_out_time.date(),
        datetime.strptime(str(shift_end_time), "%H:%M:%S").time(),
    )
    return converted_in_time, converted_out_time, converted_shift_start_time, converted_shift_end_time


def calculate_auto_attendance_by_one_shift(doc: dict = {}, hr_cust_settings: dict = {}, components: list = []):
    shift_type_exists = list(
        filter(lambda x: x.get("shift_type") == doc.shift, hr_cust_settings.enable_shift_types)
    )
    if not shift_type_exists:
        return

    shift_duration = shift_type_exists[0].get("shift_duration")
    working_hours = doc.get("working_hours")
    if not working_hours:
        working_hours = time_diff_in_hours(doc.out_time, doc.in_time)

    converted = _get_converted_times_and_shift_bounds(doc)
    if not converted:
        return
    converted_in_time, converted_out_time, converted_shift_start_time, converted_shift_end_time = converted

    flexible_minutes = get_flexible_minutes_for_attendance(doc)
    shift_name = doc.get("shift")

    if working_hours < shift_duration:
        late_minutes = _late_penalty_minutes(
            converted_in_time, converted_shift_start_time, shift_name, flexible_minutes
        )
        early_minutes = _early_penalty_minutes(
            converted_out_time, converted_shift_end_time, shift_name
        )
        total_minutes = late_minutes + early_minutes
        if total_minutes > 0:
            add_deduction_to_employee(doc, total_minutes, hr_cust_settings.default_salary_component_for_deduction, components)
    elif working_hours > shift_duration:
        overtime_minutes = max(0, (converted_out_time - converted_shift_end_time).total_seconds() / 60)
        if overtime_minutes > 0:
            add_earning_to_employee(doc, overtime_minutes, hr_cust_settings.default_salary_component_for_over_time, components)


def add_deduction_to_employee(doc, total_minutes, salary_component, components: list = []):
    _apply_attendance_penalty_or_earning(
        doc,
        total_minutes,
        "late_checkin",
        salary_component,
        use_overtime_filters=False,
        components=components,
    )


def add_earning_to_employee(doc, total_minutes, salary_component, components: list = []):
    _apply_attendance_penalty_or_earning(
        doc,
        total_minutes,
        "overtime",
        salary_component,
        use_overtime_filters=True,
        components=components,
    )



def calculate_auto_attendance_by_shift_type(doc: dict = {}, hr_cust_settings: dict = {}, components: list = []):
    """
    Add Additional Salary deduction or earning by shift type:
    1) Deduction if employee checks in late (in_time after shift start).
    2) Deduction if employee checks out early (out_time before shift end).
    3) Earning if employee has overtime (out_time after shift end).
    """
    converted = _get_converted_times_and_shift_bounds(doc)
    if not converted:
        return
    converted_in_time, converted_out_time, converted_shift_start_time, converted_shift_end_time = converted

    flexible_minutes = get_flexible_minutes_for_attendance(doc)
    shift_name = doc.get("shift")

    if (
        _late_penalty_minutes(
            converted_in_time, converted_shift_start_time, shift_name, flexible_minutes
        )
        > 0
        and hr_cust_settings.get("enable_add_deduction_for_checkin_late") == 1
    ):
        check_if_employee_get_late(
            converted_in_time,
            converted_shift_start_time,
            doc,
            hr_cust_settings,
            components,
            flexible_minutes,
        )
    if (
        _early_penalty_minutes(converted_out_time, converted_shift_end_time, shift_name) > 0
        and hr_cust_settings.get("enable_add_deduction_for_checkout_early") == 1
    ):
        check_if_employee_exit_early(
            converted_out_time,
            converted_shift_end_time,
            shift_name,
            doc,
            hr_cust_settings,
            components,
        )
    if converted_out_time > converted_shift_end_time and hr_cust_settings.get("enable_add_overtime_to_employee") == 1:
        check_if_employee_has_over_time(
            converted_out_time, converted_shift_end_time, doc, hr_cust_settings, components
        )


def check_if_employee_get_late(
    converted_in_time: datetime,
    converted_shift_start_time: datetime,
    doc: dict = {},
    hr_settings=None,
    components: list = [],
    flexible_minutes: int = 0,
):
    """Create Additional Salary when check-in exceeds grace; penalty uses full late minutes."""
    total_minutes = _late_penalty_minutes(
        converted_in_time,
        converted_shift_start_time,
        doc.get("shift"),
        flexible_minutes,
    )
    if total_minutes <= 0:
        return
    salary_component = hr_settings.get("default_salary_component_for_check_in_late") if hr_settings else None
    _apply_attendance_penalty_or_earning(
        doc,
        total_minutes,
        "late_checkin",
        salary_component,
        use_overtime_filters=False,
        components=components,
    )
        

def check_if_employee_exit_early(
    converted_out_time: datetime,
    converted_shift_end_time: datetime,
    shift_name: str,
    doc: dict = {},
    hr_settings=None,
    components: list = [],
):
    """Create Additional Salary when checkout exceeds grace; penalty uses full early minutes."""
    total_minutes = _early_penalty_minutes(
        converted_out_time, converted_shift_end_time, shift_name
    )
    if total_minutes <= 0:
        return
    salary_component = hr_settings.get("default_salary_component_for_check_out_early") if hr_settings else None
    _apply_attendance_penalty_or_earning(
        doc,
        total_minutes,
        "early_checkout",
        salary_component,
        use_overtime_filters=False,
        components=components,
    )


def check_if_employee_has_over_time(
    converted_out_time: datetime,
    shift_end_time: datetime,
    doc: dict = {},
    hr_settings=None,
    components: list = [],
):
    """Overtime = work after nominal shift end time."""
    duration = converted_out_time - shift_end_time
    total_minutes = duration.total_seconds() / 60
    if total_minutes <= 0:
        return
    salary_component = hr_settings.get("default_salary_component_for_over_time") if hr_settings else None
    _apply_attendance_penalty_or_earning(
        doc,
        total_minutes,
        "overtime",
        salary_component,
        use_overtime_filters=True,
        components=components,
    )


def before_cancel_attendance(doc, method):
    # Unlink employee checkin
    if doc.employee and doc.shift and doc.attendance_date:
        employee_checkins = frappe.db.get_all("Employee Checkin", filters={"attendance": doc.name})
        for employee_checkin in employee_checkins:
            frappe.db.set_value("Employee Checkin", employee_checkin.name, "attendance", None)


def cancel_attendance_linked_additional_salaries(attendance_name: str):
	"""Cancel or delete all Additional Salary rows linked to a submitted Attendance."""
	for name in frappe.get_all(
		"Additional Salary",
		filters={
			"ref_doctype": "Attendance",
			"ref_docname": attendance_name,
			"docstatus": ("<", 2),
		},
		pluck="name",
	):
		doc = frappe.get_doc("Additional Salary", name)
		doc.flags.ignore_permissions = True
		if doc.docstatus == 1:
			doc.cancel()
		else:
			frappe.delete_doc("Additional Salary", name, ignore_permissions=True, force=True)


def _attendance_penalty_snapshot(doc):
	"""Minimal attendance state used to detect penalty recalculation needs."""
	return {
		"employee": doc.get("employee"),
		"attendance_date": doc.get("attendance_date"),
		"shift": doc.get("shift"),
		"in_time": doc.get("in_time"),
		"out_time": doc.get("out_time"),
		"manual_in_time": doc.get("manual_in_time"),
		"manual_out_time": doc.get("manual_out_time"),
	}


def _attendance_penalty_inputs_changed(before_doc, after_doc) -> bool:
	before = _attendance_penalty_snapshot(before_doc)
	after = _attendance_penalty_snapshot(after_doc)
	if _has_incomplete_punch(before) != _has_incomplete_punch(after):
		return True
	for field in ("in_time", "out_time", "manual_in_time", "manual_out_time"):
		before_val = before.get(field)
		after_val = after.get(field)
		if before_val is None and after_val is None:
			continue
		if before_val is None or after_val is None:
			return True
		if get_datetime(before_val) != get_datetime(after_val):
			return True
	return False


def _reapply_attendance_penalties(attendance_doc, event=""):
	"""Cancel linked Additional Salary and recalculate penalties from current attendance."""
	cancel_attendance_linked_additional_salaries(attendance_doc.name)
	attendance_on_submit(attendance_doc, event)


def _refresh_attendance_penalties_after_checkin_sync(before_doc, attendance_doc, event="checkin_sync"):
	"""
	Recalculate penalties after check-in sync when punch completeness or times changed.

	Fixes the race where attendance submits with only IN before OUT syncs later.
	"""
	if _attendance_penalty_inputs_changed(before_doc, attendance_doc):
		_reapply_attendance_penalties(attendance_doc, event)
	else:
		attendance_on_submit(attendance_doc, event)


def employee_has_checkins_for_attendance_day(
	employee, attendance_date, shift=None, *, any_shift_on_day=False
) -> bool:
	"""True if any check-in exists for this employee on the attendance date (includes offshift)."""
	query_shift = None if any_shift_on_day else shift
	return bool(
		_get_checkin_names_for_attendance_day(
			employee, attendance_date, query_shift, limit=1
		)
	)


def _clear_skip_auto_attendance_for_checkins(checkin_names):
	"""Re-enable check-ins that were skipped after a failed auto-attendance attempt."""
	if not checkin_names:
		return
	frappe.db.set_value(
		"Employee Checkin",
		{"name": ["in", checkin_names]},
		"skip_auto_attendance",
		0,
		update_modified=False,
	)


def _resolve_checkin_shift(employee, shift=None):
	"""Shift for attendance from check-in row, else employee default shift."""
	return shift or frappe.db.get_value("Employee", employee, "default_shift")


def _append_offshift_checkins_for_day(employee, attendance_date, log_rows):
	"""Include same-day offshift punches not already in log_rows (e.g. checkout after shift window)."""
	if not employee or not attendance_date or not log_rows:
		return log_rows

	existing_names = set()
	for row in log_rows:
		name = row.get("name") if isinstance(row, dict) else getattr(row, "name", None)
		if name:
			existing_names.add(name)

	extra = []
	for row in _get_checkin_rows_for_employee_day(employee, attendance_date):
		if cint(row.get("offshift")) and row.name not in existing_names:
			extra.append(row)

	if not extra:
		return log_rows

	merged = list(log_rows) + extra
	merged.sort(key=lambda r: get_datetime(r.get("time") if isinstance(r, dict) else r.time))
	return merged


def _get_checkin_rows_for_employee_day(employee, attendance_date, shift=None):
	"""All check-ins on calendar day for employee (includes offshift and skip_auto_attendance)."""
	attendance_date = getdate(attendance_date)
	day_start = datetime.combine(attendance_date, time.min)
	day_end = datetime.combine(attendance_date, time.max)
	fields = [
		"name",
		"employee",
		"log_type",
		"time",
		"shift",
		"shift_start",
		"shift_end",
		"shift_actual_start",
		"shift_actual_end",
		"offshift",
	]
	name_set = set(
		_get_checkin_names_for_attendance_day(
			employee, attendance_date, shift=None, any_shift_on_day=True
		)
	)
	offshift_names = frappe.db.sql(
		"""
		SELECT c.name
		FROM `tabEmployee Checkin` c
		WHERE c.employee = %(employee)s
			AND c.offshift = 1
			AND (
				c.time BETWEEN %(day_start)s AND %(day_end)s
				OR c.shift_start BETWEEN %(day_start)s AND %(day_end)s
			)
		""",
		{"employee": employee, "day_start": day_start, "day_end": day_end},
		pluck=True,
	)
	name_set.update(offshift_names)
	if not name_set:
		return []
	return frappe.get_all(
		"Employee Checkin",
		filters={"name": ["in", list(name_set)]},
		fields=fields,
		order_by="time asc",
	)


def _get_skipped_checkin_names_for_attendance_day(
	employee, attendance_date, attendance_name=None, shift=None, *, any_shift_on_day=False
):
	"""Check-ins marked skip_auto_attendance (usually after duplicate Absent was created)."""
	attendance_date = getdate(attendance_date)
	day_start = datetime.combine(attendance_date, time.min)
	day_end = datetime.combine(attendance_date, time.max)
	conditions = [
		"c.employee = %(employee)s",
		"c.skip_auto_attendance = 1",
		"(c.time BETWEEN %(day_start)s AND %(day_end)s OR c.shift_start BETWEEN %(day_start)s AND %(day_end)s)",
		"(c.attendance IS NULL OR c.attendance = %(attendance)s)",
	]
	params = {
		"employee": employee,
		"day_start": day_start,
		"day_end": day_end,
		"attendance": attendance_name or "",
	}
	if shift and not any_shift_on_day:
		conditions.append("c.shift = %(shift)s")
		params["shift"] = shift

	return frappe.db.sql(
		f"""
		SELECT c.name
		FROM `tabEmployee Checkin` c
		WHERE {" AND ".join(conditions)}
		ORDER BY c.time ASC
		""",
		params,
		pluck=True,
	)


def _get_checkin_names_for_attendance_day(
	employee, attendance_date, shift=None, limit=None, *, any_shift_on_day=False
):
	"""Check-in names for employee on calendar day (matches by log time or shift_start date)."""
	attendance_date = getdate(attendance_date)
	day_start = datetime.combine(attendance_date, time.min)
	day_end = datetime.combine(attendance_date, time.max)

	conditions = [
		"c.employee = %(employee)s",
		"(c.time BETWEEN %(day_start)s AND %(day_end)s OR c.shift_start BETWEEN %(day_start)s AND %(day_end)s)",
	]
	params = {
		"employee": employee,
		"day_start": day_start,
		"day_end": day_end,
	}
	if shift and not any_shift_on_day:
		conditions.append("c.shift = %(shift)s")
		params["shift"] = shift

	limit_sql = f"LIMIT {cint(limit)}" if limit else ""
	return frappe.db.sql(
		f"""
		SELECT c.name
		FROM `tabEmployee Checkin` c
		WHERE {" AND ".join(conditions)}
		ORDER BY c.time ASC
		{limit_sql}
		""",
		params,
		pluck=True,
	)


def _checkin_logs_for_attendance_shift(log_rows, attendance_shift, attendance_date):
	"""
	Use real punch times from check-ins but evaluate late/early against the attendance
	shift window (employee's assigned shift on the Absent record).
	"""
	if not log_rows or not attendance_shift:
		return log_rows

	timing_map = get_shift_type_timing([attendance_shift], for_date=attendance_date)
	timing = timing_map.get(attendance_shift) or {}
	start_time = timing.get("start_time")
	end_time = timing.get("end_time")
	if not start_time or not end_time:
		return log_rows

	att_date = getdate(attendance_date)
	shift_start = datetime.combine(att_date, get_time(start_time))
	shift_end = datetime.combine(att_date, get_time(end_time))
	if shift_end <= shift_start:
		shift_end += timedelta(days=1)

	normalized = []
	for row in log_rows:
		if isinstance(row, dict):
			r = frappe._dict(row.copy())
		elif hasattr(row, "as_dict"):
			r = frappe._dict(row.as_dict())
		else:
			r = frappe._dict(dict(row))
		r.shift = attendance_shift
		r.shift_start = shift_start
		r.shift_end = shift_end
		normalized.append(r)
	return normalized


def _get_checkin_rows_for_attendance(
	attendance_doc, checkin_shift=None, include_all_shifts_on_day=True
):
	"""Employee Checkin rows for recomputing attendance (linked, same day, skip_auto_attendance).

	When include_all_shifts_on_day is True, includes check-ins from other shifts on the same
	calendar day (Absent on shift A + check-ins on shift B).
	"""
	fields = [
		"name",
		"employee",
		"log_type",
		"time",
		"shift",
		"shift_start",
		"shift_end",
		"shift_actual_start",
		"shift_actual_end",
	]
	query_shift = (
		None
		if include_all_shifts_on_day
		else (checkin_shift or attendance_doc.shift)
	)
	name_set = set()

	for row in frappe.get_all(
		"Employee Checkin",
		filters={"attendance": attendance_doc.name},
		fields=fields,
		order_by="time asc",
	):
		name_set.add(row.name)

	for name in _get_checkin_names_for_attendance_day(
		attendance_doc.employee,
		attendance_doc.attendance_date,
		query_shift,
		any_shift_on_day=include_all_shifts_on_day,
	):
		name_set.add(name)

	for name in _get_skipped_checkin_names_for_attendance_day(
		attendance_doc.employee,
		attendance_doc.attendance_date,
		attendance_name=attendance_doc.name,
		shift=query_shift,
		any_shift_on_day=include_all_shifts_on_day,
	):
		name_set.add(name)

	# Explicitly merge offshift check-ins on the same day.
	for row in _get_checkin_rows_for_employee_day(
		attendance_doc.employee, attendance_doc.attendance_date
	):
		if cint(row.get("offshift")):
			name_set.add(row.name)

	if not name_set:
		return []

	return frappe.get_all(
		"Employee Checkin",
		filters={"name": ["in", list(name_set)]},
		fields=fields,
		order_by="time asc",
	)


def _recompute_attendance_fields_from_checkins(attendance_doc) -> bool:
	"""Update in/out, working hours, and flags from check-ins. Returns True if check-ins were applied."""
	if not attendance_doc.shift:
		return False

	log_rows = _get_checkin_rows_for_attendance(attendance_doc)
	if not log_rows:
		return False

	shift_doc = frappe.get_doc("Shift Type", attendance_doc.shift)
	if hasattr(shift_doc, "should_mark_attendance") and not shift_doc.should_mark_attendance(
		attendance_doc.employee, getdate(attendance_doc.attendance_date)
	):
		return False

	log_rows = _checkin_logs_for_attendance_shift(
		log_rows, attendance_doc.shift, attendance_doc.attendance_date
	)

	(
		attendance_status,
		working_hours,
		late_entry,
		early_exit,
		in_time,
		out_time,
	) = shift_doc.get_attendance(log_rows)

	leave_info = (
		shift_doc._check_leave_record(attendance_doc.employee, getdate(attendance_doc.attendance_date))
		if hasattr(shift_doc, "_check_leave_record")
		else None
	)
	if leave_info:
		attendance_status = leave_info["status"]

	update_fields = {
		"working_hours": working_hours,
		"late_entry": cint(late_entry),
		"early_exit": cint(early_exit),
		"in_time": in_time,
		"out_time": out_time,
		"status": attendance_status,
	}
	if leave_info:
		update_fields["leave_type"] = leave_info.get("leave_type")
		update_fields["leave_application"] = leave_info.get("leave_application")
		if attendance_status == "Half Day":
			update_fields["half_day_status"] = "Present"
			update_fields["modify_half_day_status"] = 0

	frappe.db.set_value("Attendance", attendance_doc.name, update_fields, update_modified=False)
	checkin_names = [r.name for r in log_rows]
	update_attendance_in_checkins(checkin_names, attendance_doc.name)

	EmployeeCheckin = frappe.qb.DocType("Employee Checkin")
	(
		frappe.qb.update(EmployeeCheckin)
		.set("skip_auto_attendance", 0)
		.where(EmployeeCheckin.name.isin(checkin_names))
	).run()
	return True


def recalculate_single_attendance(attendance_name: str):
	"""Re-sync attendance from check-ins, replace linked Additional Salary, and recalculate penalties."""
	if getattr(frappe.flags, "in_install", False) or getattr(frappe.flags, "in_migrate", False):
		return

	attendance_doc = frappe.get_doc("Attendance", attendance_name)
	if attendance_doc.docstatus != 1:
		return

	if employee_has_attendance_exception_on_date(
		attendance_doc.employee, getdate(attendance_doc.attendance_date)
	):
		return

	_recompute_attendance_fields_from_checkins(attendance_doc)
	attendance_doc.reload()
	_reapply_attendance_penalties(attendance_doc, "recalculate")


def get_recalculation_date_range(assignment_doc, before_doc=None):
	"""Inclusive date range (up to today) affected by a shift assignment change."""
	today = getdate()
	start = getdate(assignment_doc.start_date)
	end = getdate(assignment_doc.end_date) if assignment_doc.end_date else today

	if before_doc:
		start = min(start, getdate(before_doc.start_date))
		before_end = getdate(before_doc.end_date) if before_doc.end_date else today
		end = max(end, before_end)

	end = min(end, today)
	if start > end:
		return None, None
	return start, end


def _shift_types_for_recalculation(assignment_doc, before_doc=None):
	shift_types = []
	if assignment_doc.shift_type:
		shift_types.append(assignment_doc.shift_type)
	if before_doc and before_doc.shift_type and before_doc.shift_type not in shift_types:
		shift_types.append(before_doc.shift_type)
	return shift_types or None


def recalculate_attendance_for_shift_change(
	employee: str,
	from_date,
	to_date=None,
	shift_types: list | None = None,
	*,
	enqueue: bool = False,
):
	"""
	Recalculate submitted attendance and linked Additional Salary for an employee
	when shift assignment changes affect past dates.
	"""
	if not employee or not from_date:
		return {"processed": 0, "attendances": []}

	if getattr(frappe.flags, "in_install", False) or getattr(frappe.flags, "in_migrate", False):
		return {"processed": 0, "attendances": []}

	from_date = getdate(from_date)
	today = getdate()
	to_date = min(getdate(to_date) if to_date else today, today)

	if from_date > to_date:
		return {"processed": 0, "attendances": []}

	if enqueue:
		frappe.enqueue(
			"acc_egypt_cust.acc_egypt_cust.doc_events.attendance.recalculate_attendance_for_shift_change",
			employee=employee,
			from_date=str(from_date),
			to_date=str(to_date),
			shift_types=shift_types,
			enqueue=False,
			queue="long",
			timeout=60 * 30,
		)
		return {"status": "queued", "from_date": str(from_date), "to_date": str(to_date)}

	filters = {
		"employee": employee,
		"docstatus": 1,
		"attendance_date": ["between", [from_date, to_date]],
	}
	if shift_types:
		filters["shift"] = ["in", shift_types]

	attendance_names = frappe.get_all("Attendance", filters=filters, pluck="name", order_by="attendance_date asc")
	processed = []
	for name in attendance_names:
		try:
			recalculate_single_attendance(name)
			processed.append(name)
		except Exception:
			frappe.log_error(
				title=_("Failed to recalculate Attendance after shift change"),
				message=frappe.get_traceback(),
			)

	if processed:
		frappe.db.commit()

	return {"processed": len(processed), "attendances": processed}


def recalculate_after_shift_assignment_ops(
	employee: str,
	start_date,
	end_date=None,
	shift_types: list | None = None,
	*,
	enqueue: bool | None = None,
):
	"""Entry point after shift assignment create/update/overlap handling."""
	from_date, to_date = getdate(start_date), getdate(end_date) if end_date else getdate()
	if from_date > getdate():
		return {"processed": 0, "attendances": []}

	if enqueue is None:
		span_days = (to_date - from_date).days + 1
		enqueue = span_days > 31

	return recalculate_attendance_for_shift_change(
		employee,
		from_date,
		to_date,
		shift_types=shift_types,
		enqueue=enqueue,
	)


def _attendance_can_generate_additional_salary(attendance_name: str) -> bool:
    """Check whether this attendance qualifies for any deduction/earning calculation."""
    doc = frappe.get_doc("Attendance", attendance_name)
    if not doc.get("employee") or not doc.get("shift"):
        return False

    hr_cust_settings = get_ouredu_hr_settings(doc.company)

    if _has_incomplete_punch(doc):
        return _incomplete_punch_deduction_enabled(hr_cust_settings)

    effective_in = doc.get("in_time") or doc.get("manual_in_time")
    effective_out = doc.get("out_time") or doc.get("manual_out_time")
    if not (effective_in and effective_out):
        return False

    if hr_cust_settings.get("enable_shift_duration"):
        shift_type_exists = list(
            filter(lambda x: x.get("shift_type") == doc.shift, hr_cust_settings.enable_shift_types)
        )
        return bool(shift_type_exists)

    if hr_cust_settings.get("enable_standard_shift"):
        return bool(
            hr_cust_settings.get("enable_add_deduction_for_checkin_late")
            or hr_cust_settings.get("enable_add_deduction_for_checkout_early")
            or hr_cust_settings.get("enable_add_overtime_to_employee")
        )

    return False


def _auto_attendance_tier_matches(shift, parentfield, total_minutes):
	total_minute = int(round(total_minutes))
	if total_minute <= 0 or not shift:
		return False
	filters = {
		"parentfield": parentfield,
		"parent": shift,
		"from": ["<=", total_minute],
		"to": [">=", total_minute],
	}
	or_filters = {
		"parentfield": parentfield,
		"parent": shift,
		"from": ["<=", total_minute],
		"to": ["=", 0],
	}
	return bool(
		frappe.db.get_all(
			"Auto Attendance Settings",
			filters=filters,
			or_filters=or_filters,
			fields=["name"],
			limit=1,
		)
	)


def _attendance_penalty_minutes_under_current_rules(doc):
	converted = _get_converted_times_and_shift_bounds(
		doc.as_dict() if hasattr(doc, "as_dict") else doc
	)
	if not converted:
		return 0, 0

	in_time, out_time, shift_start, shift_end = converted
	flexible_minutes = get_flexible_minutes_for_attendance(doc)
	shift_name = doc.get("shift")
	late_minutes = _late_penalty_minutes(
		in_time, shift_start, shift_name, flexible_minutes
	)
	early_minutes = _early_penalty_minutes(out_time, shift_end, shift_name)
	return late_minutes, early_minutes


def attendance_should_create_penalty_additional_salary(attendance_name: str) -> bool:
	"""True when current rules would create a late/early penalty Additional Salary."""
	doc = frappe.get_doc("Attendance", attendance_name)
	if doc.docstatus != 1 or not doc.get("employee") or not doc.get("shift"):
		return False

	if employee_has_attendance_exception_on_date(doc.employee, doc.attendance_date):
		return False

	hr_cust_settings = get_ouredu_hr_settings(doc.company)
	if _has_incomplete_punch(doc):
		return _incomplete_punch_deduction_enabled(hr_cust_settings)

	effective_in = doc.get("in_time") or doc.get("manual_in_time")
	effective_out = doc.get("out_time") or doc.get("manual_out_time")
	if not (effective_in and effective_out):
		return False

	late_minutes, early_minutes = _attendance_penalty_minutes_under_current_rules(doc)
	if (
		hr_cust_settings.get("enable_add_deduction_for_checkin_late")
		and late_minutes > 0
		and _auto_attendance_tier_matches(doc.shift, "late_checkin", late_minutes)
	):
		return True
	if (
		hr_cust_settings.get("enable_add_deduction_for_checkout_early")
		and early_minutes > 0
		and _auto_attendance_tier_matches(doc.shift, "early_checkout", early_minutes)
	):
		return True
	return False


def get_attendances_missing_penalty_additional_salary(
	from_date=None, to_date=None, company=None, limit=500
):
	"""Submitted attendances that should have penalty Additional Salary but do not."""
	attendance_filters = {"docstatus": 1}
	if company:
		attendance_filters["company"] = company
	attendance_filters.update(
		_attendance_list_date_filters(from_date, to_date, fieldname="attendance_date")
	)

	attendance_rows = frappe.get_all(
		"Attendance",
		filters=attendance_filters,
		fields=["name", "employee", "company", "attendance_date", "shift", "late_entry", "early_exit"],
		order_by="attendance_date asc, modified asc",
		limit_page_length=cint(limit) if limit else 500,
	)
	if not attendance_rows:
		return []

	attendance_names = [row.name for row in attendance_rows]
	existing_ref_names = set(
		frappe.get_all(
			"Additional Salary",
			filters={
				"ref_doctype": "Attendance",
				"ref_docname": ["in", attendance_names],
				"docstatus": ["<", 2],
			},
			pluck="ref_docname",
		)
	)

	pending = []
	for row in attendance_rows:
		if row.name in existing_ref_names:
			continue
		if attendance_should_create_penalty_additional_salary(row.name):
			pending.append(row)
	return pending


@frappe.whitelist()
def preview_missing_penalty_additional_salary_for_attendance(
	from_date=None, to_date=None, company=None, limit=500
):
	rows = get_attendances_missing_penalty_additional_salary(
		from_date=from_date, to_date=to_date, company=company, limit=limit
	)
	return {"count": len(rows), "records": rows[:200]}


@frappe.whitelist()
def create_missing_penalty_additional_salary_for_attendance(
	from_date=None, to_date=None, company=None, limit=500, dry_run=1
):
	"""Create missing penalty Additional Salary rows for attendances like late-within-grace-gap cases."""
	dry_run = cint(dry_run)
	pending = get_attendances_missing_penalty_additional_salary(
		from_date=from_date, to_date=to_date, company=company, limit=limit
	)

	processed = 0
	created_for = []
	errors = []

	for row in pending:
		if dry_run:
			created_for.append(row.name)
			continue
		try:
			if _attendance_additional_salary_exists(row.name):
				continue
			attendance_doc = frappe.get_doc("Attendance", row.name)
			before_count = frappe.db.count(
				"Additional Salary",
				{
					"ref_doctype": "Attendance",
					"ref_docname": row.name,
					"docstatus": ["<", 2],
				},
			)
			attendance_on_submit(attendance_doc, "backfill_penalty")
			after_count = frappe.db.count(
				"Additional Salary",
				{
					"ref_doctype": "Attendance",
					"ref_docname": row.name,
					"docstatus": ["<", 2],
				},
			)
			if after_count > before_count:
				created_for.append(row.name)
			processed += 1
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			errors.append({"name": row.name, "error": frappe.get_traceback()})
			frappe.log_error(
				title="Failed to create missing penalty Additional Salary for Attendance",
				message=frappe.get_traceback(),
			)

	return {
		"dry_run": dry_run,
		"matched": len(pending),
		"processed": processed,
		"created_for": created_for,
		"errors": errors,
	}


def _amount_is_full_daily_rate(amount, daily_rate) -> bool:
	"""Compare ADS amount to daily rate with currency precision tolerance."""
	if not amount or not daily_rate:
		return False
	return flt(amount, 2) == flt(daily_rate, 2)


def get_false_incomplete_punch_additional_salary_attendances(
	from_date=None, to_date=None, company=None, limit=500
):
	"""
	Attendances with a linked Additional Salary equal to full daily rate while the
	punch is complete (false incomplete-punch or IN-only submit race deductions).
	"""
	limit = cint(limit) if limit else 500
	ads_filters = {
		"ref_doctype": "Attendance",
		"docstatus": 1,
	}
	if company:
		ads_filters["company"] = company

	ads_rows = frappe.get_all(
		"Additional Salary",
		filters=ads_filters,
		fields=["name", "ref_docname", "amount", "employee", "payroll_date"],
		order_by="payroll_date desc, creation desc",
		limit_page_length=limit * 3,
	)
	if not ads_rows:
		return []

	seen_attendance = set()
	false_positives = []

	for ads in ads_rows:
		attendance_name = ads.ref_docname
		if not attendance_name or attendance_name in seen_attendance:
			continue

		attendance = frappe.db.get_value(
			"Attendance",
			attendance_name,
			["name", "employee", "company", "attendance_date", "shift", "in_time", "out_time", "docstatus"],
			as_dict=True,
		)
		if not attendance or attendance.docstatus != 1:
			continue
		if not attendance.in_time or not attendance.out_time:
			continue
		if from_date and getdate(attendance.attendance_date) < getdate(from_date):
			continue
		if to_date and getdate(attendance.attendance_date) > getdate(to_date):
			continue
		if company and attendance.company != company:
			continue

		attendance_doc = frappe.get_doc("Attendance", attendance_name)
		if _has_incomplete_punch(attendance_doc):
			continue
		# Full daily rate with late/early flags usually means a legitimate 100% tier penalty.
		if cint(attendance_doc.late_entry) or cint(attendance_doc.early_exit):
			continue

		hr_cust_settings = get_ouredu_hr_settings(attendance.company)
		components = _get_salary_components_for_attendance_penalties(hr_cust_settings)
		daily_rate = get_employee_daily_rate(
			attendance.employee, attendance.attendance_date, components
		)
		if not daily_rate or not _amount_is_full_daily_rate(ads.amount, daily_rate):
			continue

		seen_attendance.add(attendance_name)
		false_positives.append(
			{
				"attendance": attendance_name,
				"employee": attendance.employee,
				"attendance_date": attendance.attendance_date,
				"additional_salary": ads.name,
				"amount": flt(ads.amount, 2),
				"daily_rate": flt(daily_rate, 2),
			}
		)
		if len(false_positives) >= limit:
			break

	return false_positives


@frappe.whitelist()
def cleanup_false_incomplete_punch_additional_salary(
	from_date=None, to_date=None, company=None, limit=500, dry_run=1
):
	"""Cancel false full-day deductions and recalculate penalties for affected attendances."""
	dry_run = cint(dry_run)
	matches = get_false_incomplete_punch_additional_salary_attendances(
		from_date=from_date, to_date=to_date, company=company, limit=limit
	)

	recalculated = []
	errors = []
	for row in matches:
		if dry_run:
			recalculated.append(row["attendance"])
			continue
		try:
			recalculate_single_attendance(row["attendance"])
			recalculated.append(row["attendance"])
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			errors.append({"attendance": row["attendance"], "error": frappe.get_traceback()})
			frappe.log_error(
				title="Failed to cleanup false incomplete punch Additional Salary",
				message=frappe.get_traceback(),
			)

	return {
		"dry_run": dry_run,
		"matched": len(matches),
		"records": matches[:200],
		"recalculated": recalculated,
		"errors": errors,
	}


def _attendance_needs_penalty_reconciliation(attendance_name: str) -> bool:
	"""True when this submitted attendance may need penalty Additional Salary synced."""
	doc = frappe.get_doc("Attendance", attendance_name)
	if doc.docstatus != 1 or not doc.get("shift"):
		return False
	if doc.status not in ("Present", "Half Day", "Work From Home"):
		return False
	if employee_has_attendance_exception_on_date(doc.employee, getdate(doc.attendance_date)):
		return False

	hr_cust_settings = get_ouredu_hr_settings(doc.company)
	if not hr_cust_settings:
		return False
	if not (
		_incomplete_punch_deduction_enabled(hr_cust_settings)
		or _attendance_deductions_enabled(hr_cust_settings, doc)
	):
		return False

	if _attendance_additional_salary_exists(attendance_name):
		return True
	if attendance_should_create_penalty_additional_salary(attendance_name):
		return True
	if _attendance_can_generate_additional_salary(attendance_name):
		return True
	return employee_has_checkins_for_attendance_day(
		doc.employee, doc.attendance_date, any_shift_on_day=True
	)


def get_attendances_for_penalty_reconciliation(
	attendance_date=None, company=None, limit=5000
):
	"""Submitted attendances on a date that should be checked for penalty Additional Salary."""
	attendance_date = getdate(attendance_date) if attendance_date else getdate()
	filters = {
		"docstatus": 1,
		"attendance_date": attendance_date,
		"shift": ["is", "set"],
		"status": ["in", ["Present", "Half Day", "Work From Home"]],
	}
	if company:
		filters["company"] = company

	rows = frappe.get_all(
		"Attendance",
		filters=filters,
		fields=["name", "employee", "company", "attendance_date"],
		order_by="modified asc",
		limit_page_length=cint(limit) if limit else 5000,
	)
	return [row for row in rows if _attendance_needs_penalty_reconciliation(row.name)]


def reconcile_attendance_additional_salaries_for_date(
	attendance_date=None, company=None, limit=5000, dry_run=False
):
	"""
	Re-sync submitted attendances for one day from check-ins and rebuild linked
	penalty Additional Salary rows.
	"""
	dry_run = cint(dry_run)
	attendance_date = getdate(attendance_date) if attendance_date else getdate()
	rows = get_attendances_for_penalty_reconciliation(
		attendance_date=attendance_date, company=company, limit=limit
	)

	recalculated = []
	errors = []
	for row in rows:
		if dry_run:
			recalculated.append(row.name)
			continue
		try:
			recalculate_single_attendance(row.name)
			recalculated.append(row.name)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			errors.append({"attendance": row.name, "error": frappe.get_traceback()})
			frappe.log_error(
				title="Failed end-of-day attendance Additional Salary reconciliation",
				message=frappe.get_traceback(),
			)

	return {
		"dry_run": dry_run,
		"attendance_date": str(attendance_date),
		"matched": len(rows),
		"recalculated": recalculated,
		"errors": errors,
	}


def reconcile_attendance_additional_salaries_daily(
	lookback_days=1, company=None, limit_per_day=5000, dry_run=False
):
	"""
	End-of-day reconciliation across today and recent days (late BioTime sync buffer).

	For each eligible submitted attendance:
	1. Recompute in/out from Employee Checkins
	2. Cancel linked Additional Salary
	3. Recalculate penalties (late, early, incomplete punch, overtime)
	"""
	dry_run = cint(dry_run)
	lookback_days = max(0, cint(lookback_days))
	today = getdate()
	summary = {
		"dry_run": dry_run,
		"lookback_days": lookback_days,
		"days": [],
		"total_matched": 0,
		"total_recalculated": 0,
		"total_errors": 0,
	}

	for day_offset in range(lookback_days + 1):
		attendance_date = add_days(today, -day_offset)
		day_result = reconcile_attendance_additional_salaries_for_date(
			attendance_date=attendance_date,
			company=company,
			limit=limit_per_day,
			dry_run=dry_run,
		)
		summary["days"].append(day_result)
		summary["total_matched"] += day_result["matched"]
		summary["total_recalculated"] += len(day_result["recalculated"])
		summary["total_errors"] += len(day_result["errors"])

	frappe.logger().info(
		"Attendance Additional Salary EOD reconciliation: "
		f"matched={summary['total_matched']} "
		f"recalculated={summary['total_recalculated']} "
		f"errors={summary['total_errors']} "
		f"dry_run={summary['dry_run']}"
	)
	return summary


@frappe.whitelist()
def preview_daily_attendance_additional_salary_reconciliation(
	lookback_days=1, company=None, limit_per_day=5000
):
	return reconcile_attendance_additional_salaries_daily(
		lookback_days=lookback_days,
		company=company,
		limit_per_day=limit_per_day,
		dry_run=1,
	)


@frappe.whitelist()
def run_daily_attendance_additional_salary_reconciliation(
	lookback_days=1, company=None, limit_per_day=5000
):
	return reconcile_attendance_additional_salaries_daily(
		lookback_days=lookback_days,
		company=company,
		limit_per_day=limit_per_day,
		dry_run=0,
	)


def get_attendances_missing_additional_salary(from_date=None, to_date=None, company=None, limit=500):
    """
    Return submitted attendances that can generate Additional Salary,
    but currently have no Additional Salary linked to them.
    """
    attendance_filters = {"docstatus": 1}
    if company:
        attendance_filters["company"] = company
    if from_date:
        attendance_filters["attendance_date"] = [">=", getdate(from_date)]
    if to_date:
        if attendance_filters.get("attendance_date"):
            attendance_filters["attendance_date"] = [
                "between",
                [getdate(from_date), getdate(to_date)],
            ]
        else:
            attendance_filters["attendance_date"] = ["<=", getdate(to_date)]

    attendance_rows = frappe.get_all(
        "Attendance",
        filters=attendance_filters,
        fields=["name", "employee", "company", "attendance_date", "shift"],
        order_by="attendance_date asc, modified asc",
        limit_page_length=cint(limit) if limit else 500,
    )
    if not attendance_rows:
        return []

    attendance_names = [row.name for row in attendance_rows]
    existing_ref_names = set(
        frappe.get_all(
            "Additional Salary",
            filters={
                "ref_doctype": "Attendance",
                "ref_docname": ["in", attendance_names],
                "docstatus": ["<", 2],
            },
            pluck="ref_docname",
        )
    )

    pending = []
    for row in attendance_rows:
        if row.name in existing_ref_names:
            continue
        if _attendance_can_generate_additional_salary(row.name):
            pending.append(row)

    frappe.log_error(f"Pending Attendances: {len(pending)}")

    return pending


@frappe.whitelist()
def enqueue_create_missing_additional_salary_for_attendance(
    from_date=None, to_date=None, company=None, limit=500
):
    """Queue long-running background job to create missing Additional Salary for Attendance."""
    frappe.enqueue(
        create_missing_additional_salary_for_attendance,
        queue="long",
        timeout=60 * 60,
        from_date=from_date,
        to_date=to_date,
        company=company,
        limit=limit,
    )
    return {"status": "queued"}


def create_missing_additional_salary_for_attendance(from_date=None, to_date=None, company=None, limit=500):
    """
    Background worker: find attendances missing Additional Salary and re-run
    existing attendance salary logic to create required records.
    """
    pending_attendances = get_attendances_missing_additional_salary(
        from_date=from_date, to_date=to_date, company=company, limit=limit
    )
    if not pending_attendances:
        return {"processed": 0, "created_for": []}

    frappe.log_error(f"Pending Attendances: {len(pending_attendances)}")

    processed = 0
    created_for = []

    frappe.log_error(f"Pending Attendances: {pending_attendances}")

    for row in pending_attendances:
        try:
            if _attendance_additional_salary_exists(row.name):
                continue

            attendance_doc = frappe.get_doc("Attendance", row.name)
            before_count = frappe.db.count(
                "Additional Salary", {"ref_doctype": "Attendance", "ref_docname": row.name, "docstatus": ["<", 2]}
            )
            attendance_on_submit(attendance_doc, "on_submit")
            after_count = frappe.db.count(
                "Additional Salary", {"ref_doctype": "Attendance", "ref_docname": row.name, "docstatus": ["<", 2]}
            )
            if after_count > before_count:
                created_for.append(row.name)
            processed += 1
            frappe.db.commit()
        except Exception:
            frappe.log_error(
                title="Failed to create missing Additional Salary for Attendance",
                message=frappe.get_traceback(),
            )
            continue

    return {"processed": processed, "created_for": created_for}


def _attendance_list_date_filters(from_date=None, to_date=None, fieldname="attendance_date"):
	"""Build frappe filters for a date / date-range on an Attendance (or similar) field."""
	filters = {}
	if from_date and to_date:
		filters[fieldname] = ["between", [getdate(from_date), getdate(to_date)]]
	elif from_date:
		filters[fieldname] = [">=", getdate(from_date)]
	elif to_date:
		filters[fieldname] = ["<=", getdate(to_date)]
	return filters


def _checkin_docs_from_rows(log_rows):
	return [frappe.get_doc("Employee Checkin", row["name"]) for row in log_rows]


def _attendance_shift_key(employee, shift, attendance_date):
	return (employee, shift, getdate(attendance_date))


def _get_submitted_attendance_row_for_employee_day(employee, attendance_date, shift=None):
	"""Best submitted Attendance row for employee on a date (prefer matching shift, then Absent)."""
	attendance_date = getdate(attendance_date)
	rows = frappe.get_all(
		"Attendance",
		filters={"employee": employee, "attendance_date": attendance_date, "docstatus": 1},
		fields=["name", "status", "shift", "company"],
		order_by="modified desc",
	)
	if not rows:
		return None
	if shift:
		for row in rows:
			if row.shift == shift:
				return row
	for row in rows:
		if row.status == "Absent":
			return row
	return rows[0]


def get_absent_attendance_with_checkins_candidates(
	from_date=None, to_date=None, company=None, limit=500
):
	"""
	Submitted Absent attendance that has Employee Check-in(s) on the same calendar day.
	"""
	date_filters = _attendance_list_date_filters(from_date, to_date)
	company_sql = "AND a.company = %(company)s" if company else ""
	params = {"company": company} if company else {}

	date_sql = ""
	if date_filters.get("attendance_date"):
		op = date_filters["attendance_date"]
		if isinstance(op, list) and op[0] == "between":
			date_sql = "AND a.attendance_date BETWEEN %(from_d)s AND %(to_d)s"
			params["from_d"], params["to_d"] = op[1]
		elif isinstance(op, list) and op[0] == ">=":
			date_sql = "AND a.attendance_date >= %(from_d)s"
			params["from_d"] = op[1]
		elif isinstance(op, list) and op[0] == "<=":
			date_sql = "AND a.attendance_date <= %(to_d)s"
			params["to_d"] = op[1]

	rows = frappe.db.sql(
		f"""
		SELECT DISTINCT a.name, a.employee, a.company, a.attendance_date, a.shift
		FROM `tabAttendance` a
		WHERE a.docstatus = 1
			AND a.status = 'Absent'
			{date_sql}
			{company_sql}
			AND EXISTS (
				SELECT 1 FROM `tabEmployee Checkin` c
				WHERE c.employee = a.employee
					AND (
						DATE(c.time) = a.attendance_date
						OR DATE(c.shift_start) = a.attendance_date
					)
					/* includes skip_auto_attendance = 1 after failed duplicate attendance */
			)
		ORDER BY a.attendance_date ASC, a.modified ASC
		LIMIT {cint(limit) if limit else 500}
		""",
		params,
		as_dict=True,
	)

	candidates = []
	for row in rows:
		if employee_has_attendance_exception_on_date(row.employee, row.attendance_date):
			continue
		candidates.append(
			{
				"type": "absent_with_checkins",
				"attendance": row.name,
				"employee": row.employee,
				"shift": row.shift,
				"attendance_date": row.attendance_date,
				"company": row.company,
			}
		)
	return candidates


def _get_unlinked_checkins_for_date_range(from_date=None, to_date=None, company=None, limit=5000):
	"""Check-ins not linked to attendance and employee has no submitted Attendance that day."""
	params = {}
	conditions = [
		"(c.attendance IS NULL OR c.attendance = '')",
		"(c.offshift = 1 OR (c.shift IS NOT NULL AND c.shift != ''))",
		"""NOT EXISTS (
			SELECT 1 FROM `tabAttendance` a
			WHERE a.employee = c.employee
				AND a.docstatus < 2
				AND a.attendance_date = DATE(COALESCE(c.shift_start, c.time))
		)""",
	]
	if company:
		conditions.append("e.company = %(company)s")
		params["company"] = company
	if from_date and to_date:
		conditions.append(
			"(c.time BETWEEN %(day_start)s AND %(day_end)s OR c.shift_start BETWEEN %(day_start)s AND %(day_end)s)"
		)
		params["day_start"] = datetime.combine(getdate(from_date), time.min)
		params["day_end"] = datetime.combine(getdate(to_date), time.max)
	elif from_date:
		conditions.append(
			"(c.time >= %(day_start)s OR c.shift_start >= %(day_start)s)"
		)
		params["day_start"] = datetime.combine(getdate(from_date), time.min)
	elif to_date:
		conditions.append(
			"(c.time <= %(day_end)s OR c.shift_start <= %(day_end)s)"
		)
		params["day_end"] = datetime.combine(getdate(to_date), time.max)

	limit_sql = f"LIMIT {cint(limit)}" if limit else ""
	join_employee = "INNER JOIN `tabEmployee` e ON e.name = c.employee" if company else ""
	return frappe.db.sql(
		f"""
		SELECT c.name, c.employee, c.shift, c.shift_start, c.time, c.offshift
		FROM `tabEmployee Checkin` c
		{join_employee}
		WHERE {" AND ".join(conditions)}
		ORDER BY c.employee ASC, c.shift_start ASC, c.time ASC
		{limit_sql}
		""",
		params,
		as_dict=True,
	)


def get_checkin_groups_without_attendance_candidates(
	from_date=None, to_date=None, company=None, limit=500, exclude_keys=None
):
	"""
	Employee Check-in groups (employee + shift + day) with no linked attendance and
	no submitted Attendance on that calendar date (filtered in SQL).
	"""
	exclude_keys = exclude_keys or set()
	checkins = _get_unlinked_checkins_for_date_range(
		from_date=from_date,
		to_date=to_date,
		company=company,
		limit=(cint(limit) if limit else 500) * 20,
	)

	from collections import defaultdict

	grouped = defaultdict(list)
	for row in checkins:
		if row.shift_start:
			attendance_date = getdate(get_datetime(row.shift_start))
		elif row.time:
			attendance_date = getdate(get_datetime(row.time))
		else:
			continue
		shift = _resolve_checkin_shift(row.employee, row.shift)
		if not shift:
			continue
		key = _attendance_shift_key(row.employee, shift, attendance_date)
		if key in exclude_keys:
			continue
		grouped[key].append(row.name)

	candidates = []
	for (employee, shift, attendance_date), checkin_names in grouped.items():
		if len(candidates) >= cint(limit or 500):
			break
		if employee_has_attendance_exception_on_date(employee, attendance_date):
			continue

		candidates.append(
			{
				"type": "checkins_without_attendance",
				"employee": employee,
				"shift": shift,
				"attendance_date": attendance_date,
				"checkin_names": checkin_names,
				"company": frappe.db.get_value("Employee", employee, "company"),
			}
		)
	return candidates


def get_fix_absent_with_checkins_candidates(from_date=None, to_date=None, company=None, limit=500):
	"""All rows eligible for fix_absent_attendance_with_checkins_to_present."""
	absent_rows = get_absent_attendance_with_checkins_candidates(
		from_date=from_date, to_date=to_date, company=company, limit=limit
	)
	keys = {
		_attendance_shift_key(r["employee"], r["shift"], r["attendance_date"]) for r in absent_rows
	}
	orphan_rows = get_checkin_groups_without_attendance_candidates(
		from_date=from_date,
		to_date=to_date,
		company=company,
		limit=limit,
		exclude_keys=keys,
	)
	remaining = (cint(limit) if limit else 500) - len(absent_rows)
	if remaining > 0:
		orphan_rows = orphan_rows[:remaining]
	return absent_rows + orphan_rows


def correct_absent_attendance_when_checkins_exist(doc, method=None):
	"""On submit: never keep Absent when check-ins exist on that day (incl. offshift)."""
	if doc.docstatus != 1 or doc.status != "Absent":
		return
	if getattr(doc.flags, "skip_correct_absent_from_checkins", False):
		return
	if employee_has_attendance_exception_on_date(doc.employee, doc.attendance_date):
		return
	ok, _reason = _apply_present_from_checkins_to_attendance(
		doc,
		force_present=True,
		checkin_shift=doc.shift or _resolve_checkin_shift(doc.employee),
		add_comment=True,
		ignore_should_mark=True,
	)
	if ok:
		doc.reload()


def _apply_present_from_checkins_to_attendance(
	attendance_doc,
	*,
	force_present=True,
	checkin_shift=None,
	add_comment=True,
	ignore_should_mark=False,
):
	"""
	Update submitted attendance from check-ins. When force_present is True, status is
	set to Present (corrective action for mistaken Absent / low-hours cases).

	Returns (success, failure_reason).
	"""
	log_rows = _get_checkin_rows_for_attendance(
		attendance_doc,
		checkin_shift=checkin_shift,
		include_all_shifts_on_day=True,
	)
	if not log_rows:
		return False, _("No check-ins found for this date")

	_clear_skip_auto_attendance_for_checkins([r.name for r in log_rows])

	# Keep Present on the shift already set on Absent (assigned shift), not the check-in shift.
	attendance_shift = (
		attendance_doc.shift
		or checkin_shift
		or _resolve_checkin_shift(attendance_doc.employee)
	)
	if not attendance_shift:
		return False, _("Employee has no shift on attendance or default shift")
	if not attendance_doc.shift:
		frappe.db.set_value(
			"Attendance",
			attendance_doc.name,
			"shift",
			attendance_shift,
			update_modified=False,
		)
		attendance_doc.shift = attendance_shift

	log_rows = _checkin_logs_for_attendance_shift(
		log_rows, attendance_shift, attendance_doc.attendance_date
	)
	shift_doc = frappe.get_doc("Shift Type", attendance_shift)
	if (
		not ignore_should_mark
		and hasattr(shift_doc, "should_mark_attendance")
		and not shift_doc.should_mark_attendance(
			attendance_doc.employee, getdate(attendance_doc.attendance_date)
		)
	):
		return False, _("Shift type does not mark attendance on this date (holiday / off day)")

	(
		attendance_status,
		working_hours,
		late_entry,
		early_exit,
		in_time,
		out_time,
	) = shift_doc.get_attendance(log_rows)

	leave_info = (
		shift_doc._check_leave_record(attendance_doc.employee, getdate(attendance_doc.attendance_date))
		if hasattr(shift_doc, "_check_leave_record")
		else None
	)
	if leave_info:
		attendance_status = leave_info["status"]
		if attendance_status == "On Leave":
			return False, _("Employee is on leave for this date")

	if force_present and attendance_status not in ("On Leave",):
		attendance_status = "Present"

	update_fields = {
		"working_hours": working_hours,
		"late_entry": cint(late_entry),
		"early_exit": cint(early_exit),
		"in_time": in_time,
		"out_time": out_time,
		"status": attendance_status,
	}
	if leave_info:
		update_fields["leave_type"] = leave_info.get("leave_type")
		update_fields["leave_application"] = leave_info.get("leave_application")
		if attendance_status == "Half Day":
			update_fields["half_day_status"] = "Present"
			update_fields["modify_half_day_status"] = 0
	else:
		update_fields["leave_type"] = None
		update_fields["leave_application"] = None

	frappe.db.set_value("Attendance", attendance_doc.name, update_fields, update_modified=True)
	checkin_names = [r.name for r in log_rows]
	update_attendance_in_checkins(checkin_names, attendance_doc.name)

	EmployeeCheckin = frappe.qb.DocType("Employee Checkin")
	(
		frappe.qb.update(EmployeeCheckin)
		.set("skip_auto_attendance", 0)
		.where(EmployeeCheckin.name.isin(checkin_names))
	).run()

	if add_comment:
		frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Comment",
				"reference_doctype": "Attendance",
				"reference_name": attendance_doc.name,
				"content": _(
					"Status set to Present because Employee Check-in(s) exist on this date (offshift included)."
				),
			}
		).insert(ignore_permissions=True)
	return True, None


def _insert_submitted_present_attendance(employee, shift, attendance_date, log_rows):
	"""Create and submit Present attendance (bulk fix; bypasses inactive employee validate)."""
	attendance_date = getdate(attendance_date)
	shift_doc = frappe.get_doc("Shift Type", shift)
	log_rows = _checkin_logs_for_attendance_shift(log_rows, shift, attendance_date)
	(
		_attendance_status,
		working_hours,
		late_entry,
		early_exit,
		in_time,
		out_time,
	) = shift_doc.get_attendance(log_rows)

	doc = frappe.new_doc("Attendance")
	doc.update(
		{
			"employee": employee,
			"attendance_date": attendance_date,
			"status": "Present",
			"shift": shift,
			"company": frappe.db.get_value("Employee", employee, "company"),
			"working_hours": working_hours,
			"late_entry": cint(late_entry),
			"early_exit": cint(early_exit),
			"in_time": in_time,
			"out_time": out_time,
		}
	)
	doc.flags.ignore_permissions = True
	doc.flags.ignore_validate = True
	doc.insert()
	doc.flags.ignore_validate = True
	doc.submit()

	checkin_names = [r.name for r in log_rows]
	update_attendance_in_checkins(checkin_names, doc.name)
	_clear_skip_auto_attendance_for_checkins(checkin_names)

	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": "Attendance",
			"reference_name": doc.name,
			"content": _(
				"Present attendance created via Attendance list action (check-ins existed without attendance)."
			),
		}
	).insert(ignore_permissions=True)
	return doc.name


def create_attendance_for_checkins_without_attendance(
	employee, shift, attendance_date, checkin_names
):
	"""Create submitted Present attendance and link check-ins (no open attendance row that day)."""
	attendance_date = getdate(attendance_date)
	_clear_skip_auto_attendance_for_checkins(checkin_names)

	open_attendance = frappe.get_all(
		"Attendance",
		filters={
			"employee": employee,
			"attendance_date": attendance_date,
			"docstatus": ["<", 2],
		},
		fields=["name", "status", "docstatus", "shift"],
		order_by="modified desc",
		limit=1,
	)
	if open_attendance:
		row = open_attendance[0]
		attendance_doc = frappe.get_doc("Attendance", row.name)
		if row.docstatus == 1:
			if row.status == "Absent":
				ok, _reason = _apply_present_from_checkins_to_attendance(
					attendance_doc,
					force_present=True,
					checkin_shift=shift or attendance_doc.shift,
					add_comment=True,
					ignore_should_mark=True,
				)
				return attendance_doc.name if ok else None
			update_attendance_in_checkins(checkin_names, row.name)
			return row.name
		if row.docstatus == 0:
			ok, _reason = _apply_present_from_checkins_to_attendance(
				attendance_doc,
				force_present=True,
				checkin_shift=shift or attendance_doc.shift or _resolve_checkin_shift(employee),
				add_comment=False,
				ignore_should_mark=True,
			)
			if ok:
				attendance_doc.reload()
				if attendance_doc.docstatus == 0:
					attendance_doc.flags.ignore_permissions = True
					attendance_doc.flags.ignore_validate = True
					attendance_doc.submit()
				return attendance_doc.name
			return None

	if frappe.db.exists(
		"Attendance",
		{
			"employee": employee,
			"attendance_date": attendance_date,
			"shift": shift,
			"docstatus": 1,
		},
	):
		att_name = frappe.db.get_value(
			"Attendance",
			{
				"employee": employee,
				"attendance_date": attendance_date,
				"shift": shift,
				"docstatus": 1,
			},
			"name",
		)
		update_attendance_in_checkins(checkin_names, att_name)
		return att_name

	log_rows = frappe.get_all(
		"Employee Checkin",
		filters={"name": ["in", checkin_names]},
		fields=[
			"name",
			"employee",
			"log_type",
			"time",
			"shift",
			"shift_start",
			"shift_end",
			"shift_actual_start",
			"shift_actual_end",
		],
		order_by="time asc",
	)
	if not log_rows:
		return None

	try:
		return _insert_submitted_present_attendance(employee, shift, attendance_date, log_rows)
	except Exception:
		frappe.log_error(
			title="Failed to create Present attendance from check-ins",
			message=frappe.get_traceback(),
		)
		return None


def _create_present_attendance_from_checkins(employee, shift, attendance_date, checkin_names):
	"""Create Present attendance or update existing submitted Absent for the same shift/day."""
	existing = frappe.db.get_value(
		"Attendance",
		{
			"employee": employee,
			"attendance_date": getdate(attendance_date),
			"shift": shift,
			"docstatus": 1,
			"status": "Absent",
		},
		"name",
	)
	if existing:
		attendance_doc = frappe.get_doc("Attendance", existing)
		ok, _reason = _apply_present_from_checkins_to_attendance(
			attendance_doc,
			force_present=True,
			checkin_shift=shift,
			ignore_should_mark=True,
		)
		if ok:
			return attendance_doc.name
		return None

	return create_attendance_for_checkins_without_attendance(
		employee, shift, attendance_date, checkin_names
	)


def fix_absent_attendance_with_checkins_to_present(
	from_date=None, to_date=None, company=None, limit=500
):
	"""
	Mark Absent attendance as Present when check-ins exist, and create Present
	attendance for check-in groups that have no attendance record.
	"""
	candidates = get_fix_absent_with_checkins_candidates(
		from_date=from_date, to_date=to_date, company=company, limit=limit
	)
	if not candidates:
		return {
			"processed": 0,
			"updated": [],
			"created": [],
			"skipped": [],
			"skipped_details": [],
			"candidates": 0,
		}

	updated = []
	created = []
	skipped = []
	skipped_details = []

	for row in candidates:
		try:
			if row["type"] == "absent_with_checkins":
				attendance_doc = frappe.get_doc("Attendance", row["attendance"])
				if attendance_doc.status != "Absent":
					skipped.append(row["attendance"])
					skipped_details.append(
						{"id": row["attendance"], "reason": _("Already not Absent")}
					)
					continue
				resolved_shift = _resolve_checkin_shift(
					row["employee"], row.get("shift")
				)
				ok, reason = _apply_present_from_checkins_to_attendance(
					attendance_doc,
					force_present=True,
					checkin_shift=resolved_shift,
					ignore_should_mark=True,
				)
				if not ok:
					skipped.append(row["attendance"])
					skipped_details.append(
						{
							"id": row["attendance"],
							"reason": reason or _("Could not update attendance from check-ins"),
						}
					)
					continue
				frappe.db.commit()
				updated.append(row["attendance"])
				try:
					attendance_doc.reload()
					cancel_attendance_linked_additional_salaries(row["attendance"])
					attendance_on_submit(attendance_doc, "fix_present")
					frappe.db.commit()
				except Exception:
					frappe.log_error(
						title="Present set but Additional Salary recalc failed",
						message=frappe.get_traceback(),
					)
			elif row["type"] == "checkins_without_attendance":
				name = create_attendance_for_checkins_without_attendance(
					row["employee"],
					row["shift"],
					row["attendance_date"],
					row["checkin_names"],
				)
				if name:
					frappe.db.commit()
					created.append(name)
					try:
						attendance_doc = frappe.get_doc("Attendance", name)
						attendance_on_submit(attendance_doc, "fix_present")
						frappe.db.commit()
					except Exception:
						frappe.db.rollback()
						frappe.log_error(
							title="Present created but Additional Salary recalc failed",
							message=frappe.get_traceback(),
						)
				else:
					row_id = f"{row['employee']}|{row['shift']}|{row['attendance_date']}"
					skipped.append(row_id)
					emp_status = frappe.db.get_value("Employee", row["employee"], "status")
					open_att = frappe.db.exists(
						"Attendance",
						{
							"employee": row["employee"],
							"attendance_date": getdate(row["attendance_date"]),
							"docstatus": ["<", 2],
						},
					)
					reason = _("Could not create attendance (employee status: {0})").format(
						emp_status or "?"
					)
					if open_att:
						reason = _("Open attendance already exists: {0}").format(open_att)
					skipped_details.append({"id": row_id, "reason": reason})
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				title="Failed to fix Absent attendance with check-ins",
				message=frappe.get_traceback(),
			)
			row_id = row.get("attendance") or row.get("employee")
			skipped.append(row_id)
			skipped_details.append({"id": row_id, "reason": _("Unexpected error — see Error Log")})

	return {
		"processed": len(updated) + len(created),
		"updated": updated,
		"created": created,
		"skipped": skipped,
		"skipped_details": skipped_details[:50],
		"candidates": len(candidates),
	}


@frappe.whitelist()
def preview_fix_absent_attendance_with_checkins_to_present(
	from_date=None, to_date=None, company=None, limit=500
):
	"""Return how many rows would be fixed (for debugging before queueing)."""
	candidates = get_fix_absent_with_checkins_candidates(
		from_date=from_date, to_date=to_date, company=company, limit=limit
	)
	absent_count = sum(1 for c in candidates if c["type"] == "absent_with_checkins")
	orphan_count = sum(1 for c in candidates if c["type"] == "checkins_without_attendance")
	date_filters = _attendance_list_date_filters(from_date, to_date, fieldname="a.attendance_date")
	extra_sql = ""
	params = {}
	if company:
		extra_sql += " AND a.company = %(company)s"
		params["company"] = company
	if date_filters.get("attendance_date"):
		op = date_filters["attendance_date"]
		if isinstance(op, list) and op[0] == "between":
			extra_sql += " AND a.attendance_date BETWEEN %(from_d)s AND %(to_d)s"
			params["from_d"], params["to_d"] = op[1]
		elif isinstance(op, list) and op[0] == ">=":
			extra_sql += " AND a.attendance_date >= %(from_d)s"
			params["from_d"] = op[1]
		elif isinstance(op, list) and op[0] == "<=":
			extra_sql += " AND a.attendance_date <= %(to_d)s"
			params["to_d"] = op[1]

	skipped_checkin_count = frappe.db.sql(
		f"""
		SELECT COUNT(DISTINCT a.name)
		FROM `tabAttendance` a
		INNER JOIN `tabEmployee Checkin` c
			ON c.employee = a.employee
			AND c.skip_auto_attendance = 1
			AND (
				DATE(c.time) = a.attendance_date
				OR DATE(c.shift_start) = a.attendance_date
			)
		WHERE a.docstatus = 1
			AND a.status = 'Absent'
			{extra_sql}
		""",
		params,
	)[0][0]
	return {
		"total": len(candidates),
		"absent_with_checkins": absent_count,
		"checkins_without_attendance": orphan_count,
		"absent_with_skipped_checkins": skipped_checkin_count,
	}


@frappe.whitelist()
def enqueue_fix_absent_attendance_with_checkins_to_present(
	from_date=None, to_date=None, company=None, limit=500, run_now=1
):
	"""Queue (or run immediately) fix for Absent / missing attendance when check-ins exist."""
	if cint(run_now):
		result = fix_absent_attendance_with_checkins_to_present(
			from_date=from_date, to_date=to_date, company=company, limit=limit
		)
		return {"status": "completed", **result}

	job = frappe.enqueue(
		"acc_egypt_cust.acc_egypt_cust.doc_events.attendance.fix_absent_attendance_with_checkins_to_present",
		queue="long",
		timeout=60 * 60,
		job_name="fix_absent_attendance_with_checkins_to_present",
		from_date=from_date,
		to_date=to_date,
		company=company,
		limit=limit,
	)
	return {
		"status": "queued",
		"job_id": job.id if job else None,
		"message": _(
			"Job queued. Enable 'Run now' to see results immediately, or open RQ Job after the worker runs."
		),
	}