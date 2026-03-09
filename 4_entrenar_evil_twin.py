#%%
# BUSQUEDA DE ARCHIVOS LIMPIOS O INFECTADOS EN EVIL TWIN:
import pandas as pd
import os

# --- ⚙️ CONFIGURACIÓN ---
CARPETA = "/Users/joseda_cond/Desktop/- TFG -/AWID3_Dataset_CSV/CSV/12.Evil_Twin"

print(f"🕵️‍♂️ Rastreando la carpeta: {CARPETA}")
print("Buscando paquetes venenosos... ⏳\n")
print("-" * 50)
print(f"{'ARCHIVO':<20} | {'NORMALES':<10} | {'ATAQUES':<10} | {'ESTADO'}")
print("-" * 50)

# Contadores totales para tu reporte
total_archivos_limpios = 0
archivos_infectados = []

# Vamos a mirar del 0 al 75 (por si tienes hasta el 75)
for i in range(76):
    archivo = f"Evil_Twin_{i}.csv"
    ruta_completa = os.path.join(CARPETA, archivo)
    
    if os.path.exists(ruta_completa):
        try:
            # Leemos SOLO la columna Label para ir rapidísimo
            df = pd.read_csv(ruta_completa, usecols=['Label'])
            
            # Contamos qué hay dentro
            conteo = df['Label'].value_counts()
            
            normales = conteo.get('Normal', 0)
            
            # Sumamos todos los que NO sean 'Normal'
            ataques = df['Label'][df['Label'] != 'Normal'].count()
            
            if ataques > 0:
                estado = "🚨 INFECTADO"
                archivos_infectados.append(archivo)
                # Lo imprimimos en rojo para que destaque si tu consola lo pilla
                print(f"\033[91m{archivo:<20} | {normales:<10} | {ataques:<10} | {estado}\033[0m")
            else:
                estado = "✅ LIMPIO"
                total_archivos_limpios += 1
                print(f"{archivo:<20} | {normales:<10} | {ataques:<10} | {estado}")
                
        except Exception as e:
            print(f"⚠️ Error al leer {archivo}: {e}")
    else:
        # Si no existe el archivo 75, por ejemplo, no decimos nada y pasamos
        pass

print("-" * 50)
print("\n📋 RESUMEN DE LA BÚSQUEDA:")
print(f"Archivos 100% limpios encontrados: {total_archivos_limpios}")
if archivos_infectados:
    print(f"¡Cuidado! Se encontraron ataques en estos {len(archivos_infectados)} archivos:")
    print(", ".join(archivos_infectados))
else:
    print("Pues parece que aquí no hay ningún Evil Twin... ¿Seguro que es la carpeta correcta?")


