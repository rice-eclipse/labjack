import numpy as np
from datetime import datetime
from labjack import ljm
import csv
import json
import random
import os
import re
from socket import socket
from websockets import WebSocketServerProtocol
from typing import Union, List, Any
import time

def should_close(close, close_lock):
    with close_lock:
        if close[0] == 1:
            return True
    return False

def set_close(close, close_lock):
    with close_lock:
        close[0] = 1

def construct_message(buf_data: List[Any], states: List[int]):
    {
            "tcs": {
                "type": "SensorValue",
                "group_id": 0,
                "readings": [
                    {
                        "sensor_id": 0,
                        "reading": buf_data[6],
                        "time": {
                            "secs_since_epoch": int(time.time()),
                            "nanos_since_epoch": 0
                        }
                    },
                    {
                        "sensor_id": 1,
                        "reading": buf_data[7]
                    }
                ]
            },
            "pts": {
                "type": "SensorValue",
                "group_id": 1,
                "readings": [
                    {
                        "sensor_id": 0,
                        "reading": buf_data[10],
                    },
                    {
                        "sensor_id": 1,
                        "reading": buf_data[11]
                    },
                    {
                        "sensor_id": 2,
                        "reading": buf_data[12]
                    },
                    {
                        "sensor_id": 3,
                        "reading": buf_data[13]
                    }
                ]
            },
            "lcs": {
                "type": "SensorValue",
                "group_id": 2,
                "readings": [
                    {
                        "sensor_id": 0,
                        "reading": buf_data[0],
                    },
                ]
            },
            "driver": {
                "type": "DriverValue",
                "values": [bool(state) for state in states]
            }
        }

def send_msg_to_operator(dash_sender, msg):
    print(msg)
    dash_sender.add_work(lambda: dash_sender.msg_to_dash(msg))

def open_file(config):
    filename = next_test_data_filename("../data")
    f = open("../data/" + filename + ".csv", "x")
    fd = csv.writer(f)
    # Write in the initial column labels
    print("[I] Created new file in ../data/: ", filename)
    cols = ["Time (s)"]
    for sensors in config["sensor_channel_mapping"]:
        cols.append(sensors)
    fd.writerow(cols)
    return fd,f

def clear_drivers(config, handle):
    for driver in config["driver_mapping"]:
        ljm.eWriteName(handle, config["driver_mapping"][driver], 0)

def stream_setup(config, handle, num_channels, sample_rate, reads_per_sec):
    aScanListNames = list(config["sensor_channel_mapping"].values())
    aScanList = ljm.namesToAddresses(num_channels, aScanListNames)[0]
    scansPerRead = sample_rate // reads_per_sec

    reg_names = ["STREAM_TRIGGER_INDEX", "STREAM_CLOCK_SOURCE", "STREAM_RESOLUTION_INDEX", "STREAM_SETTLING_US"]
    reg_values = [0, 0, 0, 0]
    for chan in config["sensor_negative_channels"].keys():
        reg_names.append(config["sensor_channel_mapping"][chan] + "_NEGATIVE_CH")
        reg_values.append(int(config["sensor_negative_channels"][chan][3:]))
        reg_names.append(config["sensor_channel_mapping"][chan] + "_RANGE")
        reg_values.append(1)
        """
        Differential inputs (load cells and strain gauges) require amplification.
        Setting to "1" sets a gain of 10x- increasing this will improve the precision of these
        values, at the expense of sample rate.
        """
    numFrames = len(reg_names)
    ljm.eWriteNames(handle, numFrames, reg_names, reg_values)
    if (int(ljm.eStreamStart(handle, scansPerRead, num_channels, aScanList, sample_rate))\
        != sample_rate):
        raise Exception("Failed to configure LabJack data stream!")

def next_test_data_filename(directory):
    pattern = re.compile(r'test_data_(\d+)')
    files = os.listdir(directory)
    numbers = [int(match.group(1)) for file in files if (match := pattern.match(file))]
    if not numbers:
        highest_num = 0
    else:
        highest_num = max(numbers)    
    next_num = highest_num + 1
    return f"test_data_{next_num:03}"
