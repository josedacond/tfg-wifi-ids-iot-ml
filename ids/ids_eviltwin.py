# =============================================================================
#        IDS EVIL TWIN — ML CON FEATURES DE VENTANA + ALERTAS MQTT
# =============================================================================
#
#  Modelo entrenado con tráfico real del laboratorio.
#  Clasifica ventanas usando features agregadas que capturan
#  la presencia de APs duplicados (Evil Twin).
#
#  ALERTAS MQTT:
#    Publica en tfg/alerta cuando detecta ataque.
#    El dashboard y la Rustboard pueden suscribirse para reaccionar.
#
# =============================================================================

import subprocess
import pandas as pd
import numpy as np
import joblib
import json
import warnings
import time
import threading
import csv
import os
import paho.mqtt.client as mqtt_client
from datetime import datetime

warnings.filterwarnings("ignore")

# =============================================================================
#                              CONFIGURACIÓN
# =============================================================================

RASPI_IP = "10.44.92.213"
RASPI_USER = "joseda_cond"
INTERFAZ = "wlan2"
MODELO_PATH = "/Users/joseda_cond/Desktop/- TFG -/TrainedModels/modelo_eviltwin_hibrido.pkl"
FEATURES_PATH = "/Users/joseda_cond/Desktop/- TFG -/TrainedModels/modelo_eviltwin_hibrido_features.json"

# AP legítimo
AP_LEGITIMO_BSSID = "24:ec:99:ca:88:26"
AP_LEGITIMO_SSID = "TFG_TestAP"

# Ventana
TAMANO_VENTANA = 150

# MQTT para alertas
MQTT_BROKER = "10.39.89.213"
MQTT_PORT = 1883
MQTT_TOPIC_ALERTA = "tfg/alerta"

# Log
timestamp_inicio = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_CSV = f"/Users/joseda_cond/Desktop/- TFG -/logs/log_ids_eviltwin_ml_{timestamp_inicio}.csv"

# =============================================================================
#                     CONEXIÓN MQTT PARA ALERTAS
# =============================================================================

mqtt_alertas = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)

try:
    mqtt_alertas.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_alertas.loop_start()
    mqtt_ok = True
    print(f"[MQTT] Conectado a {MQTT_BROKER} para alertas")
except Exception as e:
    mqtt_ok = False
    print(f"[MQTT] No se pudo conectar ({e}). Alertas desactivadas.")

# =============================================================================
#                     CONTROL DE MODO
# =============================================================================

modo_ataque = False
lock_modo = threading.Lock()

def escuchar_teclado():
    global modo_ataque
    while True:
        try:
            input()
            with lock_modo:
                modo_ataque = not modo_ataque
                estado = "🔴 ATAQUE (Evil Twin ON)" if modo_ataque else "🟢 NORMAL (Evil Twin OFF)"
                print(f"\n{'='*55}")
                print(f"  Modo cambiado a: {estado}")
                print(f"{'='*55}\n")
        except EOFError:
            break

# =============================================================================
#               FUNCIÓN: decodificar SSID hex a texto
# =============================================================================

def hex_to_ssid(hex_str):
    try:
        if hex_str and len(str(hex_str).strip()) > 0:
            return bytes.fromhex(str(hex_str).strip()).decode('utf-8', errors='ignore')
    except (ValueError, UnicodeDecodeError):
        pass
    return ""

# =============================================================================
#               FUNCIÓN: extraer features de ventana
# =============================================================================

def extraer_features_ventana(paquetes_features, paquetes_bssid_ssid):
    df = pd.DataFrame(paquetes_features, columns=[
        'wlan.fc.type', 'wlan.fc.subtype', 'wlan_radio.signal_dbm',
        'frame.len', 'wlan.fc.retry', 'wlan.duration'
    ])

    for col in ['wlan.fc.type', 'wlan.fc.subtype', 'wlan_radio.signal_dbm',
                'frame.len', 'wlan.duration']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df['wlan.fc.retry'] = df['wlan.fc.retry'].apply(
        lambda x: 1 if str(x).lower() == 'true' else 0
    )
    df = df.fillna(0)

    df_bs = pd.DataFrame(paquetes_bssid_ssid, columns=['bssid', 'ssid_hex'])
    n = len(df)

    signal_mean = df['wlan_radio.signal_dbm'].mean()
    signal_std = df['wlan_radio.signal_dbm'].std()
    frame_len_mean = df['frame.len'].mean()
    frame_len_std = df['frame.len'].std()
    retry_sum = df['wlan.fc.retry'].sum()
    duration_mean = df['wlan.duration'].mean()

    type0_count = (df['wlan.fc.type'] == 0).sum()
    type1_count = (df['wlan.fc.type'] == 1).sum()
    type2_count = (df['wlan.fc.type'] == 2).sum()

    beacon_count = ((df['wlan.fc.type'] == 0) & (df['wlan.fc.subtype'] == 8)).sum()
    probe_resp_count = ((df['wlan.fc.type'] == 0) & (df['wlan.fc.subtype'] == 5)).sum()
    probe_req_count = ((df['wlan.fc.type'] == 0) & (df['wlan.fc.subtype'] == 4)).sum()
    beacon_ratio = beacon_count / n

    ssid_mask = df_bs['ssid_hex'].apply(
        lambda x: hex_to_ssid(str(x)) == AP_LEGITIMO_SSID if pd.notna(x) and str(x).strip() else False
    )
    ssid_matches = df_bs[ssid_mask]

    bssids_con_ssid = ssid_matches['bssid'].nunique() if len(ssid_matches) > 0 else 0

    paquetes_bssid_falso = 0
    if len(ssid_matches) > 0:
        paquetes_bssid_falso = (ssid_matches['bssid'].str.lower() != AP_LEGITIMO_BSSID.lower()).sum()

    bssids_totales = df_bs['bssid'].replace('', np.nan).dropna().nunique()

    signal_var_same_ssid = 0
    if len(ssid_matches) > 1:
        idx_matches = ssid_matches.index
        signals = df.loc[idx_matches, 'wlan_radio.signal_dbm']
        signal_var_same_ssid = signals.std()
        if pd.isna(signal_var_same_ssid):
            signal_var_same_ssid = 0

    return {
        'signal_mean': signal_mean,
        'signal_std': signal_std if not pd.isna(signal_std) else 0,
        'frame_len_mean': frame_len_mean,
        'frame_len_std': frame_len_std if not pd.isna(frame_len_std) else 0,
        'retry_sum': retry_sum,
        'duration_mean': duration_mean,
        'type0_mgmt': type0_count,
        'type1_ctrl': type1_count,
        'type2_data': type2_count,
        'beacon_count': beacon_count,
        'probe_resp_count': probe_resp_count,
        'probe_req_count': probe_req_count,
        'beacon_ratio': beacon_ratio,
        'bssids_con_ssid': bssids_con_ssid,
        'paquetes_bssid_falso': paquetes_bssid_falso,
        'bssids_totales': bssids_totales,
        'signal_var_same_ssid': signal_var_same_ssid,
    }, paquetes_bssid_falso, bssids_con_ssid

# =============================================================================
#                          CARGAR MODELO
# =============================================================================

print("\n" + "="*55)
print("  IDS EVIL TWIN — ML Ventana + Alertas MQTT")
print("="*55)
print(f"\n  Modelo:      {MODELO_PATH}")
print(f"  AP legítimo: {AP_LEGITIMO_SSID} ({AP_LEGITIMO_BSSID})")

modelo = joblib.load(MODELO_PATH)
with open(FEATURES_PATH, 'r') as f:
    feature_names = json.load(f)

print(f"  Features:    {len(feature_names)}")
print("  Modelo cargado correctamente.\n")

# =============================================================================
#                        CONEXIÓN SSH
# =============================================================================

comando_ssh = [
    "ssh", f"{RASPI_USER}@{RASPI_IP}",
    f"echo 'vayatela' | sudo -S tshark -l -i {INTERFAZ} -T fields "
    f"-e wlan.fc.type -e wlan.fc.subtype -e wlan_radio.signal_dbm "
    f"-e frame.len -e wlan.fc.retry -e wlan.duration "
    f"-e wlan.bssid -e wlan.ssid"
]

print(f"Conectándose a {RASPI_IP} por SSH...")
print("Esperando paquetes de tráfico...\n")
print("-"*55)
print("  INSTRUCCIONES:")
print("  → Enciende el ESP32 Evil Twin")
print("  → Espera 3-4 seg, pulsa ENTER (modo ataque)")
print("  → Apaga Evil Twin, espera, pulsa ENTER")
print("  → Ctrl+C para métricas")
print("-"*55)
print(f"\n  Modo actual: 🟢 NORMAL (Evil Twin OFF)\n")

proceso = subprocess.Popen(
    comando_ssh,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True
)

# =============================================================================
#                         LOGGING Y MÉTRICAS
# =============================================================================

log_data = []

def guardar_log():
    if not log_data:
        print("No hay datos para guardar.")
        return
    with open(LOG_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'timestamp', 'ventana_num', 'prediccion_ml',
            'bssid_falsos', 'bssids_con_ssid',
            'alerta', 'ground_truth', 'tiempo_ventana_ms'
        ])
        writer.writerows(log_data)
    print(f"\n📁 Log guardado en: {os.path.abspath(LOG_CSV)}")

def calcular_metricas():
    if not log_data:
        print("No hay datos suficientes para métricas.")
        return

    df = pd.DataFrame(log_data, columns=[
        'timestamp', 'ventana_num', 'prediccion_ml',
        'bssid_falsos', 'bssids_con_ssid',
        'alerta', 'ground_truth', 'tiempo_ventana_ms'
    ])

    ventanas_ataque = df[df['ground_truth'] == 1]
    ventanas_normal = df[df['ground_truth'] == 0]

    print(f"\n  Total ventanas analizadas:  {len(df)}")
    print(f"  Ventanas en modo ATAQUE:    {len(ventanas_ataque)}")
    print(f"  Ventanas en modo NORMAL:    {len(ventanas_normal)}")
    print(f"\n  {'─'*46}")

    if len(ventanas_ataque) > 0:
        tp = ventanas_ataque['alerta'].sum()
        tpr = tp / len(ventanas_ataque) * 100
        print(f"  ✅ TPR (True Positive Rate):   {tpr:.1f}%  ({int(tp)}/{len(ventanas_ataque)})")
    else:
        print(f"  ⚠️  TPR: Sin datos")

    if len(ventanas_normal) > 0:
        fp = ventanas_normal['alerta'].sum()
        fpr = fp / len(ventanas_normal) * 100
        print(f"  ❌ FPR (False Positive Rate):  {fpr:.1f}%  ({int(fp)}/{len(ventanas_normal)})")
    else:
        print(f"  ⚠️  FPR: Sin datos")

    if len(ventanas_ataque) > 0:
        tiempo_medio = ventanas_ataque['tiempo_ventana_ms'].mean()
        print(f"  ⏱️  Tiempo medio detección:    {tiempo_medio:.0f} ms")

    print(f"  {'─'*46}")
    print("="*55)

# =============================================================================
#                      BUCLE PRINCIPAL
# =============================================================================

hilo_teclado = threading.Thread(target=escuchar_teclado, daemon=True)
hilo_teclado.start()

ventana_features = []
ventana_bssid_ssid = []
ventana_num = 0
tiempo_inicio_ventana = time.time()

try:
    for linea in proceso.stdout:
        datos = linea.strip().split('\t')

        if len(datos) >= 6:
            features = datos[:6]
            bssid = datos[6].strip() if len(datos) > 6 else ''
            ssid_hex = datos[7].strip() if len(datos) > 7 else ''

            if len(ventana_features) == 0:
                tiempo_inicio_ventana = time.time()

            ventana_features.append(features)
            ventana_bssid_ssid.append((bssid, ssid_hex))

            if len(ventana_features) >= TAMANO_VENTANA:
                tiempo_ventana_ms = (time.time() - tiempo_inicio_ventana) * 1000
                ventana_num += 1

                # Extraer features de ventana
                feat_dict, bssid_falsos, bssids_ssid = extraer_features_ventana(
                    ventana_features, ventana_bssid_ssid
                )

                # Predicción ML
                X = pd.DataFrame([feat_dict])[feature_names]
                prediccion = modelo.predict(X)[0]
                alerta = int(prediccion == 1)

                with lock_modo:
                    gt = 1 if modo_ataque else 0

                log_data.append([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    ventana_num,
                    int(prediccion),
                    int(bssid_falsos),
                    int(bssids_ssid),
                    alerta,
                    gt,
                    round(tiempo_ventana_ms, 1)
                ])

                modo_str = "🔴ATK" if gt else "🟢NOR"

                if alerta:
                    extra = ""
                    if bssid_falsos > 0:
                        extra = f" | BSSIDs falsos: {bssid_falsos}"
                    if bssids_ssid > 1:
                        extra += f" | APs con SSID: {bssids_ssid}"
                    print(f"[{modo_str}] 🚨 Evil Twin detectado por ML{extra} | #{ventana_num} | {tiempo_ventana_ms:.0f}ms")

                    # === PUBLICAR ALERTA MQTT ===
                    if mqtt_ok:
                        alerta_payload = json.dumps({
                            "tipo": "eviltwin",
                            "nivel": "critico",
                            "bssid_falsos": int(bssid_falsos),
                            "aps_con_ssid": int(bssids_ssid),
                            "ventana": ventana_num,
                            "tiempo_deteccion_ms": round(tiempo_ventana_ms, 1),
                            "timestamp": datetime.now().strftime("%H:%M:%S")
                        })
                        mqtt_alertas.publish(MQTT_TOPIC_ALERTA, alerta_payload)
                else:
                    print(f"[{modo_str}] 🟢 Tráfico normal | #{ventana_num} | {tiempo_ventana_ms:.0f}ms")

                    if mqtt_ok:
                        mqtt_alertas.publish(MQTT_TOPIC_ALERTA, json.dumps({
                            "tipo": "normal",
                            "nivel": "ok",
                            "ventana": ventana_num,
                            "timestamp": datetime.now().strftime("%H:%M:%S")
                        }))

                ventana_features = []
                ventana_bssid_ssid = []

except KeyboardInterrupt:
    print("\n\n Fin de la captura.")
    proceso.terminate()

    if mqtt_ok:
        mqtt_alertas.loop_stop()
        mqtt_alertas.disconnect()

    guardar_log()
    print("\n" + "="*55)
    print("       MÉTRICAS DEL IDS EVIL TWIN (ML VENTANA)")
    print("="*55)
    calcular_metricas()