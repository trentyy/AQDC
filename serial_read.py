#!/usr/bin python3
import time, json
import serial, pymysql.cursors

COM_PORT = '/dev/ttyACM0' # linux device in /dev/ttyACM*
# COM_PORT = 'COM1' # windows device name
BAUD_RATES = 115200
ser = serial.Serial(COM_PORT, BAUD_RATES)

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

            #print("data_raw: ", data_raw)
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

            except json.decoder.JSONDecodeError:
                continue
            sql = "INSERT INTO sensor_data(temperture, humidity, CO2, TVOC)" + \
                  "VALUES({0}, {1}, {2}, {3});".format(Temp, Humid, CO2, TVOC)

            #db.ping(reconnect=True)
            try:
                db = pymysql.connect(host=HOST, user=USER, password=PW, db=DB,
                             cursorclass=pymysql.cursors.DictCursor)
                cursor = db.cursor()

                db.ping(reconnect = True)
                cursor.execute(sql)
                db.commit()
            except Exception as e:
                print("sql execute Exception:", e)
                db.rollback()

            db.close()

            time.sleep(5*60)




except KeyboardInterrupt:
    ser.close()
    print('bye')
