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

print("Dimmer funcionando...")