from machine import Pin, ADC
import time
import network
import secrets

sensor = ADC(Pin(3)) #where my soil sensor is connected
red = Pin(4, Pin.OUT) # input of red led
green = Pin(10, Pin.OUT)

def connect_wifi(timeout=10):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print("already connected:", wlan.ifconfig()[0])
        return wlan

    print("connecting to", secrets.WIFI_SSID)
    wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)

    for _ in range(timeout * 2):
        if wlan.isconnected():
            print("connected:", wlan.ifconfig()[0])
            return wlan
        time.sleep(0.5)

    print("wifi failed — continuing offline")
    return wlan

wlan = connect_wifi()

while True:
    v = sensor.read_u16()
    red.value(0)
    green.value(0)

    if v >= 47000:
        red.value(1)
        state = "DRY — water me"
    elif v >= 40000:
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
