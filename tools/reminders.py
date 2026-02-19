"""iCloud Reminders tools — EventKit/PyObjC implementation.

Uses the macOS EventKit framework via PyObjC. No authentication is needed
because EventKit talks directly to Reminders.app, which is already signed
in to iCloud. Requires a one-time macOS permission grant on first run.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from dateutil import parser as dateparser

# EventKit constants
EK_ENTITY_TYPE_REMINDER = 1  # EKEntityTypeReminder


def _get_store() -> Any:
    """Return an authorised EKEventStore, requesting access if needed."""
    from EventKit import EKEventStore  # type: ignore[import]

    store = EKEventStore.alloc().init()
    granted_event = threading.Event()
    result_holder: list[bool] = []

    def handler(granted: bool, error: Any) -> None:
        result_holder.append(granted)
        granted_event.set()

    store.requestAccessToEntityType_completion_(EK_ENTITY_TYPE_REMINDER, handler)
    granted_event.wait(timeout=30)

    if not result_holder or not result_holder[0]:
        raise PermissionError(
            "Access to Reminders was denied. "
            "Grant access in System Settings → Privacy & Security → Reminders."
        )

    return store


def _fmt_reminder(reminder: Any) -> dict:
    due = ""
    if reminder.dueDateComponents():
        nscal = reminder.dueDateComponents()
        try:
            year = nscal.year()
            month = nscal.month()
            day = nscal.day()
            if year and month and day:
                due = f"{year:04d}-{month:02d}-{day:02d}"
        except Exception:  # noqa: BLE001
            due = ""

    return {
        "uid": str(reminder.calendarItemIdentifier()),
        "title": str(reminder.title() or ""),
        "description": str(reminder.notes() or ""),
        "completed": bool(reminder.isCompleted()),
        "due": due,
        "priority": int(reminder.priority()),
        "list": str(reminder.calendar().title() or ""),
    }


def list_lists() -> list[dict]:
    """Return all reminder lists."""
    from EventKit import EKEntityTypeReminder  # type: ignore[import]

    store = _get_store()
    calendars = store.calendarsForEntityType_(EKEntityTypeReminder)
    return [
        {
            "uid": str(cal.calendarIdentifier()),
            "title": str(cal.title() or ""),
        }
        for cal in calendars
    ]


def list_reminders(
    list_uid: str | None = None,
    include_completed: bool = False,
) -> list[dict]:
    """
    Return reminders, optionally filtered by list and completion status.

    Args:
        list_uid: Restrict to a specific reminder list UID.
        include_completed: Include completed reminders (default: False).
    """
    from EventKit import EKEntityTypeReminder  # type: ignore[import]

    store = _get_store()
    calendars = store.calendarsForEntityType_(EKEntityTypeReminder)

    if list_uid:
        calendars = [c for c in calendars if str(c.calendarIdentifier()) == list_uid]

    predicate = store.predicateForRemindersInCalendars_(calendars)

    result_holder: list[list] = []
    done_event = threading.Event()

    def completion(reminders: Any) -> None:
        result_holder.append(list(reminders) if reminders else [])
        done_event.set()

    store.fetchRemindersMatchingPredicate_completion_(predicate, completion)
    done_event.wait(timeout=30)

    all_reminders = result_holder[0] if result_holder else []
    results = [_fmt_reminder(r) for r in all_reminders]

    if not include_completed:
        results = [r for r in results if not r["completed"]]

    return results


def create_reminder(
    title: str,
    list_uid: str | None = None,
    due: str | None = None,
    description: str = "",
    priority: int = 0,
) -> dict:
    """
    Create a new reminder.

    Args:
        title: Reminder title.
        list_uid: Target list UID (uses default list if omitted).
        due: Optional ISO-8601 due date/time.
        description: Optional notes.
        priority: 0=none, 1=high, 5=medium, 9=low.

    Returns:
        The created reminder as a dict.
    """
    from EventKit import EKEntityTypeReminder, EKReminder  # type: ignore[import]
    from Foundation import NSCalendar, NSDateComponents  # type: ignore[import]

    store = _get_store()
    calendars = store.calendarsForEntityType_(EKEntityTypeReminder)

    if list_uid:
        cal = next(
            (c for c in calendars if str(c.calendarIdentifier()) == list_uid), None
        )
        if cal is None:
            raise ValueError(f"Reminder list '{list_uid}' not found.")
    else:
        cal = store.defaultCalendarForNewReminders()

    reminder = EKReminder.reminderWithEventStore_(store)
    reminder.setTitle_(title)
    reminder.setCalendar_(cal)
    reminder.setPriority_(priority)

    if description:
        reminder.setNotes_(description)

    if due:
        due_dt = dateparser.parse(due)
        nscal = NSCalendar.currentCalendar()
        units = (
            1 << 2  # NSCalendarUnitYear
            | 1 << 4  # NSCalendarUnitMonth
            | 1 << 5  # NSCalendarUnitDay
            | 1 << 6  # NSCalendarUnitHour
            | 1 << 7  # NSCalendarUnitMinute
        )
        from Foundation import NSDate  # type: ignore[import]

        ns_date = NSDate.dateWithTimeIntervalSince1970_(due_dt.timestamp())
        components = nscal.components_fromDate_(units, ns_date)
        reminder.setDueDateComponents_(components)

    error_holder: list[Any] = []
    success = store.saveReminder_commit_error_(reminder, True, None)
    if not success:
        raise RuntimeError("Failed to save reminder.")

    return _fmt_reminder(reminder)


def complete_reminder(uid: str) -> bool:
    """
    Mark a reminder as completed.

    Args:
        uid: The reminder's calendarItemIdentifier.

    Returns:
        True if found and marked complete, False if not found.
    """
    store = _get_store()
    reminder = store.calendarItemWithIdentifier_(uid)

    if reminder is None:
        return False

    reminder.setCompleted_(True)
    store.saveReminder_commit_error_(reminder, True, None)
    return True
