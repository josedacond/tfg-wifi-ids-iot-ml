# =============================================================================
#   ANÁLISIS DE MÉTRICAS IDS DEAUTH — Para la memoria del TFG
# =============================================================================

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

# =============================================================================
#                              CONFIGURACIÓN
# =============================================================================

CSV_PATH = "/Users/joseda_cond/Desktop/- TFG -/logs/log_ids_deauth_20260406_124611.csv"
OUTPUT_DIR = "/Users/joseda_cond/Desktop/- TFG -/tfg-wifi-ids-iot-ml/docs/analisis_deauth"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# =============================================================================
#                          CARGAR DATOS
# =============================================================================

print("\n" + "="*60)
print("  ANÁLISIS DE MÉTRICAS — IDS DEAUTH")
print("="*60)

df = pd.read_csv(CSV_PATH)
df['timestamp'] = pd.to_datetime(df['timestamp'])

print(f"\n  CSV: {CSV_PATH}")
print(f"  Total ventanas: {len(df)}")
print(f"  Normal (ground_truth=0): {(df['ground_truth'] == 0).sum()}")
print(f"  Ataque (ground_truth=1): {(df['ground_truth'] == 1).sum()}")
print(f"  Duración: {(df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds():.0f} segundos")

# =============================================================================
#                      MÉTRICAS PRINCIPALES
# =============================================================================

ataque = df[df['ground_truth'] == 1]
normal = df[df['ground_truth'] == 0]

tp = ((df['ground_truth'] == 1) & (df['alerta_ids'] == 1)).sum()
fn = ((df['ground_truth'] == 1) & (df['alerta_ids'] == 0)).sum()
fp = ((df['ground_truth'] == 0) & (df['alerta_ids'] == 1)).sum()
tn = ((df['ground_truth'] == 0) & (df['alerta_ids'] == 0)).sum()

tpr = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
fpr = fp / (fp + tn) * 100 if (fp + tn) > 0 else 0
precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
f1 = 2 * (precision * tpr) / (precision + tpr) if (precision + tpr) > 0 else 0
accuracy = (tp + tn) / len(df) * 100

tiempo_medio_ataque = ataque['tiempo_ventana_ms'].mean()
tiempo_medio_normal = normal['tiempo_ventana_ms'].mean()

print(f"\n{'─'*60}")
print(f"  MÉTRICAS DE RENDIMIENTO")
print(f"{'─'*60}")
print(f"  True Positives (TP):   {tp}")
print(f"  False Negatives (FN):  {fn}")
print(f"  False Positives (FP):  {fp}")
print(f"  True Negatives (TN):   {tn}")
print(f"{'─'*60}")
print(f"  TPR (Recall):          {tpr:.1f}%")
print(f"  FPR:                   {fpr:.1f}%")
print(f"  Precision:             {precision:.1f}%")
print(f"  F1-Score:              {f1:.1f}%")
print(f"  Accuracy:              {accuracy:.1f}%")
print(f"{'─'*60}")
print(f"  Tiempo medio (ataque): {tiempo_medio_ataque:.0f} ms")
print(f"  Tiempo medio (normal): {tiempo_medio_normal:.0f} ms")
print(f"  Tiempo medio (total):  {df['tiempo_ventana_ms'].mean():.0f} ms")
print(f"{'─'*60}")

# =============================================================================
#                  GRÁFICA 1: Timeline de detecciones
# =============================================================================

fig, ax = plt.subplots(figsize=(14, 5))

for i in range(len(df)):
    color = '#ffcccc' if df.iloc[i]['ground_truth'] == 1 else '#ccffcc'
    ax.axvspan(i - 0.5, i + 0.5, alpha=0.3, color=color, linewidth=0)

colors = []
for _, row in df.iterrows():
    if row['ground_truth'] == 1 and row['alerta_ids'] == 1:
        colors.append('#dc2626')  # TP
    elif row['ground_truth'] == 1 and row['alerta_ids'] == 0:
        colors.append('#f59e0b')  # FN
    elif row['ground_truth'] == 0 and row['alerta_ids'] == 1:
        colors.append('#f97316')  # FP
    else:
        colors.append('#16a34a')  # TN

ax.scatter(range(len(df)), df['alerta_ids'], c=colors, s=8, alpha=0.7, zorder=2)

tp_patch = mpatches.Patch(color='#dc2626', label=f'TP (ataque detectado): {tp}')
fn_patch = mpatches.Patch(color='#f59e0b', label=f'FN (ataque no detectado): {fn}')
fp_patch = mpatches.Patch(color='#f97316', label=f'FP (falsa alarma): {fp}')
tn_patch = mpatches.Patch(color='#16a34a', label=f'TN (normal correcto): {tn}')
ax.legend(handles=[tp_patch, fn_patch, fp_patch, tn_patch], loc='upper right', fontsize=9)

ax.set_xlabel('Ventana #', fontsize=11)
ax.set_ylabel('Alerta IDS (0=Normal, 1=Ataque)', fontsize=11)
ax.set_title('Timeline de Detecciones — IDS Deauth (ML AWID3)', fontsize=13, fontweight='bold')
ax.set_yticks([0, 1])
ax.set_yticklabels(['Normal', 'Ataque'])
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'timeline_detecciones_deauth.png'), dpi=200)
plt.show()
print(f"\n📁 Gráfica guardada: timeline_detecciones_deauth.png")

# =============================================================================
#              GRÁFICA 2: Matriz de confusión
# =============================================================================

fig, ax = plt.subplots(figsize=(6, 5))

confusion = np.array([[tn, fp], [fn, tp]])
cell_colors = [
    ['#c6f6d5', '#fed7aa'],
    ['#fef9c3', '#fecaca']
]
for i in range(2):
    for j in range(2):
        ax.add_patch(plt.Rectangle((j, i), 1, 1, fill=True, color=cell_colors[i][j]))

labels = [['TN\n(Tráfico normal)', 'FP\n(Falsa alarma)'],
          ['FN\n(Ataque no\ndetectado)', 'TP\n(Ataque detectado)']]

for i in range(2):
    for j in range(2):
        ax.text(j + 0.5, i + 0.5, f'{labels[i][j]}\n{confusion[i, j]}',
                ha='center', va='center', fontsize=12, fontweight='bold', color='black')

ax.set_xlim(0, 2)
ax.set_ylim(0, 2)
ax.invert_yaxis()
ax.set_xticks([0.5, 1.5])
ax.set_yticks([0.5, 1.5])
ax.set_xticklabels(['Predicción:\nNormal', 'Predicción:\nAtaque'], fontsize=10)
ax.set_yticklabels(['Real:\nNormal', 'Real:\nAtaque'], fontsize=10)
ax.set_title('Matriz de Confusión — IDS Deauth', fontsize=13, fontweight='bold')

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'confusion_matrix_deauth.png'), dpi=200)
plt.show()
print(f"📁 Gráfica guardada: confusion_matrix_deauth.png")

# =============================================================================
#              GRÁFICA 3: Distribución de tiempos de detección
# =============================================================================

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
bins = range(0, 850, 50)

if len(ataque) > 0:
    ax1.hist(ataque['tiempo_ventana_ms'], bins=bins, color='#dc2626', alpha=0.7, edgecolor='black')
    ax1.axvline(ataque['tiempo_ventana_ms'].mean(), color='black', linestyle='--', linewidth=2,
                label=f'Media: {ataque["tiempo_ventana_ms"].mean():.0f} ms')
    ax1.set_xlabel('Tiempo (ms)', fontsize=11)
    ax1.set_ylabel('Frecuencia', fontsize=11)
    ax1.set_title('Tiempo de Ventana — Modo Ataque', fontsize=12, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(alpha=0.3)
    ax1.set_xlim(0, 800)

if len(normal) > 0:
    ax2.hist(normal['tiempo_ventana_ms'], bins=bins, color='#16a34a', alpha=0.7, edgecolor='black')
    ax2.axvline(normal['tiempo_ventana_ms'].mean(), color='black', linestyle='--', linewidth=2,
                label=f'Media: {normal["tiempo_ventana_ms"].mean():.0f} ms')
    ax2.set_xlabel('Tiempo (ms)', fontsize=11)
    ax2.set_ylabel('Frecuencia', fontsize=11)
    ax2.set_title('Tiempo de Ventana — Modo Normal', fontsize=12, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(alpha=0.3)
    ax2.set_xlim(0, 800)

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'tiempos_deteccion_deauth.png'), dpi=200)
plt.show()
print(f"📁 Gráfica guardada: tiempos_deteccion_deauth.png")

# =============================================================================
#          GRÁFICA 4: Paquetes maliciosos por ventana
# =============================================================================

fig, ax = plt.subplots(figsize=(14, 4))

ataque_idx = df[df['ground_truth'] == 1].index
normal_idx = df[df['ground_truth'] == 0].index

ax.bar(normal_idx, df.loc[normal_idx, 'paquetes_maliciosos'], color='#16a34a', alpha=0.6, label='Normal', width=1)
ax.bar(ataque_idx, df.loc[ataque_idx, 'paquetes_maliciosos'], color='#dc2626', alpha=0.6, label='Ataque', width=1)

ax.axhline(y=20, color='#f59e0b', linestyle='--', linewidth=1.5, label='Umbral de alerta (20)')

ax.set_xlabel('Ventana #', fontsize=11)
ax.set_ylabel('Paquetes maliciosos detectados', fontsize=11)
ax.set_title('Paquetes Maliciosos por Ventana — IDS Deauth', fontsize=13, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'paquetes_maliciosos_deauth.png'), dpi=200)
plt.show()
print(f"📁 Gráfica guardada: paquetes_maliciosos_deauth.png")

# =============================================================================
#                      RESUMEN PARA LA MEMORIA
# =============================================================================

print("\n" + "="*60)
print("  RESUMEN PARA LA MEMORIA DEL TFG")
print("="*60)
print(f"""
  Modelo: Random Forest (AWID3, ventana de 150 paquetes)
  Dataset de entrenamiento: AWID3 — Deauthentication (archivos 15-24)
  Evaluación: {len(df)} ventanas en tiempo real
    - {(df['ground_truth'] == 0).sum()} ventanas de tráfico normal
    - {(df['ground_truth'] == 1).sum()} ventanas durante ataque Deauth

  Resultados:
    TPR (True Positive Rate):   {tpr:.1f}%  ({tp}/{tp+fn})
    FPR (False Positive Rate):  {fpr:.1f}%  ({fp}/{fp+tn})
    Precision:                  {precision:.1f}%
    F1-Score:                   {f1:.1f}%
    Accuracy:                   {accuracy:.1f}%

  Tiempos de detección:
    Media (ataque):  {tiempo_medio_ataque:.0f} ms
    Media (normal):  {tiempo_medio_normal:.0f} ms
    Media (total):   {df['tiempo_ventana_ms'].mean():.0f} ms

  Gráficas generadas en: {OUTPUT_DIR}
""")
print("="*60)