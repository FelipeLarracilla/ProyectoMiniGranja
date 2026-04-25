import machine
import onewire, ds18x20
import time
import ubinascii

ds = ds18x20.DS18X20(onewire.OneWire(machine.Pin(15)))

roms = ds.scan()

print("Sensores encontrados (HEX):\n")

roms_hex = []

for i, rom in enumerate(roms):
    rom_hex = ubinascii.hexlify(rom).decode()
    roms_hex.append(rom_hex)
    print(f"Sensor {i+1}: {rom_hex}")

print("\n--- Lectura de temperatura ---\n")

while True:
    ds.convert_temp()
    time.sleep(1)

    for i, rom in enumerate(roms):
        temp = ds.read_temp(rom)
        print(f"Sensor {i+1} ({roms_hex[i]}): {temp} °C")

    print("----------------------------")
    time.sleep(3)