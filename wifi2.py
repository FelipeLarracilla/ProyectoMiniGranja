import network
import time

SSID = "HONOR90"
PASSWORD = "123456789#"

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

print("Escaneando redes...")
redes = wlan.scan()

for red in redes:
    print(red[0].decode())

print("\nIntentando conectar...")

wlan.connect(SSID, PASSWORD)

intentos = 0

while not wlan.isconnected():
    print("Intento:", intentos, "| Status:", wlan.status())
    time.sleep(1)
    intentos += 1
    
    if intentos > 15:
        print("❌ No se pudo conectar")
        break

if wlan.isconnected():
    print("✅ Conectado!")
    print("IP:", wlan.ifconfig())