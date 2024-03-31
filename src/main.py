"""
Data Acquisition and Remote Control for Eclipse Hybrid Engines
Spencer Darwall, Avionics & Software Lead '22-23

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

def main():
    # Get config info from peer file
    config = configparser.ConfigParser()
    config.read('config.ini')
    SAMPLE_RATE   = int(config["general"]["sample_rate"])
    READS_PER_SEC = int(config["general"]["reads_per_sec"])
    NUM_CHANNELS  = len(config["sensor_channel_mapping"].keys())

    # Swap over the configs to be loaded from the JSON config.json file.
    # DataLogger and potentially others use fd, which is a csv.writer object.
    # I'm unsure how the following code could affect this.
    
    # config_file = open("C:\Z-Personal\Rice Eclipse\labjack\src\config.json")
    # config = json.load(config_file)
    # config_file.close()

    # SAMPLE_RATE = int(config["general"]["sample_rate"])
    # READS_PER_SEC = int(config["general"]["reads_per_sec"])
    # NUM_CHANNELS = len(config["sensor_channel_mapping"].keys())

    # print('Sample Rate', SAMPLE_RATE)
    # print('Reads Per Sec', READS_PER_SEC)
    # print('Number of Channels', NUM_CHANNELS)

    # Setup socket for mission control
    setup_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    setup_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    print("[I] Binding socket to " + str(config["general"]["HOST"])\
          + ":" + str(config["general"]["PORT"]))

    setup_sock.bind((config["general"]["HOST"], int(config["general"]["PORT"])))

    # Wait for connection
    sock = setup_socket(setup_sock)
    setup_sock.settimeout(.5)

    JSONData = {}
    JSONData['sensors'] = [0,0,0,0]
    JSONData['states'] = [0,0,0,0]
    JSONData['console'] = "data"
    JSONData['timestamp'] = ""
    JSONObj = json.dumps(JSONData)
    sendStr = JSONObj.encode('UTF-8')
    sock.sendall(sendStr)

    fd, f = open_file(config)
    try:
        # Start necessary workers
        close         = [0] # global shutdown indicator
        close_lock    = Lock()
        data_buf      = [[]] # special buffer for data sent to dashboard
        data_buf_lock = Lock()

        dash_sender = DataSender(config, setup_sock, sock, close, close_lock, data_buf, data_buf_lock)
        dash_sender.start_thread()

        cmd_listener = CmdListener(config, sock, close, close_lock, dash_sender)
        cmd_listener.start_thread()
        dash_sender.cmd_listener = cmd_listener

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
    main()
    print("[I] Stopping program")
