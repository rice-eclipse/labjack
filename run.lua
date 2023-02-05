LJ.intervalConfig(0, 10) -- Data-collection interval
LJ.intervalConfig(1, 200) -- Data logging Interval
LJ.setLuaThrottle(1000)

-- Define local functions for speed
local checkInterval = LJ.CheckInterval
local R = MB.R
local W = MB.W
local WA = MB.WA
local RA = MB.RA

local logging = 0 -- not logging
local emergencyMax = 100

local dataAddresses = {0, 2, 4, 6} -- AIN(0:3) for now
local data = {}

while true do
    if checkInterval(0) then
        for i = 1,table.gen do
            R(address, 3)
        end
    end
    if checkInterval(1) then
        -- Read data logging signal from USER_RAM8_UINT16 (UINT16)
        logging = R(46188, 0)
        -- Read signal from AIN0 for emergency shutdown (F32)
        emergencySensorValue = R(46000, 3)
        if emergencySensorValue > emergencyMax then
            -- Set all valves to low
        end
        
    end
    
end