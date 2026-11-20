"""純邏輯單元測試：python -m unittest discover -s test -p "test_logic.py"（在專案根目錄執行）"""
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from actor_logic import PresenceDetector, is_in_time_range, pick_state  # noqa: E402
from sensor_parse import parse_payload  # noqa: E402


def h(hours, minutes=0):
    return timedelta(hours=hours, minutes=minutes)


class TimeRangeTest(unittest.TestCase):
    def test_boundaries(self):
        self.assertTrue(is_in_time_range(h(8), h(8), h(18)))    # 起點含
        self.assertFalse(is_in_time_range(h(18), h(8), h(18)))  # 終點不含
        self.assertTrue(is_in_time_range(h(0), h(0), h(6)))     # 00:00 不再漏掉

    def test_overnight(self):
        self.assertTrue(is_in_time_range(h(23), h(22), h(6)))
        self.assertTrue(is_in_time_range(h(3), h(22), h(6)))
        self.assertFalse(is_in_time_range(h(12), h(22), h(6)))

    def test_empty_range(self):
        self.assertFalse(is_in_time_range(h(8), h(8), h(8)))


class PickStateTest(unittest.TestCase):
    states = [  # 與資料庫一樣以 state DESC 排列
        {"state": 2, "in_home": 0, "start_time": h(0), "end_time": h(24)},
        {"state": 1, "in_home": 1, "start_time": h(8), "end_time": h(22)},
    ]

    def test_match(self):
        self.assertEqual(pick_state(self.states, h(10), True)["state"], 1)
        self.assertEqual(pick_state(self.states, h(10), False)["state"], 2)

    def test_fallback_is_lowest_state(self):
        self.assertEqual(pick_state(self.states, h(23), True)["state"], 1)

    def test_empty(self):
        with self.assertRaises(ValueError):
            pick_state([], h(10), True)


class PresenceTest(unittest.TestCase):
    now = datetime(2025, 1, 1, 12, 0)

    def samples(self, co2, minutes_ago=0, n=5):
        return [(self.now - timedelta(minutes=minutes_ago + i), co2) for i in range(n)]

    def test_enter_home(self):
        p = PresenceDetector(initial=False)
        self.assertTrue(p.update(self.samples(700), self.now))

    def test_hysteresis_keeps_state(self):
        p = PresenceDetector(initial=True)
        self.assertTrue(p.update(self.samples(550), self.now))   # 500~600 之間不變
        p = PresenceDetector(initial=False)
        self.assertFalse(p.update(self.samples(550), self.now))

    def test_leave_needs_delay(self):
        p = PresenceDetector(initial=True, away_minutes=30)
        self.assertTrue(p.update(self.samples(450), self.now))
        later = self.now + timedelta(minutes=31)
        self.assertFalse(p.update([(later - timedelta(minutes=i), 450) for i in range(5)], later))

    def test_rise_resets_away_timer(self):
        p = PresenceDetector(initial=True, away_minutes=30)
        p.update(self.samples(450), self.now)
        mid = self.now + timedelta(minutes=20)
        p.update([(mid - timedelta(minutes=i), 700) for i in range(5)], mid)
        end = self.now + timedelta(minutes=35)
        self.assertTrue(p.update([(end - timedelta(minutes=i), 450) for i in range(5)], end))

    def test_stale_keeps_state(self):
        p = PresenceDetector(initial=True)
        self.assertTrue(p.update(self.samples(400, minutes_ago=60), self.now))
        self.assertTrue(p.stale)
        self.assertTrue(p.update([], self.now))

    def test_invalid_values_ignored(self):
        p = PresenceDetector(initial=True)
        p.update([(self.now, 0), (self.now, None)], self.now)
        self.assertTrue(p.stale)


class ParsePayloadTest(unittest.TestCase):
    good = {
        "DS18B20": {"Temperature": 25.1},
        "DHT22": {"Temperature": 25.0, "Humidity": 60.5},
        "PMS7003": {"PM1": 3, "PM2_5": 5, "PM10": 6},
        "MHZ19B": {"CO2": 620, "Temperature": 26},
    }

    def test_all_good(self):
        rows, rejected = parse_payload(self.good)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rejected, [])

    def test_null_and_out_of_range(self):
        bad = dict(self.good)
        bad["DS18B20"] = {"Temperature": -127}
        bad["DHT22"] = {"Temperature": None, "Humidity": 60}
        bad["MHZ19B"] = {"CO2": 0, "Temperature": 26}
        rows, rejected = parse_payload(bad)
        self.assertEqual([r[0] for r in rows], ["home_pms7003"])
        self.assertEqual(len(rejected), 3)

    def test_missing_block(self):
        rows, rejected = parse_payload({})
        self.assertEqual(rows, [])
        self.assertEqual(len(rejected), 4)


if __name__ == "__main__":
    unittest.main()
