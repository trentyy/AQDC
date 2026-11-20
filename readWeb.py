#!/usr/bin/python3
"""定期從氣象署 (CWA) 與環境部 (EPA) 開放資料取得戶外資料並寫入資料庫。"""

import time

import requests
from loguru import logger

from common import db_connect, load_home_setting, redact, table_name
from web_parse import parse_cwa, parse_epa

logger.add("./log/readWeb.log", rotation="monthly", encoding="utf-8",
           enqueue=True, retention="1 year")

UPDATE_INTERVAL = 600   # 成功後 10 分鐘再抓
RETRY_INTERVAL = 60     # 失敗後 1 分鐘重試
HTTP_TIMEOUT = 15       # 秒

setting = load_home_setting()
SOURCES = {
    "cwa": (setting['cwa']['url'], setting['cwa']['params']),
    "epa": (setting['airtw_epa']['url'], setting['airtw_epa']['params']),
}
# 需要從 log / 例外訊息中遮掉的密鑰
SECRETS = [v for _, params in SOURCES.values() for v in params.values()]
SECRETS += [setting.get('pw')]

# 寫入資料表的欄位白名單（欄位名稱不再直接取自外部資料）
CWA_COLUMNS = ['StationName', 'DateTime', 'AirTemperature', 'RelativeHumidity', 'AirPressure']
EPA_COLUMNS = ['PM2_5', 'PM10', 'time']


def http_get_json(url, params):
    resp = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def insert(table, columns, data):
    """以參數化查詢寫入；INSERT IGNORE 讓重複的時間戳不會報錯。
    table 為邏輯名稱，實際資料表名稱可在設定檔 table_names 對應（Linux 的 MySQL 區分大小寫）。"""
    table = table_name(setting, table)
    cols = [c for c in columns if c in data]
    sql = (f"INSERT IGNORE INTO `{table}`({','.join('`%s`' % c for c in cols)}) "
           f"VALUES ({','.join(['%s'] * len(cols))})")
    con = db_connect(setting)
    try:
        with con.cursor() as cur:
            cur.execute(sql, [data[c] for c in cols])
        con.commit()
    finally:
        con.close()
    logger.success(f"{table}: {dict(zip(cols, [data[c] for c in cols]))}")


JOBS = [
    ("cwa", parse_cwa, "cwa_Home", CWA_COLUMNS),
    ("epa", parse_epa, "epa_Home", EPA_COLUMNS),
]


def run_once():
    """兩個來源各自獨立處理，一邊失敗不影響另一邊。回傳是否全部成功。"""
    all_ok = True
    for name, parse, table, columns in JOBS:
        url, params = SOURCES[name]
        try:
            data = parse(http_get_json(url, params))
            if data is None:
                logger.warning(f"{name}: no usable data")
                all_ok = False
                continue
            insert(table, columns, data)
        except Exception as e:
            # 不用 logger.exception：requests 的錯誤訊息會含帶 API key 的完整 URL
            logger.error(f"{name}: {type(e).__name__}: {redact(e, SECRETS)}")
            all_ok = False
    return all_ok


def main():
    next_run = 0.0
    while True:
        now = time.monotonic()
        if now >= next_run:
            ok = run_once()
            next_run = time.monotonic() + (UPDATE_INTERVAL if ok else RETRY_INTERVAL)
        time.sleep(5)


if __name__ == '__main__':
    main()
