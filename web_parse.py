"""氣象署 (CWA) / 環境部 (EPA) 開放資料的解析（純函式，方便測試）。"""
from datetime import datetime

# CWA 要保存的氣象要素（O-A0003-001 的 WeatherElement 內為扁平欄位）
CWA_ELEMENTS = ['AirTemperature', 'RelativeHumidity', 'AirPressure']
# 官方以 -99 表示無資料（另有 -990~-999 等特殊代碼）；這些要素不可能為負值或如此低，
# 一律視為缺值。
MISSING_THRESHOLD = -90


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_cwa(jdata, station_id=None):
    """回傳 dict 或 None（無測站資料 / 溫度或濕度缺值）。

    station_id 有指定時，回傳的測站代碼必須相符，避免 API 回了別的測站而寫進錯的表。
    """
    stations = jdata['records']['Station']
    if station_id is not None:
        stations = [s for s in stations if s.get('StationId') == station_id]
    if not stations:
        return None
    station = stations[0]
    result = {
        'StationName': station['StationName'],
        'DateTime': datetime.fromisoformat(station['ObsTime']['DateTime']),
    }
    elements = station['WeatherElement']
    for key in CWA_ELEMENTS:
        number = _to_float(elements.get(key))
        if number is None or number <= MISSING_THRESHOLD:
            if key in ('AirTemperature', 'RelativeHumidity'):
                return None          # 溫度或濕度缺值，整筆捨棄
            continue                 # 氣壓缺值只是不存這個欄位
        result[key] = elements[key]
    return result


def parse_epa(jdata):
    """回傳 dict 或 None。

    相容兩種回傳格式：
    - list（aqx_p_212 目前的格式）
    - {"records": [...]}（舊格式，如 aqx_p_203 之外的 v2 端點）
    取最新的 monitordate，並收集該時間點的 PM2.5 / PM10。
    """
    records = jdata.get('records') if isinstance(jdata, dict) else jdata
    if not records:
        return None
    wanted = {'PM2.5': 'PM2_5', 'PM10': 'PM10'}
    items = [r for r in records
             if r.get('itemengname') in wanted
             and _to_float(r.get('concentration')) is not None
             and r.get('monitordate')]
    if not items:
        return None
    latest = max(r['monitordate'] for r in items)
    result = {}
    for r in items:
        if r['monitordate'] == latest:
            result[wanted[r['itemengname']]] = r['concentration']
    result['time'] = datetime.fromisoformat(latest)
    return result
