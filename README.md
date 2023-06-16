# Air Quality Data Collector

In order to keep tracking the air quality such as CO2( which will make people drowsy), TVOC (Total Volatile Organic Compounds, which might damage people's health), temperature, humidity to make people feel more comfortable in the room. I want to build a data center, to collect data from types of sensors and plot these data in a website, also I want to compare these data with outside weather by the collected data from the government.

## Hardware

### Server:

* Raspberry Pi 4

### Data collector:

* Arduino Uno
* Raspberry Pi 4 for Raspberry Pi Camera 2(new)

### Sensor:

* DS18B20: detect **temperature**
* DHT22: detect **Humidity** and temperature
* SHARP GP2Y1014AU: detect **PM2.5** 
* Gravity CCS811: detect **CO2** and **TVOC**
* Raspberry Pi Camera 2(for the power consumption of extension cord)

## Software:
## Libraries:
* Raspberry Pi:
    * pyserial
    * arduino
    * arduino-mk
* Arduino:
  * [pusubclient](https://github.com/knolleary/pubsubclient)
  * [ArduinoJson](https://arduinojson.org/)
  * DFRobot_CCS811
  * DallasTemperature
  * OneWire
  * DHT
  * PMS
  * SoftwareSerial

## Working Goals:
to show the data collected from local and opensourse website and manage a way to show them

## Workflow:
1. Collect data from local, and save them into db
2. Collect data from web, and save them into db
3. show the data by grafana, let me check it by internet
4. show the data by local screen, let me check it in my room

### Long-term Goals:
- [] Add a local e-ink screen
- [] Add co2 sensor
- [] Add power consumption data of extension cord

### Short-term Goals:
- [] Read extension cord data by seven segment LED
- [] Find a way to control e-ink screen
  - [] try c
  - [x] try microPython

### To-Do List
1. Reduce failed reading
2. Move functions into a package
3. Merge `readElectricity.py` into `readSensor.py` using `asycio` library

## Used API
* air quality (pm2.5) https://data.epa.gov.tw/
* weather https://opendata.cwb.gov.tw/
## issue
shutter speed too slow, sometimes there will be a afterimage -> trying to speed up and change some pre-process parameter to keep image reading quality


## Reference data
### DS18B20: detect **temperature**
### DHT22: detect **Humidity** and temperature
### SHARP GP2Y1014AU: detect **PM2.5** 
[datasheet]([ref]http://download.kamami.pl/p563980-PMS3003%20series%20data%20manual_English_V2.5.pdf)
### Gravity CCS811: detect **CO2** and **TVOC**
[Gravity: CCS811 Air Quality Sensor SKU: SEN0318]([ref]https://wiki.dfrobot.com/Gravity:%20CCS811%20Air%20Quality%20Sensor%20SKU:%20SEN0318)