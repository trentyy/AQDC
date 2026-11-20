"""感測器讀數的 Prometheus 指標：記憶體內保存最新值，以 HTTP /metrics 提供。

只用標準函式庫。指標更新與資料庫無關：readSensor 在 parse_payload 之後、寫入 MySQL 之前呼叫
`METRICS.update(rows)`，所以資料庫失敗時指標仍會更新。
"""
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from loguru import logger

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9106
BIND_RETRY_SECONDS = 30
WILDCARD_HOSTS = ("", "0.0.0.0", "::", "0:0:0:0:0:0:0:0")

# (資料表, 欄位) -> (指標名稱, 標籤名稱, 標籤值)。刻意寫成明確對照，不依欄位名稱自動產生。
VALUE_METRICS = {
    ("home_ds18b20", "temperature"): ("aqdc_temperature_celsius", "sensor", "ds18b20"),
    ("home_dht22", "temperature"): ("aqdc_temperature_celsius", "sensor", "dht22"),
    ("home_dht22", "humidity"): ("aqdc_humidity_percent", "sensor", "dht22"),
    ("home_mhz19b", "temperature"): ("aqdc_temperature_celsius", "sensor", "mhz19b"),
    ("home_mhz19b", "co2"): ("aqdc_co2_ppm", "sensor", "mhz19b"),
    ("home_pms7003", "pm1"): ("aqdc_pm_ug_per_m3", "size", "pm1"),
    ("home_pms7003", "pm2_5"): ("aqdc_pm_ug_per_m3", "size", "pm2_5"),
    ("home_pms7003", "pm10"): ("aqdc_pm_ug_per_m3", "size", "pm10"),
}

# 資料表 -> aqdc_last_reading_timestamp_seconds 的 sensor 標籤
TIMESTAMP_SENSORS = {
    "home_ds18b20": "ds18b20",
    "home_dht22": "dht22",
    "home_mhz19b": "mhz19b",
    "home_pms7003": "pms7003",
}
TIMESTAMP_METRIC = "aqdc_last_reading_timestamp_seconds"

HELP = {
    "aqdc_temperature_celsius": "Latest temperature reading in degrees Celsius.",
    "aqdc_humidity_percent": "Latest relative humidity reading in percent.",
    "aqdc_co2_ppm": "Latest CO2 concentration in ppm.",
    "aqdc_pm_ug_per_m3": "Latest particulate matter concentration in ug/m3.",
    TIMESTAMP_METRIC: "Unix time of the last successful reading of each sensor.",
}
# 輸出順序固定
METRIC_ORDER = ["aqdc_temperature_celsius", "aqdc_humidity_percent", "aqdc_co2_ppm",
                "aqdc_pm_ug_per_m3", TIMESTAMP_METRIC]


class SensorMetrics:
    """保存每個 (指標, 標籤) 的最新值；從未讀到的感測器不會出現在輸出裡。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._values = {}   # (metric, label_name, label_value) -> float

    def update(self, rows, now=None):
        """rows 為 parse_payload 回傳的 [(table, columns, values), ...]。"""
        now = time.time() if now is None else now
        with self._lock:
            for table, columns, values in rows:
                sensor = TIMESTAMP_SENSORS.get(table)
                if sensor is None:
                    continue
                for column, value in zip(columns, values):
                    target = VALUE_METRICS.get((table, column))
                    if target is not None:
                        self._values[target] = float(value)
                self._values[(TIMESTAMP_METRIC, "sensor", sensor)] = float(now)

    def render(self):
        """Prometheus text exposition format 0.0.4。"""
        with self._lock:
            snapshot = dict(self._values)
        lines = []
        for metric in METRIC_ORDER:
            samples = sorted((k, v) for k, v in snapshot.items() if k[0] == metric)
            if not samples:
                continue
            lines.append(f"# HELP {metric} {HELP[metric]}")
            lines.append(f"# TYPE {metric} gauge")
            for (_, label, label_value), value in samples:
                lines.append(f'{metric}{{{label}="{label_value}"}} {value!r}')
        return "\n".join(lines) + "\n" if lines else ""


METRICS = SensorMetrics()


def metrics_address(setting, environ=None):
    """(host, port)：環境變數 AQDC_METRICS_HOST / AQDC_METRICS_PORT > 設定檔 metrics.host / metrics.port > 預設。"""
    environ = os.environ if environ is None else environ
    cfg = setting.get("metrics") or {}
    host = environ.get("AQDC_METRICS_HOST") or cfg.get("host") or DEFAULT_HOST
    port = environ.get("AQDC_METRICS_PORT") or cfg.get("port") or DEFAULT_PORT
    return str(host).strip(), int(port)


def _make_handler(registry):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?", 1)[0] != "/metrics":
                self.send_error(404)
                return
            body = registry.render().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):   # 不要每次抓取都寫 stderr
            pass

    return Handler


def serve_forever(registry, host, port, retry_seconds=BIND_RETRY_SECONDS):
    """綁定並提供 /metrics；綁定失敗（例如 Tailscale 尚未啟動）就記錄並重試，永不拋出例外。"""
    if host in WILDCARD_HOSTS:
        logger.error(f"metrics: refuse to bind wildcard address {host!r}; "
                     "set a specific address (e.g. the Tailscale IP). metrics endpoint disabled")
        return
    while True:
        try:
            server = ThreadingHTTPServer((host, port), _make_handler(registry))
        except OSError as e:
            logger.error(f"metrics: cannot bind {host}:{port}: {e}, retry in {retry_seconds}s")
            time.sleep(retry_seconds)
            continue
        logger.info(f"metrics: serving http://{host}:{port}/metrics")
        try:
            server.serve_forever()
        except Exception as e:
            logger.error(f"metrics: server stopped: {e!r}, restart in {retry_seconds}s")
        finally:
            server.server_close()
        time.sleep(retry_seconds)


def start_server(registry, host, port, retry_seconds=BIND_RETRY_SECONDS):
    """在背景 daemon 執行緒啟動，不會阻塞或拖垮主迴圈。"""
    thread = threading.Thread(target=serve_forever, args=(registry, host, port, retry_seconds),
                              name="metrics-server", daemon=True)
    thread.start()
    return thread
