import machine
import network
import ntptime
import ssl
import time
import ubinascii
import ujson
import onewire, ds18x20
import dht

from simple import MQTTClient
from FuzzyLogicGeneral2 import proyecto_minigranja_porcina
from dimmer_multicanal import set_brightness

# ================= WIFI =================
SSID = "HONOR"
PASSWORD = "123456789#"

# ================= AWS =================
MQTT_CLIENT_ID = ubinascii.hexlify(machine.unique_id()).decode()
MQTT_BROKER = "a3p59r2o0rf9tq-ats.iot.us-east-1.amazonaws.com"

MQTT_CLIENT_KEY = "xxxx-private.pem.key"
MQTT_CLIENT_CERT = "xxxx-certificate.pem.crt"
MQTT_CA = "AmazonRootCA1.pem"

TOPIC = b"minigranja/temperatura"

# ================= PINES =================
ds = ds18x20.DS18X20(onewire.OneWire(machine.Pin(15)))
dht1 = dht.DHT22(machine.Pin(13))
dht2 = dht.DHT22(machine.Pin(12))

ventilador = machine.Pin(19, machine.Pin.OUT)

# ================= CONTROL DIFUSO =================
ctrl1 = proyecto_minigranja_porcina()
ctrl2 = proyecto_minigranja_porcina()
ctrl3 = proyecto_minigranja_porcina()

# ================= VARIABLES CONTROL =================
last_send = 0
last_ping = 0
last_ntp_sync = 0

# ================= FUNCIONES =================

def read_pem(file):
    with open(file, "r") as f:
        text = f.read().strip()
        return ubinascii.a2b_base64("".join(text.split("\n")[1:-1]))

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        wlan.connect(SSID, PASSWORD)
        print("🔄 Conectando WiFi...")

        for _ in range(20):
            if wlan.isconnected():
                print("✅ WiFi conectado:", wlan.ifconfig())
                return True
            time.sleep(1)

        print("❌ No se pudo conectar WiFi")
        return False
    return True

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
        return client
    except Exception as e:
        print("❌ Error MQTT:", e)
        return None

def sync_time():
    try:
        ntptime.settime()
        print("🕒 Hora sincronizada")
    except:
        print("⚠️ Error NTP")

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

# ================= INICIO =================

connect_wifi()
sync_time()

mqtt = connect_mqtt()

# ================= LOOP PRINCIPAL =================

while True:
    try:
        now = time.time()

        # 🔄 Verificar WiFi
        wlan = network.WLAN(network.STA_IF)
        if not wlan.isconnected():
            print("⚠️ WiFi perdido, reconectando...")
            if connect_wifi():
                mqtt = connect_mqtt()

        # 🔄 Verificar MQTT
        if mqtt is None:
            print("⚠️ MQTT desconectado, reconectando...")
            mqtt = connect_mqtt()

        # 🔄 Sincronizar NTP cada 6 horas
        if now - last_ntp_sync > 21600:
            sync_time()
            last_ntp_sync = now

        # 🔄 Ping MQTT cada 30 segundos
        if mqtt and (now - last_ping > 30):
            try:
                mqtt.ping()
                last_ping = now
            except:
                print("⚠️ MQTT ping falló")
                mqtt = connect_mqtt()

        # 📡 Enviar datos cada 60 segundos
        if now - last_send > 60:

            cunas = leer_cunas()
            temp_amb, hum = leer_ambiente()

            # 🔥 CONTROL POR CUNA
            res1 = ctrl1.compute({"edad": 2, "tempcuna": cunas.get("cuna1", 0), "tempamb": temp_amb})
            res2 = ctrl2.compute({"edad": 2, "tempcuna": cunas.get("cuna2", 0), "tempamb": temp_amb})
            res3 = ctrl3.compute({"edad": 2, "tempcuna": cunas.get("cuna3", 0), "tempamb": temp_amb})

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
            except:
                print("⚠️ Error al publicar")
                mqtt = connect_mqtt()

            last_send = now

        time.sleep(0.1)

    except Exception as e:
        print("❌ Error general:", e)
        time.sleep(5)