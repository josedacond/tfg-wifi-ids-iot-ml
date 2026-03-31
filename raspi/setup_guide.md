# Guía de Configuración — Raspberry Pi 5

## Requisitos Previos

- Raspberry Pi 5 con Raspberry Pi OS
- 2x Adaptador Wi-Fi USB Atheros AR9271
- Mosquitto instalado (`sudo apt install mosquitto mosquitto-clients`)
- tshark instalado (`sudo apt install tshark`)
- Python 3 con pip

---

## Pasos de Configuración (ejecutar en cada inicio)

### 1. Configurar wlan1 como AP

```bash
sudo ip link set wlan1 down
sudo ip addr flush dev wlan1
sudo ip addr add 192.168.50.1/24 dev wlan1
sudo ip link set wlan1 up
```

> Para hacer la IP permanente, añadir al final de `/etc/dhcpcd.conf`:
> ```
> interface wlan1
> static ip_address=192.168.50.1/24
> nohook wpa_supplicant
> ```

### 2. Levantar AP y DHCP

```bash
sudo systemctl restart hostapd
sudo systemctl restart dnsmasq
```

### 3. Poner wlan2 en modo monitor (canal 6)

```bash
sudo ip link set wlan2 down
sudo iw dev wlan2 set type monitor
sudo ip link set wlan2 up
sudo iw dev wlan2 set channel 6
```

### 4. Iniciar Mosquitto

```bash
sudo systemctl restart mosquitto
```

### 5. Verificar todo

```bash
sudo systemctl status hostapd --no-pager | grep AP-ENABLED
sudo systemctl status dnsmasq --no-pager | grep active
sudo systemctl status mosquitto --no-pager | grep active
iw dev wlan2 info | grep type
```

Debe salir: hostapd AP-ENABLED, dnsmasq active, mosquitto active, wlan2 type monitor.

### 6. Verificar datos de la Rustboard

```bash
mosquitto_sub -t "tfg/sensor1" -v
```

---

## Lanzar el Dashboard

```bash
cd ~/tfg_dashboard
source .venv/bin/activate
sudo .venv/bin/python app.py
```

Acceder desde: `http://192.168.50.1:8080` (login: admin / tfg2026)

---

## Archivos de Configuración

### hostapd.conf (`/etc/hostapd/hostapd.conf`)

```
interface=wlan1
driver=nl80211
ssid=TFG_TestAP
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
wpa_passphrase=passwordsegura
```

### dnsmasq.conf (`/etc/dnsmasq.conf`)

```
interface=wlan1
dhcp-range=192.168.50.10,192.168.50.200,12h
dhcp-option=3,192.168.50.1
dhcp-option=6,192.168.50.1
server=8.8.8.8
listen-address=127.0.0.1,192.168.50.1
bind-interfaces
```

---

## Conexión Remota (fuera de casa)

La Raspberry Pi tiene guardada la red del hotspot móvil. Se conecta automáticamente si no encuentra la red de casa.

Para encontrar la IP de la Raspi en el hotspot:

```bash
for i in $(seq 1 254); do ping -c 1 -W 1 10.38.151.$i &>/dev/null && echo "10.38.151.$i está vivo"; done
```

Luego conectar por SSH:

```bash
ssh joseda_cond@[IP_ENCONTRADA]
```

---

## Nota sobre la IP del MQTT Broker

El broker Mosquitto corre en la Raspi y escucha en todas las interfaces. Los scripts IDS que corren en el Mac deben apuntar a la IP correcta según la red:

| Red | IP del broker (MQTT_BROKER) |
|-----|----------------------------|
| Casa (MOVISTAR) | `192.168.1.49` |
| Hotspot móvil | La IP que tenga la Raspi en el hotspot |
| Desde el AP (TFG_TestAP) | `192.168.50.1` |
