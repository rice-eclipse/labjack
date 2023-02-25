#Main driver code for Raspberry Pi3
#
#Multithreaded logging, command listening/handling, and dashbaord uploading
#Configured by configurations.ini
#
#Spencer Darwall
#2/21/23

from datetime import datetime
from labjack import ljm
import sys
import time
import csv
import os
import socket
import select
import numpy as np
import configparser
import json
from threading import Thread
from threading import Lock

# Read config file settings
def read_config():
    config = configparser.ConfigParser()
    config.read('configurations.ini')
    return config

# Configure socket connection    
def setup_socket():
    print("\nWaiting for connection request...")
    s.listen()
    global conn
    conn, _ = s.accept()

# Create file writer
def open_file():
    filename = config["general"]["filename"]
    os.remove(filename + ".csv") #TODO ensure new filename each run (get timestamp from dash?)
    file = open(filename + ".csv", "x")
    writer = csv.writer(file)
    writer.writerow(["Time (s)","LC1","LC2","LC3","LC4","SG1","SG2","PT1",\
    "PT2","PT3","PT4","TC1","TC2","TC3","TC4"])
    return writer

# Dashboard listener 
def command_from_dash(closeLock):
    #TODO proper error handling
    global close
    while True:
        try:
            ready = select.select([conn], [], [], .1)
            if ready[0]:
                ready = ([], [], [])
                cmd = conn.recv(2048).decode('utf-8')
                decodeCmd = json.loads(cmd)
                if not decodeCmd:
                    pass
                print("\nReceived command: " + str(cmd))
                # Check if command field is set_valve: set "driver" field to "value"
                if decodeCmd["command"] == "set_valve":
                    # ljm.eWriteName(handle,config["driver_mapping"][str(decodeCmd["driver"])],decodeCmd["value"])
                    ljm.eWriteName(handle,"EIO0",decodeCmd["value"])                
                    print("Successful pin write!")
                # Check if command is ignition
                elif decodeCmd["command"] == "ignition":
                    #TODO ignition sequence helper call
                    print("ignition command received")
                    pass
                # Check if command is "close"
                elif decodeCmd["command"] == "close":
                    print("Stopping command listening")
                    closeLock.acquire()
                    close = 1
                    closeLock.release()
                    break
        except:
            # If error, wait for data_to_dash thread to throw socket exception
            # and update conn with new values
            pass

# Dashboard sender
def data_to_dash(bufLock,closeLock,console = "",states = "",timestamp = ""):
    while True: 
        global conn
        states = []
        # Reading current driver pin states
        # for driver in drivers: #TODO doesn't work for some reason
        #     states.append(str(ljm.eReadName(handle,config["driver_mapping"][driver])))
        states.append(ljm.eReadName(handle,"EIO1"))
        print("states",states)
        JSONData = {}
        # Access to dataBuf from main() thread
        if bufLock.acquire(timeout = .01):
            JSONData['sensors'] = dataBuf[0]
            bufLock.release()
        JSONData['timestamp'] = timestamp
        JSONData['states'] = states
        JSONData['console'] = console
        JSONObj = json.dumps(JSONData)  
        print(JSONData['sensors'])
        try: 
            sendStr = JSONObj.encode('UTF-8')
            conn.send(len(sendStr).to_bytes(2,"big"))
            conn.sendall(sendStr)
        except:
            print("Connection issue! Waiting for reconnect before resend")
            setup_socket()
            pass
        if closeLock.acquire(timeout = .01):
            close_hold = close
            closeLock.release()
            if close_hold == 1:
                print("Stopped command sending")
                break
        else:
            print("issue obtaining close lock")
        # Sleep for arbitrary amount of time (default 1s)
        time.sleep(int(config["general"]["dash_send_delay_ms"]) / 1000)

# Log data to Raspberry Pi
def data_log(writer,sensors,sweepnum):
    timestamps = np.linspace(sweepnum - 1,sweepnum-(1/SAMPLE_RATE),SAMPLE_RATE)
    sensorsR = np.asarray(sensors).reshape(SAMPLE_RATE,NUM_SENSORS)
    write_data = np.column_stack((np.transpose(timestamps),sensorsR))
    writer.writerows(write_data)

def main(handle):
    info = ljm.getHandleInfo(handle)
    print("Opened LabJack with Device type: %i, Connection type: %i,\n"
        "Serial number: %i, IP address: %s, Port: %i,\nMax bytes per MB: %i" %
        (info[0], info[1], info[2], ljm.numberToIP(info[3]), info[4], info[5]))
    print("===============================================================")
    writer = open_file()
    aScanListNames = list(config["sensor_channel_mapping"].values())
    aScanList = ljm.namesToAddresses(NUM_SENSORS, aScanListNames)[0]
    print(aScanList)
    scanRate = SAMPLE_RATE
    scansPerRead = scanRate
    setup_socket()
    # Locks for data race prevention
    bufLock = Lock()
    closeLock = Lock()
    global dataBuf
    global close
    # Buffer for data slices for dashboard send
    dataBuf = [[]]
    # Value used to communicate stop-command status between threads
    close = 0
    dataSender = Thread(target = data_to_dash, args = (bufLock,closeLock,"data", ))
    dataSender.start()
    dashListener = Thread(target = command_from_dash, args = (closeLock,))
    dashListener.start()
    # try:
    # Ensure triggered stream is disabled.
    ljm.eWriteName(handle, "STREAM_TRIGGER_INDEX", 0)
    # Enabling internally-clocked stream.
    ljm.eWriteName(handle, "STREAM_CLOCK_SOURCE", 0)
    names = []
    values = []
    # for chan in config["sensor_channel_mapping"].keys():
    #     if chan in config["sensor_negative_channels"].keys():
    #         names.append(config["sensor_channel_mapping"][chan] + "_NEGATIVE_CH")
    #         values.append(int(config["sensor_negative_channels"][chan][3:]))
    #         names.append(config["sensor_channel_mapping"][chan] + "_RANGE")
    #         values.append(1) # Sets gain of instrumentation amplifiers to 100x
    #     # else:
    #         # names.append(config["sensor_channel_mapping"][chan] + "_RANGE")
    #         # values.append(10) # Sets gain of instrumentation amplifiers to 100x
    # Assign negative channels for load cells and strain gauges, set inamp gain setting
    for chan in config["sensor_negative_channels"].keys():
        names.append(config["sensor_channel_mapping"][chan] + "_NEGATIVE_CH")
        values.append(int(config["sensor_negative_channels"][chan][3:]))
        names.append(config["sensor_channel_mapping"][chan] + "_RANGE")
        values.append(1) # Sets gain of instrumentation amplifiers to 100x
    aNames = names + ["STREAM_RESOLUTION_INDEX","STREAM_SETTLING_US"]
    aValues = values + [0,0]
    print("aNames: ",aNames,"aValues: ",aValues)
    numFrames = len(aNames)
    print(numFrames)
    ljm.eWriteNames(handle, numFrames, aNames, aValues)
    print("number of sensors",NUM_SENSORS,"scan list",aScanList,"scans per read",scansPerRead,"scanrate",scanRate)
    scanRate = ljm.eStreamStart(handle, scansPerRead, NUM_SENSORS, aScanList, scanRate)
    totScans = 0
    totSkip = 0  # Total skipped samples
    i = 0
    # Separate thread for sending to dashboard
    # Loop until exception or stop command
    while True:
        ret = ljm.eStreamRead(handle)
        aData = ret[0]
        scans = len(aData) / NUM_SENSORS
        totScans += scans
        # Count the skipped samples which are indicated by -9999 values. Missed
        # samples occur after a device's stream buffer overflows and are
        # reported after auto-recover mode ends. 
        curSkip = aData.count(-9999.0)
        totSkip += curSkip
        print("\nBatch number: %i" % i)
        # Try to write to the buffer or continuing without
        if bufLock.acquire(timeout = .005):
            dataBuf[0] = []
            for j in range(0, NUM_SENSORS):
                dataBuf[0].append(float(aData[j]))
            bufLock.release()
        else: 
            print("issue obtaining buflock")    
        # Skipped scans indicate program struggling to keep up
        print("  Scans Skipped = %0.0f, Scan Backlogs: Device = %i, LJM = "
            "%i" % (curSkip/NUM_SENSORS, ret[1], ret[2]))
        i += 1
        # Write values from this sweep to SD card
        data_log(writer,aData,i)
        # Check close condition
        if closeLock.acquire(timeout = .01):
            closeCheck = close
            closeLock.release()
            if closeCheck == 1:
                dashListener.join()
                dataSender.join()
                break
    #     ljm.eStreamStop(handle)
    #     ljm.close(handle)
    #     s.close()
    # except ljm.LJMError:
    #     ljme = sys.exc_info()[1]
    #     print(ljme)
    #     s.close()
    # except Exception:
    #     e = sys.exc_info()[1]
    #     ljm.eStreamStop(handle)
    #     ljm.close(handle)
    #     s.close()
    #     print(e)

if __name__ == '__main__':
    print("===============================================================\
    \nStarting LabJack streaming, logging and remote command handling\
    \n===============================================================")
    config = read_config()
    HOST = config["general"]["HOST"]
    PORT = int(config["general"]["PORT"])
    SAMPLE_RATE = int(config["general"]["SAMPLE_RATE"])
    NUM_SENSORS = len(config["sensor_channel_mapping"].keys())
    NUM_DRIVERS = int(config["general"]["NUM_DRIVERS"])
    drivers = list(config["driver_mapping"].keys())
    # Open and bind socket
    try: 
        handle = ljm.openS("T7", "USB", "ANY")
    except:
        print("Can't connect to LabJack device") 
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("\nBinding socket to: " + str(HOST) + ":" + str(PORT))
        s.bind((HOST,PORT))
        main(handle)
        print("\nShutting down...")
    except ljm.LJMError:
        ljme = sys.exc_info()[1]
        print(ljme)
    except KeyboardInterrupt:
        print("Keyboard stop")
        ljm.close(handle)
        s.close()
        try:
            sys.exit(130)
        except:
            os._exit(130)
    except Exception:
        e = sys.exc_info()[1]
        s.close()
        print(e)
