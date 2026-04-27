from machine import Pin
import utime
import math

# 🔌 PINES
zero_cross = Pin(14, Pin.IN)

triac1 = Pin(16, Pin.OUT)
triac2 = Pin(17, Pin.OUT)
triac3 = Pin(18, Pin.OUT)

# 🔧 CONFIG
GAMMA = 2.2
MIN_DELAY = 1000
MAX_DELAY = 1125
OFF_DELAY = 1160

delay1 = OFF_DELAY
delay2 = OFF_DELAY
delay3 = OFF_DELAY

def calc_delay(p):
    if p <= 0:
        return OFF_DELAY
    if p > 100:
        p = 100

    x = p / 100.0
    y = math.pow(x, GAMMA)

    return int(MIN_DELAY + (1 - y) * (MAX_DELAY - MIN_DELAY))

def set_brightness(ch, porcentaje):
    global delay1, delay2, delay3

    d = calc_delay(porcentaje)

    if ch == 1:
        delay1 = d
    elif ch == 2:
        delay2 = d
    elif ch == 3:
        delay3 = d

def disparo(delay, triac):
    utime.sleep_us(delay)
    triac.value(1)
    utime.sleep_us(200)
    triac.value(0)

def zero_cross_detect(pin):
    disparo(delay1, triac1)
    disparo(delay2, triac2)
    disparo(delay3, triac3)

zero_cross.irq(trigger=Pin.IRQ_RISING, handler=zero_cross_detect)