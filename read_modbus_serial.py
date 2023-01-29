"""
read_modbus_serial.py
Rice Eclipse
Andrew Bare
"""
import sys
import os
from labjack import ljm

def main(handle):


    info = ljm.getHandleInfo(handle)
    print("Opened a LabJack with Device type: %i, Connection type: %i,\n"
        "Serial number: %i, IP address: %s, Port: %i,\nMax bytes per MB: %i" %
        (info[0], info[1], info[2], ljm.numberToIP(info[3]), info[4], info[5]))


    try:
        address = int(sys.argv[1])  # Set serial number from terminal args
    except IndexError:
        address = 0 # Set default serial number 0
    dataType = ljm.constants.UINT32
    result = ljm.eReadAddress(handle, address, dataType)

    print("\neReadAddress result: ")
    print("    Address - %i, data type - %i, value : %f" %
        (address, dataType, result))


if __name__ == '__main__':
    handle = ljm.openS("T7", "ANY", "ANY")
    try:
        main(handle)
        ljm.close(handle)
    except KeyboardInterrupt:
        ljm.close(handle)
        try:
            sys.exit(130)
        except:
            os._exit(130)
