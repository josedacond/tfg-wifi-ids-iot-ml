
# =============================================================================
#                          PRUEBA IA CON TRAFICO REAL
# =============================================================================

import subprocess
import pandas as pd
import joblib
import warnings

# Evitar avisos molestos de pandas en la consola
warnings.filterwarnings("ignore")

# --- CARGAMOS LA IA ---
print("\n\nCargando IA entrenada...")
modelo = joblib.load('modelo_deauth.pkl')

# --- CONEXIÓN CON LA RASPI ---
RASPI_IP = "192.168.1.49"
RASPI_USER = "joseda_cond"
INTERFAZ = "wlan2"

comando_ssh = [
    "ssh", f"{RASPI_USER}@{RASPI_IP}",
    f"echo 'vayatela' | sudo -S tshark -l -i {INTERFAZ} -T fields "
    f"-e wlan.fc.type -e wlan.fc.subtype -e wlan_radio.signal_dbm "
    f"-e frame.len -e wlan.fc.retry -e wlan.duration"
]

print(f"Conectándose a {RASPI_IP} por ssh...")
print("Esperando paquetes de tráfico...\n")

# usamos el ssh y lo que imprime la raspi se lo manda a python
proceso = subprocess.Popen(comando_ssh, stdout=subprocess.PIPE, 
                           stderr=subprocess.DEVNULL, text=True)
ventana_temporal = []

try:        # bucle, cada paquete que manda la raspi pasa por aquí
    for linea in proceso.stdout: 
        datos = linea.strip().split('\t') #limpia saltos de línea y corta cada tab
        
        if len(datos) == 6: # si el paquete tiene los parámetros que necesitamos
            ventana_temporal.append(datos)
            
            # hacemos ventanas de 50 paquetes
            if len(ventana_temporal) >= 50:
                columnas_modelo = ['wlan.fc.type', 'wlan.fc.subtype', 
                                   'wlan_radio.signal_dbm', 'frame.len', 
                                   'wlan.fc.retry', 'wlan.duration']
                df = pd.DataFrame(ventana_temporal, columns=columnas_modelo)
                
                # convertimos el texto en números para la IA:
                df['wlan.fc.type'] = pd.to_numeric(df['wlan.fc.type'], errors='coerce')
                df['wlan.fc.subtype'] = pd.to_numeric(df['wlan.fc.subtype'], errors='coerce')
                df['wlan_radio.signal_dbm'] = pd.to_numeric(df['wlan_radio.signal_dbm'], errors='coerce')
                df['frame.len'] = pd.to_numeric(df['frame.len'], errors='coerce')
                df['wlan.duration'] = pd.to_numeric(df['wlan.duration'], errors='coerce')
                
                # convertimos el parámetro booleano de 1 y 0:
                df['wlan.fc.retry'] = df['wlan.fc.retry'].apply(lambda x: 1 if str(x).lower() == 'true' else 0)

                # si llega algún paquete corrupto llenamos los vacíos con 0
                df = df.fillna(0)

                # la IA analiza los 50 paquetes a la vez
                predicciones = modelo.predict(df)
                # comprobamos si hay paquetes maliciosos (usando -1 como etiqueta de ataque)
                paquetes_maliciosos = (predicciones == -1).sum()
                
                if paquetes_maliciosos > 3: # ponemos el umbral de error
                    print(f"🚨 Ataque Deauth detectado: ({paquetes_maliciosos}/50 paquetes maliciosos)")
                else:
                    print("🟢 Tráfico normal 🟢")
                
                # reseteamos ventana
                ventana_temporal = [] 

except KeyboardInterrupt:
    print("\n Fin de la captura.")
    proceso.terminate()
    
    
    