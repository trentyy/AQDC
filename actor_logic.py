"""actor.py 的純邏輯（不依賴資料庫與雲端 API，方便單元測試）。"""
from datetime import datetime, timedelta
from typing import List, Optional, Tuple


def is_in_time_range(cur: timedelta, start: timedelta, end: timedelta) -> bool:
    """cur 是否落在 [start, end)。

    - 起點含、終點不含（原本是兩端都不含，整點那一分鐘會漏掉）
    - start > end 視為跨午夜，例如 22:00~06:00
    - start == end 視為空區間
    """
    if start < end:
        return start <= cur < end
    if start > end:
        return cur >= start or cur < end
    return False


def pick_state(states: List[dict], cur: timedelta, in_home: bool) -> dict:
    """依時間與在家狀態挑出要套用的狀態設定。

    都不符合時，明確退回 state 編號最小的那一筆（與舊版行為相同，
    舊版是靠 for 迴圈變數殘留的最後一筆，而 states 以 state DESC 排序）。
    states 為空時丟出 ValueError，由主迴圈記錄後略過這一輪。
    """
    if not states:
        raise ValueError("table actor_RD-200HH1 has no state rows")
    for state in states:
        if (is_in_time_range(cur, state["start_time"], state["end_time"])
                and bool(state["in_home"]) == in_home):
            return state
    return min(states, key=lambda s: s["state"])


class PresenceDetector:
    """以 CO2 判斷是否在家，加入平均、遲滯、離家延遲與資料新鮮度檢查。

    - 進入在家：最近 window_minutes 的平均 CO2 > home_ppm
    - 離開在家：平均 CO2 < away_ppm 且持續 away_minutes 分鐘
    - away_ppm ~ home_ppm 之間維持原狀態（遲滯），避免開窗或短暫外出造成來回切換
    - 最新一筆資料超過 stale_minutes 沒更新 -> 感測器可能壞了，維持原狀態
    """

    def __init__(self, home_ppm=600, away_ppm=500, away_minutes=30,
                 window_minutes=10, stale_minutes=15, initial=True):
        self.home_ppm = home_ppm
        self.away_ppm = away_ppm
        self.away_minutes = away_minutes
        self.window_minutes = window_minutes
        self.stale_minutes = stale_minutes
        self.in_home = initial  # 開機且沒有可用資料時，保守地當作在家
        self.stale = False
        self._away_since: Optional[datetime] = None

    def update(self, samples: List[Tuple[datetime, Optional[float]]], now: datetime) -> bool:
        """samples: [(時間, co2), ...]，由新到舊。回傳目前是否在家。"""
        valid = [(t, c) for t, c in samples if c is not None and c >= 300]
        if not valid or now - valid[0][0] > timedelta(minutes=self.stale_minutes):
            self.stale = True
            self._away_since = None
            return self.in_home
        self.stale = False

        window = [c for t, c in valid
                  if now - t <= timedelta(minutes=self.window_minutes)]
        # 最新資料比平均視窗舊但未達 stale 時，直接用最新一筆
        avg = sum(window) / len(window) if window else valid[0][1]

        if not self.in_home:
            if avg > self.home_ppm:
                self.in_home = True
            self._away_since = None
        else:
            if avg < self.away_ppm:
                if self._away_since is None:
                    self._away_since = now
                if now - self._away_since >= timedelta(minutes=self.away_minutes):
                    self.in_home = False
                    self._away_since = None
            else:
                self._away_since = None
        return self.in_home
