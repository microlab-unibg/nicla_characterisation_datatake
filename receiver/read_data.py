import asyncio
from datetime import datetime
import time
from bleak import BleakClient, BleakScanner
import struct

from helper_functions import ble_sense_uuid, setup_logging
from pynput import keyboard
import sys
import os
from pathlib import Path

# Constants
KNOWN_ADDRESSES = [
    "2E:DA:3A:76:2C:B1" # check this address
]
TIMEOUT = 10

SENSOR_NAME_LIST = [
    "service ID",
    "humidity",
    "temperature",
    "pressure",
    "iaq",
    "iaq_s",
    "co2_eq",
    "b_voc_eq",
    "comp_t",
    "comp_h",
    "comp_g",
    "gas",
    "accuracy",
]
ID_LIST = [
    "0000", # service ID, not to be read
    "3001", # humidity
    "2001", # temperature
    "4001", # pressure
    "9001", # iaq
    "9002", # iaq_s
    "9003", # co2_eq
    "9004", # b_voc_eq
    "9005", # comp_t
    "9006", # comp_h
    "9007", # comp_g
    "9008", # gas
    "9009", # accuracy
]

CHARACTERISTIC_NAMES_TO_UUIDS = {charac_name: ble_sense_uuid(charac_id) for charac_name, charac_id in zip(SENSOR_NAME_LIST,ID_LIST)}
CHARACTERISTIC_UUIDS_TO_NAMES = {charac_uuid: charac_name for charac_name, charac_uuid in CHARACTERISTIC_NAMES_TO_UUIDS.items()}

# global variables
sensor_read = {charac_name: None for charac_name in SENSOR_NAME_LIST[1:]} # don't want device name
stop_notification = False
notification_toggle_needed = True
unpair_client = False
end_loop = False

# Setup global logging
name = "root"
now = datetime.now()
datetime_str = now.strftime("%Y_%m_%d_%H_%M_%S")
filepath_log = os.path.join(".","log")
Path(filepath_log).mkdir(parents=True,exist_ok=True)
filepath_log = os.path.join(filepath_log,f"nicla_{datetime_str}.log")
log_root = setup_logging(name,filepath_log)

# Setup files - Don't really like the position of this one
# File path - Might want to change this so that each file is created when a nicla is connected and reattached if connection is lost TODO
filepath_out = os.path.join(".","data")
Path(filepath_out).mkdir(parents=True,exist_ok=True)
filepath_out = os.path.join(filepath_out,f"nicla_{datetime_str}.dat")

async def connection_and_notification(client):
    """This function request connection with a device and notifications on specific characteristics.

    Parameters
    ----------
    client : BleakClient
        Client which exposes interesting characteristics and wants to be connected and allowed to send notifications.
    """
    log_root.info("Connecting to device...")
    try:
        await client.connect()
    except Exception as e:
        log_root.error(f"Exception: {e}")
        log_root.error("Connection failed!")
        return
    
    global unpair_client
    unpair_client = False
    
    try:
        log_root.info("Requesting notification on sensors...")
        await start_notifications(client)
        await listen_for_notifications(client)
    except Exception as e:
        log_root.error(f"Exception: {e}")
        log_root.error("Notification request failed!")
        log_root.error("Force disconnection...")
        await client.disconnect()

async def start_notifications(client):
    """This function starts notification for all the interesting characteristic in the client.

    Parameters
    ----------
    client : BleakClient
        Client to start notification from.
    """
    for sensor_name in SENSOR_NAME_LIST[1:]:
        await client.start_notify(CHARACTERISTIC_NAMES_TO_UUIDS[sensor_name],update_sensor_read)
    
    global notification_toggle_needed
    notification_toggle_needed = False
    log_root.info("The central will be notified from now on...")

async def stop_notifications(client):
    """This function stops notification for all the interesting characteristic in the client.

    Parameters
    ----------
    client : BleakClient
        Client to stop notification from.
    """
    for sensor_name in SENSOR_NAME_LIST[1:]:
        await client.stop_notify(CHARACTERISTIC_NAMES_TO_UUIDS[sensor_name])
    
    global notification_toggle_needed
    notification_toggle_needed = False
    log_root.info("The central will not be notified anymore...")

async def listen_for_notifications(client):
    """This function listens for notification from the peripheral and stop doing so only when a SIGINT signal is handled.

    Parameters
    ----------
    client : BleakClient
        Client to listen to.
    """
    global stop_notification, notification_toggle_needed
    stop_notification = False
    
    # setting up the hotkey to stop notifications
    listener = keyboard.GlobalHotKeys({
        '<ctrl>+<alt>+n': toggle_notifications_handler,
        '<ctrl>+<alt>+p': unpair_handler
    })
    listener.start()
    while client.is_connected and not unpair_client:
        if not stop_notification:
            if notification_toggle_needed: await start_notifications(client)
            log_root.info("Listening for notification... (<ctrl>+<alt>+n to toggle notifications, <ctrl>+<alt>+p to unpair)")
            await asyncio.sleep(1)
        else:
            if notification_toggle_needed: await stop_notifications(client)
            log_root.info("Not listening... (<ctrl>+<alt>+n to toggle notifications, <ctrl>+<alt>+p to unpair)")
            await asyncio.sleep(1)
    
    listener.stop()
    await client.disconnect()

def toggle_notifications_handler():
    """This function handles the <ctrl>+<alt>+n keys to toggle notifications
    """
    global stop_notification, notification_toggle_needed
    if (stop_notification):
        log_root.info('Forcefully starting notifications (<ctrl>+<alt>+n)!')
    else:
        log_root.info('Forcefully stopping notifications (<ctrl>+<alt>+n)!')
    
    stop_notification = not stop_notification
    notification_toggle_needed = True

def unpair_handler():
    """This function handles the <ctrl>+<alt>+p keys to unpair a device
    """
    log_root.info('Forcefully unpairing device (<ctrl>+<alt>+p)!')
    global unpair_client
    unpair_client = True

async def scan_devices():
    """This function scan for a device based on a filter.
    """
    device = None
    while device is None:
        log_root.info("Wait...")
        await asyncio.sleep(1)
        log_root.info("Searching for devices...")
        device = await BleakScanner.find_device_by_filter(match_known_addresses,timeout=TIMEOUT)

    log_root.info(f"Device found: {device.address}")
    client = BleakClient(device,disconnected_callback=on_disconnection)
    await connection_and_notification(client)
    return 0

async def on_disconnection(device):
    """This function handles the disconnection of a peripheral device.

    Parameters
    ----------
    device : BleakClient
        Device that was disconnected
    """
    if (unpair_client):
        log_root.info(f"Device {device.address} unpaired successfully!")
        log_root.info(f"Do you still want to scan for new devices? (y/n)")
        res = str.lower(input())
        if (res != "y"):
            global end_loop
            end_loop = True
    else: 
        log_root.info(f"Lost connection with {device.address}")
        await scan_devices()

def match_known_addresses(device,advertisement_data):
    """This function returns whether a device is in the list of known devices.

    Parameters
    ----------
    device : BleakClient
        Device to be checked.
    advertisement_data : AdvertisementData
        Data to be advertised.

    Returns
    -------
    bool
        True if device is known, False otherwise.
    """
    return device.address in KNOWN_ADDRESSES

async def update_sensor_read(sender,data):
    """This function updates the internal sensor value map and check whether it is filled. If so, calls log_sensors() and clear_sensors().

    Parameters
    ----------
    sender : BleakGATTCharacteristic
        BleakGATTCharacteristic that sent the data.
    data : bytearray
        Data read and to be stored.
    """
    sensor_name = CHARACTERISTIC_UUIDS_TO_NAMES[sender.uuid]
    log_root.info(f"Notification received from {sensor_name} sensor")

    global sensor_read
    if (sensor_read[sensor_name] is not None):
        log_root.info(f"Sensor {sensor_name} was already read!")

    sensor_read[sensor_name] = data

    if all(sensor_read[x] is not None for x in sensor_read.keys()):
        log_root.info("All sensor read, proceed to log...")
        log_sensors()
        clear_sensors()

def log_sensors():
    """This function logs obtained data both on stdout and on a file.
    """
    global sensor_read
    now = datetime.now()
    humidity = round(struct.unpack("f", sensor_read["humidity"])[0],2)
    temperature = round(struct.unpack("f", sensor_read["temperature"])[0],2)
    pressure = round(struct.unpack("f", sensor_read["pressure"])[0],2)
    iaq = struct.unpack("I", sensor_read["iaq"])[0]
    iaq_s = struct.unpack("I", sensor_read["iaq_s"])[0]
    co2_eq = struct.unpack("L", sensor_read["co2_eq"])[0]
    b_voc_eq = round(struct.unpack("f", sensor_read["b_voc_eq"])[0],4)
    comp_t = round(struct.unpack("f", sensor_read["comp_t"])[0],2)
    comp_h = round(struct.unpack("f", sensor_read["comp_h"])[0],2)
    comp_g = struct.unpack("L", sensor_read["comp_g"])[0]
    gas = round(struct.unpack("f", sensor_read["gas"])[0],2)
    accuracy = struct.unpack("H", sensor_read["accuracy"])[0]

    str_to_write = f"{now},{temperature},{humidity},{pressure},{iaq},{iaq_s},{co2_eq},{b_voc_eq},{comp_t},{comp_h},{comp_g},{gas},{accuracy}\n".replace(",","\t")

    log_root.info(f"Packet received: {str_to_write}")

    with open(filepath_out, "a") as fp:
        fp.write(str_to_write)
    
    log_root.info("Data written!")

def clear_sensors():
    """This function clears up the sensor map.
    """
    global sensor_read
    for k in sensor_read.keys():
        sensor_read[k] = None

def main():
    # Header
    with open(filepath_out, "w") as fp:
        fp.write("datetime\t" + "\t".join(SENSOR_NAME_LIST[1:]) + "\n")

    while not end_loop:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(scan_devices())
        except KeyboardInterrupt:
            log_root.info("Exiting on keyboard interrupt!")
            loop.close()
            sys.exit(0)
        except Exception as e:
            log_root.error("Something happened, restarting scan...")
        finally:
            loop.close()

if __name__ == "__main__":
    main()
