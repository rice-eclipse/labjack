import json
from websockets.asyncio.server import ServerConnection
from data_to_dash import DataSender
from configparser import ConfigParser
from labjack_interface import LabjackInterface
from typing import Dict
import logging
from websockets.exceptions import ConnectionClosedError

logger = logging.getLogger(__name__)

class CmdListener:
    def __init__(self, config: ConfigParser, data_sender: DataSender, ljm_int: LabjackInterface):
        self.config = config
        self.data_sender = data_sender
        self.ljm_int = ljm_int
    
    async def __aenter__(self):
        logger.debug("Listening...")
        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback):
        logger.debug("Exiting command listener context...")

    async def recv_cmd(self, websocket: ServerConnection):
        logger.info(websocket)
        try:
            async for cmd in websocket:
                try:
                    cmd = json.loads(cmd)
                except:
                    await self.data_sender.send_message("Invalid command syntax received!")
                await self.process_command(cmd)
        except ConnectionClosedError as e:
            logger.error(f"Connection closed unexpectedly: {e}\n{e.__traceback__}")

    async def process_command(self, cmd: Dict):
        logger.debug("Received command: " + str(cmd))
        if "type" not in cmd:
            return
        if cmd["type"] == "close":
            logger.info("No longer listening for commands")
            exit(0)
        elif cmd["type"] == "Actuate" and (("driver_id") in cmd) and (("value") in cmd):
            logger.info("Setting driver " + self.config["driver_mapping"][str(cmd["driver_id"])] + " to " + str(cmd["value"]))
            await self.ljm_int.actuate(self.config["driver_mapping"][str(cmd["driver_id"])], cmd["value"])
        elif cmd["type"] == "Ignition":
            await self.ljm_int.ignition_sequence()
        else:
            await self.data_sender.send_message(self.dash_sender, "[W] Unknown command type: " + cmd["type"])
