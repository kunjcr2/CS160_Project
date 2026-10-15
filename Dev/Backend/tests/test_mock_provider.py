"""Tests for the fake doctor's office (MockHealthcareProvider). No database needed."""

from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.healthcare.interface import (
    BookingNotFoundError,
    ProviderUnavailableError,
    SlotUnavailableError,
)
from app.adapters.healthcare.mock import OFFICE_TZ, MockHealthcareProvider

CARDIO = "mock-prac-cardiology-1"


def local(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """A 2026 time in the office's time zone (California)."""
    return datetime(2026, month, day, hour, minute, tzinfo=OFFICE_TZ)


# Fixed "now": Sunday, Oct 18, 2026, 8:00 AM (California). Same result every day.
NOW = local(10, 18, 8)
MONDAY = (local(10, 19, 0), local(10, 20, 0))  # all of Monday, Oct 19


@pytest.fixture
def office() -> MockHealthcareProvider:
    return MockHealthcareProvider(now=lambda: NOW)


# ---------- Doctors and slots ----------


def test_three_fake_doctors(office):
    doctors = office.list_practitioners()
    assert len(doctors) == 3
    assert len({d.external_ref for d in doctors}) == 3  # ids are unique


def test_monday_has_14_slots_9_to_5_without_lunch(office):
    slots = office.find_slots(CARDIO, *MONDAY)
    local_starts = [s.starts_at.astimezone(OFFICE_TZ) for s in slots]
    assert len(slots) == 14
    assert local_starts[0] == local(10, 19, 9)
    assert local_starts[-1] == local(10, 19, 16, 30)
    assert all(t.hour != 12 for t in local_starts)
    assert all(s.ends_at - s.starts_at == timedelta(minutes=30) for s in slots)


def test_slots_are_returned_in_utc(office):
    slot = office.find_slots(CARDIO, *MONDAY)[0]
    assert slot.starts_at.utcoffset() == timedelta(0)
    assert slot.starts_at == datetime(2026, 10, 19, 16, 0, tzinfo=UTC)  # 9:00 PDT


def test_no_slots_on_weekend(office):
    assert office.find_slots(CARDIO, local(10, 24, 0), local(10, 26, 0)) == []


def test_past_slots_are_hidden():
    office = MockHealthcareProvider(now=lambda: local(10, 19, 10))  # Monday 10:00
    slots = office.find_slots(CARDIO, *MONDAY)
    assert slots[0].starts_at == local(10, 19, 10, 30)


def test_daylight_saving_change(office):
    # Daylight saving ends Sunday, Nov 1, 2026. After that, 9:00 AM is 17:00 UTC (not 16:00).
    slot = office.find_slots(CARDIO, local(11, 2, 0), local(11, 3, 0))[0]
    assert slot.starts_at == datetime(2026, 11, 2, 17, 0, tzinfo=UTC)


def test_unknown_doctor(office):
    assert office.find_slots("no-such-doctor", *MONDAY) == []
    with pytest.raises(SlotUnavailableError):
        office.book("no-such-doctor", local(10, 19, 9), "user-1")


# ---------- Booking and cancelling ----------


def test_book_takes_the_slot(office):
    start = local(10, 19, 9)
    booking = office.book(CARDIO, start, "user-1")
    assert booking.external_ref.startswith("mock-appt-")
    assert booking.starts_at == start
    assert booking.ends_at == start + timedelta(minutes=30)
    assert "Valley Heart Clinic" in booking.location

    free = [s.starts_at for s in office.find_slots(CARDIO, *MONDAY)]
    assert start not in free
    assert len(free) == 13


def test_same_slot_cannot_be_booked_twice(office):
    office.book(CARDIO, local(10, 19, 9), "user-1")
    with pytest.raises(SlotUnavailableError):
        office.book(CARDIO, local(10, 19, 9), "user-2")


def test_same_time_with_another_doctor_is_fine(office):
    office.book(CARDIO, local(10, 19, 9), "user-1")
    office.book("mock-prac-primary-care-1", local(10, 19, 9), "user-2")  # no error


@pytest.mark.parametrize(
    "starts_at",
    [
        local(10, 19, 12),  # lunch
        local(10, 19, 9, 15),  # not on :00 or :30
        local(10, 19, 17),  # office closed
        local(10, 24, 9),  # Saturday
        local(10, 16, 9),  # Friday before "now" = in the past
    ],
    ids=["lunch", "not-on-half-hour", "after-closing", "saturday", "in-the-past"],
)
def test_cannot_book_a_time_that_is_not_a_slot(office, starts_at):
    with pytest.raises(SlotUnavailableError):
        office.book(CARDIO, starts_at, "user-1")


def test_cancel_frees_the_slot(office):
    booking = office.book(CARDIO, local(10, 19, 9), "user-1")
    office.cancel(booking.external_ref)
    assert len(office.find_slots(CARDIO, *MONDAY)) == 14

    with pytest.raises(BookingNotFoundError):
        office.cancel(booking.external_ref)  # already cancelled


# ---------- Safety and failures ----------


def test_time_without_time_zone_is_refused(office):
    with pytest.raises(ValueError, match="timezone-aware"):
        office.find_slots(CARDIO, datetime(2026, 10, 19), datetime(2026, 10, 20))


def test_failure_rate_1_always_fails():
    office = MockHealthcareProvider(failure_rate=1.0, now=lambda: NOW)
    with pytest.raises(ProviderUnavailableError):
        office.list_practitioners()


def test_failure_rate_must_be_between_0_and_1():
    with pytest.raises(ValueError):
        MockHealthcareProvider(failure_rate=1.5)
