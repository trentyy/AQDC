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

## Libraries:

* Raspberry Pi:
* Arduino:
  * 

## Workflow:

### Part1: Website

<img src="C:\Users\Trent-Local\Downloads\螢幕擷取畫面 2020-09-18 194655.png" style="zoom:75%;" />

### Part2: Collect Data

![](C:\Users\Trent-Local\Downloads\螢幕擷取畫面 2020-09-18 194708.png" style="zoom:75%;" )

## Working Goals:

### Short-term Goals:

* Let "THE monitor"(my pre-project which can send data to thingSpeak server to show data) can sent data to my Raspberry Pi server.
* Establish database in my Raspberry Pi server.

### Long-term Goals:

* Establish server can read data from database, and show it on a website.
* Move my website from local network to Internet!
* (Use Raspberry Pi controls sensors directly, if send data from Arduino to Pi is too complicated.)