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
from typing import List, Optional, Tuple
import pandas as pd


class EconomicEvent:
    """Đại diện cho 1 sự kiện kinh tế quan trọng."""
    def __init__(self, timestamp: datetime, event_name: str, impact: str = "HIGH"):
        if timestamp.tzinfo is None:
            self.timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            self.timestamp = timestamp.astimezone(timezone.utc)
        self.event_name = event_name
        self.impact = impact

    def in_blackout_window(
        self,
        current_time: datetime,
        minutes_before: int = 15,
        minutes_after: int = 15
    ) -> bool:
        """Kiểm tra current_time có nằm trong [event - before, event + after] không."""
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        else:
            current_time = current_time.astimezone(timezone.utc)

        start_window = self.timestamp - timedelta(minutes=minutes_before)
        end_window = self.timestamp + timedelta(minutes=minutes_after)
        return start_window <= current_time <= end_window


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
        """Đọc danh sách sự kiện từ file CSV."""
        path = Path(file_path)
        if not path.exists():
            self.events = []
            return

        try:
            df = pd.read_csv(path)
            time_col = "datetime_utc" if "datetime_utc" in df.columns else "timestamp"
            name_col = "event" if "event" in df.columns else "event_name"
            impact_col = "impact" if "impact" in df.columns else None

            loaded = []
            for _, row in df.iterrows():
                dt = pd.to_datetime(row[time_col])
                if pd.isna(dt):
                    continue
                name = str(row[name_col])
                impact = str(row[impact_col]) if impact_col else "HIGH"
                loaded.append(EconomicEvent(timestamp=dt, event_name=name, impact=impact))
            self.events = loaded
        except Exception:
            self.events = []

    def is_in_blackout(self, check_time: datetime) -> Tuple[bool, Optional[str]]:
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
