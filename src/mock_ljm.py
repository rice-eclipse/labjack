import random
import datetime as dt
import time

class SimLJM:
    def __init__(self):
        self.last_stream_read = dt.datetime.now()
        self.data = [random.randint(0, 10) for _ in range(14)]
    
    def eReadName(self, handle, name):
        return 0.0
    
    def eStreamRead(self, handle):
        time.sleep(random.randint(3,10) / 50000)
        return ([random.randint(0, 10) / 1000 for _ in range(14)], 0, 14)
    
    def eStreamStart(self, handle, scans, numAddresses, a, sample_rate):
        return sample_rate
    
    def eStreamStop(self, handle):
        return
    
    def eWriteName(self, handle, driver, value):
        return
    
    def eWriteNames(self, handle, numFrames, reg_names, reg_values):
        return
    
    def openS(self, a, b, c):
        return 0
    
    def namesToAddresses(self, num_channels, conf):
        return ([], [])
    
    def close(self, handle):
        return
    
    