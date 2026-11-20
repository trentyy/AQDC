#!/usr/bin/python3
"""定期從氣象署 (CWA) 與環境部 (EPA) 開放資料取得戶外資料並寫入資料庫。"""

import time
from datetime import datetime

import requests
from loguru import logger

from common import db_connect, load_home_setting, redact

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
# CWA 要保存的氣象要素
CWA_ELEMENTS = ['AirTemperature', 'RelativeHumidity', 'AirPressure']


def http_get_json(url, params):
    resp = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def parse_cwa(jdata):
    stations = jdata['records']['Station']
    if not stations:
        return None
    station = stations[0]
    result = {
        'StationName': station['StationName'],
        'DateTime': datetime.fromisoformat(station['ObsTime']['DateTime']),
    }
    for key, value in station['WeatherElement'].items():
        # -99 代表儀器無資料，溫度或濕度缺值時整筆捨棄
        if key in ('AirTemperature', 'RelativeHumidity') and float(value) == -99:
            logger.info(f"{key} = -99, ignore")
            return None
        if key in CWA_ELEMENTS:
            result[key] = value
    return result


def parse_epa(jdata):
    records = jdata['records']
    if not records:
        return None
    result = {}
    for item in records:
        if item['itemengname'] == 'PM2.5':
            result['PM2_5'] = item['concentration']
        elif item['itemengname'] == 'PM10':
            result['PM10'] = item['concentration']
    result['time'] = datetime.fromisoformat(item['monitordate'])
    return result


def insert(table, columns, data):
    """以參數化查詢寫入；INSERT IGNORE 讓重複的時間戳不會報錯。"""
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
