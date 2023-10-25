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

        self.thread        = Thread(target = self.start_sending, args = ())

        self.work_queue.put(lambda: self.sample_data_to_operator())

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
        print(states)
        # Access to dataBuf from main() thread
        if self.data_buf_lock.acquire(timeout = .01):
            JSONData['sensors'] = self.data_buf[0]
            buf_data = self.data_buf[0]
            if not JSONData['sensors']: return
            self.data_buf_lock.release()
        else: return

        message0 = {}
        message0["type"] = "SensorValue"
        message0["group_id"] = 0
        message0["readings"] = []

        # thermo 1
        reading = {}
        reading["sensor_id"] = 0
        reading["reading"] = buf_data[6]
        reading["time"] = {}
        reading["time"]["secs_since_epoch"] = int(time.time())
        reading["time"]["nanos_since_epoch"] = 0
        message0["readings"] += [dict(reading)]

        # thermo 2
        reading["sensor_id"] = 1
        reading["reading"] = buf_data[7]
        message0["readings"] += [dict(reading)]

        message1 = {}
        message1["type"] = "SensorValue"
        message1["group_id"] = 1
        message1["readings"] = []

        # pt 1
        reading["sensor_id"] = 0
        reading["reading"] = buf_data[10]
        message1["readings"] += [dict(reading)]

        # pt 2
        reading["sensor_id"] = 1
        reading["reading"] = buf_data[11]
        message1["readings"] += [dict(reading)]

        # pt 3
        reading["sensor_id"] = 2
        reading["reading"] = buf_data[12]
        message1["readings"] += [dict(reading)]

        # pt 4
        reading["sensor_id"] = 3
        reading["reading"] = buf_data[13]
        message1["readings"] += [dict(reading)]

        message2 = {}
        message2["type"] = "SensorValue"
        message2["group_id"] = 2
        message2["readings"] = []

        # lc 1 (small)
        reading["sensor_id"] = 0
        reading["reading"] = buf_data[0]
        message2["readings"] += [dict(reading)]

        sendStr0 = json.dumps(message0).encode('UTF-8')
        sendStr1 = json.dumps(message1).encode('UTF-8')
        sendStr2 = json.dumps(message2).encode('UTF-8')

        statesmsg = {}
        statesmsg["type"] = "DriverValue"
        tfstates = []
        for i in range(3):
            if states[i] == 0: tfstates.append(False)
            elif states[i] == 1: tfstates.append(True)
        statesmsg["values"] = tfstates
        sendStr3 = json.dumps(statesmsg).encode('UTF-8')
        try:
            # print("\nTHERMOS: " + str(sendStr0) + "\nPTS: " + str(sendStr1) + "\nLCS: " + str(sendStr2) + "\nSTATES: " + str(sendStr3))
            self.sock.sendall(sendStr0)
            self.sock.sendall(sendStr1)
            self.sock.sendall(sendStr2)

            self.sock.sendall(sendStr3)


        except Exception as e:
            print("[W] Connection issue! Waiting for reconnect before resend: " + str(e))
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

