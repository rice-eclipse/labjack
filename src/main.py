"""
Data Acquisition and Remote Control for Eclipse Hybrid Engines
Spencer Darwall, Avionics & Software Lead '22-23

Code interfaces with LabJack device hardware via LJM Library. The LabJack 
has input pins for each sensor and output pins for each driver- this script logs
collected data, periodically sends some fraction of it to the dashbaord, sets valve 
states when instructed by the dashboard, and has lightning-fast responses to unsafe 
engine conditions. Intended for use on Raspberry Pi, connected to a LabJack T7 via USB.

Ensure that config.ini is located in this sub-directory.

For more info about this software:
https://github.com/rice-eclipse/labjack

For more info about the LabJack T7 and its' acessories:
https://labjack.com/pages/support?doc=%2Fdatasheets%2Ft-series-datasheet%2F
"""

from labjack import ljm
import sys
import time
import csv
import os
import socket
import numpy as np
import configparser
import json
from threading import Thread
from threading import Lock

"""
Reads relevant configuration settings from config.ini,
which should be located in the same sub-directory
"""
def read_config():
    global config
    config = configparser.ConfigParser()
    config.read('configurations.ini')
    pass

"""
Connects TCP socket between local and dashboard. Called during setup,
and again whenever connection is lost. In both cases, will block the thread 
that calls, on s.listen(), until dashboard sends connection request or 
exception is thrown. 
Sets global variable "conn", a socket object used throughout the program,
"""
def connect_socket():
    print("\n[INFO] Waiting for connection request...\n")
    sock.listen()
    global conn
    conn, _ = sock.accept()
    pass

"""
File writer for collected data.

    Returns:
        fw: writer object to csv file where data is saved
"""
def open_file():
    filename = config["general"]["filename"]
    os.remove(filename + ".csv") #TODO ensure new filename each run (get timestamp from dash?)
    f = open(filename + ".csv", "x")
    fw = csv.writer(f)
    # Write in the initial column labels
    print("\n[INFO] Created new file %s",filename)
    fw.writerow(["Time (s)","LC1","LC2","LC3","LC4","SG1","SG2","PT1",\
    "PT2","PT3","PT4","TC1","TC2","TC3","TC4"]) #TODO format according to order in configurations.ini
    return fw

"""
Dashboard command listener, and handler.
Messages are received as encoded JSON objects, with "command" fields
denoting the desired action, and additional fields for associated
tasks. 

    Setting drivers:
        command field is "set_valve"
        Looks for "driver" field for driver to set (int 0-5)
        Looks for "value" field for desired value (int 0,1)
        Sets driver accordingly

    Ignition:
        command field is "ignition"
        Handles ignition sequence as defined by config file

    Close:
        command field is "close"
        Sets global variable to 1, indicating to other threads to 
        shut down. 
        Breaks from infinite loop and closes

"""
def command_from_dash(close_lock,close):
    while True:
        try:
            # Receive up to 2048 bytes, in the utf-8 format
            cmd = conn.recv(2048).decode('utf-8')
            # Unpack into JSON object
            decodeCmd = json.loads(cmd)
            if not decodeCmd: pass
            print("\n[INFO] Received command: " + str(cmd))
            # Check if command field is set_valve: set "driver" field to "value"
            if decodeCmd["command"] == "set_valve":
                # Carry out command on hardware
                ljm.eWriteName(handle,config["driver_mapping"][str(decodeCmd["driver"])],decodeCmd["value"])
                print("\n[INFO] Set driver %d to value of %d"\
                    ,config["driver_mapping"][str(decodeCmd["driver"])],decodeCmd["value"])
            # Check if command is ignition
            elif decodeCmd["command"] == "ignition":
                #TODO ignition sequence helper call
                print("\n[INFO] Ignition command received...")
                pass
            # Check if command is "close"
            elif decodeCmd["command"] == "close":
                print("\n[INFO] Stopping command listening...")
                with close_lock.acquire():
                    close = 1
                break
        except socket.error:
            print("\n[WARN] Invalid dashboard connection")
            """
            In the event of an issue with the socket, the issue is almost certainly
            that the connection has been lost. Since there are two threads that rely
            on an valid connection, only one needs to regain it for both to work. 
            data_to_dash() does this, so command_from_dash() should do nothing 
            and then try again.
            """
            time.sleep(.5)
            pass

"""
Dashboard data sender 
Sends, with frequency defined in config.ini, packets to dashboard.
Packets are sent as encoded JSON objects, with the following fields:

    sensors:
        Array of floats, representing converted sensor values

    states: 
        Array of integers, representing driver states: 1 = ON, 0 = OFF

    console:
        String, representing arbitrary message. Packets sent from this
        function contain "data" here. Others, such as errors, will have 
        something else
"""
def data_to_dash(handle,data_buf,locks):
    while True: 
        states = []
        JSONData = {}
        # Reading current driver pin states
        statebin = format(int(ljm.eReadName(handle,"EIO_STATE")),'05b')
        for char in statebin:
            states.append(int(char))
        # Access to dataBuf from main() thread
        with locks[buf_lock].acquire(timeout = .01):
            JSONData['sensors'] = convert_vals(np.asarray(data_buf[0]))
        JSONData['states'] = states[::-1]
        JSONData['console'] = "data"
        JSONObj = json.dumps(JSONData)  
        try: 
            sendStr = JSONObj.encode('UTF-8')
            conn.send(len(sendStr).to_bytes(2,"big"))
            conn.sendall(sendStr)
        except socket.error:
            print("\n[WARN] Connection issue! Waiting for reconnect before resend")
            """
            If the connection is invalid, attempts to repair via connect_socket()
            which blocks until connection is fixed or exception is thrown
            """
            connect_socket()
            pass
        with locks[close_lock].acquire(timeout = .01):
            if close == 1:
                print("\n[INFO] Stopped command sending...")
                break
        time.sleep(int(config["general"]["dash_send_delay_ms"]) / 1000)

def msg_to_dash(sock_lock,msg):
    with sock_lock:
        JSONData = {}
        JSONData['sensors'] = []
        JSONData['states'] = []
        JSONData['console'] = msg
        JSONObj = json.dumps(JSONData)  
        try: 
            sendStr = JSONObj.encode('UTF-8')
            conn.send(len(sendStr).to_bytes(2,"big"))
            conn.sendall(sendStr)
        except socket.error:
            print("\n[WARN] Failed to send console msg: %s !",msg)
            pass

"""
Converts raw voltages into readable sensor values (PSI, degrees, lb, etc...)
Each sensor conversion is defined by an offset (y-intercept) and scale factor
(slope) located for each sensor in config.ini. These values should be recalibrated 
regularly.

    Parameters: 
        sensors_vals: Array of sensor voltages; can be a single point in time 
        (shape of array is 1) or many (shape of array is 2)

    Returns: 
        a list containing the converted values 
"""
def convert_vals(sensor_vals):
    if sensor_vals.size == 0: return []
    n_sensors = sensor_vals.copy()
    for i, chan in enumerate(list(config['sensor_channel_mapping'].keys())):
        # Iterating through the sensors and treating each column of data accordingly
        if chan[:6] == "thermo":
            if len(n_sensors.shape) == 2:
                n_sensors[:,i] = np.round((sensor_vals[:,i] * config['conversion']['thermo_scale']\
                     + config['conversion']['thermo_offset']))
            elif len(n_sensors.shape) == 1:
                n_sensors[i] = np.round((sensor_vals[i] * config['conversion']['thermo_scale']\
                     + config['conversion']['thermo_offset']))
        elif chan[:4] ==  "load":
            if len(n_sensors.shape) == 2:
                n_sensors[:,i] = np.round((sensor_vals[:,i] * config['conversion']['big_lc_scale']\
                     + config['conversion']['big_lc_offset']))            
            elif len(n_sensors.shape) == 1:
                n_sensors[i] = np.round((sensor_vals[i] * config['conversion']['big_lc_scale']\
                     + config['conversion']['big_lc_offset']))
        elif chan[:4] ==  "pres":
            if len(n_sensors.shape) == 2:
                n_sensors[:,i] = np.round((sensor_vals[:,i] * config['conversion']['pres_scale']\
                     + config['conversion']['pres_offset']))                
            elif len(n_sensors.shape) == 1: 
                n_sensors[i] = np.round((sensor_vals[i] * config['conversion']['pres_scale']\
                     + config['conversion']['pres_offset']))
    return n_sensors.tolist()

"""
File logger for collected data
Takes writer object, sensor data and the sweep number to extrapolate timestamps
and write data into the file

    Parameters:
        fw: file writer 
        sensors: array with data from sensors 
        sweepnum: sample number for timestamp extrapolation
        constants: dictionary with program constants
"""
def data_log(fw,sensors,sweepnum,constants):
    timestamps = np.linspace((sweepnum - 1)/constants[READS_PER_SEC],(sweepnum-(1/constants[SAMPLE_RATE]))\
        /constants[READS_PER_SEC],constants[SAMPLE_RATE] // constants[READS_PER_SEC])
    sensorsR = np.asarray(sensors).reshape(constants[SAMPLE_RATE] // constants[READS_PER_SEC],constants[NUM_CHANNELS])
    write_data = np.column_stack((np.transpose(timestamps),vconv(sensorsR)))
    fw.writerows(write_data)

"""
Setup LabJack sensor stream by writing config values to relevant device registers
This involves ensuring the stream is clocked intoernally, along with setting the 
resolution and settling time.
Differential sensor inputs also requires special handling, including
negative channel setting and analog signal amplification.

    Parameters:
        handle: object for connection to LabJack device hardware
"""
def stream_setup(handle):
    reg_names = ["STREAM_TRIGGER_INDEX","STEAM_CLOCK_SOURCE","STREAM_RESOLUTION_INDEX","STREAM_SETTLING_US"]
    reg_values = [0,0,0,0]
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
    pass

'''
Indefinitely collects and handles data from sensors
Notifies user if values are being skipped, places subset of values in
array for other threads to access, and logs all collected values to file.

    Parameters:
        handle: object for connection to LabJack device hardware
        fw: file writer object
        close: global variable indicating whether close command has been sent
        data_buf: array containing recent subset of collected values to send to dash
        constants: dictionary with program constants
        locks: dictionary with shared data structure access locks
'''
def collect_data(handle,fw,close,data_buf,constants,locks):
    i = 0
    print("\n[INFO] Starting data collection...")
    # Spawn two additional threads for dashboard sending and receiving
    try:
        data_sender = Thread(target = data_to_dash, args = (handle,data_buf,locks,close ))
        data_sender.start()
        dash_listener = Thread(target = command_from_dash, args = (locks[close_lock],close))
        dash_listener.start()
    except Exception as e:
        print("\n[ERR] Got exception while attempting to start dash sender and/or dash listener:"\
             + str(e))
        msg_to_dash(locks[sock_lock],"\nERROR: Got exception while attempting to start dash sender and/or dash listener:"\
             + str(e))
        return
    while True:
        try:
            ret = ljm.eStreamRead(handle)
        except Exception as e:
            print("\n[ERR] Got exception while attmpting to read from LabJack stream: " + str(e))
            msg_to_dash(locks[sock_lock],"\nERROR: Got exception while attmpting to read from LabJack stream: "\
                 + str(e))
        try:
            all_data = ret[0]
            # Count the skipped samples which are indicated by -9999 values. Missed
            # samples occur after a device's stream buffer overflows and are
            # reported after auto-recover mode ends. 
            if all_data.count(-9999.0) > 0:
                msg_to_dash(locks[sock_lock],"\nWARNING: %d Samples got skipped! Program too slow or sample\
                    rate too high",all_data.count(-9999.0))
            # Every 1000 samples (roughly 3.3 sec) indicate correct running
            if (i % 1000 == 0): print("\n[INFO] Successfully collected %i samples" % i)
            # Try to write to the buffer or continuing without
            with locks[buf_lock].acquire(timeout = .005):
                data_buf[0] = []
                for j in range(0, constants[NUM_CHANNELS]):
                    data_buf[0].append(float(all_data[j])) 
            i += 1
            # Write values from this sweep to SD card
            data_log(fw,all_data,i,constants)
            # Check close condition
            if locks[close_lock].acquire(timeout = .01):
                if close == 1: 
                    print("\n[INFO] Close command received. Shutting down...")
                    data_sender.join(timeout = 5)
                    dash_listener.join(timeout = 5)
                    break
        except:
            """
            In the event of an error here, let helper functions handle
            the exception independently. Return to ensure proper closing of program
            handles and writers
            """

            return
    
def main():
    read_config()
    # Creating and binding socket to HOST:PORT, creating lock for send access
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(config["general"]["HOST"],int(config["general"]["PORT"]))
    print("\n[INFO] Bound socket to: " + str(config["general"]["HOST"])\
         + ":" + str(config["general"]["PORT"]))
    sock_lock = Lock()
    # Defining relevant constants
    SAMPLE_RATE = 300 # See external documentation for more info on this value
    NUM_CHANNELS = len(config["sensor_channel_mapping"].keys())
    NUM_DRIVERS = len(config["driver_mapping"].keys())
    READS_PER_SEC = int(config['general']["reads_per_sec"])
    constants = {
        SAMPLE_RATE:SAMPLE_RATE,
        NUM_CHANNELS:NUM_CHANNELS,
        NUM_DRIVERS:NUM_DRIVERS,
        READS_PER_SEC:READS_PER_SEC
    }
    try: 
        handle = ljm.openS("T7", "USB", "ANY")
    except:
        print("\n[ERR] Can't connect to LabJack device, shutting down...") 
        msg_to_dash(sock_lock,"\n[ERR] Can't connect to LabJack device, shutting down...")
        sock.close()
        return
    aScanListNames = list(config["sensor_channel_mapping"].values())
    aScanList = ljm.namesToAddresses(NUM_CHANNELS, aScanListNames)[0]
    scansPerRead = SAMPLE_RATE // READS_PER_SEC
    # Locks for data race prevention
    buf_lock = Lock()
    close_lock = Lock()
    locks = {
        buf_lock:buf_lock,
        close_lock:close_lock,
        sock_lock:sock_lock
    }
    # Buffer for data slices for dashboard send
    data_buf = [[]]
    # Value used to communicate stop-command status between threads
    close = 0
    stream_setup(handle)
    if (ljm.eStreamStart(handle, scansPerRead, NUM_CHANNELS, aScanList, SAMPLE_RATE) != SAMPLE_RATE):
        msg_to_dash(sock_lock,"\nERROR: Configured sample rate does not match actual sample rate")
        ljm.close(handle)
        sock.close()
        return
    fw = open_file()
    collect_data(handle,fw,close,data_buf,constants,locks)
    ljm.close(handle)
    sock.close()
    fw.close()
    pass

if __name__ == '__main__':
    print("===============================================================\
    \nData Acquisition and Remote Control for Eclipse Hybrid Engines\
    \n===============================================================")
    main()
    print("\n[INFO] Program ended")