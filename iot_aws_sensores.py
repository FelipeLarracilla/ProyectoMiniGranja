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

from simple import MQTTClient

# ================= WIFI =================
SSID = "HONOR"
WIFI_PASSWORD = "123456789#"

# ================= AWS =================
MQTT_CLIENT_ID = ubinascii.hexlify(machine.unique_id()).decode()

MQTT_CLIENT_KEY = "161503fd8c9c5f862e56539f58727e93fefeea3764db5794be856bf39d541e0f-private.pem.key"
MQTT_CLIENT_CERT = "161503fd8c9c5f862e56539f58727e93fefeea3764db5794be856bf39d541e0f-certificate.pem.crt"
MQTT_BROKER = "a3p59r2o0rf9tq-ats.iot.us-east-1.amazonaws.com"
MQTT_BROKER_CA = "AmazonRootCA1.pem"

TOPIC = b"minigranja/temperatura"

# ================= LED =================
led = machine.Pin("LED", machine.Pin.OUT)

# ================= SENSORES =================
# DS18B20
ds = ds18x20.DS18X20(onewire.OneWire(machine.Pin(15)))

sensores_cunas = {
    "cuna1": "28bff451000000d3",
    "cuna2": "28818514000000ec",
    "cuna3": "28c8d81400000076"
}

# DHT22
dht1 = dht.DHT22(machine.Pin(14))
dht2 = dht.DHT22(machine.Pin(13))

# ================= FUNCIONES =================

def read_pem(file):
    with open(file, "r") as input:
        text = input.read().strip()
        split_text = text.split("\n")
        base64_text = "".join(split_text[1:-1])
        return ubinascii.a2b_base64(base64_text)

def scan_networks():
    """Escanea y muestra las redes WiFi disponibles"""
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    print("📡 Escaneando redes disponibles...")
    networks = sta_if.scan()
    
    print("\n📶 Redes encontradas:")
    for i, net in enumerate(networks, 1):
        ssid = net[0].decode() if isinstance(net[0], bytes) else net[0]
        signal = net[3]
        print(f"  {i}. {ssid} (Señal: {signal} dBm)")
    print()
    return sta_if

def connect_internet():
    """Conecta a WiFi con reintentos indefinidos"""
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    
    retry_count = 0
    while True:
        try:
            if not sta_if.isconnected():
                print(f"🔄 Intento de conexión #{retry_count + 1}...")
                sta_if.connect(SSID, WIFI_PASSWORD)
                
                for i in range(20):
                    if sta_if.isconnected():
                        print("✅ WiFi conectado")
                        print(f"   IP: {sta_if.ifconfig()[0]}")
                        return True
                    time.sleep(1)
                    print(f"   Conectando... {i+1}s")
                
                print(f"❌ Error WiFi (intento {retry_count + 1} fallido)")
                retry_count += 1
                time.sleep(5)  # Esperar antes de reintentar
            else:
                print("✅ WiFi ya conectado")
                return True
                
        except Exception as e:
            print(f"⚠️ Excepción en WiFi: {e}")
            retry_count += 1
            time.sleep(5)

def sync_time():
    try:
        ntptime.settime()
        print("🕒 Hora sincronizada")
        return True
    except:
        print("⚠️ NTP falló, usando hora manual")
        rtc = machine.RTC()
        rtc.datetime((2026, 4, 11, 4, 12, 0, 0, 0))
        return False

def leer_sensores():
    cunas = {}
    ambiente = {"temp1": 0.0, "temp2": 0.0, "hum1": 0.0, "hum2": 0.0}
    
    # Leer DS18B20 - Escanear dinámicamente los sensores disponibles
    try:
        # Buscar todos los ROMs disponibles en el bus
        roms_disponibles = ds.scan()
        
        if roms_disponibles:
            # Si se encuentran sensores, leer sus temperaturas
            ds.convert_temp()
            time.sleep(0.75)  # DS18B20 necesita 750ms mínimo
            
            for i, rom in enumerate(roms_disponibles):
                try:
                    temp = ds.read_temp(rom)
                    # Asignar a cuna1, cuna2, cuna3 según índice
                    cuna_name = f"cuna{i+1}"
                    if temp is not None:
                        cunas[cuna_name] = float(temp)
                    else:
                        cunas[cuna_name] = 0.0
                except Exception as e:
                    cuna_name = f"cuna{i+1}"
                    print(f"  Error leyendo {cuna_name}: {e}")
                    cunas[cuna_name] = 0.0
        else:
            # Si no hay sensores disponibles
            print("  ⚠️ No se detectaron sensores DS18B20")
            cunas = {"cuna1": 0.0, "cuna2": 0.0, "cuna3": 0.0}
            
    except Exception as e:
        print(f"  Error DS18B20: {e}")
        cunas = {"cuna1": 0.0, "cuna2": 0.0, "cuna3": 0.0}

    # Leer DHT1
    try:
        dht1.measure()
        t1 = float(dht1.temperature())
        h1 = float(dht1.humidity())
        ambiente["temp1"] = t1
        ambiente["hum1"] = h1
    except Exception as e:
        print(f"  Error DHT1: {e}")
        ambiente["temp1"] = 0.0
        ambiente["hum1"] = 0.0

    # Leer DHT2
    try:
        dht2.measure()
        t2 = float(dht2.temperature())
        h2 = float(dht2.humidity())
        ambiente["temp2"] = t2
        ambiente["hum2"] = h2
    except Exception as e:
        print(f"  Error DHT2: {e}")
        ambiente["temp2"] = 0.0
        ambiente["hum2"] = 0.0

    return {
        "cunas": cunas,
        "ambiente": ambiente
    }

def on_mqtt_msg(topic, msg):
    topic_str = topic.decode()
    msg_str = msg.decode()

    print(f"📩 RX: {topic_str} -> {msg_str}")

    if topic_str == 'LED':
        if msg_str == "on":
            led.on()
        elif msg_str == "off":
            led.off()
        elif msg_str == "toggle":
            led.toggle()

# ================= INICIO =================

print("🚀 Iniciando MiniGranja IoT...\n")

# Escanear y conectar WiFi
scan_networks()
connect_internet()

sync_time()

# Cargar certificados
print("📄 Cargando certificados...")
try:
    key = read_pem(MQTT_CLIENT_KEY)
    cert = read_pem(MQTT_CLIENT_CERT)
    ca = read_pem(MQTT_BROKER_CA)
    print("✅ Certificados cargados")
except Exception as e:
    print(f"❌ Error al cargar certificados: {e}")
    while True:
        time.sleep(1)

# Crear cliente MQTT
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

mqtt_client.set_callback(on_mqtt_msg)

# Conectar a MQTT con reintentos
mqtt_connected = False
mqtt_retry = 0

while not mqtt_connected:
    try:
        print(f"🔗 Conectando a AWS IoT (intento {mqtt_retry + 1})...")
        mqtt_client.connect()
        mqtt_client.subscribe(b'LED')
        print("✅ Conectado a AWS IoT")
        mqtt_connected = True
    except Exception as e:
        print(f"❌ Error MQTT: {e}")
        mqtt_retry += 1
        time.sleep(5)
        
        # Reconectar WiFi si es necesario
        sta_if = network.WLAN(network.STA_IF)
        if not sta_if.isconnected():
            print("WiFi desconectado, reconectando...")
            connect_internet()

last_send = 0
mqtt_reconnect_attempt = 0

# ================= LOOP PRINCIPAL =================

try:
    while True:
        try:
            # Verificar conectividad
            sta_if = network.WLAN(network.STA_IF)
            if not sta_if.isconnected():
                print("⚠️ WiFi desconectado, reconectando...")
                connect_internet()
            
            current_time = time.time()

            # Enviar datos cada 5 segundos
            if current_time - last_send > 60:
                try:
                    sensores = leer_sensores()

                    # Redondear y garantizar que sean números
                    cunas_datos = {}
                    for nombre, temp in sensores["cunas"].items():
                        cunas_datos[nombre] = round(temp, 2)
                    
                    ambiente_datos = {}
                    for key, val in sensores["ambiente"].items():
                        ambiente_datos[key] = round(val, 2)

                    data = {
                        "device_id": MQTT_CLIENT_ID,
                        "timestamp": int(current_time),
                        "cunas": cunas_datos,
                        "ambiente": ambiente_datos
                    }

                    msg = ujson.dumps(data)

                    mqtt_client.publish(TOPIC, msg)
                    print("📤 Enviado:", msg)
                    mqtt_reconnect_attempt = 0  # Reset contador

                    last_send = current_time
                    
                except Exception as e:
                    print(f"⚠️ Error enviando datos: {e}")
                    mqtt_reconnect_attempt += 1

            # Mantener conexión y recibir mensajes
            try:
                mqtt_client.check_msg()
            except Exception as e:
                print(f"⚠️ Error MQTT: {e}")
                mqtt_reconnect_attempt += 1
                
                if mqtt_reconnect_attempt > 3:
                    print("🔄 Reintentando conexión MQTT...")
                    try:
                        mqtt_client.connect()
                        mqtt_client.subscribe(b'LED')
                        mqtt_reconnect_attempt = 0
                    except Exception as e2:
                        print(f"❌ Error reconectando: {e2}")

            time.sleep(0.1)

        except KeyboardInterrupt:
            raise  # Re-raise para que lo capture el except externo

        except Exception as e:
            print(f"⚠️ Error en loop: {e}")
            time.sleep(1)  # Pequeño delay para no abrumar

except KeyboardInterrupt:
    print("\n⏹️ Interrupción recibida, deteniendo programa...")
    mqtt_client.disconnect()

except Exception as e:
    print(f"\n❌ Error fatal: {e}")
    time.sleep(5)

finally:
    try:
        mqtt_client.disconnect()
        print("🔌 MQTT desconectado")
    except:
        pass
    print("✋ Programa detenido")