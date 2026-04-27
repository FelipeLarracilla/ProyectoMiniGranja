from machine import Pin
import utime
import math

zero_cross = Pin(14, Pin.IN)
triac = Pin(15, Pin.OUT)

# --- CALIBRACIÓN REAL ---
MIN_DELAY = 1000   # máximo brillo
MAX_DELAY = 1125   # mínimo visible
OFF_DELAY = 1160   # apagado total

GAMMA = 2.2

dimming_delay = OFF_DELAY


def set_brightness(porcentaje):
    global dimming_delay

    if porcentaje <= 0:
        dimming_delay = OFF_DELAY
        return

    if porcentaje > 100:
        porcentaje = 100

    # normalizar
    x = porcentaje / 100.0

    # curva gamma
    y = math.pow(x, GAMMA)

    # mapear SOLO rango útil
    delay = MIN_DELAY + (1 - y) * (MAX_DELAY - MIN_DELAY)

    dimming_delay = int(delay)


def zero_cross_detect(pin):
    utime.sleep_us(dimming_delay)
    
    triac.value(1)
    utime.sleep_us(200)
    triac.value(0)


zero_cross.irq(trigger=Pin.IRQ_RISING, handler=zero_cross_detect)

print("Dimmer calibrado correctamente")

# prueba
nivel = 0

while True:
    set_brightness(nivel)
    print("Brillo:", nivel, "% | delay:", dimming_delay)
    
    nivel += 5
    if nivel > 100:
        nivel = 0
    
    utime.sleep(1)