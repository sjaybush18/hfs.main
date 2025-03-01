import logging
from logging.handlers import RotatingFileHandler
# Load the logfile
log_name = "/usr/local/src/hfs/public/public.log"
#log_name = "./public/public.log"
#use ArpaE (ArpaE2019)
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

handler = RotatingFileHandler(log_name, maxBytes= 3 * 1024, backupCount=1, encoding=None, delay=0)
handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', '%d/%m/%Y %H:%M:%S'))

log.addHandler(handler)

log.info('HFS server starting...')

from bleak import BleakClient, BleakScanner, BleakError
import json
from math import pi
import subprocess
import time
import struct
import asyncio
import json
from datetime import datetime
import dynamic_graphs as dgraphing
import sys

import pickle

# load the configurations
_CONFIG = None
_AVERAGE_FLUX = 1

# global device list
DEVICES = dict()

# initialize the addresses and uuids
_ADDRESSES = {"A8:03:2A:6A:36:E6", "B8:27:EB:F1:28:DD"}
_HANDLES = set()

_COMM_UUID = "26c00001-ece0-4f7a-b663-223de05387cc"
_COMM_RW_UUID = "26c00002-ece0-4f7a-b663-223de05387cc"

_SERVICE_UUIDS = [_COMM_UUID]

class DeviceConfig():
    def __init__(self, address, name):
        self.command = 10
        self.parameter = 0
        self.interval = 30 # min
        self.name = name
        self.address = address

class Device():
    def __init__(self, client_info):
        self.client_info = client_info
        self.address = self.client_info.address
        self.event = asyncio.Event()
        self.msg = None
        self.task = None
        self.main = None
        self.config = self.load_config(defaultname=self.client_info.name)
    
    def command(self):
        return (self.config.command, self.config.parameter)
    
    def name(self):
        return self.config.name + " (" + self.address + ")"
    
    def save_config(self):
        path = '/usr/local/src/hfs/devices/' + self.address.replace(':', '') + '.pickle'
        log.info(f"Saving {self.name()} to {path}...")
        try:
            with open(path, 'wb+') as config_file:
                pickle.dump(self.config, config_file, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as err:
            log.info(f'BAD {err}')
        log.info(f"Saved {self.name()} to {path}")
        
    def load_config(self, defaultname=""):
        path = '/usr/local/src/hfs/devices/' + self.address.replace(':', '') + '.pickle'
        try:
            with open(path, 'rb') as config_file:
                return pickle.load(config_file)
        except (OSError, IOError):
            return DeviceConfig(self.address, defaultname)
        
    async def run(self, client):
        log.info('runner')
        try:
            log.info(f"{self.name()} is running program {self.config.command} with parameter {self.config.parameter} every {self.config.interval} minutes")
            while True:
                await asyncio.sleep(self.config.interval * 60)
                log.info(f"Running command {self.config.command} on {self.name()}")
                await self.send(client, self.command())
        except Exception as error:
            log.warning(f"Current program execution for {self.name()} has been cancelled due to the following error: '{error}'")
    
    async def send(self, client, command):
        try:
            await client.write_gatt_char(_COMM_RW_UUID, data=struct.pack("HI", *command))
        except Exception as error:
            log.error(f"Sending command {command} to {self.name()} failed due ot the following error: {error}")
        
    async def disconnect(self):
        if (self.task != None) and (not self.task.cancelled()):
            self.task.cancel()
        self.main.cancel()
    
    def onMessage(self, msg):
        self.msg = msg
        self.event.set()
    
    async def handler(self, client, cmd, data):
        if cmd <= 0: # send the command directly to the controller
            await self.send(client, (abs(cmd), int(data)))
        elif cmd == 2: # update the command we run
            #self.command = (abs(data), self.command[1])
            
            try:
                self.config.command = abs(int(data))
                self.save_config()
                log.info(f"{self.name()} will now run program {self.config.command}")
                if (self.config.command != 10):
                    if (self.task != None) and (not self.task.cancelled()):
                        self.task.cancel()
                    self.task = None
                elif (self.task == None) or self.task.cancelled(): 
                    self.task = asyncio.create_task(self.run(client))
            except Exception as err:
                log.info(err)
        elif cmd == 4: # update the delay in our run function
            if int(data) < 0: return
            
            if (self.task != None) and (not self.task.cancelled()):
                self.task.cancel()
            
            self.config.interval = int(data)
            self.save_config()
            
            if (self.config.command != 10): return
            self.task = asyncio.create_task(self.run(client))
        elif cmd == 5: # update the name of the device
            old_name = self.name()
            self.config.name = data
            self.save_config()
            log.info(f"'{old_name}' has been renamed to '{self.name()}'")
        else:
            log.warning(f'Unknown command {self.msg["cmd"]}')

    async def check_for_disconnect(self, client):
        if not client.is_connected:
            await disconnect_handler(client)
            return True
        return False
            
                            
    async def keep_alive(self): 
        try:
            async with BleakClient(
                self.client_info, timeout=5.0, disconnected_callback=disconnect_handler
            ) as client:
                log.info(f"Connected to {self.name()}")
                try:
                    
                    # start the task if running default
                    if self.config.command == 10: self.task = asyncio.create_task(self.run(client))
                    # ??? no idea what this does, but is probably very important
                    await client.start_notify(_COMM_RW_UUID, notification_handler)
                    # update the device's interal clock
                    await self.send(client, (6, int(time.time())))
                    # start the device loop
                    while True:
                        try:
                            await asyncio.wait_for(self.event.wait(), timeout=2) # wait for us to recieve a message
                            if(await self.check_for_disconnect(client)): 
                                raise BleakError("Client is no longer connected")
                            await self.handler(client, self.msg['cmd'], self.msg['data']) # handle the message
                            self.event.clear() # reset the message flag
                        except asyncio.TimeoutError:
                            if(await self.check_for_disconnect(client)):
                                raise BleakError("Client is no longer connected")
                except (BleakError, KeyboardInterrupt):
                    log.info(f"{self.name()} disconnected")    
        except Exception as error:
            log.error(f"Something went wrong... {error}")
            await disconnect_handler(self.client_info)
        
class OnMessageEvent():
  def __init__(self):
    self.listeners = {}

  def emit(self, msg_json):
    for address, device in DEVICES.items():
        if address != msg_json['addr']: continue
        device.onMessage(msg_json)

def load_config(path="/usr/local/src/hfs/config.json"):
    global _CONFIG, _AVERAGE_FLUX
    # load the config file
    try:
        with open(path, "r") as file:
            _CONFIG = json.load(file)
        # compute the average flux
        sensing_area = ((_CONFIG["constants"]["cutoff_diameter_mm"] / 2) ** 2) * pi
        _AVERAGE_FLUX = _CONFIG["constants"]["total_canopy_flux"] / sensing_area
        log.info(f"Loaded config file {_CONFIG}")
        return True
    except:
        log.warning(f"Config file does not exist at {path}")
        return False

# helper to print advertisement data
def print_ad_data(data):
    count = 0
    if data.service_uuids:
        for service in data.service_uuids:
            count += 1
    if data.local_name:
        log.info(f"Found '{data.local_name}' with {count} services")
        return
    log.info(f"Found '{device.address}' with {count} services")

# decode value from characteristic
def decode(data):
    decoded_data = struct.unpack_from("<HIHHH", data)
    return (decoded_data[0], decoded_data[1], decoded_data[2], decoded_data[3], decoded_data[4])

def scan_handler(device, data):
    print_ad_data(data)

def notification_handler(sender, data):
    # decode the data and print to logs
    try:
        id, timestamp, distance_mm, chlf_raw, msg_len = decode(data)
        if msg_len != 0:
            msg = struct.unpack_from(f"{msg_len}s", data, struct.calcsize("<HIHHH"))[0].decode()
            log.info(f"[{id}] {msg}")
            return
    except Exception as err:
        log.error(f"Could not decode message because {err}")
        return
    
    
    log.info(f"Recieved data from {sender} (id={id}) at {timestamp}: chlf={chlf_raw} d={distance_mm}mm")
    # compute the datetime, sensor id, normal chlf, and chlf factor
    dt_timestamp = datetime.fromtimestamp(timestamp)
    f_factor = 0
    chlf_normal = 0
    
    try:
        chlf_normal = chlf_raw / _CONFIG["constants"]["max_raw_value"]
    except Exception as error:
        log.error(f"Calculating flourescence factor and normalized chlf failed because {error}")
        
    try:
        chlf_scaled_raw = chlf_normal * 4095 
        f_factor = (chlf_scaled_raw * _CONFIG["constants"]["k"]) / (_AVERAGE_FLUX * _AVERAGE_FLUX * distance_mm * distance_mm)
    except Exception as error:
        log.error(f"Calculating flourescence factor and normalized chlf failed because {error}")
    # update the database
    try:
        cmd = f'psql -c  "INSERT INTO data (id, timestamp, chlf_raw, chlf_normal, f_factor, distance) VALUES ({id}, to_timestamp({timestamp}), {chlf_raw}, {chlf_normal}, {f_factor}, {distance_mm});"'
        result = subprocess.run(["su", "-", "postgres", "-c", f"{cmd}"], stdout=subprocess.DEVNULL)
        log.info(f"Updated database with {result}")
    except Exception as error:
        log.error(f"Failed to update database because {error}")
    # update the local visuals
    try:
        dgraphing.update(dt_timestamp, id, chlf_raw, chlf_normal, f_factor)
        dgraphing.save()
        log.info("Updated visuals!")
    except Exception as error:
        log.error(f"Failed to update visuals because {error}")

#load_config()
#notification_handler('dummy', struct.pack('<HIHH', 0, int(time.time()), int(15.30 * 100), 3207))

async def scan(timeout=5.0):
    scanner = BleakScanner(detection_callback=scan_handler, service_uuids=_SERVICE_UUIDS)

    log.info('Starting scan...')
    await scanner.start()
    await asyncio.sleep(timeout)
    await scanner.stop()
    log.info('Scan finished.')

    #return scanner.discovered_devices
    try:
        return await scanner.get_discovered_devices()
    except Exception as exception:
        log.error(exception)
        return []
        
async def disconnect_handler(client):
    log.info(f"Disconnected from {client.address}")
    log.info(DEVICES)
    device = DEVICES[client.address]
    DEVICES.pop(client.address)
    log.info(DEVICES)
    await device.disconnect()
    log.info('- finished disconnecting')

async def connect_to_device(client):
    try:
        if client.address in DEVICES:
            # something is wrong, forcibly disconnect and remove
            DEVICES[client.address].disconnect()
            DEVICES.pop(client.address)
    except Exception as error:
        log.info(error)
    log.info(f'Connecting to {client}...')
    device = Device(client)
    DEVICES[client.address] = device
    device.main = asyncio.create_task(device.keep_alive())
    await device.main
    log.warning(f"{client.address} is unresponsive!")

async def ainput():
    return await asyncio.get_event_loop().run_in_executor(
            None, sys.stdin.readline)

async def inputLoop():
    global on_msg_event
    run = True
    while run:
        try:
            msg = json.loads(await ainput())
            log.info(f'> {msg}')
            if msg['cmd'] == 3: # wants a list of returned devices
                devices = []
                for device in DEVICES.values():
                    devices.append(json.dumps(device.config.__dict__))
                response = json.dumps({'code': 1, 'devices': devices})
                log.info(f'< {response}')
                print(response)
            else:                
                try:
                    on_msg_event.emit(msg)
                    log.info("< {'code': 1}")
                    print(json.dumps({'code': 1}))
                except Exception as error:
                    log.info(f"< \{'code': 0, 'error': {error}\}")
                    print(json.dumps({'code': 0, 'error': error}))
                    
                
        except EOFError:
            log.warning("EOF Error")
            print(json.dumps({'code': 0})) # tell the Node.js server we crashed
            run = False

async def bleLoop():
    run = True
    while run:
        devices = await scan()
        if devices:
            log.info("Found device(s) with valid service.")
            asyncio.gather(*(connect_to_device(dev) for dev in devices))
            log.info(devices)
            log.info("Searching for devices again in 5 minutes..")
            # await asyncio.sleep(60*5)
            await asyncio.sleep(10)
        else:
            log.info("No devices with valid services found. Retrying in 10 seconds..")
            await asyncio.sleep(10)

on_msg_event = OnMessageEvent()

async def main():
    log.info("Loading config.json...")
    
    if not load_config():
        log.warning("Loading expected config.json failed, resorting to local configuration")
        load_config("./config.json")

    task_ble = asyncio.create_task(bleLoop())
    task_api = asyncio.create_task(inputLoop())
    
    await task_ble
    log.error("BLE task has ended prematurely!")
    await task_api
    log.error("API task has ended prematurely!")

if __name__ == "__main__":
    asyncio.run(main())
