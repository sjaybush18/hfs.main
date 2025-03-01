from machine import Pin, ADC, PWM

import time
import uasyncio as asyncio

import device_sensor as sensor # sensor.readAndSend(server, pipe)
import device_pins as pins

fs = [15, 50, 100, 200, 400, 800, 1000, 1200, 1400, 1600, 1800, 2000]

# entry point for the program
# run this program once and only once, server will decide how to loop
async def run(server, pipe, data: int):    
    print("[prgm_flashtest] start")
    led_flash = PWM(Pin(33, Pin.OUT))

    # set up pins
    #measured_result = ADC(Pin(14, Pin.IN))
    for f in fs:
        print(f"[prgm_flashtest] flashing with freq={f}...")
        led_flash.init(freq=f)
        asyncio.sleep(2)
        led_flash.deinit()
    pipe.notify(server)
    print("[prgm_flashtest] stop")

