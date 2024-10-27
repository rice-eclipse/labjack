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
import websockets
import asyncio

async def main():
    # Get config info from peer file
    config = configparser.ConfigParser()
    config.read('config.ini')
    SAMPLE_RATE   = int(config["general"]["sample_rate"])
    READS_PER_SEC = int(config["general"]["reads_per_sec"])
    NUM_CHANNELS  = len(config["sensor_channel_mapping"].keys())

    # Setup socket for mission control
    host, port = config["general"]["HOST"], int(config["general"]["PORT"])

    if not bool(config["general"]["websocket"]):
        print(f"[E] Non-websocket communication temporarily disabled. Do not use this version of the code if you don't want websockets!")
        exit(1)

    # async def recv_fn(websocket: websockets.WebSocketServerProtocol, path: str):
    #     async for message in websocket:
    #         await websocket.send(message)
        
    # setup_sock = await websockets.serve(recv_fn, config["general"]["HOST"], int(config["general"]["PORT"])).__aenter__()
    print(f"[I] Connecting to websocket at {host}:{port}")

    fd, f = open_file(config)
    try:
        # Start necessary workers
        close         = [0] # global shutdown indicator
        close_lock    = Lock()
        data_buf      = [[]] # special buffer for data sent to dashboard
        data_buf_lock = Lock()

        dash_sender = DataSender(config, close, close_lock, data_buf, data_buf_lock)
        dash_sender.start_thread()

        cmd_listener = CmdListener(config, close, close_lock, dash_sender)
        cmd_listener.start_thread()
        dash_sender.cmd_listener = cmd_listener

        async def handle(websocket: websockets.WebSocketServerProtocol, path: str):
            await dash_sender.add_client(websocket)
            await cmd_listener.handle(websocket, path)
        
        sock = await websockets.serve(handle, config["general"]["HOST"], config["general"]["PORT"]).__aenter__()
        print("server started")
        
        # Open connection to LabJack device

        data_logger = DataLogger(config, close, close_lock, data_buf, data_buf_lock, \
                                fd, dash_sender, SAMPLE_RATE, NUM_CHANNELS)
        handle = ljm.openS("T7", "USB", "ANY")

        # Default all drivers (in case of improper shutdown)
        clear_drivers(config, handle)
        stream_setup(config, handle, NUM_CHANNELS, SAMPLE_RATE, READS_PER_SEC)

        dash_sender.handle  = handle
        cmd_listener.handle = handle
        data_logger.handle  = handle
        data_logger.start_reading() # Using main thread

        # Wait for shutdown condition
    except (Exception, KeyboardInterrupt) as e:
        print("[E] Exception: " + str(e))
        set_close(close, close_lock)
        try: clear_drivers(config, handle)
        except: pass
        ljm.eStreamStop(handle)
        ljm.close(handle)
        sock.close()
        dash_sender.join_thread()
        cmd_listener.join_thread()
        raise e

    try: clear_drivers(config, handle)
    except: pass
    ljm.eStreamStop(handle)
    ljm.close(handle)
    sock.close()
    dash_sender.join_thread()
    cmd_listener.join_thread()
    return

if __name__ == '__main__':
    print("\n===============================================================\
    \nData Acquisition and Remote Control for Eclipse Hybrid Engines\
    \nSoftware version 1.2.0\
    \n===============================================================")
    asyncio.run(main())
    print("[I] Stopping program")
