/*
  write by Trent
*/
// include data process lib
#include <ArduinoJson.h>
// include wifi lib
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
// include LCD lib
// #include <LiquidCrystal_I2C.h>
// include sensors lib
#include <DFRobot_DHT20.h>

// define wifi configs
#include "secret.h"
#ifndef STASSID
#define STASSID "SSID"
#define STAPSK "PASSWORD"
#endif

// declare variables
DynamicJsonDocument doc(256);
int count = 0;
float AM2108_t, AM2108_h;

DFRobot_DHT20 dht20;

void setup() {
  // init system setup
  Serial.begin(115200);
  // declare the ledPin as an OUTPUT:
  // init object
  WiFi.begin(STASSID, STAPSK);
  WiFi.config(IPAddress(192,168,LOCAL_IP_3,249),     // 本機IP位址
              IPAddress(192,168,LOCAL_IP_3,1),     // 閘道（gateway）位址
              IPAddress(255,255,255,0));  // 網路遮罩（netmask）
  while(dht20.begin()){
    Serial.println("Initialize sensor failed");
    delay(1000);
  }

  // delay for sensor's stable time
  Serial.print("Wifi connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    ++count;
    Serial.println(count);
  }
  Serial.print("Connected! IP address: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  // read the value from the sensor:
  AM2108_t = dht20.getTemperature();
  AM2108_h = dht20.getHumidity() * 100;

  // Output
  doc["fridge_AM2108"]["Temperature"] = AM2108_t;
  doc["fridge_AM2108"]["Humidity"] = AM2108_h;
  
  serializeJson(doc, Serial);
  Serial.println();

  // wait for WiFi connection
  if ((WiFi.status() == WL_CONNECTED)) {

    WiFiClient client;
    HTTPClient http;

    Serial.print("[HTTP] begin...\n");
    // configure traged server and url
    http.begin(client, "http://" SERVER_IP "/addData/fridge/AM2108");  // HTTP
    http.addHeader("Content-Type", "application/json");

    Serial.print("[HTTP] POST...\n");
    // start connection and send HTTP header and body
    String output;
    serializeJson(doc, output);
    Serial.print("[HTTP] output=");
    Serial.println(output);
    int httpCode = http.POST(output);

    // httpCode will be negative on error
    if (httpCode > 0) {
      // HTTP header has been send and Server response header has been handled
      Serial.printf("[HTTP] POST... code: %d\n", httpCode);

      // file found at server
      if (httpCode == HTTP_CODE_OK) {
        const String& payload = http.getString();
        Serial.println("received payload:\n<<");
        Serial.println(payload);
        Serial.println(">>");
      }
    } else {
      Serial.printf("[HTTP] POST... failed, error: %s\n", http.errorToString(httpCode).c_str());
    }

    http.end();
  }
  
  delay(60000);
}
