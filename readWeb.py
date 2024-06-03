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
udtCWA = 10 # update time for cwa: 10 min 
wdCWA = True # flag for forcing to write data into database

with open("./setting/AQDC-home.json", 'r') as f:
    jdata = json.load(f)

HOST = jdata['host']
USER = jdata['user']
PW = jdata['pw']
DB = jdata['db']

url_cwa = jdata['cwa']['url']
params_cwa = jdata['cwa']['params']
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


# curl -X GET "https://data.moenv.gov.tw/api/v2/aqx_p_212?api_key=[YOURKEY]" -H "accept: */*"
# curl -X GET "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization=[YOURKEY]&stationId=467490" -H  "accept: application/json"

async def getDataEPA(url, params, DEBUG = False):
    def getData(url, params):
        data = requests.get(url, params)
        if data.status_code != 200:
            logger.info(f"data.status_code: {data.status_code}")
        try:
            data.raise_for_status() 
        except HTTPError:
            return None
            

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
    if data == None:
        return None
    myDict = parseData(data)
    return myDict

async def getDataCWA(url, params, DEBUG = False):
    def getData(url, params):
        # get data from cwa
        data = requests.get(url, params)

        # dealing with request error
        if data.status_code != 200:
            logger.info(f"data.status_code: {data.status_code}")
        try:
            data.raise_for_status() 
        except HTTPError:
            return None
        data = data.text
        # use json.loads() to parse data from string-version, will become type: dict
        data = json.loads(data)
        print(json.dumps(data))
        if (len(data['records']['Station'])==0):
            return None

        return data

    def parseData(jdata):
        myDict = {}
        tmpList = jdata['records']['Station'][0]
        myDict['StationName'] = tmpList['StationName']
        
        t = tmpList['ObsTime']['DateTime']      # from Taipei to UTC
        t = datetime.fromisoformat(t)

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
    if data == None:
        return None
    myDict = parseData(data)
    return myDict

async def main():
    loop = asyncio.get_event_loop()
    counter = 0
    wdCWA = True
    CWA_data_fetched = False
    EPA_data_fetched = False
    while True:
        counter += 1
        if (counter >= udtCWA or wdCWA):
            print(f"{bcolors.OKBLUE}{datetime.now()}{bcolors.ENDC}")
            sql = ""
            
            try:
                cwa_dict = await getDataCWA(url_cwa, params_cwa)
                if (cwa_dict == None):
                    CWA_data_fetched = False
                else:
                    CWA_data_fetched = True
            except UnicodeDecodeError:
                logger.error(f"[UnicodeDecodeError] cwa_dict: {cwa_dict}")
            except json.decoder.JSONDecodeError:
                logger.error(f"[JSONDecodeError] cwa_dict: {cwa_dict}")
            except pymysql.err.OperationalError:
                logger.exception("pymysql.err.OperationalError, sleep 1 min and continue")
                await asyncio.sleep(60)
            except (requests.exceptions.HTTPError, NewConnectionError) as e:
                logger.exception(e)
                await asyncio.sleep(60)
            except Exception as e:
                logger.exception(e)
                await asyncio.sleep(60)

            try:
                epa_dict = await getDataEPA(url_epa, params_epa)
                if (epa_dict == None):
                    EPA_data_fetched = False
                else:
                    EPA_data_fetched = True
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
            except Exception as e:
                logger.exception(e)
                await asyncio.sleep(60)
                
            try:
                db = pymysql.connect(host=HOST, user=USER, password=PW, db=DB,
                                    cursorclass=pymysql.cursors.DictCursor)
                tmp = "\',\'"
                if CWA_data_fetched:
                    sql = (
                        "INSERT IGNORE INTO cwa_Home("
                        f"{','.join([key for key in cwa_dict.keys()])}"
                        ")VALUES(\'"
                        f"{tmp.join([str(value) for value in cwa_dict.values()])}"
                        "');"
                    )
                    db.cursor().execute(sql)
                    db.commit()
                    logger.success(sql)

                if EPA_data_fetched:
                    sql = (
                        "INSERT IGNORE INTO epa_Home("
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
                wdCWA = False
                CWA_data_fetched = False
                EPA_data_fetched = False
            except Exception as e:
                logger.exception(e)
                time.sleep(90)
                continue
        await asyncio.sleep(60)

if __name__ == '__main__':
    asyncio.run(main())
