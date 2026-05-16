# ================= IMPORTS =================
import machine
import network
import ntptime
import ssl
import time
import ubinascii
import ujson
import onewire, ds18x20
import dht
import ssd1306

from simple import MQTTClient
from FuzzyLogicGeneral2 import proyecto_minigranja_porcina
from dimmer_multicanal import set_brightness
from machine import Pin, I2C

# ================= WIFI =================
SSID = "QuamtumHS4_9818"
PASSWORD = "HotSpotHS4_0B2B"

# ================= AWS =================
MQTT_CLIENT_ID = ubinascii.hexlify(machine.unique_id()).decode()
MQTT_BROKER = "a3p59r2o0rf9tq-ats.iot.us-east-1.amazonaws.com"

MQTT_CLIENT_KEY = "161503fd8c9c5f862e56539f58727e93fefeea3764db5794be856bf39d541e0f-private.pem.key"
MQTT_CLIENT_CERT = "161503fd8c9c5f862e56539f58727e93fefeea3764db5794be856bf39d541e0f-certificate.pem.crt"
MQTT_CA = "AmazonRootCA1.pem"

TOPIC = b"minigranja/temperatura"

# ================= PINES =================
ds = ds18x20.DS18X20(onewire.OneWire(machine.Pin(15)))

dht1 = dht.DHT22(machine.Pin(13))
dht2 = dht.DHT22(machine.Pin(12))

ventilador = machine.Pin(19, machine.Pin.OUT)


i2c = I2C(0, scl=Pin(1), sda=Pin(0))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# ================= CONTROL DIFUSO =================
ctrl1 = proyecto_minigranja_porcina()
ctrl2 = proyecto_minigranja_porcina()
ctrl3 = proyecto_minigranja_porcina()

# ================= VARIABLES =================
last_send = 0

# ================= FUNCIONES =================

def read_pem(file):
    with open(file, "r") as f:
        text = f.read().strip()
        return ubinascii.a2b_base64("".join(text.split("\n")[1:-1]))

# 🔥 WIFI ROBUSTO (TU VERSIÓN)
def scan_networks():
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)

    print("📡 Escaneando redes...")
    networks = sta_if.scan()

    for net in networks:
        ssid = net[0].decode()
        signal = net[3]
        print(f"📶 {ssid} ({signal} dBm)")

    return sta_if


def connect_internet():
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)

    retry_count = 0

    while True:
        try:
            if not sta_if.isconnected():
                print(f"🔄 Intento WiFi #{retry_count + 1}")
                sta_if.connect(SSID, PASSWORD)

                for i in range(20):
                    if sta_if.isconnected():
                        print("✅ WiFi conectado")
                        oled_status("OK", "--", 0, 0, "WiFi OK")
                        print("IP:", sta_if.ifconfig()[0])
                        return True

                    print(f"   Conectando... {i+1}s")
                    time.sleep(1)

                print("❌ Falló conexión WiFi")
                retry_count += 1
                time.sleep(5)

            else:
                print("✅ WiFi ya conectado")
                return True

        except Exception as e:
            print("⚠️ Error WiFi:", e)
            retry_count += 1
            time.sleep(5)


# 🔥 MQTT
def connect_mqtt():
    try:
        client = MQTTClient(
            MQTT_CLIENT_ID,
            MQTT_BROKER,
            keepalive=60,
            ssl=True,
            ssl_params={
                "key": read_pem(MQTT_CLIENT_KEY),
                "cert": read_pem(MQTT_CLIENT_CERT),
                "server_hostname": MQTT_BROKER,
                "cert_reqs": ssl.CERT_REQUIRED,
                "cadata": read_pem(MQTT_CA),
            },
        )
        client.connect()
        print("✅ MQTT conectado")
        oled_status("OK", "OK", 0, 0, "AWS OK")
        return client
    except Exception as e:
        print("❌ Error MQTT:", e)
        oled_status("OK", "ERROR", 0, 0, "MQTT FAIL")
        return None


def sync_time():
    try:
        ntptime.settime()
        print("🕒 Hora sincronizada")
    except:
        print("⚠️ Error NTP")


# 🔥 SENSORES
def leer_cunas():
    ds.convert_temp()
    time.sleep(0.75)

    roms = ds.scan()
    temps = {}

    for i, rom in enumerate(roms):
        temps[f"cuna{i+1}"] = ds.read_temp(rom)

    return temps


def leer_ambiente():
    try:
        dht1.measure()
        dht2.measure()

        temp = (dht1.temperature() + dht2.temperature()) / 2
        hum = (dht1.humidity() + dht2.humidity()) / 2

        return temp, hum
    except:
        return 0, 0
    

def oled_status(wifi, mqtt, temp, hum, estado):

    oled.fill(0)

    oled.text("MiniGranja IoT", 0, 0)

    oled.text(f"WiFi: {wifi}", 0, 15)

    oled.text(f"AWS: {mqtt}", 0, 25)

    oled.text(f"T:{temp:.1f}C", 0, 40)

    oled.text(f"H:{hum:.1f}%", 64, 40)

    oled.text(estado, 0, 55)

    oled.show()

# ================= INICIO =================

print("🚀 Iniciando sistema...\n")

oled.fill(0)
oled.text("Iniciando...", 0, 0)
oled.show()

scan_networks()
connect_internet()
sync_time()

mqtt = connect_mqtt()

# ================= LOOP =================

while True:
    try:
        now = time.time()

        # 🔄 Verificar WiFi
        sta_if = network.WLAN(network.STA_IF)
        if not sta_if.isconnected():
            print("⚠️ WiFi perdido, reconectando...")
            connect_internet()
            mqtt = connect_mqtt()

        # 🔄 Verificar MQTT
        if mqtt is None:
            mqtt = connect_mqtt()

        # 📡 Enviar cada 60s
        if now - last_send > 60:

            cunas = leer_cunas()
            temp_amb, hum = leer_ambiente()

            # 🔥 CONTROL POR CUNA
            res1 = ctrl1.compute({
                "edad": 2,
                "tempcuna": cunas.get("cuna1", 0),
                "tempamb": temp_amb
            })

            res2 = ctrl2.compute({
                "edad": 2,
                "tempcuna": cunas.get("cuna2", 0),
                "tempamb": temp_amb
            })

            res3 = ctrl3.compute({
                "edad": 2,
                "tempcuna": cunas.get("cuna3", 0),
                "tempamb": temp_amb
            })

            # 🔥 DIMMER
            set_brightness(1, res1["foco"])
            set_brightness(2, res2["foco"])
            set_brightness(3, res3["foco"])

            # 🔥 VENTILADOR
            vent = (res1["vent"] + res2["vent"] + res3["vent"]) / 3
            ventilador.value(1 if vent > 50 else 0)

            data = {
                "device_id": MQTT_CLIENT_ID,
                "timestamp": int(now),
                "cunas": cunas,
                "ambiente": {"temp": temp_amb, "hum": hum},
                "control": {
                    "cuna1": res1,
                    "cuna2": res2,
                    "cuna3": res3,
                    "ventilador": vent
                }
            }

            try:
                mqtt.publish(TOPIC, ujson.dumps(data))
                print("📤 Enviado:", data)
                oled_status(
                    "OK",
                    "OK",
                    temp_amb,
                    hum,
                    "Datos enviados"
                )
            except:
                print("⚠️ Error publicando")
                oled_status(
                    "OK",
                    "ERROR",
                    temp_amb,
                    hum,
                    "Pub Error"
                )
                mqtt = connect_mqtt()

            last_send = now

        time.sleep(0.1)

    except Exception as e:
        print("❌ Error general:", e)
        oled.fill(0)
        oled.text("ERROR GENERAL", 0, 0)
        oled.text(str(e)[:16], 0, 20)
        oled.show()
        time.sleep(5)