#!/usr/bin/python3
"""從 Arduino（序列埠 JSON）讀取感測器資料並寫入資料庫。"""

import json
import time

import pymysql
import serial
from loguru import logger

from common import db_connect, load_home_setting
from sensor_parse import parse_payload

logger.add("./log/readSensor.log", rotation="monthly", encoding="utf-8",
           enqueue=True, retention="1 year")

COM_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600
SERIAL_TIMEOUT = 5      # 秒；readline 逾時回傳空字串，不會永久阻塞
RETRY_SECONDS = 30      # 序列埠 / 資料庫失敗後的重試間隔


def open_serial():
    while True:
        try:
            ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=SERIAL_TIMEOUT)
            logger.info(f"serial opened: {COM_PORT}")
            return ser
        except serial.SerialException as e:
            logger.error(f"cannot open {COM_PORT}: {e}, retry in {RETRY_SECONDS}s")
            time.sleep(RETRY_SECONDS)


def read_latest_line(ser):
    """讀一行；若緩衝區已積了多行，丟掉舊的只留最新一行。"""
    line = ser.readline()
    skipped = 0
    while ser.in_waiting:
        line = ser.readline()
        skipped += 1
    if skipped:
        logger.warning(f"serial backlog, skipped {skipped} old line(s)")
    return line


def save(con, curtime, rows):
    """四張表的寫入放在同一個交易，其中一張失敗就整批 rollback。"""
    con.ping(reconnect=True)
    try:
        with con.cursor() as cur:
            for table, columns, values in rows:
                cols = ",".join(f"`{c}`" for c in ["time"] + columns)
                marks = ",".join(["%s"] * (len(columns) + 1))
                cur.execute(f"INSERT INTO `{table}`({cols}) VALUES ({marks})",
                            [curtime] + values)
        con.commit()
    except Exception:
        con.rollback()
        raise


def main():
    setting = load_home_setting()
    con = db_connect(setting)
    ser = open_serial()

    while True:
        try:
            raw = read_latest_line(ser)
            if not raw:
                continue  # 逾時沒收到資料
            jdata = json.loads(raw.decode())
            logger.info(jdata)

            rows, rejected = parse_payload(jdata)
            if rejected:
                logger.warning(f"rejected: {rejected}")
            if not rows:
                continue

            curtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            save(con, curtime, rows)
            logger.success(f"saved: {[r[0] for r in rows]}")

        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("bad line from serial, skip")
        except (KeyError, TypeError, AttributeError) as e:
            logger.warning(f"unexpected payload structure: {e!r}")
        except serial.SerialException as e:
            logger.error(f"serial error: {e}, reopen in {RETRY_SECONDS}s")
            try:
                ser.close()
            except Exception:
                pass
            time.sleep(RETRY_SECONDS)
            ser = open_serial()
        except pymysql.err.MySQLError as e:
            logger.error(f"database error: {e!r}, retry in {RETRY_SECONDS}s")
            time.sleep(RETRY_SECONDS)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt, exit")
            break


if __name__ == "__main__":
    main()
