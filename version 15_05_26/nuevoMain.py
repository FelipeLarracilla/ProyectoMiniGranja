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
import sh1106

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


# ================= OLED =================
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)

oled = sh1106.SH1106_I2C(128, 64, i2c)
oled.sleep(False)
oled.fill(0)
oled.show()

# ================= CONTROL DIFUSO =================
ctrl1 = proyecto_minigranja_porcina()
ctrl2 = proyecto_minigranja_porcina()
ctrl3 = proyecto_minigranja_porcina()

# ================= VARIABLES =================
last_send = 0
last_control = 0

CONTROL_INTERVAL = 10
SEND_INTERVAL = 60
# ================= EDADES DINAMICAS
inicio_cuna1 = 0
inicio_cuna2 = 0
inicio_cuna3 = 0
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

''' def connect_internet():


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
            time.sleep(5) '''

def connect_internet():

    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)

    try:

        if not sta_if.isconnected():

            print("🔄 Conectando WiFi...")

            sta_if.connect(SSID, PASSWORD)

            for i in range(10):

                if sta_if.isconnected():

                    print("✅ WiFi conectado")

                    return True

                time.sleep(1)

        return sta_if.isconnected()

    except Exception as e:

        print("⚠️ Error WiFi:", e)

        return False

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

def mqtt_callback(topic, msg):

    global inicio_cuna1
    global inicio_cuna2
    global inicio_cuna3

    try:

        data = ujson.loads(msg)

        if "inicio_cuna1" in data:
            inicio_cuna1 = int(data["inicio_cuna1"])

        if "inicio_cuna2" in data:
            inicio_cuna2 = int(data["inicio_cuna2"])

        if "inicio_cuna3" in data:
            inicio_cuna3 = int(data["inicio_cuna3"])

        print("✅ Fechas actualizadas")

        guardar_config()

        oled_status(
            "OK",
            "OK",
            0,
            0,
            "Config OK"
        )

    except Exception as e:
        print("❌ Error callback:", e)

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

    oled.text("MiniGranja", 0, 0)

    oled.text(f"WiFi:{wifi}", 0, 15)

    oled.text(f"AWS:{mqtt}", 0, 28)

    oled.text(f"T:{temp:.1f}C", 0, 42)

    oled.text(f"H:{hum:.1f}%", 64, 42)

    oled.text(estado, 0, 56)

    oled.show()

def calcular_dias(timestamp_inicio):

    if timestamp_inicio == 0:
        return 0

    ahora = time.time()

    dias = int(
        (ahora - timestamp_inicio) / 86400
    )

    return dias

def guardar_config():

    data = {
        "inicio_cuna1": inicio_cuna1,
        "inicio_cuna2": inicio_cuna2,
        "inicio_cuna3": inicio_cuna3
    }

    with open("config.json", "w") as f:
        ujson.dump(data, f)

def cargar_config():

    global inicio_cuna1
    global inicio_cuna2
    global inicio_cuna3

    try:

        with open("config.json", "r") as f:

            data = ujson.load(f)

            inicio_cuna1 = data.get("inicio_cuna1", 0)
            inicio_cuna2 = data.get("inicio_cuna2", 0)
            inicio_cuna3 = data.get("inicio_cuna3", 0)

        print("✅ Config local cargada")

    except:
        print("⚠️ No existe config local")

def setup_mqtt():

    client = connect_mqtt()

    if client:
        client.set_callback(mqtt_callback)
        client.subscribe(b"minigranja/config")

    return client
# ================= INICIO =================

print("🚀 Iniciando sistema...\n")

cargar_config()

oled.fill(0)
oled.text("Iniciando...", 0, 0)
oled.show()

scan_networks()
connect_internet()
sync_time()

mqtt = setup_mqtt()
if mqtt:
    mqtt.set_callback(mqtt_callback)
    mqtt.subscribe(b"minigranja/config")

# ================= LOOP =================

while True:
    try:
        now = time.time()

        # 🔄 Verificar WiFi
        sta_if = network.WLAN(network.STA_IF)
        if not sta_if.isconnected():
            print("⚠️ WiFi perdido, reconectando...")
            connect_internet()
            mqtt = setup_mqtt()

        # 🔄 Verificar MQTT
        if mqtt is None:
            mqtt = setup_mqtt()

        # 🔄 Verificar mensajes
        if mqtt:

            try:
                mqtt.check_msg()

            except Exception as e:

                print("⚠️ MQTT check error:", e)
                mqtt = None


        edad_cuna1 = calcular_dias(inicio_cuna1)
        edad_cuna2 = calcular_dias(inicio_cuna2)
        edad_cuna3 = calcular_dias(inicio_cuna3)

        print(f"📊 Edades: Cuna1={edad_cuna1}d, Cuna2={edad_cuna2}d, Cuna3={edad_cuna3}d")

        # ================= CONTROL LOCAL =================

        if now - last_control > CONTROL_INTERVAL:
        
            cunas = leer_cunas()

            temp_amb, hum = leer_ambiente()

            # 🔥 CONTROL POR CUNA

            res1 = ctrl1.compute({
                "edad": edad_cuna1,
                "tempcuna": cunas.get("cuna1", 0),
                "tempamb": temp_amb
            })

            res2 = ctrl2.compute({
                "edad": edad_cuna2,
                "tempcuna": cunas.get("cuna2", 0),
                "tempamb": temp_amb
            })

            res3 = ctrl3.compute({
                "edad": edad_cuna3,
                "tempcuna": cunas.get("cuna3", 0),
                "tempamb": temp_amb
            })

            # 🔥 PROMEDIO VENTILADOR

            vent = (
                res1["vent"] +
                res2["vent"] +
                res3["vent"]
            ) / 3

            # 🔥 DIMMER

            set_brightness(1, res1["foco"])
            set_brightness(2, res2["foco"])
            set_brightness(3, res3["foco"])

            # 🔥 VENTILADOR

            if vent > 60:
                ventilador.value(1)
            else:
                ventilador.value(0)

            last_control = now   

        # ================= ENVIO AWS =================

        if now - last_send > SEND_INTERVAL:


            data = {
            
                "device_id": MQTT_CLIENT_ID,

                "timestamp": int(now),

                "cunas": cunas,

                "ambiente": {
                    "temp": temp_amb,
                    "hum": hum
                },

                "control": {
                
                    "cuna1": res1,
                    "cuna2": res2,
                    "cuna3": res3,

                    "ventilador": vent
                },

                "edades": {
                
                    "cuna1": edad_cuna1,
                    "cuna2": edad_cuna2,
                    "cuna3": edad_cuna3
                }
            }

            try:
            
                mqtt.publish(
                    TOPIC,
                    ujson.dumps(data)
                )

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
