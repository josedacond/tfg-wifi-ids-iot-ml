
import pandas as pd
import os
from sklearn.ensemble import RandomForestClassifier

# --- 1. CONFIGURACIÓN ---
CARPETA = "/Users/joseda_cond/Desktop/- TFG -/AWID3_Dataset_CSV/CSV/1.Deauth"

FEATURES = [
    'wlan.fc.type', 
    'wlan.fc.subtype', 
    'wlan_radio.signal_dbm',
    'frame.len',
    'wlan.fc.retry',
    'Label' 
]

# --- 2. FUNCIÓN DE VENTANAS TEMPORALES ---
def procesar_ventanas(df, tamano_ventana=50):
    ventanas = []
    for i in range(0, len(df), tamano_ventana):
        bloque = df.iloc[i:i+tamano_ventana]
        if len(bloque) < tamano_ventana:
            continue 

        deauth_count = len(bloque[(bloque['wlan.fc.type'] == 0) & (bloque['wlan.fc.subtype'] == 12)])
        potencia_media = bloque['wlan_radio.signal_dbm'].mean()
        potencia_var = bloque['wlan_radio.signal_dbm'].std()
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

# --- 3. ENTRENAMIENTO (Random Forest) ---
print("\n🧠 Entrenando Random Forest con ventanas (archivos 0 al 26)...")
archivos_train = []

for i in range(0, 27):     
    archivo_temp = os.path.join(CARPETA, f"Deauth_{i}.csv")
    if os.path.exists(archivo_temp):
        df_temp = pd.read_csv(archivo_temp, usecols=FEATURES).fillna(0)
        archivos_train.append(df_temp)

df_train_raw = pd.concat(archivos_train, ignore_index=True)
df_train_ventanas = procesar_ventanas(df_train_raw, tamano_ventana=50)

X_train = df_train_ventanas.drop('Es_Ataque', axis=1)
y_train = df_train_ventanas['Es_Ataque'].apply(lambda x: -1 if x == 1 else 1) 

modelo = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
modelo.fit(X_train, y_train)

# --- 4. TEST DE PRUEBA ---
rango_inicio = 27
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
    
    # --- 5. RESULTADOS FINALES ---
    print("\n" + "-"*50)
    print("             = RESULTADOS POR VENTANA (RF) =")
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
    print("No se han encontrado los archivos de test.")



