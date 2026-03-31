# =============================================================================
#   ENTRENAMIENTO EVIL TWIN — Features de Ventana + Hyperparameter Optimization
# =============================================================================

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, f1_score
import joblib
import json
import time
import warnings

warnings.filterwarnings("ignore")

# =============================================================================
#                              CONFIGURACIÓN
# =============================================================================

CSV_PATH = "/Users/joseda_cond/Desktop/- TFG -/logs/captura_eviltwin_20260329_184424.csv"
MODELO_OUTPUT = "/Users/joseda_cond/Desktop/- TFG -/TrainedModels/modelo_eviltwin_hibrido.pkl"
AP_LEGITIMO_BSSID = "24:ec:99:ca:88:26"
AP_LEGITIMO_SSID = "TFG_TestAP"
AP_LEGITIMO_SSID_HEX = AP_LEGITIMO_SSID.encode('utf-8').hex()
TAMANO_VENTANA = 150

# =============================================================================
#                          CARGAR DATOS
# =============================================================================

print("\n" + "="*55)
print("  ENTRENAMIENTO EVIL TWIN — Hyperparameter Optimization")
print("="*55)

print(f"\nCargando CSV: {CSV_PATH}")
df = pd.read_csv(CSV_PATH, dtype=str)
print(f"  Total paquetes: {len(df)}")
print(f"  Normal: {(df['Label'] == 'Normal').sum()}")
print(f"  Ataque: {(df['Label'] == 'Attack').sum()}")

# Convertir tipos numéricos
for col in ['wlan.fc.type', 'wlan.fc.subtype', 'wlan_radio.signal_dbm', 'frame.len', 'wlan.duration']:
    df[col] = pd.to_numeric(df[col], errors='coerce')

df['wlan.fc.retry'] = df['wlan.fc.retry'].apply(lambda x: 1 if str(x).lower() == 'true' else 0)
df = df.fillna(0)

# =============================================================================
#               FUNCIÓN: decodificar SSID hex a texto
# =============================================================================

def hex_to_ssid(hex_str):
    try:
        if pd.notna(hex_str) and len(str(hex_str).strip()) > 0:
            return bytes.fromhex(str(hex_str).strip()).decode('utf-8', errors='ignore')
    except (ValueError, UnicodeDecodeError):
        pass
    return ""

# =============================================================================
#              CREAR FEATURES DE VENTANA
# =============================================================================

print("\nCreando features de ventana...")

ventanas = []

for i in range(0, len(df) - TAMANO_VENTANA, TAMANO_VENTANA):
    bloque = df.iloc[i:i + TAMANO_VENTANA]

    signal_mean = bloque['wlan_radio.signal_dbm'].mean()
    signal_std = bloque['wlan_radio.signal_dbm'].std()
    frame_len_mean = bloque['frame.len'].mean()
    frame_len_std = bloque['frame.len'].std()
    retry_sum = bloque['wlan.fc.retry'].sum()
    duration_mean = bloque['wlan.duration'].mean()

    type0_count = (bloque['wlan.fc.type'] == 0).sum()
    type1_count = (bloque['wlan.fc.type'] == 1).sum()
    type2_count = (bloque['wlan.fc.type'] == 2).sum()

    beacon_count = ((bloque['wlan.fc.type'] == 0) & (bloque['wlan.fc.subtype'] == 8)).sum()
    probe_resp_count = ((bloque['wlan.fc.type'] == 0) & (bloque['wlan.fc.subtype'] == 5)).sum()
    probe_req_count = ((bloque['wlan.fc.type'] == 0) & (bloque['wlan.fc.subtype'] == 4)).sum()

    ssid_matches = bloque[bloque['wlan.ssid_hex'].apply(
        lambda x: hex_to_ssid(str(x)) == AP_LEGITIMO_SSID if pd.notna(x) else False
    )]
    bssids_con_nuestro_ssid = ssid_matches['wlan.bssid'].nunique()

    paquetes_bssid_falso = 0
    if len(ssid_matches) > 0:
        paquetes_bssid_falso = (ssid_matches['wlan.bssid'].str.lower() != AP_LEGITIMO_BSSID.lower()).sum()

    bssids_totales = bloque['wlan.bssid'].replace('', np.nan).dropna().nunique()

    signal_var_same_ssid = 0
    if len(ssid_matches) > 1:
        signal_var_same_ssid = ssid_matches['wlan_radio.signal_dbm'].std()
        if pd.isna(signal_var_same_ssid):
            signal_var_same_ssid = 0

    beacon_ratio = beacon_count / TAMANO_VENTANA

    es_ataque = (bloque['Label'] == 'Attack').sum() > TAMANO_VENTANA / 2

    ventanas.append({
        'signal_mean': signal_mean,
        'signal_std': signal_std,
        'frame_len_mean': frame_len_mean,
        'frame_len_std': frame_len_std,
        'retry_sum': retry_sum,
        'duration_mean': duration_mean,
        'type0_mgmt': type0_count,
        'type1_ctrl': type1_count,
        'type2_data': type2_count,
        'beacon_count': beacon_count,
        'probe_resp_count': probe_resp_count,
        'probe_req_count': probe_req_count,
        'beacon_ratio': beacon_ratio,
        'bssids_con_ssid': bssids_con_nuestro_ssid,
        'paquetes_bssid_falso': paquetes_bssid_falso,
        'bssids_totales': bssids_totales,
        'signal_var_same_ssid': signal_var_same_ssid,
        'es_ataque': 1 if es_ataque else 0
    })

df_ventanas = pd.DataFrame(ventanas).fillna(0)

print(f"  Ventanas creadas: {len(df_ventanas)}")
print(f"  Ventanas Normal:  {(df_ventanas['es_ataque'] == 0).sum()}")
print(f"  Ventanas Ataque:  {(df_ventanas['es_ataque'] == 1).sum()}")

# =============================================================================
#                      PREPARAR DATOS
# =============================================================================

features = [col for col in df_ventanas.columns if col != 'es_ataque']
X = df_ventanas[features]
y = df_ventanas['es_ataque']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.3, random_state=42, stratify=y
)

print(f"\n  Train: {len(X_train)} ventanas | Test: {len(X_test)} ventanas")

# =============================================================================
#       EVALUACIÓN DE HIPERPARÁMETROS (Comparación directa)
# =============================================================================

print("\n" + "-"*55)
print("  Evaluación de configuraciones de hiperparámetros")
print("-"*55)

configs = [
    {'n_estimators': 100, 'max_depth': 10,   'class_weight': None,       'min_samples_split': 2},
    {'n_estimators': 150, 'max_depth': None,  'class_weight': None,       'min_samples_split': 2},
    {'n_estimators': 150, 'max_depth': 20,    'class_weight': 'balanced', 'min_samples_split': 2},
    {'n_estimators': 200, 'max_depth': 15,    'class_weight': 'balanced', 'min_samples_split': 2},
    {'n_estimators': 200, 'max_depth': None,  'class_weight': 'balanced', 'min_samples_split': 5},
    {'n_estimators': 300, 'max_depth': 20,    'class_weight': None,       'min_samples_split': 5},
]

resultados = []

for i, cfg in enumerate(configs):
    print(f"\n  [{i+1}/{len(configs)}] Entrenando: {cfg}")
    t_start = time.time()
    
    m = RandomForestClassifier(**cfg, random_state=42, n_jobs=-1)
    m.fit(X_train, y_train)
    
    t_train = time.time() - t_start
    
    pred = m.predict(X_test)
    f1 = f1_score(y_test, pred)
    tpr = ((y_test == 1) & (pred == 1)).sum() / (y_test == 1).sum() * 100
    fpr = ((y_test == 0) & (pred == 1)).sum() / (y_test == 0).sum() * 100
    
    resultados.append({
        'config': cfg,
        'modelo': m,
        'f1': f1,
        'tpr': tpr,
        'fpr': fpr,
        'tiempo': t_train
    })
    
    print(f"  → F1: {f1:.4f} | TPR: {tpr:.1f}% | FPR: {fpr:.1f}% | Tiempo: {t_train:.1f}s")

# =============================================================================
#                SELECCIONAR MEJOR CONFIGURACIÓN
# =============================================================================

resultados.sort(key=lambda x: x['f1'], reverse=True)
mejor = resultados[0]

print("\n" + "="*55)
print("          TABLA COMPARATIVA DE CONFIGURACIONES")
print("="*55)
print(f"\n  {'#':<4} {'n_est':<8} {'depth':<8} {'weight':<12} {'split':<8} {'F1':<8} {'TPR':<8} {'FPR':<8} {'Tiempo':<8}")
print(f"  {'─'*72}")

for i, r in enumerate(resultados):
    cfg = r['config']
    marca = " ★" if i == 0 else ""
    print(f"  {i+1:<4} {cfg['n_estimators']:<8} {str(cfg['max_depth']):<8} {str(cfg['class_weight']):<12} {cfg['min_samples_split']:<8} {r['f1']:<8.4f} {r['tpr']:<8.1f} {r['fpr']:<8.1f} {r['tiempo']:<8.1f}{marca}")

print(f"\n  ★ Mejor configuración seleccionada:")
for param, valor in mejor['config'].items():
    print(f"     {param}: {valor}")
print(f"     F1-score: {mejor['f1']:.4f}")
print(f"     TPR: {mejor['tpr']:.1f}%")
print(f"     FPR: {mejor['fpr']:.1f}%")

modelo = mejor['modelo']

# =============================================================================
#                      RESULTADOS DETALLADOS
# =============================================================================

y_pred = modelo.predict(X_test)

print("\n" + "="*55)
print("        RESULTADOS DETALLADOS (MEJOR MODELO)")
print("="*55)
print(classification_report(y_test, y_pred, target_names=['Normal', 'Evil Twin']))

# Feature importance
print("\n  Top 10 features más importantes:")
importances = pd.Series(modelo.feature_importances_, index=features).sort_values(ascending=False)
for i, (feat, imp) in enumerate(importances.head(10).items()):
    print(f"  {i+1}. {feat}: {imp:.4f}")

# =============================================================================
#                      GUARDAR MODELO OPTIMIZADO
# =============================================================================

joblib.dump(modelo, MODELO_OUTPUT)
print(f"\n📁 Modelo guardado: {MODELO_OUTPUT}")

features_path = MODELO_OUTPUT.replace('.pkl', '_features.json')
with open(features_path, 'w') as f:
    json.dump(features, f)
print(f"📁 Features guardadas: {features_path}")

print("\n✅ Entrenamiento con optimización completado!")
print("="*55)