#!/usr/bin python3
import time, json
import serial, pymysql.cursors


LOOP_SLEEP_TIME = 60     # set Loop sleep time in seconds
COM_PORT = '/dev/ttyACM0' # linux device in /dev/ttyACM*
# COM_PORT = 'COM1' # windows device name
BAUD_RATES = 9600
ser = serial.Serial(COM_PORT, BAUD_RATES)

# load information for read & write database
with open("AQDC.json", 'r') as f:
    jdata = json.load(f)

HOST = jdata['host']
USER = jdata['user']
PW = jdata['pw']
DB = jdata['db']

try:
    while True:
        # Read data
        while ser.in_waiting:
            data_raw = ser.readline()
            data = data_raw.decode()

            print("data: ", data) # decomment if need to check data
            
            # Parse json data
            try:
                j_data = json.loads(data)
                # get temp data
                Temp = j_data['DS18B20']['Temperature']
                # get humidity data
                Humid = j_data['DHT22']['Humidity']
                # get CO2 and TVOC data_raw
                CO2 = j_data['CCS811']['CO2']
                TVOC = j_data['CCS811']['TVOC']
                PM1 = j_data['PMS3003']['PM1']
                PM2_5 = j_data['PMS3003']['PM2_5']
                PM10 = j_data['PMS3003']['PM10']

            except json.decoder.JSONDecodeError:
                continue
            sql = "INSERT INTO sensor_data(temperture, humidity, CO2, TVOC, PM1, PM2_5, PM10)" + \
                  "VALUES({0},{1},{2},{3},{4},{5},{6});".format(
                      Temp, Humid, CO2, TVOC, PM1, PM2_5, PM10)

            try:
                db = pymysql.connect(host=HOST, user=USER, password=PW, db=DB,
                             cursorclass=pymysql.cursors.DictCursor)
                cursor = db.cursor()

                # ping() is used to reconnect database if it lost connection
                db.ping(reconnect = True)
                cursor.execute(sql)
                db.commit()
            # if sql fail to execute, print Exception and cancel INSERT
            except Exception as e:
                print("sql execute Exception:", e)
                db.rollback()

            db.close()

            time.sleep(LOOP_SLEEP_TIME)




except KeyboardInterrupt:
    ser.close()
    print('bye')
