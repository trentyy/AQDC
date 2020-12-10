#!/usr/bin python3
import time, json
import serial, pymysql.cursors

COM_PORT = '/dev/ttyACM0' # linux device in /dev/ttyACM*
# COM_PORT = 'COM1' # windows device name
BAUD_RATES = 115200

ser = serial.Serial(COM_PORT, BAUD_RATES)
connection = pymysql.connect(host='localhost',
                             user='pi',
                             password='pi_nchu',
                             db='AQDC',
                             cursorclass=pymysql.cursors.DictCursor)

try:
    while True:
        # Read data
        while ser.in_waiting:
            data_raw = ser.readline()
            data = data_raw.decode()
            #print("data_raw: ", data_raw)
            # print("data: ", data) # decomment if need to check data
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
            connection.cursor().execute(sql)
            connection.commit()
            connection.close()

            time.sleep(60)




except KeyboardInterrupt:
    ser.close()
    print('bye')
