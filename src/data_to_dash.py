from labjack import ljm
from common_util import should_close, setup_socket, get_valve_states, set_close
import json
import queue
import socket
import time
from threading import Thread

class DataSender:
    def __init__(self, config, setup_sock, sock, close, close_lock, data_buf, data_buf_lock):
        self.config        = config
        self.setup_sock    = setup_sock
        self.sock          = sock
        self.close         = close
        self.close_lock    = close_lock
        self.data_buf      = data_buf
        self.data_buf_lock = data_buf_lock
        self.work_queue    = queue.Queue()
        self.cmd_listener  = None
        self.handle        = None
        self.prev_send     = 0
        self.disconnect_t  = None

        self.thread        = Thread(target = self.start_sending, args = ())

        self.work_queue.put(lambda: self.sample_data_to_operator())

        self.VALVE_RESET_SECS = int(self.config['general']['reset_valves_min']) * 60

    def start_thread(self):
        self.thread.start()

    def join_thread(self):
        self.thread.join()

    """
    Helper method for debugging
    """
    def msg_to_dash(self, message):
        JSONData = {}
        JSONData['sensors'] = []
        JSONData['states'] = []
        JSONData['console'] = message
        JSONObj = json.dumps(JSONData)
        sendStr = JSONObj.encode('UTF-8')
        # try:
        #     self.sock.sendall(sendStr)
        # except socket.error:
        #     print("[W] Failed to send console msg: " + message)

    def add_work(self, task):
        self.work_queue.put(task)

    def sample_data_to_operator(self):
        self.add_work(lambda: self.sample_data_to_operator())
        now = time.time() * 1000
        if (now < int(self.config["general"]["dash_send_delay_ms"]) + self.prev_send) or (self.handle == None):
            time.sleep(.001)
            return
        self.prev_send = now
        states = []
        JSONData = {}
        states = get_valve_states(self.handle)
        # print(states)
        # Access to dataBuf from main() thread
        if self.data_buf_lock.acquire(timeout = .01):
            JSONData['sensors'] = self.data_buf[0]
            buf_data = self.data_buf[0]
            if not JSONData['sensors']: return
            self.data_buf_lock.release()
        else: return
    
        buf_reorg_data = [buf_data[6], buf_data[7], buf_data[10], buf_data[11],
                          buf_data[12],buf_data[13], buf_data[0]]
        
        tc_data ={}
        pt_data ={}
        lc_data = {}
        full_msg = {"tcs": tc_data, "pts": pt_data, "lcs":lc_data}
        #populates the sensor data
        grp_id = 0
        total_sensor_count = 0
        for sensor_grp in full_msg.values():
                sensor_grp["type"] = "SensorValue"
                sensor_grp["group_id"] = grp_id

                #gets the reading for each sensor in each sensor group
                readings = []
                sensor_count = len(self.config["sensor_groups"][grp_id]["sensors"])
                for sensor_id in range(sensor_count):
                        reading = {}
                        reading["sensor_id"] = sensor_id

                        #thermo data starts from column 6
                        reading["reading"] = buf_reorg_data[total_sensor_count]
                        #print(grp_id+sensor_id)
                        reading["time"] = {}
                        reading["time"]["secs_since_epoch"] = 0
                        reading["time"]["nanos_since_epoch"] = 0
                        #print(reading)
                        readings.append(reading)
                        total_sensor_count += 1

                sensor_grp["readings"] = readings
                grp_id += 1

        statesmsg = {}
        statesmsg["type"] = "DriverValue"
        tfstates = []
        for i in range(len(states)):
            if states[i] == 0: tfstates.append(False)
            elif states[i] == 1: tfstates.append(True)
        statesmsg["values"] = tfstates
        sendStr3 = json.dumps(statesmsg).encode('UTF-8')
        full_msg["driver"] = statesmsg
        sendstr = json.dumps(full_msg).encode('UTF-8')
        try:
            #print(sendstr)
            self.sock.sendall(sendstr)
            self.disconnect_t = None

        except Exception as e:
            print("[W] Connection issue! Waiting for reconnect before resend: " + str(e))

            if self.disconnect_t is None:
                self.disconnect_t = time.time()
            else:
                secs_remaining = self.VALVE_RESET_SECS - (time.time() - self.disconnect_t)
                if secs_remaining < 0:
                    set_close(self.close, self.close_lock)
                else:
                    print(f"[W] Valve states will automatically reset in: {'{:02d}'.format(int(secs_remaining // 60))}:{'{:02d}'.format(int(secs_remaining % 60))}")

            try:
                self.sock = setup_socket(self.setup_sock)
                self.cmd_listener.sock = self.sock
            except socket.timeout:
                pass

    def start_sending(self):
        try:
            while not should_close(self.close, self.close_lock):
                task = self.work_queue.get()
                if task is None:
                    continue
                task()
        except Exception as e:
            set_close(self.close, self.close_lock)
            raise e
