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


# -------------------------------------------------------------
# G3 Regression Tests: Readiness, Errors, and Fixture Injection
# -------------------------------------------------------------
def test_news_calendar_missing_file_marks_unready(tmp_path):
    """G3: Không tìm thấy file CSV -> is_ready=False, ghi nhận load_error rõ ràng."""
    missing_file = str(tmp_path / "does_not_exist.csv")
    cfg = {"news_filter": {"enabled": True, "calendar_file": missing_file}}

    filter_inst = NewsCalendarFilter(cfg)
    assert filter_inst.is_ready is False
    assert filter_inst.load_error is not None
    assert "CALENDAR_LOAD_ERROR" in filter_inst.load_error
    assert "Calendar file not found" in filter_inst.load_error

    # Khi không ready, is_in_blackout an toàn trả về (False, None)
    blocked, reason = filter_inst.is_in_blackout(datetime(2024, 1, 11, 13, 30, tzinfo=timezone.utc))
    assert blocked is False
    assert reason is None


def test_news_calendar_missing_columns_marks_unready(tmp_path):
    """G3: File CSV thiếu cột datetime_utc/timestamp hoặc event/event_name."""
    bad_csv = tmp_path / "missing_cols.csv"
    bad_csv.write_text("some_col,another_col\n1,2\n", encoding="utf-8")

    cfg = {"news_filter": {"enabled": True, "calendar_file": str(bad_csv)}}
    filter_inst = NewsCalendarFilter(cfg)
    assert filter_inst.is_ready is False
    assert "missing time column" in filter_inst.load_error

    # Test thiếu cột event name
    bad_csv2 = tmp_path / "missing_name.csv"
    bad_csv2.write_text("datetime_utc,another_col\n2024-01-11 13:30:00,2\n", encoding="utf-8")

    cfg2 = {"news_filter": {"enabled": True, "calendar_file": str(bad_csv2)}}
    filter_inst2 = NewsCalendarFilter(cfg2)
    assert filter_inst2.is_ready is False
    assert "missing event name column" in filter_inst2.load_error


def test_news_calendar_corrupted_row_marks_unready(tmp_path):
    """G3: File CSV chứa dòng có timestamp bị hỏng (NaT/rác) -> không nuốt lỗi, đánh dấu unready."""
    corrupt_csv = tmp_path / "corrupt.csv"
    corrupt_csv.write_text("datetime_utc,event,impact\nnot-a-valid-date,CPI,HIGH\n", encoding="utf-8")

    cfg = {"news_filter": {"enabled": True, "calendar_file": str(corrupt_csv)}}
    filter_inst = NewsCalendarFilter(cfg)
    assert filter_inst.is_ready is False
    assert "Malformed or unparseable row" in filter_inst.load_error


def test_news_calendar_empty_valid_csv_marks_ready(tmp_path):
    """G3: File CSV có schema hợp lệ nhưng rỗng (0 dòng sự kiện) -> is_ready=True, events=[]."""
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("datetime_utc,event,impact\n", encoding="utf-8")

    cfg = {"news_filter": {"enabled": True, "calendar_file": str(empty_csv)}}
    filter_inst = NewsCalendarFilter(cfg)
    assert filter_inst.is_ready is True
    assert filter_inst.load_error is None
    assert len(filter_inst.events) == 0

    blocked, reason = filter_inst.is_in_blackout(datetime(2024, 1, 11, 13, 30, tzinfo=timezone.utc))
    assert blocked is False
    assert reason is None


def test_news_calendar_reload_after_error_recovers_readiness(tmp_path):
    """G3: Khả năng phục hồi (reload) sau lỗi tải lịch."""
    file_path = tmp_path / "calendar.csv"
    # Ban đầu file chưa có
    cfg = {"news_filter": {"enabled": True, "calendar_file": str(file_path)}}
    filter_inst = NewsCalendarFilter(cfg)
    assert filter_inst.is_ready is False

    # Ghi file CSV hợp lệ
    file_path.write_text(
        "datetime_utc,event,impact\n2024-01-11 13:30:00,US CPI YoY,HIGH\n",
        encoding="utf-8"
    )

    # Nạp lại lịch
    filter_inst.load_calendar(str(file_path))
    assert filter_inst.is_ready is True
    assert filter_inst.load_error is None
    assert len(filter_inst.events) == 1


def test_news_calendar_set_events_fixture_support():
    """G3: set_events và gán trực tiếp events hỗ trợ các unit test fixture."""
    filter_inst = NewsCalendarFilter({"news_filter": {"enabled": True, "calendar_file": "dummy.csv"}})
    assert filter_inst.is_ready is False

    event = EconomicEvent(timestamp=datetime(2024, 1, 11, 13, 30, tzinfo=timezone.utc), event_name="FOMC")
    filter_inst.set_events([event], is_ready=True)
    assert filter_inst.is_ready is True
    assert filter_inst.load_error is None
    assert len(filter_inst.events) == 1

    # Thử set unready tường minh
    filter_inst.set_events([], is_ready=False)
    assert filter_inst.is_ready is False
