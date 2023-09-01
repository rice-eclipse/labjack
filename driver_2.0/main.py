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
from common_util import setup_socket, open_file, send_msg_to_operator, clear_drivers, stream_setup
import configparser
import socket
from threading import Lock
from labjack import ljm
import json

def main():
    # Get config info from peer file
    config = configparser.ConfigParser()
    config.read('config.ini')
    SAMPLE_RATE   = int(config["general"]["sample_rate"])
    READS_PER_SEC = int(config["general"]["reads_per_sec"])
    NUM_CHANNELS  = len(config["sensor_channel_mapping"].keys())

    # Setup socket for mission control
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    print("[I] Binding socket to " + str(config["general"]["HOST"])\
          + ":" + str(config["general"]["PORT"]))

    sock.bind((config["general"]["HOST"], int(config["general"]["PORT"])))

    print("[I] Waiting for connection request...")

    # Wait for connection
    filename = setup_socket(sock)
    sock.settimeout(.5)

    # JSONData = {}
    # JSONData['sensors'] = [0,0,0,0]
    # JSONData['states'] = [0,0,0,0]
    # JSONData['console'] = "data"
    # JSONData['timestamp'] = ""
    # JSONObj = json.dumps(JSONData)
    # sendStr = JSONObj.encode('UTF-8')
    # sock.sendall(sendStr)

    # Open data file
    fd, f = open_file(config, filename)

    with f, sock:
        close         = [0] # global shutdown indicator
        close_lock    = Lock()

        data_buf      = [[]] # special buffer for data sent to dashboard
        data_buf_lock = Lock()

        # Start necessary workers
        dash_sender   = DataSender(config, sock, close, close_lock, data_buf, data_buf_lock)
        dash_sender.start_thread()

        cmd_listener  = CmdListener(config, sock, close, close_lock, dash_sender)
        cmd_listener.start_thread()

        data_logger   = DataLogger(config, close, close_lock, data_buf, data_buf_lock, \
                                fd, dash_sender, SAMPLE_RATE, NUM_CHANNELS)

        # Open connection to LabJack device
        try: handle = ljm.openS("T7", "USB", "ANY")
        except Exception as e:
            send_msg_to_operator(dash_sender, "[E] During LabJack device setup" + str(e))
            # close(fd)
            ljm.close(handle)
            close[0] = 1
            raise e

        # Default all drivers (in case of improper shutdown)
        clear_drivers(config, handle)

        try: stream_setup(config, handle, NUM_CHANNELS, SAMPLE_RATE, READS_PER_SEC)
        except Exception as e:
            send_msg_to_operator(dash_sender, "[E] During stream setup: " + str(e))
            # close(fd)
            ljm.close(handle)
            close[0] = 1
            raise e

        dash_sender.handle  = handle
        cmd_listener.handle = handle
        data_logger.handle  = handle

        data_logger.start_reading() # Using main thread

        # Wait for shutdown condition
        dash_sender.join_thread()
        cmd_listener.join_thread()

        clear_drivers(config, handle)
        close(fd)
        ljm.close(handle)
        return

if __name__ == '__main__':
    print("\n===============================================================\
    \nData Acquisition and Remote Control for Eclipse Hybrid Engines\
    \nSoftware version 1.2.0\
    \n===============================================================")
    main()
    print("[I] Restarting program")