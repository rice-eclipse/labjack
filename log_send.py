"""
log_send.py
Rice Eclipse
Andrew Bare
"""
from labjack import ljm
from datetime import datetime
import socket
import sys
import os


def main(handle):
    # Set up TCP socket
    HOST = ""
    PORT = 


    # Get info about LabJack
    info = ljm.getHandleInfo(handle)
    print("Opened a LabJack with Device type: %i, Connection type: %i,\n"
        "Serial number: %i, IP address: %s, Port: %i,\nMax bytes per MB: %i" %
        (info[0], info[1], info[2], ljm.numberToIP(info[3]), info[4], info[5]))

    
    aScanListNames = ["AIN0", "AIN1"] # List of names to stream from
    numAddresses = len(aScanListNames)
    aScanList = ljm.namesToAddresses(numAddresses, aScanListNames)[0]
    scanRate = 1000
    scansPerRead = int(scanRate / 2)
    print("Stream will occur from the following AIN#:")
    print('\t' + aScanListNames)
    print("At rate %i" % scanRate)


    try:
        # Ensure triggered stream is disabled.
        ljm.eWriteName(handle, "STREAM_TRIGGER_INDEX", 0)

        # Enabling internally-clocked stream.
        ljm.eWriteName(handle, "STREAM_CLOCK_SOURCE", 0)


    

def stream_ain(handle, addresses)

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