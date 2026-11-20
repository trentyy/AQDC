"""AQDC 共用模組：設定檔載入、資料庫連線、log 遮蔽工具。

所有程式（readSensor / readWeb / readElectricity / actor / healthcheck）
都從這裡取得設定與資料庫連線，避免各自複製貼上。
"""
import json
import os

import pymysql

# 設定檔目錄，預設 ./setting，可用環境變數 AQDC_SETTING_DIR 覆蓋
SETTING_DIR = os.getenv("AQDC_SETTING_DIR", "./setting")

DB_CONNECT_TIMEOUT = 10  # 秒，避免資料庫無回應時永久卡住


def load_setting(name: str) -> dict:
    """讀取 SETTING_DIR 底下的 JSON 設定檔，例如 load_setting("AQDC-home.json")。"""
    with open(os.path.join(SETTING_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def load_home_setting() -> dict:
    return load_setting("AQDC-home.json")


def db_connect(setting: dict, **kwargs):
    """依 AQDC-home.json 的內容建立 MySQL 連線。"""
    kwargs.setdefault("connect_timeout", DB_CONNECT_TIMEOUT)
    return pymysql.connect(
        host=setting["host"],
        user=setting["user"],
        password=setting["pw"],
        database=setting["db"],
        **kwargs,
    )


def table_name(setting: dict, logical_name: str) -> str:
    """資料表名稱對應：設定檔 `table_names` 可覆蓋，例如 {"cwa_Home": "cwa_home"}。

    Linux 上的 MySQL / MariaDB 預設區分資料表名稱大小寫，各安裝的實際名稱可能不同。
    """
    return setting.get("table_names", {}).get(logical_name, logical_name)


def cwa_stations(setting: dict) -> list:
    """氣象署要抓取的測站清單：[{"id", "label", "table"}, ...]。

    設定檔 cwa.stations 有寫就用它；沒有的話相容舊設定，使用 cwa.params.StationId，
    寫入 cwa_Home。每個測站各寫一張表（cwa_Home 的主鍵只有 DateTime，不能混存多個測站）。
    """
    cwa = setting["cwa"]
    stations = cwa.get("stations")
    if stations:
        return [{"id": s["id"], "label": s.get("label", s["id"]),
                 "table": s.get("table", "cwa_Home")} for s in stations]
    return [{"id": cwa["params"].get("StationId") or cwa["params"].get("stationId"),
             "label": "default", "table": "cwa_Home"}]


def redact(text, secrets) -> str:
    """把字串中的密鑰（API key、密碼）換成 ***，避免寫進 log。"""
    text = str(text)
    for s in secrets:
        if s:
            text = text.replace(str(s), "***")
    return text
