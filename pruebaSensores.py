import time, machine, dht, onewire, ds18x20

# DS18B20
ds = ds18x20.DS18X20(onewire.OneWire(machine.Pin(15)))
roms = ds.scan()

# DHT22
dht1 = dht.DHT22(machine.Pin(14))
dht2 = dht.DHT22(machine.Pin(13))

while True:
    print("\n--- TEST ---")

    ds.convert_temp()
    time.sleep(1)

    for i, rom in enumerate(roms):
        print("Cuna", i+1, ds.read_temp(rom))

    try:
        dht1.measure()
        print("DHT1:", dht1.temperature(), dht1.humidity())
    except:
        print("Error DHT1")

    try:
        dht2.measure()
        print("DHT2:", dht2.temperature(), dht2.humidity())
    except:
        print("Error DHT2")

    time.sleep(3)