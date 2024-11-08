from labjack import ljm
from configparser import ConfigParser
import logging
import asyncio
from data_to_dash import DataSender
import numpy as np
from typing import List
import csv
import datetime as dt

logger = logging.getLogger(__name__)

class LabjackInterface():
    def __init__(self, config: ConfigParser, data_sender: DataSender, data_buf: List[List[int]], valve_state_buf = List[int]):
        self.handle = ljm.openS("T7", "USB", "ANY")
        # try:
        #     ljm.eStreamStop(self.handle)
        #     ljm.close(self.handle)
        # finally:
        #     self.handle = ljm.openS("T7", "USB", "ANY")
        self.config = config
        self.sample_rate = int(self.config["general"]["sample_rate"])
        self.reads_per_sec = int(self.config["general"]["reads_per_sec"])
        self.num_channels = len(self.config["sensor_channel_mapping"].keys())
        self.data_sender = data_sender
        self._clear_drivers()
        self._stream_setup()
        self.running = False
        self.task = None
        self.data_buf = data_buf
        self.valve_state_buf = valve_state_buf
        self.e_index = self._get_emergency_sensor_index() 
        self.total_samples_read = 0
        self.csv_writer = None
        self.csv_fd = None
        self.ignition_in_progress = False
        # TODO: Why was the emergency check commented out earlier?
        
    async def __aenter__(self):
        self.running = True
        filename = f"../data/{dt.datetime.now().strftime('%m_%d_%Y_%H:%M:%S')}.csv"
        self.csv_fd = open(filename, "x")
        self.csv_writer = csv.writer(self.csv_fd)
        logger.info(f"Created new file: {filename}")
        cols = ["Time (s)"]
        for sensors in self.config["sensor_channel_mapping"]:
            cols.append(sensors)
        self.csv_writer.writerow(cols)
        self.task = asyncio.create_task(self._read_labjack_data())
        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback):
        self.running = False
        if exc_type != None:
            logger.error(f"Labjack interface closed, exception:\n{exc_value}\n\n{traceback}")
        await self.task
        try:
            self._clear_drivers()
        except:
            pass
        ljm.eStreamStop(self.handle)
        ljm.close(self.handle)
        self.csv_fd.close()
        
    async def _read_labjack_data(self):
        while self.running:
            await self._write_data_to_sd(await self._sample_data())
            await asyncio.sleep(0.001)
            
    async def _sample_data(self):
        max_reads = 15 # In case of extreme loopback lag allow max of 15 new rows
        new_rows = []
        for i in range(max_reads):
            read_val = ljm.eStreamRead(self.handle)
            new_rows += list(read_val[0])
            samples_in_ljm_buff = read_val[2]
            # print(samples_in_ljm_buff)
            # self.check_for_emergency(new_rows)
            self.total_samples_read += 1
            if self.total_samples_read % 1000 == 0: logger.info(f"{self.total_samples_read} samples obtained")
            if samples_in_ljm_buff == 0:
                break
        await self._update_valve_states()
        return new_rows

    def _voltages_to_values(self, sensor_vals: np.ndarray):
        if sensor_vals.size == 0: return []
        n_sensors = sensor_vals.copy()
        sensor_keys = list(self.config['sensor_channel_mapping'].keys())
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
                n_sensors[sensor_index] = np.round((sensor_vals[sensor_index] - float(self.config['conversion'][offset_key])) /\
                                                float(self.config['conversion'][scale_key]), 5)
    
        return n_sensors.tolist()
    
    async def _write_data_to_sd(self, data: List[int]):
        num_new_rows = int(len(data) / self.num_channels)
        start_time   = (self.total_samples_read - num_new_rows) / self.sample_rate
        end_time     = (self.total_samples_read - 1) / self.sample_rate
        timestamps   = np.round(np.linspace(start_time, end_time, num_new_rows), 5)

        dataR        = np.asarray(data).reshape(num_new_rows, self.num_channels)
        try:
            write_data   = np.column_stack((np.transpose(timestamps), self._voltages_to_values(dataR)))
        except Exception as e:
            logger.error(e)

        self.data_buf[0] = write_data[-1].tolist()[-self.num_channels:]
        self.csv_writer.writerows(write_data)
    
    def _clear_drivers(self):
        for driver in self.config["driver_mapping"]:
            ljm.eWriteName(self.handle, self.config["driver_mapping"][driver], 0)
    
    def _stream_setup(self):
        
        aScanListNames = list(self.config["sensor_channel_mapping"].values())
        aScanList = ljm.namesToAddresses(self.num_channels, aScanListNames)[0]
        scansPerRead = self.sample_rate // self.reads_per_sec

        reg_names = ["STREAM_TRIGGER_INDEX", "STREAM_CLOCK_SOURCE", "STREAM_RESOLUTION_INDEX", "STREAM_SETTLING_US"]
        reg_values = [0, 0, 0, 0]
        for chan in self.config["sensor_negative_channels"].keys():
            reg_names.append(self.config["sensor_channel_mapping"][chan] + "_NEGATIVE_CH")
            reg_values.append(int(self.config["sensor_negative_channels"][chan][3:]))
            reg_names.append(self.config["sensor_channel_mapping"][chan] + "_RANGE")
            reg_values.append(1)
            """
            Differential inputs (load cells and strain gauges) require amplification.
            Setting to "1" sets a gain of 10x- increasing this will improve the precision of these
            values, at the expense of sample rate.
            """
        numFrames = len(reg_names)
        ljm.eWriteNames(self.handle, numFrames, reg_names, reg_values)
        if (int(ljm.eStreamStart(self.handle, scansPerRead, self.num_channels, aScanList, self.sample_rate))\
            != self.sample_rate):
            raise Exception("Failed to configure LabJack data stream!")
        
    async def ignition_sequence(self):
        self.ignition_in_progress = True
        ljm.eWriteName(self.handle, self.config["driver_mapping"][str(6)],1)
        for countdown in range(10, -1, -1):
            if not self.ignition_in_progress:
                break
            await self.data_sender.send_message(f"Ignition sequence in {countdown}...")
            await asyncio.sleep(1)
        if self.ignition_in_progress:
            await self.data_sender.send_message(f"IGNITION IN PROGRESS")
            ljm.eWriteName(self.handle, self.config["driver_mapping"][str(6)],0)
        else:
            await self.data_sender.send_message(f"IGNITION CANCELED")
            logger.warning("Ignition canceled")
    
    async def cancel_ignition(self):
        await self.data_sender.send_message(f"Canceling ignition...")
        self.ignition_in_progress = False

    async def actuate(self, driver: int, value: bool):
        ljm.eWriteName(self.handle, driver, value)
        
    async def check_for_emergency(self, sensor_readings):
        if sensor_readings[-self.num_channels:][self.e_index] > int(self.config["proxima_emergency_shutdown"]["max_pressure"]):
            '''TODO: we probably need to bound this condition so invalid readings from the sensor being
               unplugged dont falsely trigger emergency'''
            self.strikes += 1
            if (self.strikes >= 3):
                # 3 bad values in a row -> emergency shutdown
                ljm.eWriteName(self.handle, self.config["proxima_emergency_shutoff"]["shutdown_valve"], 0)
                await self.data_sender.send("Emergency shutdown executed!")
        else:
            self.strikes = 0
            
    """
    Get the index to refer to the emergency shutdown indicating sensor by
    """
    def _get_emergency_sensor_index(self):
        idx = 0
        for sensor in self.config["sensor_channel_mapping"]:
            if sensor == self.config['proxima_emergency_shutdown']['sensor_name']:
                return idx
            idx += 1
        raise Exception("'sensor name' field of emergency config not found in sensors list")

    async def _update_valve_states(self):
        states = []
        statebin = format(int(ljm.eReadName(self.handle,"EIO_STATE")),'05b')
        for char in statebin:
            states.append(int(char))
        statebin = format(int(ljm.eReadName(self.handle,"CIO_STATE")),'04b')
        states = [(int(statebin[1]))] + states
        self.valve_state_buf[0] = states[::-1]