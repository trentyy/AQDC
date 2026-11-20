#!/usr/bin/python3
"""資料新鮮度檢查：任何一張表超過指定時間沒有新資料就回傳非 0 並記錄 / 通知。

用法：python healthcheck.py
建議用 systemd timer 每 10 分鐘執行一次（見 service/AQDC_health.timer）。

可選設定：在 setting/AQDC-home.json 加上
    "healthcheck": {"notify_url": "https://...", "max_age_minutes": {"home_dht22": 10}}
有 notify_url 時，會以 POST {"text": "..."} 送出告警（Slack / Discord / ntfy 等 webhook 皆可調整）。
"""
import sys
from datetime import datetime, timedelta

import requests
from loguru import logger

from common import db_connect, load_home_setting, redact

logger.add("./log/healthcheck.log", rotation="monthly", encoding="utf-8",
           enqueue=True, retention="1 year")

# 資料表 -> (時間欄位, 預設容許的最大延遲(分鐘))
TABLES = {
    "home_ds18b20": ("time", 10),
    "home_dht22": ("time", 10),
    "home_pms7003": ("time", 10),
    "home_mhz19b": ("time", 10),
    "cwa_Home": ("DateTime", 180),   # 氣象署資料本身約每小時更新
}


def main() -> int:
    setting = load_home_setting()
    hc = setting.get("healthcheck", {})
    limits = hc.get("max_age_minutes", {})
    now = datetime.now()
    problems = []

    con = db_connect(setting)
    try:
        with con.cursor() as cur:
            for table, (col, default_max) in TABLES.items():
                cur.execute(f"SELECT MAX(`{col}`) FROM `{table}`")
                latest = cur.fetchone()[0]
                limit = timedelta(minutes=limits.get(table, default_max))
                if latest is None:
                    problems.append(f"{table}: no data")
                elif now - latest > limit:
                    problems.append(f"{table}: last data {latest} ({(now - latest)} ago, limit {limit})")
    finally:
        con.close()

    if not problems:
        logger.info("all tables fresh")
        return 0

    msg = "AQDC healthcheck failed:\n" + "\n".join(problems)
    logger.error(msg)
    url = hc.get("notify_url")
    if url:
        try:
            requests.post(url, json={"text": msg}, timeout=10)
        except Exception as e:
            logger.error(f"notify failed: {redact(e, [url])}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
