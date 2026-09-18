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
    """
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.news_cfg = self.config.get("news_filter", {})
        self.enabled: bool = bool(self.news_cfg.get("enabled", False))
        self.blackout_before: int = int(self.news_cfg.get("blackout_minutes_before", 15))
        self.blackout_after: int = int(self.news_cfg.get("blackout_minutes_after", 15))
        self.calendar_file: str = self.news_cfg.get("calendar_file", "data/news_calendar.csv")
        self.events: List[EconomicEvent] = []

        if self.enabled:
            self.load_calendar(self.calendar_file)

    def load_calendar(self, file_path: str) -> None:
        """
        Đọc danh sách sự kiện từ file CSV.
        Log warning chi tiết ở từng trường hợp lỗi (không swallow exception câm lặng).
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(
                "[NewsFilter] File lịch kinh tế không tồn tại: '{}'. "
                "Không có sự kiện nào được nạp, bộ lọc tin sẽ không chặn lệnh.",
                file_path
            )
            self.events = []
            return

        try:
            df = pd.read_csv(path)
            time_col = "datetime_utc" if "datetime_utc" in df.columns else ("timestamp" if "timestamp" in df.columns else None)
            if not time_col:
                logger.warning(
                    "[NewsFilter] File CSV '{}' thiếu cột thời gian ('datetime_utc' hoặc 'timestamp'). "
                    "Các cột hiện có: {}. Bỏ qua nạp lịch.",
                    file_path, list(df.columns)
                )
                self.events = []
                return

            name_col = "event" if "event" in df.columns else ("event_name" if "event_name" in df.columns else None)
            if not name_col:
                logger.warning(
                    "[NewsFilter] File CSV '{}' thiếu cột tên sự kiện ('event' hoặc 'event_name'). "
                    "Các cột hiện có: {}. Bỏ qua nạp lịch.",
                    file_path, list(df.columns)
                )
                self.events = []
                return

            impact_col = "impact" if "impact" in df.columns else None

            loaded = []
            for idx, row in df.iterrows():
                try:
                    dt = pd.to_datetime(row[time_col])
                    if pd.isna(dt):
                        logger.warning(
                            "[NewsFilter] Dòng {} trong '{}' có timestamp không hợp lệ (NaT), bỏ qua: {}",
                            idx, file_path, row.to_dict()
                        )
                        continue
                    name = str(row[name_col])
                    impact = str(row[impact_col]) if impact_col else "HIGH"
                    loaded.append(EconomicEvent(timestamp=dt, event_name=name, impact=impact))
                except Exception as row_err:
                    logger.warning(
                        "[NewsFilter] Lỗi parse dòng {} trong '{}': {}. Bỏ qua dòng này.",
                        idx, file_path, row_err
                    )
            self.events = loaded
            logger.info("[NewsFilter] Đã nạp thành công {} sự kiện kinh tế từ '{}'", len(self.events), file_path)
        except Exception as e:
            logger.warning(
                "[NewsFilter] Lỗi khi đọc file lịch kinh tế '{}': {}. "
                "Bộ lọc tin sẽ tạm thời rỗng.",
                file_path, e
            )
            self.events = []

    def is_in_blackout(self, check_time: Union[datetime, int, float, str]) -> Tuple[bool, Optional[str]]:
        """
        Kiểm tra thời điểm hiện tại có bị cấm giao dịch vì tin tức không.
        Returns:
            (True, event_name) nếu đang trong khung cấm tin.
            (False, None) nếu bình thường (hoặc nếu enabled=False).
        """
        if not self.enabled:
            return False, None

        for event in self.events:
            if event.in_blackout_window(check_time, self.blackout_before, self.blackout_after):
                return True, event.event_name

        return False, None
