
from common_util import should_close, set_close, send_msg_to_operator
import socket
import json
import time
from threading import Thread
from labjack import ljm

class CmdListener:
    def __init__(self, config, sock, close, close_lock, dash_sender):
        self.config      = config
        self.sock        = sock
        self.close       = close
        self.close_lock  = close_lock
        self.handle      = None
        self.dash_sender = dash_sender

        self.cmd_thread  = Thread(target = self.listen, args = ())
        self.ign_thread  = Thread(target = self.ignition_sequence, args = ())

    def start_thread(self):
        self.thread.start()

    def join_thread(self):
        self.thread.join()

    def recv_cmd(self):
        try:
            return self.sock.recv(2048).decode('utf-8')
        except socket.timeout:
            time.sleep(.001)
            return None
        except socket.error:
            # Shared socket; wait for DashSender to fix it (otherwise race condition arises)
            time.sleep(.05)
            return None

    def ignition_sequence(self):
        ljm.eWriteName(self.handle,self.config["driver_mapping"][str(6)],1)
        send_msg_to_operator(self.dash_sender, "[I] Igniting...")
        time.sleep(5)
        ljm.eWriteName(self.handle,self.config["driver_mapping"][str(6)],0)

    def start_thread(self):
        self.cmd_thread.start()

    def listen(self):
        while not should_close(self.close, self.close_lock):
            if (cmd := self.recv_cmd()) is not None:
                print("[I] Received command: %s", str(cmd))
                decode_cmd = json.loads(cmd)
                if decode_cmd["command"] == "close":
                    print("[I] No longer listening for commands")
                    set_close(self.close, self.close_lock)
                elif self.handle == None:
                    send_msg_to_operator(self.dash_sender, "[E] Dropping command; no active LabJack handle")
                elif decode_cmd["command"] == "set_valve":
                    print("[I] Setting driver %s to %s",self.config["driver_mapping"][str(decode_cmd["driver"])],decode_cmd["value"])
                    ljm.eWriteName(self.handle,self.config["driver_mapping"][str(decode_cmd["driver"])],decode_cmd["value"])
                elif decode_cmd["command"] == "ignition":
                    if not self.ign_thread.is_alive(): self.ign_thread.start()
            else: time.sleep(.001)
