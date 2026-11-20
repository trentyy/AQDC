#include <ArduinoJson.h>
//#include "DFRobot_CCS811.h"
#include <DallasTemperature.h>
#include <OneWire.h>
#include <DHT.h>
#include "PMS.h"
#include <SoftwareSerial.h>
#include "MHZ19.h"
#include <LiquidCrystal_I2C.h> // Library for LCD
LiquidCrystal_I2C lcd = LiquidCrystal_I2C(0x27, 20, 4); // Change to (0x27,16,2) for 16x2 LCD.

#define ONE_WIRE_BUS 2
#define DHT_PIN 3
#define SOFT_RX 4
#define SOFT_TX 5
#define DHT_TYPE 22
#define DELAY_MINUTE 1
#define DHT_RETRY 5   // DHT22 讀到 NaN 時最多重試次數
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature DS18B20(&oneWire);
#define MHZ19_RX 6                                          // Rx pin which the MHZ19 Tx pin is attached to
#define MHZ19_TX 7                                          // Tx pin which the MHZ19 Rx pin is attached to

DynamicJsonDocument doc(256);
float DS18B20_t, dht_t, dht_h;
//unsigned int ccs811_co2, ccs811_tvoc;
unsigned int PM01Value=0;          //define PM1.0 value of the air detector module
unsigned int PM2_5Value=0;         //define PM2.5 value of the air detector module
unsigned int PM10Value=0;         //define PM10 value of the air detector module

//DFRobot_CCS811 ccs811(&Wire, /*IIC_ADDRESS=*/0x5A);
//DFRobot_CCS811 ccs811;
DHT dht(DHT_PIN, DHT_TYPE);

SoftwareSerial PMSerial(SOFT_RX, SOFT_TX); // Arduino RX, TX
PMS pms(PMSerial);
PMS::DATA data;

// MHZ19 setup
MHZ19 myMHZ19;                                             // Constructor for library
SoftwareSerial MHZ19_Serial(MHZ19_RX, MHZ19_TX);                   // (Uno example) create device to MH-Z19 serial
int CO2;
int8_t MHZ19_Temp;

void setup(void)
{
  Serial.begin(9600);
  DS18B20.begin();
  dht.begin();
  /*Wait for the chip to be initialized completely, and then exit*/
  /*
  while(ccs811.begin() != 0){
      Serial.println("failed to init chip, please check if the chip connection is fine");
      delay(1000);
  }
  */
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
  //ccs811.setMeasCycle(ccs811.eCycle_10s);

  PMSerial.begin(9600);
  PMSerial.setTimeout(1500);
  //pms.passiveMode();    // Switch to passive mode

  MHZ19_Serial.begin(9600);
  myMHZ19.begin(MHZ19_Serial); 
  myMHZ19.autoCalibration();

  // stable time
  // wait 30 seconds for pms7003 stable
  lcd.init();

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("stable time:");
  lcd.backlight();
 
  for (int i = 30; i > 0; --i) {
    delay(1000);
    lcd.setCursor(0, 1);
    lcd.print(i);
    lcd.print("s    ");
  }
  lcd.clear();
}

void loop() {

  //pms.wakeUp();
  //delay(30000);


  

  // let sensor ready
  /*
  while(ccs811.checkDataReady() != true){
    delay(1000);
  } 
  */
  
  // read data
  //ccs811_co2 =  ccs811.getCO2PPM();
  //ccs811_tvoc = ccs811.getTVOCPPB();
  // read ds18b20
  DS18B20.requestTemperatures();
  DS18B20_t = DS18B20.getTempCByIndex(0);
  // 斷線時函式庫回 -127，視為讀取失敗，之後以 null 送出
  bool ds18b20Ok = (DS18B20_t != DEVICE_DISCONNECTED_C);

  // read dht22（最多重試 DHT_RETRY 次，不再無限迴圈；NaN 必須用 isnan() 判斷）
  dht_t = dht.readTemperature();
  for (int i = 0; i < DHT_RETRY && isnan(dht_t); i++) {
    delay(1000);
    dht_t = dht.readTemperature();
  }

  dht_h = dht.readHumidity();
  for (int i = 0; i < DHT_RETRY && isnan(dht_h); i++) {
    delay(1000);
    dht_h = dht.readHumidity();
  }

  // read pms data（讀取失敗時不再沿用上一次的舊值，改送 null）
  PMSerial.listen();
  pms.requestRead();
  bool pmsOk = pms.readUntil(data);
  if (pmsOk)
  {
    PM01Value=data.PM_AE_UG_1_0;          //define PM1.0 value of the air detector module
    PM2_5Value=data.PM_AE_UG_2_5;         //define PM2.5 value of the air detector module
    PM10Value=data.PM_AE_UG_10_0;
  }

  // read MHZ19
  MHZ19_Serial.listen();
  CO2 = myMHZ19.getCO2();                             // Request CO2 (as ppm)
  MHZ19_Temp = myMHZ19.getTemperature();              // Request Temperature (as Celsius)
  bool mhzOk = (CO2 > 0);                             // 讀取失敗時函式庫回 0

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("T:");
  lcd.print(dht_t);
  lcd.setCursor(6, 0);  
  // lcd.print((char)223);
  // lcd.print("C");

  lcd.setCursor(8, 0);
  lcd.print("RH:");
  lcd.print(dht_h);
  lcd.setCursor(15, 0);
  // lcd.print('%');

  lcd.setCursor(0, 1);
  lcd.print("PM2.5:");
  lcd.print(PM2_5Value);
  
  lcd.setCursor(8, 1);
  lcd.print("CO2:");
  lcd.print(CO2);


  //doc["CCS811"]["CO2"] = ccs811_co2;
  //doc["CCS811"]["TVOC"] = ccs811_tvoc;
  // 讀取失敗的欄位送 null，Python 端 (sensor_parse.py) 會略過該感測器
  if (ds18b20Ok) doc["DS18B20"]["Temperature"] = DS18B20_t;
  else           doc["DS18B20"]["Temperature"] = nullptr;
  if (!isnan(dht_t)) doc["DHT22"]["Temperature"] = dht_t;
  else               doc["DHT22"]["Temperature"] = nullptr;
  if (!isnan(dht_h)) doc["DHT22"]["Humidity"] = dht_h;
  else               doc["DHT22"]["Humidity"] = nullptr;
  if (pmsOk) {
    doc["PMS7003"]["PM1"] = PM01Value;
    doc["PMS7003"]["PM2_5"] = PM2_5Value;
    doc["PMS7003"]["PM10"] = PM10Value;
  } else {
    doc["PMS7003"]["PM1"] = nullptr;
    doc["PMS7003"]["PM2_5"] = nullptr;
    doc["PMS7003"]["PM10"] = nullptr;
  }
  if (mhzOk) {
    doc["MHZ19B"]["CO2"] = CO2;
    doc["MHZ19B"]["Temperature"] = MHZ19_Temp;
  } else {
    doc["MHZ19B"]["CO2"] = nullptr;
    doc["MHZ19B"]["Temperature"] = nullptr;
  }
  
  serializeJson(doc, Serial);
  Serial.println();
  
  /*!
   * @brief Set baseline
   * @param get from getBaseline.ino
   */
  //ccs811.writeBaseLine(0x847B);
  //pms.sleep();
  
  for (int i=0; i<DELAY_MINUTE; i++){
    delay(60000);
  }
  
}
