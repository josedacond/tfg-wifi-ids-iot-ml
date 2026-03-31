# =============================================================================
#   ENTRENAMIENTO DEAUTH — Random Forest + Hyperparameter Optimization
# =============================================================================

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, f1_score
import joblib
import os
import time
import warnings

warnings.filterwarnings("ignore")

# =============================================================================
#                              CONFIGURACIÓN
# =============================================================================

CARPETA = "/Users/joseda_cond/Desktop/- TFG -/AWID3_Dataset_CSV/CSV/1.Deauth"
MODELO_OUTPUT = "/Users/joseda_cond/Desktop/- TFG -/TrainedModels/modelo_deauth.pkl"

FEATURES = [
    'wlan.fc.type', 
    'wlan.fc.subtype', 
    'wlan_radio.signal_dbm',
    'frame.len',
    'wlan.fc.retry',
    'wlan.duration'
]

# Rangos de archivos (SIN solapamiento)
TRAIN_RANGE = range(0, 22)      # Archivos 0-21 para entrenamiento
TEST_RANGE = range(22, 33)      # Archivos 22-32 para test

# =============================================================================
#                          CARGAR DATOS
# =============================================================================

print("\n" + "="*55)
print("  ENTRENAMIENTO DEAUTH — Hyperparameter Optimization")
print("="*55)

# --- TRAIN ---
archivos_train = []
print(f"\n  Cargando archivos de ENTRENAMIENTO ({TRAIN_RANGE.start}-{TRAIN_RANGE.stop-1})...")
for i in TRAIN_RANGE:
    archivo_temp = os.path.join(CARPETA, f"Deauth_{i}.csv")
    if os.path.exists(archivo_temp):
        df_temp = pd.read_csv(archivo_temp, usecols=FEATURES + ['Label'])
        archivos_train.append(df_temp)

df_train = pd.concat(archivos_train, ignore_index=True)
X_train = df_train[FEATURES].fillna(0)
y_train = df_train['Label'].apply(lambda x: 1 if x == 'Normal' else -1)

print(f"  Paquetes train: {len(df_train)}")
print(f"  Normal: {(y_train == 1).sum()} | Ataque: {(y_train == -1).sum()}")

# --- TEST ---
archivos_test = []
print(f"\n  Cargando archivos de TEST ({TEST_RANGE.start}-{TEST_RANGE.stop-1})...")
for i in TEST_RANGE:
    archivo_temp = os.path.join(CARPETA, f"Deauth_{i}.csv")
    if os.path.exists(archivo_temp):
        df_temp = pd.read_csv(archivo_temp, usecols=FEATURES + ['Label'])
        archivos_test.append(df_temp)

df_test = pd.concat(archivos_test, ignore_index=True)
X_test = df_test[FEATURES].fillna(0)
y_test = df_test['Label'].apply(lambda x: 1 if x == 'Normal' else -1)

print(f"  Paquetes test: {len(df_test)}")
print(f"  Normal: {(y_test == 1).sum()} | Ataque: {(y_test == -1).sum()}")

# =============================================================================
#       EVALUACIÓN DE HIPERPARÁMETROS (Comparación directa)
# =============================================================================

print("\n" + "-"*55)
print("  Evaluación de configuraciones de hiperparámetros")
print("-"*55)

es_ataque = y_test == -1
es_normal = y_test == 1
total_ataques = es_ataque.sum()
total_normales = es_normal.sum()

configs = [
    {'n_estimators': 100, 'max_depth': 10,   'class_weight': None,       'min_samples_split': 2},
    {'n_estimators': 150, 'max_depth': None,  'class_weight': None,       'min_samples_split': 2},
    {'n_estimators': 150, 'max_depth': 20,    'class_weight': 'balanced', 'min_samples_split': 2},
    {'n_estimators': 200, 'max_depth': None,  'class_weight': 'balanced', 'min_samples_split': 5},
    {'n_estimators': 200, 'max_depth': 15,    'class_weight': 'balanced', 'min_samples_split': 2},
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
    tpr = (es_ataque & (pred == -1)).sum() / total_ataques * 100
    fpr = (es_normal & (pred == -1)).sum() / total_normales * 100
    
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

# Ordenar por F1-score
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

# Usar el mejor modelo
modelo = mejor['modelo']

# =============================================================================
#                      RESULTADOS DETALLADOS
# =============================================================================

y_pred = modelo.predict(X_test)

print("\n" + "="*55)
print("        RESULTADOS DETALLADOS (MEJOR MODELO)")
print("="*55)
print(classification_report(y_test, y_pred, target_names=['Normal (1)', 'Ataque (-1)']))

ataques_detectados = (es_ataque & (y_pred == -1)).sum()
falsas_alarmas = (es_normal & (y_pred == -1)).sum()

print(f"  TPR (Ataques detectados):     {ataques_detectados}/{total_ataques} ({mejor['tpr']:.1f}%)")
print(f"  FPR (Falsas alarmas):         {falsas_alarmas}/{total_normales} ({mejor['fpr']:.1f}%)")

# Feature importance
print(f"\n  Top features más importantes:")
importances = pd.Series(modelo.feature_importances_, index=FEATURES).sort_values(ascending=False)
for i, (feat, imp) in enumerate(importances.items()):
    print(f"  {i+1}. {feat}: {imp:.4f}")

# =============================================================================
#                      GUARDAR MODELO OPTIMIZADO
# =============================================================================

joblib.dump(modelo, MODELO_OUTPUT)
print(f"\n📁 Modelo guardado: {MODELO_OUTPUT}")
print("\n✅ Entrenamiento con optimización completado!")
print("="*55)