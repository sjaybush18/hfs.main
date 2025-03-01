#taken from https://github.com/uceeatz/VL53L0X/blob/master/main.py

import pycom
import time
from machine import Pin
from machine import I2C
import VL53L0X

#i2c = I2C(0)
#i2c = I2C(0, I2C.MASTER)
#i2c = I2C(0, pins=('P10','P9'))
#i2c = I2C(0, sda=Pin(21), scl=Pin(22),freq=100000) 
i2c = I2C(0, sda=Pin(5), scl=Pin(4))
#i2c.init(I2C.MASTER, baudrate=9600)#

# Create a VL53L0X object
i2c.scan()
tof = VL53L0X.VL53L0X(i2c)

tof.set_Vcsel_pulse_period(tof.vcsel_period_type[0], 18)

tof.set_Vcsel_pulse_period(tof.vcsel_period_type[1], 14)


while True:
# Start ranging
    tof.start()
    tof.read()
    print(tof.read())
    tof.stop()






    #q = tof.set_signal_rate_limit(0.1)
    #
    # time.sleep(0.1)