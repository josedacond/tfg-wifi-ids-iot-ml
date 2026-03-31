# =============================================================================
#   CAPTURA DE TRÁFICO REAL PARA ENTRENAR MODELO EVIL TWIN
# =============================================================================
#
#  USO:
#    1. Ejecuta el script
#    2. Captura tráfico NORMAL unos minutos (Evil Twin apagado)
#    3. Pulsa ENTER → cambia a modo ATAQUE
#    4. Enciende el Evil Twin y captura unos minutos
#    5. Ctrl+C → guarda el CSV etiquetado
#
# =============================================================================

import subprocess
import warnings
import time
import threading
import csv
import os
from datetime import datetime

warnings.filterwarnings("ignore")

# =============================================================================
#                              CONFIGURACIÓN
# =============================================================================

RASPI_IP = "10.39.89.213"
RASPI_USER = "joseda_cond"
INTERFAZ = "wlan2"

# Donde guardar el dataset
timestamp_inicio = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_CSV = f"/Users/joseda_cond/Desktop/- TFG -/logs/captura_eviltwin_{timestamp_inicio}.csv"

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
#                        CONEXIÓN SSH
# =============================================================================

comando_ssh = [
    "ssh", f"{RASPI_USER}@{RASPI_IP}",
    f"echo 'vayatela' | sudo -S tshark -l -i {INTERFAZ} -T fields "
    f"-e wlan.fc.type -e wlan.fc.subtype -e wlan_radio.signal_dbm "
    f"-e frame.len -e wlan.fc.retry -e wlan.duration "
    f"-e wlan.bssid -e wlan.ssid"
]

print("\n" + "="*55)
print("  CAPTURA DE TRÁFICO PARA ENTRENAMIENTO EVIL TWIN")
print("="*55)
print(f"\n  Guardando en: {OUTPUT_CSV}")
print(f"\n  INSTRUCCIONES:")
print(f"  1. Deja capturar tráfico NORMAL 3-5 minutos")
print(f"  2. Pulsa ENTER para cambiar a ATAQUE")
print(f"  3. Enciende el Evil Twin, captura 3-5 minutos")
print(f"  4. Ctrl+C para guardar y terminar")
print("="*55)
print(f"\n  Modo actual: 🟢 NORMAL\n")

proceso = subprocess.Popen(
    comando_ssh,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True
)

# =============================================================================
#                      CAPTURA
# =============================================================================

hilo_teclado = threading.Thread(target=escuchar_teclado, daemon=True)
hilo_teclado.start()

paquetes = []
count = 0

try:
    for linea in proceso.stdout:
        datos = linea.strip().split('\t')

        if len(datos) >= 6:
            # Extraer campos
            fc_type = datos[0]
            fc_subtype = datos[1]
            signal = datos[2]
            frame_len = datos[3]
            retry = datos[4]
            duration = datos[5]
            bssid = datos[6].strip() if len(datos) > 6 else ''
            ssid_hex = datos[7].strip() if len(datos) > 7 else ''

            with lock_modo:
                label = "Attack" if modo_ataque else "Normal"

            paquetes.append([
                fc_type, fc_subtype, signal, frame_len,
                retry, duration, bssid, ssid_hex, label
            ])

            count += 1
            if count % 200 == 0:
                modo_str = "🔴ATK" if label == "Attack" else "🟢NOR"
                print(f"[{modo_str}] {count} paquetes capturados...")

except KeyboardInterrupt:
    print(f"\n\n Captura finalizada. Total: {count} paquetes.")
    proceso.terminate()

    # Guardar CSV
    with open(OUTPUT_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'wlan.fc.type', 'wlan.fc.subtype', 'wlan_radio.signal_dbm',
            'frame.len', 'wlan.fc.retry', 'wlan.duration',
            'wlan.bssid', 'wlan.ssid_hex', 'Label'
        ])
        writer.writerows(paquetes)

    # Contar
    normales = sum(1 for p in paquetes if p[8] == "Normal")
    ataques = sum(1 for p in paquetes if p[8] == "Attack")

    print(f"\n📁 CSV guardado: {OUTPUT_CSV}")
    print(f"   Normal:  {normales} paquetes")
    print(f"   Ataque:  {ataques} paquetes")
    print(f"   Total:   {count} paquetes")