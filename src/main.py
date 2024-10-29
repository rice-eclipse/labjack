"""
Data Acquisition and Remote Control for Eclipse Hybrid Engines
Ian Rundle, President '23-24
Spencer Darwall, Avionics & Software Lead '22-23

Code interfaces with LabJack device hardware via LJM Library. The LabJack
has input pins for each sensor and output pins for each driver- this script logs
collected data, periodically sends some fraction of it to the dashbaord, sets valve
states when instructed by the dashboard, and has lightning-fast responses to unsafe
engine conditions. Intended for use on Raspberry Pi, connected to a LabJack T7 via USB.

Ensure that config.ini is located in this sub-directory.

For documentation on the overall setup:
https://docs.google.com/document/d/1y7f7A9FtFfV9nHa74x1uJAnZVh4cjQFKVG3zE4jUQEY/edit?usp=sharing

For more info about this software:
https://github.com/rice-eclipse/labjack

For more info about the LabJack T7 and its' acessories:
https://labjack.com/pages/support?doc=%2Fdatasheets%2Ft-series-datasheet%2F

Run-on-startup config at: /home/eclipsepi/.config/systemd/user/labjack.service
"""

from data_to_dash import DataSender
from cmd_from_dash import CmdListener
from configparser import ConfigParser
from websockets.asyncio.server import ServerConnection, serve
import asyncio
import signal
from labjack_interface import LabjackInterface

class ServiceDirector():
    def __init__(self, config_file: str):
        self.conf = ConfigParser()
        self.conf.read(config_file)
        self._validate_config()
        self.data_buf = [None]
        self.valve_state_buf = [None]
        
    def _validate_config():
        pass
    
    async def run(self):
        async with DataSender(self.config, self.data_buf, self.valve_state_buf) as data_sender:
            async with LabjackInterface(self.config, data_sender, self.data_buf, self.valve_state_buf) as ljm_int:
                async with CmdListener(self.config, data_sender, ljm_int) as cmd_listener:
                    async def ws_handle(self, websocket: ServerConnection, path: str):
                        await data_sender.add_client(websocket)
                        await cmd_listener.recv_cmd(websocket, path)
                    
                    loop = asyncio.get_event_loop()
                    stop = loop.create_future()
                    loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)
                    async with serve(
                        ws_handle, 
                        self.config["general"]["HOST"], 
                        self.config["general"]["PORT"]
                    ):
                        await stop
        
def main():
    asyncio.run(ServiceDirector("config.ini").run())

if __name__ == '__main__':
    print("\n===============================================================\
    \nData Acquisition and Remote Control for Eclipse Hybrid Engines\
    \nSoftware version 1.2.0\
    \n===============================================================")
    main()
    print("[I] Stopping program")
