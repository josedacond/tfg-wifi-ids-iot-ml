# %%
#
import subprocess

# --- CONEXIÓN CON LA RASPI ---
RASPI_IP = "192.168.1.49"
RASPI_USER = "joseda_cond"
INTERFAZ = "wlan2"

comando_ssh = [
    "ssh", f"{RASPI_USER}@{RASPI_IP}",
    f"echo 'vayatela' | sudo -S tshark -l -i {INTERFAZ} -T fields "
    f"-e wlan.fc.type -e wlan.fc.subtype -e wlan_radio.signal_dbm "
    f"-e frame.len -e wlan.fc.retry -e wlan.duration"
]

print(f"Conectándose a {RASPI_IP} por ssh...")
print("Esperando paquetes de la AR9271...\n")

proceso = subprocess.Popen(comando_ssh, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
ventana_temporal = []

try:
    for linea in proceso.stdout:
        datos = linea.strip().split('\t') # tshark separa con un tab
        
        # Si la línea tiene exactamente nuestras 6 columnas, la guardamos
        if len(datos) == 6:
            ventana_temporal.append(datos)
            
            # Para probar: Cada vez que juntemos 50 paquetes
            if len(ventana_temporal) >= 50:
                print(f"-> Ventana lista con 50 paquetes. Ejemplo del último: {datos}")
                
                ventana_temporal = [] # reseteamos ventana

except KeyboardInterrupt:
    print("\n Fin de la captura.")
    proceso.terminate()
    
    