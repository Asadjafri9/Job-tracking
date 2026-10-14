"""Scheduler local-time resolution checks without a database dependency."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from app.worker import scheduler


def _at(local: str, tz_name: str) -> datetime:
    return datetime.strptime(local, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz_name))


def test_next_daily_run_returns_todays_nine_when_still_upcoming() -> None:
    now = _at("2026-10-14 05:00", "Asia/Karachi").astimezone(UTC)
    slot = scheduler.next_daily_run_utc("Asia/Karachi", now)
    assert slot.astimezone(ZoneInfo("Asia/Karachi")).strftime("%H:%M") == "09:00"
    assert slot == _at("2026-10-14 09:00", "Asia/Karachi").astimezone(UTC)


def test_next_daily_run_rolls_to_tomorrow_after_nine() -> None:
    now = _at("2026-10-14 09:00", "Asia/Karachi").astimezone(UTC)
    slot = scheduler.next_daily_run_utc("Asia/Karachi", now)
    assert slot == _at("2026-10-15 09:00", "Asia/Karachi").astimezone(UTC)


def test_next_daily_run_handles_utc_and_western_timezones() -> None:
    now = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
    assert scheduler.next_daily_run_utc("UTC", now) == datetime(2026, 10, 15, 9, tzinfo=UTC)
    # America/New_York is UTC-4 in October: it is 08:00 local, so today's
    # 09:00 EDT (13:00 UTC) is still upcoming.
    slot = scheduler.next_daily_run_utc("America/New_York", now)
    assert slot == datetime(2026, 10, 14, 13, tzinfo=UTC)


def test_next_daily_run_stays_on_local_time_across_dst_change() -> None:
    # US spring forward: 2026-03-08 02:00 -> 03:00; 09:00 exists both days.
    before = _at("2026-03-07 09:00", "America/New_York").astimezone(UTC)
    slot = scheduler.next_daily_run_utc("America/New_York", before)
    assert slot == _at("2026-03-08 09:00", "America/New_York").astimezone(UTC)
    assert slot == datetime(2026, 3, 8, 13, tzinfo=UTC)  # 09:00 EDT, not 14:00 UTC


def test_ambiguous_local_time_resolves_to_earliest_occurrence(monkeypatch) -> None:
    # US fall back: 2026-11-01 01:30 occurs twice (EDT then EST).
    monkeypatch.setattr(scheduler, "DAILY_LOCAL_TIME", dtime(1, 30))
    slot = scheduler._resolve_local_slot(ZoneInfo("America/New_York"), date(2026, 11, 1))
    assert slot == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)  # 01:30 EDT, the first pass


def test_nonexistent_local_time_resolves_to_next_valid_instant(monkeypatch) -> None:
    # 02:30 does not exist on the US spring-forward date.
    monkeypatch.setattr(scheduler, "DAILY_LOCAL_TIME", dtime(2, 30))
    slot = scheduler._resolve_local_slot(ZoneInfo("America/New_York"), date(2026, 3, 8))
    assert slot.astimezone(ZoneInfo("America/New_York")).strftime("%H:%M") == "03:00"
    assert slot == datetime(2026, 3, 8, 7, 0, tzinfo=UTC)


def test_next_daily_run_rejects_unknown_timezone() -> None:
    with pytest.raises(ZoneInfoNotFoundError):
        scheduler.next_daily_run_utc("Not/AZone", datetime.now(UTC))


def test_next_daily_run_is_strictly_after_reference() -> None:
    now = datetime(2026, 10, 14, 4, 0, tzinfo=UTC)  # exactly 09:00 Asia/Karachi
    slot = scheduler.next_daily_run_utc("Asia/Karachi", now)
    assert slot > now
    assert slot - now <= timedelta(hours=24)
