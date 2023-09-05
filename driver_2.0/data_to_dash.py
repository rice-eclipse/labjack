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
        try:
            self.sock.sendall(sendStr)
        except socket.error:
            print("[W] Failed to send console msg: " + message)

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
        # Access to dataBuf from main() thread
        if self.data_buf_lock.acquire(timeout = .01):
            JSONData['sensors'] = self.data_buf[0]
            if not JSONData['sensors']: return
            self.data_buf_lock.release()
        else: return
        JSONData['states'] = states
        JSONData['console'] = "data"
        JSONData['timestamp'] = ""
        JSONObj = json.dumps(JSONData)
        sendStr = JSONObj.encode('UTF-8')
        try:
            print(sendStr)
            # self.sock.sendall(sendStr)
        except Exception as e:
            print("[W] Connection issue! Waiting for reconnect before resend: " + str(e))
            try:
                _, self.sock = setup_socket(self.setup_sock)
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

