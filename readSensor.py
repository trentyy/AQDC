#!/usr/bin/python3

import traceback, time, json
import serial
import pymysql.cursors
from loguru import logger

# log file name
trace = logger.add("./log/readSensor.log", rotation="monthly", encoding="utf-8", enqueue=True, retention="1 year")

COM_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600

ser = serial.Serial(COM_PORT, BAUD_RATE)

with open("AQDC-home.json", 'r') as f:
    jdata = json.load(f)

HOST = jdata['host']
USER = jdata['user']
PW = jdata['pw']
DB = jdata['db']

con=pymysql.connect(host=HOST, user=USER, passwd=PW, db=DB)

counter = 0

while True:
    try:
        counter += 1
        while ser.in_waiting:
            raw_data = ser.readline()
            data = raw_data.decode()
            print(data)
            jdata = json.loads(data)
            logger.info(jdata)
            
            DS18B20 = jdata["DS18B20"]
            DHT22 = jdata["DHT22"]
            PMS7003 = jdata["PMS7003"]

            curtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            
            sql = "INSERT INTO `home_ds18b20`(`time`,`temperature`)"
            sql += " VALUES (%s,%s)"
            print(sql, (curtime, DS18B20["Temperature"]))
            
            sql1 = "INSERT INTO `home_dht22`(`time`,`temperature`,`humidity`)"
            sql1 += " VALUES (%s,%s,%s)"
            print(sql1, (curtime,DHT22["Temperature"], DHT22["Humidity"]))

            sql2 = "INSERT INTO `home_pms7003`(`time`,`pm1`,`pm2_5`,`pm10`)"
            sql2 += " VALUES (%s,%s,%s,%s)"
            print(sql2, (curtime,PMS7003["PM1"],PMS7003["PM2_5"],PMS7003["PM10"]))
            
            con.ping(reconnect=True)

            
            with con.cursor() as cur:
                isNone = False
                for key, value in DS18B20.items():
                    if value == None:   isNone = True
                if not isNone:  cur.execute(sql, (curtime, DS18B20["Temperature"]))

                isNone = False
                for key, value in DHT22.items():
                    if value == None:   isNone = True
                if not isNone:  cur.execute(sql1, (curtime,DHT22["Temperature"], DHT22["Humidity"]))
                isNone = False
                for key, value in PMS7003.items():
                    if value == None:   isNone = True
                if not isNone:  cur.execute(sql2, (curtime,PMS7003["PM1"],PMS7003["PM2_5"],PMS7003["PM10"]))
            con.commit()
            logger.success("update success")
            """
            except Exception as e:
                print(traceback.format_exc())
            finally:
                print("sql success")
            """
        time.sleep(60)
    except UnicodeDecodeError:
        print("UnicodeDecodeError, continue")
    except json.decoder.JSONDecodeError:
        print("JSONDecodeError, continue")
    except pymysql.err.OperationalError:
        traceback.print_exc()
        print("pymysql.err.OperationalError, sleep 1 min and continue")
    except KeyboardInterrupt:
        print("KeyboardInterrupt, program exit")
        raise KeyboardInterrupt
