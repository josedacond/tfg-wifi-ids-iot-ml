#%% Entrenamiento y test con múltiples archivos:

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import os

# --- CONFIGURACIÓN ---
CARPETA = "/Users/joseda_cond/Desktop/- TFG -/AWID3_Dataset_CSV/CSV/1.Deauth"

FEATURES = [
    'wlan.fc.type', 
    'wlan.fc.subtype', 
    'wlan_radio.signal_dbm',
    'frame.len',         # Tamaño del paquete
    'wlan.fc.retry',     # Reintentos de conexión
    'wlan.duration'      # Tiempo que reserva el canal
]

# --- ENTRENAMIENTO SUPERVISADO (Random Forest) ---
archivos_train = []

print("\n-> Entrenamiento iniciado. Comparando ficheros...")
# Entrenamos del 0 al 15 para que vea tráfico limpio y ataques
for i in range(15, 25):     
    archivo_temp = os.path.join(CARPETA, f"Deauth_{i}.csv")
    if os.path.exists(archivo_temp):
        # Ahora SÍ cargamos el Label porque el Random Forest no es ciego
        df_temp = pd.read_csv(archivo_temp, usecols=FEATURES + ['Label'])
        archivos_train.append(df_temp)

df_train = pd.concat(archivos_train, ignore_index=True)
X_train = df_train[FEATURES].fillna(0)

# Traducimos para la IA: 1 si es Normal, -1 si es Ataque
y_train = df_train['Label'].apply(lambda x: 1 if x == 'Normal' else -1)

# Nuestro modelo estrella
modelo = RandomForestClassifier(
    n_estimators=150,
    random_state=42, 
    n_jobs=-1
)
modelo.fit(X_train, y_train)

# guardamos el modelo entrenado:
import joblib
joblib.dump(modelo, 'modelo_deauth.pkl')
print("Modelo guardado como modelo_deauth.pkl")

# --- TEST DE PRUEBA ---
rango_inicio = 22
rango_fin = 32

archivos_test = []
print(f"-> Iniciando test con archivos del {rango_inicio} al {rango_fin}...")

for i in range(rango_inicio, rango_fin + 1):
    archivo_temp = os.path.join(CARPETA, f"Deauth_{i}.csv")
    if os.path.exists(archivo_temp):
        df_temp = pd.read_csv(archivo_temp, usecols=FEATURES + ['Label'])
        archivos_test.append(df_temp)

if archivos_test:
    df_test = pd.concat(archivos_test, ignore_index=True)
    X_test = df_test[FEATURES].fillna(0)
    
    df_test['IA_Dice'] = modelo.predict(X_test)
    
# --- RESULTADOS ---
    print("-" * 50)
    print("             = RESULTADOS DEL TEST =")
    print("-" * 50)
    
    es_ataque = df_test['Label'] != 'Normal'
    es_normal = df_test['Label'] == 'Normal'
    
    total_ataques = es_ataque.sum()
    total_normales = es_normal.sum()
    
    ataques_detectados = (es_ataque & (df_test['IA_Dice'] == -1)).sum()
    ataques_no_detectados = (es_ataque & (df_test['IA_Dice'] == 1)).sum()
    
    normales_correctos = (es_normal & (df_test['IA_Dice'] == 1)).sum()
    falsas_alarmas = (es_normal & (df_test['IA_Dice'] == -1)).sum()
    
    pct_det = (ataques_detectados / total_ataques * 100) if total_ataques > 0 else 0
    pct_no_det = (ataques_no_detectados / total_ataques * 100) if total_ataques > 0 else 0
    pct_norm = (normales_correctos / total_normales * 100) if total_normales > 0 else 0
    pct_falsas = (falsas_alarmas / total_normales * 100) if total_normales > 0 else 0
    
    print(f"Ataques detectados        | {ataques_detectados}/{total_ataques} | {pct_det:.0f}%")
    print(f"Ataques no detectados     | {ataques_no_detectados}/{total_ataques} | {pct_no_det:.0f}%")
    print(f"Tráfico normal            | {normales_correctos}/{total_normales} | {pct_norm:.0f}%")
    print(f"Tráfico aislado por error | {falsas_alarmas}/{total_normales} | {pct_falsas:.0f}%")
    print("-" * 50)

else:
    print("No se ha podido encontrar el archivo.")

