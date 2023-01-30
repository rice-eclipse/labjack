# labjack
Scripts for interfacing with Eclipse's LabJack DAQ engine testing system

## Python scripts
The LabJack Python scripts provide a simple interface through the command-line to debug and test the LabJack system.

### stream_ain.py
stream_ain.py takes an unlimited number of AIN numbers as command-line arguments and streams 1k samples/second, displaying every 500th.
It defaults to streaming only AIN0.

### read_modbus_serial.py
read_modbus_serial.py takes a a single Modbus address as a command-line argument and reads a single value from it.

### write_address.py
write_address.py takes a single Modbus address and a single integer value as command-line arguments.
It attempts to write the value as UNIT16 to the given Modbus address.

## Lua scripts
The Lua scripts run on the LabJack T7 itself to perform local logging, emergency shutoff and data manipulation tasks.
