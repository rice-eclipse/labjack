"""
Data Acquisition and Remote Control for Eclipse Hybrid Engines
Spencer Darwall, Avionics & Software Lead '22-23
Ian Rundle, President '23-24

Code interfaces with LabJack device hardware via LJM Library. The LabJack
has input pins for each sensor and output pins for each driver- this script logs
collected data, periodically sends some fraction of it to the dashbaord, sets valve
states when instructed by the dashboard, and has lightning-fast responses to unsafe
engine conditions. Intended for use on Raspberry Pi, connected to a LabJack T7 via USB.

Ensure that config.ini is located in this sub-directory.

For documentation on the overall setup:
https://docs.google.com/document/d/1y7f7A9FtFfV9nHa74x1uJAnZVh4cjQFKVG3zE4jUQEY/edit?usp=sharing

For more info about this software:
https://github.com/rice-eclipse/labjack

For more info about the LabJack T7 and its' acessories:
https://labjack.com/pages/support?doc=%2Fdatasheets%2Ft-series-datasheet%2F

Run-on-startup config at: /home/eclipsepi/.config/systemd/user/labjack.service
"""

from data_to_dash import DataSender
from logging_and_eshutdown import DataLogger
from cmd_from_dash import CmdListener
from common_util import setup_socket, open_file, send_msg_to_operator, clear_drivers, stream_setup, set_close
import configparser
import socket
from threading import Lock
from labjack import ljm
import json
import time
from datetime import datetime
from websockets.asyncio.server import serve, Server, ServerConnection
import asyncio

async def main():
    # Get config info from peer file
    config = configparser.ConfigParser()
    config.read('config.ini')
    SAMPLE_RATE   = int(config["general"]["sample_rate"])
    READS_PER_SEC = int(config["general"]["reads_per_sec"])
    NUM_CHANNELS  = len(config["sensor_channel_mapping"].keys())

    host, port = config["general"]["HOST"], int(config["general"]["PORT"])

    if not bool(config["general"]["websocket"]):
        print(f"[E] Non-websocket communication temporarily disabled. Do not use this version of the code if you don't want websockets!")
        exit(1)

    print(f"[I] Connecting to websocket at {host}:{port}")

    fd, f = open_file(config)
    try:

        dash_sender = DataSender(config)
        await dash_sender.start_sending()

        cmd_listener = CmdListener(config)

        async def ws_handle(websocket: ServerConnection, path: str):
            await dash_sender.add_client(websocket)
            await cmd_listener.recv_cmd(websocket, path)
        
        server: Server = await serve(ws_handle, config["general"]["HOST"], config["general"]["PORT"])
        
        # Open connection to LabJack device

        data_logger = DataLogger(config, fd, dash_sender, SAMPLE_RATE, NUM_CHANNELS)
        handle = ljm.openS("T7", "USB", "ANY")

        # Default all drivers (in case of improper shutdown)
        clear_drivers(config, handle)
        stream_setup(config, handle, NUM_CHANNELS, SAMPLE_RATE, READS_PER_SEC)

        dash_sender.handle  = handle
        cmd_listener.handle = handle
        data_logger.handle  = handle
        await data_logger.start_reading() # Using main thread

        await server.serve_forever()

        # Wait for shutdown condition
    except (Exception, KeyboardInterrupt) as e:
        print("[E] Exception: " + str(e))
        try: clear_drivers(config, handle)
        except: pass
        ljm.eStreamStop(handle)
        ljm.close(handle)
        raise e

    try: clear_drivers(config, handle)
    except: pass
    ljm.eStreamStop(handle)
    ljm.close(handle)
    return

if __name__ == '__main__':
    print("\n===============================================================\
    \nData Acquisition and Remote Control for Eclipse Hybrid Engines\
    \nSoftware version 1.2.0\
    \n===============================================================")
    asyncio.run(main())
    print("[I] Stopping program")
