from labjack import ljm
from common_util import should_close, setup_socket, get_valve_states, set_close, construct_message
import json
import queue
import socket
import time
from threading import Thread
from typing import Any, List, Set
import asyncio
import websockets

class DataSender:
    def __init__(self, config, data_buf):
        self.config        = config
        self.delay         = int(config["general"]["dash_send_delay_ms"])
        self.data_buf = data_buf
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        print("created data sender")
        self.VALVE_RESET_SECS = int(self.config['general']['reset_valves_min']) * 60

    async def sample_data_to_operator(self):
        states = get_valve_states(self.handle)
        buf_data = self.data_buf[0]
        message = construct_message(buf_data, states)
        sendstr = json.dumps(message).encode('UTF-8')
        for client in self.clients:
            client.send(sendstr)
        print(f"Sent: {sendstr[:40]}")

    async def add_client(self, client: websockets.WebSocketServerProtocol):
        self.clients.add(client)

    async def remove_client(self, client: websockets.WebSocketServerProtocol):
        self.clients.remove(client)

    async def start_sending(self):
        while True:
            await self.sample_data_to_operator()
            asyncio.sleep(self.delay)

