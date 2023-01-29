"""
read_modbus_serial.py
Rice Eclipse
Andrew Bare
"""

from datetime import datetime
import sys
import os

from labjack import ljm

MAX_REQUESTS = 25

def main(handle):
    info = ljm.getHandleInfo(handle)
    print("Opened a LabJack with Device type: %i, Connection type: %i,\n"
        "Serial number: %i, IP address: %s, Port: %i,\nMax bytes per MB: %i" %
        (info[0], info[1], info[2], ljm.numberToIP(info[3]), info[4], info[5]))

    aScanListNames = []
    print(sys.argv)
    try:
        addresses = sys.argv[1:]
        for address in addresses and if addresses != []:
            aScanListNames.append("AIN" + str(address))
        else:
            aScanListNames = ["AIN0"]
    except IndexError:
        # Default to only scanning AIN0
        aScanListNames = ["AIN0"]
    print(aScanListNames)

    deviceType = info[0]
    numAddresses = len(aScanListNames)
    aScanList = ljm.namesToAddresses(numAddresses, aScanListNames)[0]
    scanRate = 1000
    scansPerRead = int(scanRate / 2)

    try:
        # Ensure triggered stream is disabled.
        ljm.eWriteName(handle, "STREAM_TRIGGER_INDEX", 0)

        # Enabling internally-clocked stream.
        ljm.eWriteName(handle, "STREAM_CLOCK_SOURCE", 0)

        # All negative channels are single-ended, AIN0 range is +/-10V,
        # stream settling is 0 (default) and stream resolution index
        # is 0 (default).
        aNames = ["AIN_ALL_NEGATIVE_CH", "AIN0_RANGE",
            "STREAM_SETTLING_US", "STREAM_RESOLUTION_INDEX"]
        aValues = [ljm.constants.GND, 10.0, 0, 0]

        # Write the analog inputs' negative channels (when applicable), ranges,
        # stream settling time and stream resolution configuration.
        numFrames = len(aNames)
        ljm.eWriteNames(handle, numFrames, aNames, aValues)

        scanRate = ljm.eStreamStart(handle, scansPerRead, numAddresses, aScanList, scanRate)
        print("\nStream started with a scan rate of %0.0f Hz." % scanRate)

        print("\nPerforming %i stream reads." % MAX_REQUESTS)
        start = datetime.now()
        totScans = 0
        totSkip = 0  # Total skipped samples

        i = 1
        while i <= MAX_REQUESTS:
            ret = ljm.eStreamRead(handle)

            aData = ret[0]
            scans = len(aData) / numAddresses
            totScans += scans

            # Count the skipped samples which are indicated by -9999 values. Missed
            # samples occur after a device's stream buffer overflows and are
            # reported after auto-recover mode ends.
            curSkip = aData.count(-9999.0)
            totSkip += curSkip

            print("\neStreamRead %i" % i)
            ainStr = ""
            for j in range(0, numAddresses):
                ainStr += "%s = %0.5f, " % (aScanListNames[j], aData[j])
            print("  1st scan out of %i: %s" % (scans, ainStr))
            print("  Scans Skipped = %0.0f, Scan Backlogs: Device = %i, LJM = "
                "%i" % (curSkip/numAddresses, ret[1], ret[2]))
            i += 1

        end = datetime.now()

        print("\nTotal scans: %i" % (totScans))
        tt = (end - start).seconds + float((end - start).microseconds) / 1000000
        print("Time taken: %f seconds" % (tt))
        print("LJM Scan Rate: %f scans/second" % (scanRate))
        print("Timed Scan Rate: %f scans/second" % (totScans / tt))
        print("Timed Sample Rate: %f samples/second" % (totScans * numAddresses / tt))
        print("Skipped scans: %0.0f" % (totSkip / numAddresses))
    except ljm.LJMError:
        ljme = sys.exc_info()[1]
        print(ljme)
    except Exception:
        e = sys.exc_info()[1]
        print(e)

if __name__ == '__main__':
    handle = ljm.openS("T7", "ANY", "ANY")
    try:
        main(handle)
        
        ljm.eStreamStop(handle)
        print("\nStream ended.")
    except ljm.LJMError:
        ljme = sys.exc_info()[1]
        print(ljme)
    except KeyboardInterrupt:
        ljm.close(handle)
        try:
            sys.exit(130)
        except:
            os._exit(130)
    except Exception:
        e = sys.exc_info()[1]
        print(e)
