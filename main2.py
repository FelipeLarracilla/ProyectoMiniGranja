import network
import time
from umqtt.simple import MQTTClient
import machine
import onewire, ds18x20
import dht
import ujson

# WIFI
SSID = "TU_WIFI"
PASSWORD = "TU_PASSWORD"

# AWS
MQTT_BROKER = "xxxxxxxxxxxx.iot.region.amazonaws.com"
CLIENT_ID = "picoW"
TOPIC = b"minigranja/temperatura"

# DS18B20
ds_pin = machine.Pin(15)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
roms = ds_sensor.scan()

# DHT22
dht_sensor = dht.DHT22(machine.Pin(14))

# Conectar WiFi
def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    while not wlan.isconnected():
        time.sleep(1)
    print("WiFi conectado:", wlan.ifconfig())

# MQTT
def conectar_mqtt():
    client = MQTTClient(CLIENT_ID, MQTT_BROKER, port=8883)
    client.connect()
    return client

# MAIN
conectar_wifi()
client = conectar_mqtt()

while True:
    # DS18B20
    ds_sensor.convert_temp()
    time.sleep(1)

    temps_cunas = []
    for rom in roms:
        temp = ds_sensor.read_temp(rom)
        temps_cunas.append(temp)

    # DHT22
    dht_sensor.measure()
    temp_amb = dht_sensor.temperature()
    hum = dht_sensor.humidity()

    # JSON
    data = {
        "cunas": temps_cunas,
        "temp_ambiente": temp_amb,
        "humedad": hum
    }

    msg = ujson.dumps(data)

    # Publicar
    client.publish(TOPIC, msg)

    print(msg)

    time.sleep(5)