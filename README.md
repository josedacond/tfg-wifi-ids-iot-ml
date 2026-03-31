# 🛡️ Wi-Fi Intrusion Detection System for IoT with Machine Learning

<p align="center">
  <strong>Trabajo Fin de Grado — Ingeniería Electrónica de Comunicaciones</strong><br>
  Universidad Complutense de Madrid · 2025/2026
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Platform-Raspberry%20Pi%205-c51a4a?logo=raspberrypi&logoColor=white" />
  <img src="https://img.shields.io/badge/ML-Random%20Forest-green?logo=scikit-learn&logoColor=white" />
  <img src="https://img.shields.io/badge/IoT-ESP32-orange?logo=espressif&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-yellow" />
</p>

---

## 📌 Descripción

Sistema de detección de intrusiones (IDS) en redes Wi-Fi orientado a entornos IoT, implementado en tiempo real sobre una Raspberry Pi 5. El sistema captura tráfico inalámbrico en modo monitor, lo analiza mediante modelos de Machine Learning (Random Forest) y genera alertas automáticas ante ataques de **Deauthentication** y **Evil Twin**.

El proyecto incluye además un **dashboard web** para monitorización en tiempo real de sensores IoT, un **firmware Evil Twin** para ataques controlados, y un **análisis de seguridad física** del hardware IoT.

**Autor:** José David Conde Quispe  
**Tutor:** Guillermo Botella Juan

---

## 🏗️ Arquitectura del Sistema

```
                    ┌──────────────────────────────────┐
                    │      SISTEMA DE DETECCIÓN        │
                    │        (Raspberry Pi 5)          │
                    │                                  │
                    │  wlan1 (AR9271) ── AP legítimo   │
                    │  wlan2 (AR9271) ── Modo monitor  │
                    │  Mosquitto MQTT ── Broker        │
                    │  Dashboard Web ── Flask+SocketIO │
                    └──────────┬──────────┬────────────┘
                               │          │
                    ┌──────────┘          └──────────┐
                    │                                 │
          ┌─────────────────┐              ┌───────────────────┐
          │   CLIENTE IoT   │              │   MAC (Python)    │
          │  ESP32-C3 Rust  │              │                   │
          │  Board          │              │  IDS Deauth       │
          │  Temp/Hum/IMU   │──── MQTT ───→ │  IDS Evil Twin   │
          │  + MQTT pub     │              │  Alertas MQTT     │
          └─────────────────┘              │  Métricas TPR/FPR │
                                           └───────────────────┘
                    ┌──────────────────┐
                    │   ATACANTES      │
                    │                  │
                    │  ESP32 Marauder  │── Deauth
                    │  ESP32 WROOM-32U │── Evil Twin + Portal Cautivo
                    └──────────────────┘
```

---

## 🎯 Características Principales

- **Detección de Deauthentication** — Modelo Random Forest entrenado con dataset AWID3. TPR ~97%, FPR ~1%.
- **Detección de Evil Twin** — Modelo Random Forest con features de ventana entrenado con tráfico real. TPR ~95%, FPR ~1%.
- **Optimización de hiperparámetros** — Grid Search con validación cruzada (5-fold CV) para ambos modelos.
- **Dashboard web en tiempo real** — Interfaz con datos de sensores IoT, gráficas y alertas de seguridad.
- **Alertas MQTT** — Los IDS publican alertas al broker que el dashboard y los dispositivos reciben.
- **Evil Twin completo** — AP falso + portal cautivo + broker MQTT falso para captura de credenciales y datos IoT.
- **Análisis de seguridad física** — Extracción de firmware, UART sniffing, análisis de eFuses, JTAG expuesto.

---

## 📁 Estructura del Repositorio

```
wifi-ids-iot-ml/
├── models/                            # Entrenamiento de modelos ML
│   ├── train_deauth_awid.py           # Deauth con AWID + GridSearchCV
│   ├── train_eviltwin_real.py         # Evil Twin con datos reales + GridSearchCV
│   └── capture_training_data.py       # Captura de tráfico para entrenamiento
│
├── ids/                               # Detección en tiempo real
│   ├── ids_deauth.py                  # IDS Deauth + métricas + alertas MQTT
│   └── ids_eviltwin.py                # IDS Evil Twin + métricas + alertas MQTT
│
├── firmware/                          # Código de los dispositivos
│   ├── rustboard_client/              # Cliente IoT (ESP32-C3 Rustboard)
│   │   └── rustboard_client.ino
│   └── evil_twin/                     # Atacante Evil Twin (ESP32 WROOM-32U)
│       └── evil_twin.ino
│
├── dashboard/                         # Dashboard web IoT
│   ├── app.py                         # Servidor Flask + SocketIO + MQTT
│   └── templates/
│       ├── login.html
│       └── dashboard.html
│
├── raspi/                             # Configuración Raspberry Pi
│   ├── hostapd.conf                   # Configuración del AP
│   ├── dnsmasq.conf                   # Configuración DHCP/DNS
│   └── setup_guide.md                 # Guía de configuración paso a paso
│
├── security-analysis/                 # Análisis de seguridad física (Parte 4)
│   ├── Parte4_Seguridad_Fisica.md
│   └── efuse_summary.txt
│
├── docs/                              # Documentación
│   ├── arquitectura.md
│   └── metricas.md
│
├── README.md
├── requirements.txt
├── .gitignore
└── LICENSE
```

---

## 🤖 Modelos de Machine Learning

### Modelo Deauth (AWID3)

| Propiedad | Valor |
|-----------|-------|
| Algoritmo | Random Forest (hiperparámetros optimizados con GridSearchCV) |
| Dataset | AWID3 — Deauthentication |
| Features | 6 (type, subtype, signal_dbm, frame_len, retry, duration) |
| Clasificación | Por paquete individual |
| Ventana de alerta | 50 paquetes, umbral >3 maliciosos |

### Modelo Evil Twin (Datos Reales)

| Propiedad | Valor |
|-----------|-------|
| Algoritmo | Random Forest (hiperparámetros optimizados con GridSearchCV) |
| Dataset | Tráfico real capturado en laboratorio (~200k paquetes) |
| Features | 17 features de ventana (estadísticas + Evil Twin específicas) |
| Clasificación | Por ventana de 150 paquetes |
| Features clave | `paquetes_bssid_falso`, `bssids_con_ssid`, `signal_var_same_ssid` |

### Evolución del enfoque ML

1. **Isolation Forest** (no supervisado) → Descartado por exceso de falsos positivos
2. **Random Forest por paquete** (supervisado, AWID3) → Funciona para Deauth, no para Evil Twin en tráfico real
3. **Random Forest por ventana** (supervisado, datos reales) → Modelo final para Evil Twin con 17 features agregadas

---

## 📊 Métricas de Rendimiento

### Validación con hardware real

| Modelo | TPR | FPR | Tiempo detección |
|--------|-----|-----|-----------------|
| **Deauth** | ~97% | ~1% | ~550 ms |
| **Evil Twin** | ~95% | ~1% | ~180 ms |

---

## 🛠️ Hardware Utilizado

| Dispositivo | Rol | Interfaz |
|-------------|-----|----------|
| Raspberry Pi 5 | Sistema de detección (IDS) | wlan0 (SSH), wlan1 (AP), wlan2 (monitor) |
| Atheros AR9271 #1 | Punto de acceso legítimo | wlan1 en modo AP |
| Atheros AR9271 #2 | Captura de tráfico | wlan2 en modo monitor |
| ESP32-C3 Rustboard | Cliente IoT (víctima) | WiFi + MQTT |
| ESP32 WROOM-32U #1 | Atacante Deauth | Firmware Marauder |
| ESP32 WROOM-32U #2 | Atacante Evil Twin | Firmware `evil_twin.ino` |

---

## ⚙️ Instalación y Uso

### Requisitos

```bash
pip install pandas scikit-learn joblib paho-mqtt flask flask-socketio
```

### 1. Configurar la Raspberry Pi

Seguir la guía en [`raspi/setup_guide.md`](raspi/setup_guide.md) para configurar:
- AP con hostapd (wlan1)
- DHCP con dnsmasq
- Modo monitor (wlan2)
- Broker MQTT (Mosquitto)

### 2. Entrenar los modelos

```bash
# Deauth (requiere dataset AWID3)
python models/train_deauth_awid.py

# Evil Twin (requiere captura previa con capture_training_data.py)
python models/train_eviltwin_real.py
```

### 3. Lanzar el Dashboard

```bash
cd dashboard
sudo python app.py
# Acceder desde http://192.168.50.1:8080 (login: admin / tfg2026)
```

### 4. Lanzar el IDS

```bash
# Detección de Deauth
python ids/ids_deauth.py

# Detección de Evil Twin
python ids/ids_eviltwin.py
```

### 5. Flashear firmware

- **Rustboard:** Abrir `firmware/rustboard_client/rustboard_client.ino` en Arduino IDE, seleccionar ESP32-C3 Dev Module
- **Evil Twin:** Abrir `firmware/evil_twin/evil_twin.ino` en Arduino IDE, seleccionar ESP32 Dev Module

---

## 🔬 Dataset

- **Deauth:** Dataset público [AWID3 (Aegean Wireless Intrusion Dataset)](https://icsdweb.aegean.gr/awid/)
- **Evil Twin:** Tráfico real capturado en el laboratorio con `models/capture_training_data.py`

> Los datasets no se incluyen en el repositorio por su tamaño. AWID3 debe descargarse desde el enlace oficial.

---

## 🔒 Análisis de Seguridad Física

Se realizó un análisis completo de la seguridad del hardware IoT (ESP32-C3 Rustboard), documentado en [`security-analysis/Parte4_Seguridad_Fisica.md`](security-analysis/Parte4_Seguridad_Fisica.md):

| Vulnerabilidad | Vector | Impacto |
|----------------|--------|---------|
| Extracción de firmware | `esptool read-flash` | Credenciales WiFi/MQTT en texto plano |
| UART/USB expuesto | Monitor Serie sin autenticación | Fuga de datos de sensores y configuración |
| JTAG habilitado | Depuración por USB/pines | Acceso total a memoria del dispositivo |
| Sin Secure Boot | Inyección de firmware malicioso | Control total del dispositivo |
| MQTT sin cifrar | Sniffing con `mosquitto_sub` | Intercepción de datos de sensores |

---

## 🚀 Trabajo Futuro

- **IPS (Intrusion Prevention System):** Respuesta automática ante ataques — blindado del dispositivo IoT al AP legítimo.
- **Cloud Security:** Integración con servicios cloud (AWS IoT Core, Azure IoT Hub) para monitorización remota.
- **Secure Boot + Flash Encryption:** Activación de protecciones hardware en el ESP32-C3.
- **TLS en MQTT:** Cifrado de las comunicaciones entre dispositivos y broker.
- **Modelo multiclase:** Unificación de los detectores en un solo modelo capaz de clasificar múltiples ataques.
- **Notificaciones remotas:** Alertas por Telegram o push notifications.

---

## ⚠️ Aviso Legal

Este proyecto es de investigación académica. Todas las técnicas de ataque se utilizan exclusivamente en un laboratorio controlado y aislado, sin conexión a redes de producción. El uso de estas técnicas fuera de un entorno autorizado puede ser ilegal.

---

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver [`LICENSE`](LICENSE) para más detalles.
