import numpy as np
from datetime import datetime
from labjack import ljm
import csv

def should_close(close, close_lock):
    with close_lock:
        if close[0] == 1:
            return True
    return False

def set_close(close, close_lock):
    with close_lock:
        close[0] = 1

def setup_socket(setup_sock):
    print("[I] Waiting for connection request...")
    setup_sock.listen()
    sock = setup_sock.accept()[0]
    sock.settimeout(.5)
    # First message after connection is always ms since epoch
    filename = str(datetime.fromtimestamp(int(sock.recv(64).decode('utf-8')) / 1000))
    return filename, sock

def voltages_to_values(config, sensor_vals):
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
            n_sensors[sensor_index] = np.round((sensor_vals[sensor_index] - float(config['conversion'][offset_key])) /\
                                               float(config['conversion'][scale_key]), 2)
    return n_sensors.tolist()

"""
Get the index to refer to the emergency shutdown indicating sensor by
"""
def get_emergency_sensor_index(config):
    idx = 0
    for sensor in config["sensor_channel_mapping"]:
        if sensor == config['proxima_emergency_shutdown']['sensor_name']:
            return idx
        idx += 1
    raise Exception("'sensor name' field of emergency config not found in sensors list")

def get_valve_states(handle):
    states = []
    statebin = format(int(ljm.eReadName(handle,"EIO_STATE")),'05b')
    for char in statebin:
        states.append(int(char))
    statebin = format(int(ljm.eReadName(handle,"CIO_STATE")),'04b')
    states = [(int(statebin[1]))] + states
    return states[::-1]

def send_msg_to_operator(dash_sender, msg):
    print(msg)
    dash_sender.add_work(lambda: dash_sender.msg_to_dash(msg))

def open_file(config, filename):
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
