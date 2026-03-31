# Parte 4 — Análisis de Seguridad Física y Hardware del Dispositivo IoT

## 4.1 Introducción

A diferencia de los ataques de red analizados en las partes anteriores (Deauthentication y Evil Twin), que se realizan de forma remota, la seguridad en hardware asume un escenario donde el atacante tiene **acceso físico** al dispositivo IoT.

Este vector de ataque es crítico en el Internet de las Cosas, ya que estos dispositivos suelen desplegarse en entornos no controlados (edificios inteligentes, industrias, exteriores) donde quedan expuestos a manipulación directa.

En esta sección se evalúa la resistencia de la **ESP32-C3 Rust Board** (Espressif) frente a ataques que explotan interfaces físicas y la falta de protección en el firmware, demostrando que la seguridad perimetral (red Wi-Fi, IDS) es insuficiente si el hardware subyacente es vulnerable.

Todos los ataques descritos a continuación han sido **reproducidos en el laboratorio** como parte de la validación práctica del TFG.

---

## 4.2 Vulnerabilidad 1 — Extracción de Firmware y Credenciales (Firmware Dumping)

### 4.2.1 Descripción

Este ataque representa uno de los vectores más directos contra un dispositivo IoT con acceso físico. Utilizando herramientas del propio fabricante (`esptool`), un atacante puede volcar la totalidad de la memoria flash del microcontrolador a un archivo binario, para después extraer información sensible mediante análisis de cadenas de texto.

Este ataque explota la ausencia de **Flash Encryption** en el dispositivo, lo que permite leer el contenido de la memoria sin ningún tipo de descifrado.

### 4.2.2 Demostración práctica

Se conectó la Rustboard ESP32-C3 al equipo atacante mediante un cable USB-C y se ejecutó el siguiente comando:

```
esptool --port /dev/cu.usbmodem1101 read-flash 0 0x400000 firmware_rustboard.bin
```

**Resultado:** Se descargaron 4.194.304 bytes (4 MB) de la memoria flash completa en 364,7 segundos.

Posteriormente, se realizó una búsqueda de cadenas de texto sensibles sin conocimiento previo del contenido:

```
strings firmware_rustboard.bin | grep -i -E "ssid|pass|key|host|broker|mqtt|wifi|192\.|172\.|10\."
```

**Información extraída en texto plano:**

| Dato | Valor encontrado | Apariciones |
|------|------------------|-------------|
| Contraseña Wi-Fi | `passwordsegura` | 7 veces |
| SSID de la red | `TFG_TestAP` | Múltiples |
| IP del broker MQTT | `192.168.50.1` | Múltiples |
| Mensajes de debug | Estados de conexión WiFi y MQTT | Múltiples |

Con esta información, un atacante puede conectarse a la red IoT, suscribirse al broker MQTT, interceptar datos de sensores o lanzar ataques dirigidos contra la infraestructura.

### 4.2.3 Causa raíz

El análisis de los eFuses del ESP32-C3 mediante `espefuse summary` confirmó:

- **`SPI_BOOT_CRYPT_CNT = Disable`** → Flash Encryption desactivada
- **`DIS_DOWNLOAD_MODE = False`** → Modo de descarga habilitado sin restricciones
- **`BLOCK_KEY0..5 = 00 00 00...`** → No hay claves de cifrado configuradas

### 4.2.4 Impacto

- **Confidencialidad:** Comprometida. Credenciales de red, IPs y topología del sistema expuestas.
- **Modelo de ataque:** Un atacante con acceso físico de ~6 minutos puede obtener acceso completo a la red IoT.

### 4.2.5 Mitigación

- Activar **Flash Encryption** en modo `Release` mediante los eFuses del ESP32.
- Almacenar credenciales en la partición NVS cifrada, no hardcodeadas en el código fuente.
- Deshabilitar el modo de descarga en producción (`DIS_DOWNLOAD_MODE = True`).

---

## 4.3 Vulnerabilidad 2 — Exposición de Información vía UART/USB (CWE-532)

### 4.3.1 Descripción

El protocolo UART (Universal Asynchronous Receiver-Transmitter) es una interfaz de comunicación serie comúnmente utilizada para tareas de depuración durante el desarrollo. Esta vulnerabilidad se clasifica como **CWE-532: Insertion of Sensitive Information into Log File**.

El dispositivo IoT, en su configuración por defecto, mantiene habilitada la salida de logs a través de la interfaz USB-Serial nativa del ESP32-C3, sin ningún mecanismo de autenticación.

### 4.3.2 Demostración práctica

Se conectó la Rustboard a un equipo mediante USB-C y se abrió una sesión serie a 115200 baudios. Sin necesidad de autenticación, contraseña ni herramientas especiales, se obtuvo la siguiente información en tiempo real:

```
---------------- LECTURA ----------------
Lateral (X): 0.95° | Frontal (Y): -8.37°
Gyro X/Y/Z: -2 / 83 / 15
Temp: 30.39°C | Humedad: 28.69 %
-----------------------------------------

[WiFi] Conectando a TFG_TestAP...
[WiFi] NO se pudo conectar (timeout).
[MQTT] No conectado, no se publica esta vez.
```

**Información expuesta sin autenticación:**
- Datos de telemetría de los sensores (temperatura, humedad, giroscopio, acelerómetro)
- Nombre de la red Wi-Fi a la que intenta conectarse (SSID)
- Estado de la conexión MQTT y dirección del broker
- Mensajes de error que revelan la arquitectura del sistema

### 4.3.3 Causa raíz

Esta vulnerabilidad tiene dos capas independientes que deben abordarse por separado:

**Capa de software (firmware):** El firmware del dispositivo incluye instrucciones explícitas de impresión por consola (`Serial.println()`) que fueron añadidas durante el desarrollo para tareas de depuración. Estas instrucciones imprimen deliberadamente datos de sensores, estados de conexión y credenciales. Esto es una decisión del desarrollador que puede eliminarse del código fuente.

**Capa de hardware (eFuses):** Incluso si se eliminan las instrucciones de impresión del firmware, la interfaz USB-Serial permanece abierta a nivel de hardware. El análisis de los eFuses confirmó:

- **`UART_PRINT_CONTROL = Enable`** → La salida UART de arranque está habilitada
- **`DIS_USB_SERIAL_JTAG = Enable (False)`** → La interfaz USB-Serial-JTAG está activa
- **`DIS_USB_SERIAL_JTAG_ROM_PRINT = Enable`** → El ROM bootloader imprime por USB

Esto significa que el bootloader del ESP32 seguirá imprimiendo información del sistema al arrancar (versión del chip, modo de arranque, etc.), y que la interfaz JTAG accesible por USB permite a un atacante inspeccionar la memoria del dispositivo incluso sin prints en el firmware.

### 4.3.4 Impacto

- **Confidencialidad:** Comprometida. Fuga de datos operacionales y de configuración.
- **Modelo de ataque:** Escucha pasiva; no requiere herramientas criptográficas. Un atacante puede pivotar hacia ataques de red con el conocimiento previo obtenido.

### 4.3.5 Mitigación

La protección completa requiere actuar en ambas capas:

**Software:** Eliminar todas las instrucciones `Serial.println()` del firmware de producción o deshabilitar el logging mediante directivas de preprocesador: `#define CONFIG_LOG_DEFAULT_LEVEL ESP_LOG_NONE`.

**Hardware:** Quemar el eFuse `DIS_USB_SERIAL_JTAG_ROM_PRINT` para desactivar la impresión del bootloader. Deshabilitar la interfaz USB-Serial si no se necesita en producción.

Aplicar solo una de las dos capas es insuficiente: sin protección hardware, un atacante podría flashear un firmware que reactive los prints; sin eliminar los prints, se desperdician recursos y se mantiene el riesgo si las protecciones hardware se omiten o fallan.

---

## 4.4 Vulnerabilidad 3 — Interfaces de Depuración Expuestas (JTAG)

### 4.4.1 Descripción

JTAG (Joint Test Action Group) es un protocolo de depuración hardware que permite a un atacante con acceso físico inspeccionar la memoria del microcontrolador en tiempo real, establecer breakpoints, modificar registros y extraer claves criptográficas directamente del hardware.

### 4.4.2 Demostración práctica

El análisis de eFuses reveló que todas las interfaces de depuración están completamente abiertas:

| eFuse | Valor | Significado |
|-------|-------|-------------|
| `SOFT_DIS_JTAG` | 0 (0b000) | JTAG por software habilitado |
| `DIS_PAD_JTAG` | False | JTAG por pines físicos habilitado |
| `DIS_USB_JTAG` | False | JTAG por USB habilitado |

Esto significa que un atacante puede conectar un depurador JTAG (o usar la propia interfaz USB del dispositivo) para:
- Leer y modificar la memoria RAM en tiempo real
- Extraer claves criptográficas almacenadas en memoria volátil
- Inyectar código arbitrario durante la ejecución
- Analizar el flujo de ejecución del firmware

### 4.4.3 Impacto

- **Confidencialidad e Integridad:** Comprometidas. Acceso total al estado interno del dispositivo.
- **Modelo de ataque:** Requiere un depurador JTAG (~10€) y acceso físico.

### 4.4.4 Mitigación

- Quemar el eFuse `DIS_PAD_JTAG = True` para deshabilitar JTAG permanentemente por hardware
- Quemar `DIS_USB_JTAG = True` para deshabilitar JTAG por USB
- Nota: Estos eFuses son **irreversibles** (OTP - One Time Programmable)

---

## 4.5 Vulnerabilidad 4 — Ausencia de Secure Boot (Inyección de Firmware)

### 4.5.1 Descripción

Secure Boot es un mecanismo que verifica criptográficamente la integridad y autenticidad del firmware antes de ejecutarlo. Sin Secure Boot, el dispositivo acepta y ejecuta cualquier firmware que se cargue en su memoria flash, sin verificar su origen ni integridad.

### 4.5.2 Demostración práctica

El análisis de eFuses confirmó:

| eFuse | Valor | Significado |
|-------|-------|-------------|
| `SECURE_BOOT_EN` | False | Secure Boot desactivado |
| `SECURE_BOOT_AGGRESSIVE_REVOKE` | False | Revocación agresiva desactivada |
| `SECURE_BOOT_KEY_REVOKE0..2` | False | No hay claves de Secure Boot configuradas |
| `KEY_PURPOSE_0..5` | USER | No hay claves dedicadas a Secure Boot ni Flash Encryption |
| `SECURE_VERSION` | 0 | Anti-rollback no configurado |

Esto permite un ataque de dos fases:

**Fase 1 — Extracción:** El atacante descarga el firmware legítimo (demostrado en la sección 4.2) para análisis o ingeniería inversa.

**Fase 2 — Inyección:** El atacante genera un firmware modificado (malicioso) y lo carga en el dispositivo. Por ejemplo:
- Un firmware que envía datos falsificados al broker MQTT (temperaturas alteradas, alertas falsas)
- Un firmware que actúa como backdoor, reenviando los datos a un servidor del atacante
- Un firmware que inutiliza el dispositivo (bricking)
- Un firmware que deshabilita la suscripción a las alertas del IDS (topic `tfg/alerta`), anulando la respuesta defensiva del dispositivo frente a ataques de red como Deauth o Evil Twin. Esto convierte al dispositivo en un objetivo que no reacciona ante las alertas del sistema de detección, facilitando **ataques combinados hardware-red** donde el compromiso físico del dispositivo potencia la efectividad de los ataques inalámbricos

Este último ejemplo es especialmente relevante en el contexto de este TFG, ya que demuestra que la seguridad del sistema IDS/IPS implementado en las Partes 1-3 depende directamente de la integridad del firmware del dispositivo IoT. Sin Secure Boot, un atacante puede neutralizar las defensas de red comprometiendo el hardware.

El dispositivo ejecutará el firmware malicioso sin ninguna verificación, ya que no existe una **Cadena de Confianza (Chain of Trust)**.

### 4.5.3 Impacto

- **Integridad:** Comprometida totalmente. El atacante controla el comportamiento del dispositivo.
- **Disponibilidad:** Comprometida si el firmware malicioso inutiliza el dispositivo.
- **Autenticidad:** No hay garantía de que el firmware en ejecución sea legítimo.

### 4.5.4 Mitigación

- Activar **Secure Boot V2** del ESP32-C3, que verifica la firma RSA-3072 o ECDSA del firmware antes del arranque
- Configurar **anti-rollback** (`SECURE_VERSION`) para prevenir la carga de firmwares antiguos con vulnerabilidades conocidas
- Combinar con Flash Encryption para proteger tanto la integridad como la confidencialidad del firmware

---

## 4.6 Vulnerabilidad 5 — Comunicación MQTT sin Cifrado

### 4.6.1 Descripción

Los datos de telemetría enviados por la Rustboard al broker Mosquitto viajan mediante MQTT sobre TCP sin cifrado TLS. Cualquier dispositivo conectado a la red puede interceptar estos datos mediante herramientas estándar.

### 4.6.2 Demostración práctica

Desde cualquier dispositivo conectado al AP `TFG_TestAP`:

```
mosquitto_sub -h 192.168.50.1 -t "tfg/sensor1" -v
```

**Resultado:** Se reciben en texto plano todos los datos de los sensores:

```json
tfg/sensor1 {"ts":1838402,"pitch":0.01,"roll":-0.08,"temp":29.48,"hum":52.02}
```

No se requiere autenticación ni credenciales para suscribirse al broker.

### 4.6.3 Impacto

- **Confidencialidad:** Comprometida. Datos de sensores accesibles sin autorización.
- **Integridad:** Un atacante podría publicar datos falsos en el mismo topic.

### 4.6.4 Mitigación

- Configurar Mosquitto con **TLS** (certificados SSL) para cifrar las comunicaciones
- Habilitar **autenticación** en el broker (usuario/contraseña o certificados cliente)
- Implementar **ACLs** (Access Control Lists) para restringir quién puede publicar/suscribirse a cada topic

---

## 4.7 Resumen de Impacto (Modelo CIA)

| Vulnerabilidad | Confidencialidad | Integridad | Disponibilidad |
|---------------|-----------------|------------|----------------|
| Extracción de firmware | ✅ Comprometida | — | — |
| Exposición UART/USB | ✅ Comprometida | — | — |
| JTAG expuesto | ✅ Comprometida | ✅ Comprometida | — |
| Sin Secure Boot | — | ✅ Comprometida | ✅ Comprometida |
| MQTT sin cifrar | ✅ Comprometida | ✅ Comprometida | — |

---

## 4.8 Resumen de eFuses de Seguridad del ESP32-C3

| eFuse | Valor actual | Valor seguro | Estado |
|-------|-------------|-------------|--------|
| SECURE_BOOT_EN | False | True | ❌ Inseguro |
| SPI_BOOT_CRYPT_CNT | Disable | Enable | ❌ Inseguro |
| DIS_PAD_JTAG | False | True | ❌ Inseguro |
| DIS_USB_JTAG | False | True | ❌ Inseguro |
| SOFT_DIS_JTAG | 0 | Odd number | ❌ Inseguro |
| UART_PRINT_CONTROL | Enable | Disable | ❌ Inseguro |
| DIS_DOWNLOAD_MODE | False | True | ❌ Inseguro |
| DIS_USB_SERIAL_JTAG_ROM_PRINT | Enable | Disable | ❌ Inseguro |
| KEY_PURPOSE_0..5 | USER | Secure Boot/Encryption | ❌ No configurado |

---

## 4.9 Conclusión

El análisis demuestra que la seguridad perimetral basada en IDS/IPS y cifrado Wi-Fi es **necesaria pero no suficiente** para proteger un sistema IoT. Un dispositivo físicamente accesible sin protecciones de hardware presenta una superficie de ataque que permite a un adversario comprometer completamente la confidencialidad, integridad y disponibilidad del sistema.

La combinación de **Flash Encryption**, **Secure Boot**, deshabilitación de interfaces de depuración y **cifrado TLS en MQTT** constituye el conjunto mínimo de medidas necesarias para cerrar estos vectores de ataque en un despliegue real.

Estas medidas se proponen como **trabajo futuro** para evolucionar el prototipo del laboratorio hacia un sistema listo para producción.
