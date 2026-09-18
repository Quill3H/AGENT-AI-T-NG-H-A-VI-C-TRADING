"""
tests/test_news_calendar.py - Test cho News Calendar Filter
============================================================
Kiểm tra cơ chế đọc lịch CSV và xác định blackout window (±15 phút).
Theo quyết định 10.1: enabled=False mặc định.
"""
from datetime import datetime, timezone
import pytest
from src.features.news_calendar import EconomicEvent, NewsCalendarFilter


def test_economic_event_blackout_window():
    """Kiểm tra logic tính window ±15 phút của 1 sự kiện."""
    event_time = datetime(2024, 1, 11, 13, 30, tzinfo=timezone.utc)
    event = EconomicEvent(timestamp=event_time, event_name="US CPI YoY")

    # Đúng giờ sự kiện -> cấm
    assert event.in_blackout_window(datetime(2024, 1, 11, 13, 30, tzinfo=timezone.utc))

    # 10 phút trước -> cấm (trong 15m)
    assert event.in_blackout_window(datetime(2024, 1, 11, 13, 20, tzinfo=timezone.utc))

    # 14 phút sau -> cấm (trong 15m)
    assert event.in_blackout_window(datetime(2024, 1, 11, 13, 44, tzinfo=timezone.utc))

    # 16 phút trước -> không cấm
    assert not event.in_blackout_window(datetime(2024, 1, 11, 13, 14, tzinfo=timezone.utc))

    # 20 phút sau -> không cấm
    assert not event.in_blackout_window(datetime(2024, 1, 11, 13, 50, tzinfo=timezone.utc))


def test_news_filter_disabled_by_default(config):
    """Quyết định 10.1: Mặc định enabled=False thì luôn cho phép giao dịch."""
    assert config["news_filter"]["enabled"] is False

    news_filter = NewsCalendarFilter(config)
    # Thời điểm đúng lúc có tin CPI 2024-01-11 13:30:00
    check_time = datetime(2024, 1, 11, 13, 30, tzinfo=timezone.utc)
    is_blocked, reason = news_filter.is_in_blackout(check_time)

    # Do enabled=False nên không bao giờ bị block
    assert is_blocked is False
    assert reason is None


def test_news_filter_enabled_with_csv(config, project_root):
    """Khi bật enabled=True và có file CSV mẫu thì block đúng thời điểm."""
    test_cfg = dict(config)
    test_cfg["news_filter"] = dict(config["news_filter"])
    test_cfg["news_filter"]["enabled"] = True
    test_cfg["news_filter"]["calendar_file"] = str(project_root / "data" / "news_calendar.csv")

    news_filter = NewsCalendarFilter(test_cfg)
    assert len(news_filter.events) > 0

    # Test thời điểm CPI 2024-01-11 13:30:00
    hit_time = datetime(2024, 1, 11, 13, 35, tzinfo=timezone.utc)
    is_blocked, reason = news_filter.is_in_blackout(hit_time)
    assert is_blocked is True
    assert "CPI" in reason

    # Test thời điểm bình thường
    safe_time = datetime(2024, 1, 11, 15, 0, tzinfo=timezone.utc)
    is_blocked_safe, reason_safe = news_filter.is_in_blackout(safe_time)
    assert is_blocked_safe is False
    assert reason_safe is None
