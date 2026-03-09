#%% BUSQUEDA ARCHIVOS BUENOS Y MALOS DE DEAUTH:
import pandas as pd
import os

# --- ⚙️ CONFIGURACIÓN DEAUTH ---
CARPETA = "/Users/joseda_cond/Desktop/- TFG -/AWID3_Dataset_CSV/CSV/1.Deauth"

print(f"🕵️‍♂️ Rastreando la carpeta: {CARPETA}")
print("Buscando paquetes venenosos de desautenticación... ⏳\n")
print("-" * 50)
print(f"{'ARCHIVO':<20} | {'NORMALES':<10} | {'ATAQUES':<10} | {'ESTADO'}")
print("-" * 50)

total_archivos_limpios = 0
archivos_infectados = []

# Buscamos del 0 al 35 (por si acaso tienes hasta el 32 o más)
for i in range(35):
    archivo = f"Deauth_{i}.csv"
    ruta_completa = os.path.join(CARPETA, archivo)
    
    if os.path.exists(ruta_completa):
        try:
            # Leemos SOLO la columna Label
            df = pd.read_csv(ruta_completa, usecols=['Label'])
            
            conteo = df['Label'].value_counts()
            normales = conteo.get('Normal', 0)
            ataques = df['Label'][df['Label'] != 'Normal'].count()
            
            if ataques > 0:
                estado = "🚨 INFECTADO"
                archivos_infectados.append(archivo)
                print(f"\033[91m{archivo:<20} | {normales:<10} | {ataques:<10} | {estado}\033[0m")
            else:
                estado = "✅ LIMPIO"
                total_archivos_limpios += 1
                print(f"{archivo:<20} | {normales:<10} | {ataques:<10} | {estado}")
                
        except Exception as e:
            print(f"⚠️ Error al leer {archivo}: {e}")

print("-" * 50)
print("\n📋 RESUMEN DE LA BÚSQUEDA (DEAUTH):")
print(f"Archivos 100% limpios encontrados: {total_archivos_limpios}")
if archivos_infectados:
    print(f"¡Cuidado! Se encontraron ataques en estos {len(archivos_infectados)} archivos:")
    print(", ".join(archivos_infectados))
 