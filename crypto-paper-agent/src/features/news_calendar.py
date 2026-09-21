"""
news_calendar.py - News Filter & Economic Calendar (Placeholder)
================================================================
Quản lý lịch kinh tế (CPI, FOMC, NFP) từ file CSV và kiểm tra
khoảng thời gian cấm mở lệnh (news blackout window: ±15 phút quanh sự kiện).

Theo quyết định mục 10.1:
- Mặc định: enabled = False (tạm thời không chặn lệnh).
- Slot đã sẵn sàng: khi người dùng chuẩn bị file CSV và bật enabled = True,
  module này sẽ tự động parse và kích hoạt chặn lệnh ở Risk Invariants.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union
import math
import hashlib
from io import BytesIO
import pandas as pd
from loguru import logger

def parse_utc_datetime(ts: Any) -> datetime:
    """Chuyển đổi timestamp bất kỳ (datetime, Unix seconds/ms, ISO string) thành UTC datetime."""
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    if isinstance(ts, (int, float)):
        if type(ts) is bool or not math.isfinite(float(ts)):
            raise ValueError(f"Invalid timestamp value: {ts}")
        val = float(ts)
        if val > 1e11:
            val = val / 1000.0
        try:
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as e:
            raise ValueError(f"Timestamp value out of valid platform range: {ts!r}") from e
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, OverflowError, OSError) as e:
            raise ValueError(f"Malformed or out-of-range ISO timestamp string: {ts!r}") from e
    raise TypeError(f"Unsupported timestamp type: {type(ts)}")


class EconomicEvent:
    """Đại diện cho 1 sự kiện kinh tế quan trọng."""
    def __init__(self, timestamp: Union[datetime, int, float, str], event_name: str, impact: str = "HIGH"):
        self.timestamp = parse_utc_datetime(timestamp)
        self.event_name = event_name
        self.impact = impact

    def in_blackout_window(
        self,
        current_time: Union[datetime, int, float, str],
        minutes_before: int = 15,
        minutes_after: int = 15
    ) -> bool:
        """Kiểm tra current_time có nằm trong [event - before, event + after] không."""
        dt = parse_utc_datetime(current_time)
        start_window = self.timestamp - timedelta(minutes=minutes_before)
        end_window = self.timestamp + timedelta(minutes=minutes_after)
        return start_window <= dt <= end_window



class NewsCalendarFilter:
    """
    Bộ lọc sự kiện vĩ mô theo lịch CSV.
    Nếu config news_filter.enabled == False -> luôn cho phép (no-op).
    Nếu config news_filter.enabled == True:
        - Bắt buộc phải có lịch hợp lệ và đã nạp thành công (is_ready = True).
        - Nếu file thiếu, không đọc được, sai schema hoặc timestamp hỏng -> is_ready = False,
          chặn mở lệnh tại cổng Risk Manager (INVARIANT_FAIL_NEWS_FILTER_NOT_READY / CALENDAR_LOAD_ERROR).
    """
    def __init__(
        self,
        config: Optional[dict] = None,
        events: Optional[List[EconomicEvent]] = None,
        is_ready: Optional[bool] = None,
    ):
        self.config = config or {}
        self.news_cfg = self.config.get("news_filter", {})
        self.enabled: bool = bool(self.news_cfg.get("enabled", False))
        self.blackout_before: int = int(self.news_cfg.get("blackout_minutes_before", 15))
        self.blackout_after: int = int(self.news_cfg.get("blackout_minutes_after", 15))
        self.calendar_file: str = self.news_cfg.get("calendar_file", "data/news_calendar.csv")
        self._events: List[EconomicEvent] = []
        self.is_ready: bool = True if not self.enabled else False
        self.load_error: Optional[str] = None
        self.source_sha256: Optional[str] = None

        if events is not None:
            self._events = list(events)
            self.is_ready = True if is_ready is None else bool(is_ready)
            self.load_error = None if self.is_ready else "Injected unready calendar"
        elif self.enabled:
            self.load_calendar(self.calendar_file)

    @property
    def events(self) -> List[EconomicEvent]:
        return self._events

    @events.setter
    def events(self, val: List[EconomicEvent]) -> None:
        self._events = list(val) if val is not None else []
        if self._events:
            self.is_ready = True
            self.load_error = None

    def set_events(self, events: List[EconomicEvent], is_ready: bool = True) -> None:
        """Cập nhật danh sách sự kiện và trạng thái readiness tường minh (cho tests/fixtures)."""
        self._events = list(events)
        self.is_ready = is_ready
        self.load_error = None if is_ready else "Calendar explicitly set to unready"

    def load_calendar(self, file_path: str) -> None:
        """
        Đọc danh sách sự kiện từ file CSV.
        Đảm bảo thiết lập rõ ràng trạng thái is_ready và load_error.
        Không âm thầm nuốt lỗi hoặc bỏ qua dòng HIGH hỏng.
        """
        path = Path(file_path)
        self.source_sha256 = None
        if not path.exists():
            self.load_error = f"CALENDAR_LOAD_ERROR: Calendar file not found: '{file_path}'"
            self.is_ready = False
            self._events = []
            logger.warning("[NewsFilter] {}", self.load_error)
            return

        try:
            content = path.read_bytes()
            self.source_sha256 = hashlib.sha256(content).hexdigest()
            df = pd.read_csv(BytesIO(content))
            time_col = "datetime_utc" if "datetime_utc" in df.columns else ("timestamp" if "timestamp" in df.columns else None)
            if not time_col:
                self.load_error = (
                    f"CALENDAR_LOAD_ERROR: File CSV '{file_path}' missing time column "
                    f"('datetime_utc' or 'timestamp'). Available columns: {list(df.columns)}"
                )
                self.is_ready = False
                self._events = []
                logger.warning("[NewsFilter] {}", self.load_error)
                return

            name_col = "event" if "event" in df.columns else ("event_name" if "event_name" in df.columns else None)
            if not name_col:
                self.load_error = (
                    f"CALENDAR_LOAD_ERROR: File CSV '{file_path}' missing event name column "
                    f"('event' or 'event_name'). Available columns: {list(df.columns)}"
                )
                self.is_ready = False
                self._events = []
                logger.warning("[NewsFilter] {}", self.load_error)
                return

            impact_col = "impact" if "impact" in df.columns else None

            # Nếu file CSV rỗng dữ liệu (chỉ có header hợp lệ) -> Hợp lệ và không có sự kiện
            if len(df) == 0:
                self._events = []
                self.is_ready = True
                self.load_error = None
                logger.info("[NewsFilter] File CSV '{}' hợp lệ nhưng không chứa dòng sự kiện nào.", file_path)
                return

            loaded = []
            for idx, row in df.iterrows():
                try:
                    raw_dt = row[time_col]
                    if pd.isna(raw_dt):
                        raise ValueError("Timestamp is NaN or NaT")
                    dt = pd.to_datetime(raw_dt)
                    if pd.isna(dt):
                        raise ValueError("Timestamp cannot be converted to valid datetime")
                    name = str(row[name_col]).strip()
                    if not name or name.lower() == "nan":
                        raise ValueError("Event name is empty or NaN")
                    impact = str(row[impact_col]).strip().upper() if impact_col and not pd.isna(row[impact_col]) else "HIGH"
                    loaded.append(EconomicEvent(timestamp=dt, event_name=name, impact=impact))
                except Exception as row_err:
                    self.load_error = f"CALENDAR_LOAD_ERROR: Malformed or unparseable row {idx} in '{file_path}': {row_err}"
                    self.is_ready = False
                    self._events = []
                    logger.warning("[NewsFilter] {}", self.load_error)
                    return

            self._events = loaded
            self.is_ready = True
            self.load_error = None
            logger.info("[NewsFilter] Đã nạp thành công {} sự kiện kinh tế từ '{}'", len(self._events), file_path)
        except Exception as e:
            self.load_error = f"CALENDAR_LOAD_ERROR: Error parsing calendar file '{file_path}': {e}"
            self.is_ready = False
            self._events = []
            logger.warning("[NewsFilter] {}", self.load_error)

    def is_in_blackout(self, check_time: Union[datetime, int, float, str]) -> Tuple[bool, Optional[str]]:
        """
        Kiểm tra thời điểm hiện tại có bị cấm giao dịch vì tin tức không.
        Returns:
            (True, event_name) nếu đang trong khung cấm tin.
            (False, None) nếu bình thường (hoặc nếu enabled=False hoặc chưa ready).
        """
        if not self.enabled or not self.is_ready:
            return False, None

        for event in self._events:
            if event.in_blackout_window(check_time, self.blackout_before, self.blackout_after):
                return True, event.event_name

        return False, None
