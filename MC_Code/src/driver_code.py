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

from labjack import ljm
from datetime import datetime
import time
import csv
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
    config.read('config.ini')
    pass

"""
Connects TCP socket between local and dashboard. Called during setup,
and again whenever connection is lost. In both cases, will block the thread 
that calls, on s.listen(), until dashboard sends connection request or 
exception is thrown. 
Sets global variable "conn", a socket object used throughout the program,

    Parameters:
        sock: socket object used throughout program
"""
def connect_socket(sock):
    sock.listen()
    global conn
    temp, _ = sock.accept()
    # First message is time since LabVIEW's epoch (not the same as linux). Converting into datetime string
    filename = str(datetime.fromtimestamp(int(temp.recv(64).decode('utf-8')) - 2082844800 + 21600))
    temp.settimeout(.5)
    conn = temp
    return filename

"""
File writer for collected data.

    Returns:
        fw: csv file writer for data file
        f: file writer 
"""
def open_file(filename):
    f = open("../data/" + filename + ".csv", "x")
    fw = csv.writer(f)
    # Write in the initial column labels
    print("\n[INFO] Created new file in ../data/: ",filename)
    cols = ["Time (s)"]
    for sensors in config["sensor_channel_mapping"]:
        cols.append(sensors)
    fw.writerow(cols) 
    return fw,f

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
def command_from_dash(handle,close_lock):
    global close
    while True:
        try:
            with close_lock:
                if close == 1:
                    return 
            # Receive up to 2048 bytes, in the utf-8 format
            try:
                cmd = conn.recv(2048).decode('utf-8')
            except socket.timeout:
                cmd = ""
                pass
            # Unpack into JSON object
            if not cmd: continue
            decode_cmd = json.loads(cmd)
            print("\n[INFO] Received command: " + str(cmd))
            # Check if command field is set_valve: set "driver" field to "value"
            if decode_cmd["command"] == "set_valve":
                # Carry out command on hardware
                ljm.eWriteName(handle,config["driver_mapping"][str(decode_cmd["driver"])],decode_cmd["value"])
                print("\n[INFO] Set driver ",config["driver_mapping"][str(decode_cmd["driver"])],"to",decode_cmd["value"])
            # Check if command is ignition
            elif decode_cmd["command"] == "ignition":
                #TODO ignition sequence helper call
                print("\n[INFO] Ignition command received...")
                ljm.eWriteName(handle,config["driver_mapping"][str(6)],1)
                # ljm.eWriteName(handle,"CIO2",1)
                time.sleep(5)
                print("\n[INFO] Shutting down ignition pin")
                ljm.eWriteName(handle,config["driver_mapping"][str(6)],0)
                # ljm.eWriteName(handle,"CIO2",0)
                pass
            # Check if command is "close"
            elif decode_cmd["command"] == "close":
                print("\n[INFO] Stopping command listening...")
                with close_lock:
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
    return

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
def data_to_dash(handle,sock,data_buf,locks):
    global close
    while True: 
        with locks['close_lock']:
            if close == 1:
                return 
        states = []
        JSONData = {}
        # Reading current driver pin states
        statebin = format(int(ljm.eReadName(handle,"EIO_STATE")),'05b')
        for char in statebin:
            states.append(int(char))
        # Reading ign pin status
        statebin = format(int(ljm.eReadName(handle,"CIO_STATE")),'04b')
        states = [(int(statebin[1]))] + states
        # Access to dataBuf from main() thread
        if locks['buf_lock'].acquire(timeout = .01):
            JSONData['sensors'] = convert_vals(np.asarray(data_buf[0]))
            locks['buf_lock'].release()
        JSONData['states'] = states[::-1]
        JSONData['console'] = "data"
        JSONData['timestamp'] = ""
        JSONObj = json.dumps(JSONData)  
        try: 
            sendStr = JSONObj.encode('UTF-8')
            # Sends int length before message for dash to recv() w/ correct size
            conn.send(len(sendStr).to_bytes(2,"big"))
            conn.sendall(sendStr)
        except socket.error:
            print("\n[WARN] Connection issue! Waiting for reconnect before resend")
            """
            If the connection is invalid, attempts to repair via connect_socket()
            """
            try:
                _ = connect_socket(sock)
            except socket.timeout: 
                pass
            pass
        with locks['close_lock']:
            if close == 1:
                print("\n[INFO] Stopped command sending...")
                break
        time.sleep(int(config["general"]["dash_send_delay_ms"]) / 1000)
    return

"""
Helper method for debugging
"""
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
    sensor_keys = list(config['sensor_channel_mapping'].keys())
    for i, chan in enumerate(sensor_keys):
        key_prefix = chan[:6]
        is_two_dim = len(n_sensors.shape) == 2
        sensor_index = (slice(None), i) if is_two_dim else i
        offset_key = None
        scale_key = None

        if key_prefix == "thermo":
            offset_key = 'thermo_offset'
            scale_key = 'thermo_scale'
        elif key_prefix == "b_load":
            offset_key = 'big_lc_offset'
            scale_key = 'big_lc_scale'
        elif key_prefix == "s_load":
            offset_key = 'small_lc_offset'
            scale_key = 'small_lc_scale'
        elif key_prefix == "strain":
            offset_key = 'strain_offset'
            scale_key = 'strain_scale'
        elif key_prefix[:4] == "pres":
            pt_num = chan[:6]
            offset_key = pt_num + '_offset'
            scale_key = pt_num + '_scale'

        if offset_key and scale_key:
            n_sensors[sensor_index] = np.round(
                (sensor_vals[sensor_index] - float(config['conversion'][offset_key])) / float(config['conversion'][scale_key]), 2)
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
    num_reads = int(len(sensors) / constants['NUM_CHANNELS'])
    timestamps = np.round(np.linspace((sweepnum - num_reads)/constants['READS_PER_SEC'],\
        (sweepnum - 1)/constants['READS_PER_SEC'],num_reads),3)
    sensorsR = np.asarray(sensors).reshape(num_reads,constants['NUM_CHANNELS'])
    write_data = np.column_stack((np.transpose(timestamps),convert_vals(sensorsR)))
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
    reg_names = ["STREAM_TRIGGER_INDEX","STREAM_CLOCK_SOURCE","STREAM_RESOLUTION_INDEX","STREAM_SETTLING_US"]
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
def collect_data(handle,fw,data_buf,constants,locks):
    print("\n[INFO] Starting data collection...")
    i = 0
    e_count = 0
    idx = 0
    global close
    # Finding what index e-shutdown is at
    for sensor in config["sensor_channel_mapping"]:
        if sensor == config['proxima_emergency_shutdown']:
            break
        idx += 1
    while True:
        try:
            ret = ljm.eStreamRead(handle)
            all_data = list(ret[0])
            ljm_buff = ret[2]
            # Check if value exceed emergency treshhold
            if all_data[0:constants["NUM_CHANNELS"]][idx] > config["proxima_emergency_shutdown"]:
                e_count += 1
                # If 3 consecutive threshold exceeds, shutdown the valve
                if (e_count > 2):
                    ljm.eWriteName(handle,config["proxima_emergency_shutoff"]["shutdown_valve"],0)
            else:
                e_count = 0
            # Removing LJM buffer buildup to ensure it never overflows and crashes the stream
            if (i % 1000 == 0): print("\n[INFO] Successfully collected %i samples" % i)
            while (ljm_buff != 0):
                more_data = ljm.eStreamRead(handle)
                all_data += more_data[0]
                ljm_buff = more_data[2]
                if list(more_data[0])[0:constants["NUM_CHANNELS"]][idx] > config["proxima_emergency_shutdown"]:
                    e_count += 1
                    if (e_count > 2):
                        ljm.eWriteName(handle,config["proxima_emergency_shutoff"]["shutdown_valve"],0)
                else:
                    e_count = 0                
                i += 1
                if (i % 1000 == 0): print("\n[INFO] Successfully collected %i samples" % i)
        except Exception as e:
            print("\n[ERR] Got exception while attmpting to read from LabJack stream:\n" + str(e))
            msg_to_dash(locks['sock_lock'],"ERROR: Got exception while attmpting to read from LabJack stream: "\
                 + str(e))
            raise Exception
        try:
            # Try to write to the buffer or continue without
            if locks['buf_lock'].acquire(timeout = .5):
                data_buf[0] = []
                for j in range(0, constants['NUM_CHANNELS']):
                    data_buf[0].append(float(all_data[j])) 
                locks['buf_lock'].release()
            else:
                print("[ERR] Issue writing to data buffer")
            i += 1
            # Write values from this sweep to SD card
            data_log(fw,all_data,i,constants)
            # Check close condition
            with locks['close_lock']:
                if close == 1: 
                    print("\n[INFO] Close command received. Shutting down...")
                    return
        except Exception as e:
            """
            In the event of an error here, let helper functions handle
            the exception independently. Return to ensure proper closing of program
            handles and writers
            """
            print("\n[ERR] Issue in data collection: ",e,". Shutting down...")
            raise Exception
    
def main():
    read_config()
    # Creating and binding socket to HOST:PORT
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((config["general"]["HOST"],int(config["general"]["PORT"])))
    print("\n[INFO] Bound socket to " + str(config["general"]["HOST"])\
         + ":" + str(config["general"]["PORT"]))
    print("\n[INFO] Waiting for connection request...")
    filename = connect_socket(sock)
    sock.settimeout(.5)
    constants = {
        'SAMPLE_RATE':300,
        'NUM_CHANNELS':len(config["sensor_channel_mapping"].keys()),
        'NUM_DRIVERS':len(config["driver_mapping"].keys()),
        'READS_PER_SEC':300
    }
    # Locks for data race prevention
    locks = {
        'buf_lock':Lock(), # For the buffer containing sensors snapshot, to be sent to dash
        'close_lock':Lock(), # For universal close indicator
        'sock_lock':Lock() # For send() access on the socket
    }
    try: 
        handle = ljm.openS("T7", "USB", "ANY")
        # Default all drivers (they should already be)
        for driver in config["driver_mapping"]:
            ljm.eWriteName(handle,config["driver_mapping"][driver],0)
    except:
        print("\n[ERR] Can't connect to LabJack device, shutting down...") 
        msg_to_dash(locks["sock_lock"],"\n[ERR] Can't connect to LabJack device, shutting down...")
        conn.close()
        return
    aScanListNames = list(config["sensor_channel_mapping"].values())
    aScanList = ljm.namesToAddresses(constants["NUM_CHANNELS"], aScanListNames)[0]
    scansPerRead = constants["SAMPLE_RATE"] // constants["READS_PER_SEC"]
    # Buffer for data slices for dashboard send
    data_buf = [[]]
    # Value used to communicate stop-command status between threads
    global close
    close = 0
    stream_setup(handle)
    if (int(ljm.eStreamStart(handle, scansPerRead, constants["NUM_CHANNELS"], aScanList, constants["SAMPLE_RATE"]))\
        != constants["SAMPLE_RATE"]):
        msg_to_dash(locks["sock_lock"],"\n[ERR] Configured sample rate does not match actual sample rate")
        ljm.close(handle)
        conn.close()
        return
    fw,f = open_file(filename)
        # Spawn two additional threads for dashboard sending and receiving
    try:
        data_sender = Thread(target = data_to_dash, args = (handle,sock,data_buf,locks, ))
        data_sender.start()
        dash_listener = Thread(target = command_from_dash, args = (handle,locks['close_lock'],))
        dash_listener.start()
    except Exception as e:
        print("\n[ERR] Got exception in dash sender and/or dash listener:\n"\
             + str(e))
        msg_to_dash(locks['sock_lock'],"[ERR] Got exception in dash sender and/or dash listener:"\
             + str(e))
        ljm.close(handle)
        conn.close()
        return
    try:
        collect_data(handle,fw,data_buf,constants,locks)
    except:
        with locks["close_lock"]:
                close = 1
    print("\n[INFO] Waiting on other threads to close for shutdown...")
    data_sender.join()
    dash_listener.join()
    for driver in config["driver_mapping"]:
        ljm.eWriteName(handle,config["driver_mapping"][driver],0)
    ljm.close(handle)
    conn.close()
    f.close()
    pass

if __name__ == '__main__':
    print("\n===============================================================\
    \nData Acquisition and Remote Control for Eclipse Hybrid Engines\
    \n===============================================================")
    main()
    print("\n[INFO] Restarting program")
    