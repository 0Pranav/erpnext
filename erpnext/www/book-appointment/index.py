import frappe
import datetime
import json
import pytz


WEEKDAYS = ["Monday", "Tuesday", "Wednesday",
            "Thursday", "Friday", "Saturday", "Sunday"]

no_cache = 1


@frappe.whitelist(allow_guest=True)
def get_appointment_settings():
    settings = frappe.get_doc('Appointment Booking Settings')
    return settings


@frappe.whitelist(allow_guest=True)
def get_holiday_list(holiday_list_name):
    holiday_list = frappe.get_doc('Holiday List', holiday_list_name)
    return holiday_list


@frappe.whitelist(allow_guest=True)
def get_timezones():
    timezones = frappe.get_list('Timezone', fields='*')
    return pytz.all_timezones


@frappe.whitelist(allow_guest=True)
def get_appointment_slots(date, timezone):
    import pytz
    guest_timezone = pytz.timezone(timezone)
    format_string = '%Y-%m-%d %H:%M:%S'
    query_start_time = datetime.datetime.strptime(
        date + ' 00:00:00', format_string)
    query_end_time = datetime.datetime.strptime(
        date + ' 23:59:59', format_string)
    local_timezone = frappe.utils.get_time_zone()
    local_timezone = pytz.timezone(local_timezone)
    query_start_time = guest_timezone.localize(query_start_time)
    query_end_time = guest_timezone.localize(query_end_time)
    query_start_time = query_start_time.astimezone(local_timezone)
    query_end_time = query_end_time.astimezone(local_timezone)
    now = datetime.datetime.now()
    # now = local_timezone.localize(now)
    # Database queries
    settings = frappe.get_doc('Appointment Booking Settings')
    holiday_list = frappe.get_doc('Holiday List', settings.holiday_list)
    timeslots = get_available_slots_between(
        query_start_time, query_end_time, settings)

    # Filter timeslots based on date
    converted_timeslots = []
    for timeslot in timeslots:
        timeslot = local_timezone.localize(timeslot)
        print(timeslot)
        timeslot = timeslot.astimezone(guest_timezone)
        timeslot = timeslot.replace(tzinfo=None)
        # Check if holiday
        if _is_holiday(timeslot.date(), holiday_list):
            converted_timeslots.append(
                dict(time=timeslot, availability=False))
            continue
        # Check availability
        if check_availabilty(timeslot, settings) and timeslot >= now:
            converted_timeslots.append(
                dict(time=timeslot, availability=True))
        else:
            converted_timeslots.append(
                dict(time=timeslot, availability=False))
    date_required = datetime.datetime.strptime(
        date + ' 00:00:00', format_string).date()
    converted_timeslots = filter_timeslots(date_required, converted_timeslots)
    return converted_timeslots


def get_available_slots_between(query_start_time, query_end_time, settings):
    records = _get_records(query_start_time, query_end_time, settings)
    timeslots = []
    appointment_duration = datetime.timedelta(
        minutes=settings.appointment_duration)
    for record in records:
        if record.day_of_week == WEEKDAYS[query_start_time.weekday()]:
            current_time = _deltatime_to_datetime(
                query_start_time, record.from_time)
            end_time = _deltatime_to_datetime(
                query_start_time, record.to_time)
        else:
            current_time = _deltatime_to_datetime(
                query_end_time, record.from_time)
            end_time = _deltatime_to_datetime(
                query_end_time, record.to_time)
        while current_time + appointment_duration <= end_time:
            timeslots.append(current_time)
            current_time += appointment_duration
    return timeslots


@frappe.whitelist(allow_guest=True)
def create_appointment(date, time, contact):
    appointment = frappe.new_doc('Appointment')
    format_string = '%Y-%m-%d %H:%M:%S'
    appointment.scheduled_time = datetime.datetime.strptime(
        date+" "+time, format_string)
    contact = json.loads(contact)
    appointment.customer_name = contact['name']
    appointment.customer_phone_number = contact['number']
    appointment.customer_skype = contact['skype']
    appointment.customer_details = contact['notes']
    appointment.customer_email = contact['email']
    appointment.status = 'Open'
    appointment.insert()


# Helper Functions
def filter_timeslots(date, timeslots):
    filtered_timeslots = []
    for timeslot in timeslots:
        if(timeslot['time'].date() == date):
            filtered_timeslots.append(timeslot)
    return filtered_timeslots

def check_availabilty(timeslot, settings):
    return frappe.db.count('Appointment', {'scheduled_time': timeslot}) < settings.number_of_agents

def _is_holiday(date, holiday_list):
    for holiday in holiday_list.holidays:
        if holiday.holiday_date == date:
            return True
    return False

def _get_records(start_time, end_time, settings):
    records = []
    for record in settings.availability_of_slots:
        if record.day_of_week == WEEKDAYS[start_time.weekday()] or record.day_of_week == WEEKDAYS[end_time.weekday()]:
            records.append(record)
    return records

def _deltatime_to_datetime(date, deltatime):
    time = (datetime.datetime.min + deltatime).time()
    return datetime.datetime.combine(date.date(), time)

def _datetime_to_deltatime(date_time):
    midnight = datetime.datetime.combine(date_time.date(), datetime.time.min)
    return (date_time-midnight)