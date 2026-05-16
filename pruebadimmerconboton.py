# ...existing code...
from machine import Pin, Timer
import utime

# Pines
zero_cross = Pin(14, Pin.IN)
triac = Pin(15, Pin.OUT)

# Ajusta este valor (0 = máximo brillo, alto = menos brillo)
dimming_delay = 5000  # microsegundos

timer = Timer()

def disparar_triac(timer):
    triac.value(1)
    utime.sleep_us(10)  # pulso corto
    triac.value(0)

def zero_cross_detect(pin):
    # Se ejecuta cada cruce por cero
    timer.init(mode=Timer.ONE_SHOT,
               period=dimming_delay // 1000,  # ms
               callback=disparar_triac)

# Interrupción en cruce por cero
zero_cross.irq(trigger=Pin.IRQ_RISING, handler=zero_cross_detect)

# Botón para ajustar dimming_delay
# Conectar botón entre el pin y GND (pull-up interno activado).
button_pin = Pin(13, Pin.IN, Pin.PULL_UP)

# Variables para debounce y comunicación entre IRQ y bucle principal
button_last_ms = 0
button_changed = False
button_new_value = 0

def button_irq(pin):
    global button_last_ms, button_changed, button_new_value
    now = utime.ticks_ms()
    # Debounce 200 ms
    if utime.ticks_diff(now, button_last_ms) < 200:
        return
    button_last_ms = now
    # Calcular nuevo valor sin actualizarlo directamente (se hará en el bucle principal)
    new = dimming_delay + 1000
    if new >= 8000:
        new = 0
    button_new_value = new
    button_changed = True

# IRQ al pulsar (caída a GND)
button_pin.irq(trigger=Pin.IRQ_FALLING, handler=button_irq)

print("Dimmer funcionando...")
print("dimming_delay inicial =", dimming_delay)

# Bucle principal: aplica el cambio y muestra el valor
while True:
    if button_changed:
        # Aplicar el nuevo valor (realmente modifica la variable usada por el temporizador)
        dimming_delay = button_new_value
        button_changed = False
        print("dimming_delay =", dimming_delay)
    utime.sleep_ms(100)
# ...existing code...