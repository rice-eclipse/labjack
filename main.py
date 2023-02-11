#Concept testing for interleaved logging, command handling, and dashboard
#data relay
#
#Spencer Darwall, ChatGPT,
#2/7/23
#

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

# Method to read config file settings
def read_config():
    config = configparser.ConfigParser()
    config.read('configurations.ini')
    return config

# Open socket connection    
def setup_socket():
    print("\nWaiting for incoming connection...")
    s.listen()
    conn, addr = s.accept()
    print("\nFound incoming connection")
    return conn, addr

# Send data points to dashboard
def command_from_dash(conn):
    while True:
        print("\nChecking for command from dashboard")
        ready = select.select([conn], [], [], 1)
        if ready[0]:
            cmd = conn.recv(1024).decode('utf-8')
            print("\nReceived command: " + str(cmd))
            if not cmd:
                return "00" 
            print(cmd) 
            if cmd[0] in config["driver_mapping"].keys() and cmd[0] != "6":
                ljm.eWriteName(handle,config["driver_mapping"][cmd[0]],cmd[1])
            elif cmd[0] == "6":
                #TODO ignition sequence helper call
                pass
            elif cmd[0] == "close":
                print("Closing connection")
                break
        else:
            print("\nNone found")
        time.sleep(.01)

# Receive commands from dashboard
def data_to_dash(conn,console,sensors = "",states = "",timestamp = ""):
    """
    Encode data into JSON object with the following fields:
    - console key:
        - 1: Succesful initial connection
        - 2: TODO
    TODO better error handling
    """
    JSONData = {}
    JSONData['sensors'] = sensors
    JSONData['timestamp'] = timestamp #int, sweep num
    JSONData['states'] = states
    JSONData['console'] = console
    JSONObj = json.dumps(JSONData)
    # with conn:  
    print("\nAttempting to send ",console,"to dashboard")
    try: 
        conn.sendall(JSONObj.encode('UTF-8'))
        print("\nSuccessfully sent: ",JSONObj.encode('UTF-8'))          
    except Exception as e:
        print("\nexception raised in data sent")
        print(e)
        print("Connection lost! Waiting for reconnect before resend")
        conn, addr = setup_socket()

# Log data to Raspberry Pi
def local_log(writer,sensors,sweepnum):
    timestamps = np.linspace(sweepnum,sweepnum + 1,SAMPLE_RATE)
    sensorsR = np.asarray(sensors).reshape(SAMPLE_RATE,NUM_SENSORS)
    write_data = np.column_stack((np.transpose(timestamps),sensorsR))
    writer.writerows(write_data)
    print("\nBatch " + str(sweepnum) + " logged to Pi")

def main(handle):
    info = ljm.getHandleInfo(handle)
    print("==============================================\
    \nStarting LabJack streaming, logging and command handling\
    \n==============================================")
    print("Opened LabJack with Device type: %i, Connection type: %i,\n"
        "Serial number: %i, IP address: %s, Port: %i,\nMax bytes per MB: %i" %
        (info[0], info[1], info[2], ljm.numberToIP(info[3]), info[4], info[5]))

    aScanListNames = list(config["sensor_mapping"].values())
    filename = config["general"]["filename"]
    os.remove(filename + ".csv") #rep w new filename each time
    file = open(filename + ".csv", "x")
    writer = csv.writer(file)
    writer.writerow(["Time (s)","LC1","LC2","LC3","LC4","SG1","SG2","PT1",\
    "PT2","PT3","PT4","TC1","TC2","TC3","TC4"]) #make ms
    aScanList = ljm.namesToAddresses(NUM_SENSORS, aScanListNames)[0]
    # print(ljm.namesToAddresses(NUM_SENSORS, aScanListNames))
    scanRate = SAMPLE_RATE
    scansPerRead = scanRate#check
    conn,addr = setup_socket()
    # data_to_dash(conn,"1")
    dashlistener = Thread(target = command_from_dash, args = (conn, ))
    dashlistener.start()
    try:
        # Ensure triggered stream is disabled.
        ljm.eWriteName(handle, "STREAM_TRIGGER_INDEX", 0)

        # Enabling internally-clocked stream.
        ljm.eWriteName(handle, "STREAM_CLOCK_SOURCE", 0)

        # All negative channels are single-ended, AIN0 range is +/-10V,
        # stream settling is 0 (default) and stream resolution index
        # is 0 (default).
        aNames = ["AIN_ALL_NEGATIVE_CH", "AIN0_RANGE",
            "STREAM_SETTLING_US", "STREAM_RESOLUTION_INDEX"]
        aValues = [ljm.constants.GND, 10.0, 0, 0]
        # Write the analog inputs' negative channels (when applicable), ranges,
        # stream settling time and stream resolution configuration.
        numFrames = len(aNames)
        ljm.eWriteNames(handle, numFrames, aNames, aValues)
        scanRate = ljm.eStreamStart(handle, scansPerRead, NUM_SENSORS, aScanList, scanRate)
        print("\nStream started with a scan rate of %0.0f Hz." % scanRate)
        start = datetime.now()
        totScans = 0
        totSkip = 0  # Total skipped samples
        i = 0
        #Loop until exception or stop command
        while True:
            ret = ljm.eStreamRead(handle)
            aData = ret[0]
            print("\nCurrent batch size: ",len(aData))
            scans = len(aData) / NUM_SENSORS
            totScans += scans

            # Count the skipped samples which are indicated by -9999 values. Missed
            # samples occur after a device's stream buffer overflows and are
            # reported after auto-recover mode ends.
            curSkip = aData.count(-9999.0)
            totSkip += curSkip
            print("\nBatch number: %i" % i)
            sendData = ""
            for j in range(0, NUM_SENSORS - 1):
                sendData += str(aData[j]) + ","
            sendData += str(aData[NUM_SENSORS - 1])
            print("  Scans Skipped = %0.0f, Scan Backlogs: Device = %i, LJM = "
                "%i" % (curSkip/NUM_SENSORS, ret[1], ret[2]))
            i += 1
            #writing pin values corresponding to command received
            # data_to_dash(conn,"test")
            states = []
            #reading current valve pin states
            for driver in config["driver_mapping"].keys():
                states.append(ljm.eReadName(handle,config["driver_mapping"][driver]))
            #write values from this sweep to SD card
            local_log(writer,aData,i)
            data_to_dash(conn,"data",sendData,states)
        end = datetime.now()
        print("\nTotal scans: %i" % (totScans))
        tt = (end - start).seconds + float((end - start).microseconds) / 1000000
        print("Time taken: %f seconds" % (tt))
        print("LJM Scan Rate: %f scans/second" % (scanRate))
        print("Timed Scan Rate: %f scans/second" % (totScans / tt))
        print("Timed Sample Rate: %f samples/second" % (totScans * NUM_SENSORS / tt))
        print("Skipped scans: %0.0f" % (totSkip / NUM_SENSORS))
    except ljm.LJMError:
        ljme = sys.exc_info()[1]
        print(ljme)
    except Exception:
        e = sys.exc_info()[1]
        print(e)

if __name__ == '__main__':
    config = read_config()
    HOST = config["general"]["HOST"]
    PORT = int(config["general"]["PORT"])
    SAMPLE_RATE = int(config["general"]["SAMPLE_RATE"])
    NUM_SENSORS = int(config["general"]["NUM_SENSORS"])
    NUM_DRIVERS = int(config["general"]["NUM_DRIVERS"])
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print("\nBinding socket to: " + str(HOST) + ":" + str(PORT))
    s.bind((HOST,PORT))
    handle = ljm.openS("T7", "USB", "ANY")
    try:
        main(handle)
        ljm.eStreamStop(handle)
        print("\nStream ended.")
    except ljm.LJMError:
        ljme = sys.exc_info()[1]
        print(ljme)
    except KeyboardInterrupt:
        ljm.close(handle)
        try:
            sys.exit(130)
        except:
            os._exit(130)
    except Exception:
        e = sys.exc_info()[1]
        print(e)
