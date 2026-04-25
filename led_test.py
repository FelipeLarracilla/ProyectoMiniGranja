from machine import Pin
import time

# En la Raspberry Pi Pico W, el LED interno está en el pin 25
led = Pin(25, Pin.OUT)

while True:
    led.value(1)
    time.sleep(0.5)
    led.value(0)
    time.sleep(0.5)
