
# =============================================================================
#   ENTRENAMIENTO DEAUTH — Random Forest + Hyperparameter Optimization
# =============================================================================

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.metrics import classification_report
import joblib
import os
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
print("  ENTRENAMIENTO DEAUTH — GridSearchCV Optimization")
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
    cv=5,               # 5-fold cross validation
    scoring='f1',        # optimiza por F1-score
    verbose=1,
    n_jobs=-1
)

grid.fit(X_train, y_train)

print(f"\n  ✅ Mejores hiperparámetros encontrados:")
for param, valor in grid.best_params_.items():
    print(f"     {param}: {valor}")
print(f"  ✅ Mejor F1-score (CV): {grid.best_score_:.4f}")

# El mejor modelo ya está entrenado
modelo = grid.best_estimator_

# =============================================================================
#                      RESULTADOS EN TEST
# =============================================================================

y_pred = modelo.predict(X_test)

print("\n" + "="*55)
print("              RESULTADOS DEL TEST")
print("="*55)
print(classification_report(y_test, y_pred, target_names=['Normal (1)', 'Ataque (-1)']))

# Métricas específicas
es_ataque = y_test == -1
es_normal = y_test == 1

total_ataques = es_ataque.sum()
total_normales = es_normal.sum()

ataques_detectados = (es_ataque & (y_pred == -1)).sum()
ataques_no_detectados = (es_ataque & (y_pred == 1)).sum()
normales_correctos = (es_normal & (y_pred == 1)).sum()
falsas_alarmas = (es_normal & (y_pred == -1)).sum()

pct_det = (ataques_detectados / total_ataques * 100) if total_ataques > 0 else 0
pct_falsas = (falsas_alarmas / total_normales * 100) if total_normales > 0 else 0

print(f"  TPR (Ataques detectados):     {ataques_detectados}/{total_ataques} ({pct_det:.1f}%)")
print(f"  FPR (Falsas alarmas):         {falsas_alarmas}/{total_normales} ({pct_falsas:.1f}%)")

# Feature importance
print(f"\n  Top features más importantes:")
importances = pd.Series(modelo.feature_importances_, index=FEATURES).sort_values(ascending=False)
for i, (feat, imp) in enumerate(importances.items()):
    print(f"  {i+1}. {feat}: {imp:.4f}")

# =============================================================================
#           COMPARACIÓN: ANTES vs DESPUÉS de optimización
# =============================================================================

print("\n" + "-"*55)
print("  COMPARACIÓN: Parámetros por defecto vs Optimizados")
print("-"*55)

# Modelo sin optimizar (parámetros originales)
modelo_base = RandomForestClassifier(
    n_estimators=150,
    random_state=42,
    n_jobs=-1
)
modelo_base.fit(X_train, y_train)
y_pred_base = modelo_base.predict(X_test)

tpr_base = ((es_ataque) & (y_pred_base == -1)).sum() / total_ataques * 100
fpr_base = ((es_normal) & (y_pred_base == -1)).sum() / total_normales * 100

tpr_opt = pct_det
fpr_opt = pct_falsas

print(f"\n  {'Métrica':<25} {'Original':<15} {'Optimizado':<15}")
print(f"  {'─'*55}")
print(f"  {'TPR':<25} {tpr_base:<15.1f} {tpr_opt:<15.1f}")
print(f"  {'FPR':<25} {fpr_base:<15.1f} {fpr_opt:<15.1f}")
print(f"  {'n_estimators':<25} {'150':<15} {str(grid.best_params_['n_estimators']):<15}")
print(f"  {'max_depth':<25} {'None':<15} {str(grid.best_params_['max_depth']):<15}")
print(f"  {'min_samples_split':<25} {'2':<15} {str(grid.best_params_['min_samples_split']):<15}")
print(f"  {'class_weight':<25} {'None':<15} {str(grid.best_params_['class_weight']):<15}")

# =============================================================================
#                      GUARDAR MODELO OPTIMIZADO
# =============================================================================

joblib.dump(modelo, MODELO_OUTPUT)
print(f"\n📁 Modelo guardado: {MODELO_OUTPUT}")
print("\n✅ Entrenamiento con optimización completado!")
print("="*55)
    
    