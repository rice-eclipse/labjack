import numpy as np
from common_util import voltages_to_values, should_close, send_msg_to_operator, get_emergency_sensor_index
from labjack import ljm

class DataLogger:
    def __init__(self, config, close, close_lock, data_buf, \
                 data_buf_lock, fd, dash_sender, sample_rate, num_channels):
        self.config             = config
        self.close              = close
        self.close_lock         = close_lock
        self.data_buf_lock      = data_buf
        self.data_buf           = data_buf_lock
        self.fd                 = fd
        self.dash_sender        = dash_sender
        self.sample_rate        = sample_rate
        self.num_channels       = num_channels
        self.total_samples_read = 0
        self.handle             = None
        self.strikes            = 0
        try:
            self.e_index = get_emergency_sensor_index()
        except Exception as e:
            send_msg_to_operator(self.dash_sender, e)
            raise e

    def start(self):
        self.start_reading()

    def check_for_emergency(self, sensor_readings):
        if sensor_readings[-self.num_channels:][self.e_index] > self.config["proxima_emergency_shutdown"]:
            '''we probably need to bound this condition so invalid readings from the sensor being
               unplugged dont falsely trigger emergency'''
            self.strikes += 1
            if (self.strikes >= 3):
                # 3 bad values in a row -> emergency shutdown
                ljm.eWriteName(self.handle, self.config["proxima_emergency_shutoff"]["shutdown_valve"], 0)
                send_msg_to_operator(self.dash_sender, "[W] Emergency shutdown executed!")
        else:
            self.strikes = 0

    def get_and_check_data_from_labjack(self):
        try:
            max_reads = 15 # In case of extreme loopback lag allow max of 15 new rows
            new_rows = []
            for i in range(max_reads):
                read_val = ljm.eStreamRead(self.handle)
                new_rows += list(read_val[0])
                samples_in_ljm_buff = read_val[2]
                self.check_for_emergency(new_rows)
                self.total_samples_read += 1
                if samples_in_ljm_buff == 0:
                    break
            return new_rows
        except Exception as e:
            send_msg_to_operator(self.dash_sender, "[E] Runtime exception during LabJack read " + str(e))
            pass # Do not terminate program on read error

    def write_data_to_sd(self, data):
        num_new_rows = int(len(data) / self.num_channels)
        start_time   = (self.total_samples_read - num_new_rows) / self.sample_rate
        end_time     = (self.total_samples_read - 1) / self.sample_rate
        timestamps   = np.round(np.linspace(start_time, end_time, num_new_rows), 5)

        dataR        = np.asarray(data).reshape(num_new_rows, self.num_channels)
        write_data   = np.column_stack((np.transpose(timestamps), voltages_to_values(dataR)))

        self.share_to_dash(self, write_data[-1])
        self.fd.writerows(write_data)

    def share_to_dash(self, new_rows):
        if self.data_buf_lock.acquire(timeout = .05):
            self.data_buf[0] = new_rows[-self.num_channels:]
            self.data_buf_lock.release()

    # Effective "main"
    def start_reading(self):
        while not should_close(self.close, self.close_lock):
            self.write_data_to_sd(self.get_and_check_data_from_labjack())