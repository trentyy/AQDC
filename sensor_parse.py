"""解析 Arduino 傳來的 JSON，並檢查數值是否合理（純函式，方便測試）。"""

# 資料表 -> (JSON 區塊名稱, [(JSON 欄位, 資料表欄位, 最小值, 最大值), ...])
SENSORS = {
    "home_ds18b20": ("DS18B20", [
        ("Temperature", "temperature", -40, 85),   # 斷線時 DS18B20 會回 -127
    ]),
    "home_dht22": ("DHT22", [
        ("Temperature", "temperature", -40, 80),
        ("Humidity", "humidity", 0, 100),
    ]),
    "home_pms7003": ("PMS7003", [
        ("PM1", "pm1", 0, 1000),
        ("PM2_5", "pm2_5", 0, 1000),
        ("PM10", "pm10", 0, 1000),
    ]),
    "home_mhz19b": ("MHZ19B", [
        ("Temperature", "temperature", -40, 80),
        ("CO2", "co2", 300, 5000),                 # 讀取失敗時 MH-Z19B 會回 0
    ]),
}


def parse_payload(jdata):
    """回傳 (rows, rejected)。

    rows: [(table, [column, ...], [value, ...]), ...]，只包含整組欄位都有效的感測器
    rejected: ["home_xxx.col=value", ...]，被判定無效的欄位，供 log 使用
    """
    rows, rejected = [], []
    for table, (block, fields) in SENSORS.items():
        data = jdata.get(block)
        if not isinstance(data, dict):
            rejected.append(f"{table}: missing block {block}")
            continue
        columns, values, ok = [], [], True
        for key, column, lo, hi in fields:
            value = data.get(key)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not lo <= value <= hi):
                rejected.append(f"{table}.{column}={value!r}")
                ok = False
                continue
            columns.append(column)
            values.append(value)
        if ok:
            rows.append((table, columns, values))
    return rows, rejected
