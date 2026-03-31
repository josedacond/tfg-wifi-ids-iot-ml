#define ARDUINO_USB_CDC_ON_BOOT 1

#include <Wire.h>
#include "ICM42670P.h"       // sensor IMU
#include <Adafruit_SHTC3.h>  // sensor SHT32
#include <Adafruit_Sensor.h>
#include <Adafruit_NeoPixel.h>

#include <WiFi.h>
#include <PubSubClient.h>

// ===== configuración WiFi - MQTT =====
const char* WIFI_SSID = "TFG_TestAP";
const char* WIFI_PASS = "passwordsegura";

const char* MQTT_HOST = "192.168.50.1";   // Raspi5 (wlan1)
const uint16_t MQTT_PORT = 1883;
const char* MQTT_TOPIC = "tfg/sensor1";

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// ===== Hardware de la Rust Board =====
#define SDA_PIN 10
#define SCL_PIN 8

ICM42670 IMU(Wire, 0);   // IMU @ 0x68
Adafruit_SHTC3 SHT;
bool th_ok = false;

// LEDS
#define LED_WHITE_PIN 7
#define NEO_PIN 2
#define NEO_COUNT 1
#define NEO_BRIGHTNESS 20
#define LED_INTERVAL_MS 20

Adafruit_NeoPixel strip(NEO_COUNT, NEO_PIN, NEO_GRB + NEO_KHZ800);

// Timers
unsigned long t_led   = 0;
unsigned long t_sense = 0;
uint16_t hue = 0;

// ==================== Conexión WiFi y MQTT ====================

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println("\n[WiFi] Conectando a TFG_TestAP...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < 15000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("\n[WiFi] Conectado. IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WiFi] NO se pudo conectar (timeout).");
  }
}

void connectMQTT() {
  if (mqttClient.connected()) return;
  if (WiFi.status() != WL_CONNECTED) return;

  Serial.println("[MQTT] Conectando a broker...");
  String clientId = "rustboard-" + String((uint32_t)ESP.getEfuseMac(), HEX);

  if (mqttClient.connect(clientId.c_str())) {
    Serial.println("[MQTT] Conectado a mosquitto en 192.168.50.1");
  } else {
    Serial.print("[MQTT] Fallo, rc=");
    Serial.println(mqttClient.state());
    // No hacer delay grande, ya lo reintenta el loop
  }
}

// ==================== SETUP ====================

void setup() {
  Serial.begin(115200);

  pinMode(LED_WHITE_PIN, OUTPUT);
  digitalWrite(LED_WHITE_PIN, LOW);  // apaga led blanco

  while (!Serial) {}

  // I2C
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);

  // IMU
  int ret = IMU.begin();
  if (ret != 0) {
    Serial.print("ICM42670 init FAILED: ");
    Serial.println(ret);
    while (1) { delay(10); }
  }
  IMU.startAccel(100, 4);
  IMU.startGyro (100, 500);
  delay(100);

  // SHTC3
  th_ok = SHT.begin();
  Serial.println(th_ok ? "SHTC3 OK (0x70)" : "SHTC3 NOT FOUND");

  // NeoPixel
  strip.begin();
  strip.setBrightness(NEO_BRIGHTNESS);
  strip.clear();
  strip.show();

  unsigned long now = millis();
  t_led   = now;
  t_sense = now;

  // WiFi + MQTT
  connectWiFi();
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
}

// ==================== LOOP ====================

void loop() {
  unsigned long now = millis();

  // ----- LED arcoiris -----
  if (now - t_led >= LED_INTERVAL_MS) {
    t_led = now;
    strip.fill(strip.gamma32(strip.ColorHSV(hue)));
    strip.show();
    hue += 256;
  }

  // Mantener WiFi / MQTT
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.loop();

  // ----- Sensores cada 1 s -----
  if (now - t_sense >= 1000) {
    t_sense = now;

    inv_imu_sensor_event_t e;
    IMU.getDataFromRegisters(e);

    float ax = e.accel[0], ay = e.accel[1], az = e.accel[2];
    float pitch = atan2(ay, sqrt(ax*ax + az*az)) * 180.0f / PI;
    float roll  = atan2(-ax, az)                 * 180.0f / PI;

    Serial.println("---------------- LECTURA ----------------");
    Serial.printf("Lateral (X): %.2f° | Frontal (Y): %.2f°\n", pitch, roll);
    Serial.printf("Gyro X/Y/Z: %d / %d / %d\n",
                  e.gyro[0], e.gyro[1], e.gyro[2]);

    float tempC = NAN;
    float humR  = NAN;

    if (th_ok) {
      sensors_event_t hum, temp;
      if (SHT.getEvent(&hum, &temp)) {
        tempC = temp.temperature;
        humR  = hum.relative_humidity;
        Serial.printf("Temp: %.2f°C | Humedad: %.2f %%\n", tempC, humR);
      } else {
        Serial.println("Lectura SHTC3 fallida");
      }
    } else {
      Serial.println("SHTC3 no disponible");
    }

    Serial.println("-----------------------------------------\n");

    // ---- PUBLICAR POR MQTT ----
    if (mqttClient.connected()) {
      char payload[160];
      snprintf(payload, sizeof(payload),
               "{\"ts\":%lu,\"pitch\":%.2f,\"roll\":%.2f,"
               "\"temp\":%.2f,\"hum\":%.2f}",
               now, pitch, roll,
               isnan(tempC) ? 0.0f : tempC,
               isnan(humR)  ? 0.0f : humR);

      if (mqttClient.publish(MQTT_TOPIC, payload)) {
        Serial.print("[MQTT] Publicado: ");
        Serial.println(payload);
      } else {
        Serial.println("[MQTT] ERROR al publicar");
      }
    } else {
      Serial.println("[MQTT] No conectado, no se publica esta vez.");
    }
  }
}