import traceback, time, json, datetime
import pymysql.cursors
# from loguru import logger

from JciHitachi.api import JciHitachiAWSAPI

with open("./setting/AQDC-home.json", 'r') as f:
    jdata = json.load(f)

HOST = jdata['host']
USER = jdata['user']
PW = jdata['pw']
DB = jdata['db']

with open("./setting/AQDC-actor.json", 'r') as f:
    jdata = json.load(f)
EMAIL = jdata['EMAIL']
PASSWORD = jdata['PASSWORD']
DEVICENAME = jdata['DEVICENAME']

flag = False

api = JciHitachiAWSAPI(EMAIL, PASSWORD, DEVICENAME)
api.login()

while True:
    try:
        # activation time
        curtime = datetime.datetime.now()
        if (curtime.hour >= 0) and (curtime.hour < 8):
            time.sleep(600)
            continue
        flag = False
        con=pymysql.connect(host=HOST, user=USER, passwd=PW, db=DB)
        sql = "SELECT `time`,`humidity` from `home_dht22` ORDER BY `time` DESC limit 1"
        with con.cursor() as cur:
            cur.execute(sql)
            result = cur.fetchall()
            humidity = result[0][1]
            t = result[0][0]
            # print(t, humidity)

        con.close()
        

        # Check device status
        # device_status = api.get_status(legacy=True) # return legacy status class
        device_status = api.get_status()
        status = device_status[DEVICENAME].status
        # print(status)

        if humidity > 60:
            if status['Switch'] == 'off':
                flag = True
                if api.set_status(
                    status_name="Switch", device_name=DEVICENAME, status_value=1
                ):
                    print(f"At {t}, humidity is {humidity}. Turn on success")
                else:
                    print(f"At {t}, humidity is {humidity}. Turn on failed")

        elif humidity < 50:
            if status['Switch'] == 'on':
                flag = True
                if api.set_status(
                    status_name="Switch", device_name=DEVICENAME, status_value=0
                ):
                    print(f"At {t}, humidity is {humidity}. Turn off success")
                else:
                    print(f"At {t}, humidity is {humidity}. Turn off failed")

        # Check the updated device status
        api.refresh_status()
        device_status = api.get_status()
        if flag == True:
            print(device_status[DEVICENAME].status)
        time.sleep(60)
    except Exception:
        raise Exception
