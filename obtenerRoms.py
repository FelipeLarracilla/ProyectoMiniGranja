import machine
import onewire, ds18x20
import time

ds = ds18x20.DS18X20(onewire.OneWire(machine.Pin(15)))

roms = ds.scan()

print("Sensores encontrados:")

for i, rom in enumerate(roms):
    print(f"Sensor {i+1}: {rom}")

while True:
    ds.convert_temp()
    time.sleep(1)

    for i, rom in enumerate(roms):
        temp = ds.read_temp(rom)
        print(f"Sensor {i+1}: {temp} °C")

    print("-----")
    time.sleep(3)