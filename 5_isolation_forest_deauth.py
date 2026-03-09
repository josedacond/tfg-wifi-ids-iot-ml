# %%
# Intentos de detección de Deauth usando Isolation Forest:

import pandas as pd
from sklearn.ensemble import IsolationForest
import os

# --- CONFIGURACIÓN ---
CARPETA = "/Users/joseda_cond/Desktop/- TFG -/AWID3_Dataset_CSV/CSV/1.Deauth"

FEATURES = [
    'wlan.fc.type', 
    'wlan.fc.subtype', 
    'wlan_radio.signal_dbm',
    'frame.len',
    'wlan.fc.retry',
    'Label' 
]

# --- MAGIA DE LAS VENTANAS TEMPORALES ---
def procesar_ventanas(df, tamano_ventana=50):
    ventanas = []
    # Cortamos el dataset en bloques para no diluir el ataque
    for i in range(0, len(df), tamano_ventana):
        bloque = df.iloc[i:i+tamano_ventana]
        if len(bloque) < tamano_ventana:
            continue 

        # Rasgos clave de la ventana
        deauth_count = len(bloque[(bloque['wlan.fc.type'] == 0) & (bloque['wlan.fc.subtype'] == 12)])
        potencia_media = bloque['wlan_radio.signal_dbm'].mean()
        potencia_var = bloque['wlan_radio.signal_dbm'].std() # <-- NUEVO: Variación de la señal
        reintentos_total = bloque['wlan.fc.retry'].sum()
        tamano_medio = bloque['frame.len'].mean()
        
        es_ataque = 1 if (bloque['Label'] != 'Normal').any() else 0

        ventanas.append({
            'deauth_count': deauth_count,
            'potencia_media': potencia_media,
            'potencia_var': potencia_var, 
            'reintentos_total': reintentos_total,
            'tamano_medio': tamano_medio,
            'Es_Ataque': es_ataque
        })
    return pd.DataFrame(ventanas).fillna(0)

# --- ENTRENAMIENTO (Isolation Forest) ---
print("\n🧠 Entrenando con todo el lote para que aísle lo raro nomás...")
archivos_train = []

# Le metemos TODOS los archivos (del 0 al 32)
for i in range(0, 33):     
    archivo_temp = os.path.join(CARPETA, f"Deauth_{i}.csv")
    if os.path.exists(archivo_temp):
        df_temp = pd.read_csv(archivo_temp, usecols=FEATURES).fillna(0)
        archivos_train.append(df_temp)

df_train_raw = pd.concat(archivos_train, ignore_index=True)
df_train_ventanas = procesar_ventanas(df_train_raw, tamano_ventana=50)

X_train = df_train_ventanas.drop('Es_Ataque', axis=1)

# Le decimos: "Aproximadamente el 5% de este bulto es un ataque, aísla a los raritos"
modelo = IsolationForest(n_estimators=100, contamination=0.05, random_state=42, n_jobs=-1)
modelo.fit(X_train)

# --- TEST DE PRUEBA ---
rango_inicio = 21
rango_fin = 32

print(f"🥊 Iniciando test con archivos del {rango_inicio} al {rango_fin}...")
archivos_test = []

for i in range(rango_inicio, rango_fin + 1):
    archivo_temp = os.path.join(CARPETA, f"Deauth_{i}.csv")
    if os.path.exists(archivo_temp):
        df_temp = pd.read_csv(archivo_temp, usecols=FEATURES).fillna(0)
        archivos_test.append(df_temp)

if archivos_test:
    df_test_raw = pd.concat(archivos_test, ignore_index=True)
    df_test_ventanas = procesar_ventanas(df_test_raw, tamano_ventana=50)
    
    X_test = df_test_ventanas.drop('Es_Ataque', axis=1)
    df_test_ventanas['IA_Dice'] = modelo.predict(X_test)
    
    # --- RESULTADOS ---
    print("\n" + "-"*50)
    print("             = RESULTADOS POR VENTANA =")
    print("-" * 50)
    
    es_ataque = df_test_ventanas['Es_Ataque'] == 1
    es_normal = df_test_ventanas['Es_Ataque'] == 0
    
    total_ataques = es_ataque.sum()
    total_normales = es_normal.sum()
    
    ataques_detectados = (es_ataque & (df_test_ventanas['IA_Dice'] == -1)).sum()
    falsas_alarmas = (es_normal & (df_test_ventanas['IA_Dice'] == -1)).sum()
    
    pct_det = (ataques_detectados / total_ataques * 100) if total_ataques > 0 else 0
    pct_falsas = (falsas_alarmas / total_normales * 100) if total_normales > 0 else 0
    
    print(f"Ventanas de ataque detectadas | {ataques_detectados}/{total_ataques} | {pct_det:.0f}%")
    print(f"Ventanas aisladas por error   | {falsas_alarmas}/{total_normales} | {pct_falsas:.0f}%")
    print("-" * 50)
else:
    print("No se ha podido encontrar el archivo.")

