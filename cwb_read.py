#!/usr/bin/python3

from datetime import datetime
import time, json
import requests
import pymysql.cursors

# log file name
LOG = "cwb_read.log"

counter = 0
udtCWB = 10 # update time for cwb: 10 min 
wdCWB = True # writing data to cwb


with open("AQDC.json", 'r') as f:
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
needed_id = ['lat', 'lon', 'locationName', 
            'TEMP', 'HUMD', 'PRES',
            'H_F10', 'H_UVI',
            'Weather', 'CITY', 'TOWN']

# store request url, include cwb key, do not upload!
# curl -X GET "https://opendata.cwb.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization=YOURKEY&stationId=467490" -H  "accept: application/json"
def getDataEPA(url, params, DEBUG = False):
    myDict = dict()
    # get data from airtw.epa
    data = requests.get(url, params=params)
    data = data.text
    # use json.loads() to parse data from string-version, will become type: dict
    jdata = json.loads(data)

    tmpList = jdata['records']
    # parse data
    for item in tmpList:
        if item['ItemEngName'] == 'PM2.5':
            myDict['PM2_5'] = item['Concentration']
            myDict['time'] = item['MonitorDate']
        elif item['ItemEngName'] == 'PM10':
            myDict['PM10'] = item['Concentration']

    return myDict


def getDataCWB(url, params, DEBUG = False):
    myDict = dict()
    # get data from cwb

    data = requests.get(url, params=params, verify=False)

    
    data = data.text

    # use json.loads() to parse data from string-version, will become type: dict
    jdata = json.loads(data)

    # jdata->records->location
    # dealing with data
    tmpList = jdata['records']['location'][0]

    # parse data
    myDict['obsTime'] = tmpList['time']['obsTime']
    weatherElement = tmpList['weatherElement']
    parameter = tmpList['parameter']

    for item in tmpList.keys():
        if (item in needed_id):
            myDict[item] = tmpList[item]

    

    for item in weatherElement:
        tmpDic = dict(item)
        if (tmpDic['elementName'] in needed_id):
            myDict[tmpDic['elementName']] = tmpDic['elementValue']

    for item in parameter:
        tmpDic = dict(item)
        if (tmpDic['parameterName'] in needed_id):
            myDict[tmpDic['parameterName']] = tmpDic['parameterValue']
    

    myDict['HUMD'] = float(myDict['HUMD']) * 100
    return myDict


while True:
    time.sleep(60)
    counter += 1  
    if (counter >= udtCWB or wdCWB):
        f = open(LOG, 'a')
        cwb_dict = getDataCWB(url_cwb, params_cwb)
        print(cwb_dict)
        time.sleep(10)
        epa_dict = getDataEPA(url_epa, params_epa)
        
        print(epa_dict)
        try:
            sql_cwb = "INSERT IGNORE INTO cwb_Taichung( obsTime, " + \
                "lat, lon, locationName," + \
                "TEMP, HUMD, PRES," +\
                "H_F10, H_UVI, Weather, CITY, TOWN)" + \
                f"VALUES(\'{cwb_dict['obsTime']}\', {cwb_dict['lat']}, {cwb_dict['lon']}, \'{cwb_dict['locationName']}\', " + \
                f"{cwb_dict['TEMP']}, {cwb_dict['HUMD']}, {cwb_dict['PRES']}, {cwb_dict['H_F10']}," + \
                f"{cwb_dict['H_UVI']}, \'{cwb_dict['Weather']}\', \'{cwb_dict['CITY']}\', \'{cwb_dict['TOWN']}\'" + \
                ");"
            sql_epa = "INSERT IGNORE INTO epa_Taichung( time, " + \
                "PM2_5, PM10)" + \
                f"VALUES(\'{epa_dict['time']}\', '\{epa_dict['PM2_5']}\', \'{epa_dict['PM10']}\');"
            db = pymysql.connect(host=HOST, user=USER, password=PW, db=DB,
                             cursorclass=pymysql.cursors.DictCursor)
            db.cursor().execute(sql_cwb)
            db.commit()
            db.cursor().execute(sql_epa)
            db.commit()
            db.close()

            f.write(str(datetime.now()) + '\tSuccess insert, obsTime: ' + str(cwb_dict['obsTime']) + '\n')
            f.close()

            counter = 0
            wdCWB = False
        except Exception as e:
            f.write(str(datetime.now()) + '\tException: ')
            f.write(str(e))
            f.write("\n sql= " + sql + '\n')
            f.write(f"myDict: {cwb_dict}" + '\n')
            f.close()
            counter = 9
            
            continue

