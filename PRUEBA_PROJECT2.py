# ============================================================
# main.py
# Proyecto: Minigranja Porcina
# Control difuso usando fuzzyLogicGeneral.py
# Compatible con Raspberry Pi Pico W (MicroPython)
# ============================================================

import time
from machine import Pin
import onewire
import ds18x20

# Importar el proyecto desde la librería
from FuzzyLogicGeneral2 import proyecto_minigranja_porcina

print("Inicializando control difuso de minigranja porcina...")

# Crear el controlador difuso
ctrl_foco = proyecto_minigranja_porcina()

#Crea la instancia para la lectura del DS18x20
ow = onewire.OneWire(Pin(12))
ds = ds18x20.DS18X20(ow)
roms = ds.scan()
print('Dispositivo Encontrado:', roms)

print("Controlador listo")
print("-" * 50)

# ------------------------------------------------------------
# BUCLE PRINCIPAL
# ------------------------------------------------------------
while True:

    # --------------------------------------------------------
    # ENTRADAS:
    # --------------------------------------------------------
    # Inicia el proceso de conversion de la temperatura
    ds.convert_temp()
    # Tiempo de espera para la conversion(750 ms DS18X20)
    time.sleep_ms(750)
    
    #Lee la temperatura
    for rom in roms:
        #print(ds.read_temp(rom))
        temp_cuna = ds.read_temp(rom)
        #print("Temp x:"+str(x))
    
    

    # Temperatura manualmente
    #temp_cuna = 33

    # Edad del lechón en días (0 a 27)
    edad_lechon = 2
    
    # Temperatua Ambiente (Manualmente)
    temp_amb = 15
    
    # --------------------------------------------------------
    # CONTROL DIFUSO
    # --------------------------------------------------------
    resultado = ctrl_foco.compute({
        "edad": edad_lechon,
        "tempcuna": temp_cuna,
        "tempamb": temp_amb
        
    })

    # Variable de salida
    potencia_foco = resultado["foco"]
    
    ventilador = resultado["vent"]

    # --------------------------------------------------------
    # SALIDA
    # --------------------------------------------------------
    print("Edad del lechón:", edad_lechon, "días")
    print("Temperatura cuna:", temp_cuna, "°C")
    print("Temperatura ambiente:", temp_amb, "°C")
    print("Potencia foco:", potencia_foco, "%")
    print("Ventilador:", ventilador, "%")
    print("-" * 50)

    # --------------------------------------------------------
    # Retardo
    # --------------------------------------------------------
    time.sleep(2)