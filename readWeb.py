#!/usr/bin/python3

import traceback, time, json, asyncio
from datetime import datetime
from urllib.error import HTTPError
import requests
import pymysql.cursors
from loguru import logger

from urllib3.exceptions import NewConnectionError

# log file name
trace = logger.add("./log/readWeb.log", rotation="monthly", encoding="utf-8", enqueue=True, retention="1 year")
counter = 0
udtCWB = 10 # update time for cwb: 10 min 
wdCWB = True # flag for forcing to write data into database

with open("AQDC-home.json", 'r') as f:
    jdata = json.load(f)

HOST = jdata['host']
USER = jdata['user']
PW = jdata['pw']
DB = jdata['db']

url_cwb = jdata['cwb']['url']
params_cwb = jdata['cwb']['params']
url_epa = jdata['airtw_epa']['url']
params_epa = jdata['airtw_epa']['params']

# here is the name of data which you want to store 
needed_id = [
    'StationName', 
    'AirTemperature', 'RelativeHumidity', 'AirPressure',
]

# for print color
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# store request url, include cwb key, do not upload!
# curl -X GET "https://opendata.cwb.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization=[YOURKEY]&stationId=467490" -H  "accept: application/json"

async def getDataEPA(url, params, DEBUG = False):
    def getData(url, params):
        data = requests.get(url, params)
        if data.status_code != 200:
            logger.info(f"data.status_code: {data.status_code}")
        data.raise_for_status()

        data = data.text
        data = json.loads(data)
        return data
    
    def parseData(jdata):
        myDict = {}
        tmpList = jdata['records']
        
        for item in tmpList:
            if item['itemengname'] == 'PM2.5':
                myDict['PM2_5'] = item['concentration']
            elif item['itemengname'] == 'PM10':
                myDict['PM10'] = item['concentration']
        t = item['monitordate']      # from Taipei to UTC
        t = datetime.fromisoformat(t)
        t = t# - dt.timedelta(hours=8)
        myDict['time'] = t
        return myDict
        
    data = getData(url, params)
    myDict = parseData(data)
    return myDict

async def getDataCWB(url, params, DEBUG = False):
    def getData(url, params):
        flag = True
        while(flag):
            # get data from cwb
            data = requests.get(url, params)

            # dealing with request error
            if data.status_code != 200:
                logger.info(f"data.status_code: {data.status_code}")
            try:
                data.raise_for_status() 
            except HTTPError:
                time.sleep(60)
                continue
            data = data.text
            # use json.loads() to parse data from string-version, will become type: dict
            data = json.loads(data)
            if (len(data['records']['Station'])!=0):
                flag = False
            else:
                time.sleep(60)
        return data

    def parseData(jdata):
        myDict = {}
        tmpList = jdata['records']['Station'][0]
        myDict['StationName'] = tmpList['StationName']
        
        t = tmpList['ObsTime']['DateTime']      # from Taipei to UTC
        t = datetime.fromisoformat(t)
        t = t# - dt.timedelta(hours=8)

        myDict['DateTime'] = t
        WeatherElement = tmpList['WeatherElement']

        for key, value in WeatherElement.items():
            if (key == 'AirTemperature' and float(value) == -99):
                logger.info("AirTemperature = -99, ignore")
                return None
            elif (key == 'RelativeHumidity' and float(value) == -99):
                logger.info("RelativeHumidity = -99, ignore")
                return None
            if (key in needed_id):
                myDict[key] = value
        return myDict

    data = getData(url, params)
    myDict = parseData(data)
    return myDict

async def main():
    loop = asyncio.get_event_loop()
    counter = 0
    wdCWB = True
    while True:
        counter += 1
        if (counter >= udtCWB or wdCWB):
            print(f"{bcolors.OKBLUE}{datetime.now()}{bcolors.ENDC}")
            sql = ""
            
            try:
                cwb_dict = await getDataCWB(url_cwb, params_cwb)
                if (cwb_dict == None):
                    continue
            except UnicodeDecodeError:
                logger.error(f"[UnicodeDecodeError] cwb_dict: {cwb_dict}")
            except json.decoder.JSONDecodeError:
                logger.error(f"[JSONDecodeError] cwb_dict: {cwb_dict}")
            except pymysql.err.OperationalError:
                logger.exception("pymysql.err.OperationalError, sleep 1 min and continue")
                await asyncio.sleep(60)
                continue
            except (requests.exceptions.HTTPError, NewConnectionError) as e:
                logger.exception(e)
                await asyncio.sleep(60)
                continue
            except Exception as e:
                logger.exception(e)
                await asyncio.sleep(60)
                continue

            try:
                epa_dict = await getDataEPA(url_epa, params_epa)
            except UnicodeDecodeError:
                logger.error(f"[UnicodeDecodeError] epa_dict: {epa_dict}")
            except json.decoder.JSONDecodeError:
                logger.error(f"[JSONDecodeError] epa_dict: {epa_dict}")
            except pymysql.err.OperationalError:
                logger.exception("pymysql.err.OperationalError, sleep 1 min and continue")
                await asyncio.sleep(60)
            except (requests.exceptions.HTTPError, NewConnectionError) as e:
                traceback.print_exc()
                await asyncio.sleep(60)
                continue
            except Exception as e:
                logger.exception(e)
                await asyncio.sleep(60)
                continue
                
            try:
                db = pymysql.connect(host=HOST, user=USER, password=PW, db=DB,
                                cursorclass=pymysql.cursors.DictCursor)
                tmp = "\',\'"
                sql = (
                    "INSERT IGNORE INTO cwb_Nangang("
                    f"{','.join([key for key in cwb_dict.keys()])}"
                    ")VALUES(\'"
                    f"{tmp.join([str(value) for value in cwb_dict.values()])}"
                    "');"
                )
                db.cursor().execute(sql)
                db.commit()
                logger.success(sql)


                sql = (
                    "INSERT IGNORE INTO epa_Taipei("
                    f"{','.join([key for key in epa_dict.keys()])}"
                    ")VALUES(\'"
                    f"{tmp.join([str(value) for value in epa_dict.values()])}"
                    "');"
                )
                db.cursor().execute(sql)
                db.commit()
                logger.success(sql)
                db.close()

                counter = 0
                wdCWB = False
            except Exception as e:
                logger.exception(e)
                time.sleep(90)
                continue
        await asyncio.sleep(60)

if __name__ == '__main__':
    asyncio.run(main())
