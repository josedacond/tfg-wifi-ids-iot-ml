# =============================================================================
#        IDS DEAUTH — DETECCIÓN EN TIEMPO REAL CON MÉTRICAS + ALERTAS MQTT
# =============================================================================
#
#  USO:
#    1. Ejecuta el script normalmente
#    2. Pulsa ENTER para cambiar entre modo NORMAL y modo ATAQUE
#    3. Pulsa Ctrl+C para terminar y ver las métricas
#    4. Se genera un CSV con todo el log
#
#  ALERTAS MQTT:
#    Publica en tfg/alerta vía SSH → mosquitto_pub en la Raspi.
#    El dashboard y la Rustboard se suscriben para reaccionar.
#
# =============================================================================

import subprocess
import pandas as pd
import joblib
import warnings
import time
import threading
import csv
import os
import json
from datetime import datetime

warnings.filterwarnings("ignore")

# =============================================================================
#                              CONFIGURACIÓN
# =============================================================================

RASPI_IP = "10.44.92.213"
RASPI_USER = "joseda_cond"
INTERFAZ = "wlan2"
MODELO_PATH = "/Users/joseda_cond/Desktop/- TFG -/TrainedModels/modelo_deauth.pkl"
UMBRAL_ALERTA = 3          # paquetes maliciosos por ventana para alertar
TAMANO_VENTANA = 50         # paquetes por ventana

# MQTT
MQTT_TOPIC_ALERTA = "tfg/alerta"

# Nombre del CSV de log con timestamp para no sobreescribir
timestamp_inicio = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_CSV = f"/Users/joseda_cond/Desktop/- TFG -/logs/log_ids_deauth_{timestamp_inicio}.csv"

# =============================================================================
#                 PUBLICAR ALERTAS MQTT VÍA SSH
# =============================================================================

def publicar_alerta(payload_json):
    """Publica alerta MQTT vía SSH → mosquitto_pub en la Raspi."""
    try:
        # Escapar comillas simples en el payload
        payload_escaped = payload_json.replace("'", "'\\''")
        cmd = [
            "ssh", f"{RASPI_USER}@{RASPI_IP}",
            f"mosquitto_pub -h 127.0.0.1 -t {MQTT_TOPIC_ALERTA} -m '{payload_escaped}'"
        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        pass

mqtt_ok = True  # Siempre disponible vía SSH
print(f"[MQTT] Alertas vía SSH → mosquitto_pub en {RASPI_IP}")

# =============================================================================
#                     CONTROL DE MODO (NORMAL / ATAQUE)
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
                estado = "🔴 ATAQUE" if modo_ataque else "🟢 NORMAL"
                print(f"\n{'='*50}")
                print(f"  Modo cambiado a: {estado}")
                print(f"{'='*50}\n")
        except EOFError:
            break

# =============================================================================
#                          CARGAMOS LA IA
# =============================================================================

print("\n" + "="*50)
print("  IDS DEAUTH — Detección + Alertas MQTT")
print("="*50)
print(f"\nCargando modelo: {MODELO_PATH}")
modelo = joblib.load(MODELO_PATH)
print("Modelo cargado correctamente.\n")

# =============================================================================
#                        CONEXIÓN SSH CON LA RASPI
# =============================================================================

comando_ssh = [
    "ssh", f"{RASPI_USER}@{RASPI_IP}",
    f"echo 'vayatela' | sudo -S tshark -l -i {INTERFAZ} -T fields "
    f"-e wlan.fc.type -e wlan.fc.subtype -e wlan_radio.signal_dbm "
    f"-e frame.len -e wlan.fc.retry -e wlan.duration"
]

print(f"Conectándose a {RASPI_IP} por SSH...")
print("Esperando paquetes de tráfico...\n")
print("-"*50)
print("  INSTRUCCIONES:")
print("  → Pulsa ENTER para cambiar entre NORMAL / ATAQUE")
print("  → Pulsa Ctrl+C para terminar y ver métricas")
print("-"*50)
print(f"\n  Modo actual: 🟢 NORMAL\n")

proceso = subprocess.Popen(
    comando_ssh, 
    stdout=subprocess.PIPE, 
    stderr=subprocess.DEVNULL, 
    text=True
)

# =============================================================================
#                         LOGGING EN CSV
# =============================================================================

log_data = []

def guardar_log():
    if not log_data:
        print("No hay datos para guardar.")
        return
    
    with open(LOG_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'timestamp', 'ventana_num', 'paquetes_maliciosos',
            'alerta_ids', 'ground_truth', 'tiempo_ventana_ms'
        ])
        writer.writerows(log_data)
    
    print(f"\n📁 Log guardado en: {os.path.abspath(LOG_CSV)}")

# =============================================================================
#                      CÁLCULO DE MÉTRICAS
# =============================================================================

def calcular_metricas():
    if not log_data:
        print("No hay datos suficientes para métricas.")
        return
    
    df = pd.DataFrame(log_data, columns=[
        'timestamp', 'ventana_num', 'paquetes_maliciosos',
        'alerta_ids', 'ground_truth', 'tiempo_ventana_ms'
    ])
    
    ventanas_ataque = df[df['ground_truth'] == 1]
    ventanas_normal = df[df['ground_truth'] == 0]
    
    if len(ventanas_ataque) > 0:
        true_positives = ventanas_ataque['alerta_ids'].sum()
        tpr = true_positives / len(ventanas_ataque) * 100
    else:
        true_positives = 0
        tpr = None
    
    if len(ventanas_normal) > 0:
        false_positives = ventanas_normal['alerta_ids'].sum()
        fpr = false_positives / len(ventanas_normal) * 100
    else:
        false_positives = 0
        fpr = None
    
    if len(ventanas_ataque) > 0:
        tiempo_medio = ventanas_ataque['tiempo_ventana_ms'].mean()
    else:
        tiempo_medio = None
    
    print("\n" + "="*50)
    print("           MÉTRICAS DEL IDS DEAUTH")
    print("="*50)
    print(f"\n  Total ventanas analizadas:  {len(df)}")
    print(f"  Ventanas en modo ATAQUE:    {len(ventanas_ataque)}")
    print(f"  Ventanas en modo NORMAL:    {len(ventanas_normal)}")
    print(f"\n  {'─'*46}")
    
    if tpr is not None:
        print(f"  ✅ TPR (True Positive Rate):   {tpr:.1f}%  ({int(true_positives)}/{len(ventanas_ataque)})")
    else:
        print(f"  ⚠️  TPR: Sin datos (no hubo ventanas en modo ATAQUE)")
    
    if fpr is not None:
        print(f"  ❌ FPR (False Positive Rate):  {fpr:.1f}%  ({int(false_positives)}/{len(ventanas_normal)})")
    else:
        print(f"  ⚠️  FPR: Sin datos (no hubo ventanas en modo NORMAL)")
    
    if tiempo_medio is not None:
        print(f"  ⏱️  Tiempo medio detección:    {tiempo_medio:.0f} ms")
    
    print(f"  {'─'*46}")
    print(f"  Umbral de alerta:             >{UMBRAL_ALERTA}/{TAMANO_VENTANA} paquetes")
    print("="*50)

# =============================================================================
#                      BUCLE PRINCIPAL DE CAPTURA
# =============================================================================

hilo_teclado = threading.Thread(target=escuchar_teclado, daemon=True)
hilo_teclado.start()

ventana_temporal = []
ventana_num = 0
tiempo_inicio_ventana = time.time()

columnas_modelo = [
    'wlan.fc.type', 'wlan.fc.subtype', 'wlan_radio.signal_dbm',
    'frame.len', 'wlan.fc.retry', 'wlan.duration'
]

try:
    for linea in proceso.stdout:
        datos = linea.strip().split('\t')
        
        if len(datos) == 6:
            if len(ventana_temporal) == 0:
                tiempo_inicio_ventana = time.time()
            
            ventana_temporal.append(datos)
            
            if len(ventana_temporal) >= TAMANO_VENTANA:
                tiempo_ventana_ms = (time.time() - tiempo_inicio_ventana) * 1000
                
                ventana_num += 1
                
                df = pd.DataFrame(ventana_temporal, columns=columnas_modelo)
                
                for col in ['wlan.fc.type', 'wlan.fc.subtype', 
                           'wlan_radio.signal_dbm', 'frame.len', 'wlan.duration']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                
                df['wlan.fc.retry'] = df['wlan.fc.retry'].apply(
                    lambda x: 1 if str(x).lower() == 'true' else 0
                )
                df = df.fillna(0)
                
                predicciones = modelo.predict(df)
                paquetes_maliciosos = (predicciones == -1).sum()
                
                alerta = 1 if paquetes_maliciosos > UMBRAL_ALERTA else 0
                
                with lock_modo:
                    gt = 1 if modo_ataque else 0
                
                log_data.append([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    ventana_num,
                    int(paquetes_maliciosos),
                    alerta,
                    gt,
                    round(tiempo_ventana_ms, 1)
                ])
                
                modo_str = "🔴ATK" if gt else "🟢NOR"
                if alerta:
                    print(f"[{modo_str}] 🚨 Ataque Deauth detectado: ({paquetes_maliciosos}/{TAMANO_VENTANA} maliciosos) | ventana #{ventana_num} | {tiempo_ventana_ms:.0f}ms")
                    
                    alerta_payload = json.dumps({
                        "tipo": "deauth",
                        "nivel": "critico",
                        "paquetes_maliciosos": int(paquetes_maliciosos),
                        "total_paquetes": TAMANO_VENTANA,
                        "ventana": ventana_num,
                        "tiempo_deteccion_ms": round(tiempo_ventana_ms, 1),
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })
                    publicar_alerta(alerta_payload)
                else:
                    print(f"[{modo_str}] 🟢 Tráfico normal | ventana #{ventana_num} | {tiempo_ventana_ms:.0f}ms")
                    
                    publicar_alerta(json.dumps({
                        "tipo": "normal",
                        "nivel": "ok",
                        "ventana": ventana_num,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }))
                
                ventana_temporal = []

except KeyboardInterrupt:
    print("\n\n Fin de la captura.")
    proceso.terminate()
    
    guardar_log()
    calcular_metricas()