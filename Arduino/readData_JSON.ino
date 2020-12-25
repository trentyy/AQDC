#include <ArduinoJson.h>
#include "DFRobot_CCS811.h"
#include <DallasTemperature.h>
#include <OneWire.h>
#include <DHT.h>
#include "PMS.h"
#include <SoftwareSerial.h>

#define ONE_WIRE_BUS 2
#define DHT_PIN 3
#define SOFT_RX 4
#define SOFT_TX 5
#define DHT_TYPE 22
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature DS18B20(&oneWire);

DynamicJsonDocument doc(256);
float DS18B20_t, dht_t, dht_h;
unsigned int ccs811_co2, ccs811_tvoc;
unsigned int PM01Value=0;          //define PM1.0 value of the air detector module
unsigned int PM2_5Value=0;         //define PM2.5 value of the air detector module
unsigned int PM10Value=0;         //define PM10 value of the air detector module

//DFRobot_CCS811 ccs811(&Wire, /*IIC_ADDRESS=*/0x5A);
DFRobot_CCS811 ccs811;
DHT dht(DHT_PIN, DHT_TYPE);

SoftwareSerial PMSerial(SOFT_RX, SOFT_TX); // Arduino RX, TX
PMS pms(PMSerial);
PMS::DATA data;

void setup(void)
{
  Serial.begin(9600);
  DS18B20.begin();
  dht.begin();
  /*Wait for the chip to be initialized completely, and then exit*/
  while(ccs811.begin() != 0){
      Serial.println("failed to init chip, please check if the chip connection is fine");
      delay(1000);
  }
  /**
   * @brief Set measurement cycle
   * @param cycle:in typedef enum{
   *                  eClosed,      //Idle (Measurements are disabled in this mode)
   *                  eCycle_1s,    //Constant power mode, IAQ measurement every second
   *                  eCycle_10s,   //Pulse heating mode IAQ measurement every 10 seconds
   *                  eCycle_60s,   //Low power pulse heating mode IAQ measurement every 60 seconds
   *                  eCycle_250ms  //Constant power mode, ccs811 measurement every 250ms
   *                  }eCycle_t;
   */
  ccs811.setMeasCycle(ccs811.eCycle_250ms);

  PMSerial.begin(9600);
  PMSerial.setTimeout(1500);
  //pms.passiveMode();    // Switch to passive mode
}
void loop() {

  //pms.wakeUp();
  //delay(30000);

  
  
  
  for (int i=0; i<1; i++){
    // let sensor ready
    while(ccs811.checkDataReady() != true){
      delay(10);
    } 
    
    // read data
    ccs811_co2 =  ccs811.getCO2PPM();
    ccs811_tvoc = ccs811.getTVOCPPB();
    DS18B20.requestTemperatures();
    DS18B20_t = DS18B20.getTempCByIndex(0);
    dht_t = dht.readTemperature();
    dht_h = dht.readHumidity();
    pms.requestRead();
    if (pms.readUntil(data))
    {
      PM01Value=data.PM_AE_UG_1_0;          //define PM1.0 value of the air detector module
      PM2_5Value=data.PM_AE_UG_2_5;         //define PM2.5 value of the air detector module
      PM10Value=data.PM_AE_UG_10_0;
    }
    
    doc["CCS811"]["CO2"] = ccs811_co2;
    doc["CCS811"]["TVOC"] = ccs811_tvoc;
    doc["DS18B20"]["Temperature"] = DS18B20_t;
    doc["DHT22"]["Temperature"] = dht_t;
    doc["DHT22"]["Humidity"] = dht_h;
    doc["PMS3003"]["PM1"] = PM01Value;
    doc["PMS3003"]["PM2_5"] = PM2_5Value;
    doc["PMS3003"]["PM10"] = PM10Value;
    
    serializeJson(doc, Serial);
    Serial.println();
    
    /*!
     * @brief Set baseline
     * @param get from getBaseline.ino
     */
    ccs811.writeBaseLine(0x847B);
    delay(1000);
  }
  //pms.sleep();

  for (int i=0; i<5; i++)
    delay(60000);
}
