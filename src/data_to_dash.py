import json
from typing import List, Dict
import asyncio
from websockets.asyncio.server import ServerConnection, broadcast
import websockets
from configparser import ConfigParser
import time
import logging

logger = logging.getLogger(__name__)

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
        self.task = asyncio.create_task(self._start_sending())
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.running = False
        await self.task

    async def _sample_data_to_operator(self):
        message = self._construct_message()
        message = json.dumps(message)
        logger.info("sending...")
        for client in list(self.clients.values()):
            logger.info(f"Sending data to {client.id}")
            try:
                await client.send(message)
            except websockets.ConnectionClosed as e:
                print(f"Connection closed: {e.code} - {e.reason}")
                await self._remove_client(client)
            except Exception as e:
                logger.error(e)
        logger.debug(f"Sent: {str(message)[:40]}")

    async def add_client(self, client: ServerConnection):
        logger.info(f"Added client {client.id}")
        self.clients[client.id] = client

    async def _remove_client(self, client: ServerConnection):
        del self.clients[client.id]

    async def _start_sending(self):
        try:
            while self.running:
                if self.data_buf[0] and self.valve_state_buf[0]:
                    await self._sample_data_to_operator()
                else:
                    logger.debug("Nothing in buffer")
                await asyncio.sleep(self.delay / 1000)
        except Exception as e:
            logger.error(f"Error in sending data: \n{e}")

    async def send_message(self, message: str):
        data = {
            "sensors": [],
            "states": [],
            "console": message
        }
        payload = json.dumps(data)
        logger.info(f"Sending message: '{message}'")
        broadcast(self.clients.values(), payload)

    def _construct_message(self):
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