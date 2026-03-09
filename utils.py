#%% Enumeración de las columnas de diferentes parámetros:

import pandas as pd

ruta = "/Users/joseda_cond/Desktop/- TFG -/AWID3_Dataset_CSV/CSV/1.Deauth/Deauth_0.csv"

try:
    df = pd.read_csv(ruta, nrows=0)
    for i, columna in enumerate(df.columns, 1):
        print(f"{i}. {columna}")
    print(f"\nTotal de columnas encontradas: {len(df.columns)}")

except FileNotFoundError:
    print("No se ha encontrado el archivo.")
    
    
    
    