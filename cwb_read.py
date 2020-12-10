from datetime import datetime
import time, json
import urllib.request
import pymysql.cursors

# log file name
LOG = "cwb_read.log"

counter = 0
udtCWB = 10 # update time for cwb: 10 min 
wdCWB = True # writing data to cwb
myDict = dict()



# store request url, include cwb key, do not upload!
# curl -X GET "https://opendata.cwb.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization=YOURKEY&stationId=467490" -H  "accept: application/json"

url = "https://opendata.cwb.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization="

def getDataCWB(myDict, DEBUG = False):
    # get data from cwb
    data = urllib.request.urlopen(url).read()
    data = data.decode()

    # use json.loads() to parse data from string-version, will become type: dict
    jdata = json.loads(data)


    #jdata->records->location

    # here is the name of data which you want to store 
    needed_id = ['lat', 'lon', 'locationName', 
                'TEMP', 'HUMD', 'PRES',
                'H_F10', 'H_UVI',
                'Weather', 'CITY', 'TOWN']

    # dealing with data
    tmpList = jdata['records']['location'][0]

    myDict['obsTime'] = tmpList['time']['obsTime']

    for item in tmpList.keys():
        if (item in needed_id):
            myDict[item] = tmpList[item]

    weatherElement = tmpList['weatherElement']
    parameter = tmpList['parameter']

    for item in weatherElement:
        tmpDic = dict(item)
        if (tmpDic['elementName'] in needed_id):
            myDict[tmpDic['elementName']] = tmpDic['elementValue']

    for item in parameter:
        tmpDic = dict(item)
        if (tmpDic['parameterName'] in needed_id):
            myDict[tmpDic['parameterName']] = tmpDic['parameterValue']
    

    myDict['HUMD'] = float(myDict['HUMD']) * 100


while True:
    time.sleep(60)
    counter += 1
    
    if (counter >= udtCWB or wdCWB):
        f = open(LOG, 'a')
        getDataCWB(myDict)
        try:
            sql = "INSERT IGNORE INTO cwb_Taichung( obsTime, " + \
                "lat, lon, locationName," + \
                "TEMP, HUMD, PRES," +\
                "H_F10, H_UVI, Weather, CITY, TOWN)" + \
                f"VALUES(\'{myDict['obsTime']}\', {myDict['lat']}, {myDict['lon']}, \'{myDict['locationName']}\', " + \
                f"{myDict['TEMP']}, {myDict['HUMD']}, {myDict['PRES']}, {myDict['H_F10']}," + \
                f"{myDict['H_UVI']}, \'{myDict['Weather']}\', \'{myDict['CITY']}\', \'{myDict['TOWN']}\'" + \
                ");"
        except Exception as e:
            f.write(str(datetime.now()) + '\tsql string exception: ')
            f.write(str(e))
            f.write("\n sql= " + sql + '\n')
            f.close()
            continue
        try:
            connection = pymysql.connect(host='localhost',
                             user='pi',
                             password='pi_nchu',
                             db='AQDC',
                             cursorclass=pymysql.cursors.DictCursor)
            connection.cursor().execute(sql)
            connection.commit()
            connection.close()

            f.write(str(datetime.now()) + '\tSuccess insert, obsTime: ' + str(myDict['obsTime']) + '\n')
            f.close()

            counter = 0
            wdCWB = False
        except Exception as e:
            f.write(str(datetime.now()) + '\tException: ')
            f.write(str(e))
            f.write("\n sql= " + sql + '\n')
            f.write(f"myDict: {myDict}" + '\n')
            f.close()
            counter = 9
            
            continue
    
    




