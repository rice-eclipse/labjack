# Mission Control docs

## Keychain

**Wireless network**  
Name: LanSolo  
Password: riceeclipse

**Raspberry Pi on Labjack**  
User: eclipsepi (host ip: 192.168.0.100)  
password: 1

**Pharos Control Software (Where you can manage the network)**  
Accessed by going to 192.168.0.254 while on LanSolo  
Username: riceeclipse  
password: riceeclipse

## PT calibration

Very jank procedure with a huge scope for improvement (see below)

1) Connect the relevant pt to the nitrous tank  
2) shut down the labjack script : *systemctl –user stop labjack*  
3) Modify [testjack.py](http://testjack.py) on labjack with the sensor port corresponding to the sensor under test (the AINx port numbers are in config.ini)  (I forgot the exact path)  
4) start running [testjack.py](http://testjack.py) on labjack (I forgot the exact path)  
5) Ask the engine support lead to increase pressure in increments of 10psi and log the voltage value in 10psi intervals (up to a 100 psi is fine)  
6) Plot the data in  excel and get the calibration slope and intercept  
7) Update the config.ini file for the sensor

## Hotfire packing list

Copied this straight from the SOP. Screw terminals for ignition wires should definitely be replaced with high amperage anderson connectors.

## **C. Avionics**

Controller equipment

* Labjack Engine Controller  
* Spare wires for each part  
* 3 x Pressure Transducers   
* Combustion Chamber Thermocouple  
* Wires Box  
  * 3-wire XLR Male to Anderson Powerpole Cable (1x, for Valve Actuation)  
  * 3-wire XLR Male to Male Spade connector (2x for Valve Actuation)  
  * 3-wire XLR Male to PT Connector (4x, for Pressure Transducers)  
  * 3-wire XLR Male to TC Connector (3x, for Thermocouple)  
  * 5-wire XLR Male to amphenol connector (1x, for LC)  
  * 2-wire Anderson to 3-wire Male Power Cable amphenol connector (2x, for main power and ignition power from battery)   
  * Ignition wires soldered on and IGN OUT cable connected to igniters via screw terminals (ensure there is a non-zero resistance (\~5-10 ohms) between positive and negative terminals)  
  * 2-wire Male power XLR to igniter screw terminals (1x, for controller to igniters)  
* 2 x Pharos TP Link Router Box (The following are the contents for EACH box)  
  * Router/Antenna  
  * Wall power cord  
  * PoE injector  
  * 2 x LAN/ethernet cable  
* Ethernet to USB adapter (or equivalent)  
* 12V Batteries   
  * 1x with Anderson Powerpole Connector  
  * Optional 1x with Anderson Powerpole Connector  
  * Optional 1x with bare terminals for power inverter  
* Power Inverter for access point antenna in case of portable power supply failure  
* Charged portable battery for Repeater antenna  
* Charged portable battery for Access Point Antenna  
* Dashboard Computer  
  * [Slonkboard](https://github.com/rice-eclipse/slonkboard) pulled from the github repository   
  * [Nodejs](https://nodejs.org/en/download)  and [npm](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) installed  
  * Charger cable  
* Extra Laptop Computer   
  * [Labjack software](https://support.labjack.com/docs/ljm-installation-instructions) downloaded  
  * [Labjack V1.0](https://github.com/rice-eclipse/labjack/tree/dev) and [Labjack V2.0](https://github.com/rice-eclipse/labjack/tree/main) pulled from the github repository  
  * Downlod the test\_jack.py script  
  * Charger cable  
* Ignition key  
* Spare ethernet cable  
* Strap to strap down box to the table  
* Table for Mission Control  
* Optional table for engine controller box  
* Chair for Mission Control  
* 2x tripods (for Mission Control and engine antennas, respectively)  
* 2x antenna stand supports (PVC pipe or another rigid beam of at least 4ft length)

## Relevant repos

**Labjack Firmware**  
This is the python code running on the Raspberry Pi connected to the Labjack T7 Data Acquisition/ Engine Control System. NOTE: THE CODE IN THIS REPO IS OLD. THE LATEST CODE IS ON THE PI  
Key functions:

- Send data collected by the Labjack T7 to the Mission Control Computer  
- Send commands for valve actuation/ ignition from the Mission Control Computer to the Labjack T7    
- Log data collected onto an SD Card

Link: [https://github.com/rice-eclipse/labjack.git](https://github.com/rice-eclipse/labjack.git)    
Full Labjack Documentation: [https://docs.google.com/document/d/1y7f7A9FtFfV9nHa74x1uJAnZVh4cjQFKVG3zE4jUQEY/edit?usp=sharing](https://docs.google.com/document/d/1y7f7A9FtFfV9nHa74x1uJAnZVh4cjQFKVG3zE4jUQEY/edit?usp=sharing)

**Quonkboard**  
React application for the front end interface for the mission control computer  
Key Functions:

- Provide a graphical user interface to send commands to the engine control system  
- Plots received data in real time

Link: [https://github.com/rice-eclipse/quonkboard.git](https://github.com/rice-eclipse/quonkboard.git)

**Post Processing scripts**

- Used to process the large data files produced during hotfires, extract the data that occur during ignition and plot them

[https://github.com/rice-eclipse/hotfire-data](https://github.com/rice-eclipse/hotfire-data)

If you’re interested (not important)  
Full Karca 2 Documentation: [https://github.com/rice-eclipse/kARCA\_v2.git](https://github.com/rice-eclipse/kARCA_v2.git)

Labjack python: [https://github.com/labjack/labjack-ljm-python/tree/master/labjack](https://github.com/labjack/labjack-ljm-python/tree/master/labjack)

## Main scopes for improvements

Current problems. Just my two cents, feel free to disregard.

- Connect the pi to wifi 	  
  - Will make version control much easier  
- Clean up the directories on the pi  
  - Everything is very messy right now. Throwing all the old code into an archives folder or deleting it and keeping a single folder for the active labjack scripts would be nice  
  - I have forgotten where the main scripts are located but I’ll be able to point you to them if you send me a photo of the file tree  
- Efficient data logging  
  - currently we collect a huge amount of data over the course of a 3-4 hour hotfire. Using a state machine (or the like) to change sampling and logging rates dynamically would be nice (ie: collect data very slowly while setting up and then ramp up sample rate during fill)  
  - This would allow the post-processing code to be cleaned up and simplified   
- Less jank sensor calibration  
  - We used a rudimentary python script that printed the readings in a for-loop and then copied them down into a csv.  The calibration curve was then found in excel and the config files for the sensors were updated manually  
  - It would be nice to have scripts that do everything automatically  
    - Log the data  
    - derive the calibration curves  
    - Update the config file  
- Error-prone post processing  
  - We currently get the portion of data relevant to ignition by finding the timestamps in the csv files that correspond to the timestamps on the console logs when an ‘IGNITION’ command is sent. This has been error prone and has required us to dig around the data to find the portion of it corresponding to ignition  
  - I thought a separate csv that was opened and written to during ignition would help. You guys can probably find a much better solution.  
- minor: CSVs are expensive  
  - The Pi is incredibly powerful so this hasn’t been an issue, but logging the data in binary and then parsing it in quonkboard and the post-processing scripts is more efficient. You do lose human-readibility.