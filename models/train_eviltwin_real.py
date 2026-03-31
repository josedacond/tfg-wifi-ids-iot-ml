
# =============================================================================
#   ENTRENAMIENTO EVIL TWIN — Features de Ventana + Hyperparameter Optimization
# =============================================================================

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.metrics import classification_report
import joblib
import json
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
print("  ENTRENAMIENTO EVIL TWIN — GridSearchCV Optimization")
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

# =============================================================================
#              HYPERPARAMETER OPTIMIZATION (GridSearchCV)
# =============================================================================

print("\n" + "-"*55)
print("  Optimización de hiperparámetros (GridSearchCV)")
print("  Esto puede tardar unos minutos...")
print("-"*55)

param_grid = {
    'n_estimators': [50, 100, 150, 200, 300],
    'max_depth': [5, 10, 15, 20, None],
    'min_samples_split': [2, 5, 10],
    'class_weight': ['balanced', None]
}

grid = GridSearchCV(
    RandomForestClassifier(random_state=42, n_jobs=-1),
    param_grid,
    cv=5,
    scoring='f1',
    verbose=1,
    n_jobs=-1
)

grid.fit(X_train, y_train)

print(f"\n  ✅ Mejores hiperparámetros encontrados:")
for param, valor in grid.best_params_.items():
    print(f"     {param}: {valor}")
print(f"  ✅ Mejor F1-score (CV): {grid.best_score_:.4f}")

modelo = grid.best_estimator_

# =============================================================================
#                      RESULTADOS EN TEST
# =============================================================================

y_pred = modelo.predict(X_test)

print("\n" + "="*55)
print("              RESULTADOS DEL TEST")
print("="*55)
print(classification_report(y_test, y_pred, target_names=['Normal', 'Evil Twin']))

# Feature importance
print("\n  Top 10 features más importantes:")
importances = pd.Series(modelo.feature_importances_, index=features).sort_values(ascending=False)
for i, (feat, imp) in enumerate(importances.head(10).items()):
    print(f"  {i+1}. {feat}: {imp:.4f}")

# =============================================================================
#           COMPARACIÓN: ANTES vs DESPUÉS de optimización
# =============================================================================

print("\n" + "-"*55)
print("  COMPARACIÓN: Parámetros por defecto vs Optimizados")
print("-"*55)

modelo_base = RandomForestClassifier(
    n_estimators=200,
    max_depth=15,
    class_weight='balanced',
    random_state=42,
    n_jobs=-1
)
modelo_base.fit(X_train, y_train)
y_pred_base = modelo_base.predict(X_test)

from sklearn.metrics import f1_score, precision_score, recall_score

f1_base = f1_score(y_test, y_pred_base)
f1_opt = f1_score(y_test, y_pred)
prec_base = precision_score(y_test, y_pred_base)
prec_opt = precision_score(y_test, y_pred)
rec_base = recall_score(y_test, y_pred_base)
rec_opt = recall_score(y_test, y_pred)

print(f"\n  {'Métrica':<25} {'Original':<15} {'Optimizado':<15}")
print(f"  {'─'*55}")
print(f"  {'F1-score':<25} {f1_base:<15.4f} {f1_opt:<15.4f}")
print(f"  {'Precision':<25} {prec_base:<15.4f} {prec_opt:<15.4f}")
print(f"  {'Recall (TPR)':<25} {rec_base:<15.4f} {rec_opt:<15.4f}")
print(f"  {'n_estimators':<25} {'200':<15} {str(grid.best_params_['n_estimators']):<15}")
print(f"  {'max_depth':<25} {'15':<15} {str(grid.best_params_['max_depth']):<15}")
print(f"  {'min_samples_split':<25} {'2':<15} {str(grid.best_params_['min_samples_split']):<15}")
print(f"  {'class_weight':<25} {'balanced':<15} {str(grid.best_params_['class_weight']):<15}")

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


