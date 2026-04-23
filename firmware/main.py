from machine import Pin, ADC
import time

sensor = ADC(Pin(3)) #where my soil sensor is connected
red = Pin(4, Pin.OUT) # input of red led
green = Pin(10, Pin.OUT)

while True: 
    v = sensor.read_u16()
    red.value(0)
    green.value(0)

    if v >= 47000:
        red.value(1)
        state = "DRY — water me"
    elif v >= 38000:
        red.value(1)
        green.value(1)
        state = "getting dry"
    elif v >= 32000:
        green.value(1)
        state = "happy"
    else:
        state = "too wet"

    print(v, "->", state)
    time.sleep(1)
