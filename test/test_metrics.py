"""Prometheus 指標測試：python -m unittest discover -s test -p "test_metrics.py"（在專案根目錄執行）"""
import json
import os
import socket
import sys
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sensor_metrics  # noqa: E402
from sensor_metrics import SensorMetrics, metrics_address  # noqa: E402
from sensor_parse import parse_payload  # noqa: E402

GOOD = {
    "DS18B20": {"Temperature": 25.1},
    "DHT22": {"Temperature": 25.0, "Humidity": 60.5},
    "PMS7003": {"PM1": 3, "PM2_5": 5, "PM10": 6},
    "MHZ19B": {"CO2": 620, "Temperature": 26},
}


def samples(text):
    """把輸出轉成 {'name{label="v"}': float}，忽略 HELP / TYPE。"""
    out = {}
    for line in text.splitlines():
        if line and not line.startswith("#"):
            key, value = line.rsplit(" ", 1)
            out[key] = float(value)
    return out


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class MetricsValuesTest(unittest.TestCase):
    def test_all_sensors(self):
        m = SensorMetrics()
        rows, _ = parse_payload(GOOD)
        m.update(rows, now=1700000000.5)
        self.assertEqual(samples(m.render()), {
            'aqdc_temperature_celsius{sensor="ds18b20"}': 25.1,
            'aqdc_temperature_celsius{sensor="dht22"}': 25.0,
            'aqdc_temperature_celsius{sensor="mhz19b"}': 26.0,
            'aqdc_humidity_percent{sensor="dht22"}': 60.5,
            'aqdc_co2_ppm{sensor="mhz19b"}': 620.0,
            'aqdc_pm_ug_per_m3{size="pm1"}': 3.0,
            'aqdc_pm_ug_per_m3{size="pm2_5"}': 5.0,
            'aqdc_pm_ug_per_m3{size="pm10"}': 6.0,
            'aqdc_last_reading_timestamp_seconds{sensor="ds18b20"}': 1700000000.5,
            'aqdc_last_reading_timestamp_seconds{sensor="dht22"}': 1700000000.5,
            'aqdc_last_reading_timestamp_seconds{sensor="mhz19b"}': 1700000000.5,
            'aqdc_last_reading_timestamp_seconds{sensor="pms7003"}': 1700000000.5,
        })

    def test_exposition_format(self):
        m = SensorMetrics()
        m.update(parse_payload(GOOD)[0], now=1.0)
        text = m.render()
        self.assertIn("# TYPE aqdc_co2_ppm gauge\n", text)
        self.assertIn("# HELP aqdc_co2_ppm ", text)
        self.assertTrue(text.endswith("\n"))

    def test_never_read_sensor_not_exported(self):
        m = SensorMetrics()
        self.assertEqual(m.render(), "")
        bad = dict(GOOD, PMS7003=None, DS18B20={"Temperature": -127})
        m.update(parse_payload(bad)[0], now=100)
        out = samples(m.render())
        self.assertFalse([k for k in out if "pms7003" in k or "aqdc_pm_ug" in k or "ds18b20" in k])
        self.assertIn('aqdc_co2_ppm{sensor="mhz19b"}', out)

    def test_failed_sensor_keeps_old_value_and_old_timestamp(self):
        m = SensorMetrics()
        m.update(parse_payload(GOOD)[0], now=100)
        later = dict(GOOD, PMS7003=None, DHT22={"Temperature": None, "Humidity": 70})
        m.update(parse_payload(later)[0], now=200)
        out = samples(m.render())
        self.assertEqual(out['aqdc_pm_ug_per_m3{size="pm10"}'], 6.0)            # 舊值
        self.assertEqual(out['aqdc_last_reading_timestamp_seconds{sensor="pms7003"}'], 100)
        self.assertEqual(out['aqdc_humidity_percent{sensor="dht22"}'], 60.5)    # 整組被拒，不更新
        self.assertEqual(out['aqdc_last_reading_timestamp_seconds{sensor="dht22"}'], 100)
        self.assertEqual(out['aqdc_last_reading_timestamp_seconds{sensor="mhz19b"}'], 200)

    def test_default_timestamp_is_now(self):
        m = SensorMetrics()
        before = time.time()
        m.update(parse_payload(GOOD)[0])
        ts = samples(m.render())['aqdc_last_reading_timestamp_seconds{sensor="dht22"}']
        self.assertTrue(before <= ts <= time.time())

    def test_unknown_table_ignored(self):
        m = SensorMetrics()
        m.update([("home_electricity", ["Voltage"], [110])], now=1)
        self.assertEqual(m.render(), "")


class MetricsAddressTest(unittest.TestCase):
    def test_default(self):
        self.assertEqual(metrics_address({}, environ={}), ("127.0.0.1", 9106))

    def test_setting_and_env_override(self):
        setting = {"metrics": {"host": "100.1.2.3", "port": 9200}}
        self.assertEqual(metrics_address(setting, environ={}), ("100.1.2.3", 9200))
        env = {"AQDC_METRICS_HOST": "100.9.9.9", "AQDC_METRICS_PORT": "9300"}
        self.assertEqual(metrics_address(setting, environ=env), ("100.9.9.9", 9300))


class HttpServerTest(unittest.TestCase):
    def get(self, port, path="/metrics"):
        return urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2)

    def test_serves_metrics_and_404(self):
        m = SensorMetrics()
        m.update(parse_payload(GOOD)[0], now=5)
        port = free_port()
        sensor_metrics.start_server(m, "127.0.0.1", port, retry_seconds=0.1)
        for _ in range(50):
            try:
                resp = self.get(port)
                break
            except OSError:
                time.sleep(0.1)
        else:
            self.fail("server did not start")
        self.assertIn("text/plain", resp.headers["Content-Type"])
        self.assertIn('aqdc_co2_ppm{sensor="mhz19b"} 620.0', resp.read().decode())
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get(port, "/other")
        self.assertEqual(ctx.exception.code, 404)

    def test_bind_failure_retries_until_free(self):
        blocker = socket.socket()
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        port = blocker.getsockname()[1]
        m = SensorMetrics()
        thread = sensor_metrics.start_server(m, "127.0.0.1", port, retry_seconds=0.1)
        time.sleep(0.4)
        self.assertTrue(thread.is_alive())      # 綁定失敗也沒有結束
        blocker.close()
        for _ in range(50):
            try:
                self.get(port)
                break
            except OSError:
                time.sleep(0.1)
        else:
            self.fail("server did not recover after port was freed")

    def test_wildcard_refused(self):
        for host in ("0.0.0.0", "", "::"):
            with mock.patch.object(sensor_metrics, "ThreadingHTTPServer") as server:
                sensor_metrics.serve_forever(SensorMetrics(), host, 9106, retry_seconds=0)
                server.assert_not_called()


class ReadSensorLoopTest(unittest.TestCase):
    """資料庫寫入拋例外時，指標仍要更新（直接跑 readSensor.main 的主迴圈）。"""

    def test_metrics_updated_when_db_fails(self):
        import pymysql
        import readSensor

        class FakeSerial:
            in_waiting = 0

            def __init__(self):
                self.lines = [json.dumps(GOOD).encode()]

            def readline(self):
                if self.lines:
                    return self.lines.pop()
                raise KeyboardInterrupt     # 主迴圈收到後正常結束

        registry = SensorMetrics()
        with mock.patch.object(readSensor, "METRICS", registry), \
                mock.patch.object(readSensor, "load_home_setting", return_value={}), \
                mock.patch.object(readSensor, "start_server"), \
                mock.patch.object(readSensor, "db_connect"), \
                mock.patch.object(readSensor, "open_serial", return_value=FakeSerial()), \
                mock.patch.object(readSensor, "save",
                                  side_effect=pymysql.err.OperationalError(2003, "down")) as save, \
                mock.patch.object(readSensor.time, "sleep"):
            readSensor.main()
        save.assert_called_once()
        out = samples(registry.render())
        self.assertEqual(out['aqdc_co2_ppm{sensor="mhz19b"}'], 620.0)
        self.assertIn('aqdc_last_reading_timestamp_seconds{sensor="pms7003"}', out)


if __name__ == "__main__":
    unittest.main()
