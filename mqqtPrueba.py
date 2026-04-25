import network
import time
from umqtt.simple import MQTTClient
import ssl
import ujson

# -------- WIFI --------
SSID = "HONOR90"
PASSWORD = "123456789#"

# -------- AWS --------
MQTT_BROKER = "a3p59r2o0rf9tq-ats.iot.us-east-1.amazonaws.com"
CLIENT_ID = "pico_w_minigranja_1"
TOPIC = b"minigranja/temperatura"

# -------- WIFI --------
def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    while not wlan.isconnected():
        time.sleep(1)

    print("WiFi conectado")

# -------- MQTT --------
def conectar_mqtt():
    client = MQTTClient(
        CLIENT_ID,
        MQTT_BROKER,
        port=8883,
        ssl=True,
        ssl_params={
            "certfile": "161503fd8c9c5f862e56539f58727e93fefeea3764db5794be856bf39d541e0f-certificate.pem",
            "keyfile": "161503fd8c9c5f862e56539f58727e93fefeea3764db5794be856bf39d541e0f-private.pem.key",
            "ca_certs": "AmazonRootCA1.pem"
        }
    )
    client.connect()
    print("Conectado a AWS IoT")
    return client

# -------- MAIN --------
conectar_wifi()
client = conectar_mqtt()

while True:
    data = {
        "mensaje": "hola desde pico",
        "temp": 30
    }

    msg = ujson.dumps(data)
    client.publish(TOPIC, msg)

    print("Enviado:", msg)

    time.sleep(5)