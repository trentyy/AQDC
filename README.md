# Air Quality Data Collector

In order to keep tracking the air quality such as CO2( which will make people drowsy), TVOC (Total Volatile Organic Compounds, which might damage people's health), temperature, humidity to make people feel more comfortable in the room. I want to build a data center, like raspberry pi, to collect data from types of sensors and plot these data in a website, also I want to compare these data with outside weather by the collected data from the government.

## Hardware

### Server:

* Raspberry Pi 4

### Data collector:

* Arduino Uno

### Sensor:

* DS18B20: detect **temperature**
* DHT22: detect **Humidity** and temperature
* SHARP GP2Y1014AU: detect **PM2.5** 
* Gravity CCS811: detect **CO2** and **TVOC**

## Software:
* Raspberry Pi:
    * mosquitto, mosquitto-client ([ref](https://blog.gtwang.org/iot/raspberry-pi/raspberry-pi-mosquitto-mqtt-broker-iot-integration/))
## Libraries:

* Raspberry Pi:
    * pyserial
    * arduino
    * arduino-mk
* Arduino:
  * [pusubclient](https://github.com/knolleary/pubsubclient)

## Workflow:

### Part1: Website

<img src="C:\Users\Trent-Local\Downloads\螢幕擷取畫面 2020-09-18 194655.png" style="zoom:75%;" />

### Part2: Collect Data

![](C:\Users\Trent-Local\Downloads\螢幕擷取畫面 2020-09-18 194708.png" style="zoom:75%;" )

## Working Goals:

### Short-term Goals:

- [x] Let "THE monitor"(my pre-project which can send data to thingSpeak server to show data) can sent data to my Raspberry Pi server.
- [x] Establish database in my Raspberry Pi server.
- [x] Run myscript.service right after server booting to automatic start collecting and saving data.
### Long-term Goals:

* Show data by graph or gauge on server website.
* Move my website from local network to Internet!
## API
* air quality (pm2.5) https://data.epa.gov.tw/
* weather https://opendata.cwb.gov.tw/
## Pin
![G3 3003](https://i.imgur.com/DgNvuOd.jpg)

## Reference data
### DS18B20: detect **temperature**
### DHT22: detect **Humidity** and temperature
### SHARP GP2Y1014AU: detect **PM2.5** 
[datasheet]([ref]http://download.kamami.pl/p563980-PMS3003%20series%20data%20manual_English_V2.5.pdf)
### Gravity CCS811: detect **CO2** and **TVOC**
[Gravity: CCS811 Air Quality Sensor SKU: SEN0318]([ref]https://wiki.dfrobot.com/Gravity:%20CCS811%20Air%20Quality%20Sensor%20SKU:%20SEN0318)