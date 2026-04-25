# module imports
import machine
import network
import ntptime
import ssl
import time
import ubinascii

from simple import MQTTClient

#import config


#SSID = config.SSID
SSID = "HONOR90"
WIFI_PASSWORD = "123456789#"
#WIFI_PASSWORD = config.WIFI_PASSWORD

MQTT_CLIENT_ID = ubinascii.hexlify(machine.unique_id())
### Replace with the names of the files from your certs and keys
MQTT_CLIENT_KEY = "161503fd8c9c5f862e56539f58727e93fefeea3764db5794be856bf39d541e0f-private.pem.key"
MQTT_CLIENT_CERT = "161503fd8c9c5f862e56539f58727e93fefeea3764db5794be856bf39d541e0f-certificate.pem.crt"

### You can find this URL by going into the AWS IoT Core Settings under "Endpoint"
MQTT_BROKER = "a3p59r2o0rf9tq-ats.iot.us-east-1.amazonaws.com"
MQTT_BROKER_CA = "AmazonRootCA1.pem"

led = machine.Pin("LED", machine.Pin.OUT)


# function that reads PEM file and return byte array of data
def read_pem(file):
    with open(file, "r") as input:
        text = input.read().strip()
        split_text = text.split("\n")
        base64_text = "".join(split_text[1:-1])
        return ubinascii.a2b_base64(base64_text)


def connect_internet():
    try:
        sta_if = network.WLAN(network.STA_IF)
        sta_if.active(True)
        sta_if.connect(SSID, WIFI_PASSWORD)

        for i in range(0, 20):
            if sta_if.isconnected():
                print("Connected to Wi-Fi")
                return True
            time.sleep(1)
            print(f"Connecting... {i+1}s")
        
        print("Failed to connect to Wi-Fi")
        return False
    except Exception as e:
        print('There was an issue connecting to WIFI')
        print(e)
        return False


# callback function to handle received MQTT messages
def on_mqtt_msg(topic, msg):
    # convert topic and message from bytes to string
    topic_str = topic.decode()
    msg_str = msg.decode()

    print(f"RX: {topic_str}\n\t{msg_str}")

    # process message
    if topic_str == 'LED':
        if msg_str == "on":
            led.on()
        elif msg_str == "off":
            led.off()
        elif msg_str == "toggle":
            led.toggle()


connect_internet()

# Sincronizar hora con servidor NTP (con reintentos)
def sync_time():
    max_retries = 3
    for attempt in range(max_retries):
        try:
            ntptime.settime()
            print("Hora sincronizada con NTP")
            return True
        except Exception as e:
            print(f"Intento {attempt + 1}/{max_retries} - Error NTP: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # Esperar 2 segundos antes de reintentar
    
    # Si todos los intentos fallan, usar hora manual como respaldo
    print("NTP falló, usando hora manual...")
    try:
        rtc = machine.RTC()
        rtc.datetime((2026, 4, 11, 4, 12, 0, 0, 0))
        print("Hora manual establecida: 2026-04-11 12:00:00")
        return True
    except Exception as manual_e:
        print(f"Error hora manual: {manual_e}")
        return False

# Sincronizar hora al inicio
sync_time()

# read the data in the private key, public certificate, and
# root CA files
key = read_pem(MQTT_CLIENT_KEY)
cert = read_pem(MQTT_CLIENT_CERT)
ca = read_pem(MQTT_BROKER_CA)

# create MQTT client that use TLS/SSL for a secure connection
mqtt_client = MQTTClient(
    MQTT_CLIENT_ID,
    MQTT_BROKER,
    keepalive=60,
    ssl=True,
    ssl_params={
        "key": key,
        "cert": cert,
        "server_hostname": MQTT_BROKER,
        "cert_reqs": ssl.CERT_REQUIRED,
        "cadata": ca,
    },
)

print(f"Connecting to MQTT broker")
# register callback to for MQTT messages, connect to broker and
# subscribe to LED topic
mqtt_client.set_callback(on_mqtt_msg)
mqtt_client.connect()
mqtt_client.subscribe('LED')


# main loop, continuously check for incoming MQTT messages
print("Connection established, awaiting messages")
last_ping = time.time()
last_time_sync = time.time()

while True:
    try:
        current_time = time.time()
        
        # Sincronizar hora cada 6 horas (21600 segundos)
        if current_time - last_time_sync > 21600:
            print("Sincronizando hora periódicamente...")
            if sync_time():
                last_time_sync = time.time()
        
        # Verificar conexión WiFi cada 30 segundos
        if current_time - last_ping > 30:
            if not network.WLAN(network.STA_IF).isconnected():
                print("WiFi disconnected, reconnecting...")
                if connect_internet():
                    print("WiFi reconnected, reconnecting MQTT...")
                    mqtt_client.connect()
                    mqtt_client.subscribe('LED')
                else:
                    print("Failed to reconnect WiFi")
            else:
                # Enviar ping MQTT para mantener conexión viva
                try:
                    mqtt_client.ping()
                    last_ping = current_time
                except:
                    print("MQTT ping failed, reconnecting...")
                    mqtt_client.connect()
                    mqtt_client.subscribe('LED')
        
        # Verificar mensajes MQTT
        mqtt_client.check_msg()
        time.sleep(0.1)  # Pequeña pausa para no saturar CPU
        
    except Exception as e:
        print(f"Error in main loop: {e}")
        print("Attempting to reconnect...")
        try:
            if connect_internet():
                mqtt_client.connect()
                mqtt_client.subscribe('LED')
                print("Reconnected successfully")
            else:
                print("Failed to reconnect")
        except Exception as reconn_e:
            print(f"Reconnection failed: {reconn_e}")
        time.sleep(5)  # Esperar antes de intentar reconectar