import network
import time

SSID = "HONOR90"
PASSWORD = "123456789#"

def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    print("Conectando a WiFi...")

    while not wlan.isconnected():
        print(".")
        time.sleep(1)

    print("✅ Conectado!")
    print("IP:", wlan.ifconfig())

conectar_wifi()