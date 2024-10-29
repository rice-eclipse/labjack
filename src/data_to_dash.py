import json
from typing import List, Dict
import asyncio
from websockets.asyncio.server import ServerConnection
from configparser import ConfigParser
import time

class DataSender:
    def __init__(self, config: ConfigParser, data_buf: List[List[int]], valve_state_buf: List[List[int]]):
        self.config        = config
        self.delay         = int(config["general"]["dash_send_delay_ms"])
        self.data_buf = data_buf
        self.clients: Dict[int, ServerConnection] = {}
        self.VALVE_RESET_SECS = int(self.config['general']['reset_valves_min']) * 60
        self.running = False
        self.valve_state_buf = valve_state_buf
        
    async def __aenter__(self):
        self.running = True
        self.task = asyncio.create_task(self.start_sending())
        return self

    async def __aexit__(self):
        self.running = False
        await self.task

    async def sample_data_to_operator(self):
        message = self._construct_message()
        sendstr = json.dumps(message).encode('UTF-8')
        for client in self.clients.values():
            client.send(sendstr)
        print(f"Sent: {sendstr[:40]}")

    async def add_client(self, client: ServerConnection):
        self.clients[client.id] = client

    async def remove_client(self, client: ServerConnection):
        del self.clients[client.id]

    async def start_sending(self):
        while self.running:
            await self.sample_data_to_operator()
            asyncio.sleep(self.delay)

    async def _construct_message(self):
        buf_data = self.data_buf[0]
        states = self.valve_state_buf[0]
        return {
            "tcs": {
                "type": "SensorValue",
                "group_id": 0,
                "readings": [
                    {
                        "sensor_id": 0,
                        "reading": buf_data[6],
                        "time": {
                            "secs_since_epoch": int(time.time()),
                            "nanos_since_epoch": 0
                        }
                    },
                    {
                        "sensor_id": 1,
                        "reading": buf_data[7]
                    }
                ]
            },
            "pts": {
                "type": "SensorValue",
                "group_id": 1,
                "readings": [
                    {
                        "sensor_id": 0,
                        "reading": buf_data[10],
                    },
                    {
                        "sensor_id": 1,
                        "reading": buf_data[11]
                    },
                    {
                        "sensor_id": 2,
                        "reading": buf_data[12]
                    },
                    {
                        "sensor_id": 3,
                        "reading": buf_data[13]
                    }
                ]
            },
            "lcs": {
                "type": "SensorValue",
                "group_id": 2,
                "readings": [
                    {
                        "sensor_id": 0,
                        "reading": buf_data[0],
                    },
                ]
            },
            "driver": {
                "type": "DriverValue",
                "values": [bool(state) for state in states]
            }
        }