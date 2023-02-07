"""
Test script for logging data onto the raspberry pi
"""
from datetime import datetime
from labjack import ljm
import sys
import time
import csv
import os
import numpy as np

MAX_REQUESTS = 3

def main(handle):
    info = ljm.getHandleInfo(handle)
    print("Opened a LabJack with Device type: %i, Connection type: %i,\n"
        "Serial number: %i, IP address: %s, Port: %i,\nMax bytes per MB: %i" %
        (info[0], info[1], info[2], ljm.numberToIP(info[3]), info[4], info[5]))

    aScanListNames = ["CORE_TIMER","AIN0","AIN1","AIN2","AIN3","AIN4","AIN5","AIN6","AIN7","AIN8","AIN9"]
    # aScanListNames = [61520,61521]
    addresses = sys.argv[1:]
    if addresses != []:
        for address in addresses:
            aScanListNames = []
            aScanListNames.append("AIN" + str(address))
        
    print(aScanListNames)
    filename = "test_file_01"
    os.remove(filename + ".csv")
    file = open(filename + ".csv", "x")
    writer = csv.writer(file)
    writer.writerow(["Time (s)","LC1","LC2","LC3","LC4","SG1","SG2","PT1",\
    "PT2","PT3","PT4","TC1","TC2","TC3","TC4"])

    deviceType = info[0]
    numAddresses = len(aScanListNames)
    aScanList = ljm.namesToAddresses(numAddresses, aScanListNames)[0]
    print(ljm.namesToAddresses(numAddresses, aScanListNames))
    # aScanList = aScanListNames
    scanRate = 1000
    # scansPerRead = int(scanRate / 2)
    scansPerRead = scanRate

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
        # import pdb
        # pdb.set_trace()
        print("\nPerforming %i stream reads." % MAX_REQUESTS)
        start = datetime.now()
        totScans = 0
        totSkip = 0  # Total skipped samples
        i = 1
        while i <= MAX_REQUESTS:
            print("PRE STREAM",datetime.now())
            ret = ljm.eStreamRead(handle)
            print("POST STREAM",datetime.now())
            # timeStamps = np.linspace(1/(i*scanRate) + start,1/(i*scanRate) + start,)
            # pdb.set_trace()
            aData = ret[0]
            writeArray = np.asarray(aData)
            print(float( aData[0]))
            print("length of aData: ",len(aData))
            scans = len(aData) / numAddresses
            totScans += scans
            # now = datetime.now()
            # elapsed = (now - start).seconds + float((now - start).microseconds) / 1000000
            # writer.writerow([elapsed] + aData[0:numAddresses])
            writer.writerows(writeArray.reshape(int (scanRate),numAddresses))
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
    handle = ljm.openS("T7", "USB", "ANY")
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
