#define ARDUINO_USB_CDC_ON_BOOT 1

#include <Wire.h>
#include "ICM42670P.h"       // sensor IMU
#include <Adafruit_SHTC3.h>  // sensor SHT32
#include <Adafruit_Sensor.h>
#include <Adafruit_NeoPixel.h>

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ===== configuración WiFi - MQTT =====
const char* WIFI_SSID = "TFG_TestAP";
const char* WIFI_PASS = "passwordsegura";

const char* MQTT_HOST = "192.168.50.1";   // Raspi5 (wlan1)
const uint16_t MQTT_PORT = 1883;
const char* MQTT_TOPIC_SENSOR = "tfg/sensor1";
const char* MQTT_TOPIC_ALERTA = "tfg/alerta";
const char* MQTT_TOPIC_IPS_CONTROL = "tfg/ips_control";

// BSSID del AP legítimo (wlan1 de la Raspi)
uint8_t AP_LEGITIMO_BSSID[6] = {0x24, 0xEC, 0x99, 0xCA, 0x88, 0x26};
const int AP_CANAL = 6;

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// ===== IPS =====
bool ips_activo = false;
bool amenaza_detectada = false;
unsigned long t_amenaza = 0;
unsigned long t_ips_log = 0;
unsigned long t_pausa_serial = 0;

// ===== Hardware de la Rust Board =====
#define SDA_PIN 10
#define SCL_PIN 8

ICM42670 IMU(Wire, 0);
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

// ==================== Publicar estado IPS por MQTT ====================

void publicarEstadoIPS() {
  if (!mqttClient.connected()) return;
  
  char payload[100];
  snprintf(payload, sizeof(payload),
    "{\"ips_activo\":%s,\"amenaza\":%s,\"bssid\":\"%s\"}",
    ips_activo ? "true" : "false",
    amenaza_detectada ? "true" : "false",
    WiFi.BSSIDstr().c_str());
  
  mqttClient.publish("tfg/ips_status", payload);
}

// ==================== Callback MQTT ====================

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String topicStr = String(topic);
  
  // --- Control IPS desde dashboard ---
  if (topicStr == MQTT_TOPIC_IPS_CONTROL) {
    StaticJsonDocument<128> doc;
    DeserializationError err = deserializeJson(doc, payload, length);
    if (err) return;
    
    const char* cmd = doc["comando"] | "";
    
    if (String(cmd) == "on") {
      ips_activo = true;
      Serial.println("\n========================================");
      Serial.println("[IPS] 🛡️ IPS ACTIVADO (desde Dashboard)");
      Serial.println("========================================\n");
      blindarAlAPLegitimo();
      t_pausa_serial = millis();
      publicarEstadoIPS();
      
    } else if (String(cmd) == "off") {
      ips_activo = false;
      amenaza_detectada = false;
      Serial.println("\n========================================");
      Serial.println("[IPS] ⚠️ IPS DESACTIVADO (desde Dashboard)");
      Serial.println("========================================\n");
      t_pausa_serial = millis();
      publicarEstadoIPS();
    }
    return;
  }
  
  // --- Alertas del IDS ---
  if (topicStr == MQTT_TOPIC_ALERTA) {
    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, payload, length);
    if (err) {
      Serial.println("[IPS] Error parseando alerta JSON");
      return;
    }

    const char* tipo = doc["tipo"] | "unknown";
    const char* nivel = doc["nivel"] | "ok";

    if (String(nivel) == "critico") {
      if (amenaza_detectada && ips_activo) {
        // Ya blindados, ignorar
        return;
      }
      
      amenaza_detectada = true;
      t_amenaza = millis();
      
      Serial.println("\n========================================");
      Serial.printf("[IPS] 🚨 ALERTA RECIBIDA: %s\n", tipo);
      Serial.println("========================================");

      if (ips_activo) {
        Serial.println("[IPS] 🛡️ IPS ACTIVO — Blindando conexión...");
        blindarAlAPLegitimo();
        Serial.println("[IPS] 🔵 Conexión blindada al AP legítimo");
      } else {
        Serial.println("[IPS] ⚠️ IPS DESACTIVADO — DISPOSITIVO VULNERABLE");
        Serial.println("[IPS]    Activa el IPS desde el Dashboard o escribe 'ips on'");
      }
      
      t_pausa_serial = millis();
      publicarEstadoIPS();
      
    } else {
      if (amenaza_detectada && (millis() - t_amenaza > 10000)) {
        amenaza_detectada = false;
        Serial.println("[IPS] ✅ Amenaza descartada — volviendo a modo normal");
        t_pausa_serial = millis();
        publicarEstadoIPS();
      }
    }
  }
}

// ==================== Blindar al AP legítimo ====================

void blindarAlAPLegitimo() {
  Serial.println("[IPS] Reconectando forzando BSSID del AP legítimo...");
  
  WiFi.disconnect(true);
  delay(500);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS, AP_CANAL, AP_LEGITIMO_BSSID, true);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < 10000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[IPS] ✅ Blindado. IP: %s | BSSID: %s\n", 
      WiFi.localIP().toString().c_str(),
      WiFi.BSSIDstr().c_str());
  } else {
    Serial.println("\n[IPS] ❌ No se pudo conectar al AP legítimo");
  }
}

// ==================== Conexión WiFi ====================

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println("\n[WiFi] Conectando a TFG_TestAP...");
  WiFi.mode(WIFI_STA);

  if (ips_activo) {
    WiFi.begin(WIFI_SSID, WIFI_PASS, AP_CANAL, AP_LEGITIMO_BSSID, true);
    Serial.println("[WiFi] Modo IPS: forzando BSSID legítimo");
  } else {
    WiFi.begin(WIFI_SSID, WIFI_PASS);
  }

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < 15000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] Conectado. IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[WiFi] NO se pudo conectar (timeout).");
  }
}

// ==================== Conexión MQTT ====================

void connectMQTT() {
  if (mqttClient.connected()) return;
  if (WiFi.status() != WL_CONNECTED) return;

  Serial.println("[MQTT] Conectando a broker...");
  String clientId = "rustboard-" + String((uint32_t)ESP.getEfuseMac(), HEX);

  if (mqttClient.connect(clientId.c_str())) {
    Serial.println("[MQTT] Conectado a mosquitto");
    mqttClient.subscribe(MQTT_TOPIC_ALERTA);
    mqttClient.subscribe(MQTT_TOPIC_IPS_CONTROL);
    Serial.printf("[MQTT] Suscrito a: %s, %s\n", MQTT_TOPIC_ALERTA, MQTT_TOPIC_IPS_CONTROL);
    publicarEstadoIPS();
  } else {
    Serial.printf("[MQTT] Fallo, rc=%d\n", mqttClient.state());
  }
}

// ==================== Procesar comandos Serial ====================

void procesarSerial() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toLowerCase();

  if (cmd == "ips on") {
    ips_activo = true;
    Serial.println("\n========================================");
    Serial.println("[IPS] 🛡️ IPS ACTIVADO");
    Serial.println("========================================\n");
    blindarAlAPLegitimo();
    t_pausa_serial = millis();
    publicarEstadoIPS();

  } else if (cmd == "ips off") {
    ips_activo = false;
    amenaza_detectada = false;
    Serial.println("\n========================================");
    Serial.println("[IPS] ⚠️ IPS DESACTIVADO");
    Serial.println("========================================\n");
    t_pausa_serial = millis();
    publicarEstadoIPS();

  } else if (cmd == "status") {
    Serial.println("\n--- STATUS ---");
    Serial.printf("  IPS: %s\n", ips_activo ? "ACTIVO 🛡️" : "DESACTIVADO ⚠️");
    Serial.printf("  WiFi: %s\n", WiFi.status() == WL_CONNECTED ? "Conectado" : "Desconectado");
    Serial.printf("  IP: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("  BSSID: %s\n", WiFi.BSSIDstr().c_str());
    Serial.printf("  MQTT: %s\n", mqttClient.connected() ? "Conectado" : "Desconectado");
    Serial.printf("  Amenaza: %s\n", amenaza_detectada ? "SÍ 🚨" : "No ✅");
    Serial.println("--------------\n");
    t_pausa_serial = millis();

  } else if (cmd == "help") {
    Serial.println("\n--- COMANDOS ---");
    Serial.println("  ips on  / ips off / status / help");
    Serial.println("----------------\n");
    t_pausa_serial = millis();
  }
}

// ==================== SETUP ====================

void setup() {
  Serial.begin(115200);
  pinMode(LED_WHITE_PIN, OUTPUT);
  digitalWrite(LED_WHITE_PIN, LOW);

  delay(2000);

  Serial.println("\n==========================================");
  Serial.println("  Rustboard IoT Client + IPS");
  Serial.println("==========================================");
  Serial.println("  Comandos: 'ips on', 'ips off', 'status'");
  Serial.println("  También controlable desde el Dashboard");
  Serial.println("==========================================\n");

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);

  int ret = IMU.begin();
  if (ret != 0) {
    Serial.printf("ICM42670 init FAILED: %d\n", ret);
    while (1) { delay(10); }
  }
  IMU.startAccel(100, 4);
  IMU.startGyro(100, 500);
  delay(100);

  th_ok = SHT.begin();
  Serial.println(th_ok ? "SHTC3 OK (0x70)" : "SHTC3 NOT FOUND");

  strip.begin();
  strip.setBrightness(NEO_BRIGHTNESS);
  strip.clear();
  strip.show();

  unsigned long now = millis();
  t_led = now;
  t_sense = now;

  connectWiFi();
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
}

// ==================== LOOP ====================

void loop() {
  unsigned long now = millis();

  procesarSerial();

  // ----- LED con 4 estados -----
  if (now - t_led >= LED_INTERVAL_MS) {
    t_led = now;

    if (amenaza_detectada && !ips_activo) {
      // 🔴 ROJO PARPADEANTE: amenaza + vulnerable
      if ((now / 300) % 2 == 0) {
        strip.fill(strip.Color(255, 0, 0));
      } else {
        strip.fill(strip.Color(0, 0, 0));
      }
    } else if (amenaza_detectada && ips_activo) {
      // 🟣 MORADO FIJO: amenaza pero blindado
      strip.fill(strip.Color(128, 0, 255));
    } else if (ips_activo) {
      // 🔵 AZUL FIJO: IPS activo, sin amenaza
      strip.fill(strip.Color(0, 0, 255));
    } else {
      // 🌈 ARCOÍRIS: normal, IPS off
      strip.fill(strip.gamma32(strip.ColorHSV(hue)));
      hue += 256;
    }
    strip.show();
  }

  // Mantener WiFi / MQTT
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.loop();

  // Sensores cada 1s (pausado 5s tras comandos)
  if (now - t_sense >= 1000 && now - t_pausa_serial > 5000) {
    t_sense = now;

    inv_imu_sensor_event_t e;
    IMU.getDataFromRegisters(e);

    float ax = e.accel[0], ay = e.accel[1], az = e.accel[2];
    float pitch = atan2(ay, sqrt(ax * ax + az * az)) * 180.0f / PI;
    float roll  = atan2(-ax, az) * 180.0f / PI;

    Serial.println("---------------- LECTURA ----------------");
    Serial.printf("Lateral (X): %.2f° | Frontal (Y): %.2f°\n", pitch, roll);
    Serial.printf("Gyro X/Y/Z: %d / %d / %d\n", e.gyro[0], e.gyro[1], e.gyro[2]);

    float tempC = NAN, humR = NAN;

    if (th_ok) {
      sensors_event_t hum, temp;
      if (SHT.getEvent(&hum, &temp)) {
        tempC = temp.temperature;
        humR = hum.relative_humidity;
        Serial.printf("Temp: %.2f°C | Humedad: %.2f %%\n", tempC, humR);
      }
    }

    Serial.println("-----------------------------------------\n");

    if (mqttClient.connected()) {
      char payload[200];
      snprintf(payload, sizeof(payload),
        "{\"ts\":%lu,\"pitch\":%.2f,\"roll\":%.2f,"
        "\"temp\":%.2f,\"hum\":%.2f,\"ips\":%s,\"amenaza\":%s}",
        now, pitch, roll,
        isnan(tempC) ? 0.0f : tempC,
        isnan(humR) ? 0.0f : humR,
        ips_activo ? "true" : "false",
        amenaza_detectada ? "true" : "false");

      mqttClient.publish(MQTT_TOPIC_SENSOR, payload);
    }

    if (ips_activo && (now - t_ips_log > 10000)) {
      t_ips_log = now;
      Serial.printf("[IPS] 🛡️ Activo | BSSID: %s | Amenaza: %s\n",
        WiFi.BSSIDstr().c_str(),
        amenaza_detectada ? "SÍ" : "No");
    }
  }
}
