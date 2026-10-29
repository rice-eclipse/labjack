# **LabJack Mission Control Testing and Launch Electronics**

Spencer Darwall[^1], Andrew Bare[^2], Amy Danjul[^3], Clayton Ramsey[^4], Bryn Gerwin[^5]  
*Rice University, Houston, Texas 77005*

*and*

Adam Sher[^6], Ian Rundle[^7], Deepak Narayan[^8]  
*Rice University, Houston, Texas 77005*

**This document details the LabJack mission control setup, a hot-fire/launch and diagnostics system for Eclipse’s hybrid rocket engines. The system leverages commercial data acquisition technology, driver software written in Python running on a Raspberry Pi, and an interactive React dashboard. Data is processed from 14 analog sensors, monitoring load produced by the engine, oxidizer pressure throughout the ground system plumbing, engine temperature at various points, and material strain. The LabJack serves as the main interface for these sensors and manages driver actuation and ignition control. The Raspberry Pi, running Python code, handles logging and dashboard communication, and control of the LabJack. The operator uses an interactive LabVIEW dashboard via a long-range antenna and Wi-Fi connection, offering a reliable interface for remote monitoring. The setup's modular design ensures adaptability and longevity, and emphasis on use of commercial equipment promises reliability.**

# **![][image1]**

[**Figure 1\.**](#heading) Mission Control electronics box housing LabJack, Pi, power management and sensor harnessing

# 

# **Table of Contents**

[**Table of Contents	2**](#table-of-contents)

[**Revision Log	3**](#revision-log)

[Introduction	4](#introduction)

[Design Requirements	4](#design-requirements)

[Hardware Overview	6](#hardware-overview)

[1\. LabJack T7	6](#1.-labjack-t7)

[2\. Raspberry Pi	7](#2.-raspberry-pi)

[3\. Terminal Board	7](#3.-terminal-board)

[4\. Power Switching Board	8](#4.-power-switching-board)

[5\. Ignition Wiring	8](#5.-ignition-wiring)

[6\. Muxer	9](#6.-muxer)

[7\. Power Distribution	9](#7.-power-distribution)

[8\. 12V to 5V Step Down Converter	9](#8.-12v-to-5v-step-down-converter)

[9\. Ethernet & Router Power	9](#9.-ethernet-&-router-power)

[10\. Main Power & Ignition Safety	9](#10.-main-power-&-ignition-safety)

[11\. Ignition Power Input & Output	9](#11.-ignition-power-input-&-output)

[12\. Thermocouple XLR Connectors	9](#12.-thermocouple-xlr-connectors)

[13\. Load Cell & Strain Gauge XLR Connectors	10](#13.-load-cell-&-strain-gauge-xlr-connectors)

[11\. Pressure Transducer XLR Connectors	11](#11.-pressure-transducer-xlr-connectors)

[12\. Solenoid Valve Driver XLR Connectors	12](#12.-solenoid-valve-driver-xlr-connectors)

[Driver Software Overview	12](#driver-software-overview)

[1\. Program overview	13](#1.-program-overview)

[2\. Networking	13](#2.-networking)

[3\. Concurrency and Thread-safety	13](#3.-concurrency-and-thread-safety)

[4\. Sampling and Logging	14](#4.-sampling-and-logging)

[5\. Data to dashboard	14](#5.-data-to-dashboard)

[6\. Command from dashboard	14](#6.-command-from-dashboard)

[Dashboard Overview	15](#dashboard-overview)

[1\. Event Handling Loop (EHL)	15](#heading=h.654sgksdvihv)

[2\. UI Message Loop	15](#heading=h.oh5vx9sqgbvi)

# 

# **Revision Log**

| Revision Number | Date | Change Summary |
| :---: | :---: | ----- |
| **1** | **5/9/23** | **First full version of LabJack MC documentation** |

# **Introduction**	

Rice Eclipse has two separate hybrid engine development projects, both of which demand a sophisticated electronics and software setup for control and telemetry. The setup must sample various types of analog sensors throughout the ground systems setup, actuate up to 5 cryogenic solenoid valves, and provide 600 watt ignition power. All of this must be done wirelessly from outside the engine’s standoff radius, and adhere to safety regulations mandating proper valve protocol and rapid emergency shutoff in the event of unsafe conditions. 

For many years, the club has used a custom printed circuit board (PCB) system, Mk. 1.1, to log data and actuate valves. As the system has aged, it has become less reliable and has caused many scrubbed engine tests. To address this problem, the club developed ARCA, a revamped, up-to-date PCB resembling Mk. 1.1, as well as this, an entirely separate system built around the commercial LabJack data acquisition and control (DAQ) system. The LabJack mission control setup is designed around as much professional equipment as is affordably available and feasible given the tight design specifications of the project. In the first iteration, a $1,000 sponsorship was awarded to the club by LabJack for the completion of this project. The primary soft goals for this setup are:

* Build the mission-critical parts around industry-grade equipment, robust to failure and paired with extensive outside documentation.   
* Provide a modular foundation flexible for future iterations.  
* Use frameworks familiar to Eclipse engineers, and create a setup that is relatively easy to understand.

As is shown in Figure 2, the LabJack interacts directly with hardware in the ground systems plumbing setup; it streams data at a fixed sample rate to the Raspberry Pi and manages power distribution for valves and ignition. The Raspberry Pi runs on driver software written in Python, which handles logging, communication with the operator, and emergency shutdown monitoring. The operator uses a dashboard running on a personal computer built on National Instruments’ LabVIEW framework. Data is periodically sent from the Pi to the dashboard updating the user of the engine state, and commands are sent from the dashboard to the Pi to control the engine.

**Figure 2:** Block diagram detailing full field testing setup. Not included are CPE210 WiFi router and ground systems plumbing setup.

The design and construction of this system began in January, 2023 and it successfully completed its first mock-flow test in March, 2023\.

# **Design Requirements** 

The design requirements of the system revolve around the inputs and outputs of the ground systems plumbing setup, which are as follows:

| Table 1: Sensors (Inputs & Outputs) |  |  |  |  |
| :---: | :---: | :---: | :---: | ----- |
| **Device Item** | **Quantity** | **Device Input(s)** | **Device Output(s)** | **Notes** |
| **Pressure transducers** (measure oxidizer pressure) | 4 | 12V | 4 to 20mA | Current-loop device |
| **Thermocouples** (measure engine material temperature) | 4 | 5V, GND | 0 to 5V | Single-ended output voltage |
| **Load cells**  (measure force produced by engine during fire) | 4 | 5V, GND |  V+, V- | Must support both S-type and pancake type. Both give differential voltage outputs |
| **Strain gauges** (measure physical expansion of engine material) | 2 | 5V, GND | V+, V- | Exact specs not yet set. Give differential voltage outputs |

## 

| Table 2: Drivers (Outputs) |  |  |  |  |
| :---: | :---: | :---: | :---: | :---: |
| **Device Item** | **Quantity** | **Device Input(s)** | **Device Output(s)** | **Notes** |
| **Solenoid valves** | 5 | 12V, \>1A | \- | Digitally controlled |
| **Ignition** | 1 | 12V, \~50A | \- | Digitally controlled. Must use separate battery to avoid brown-out |

| Table 3: General Requirements |  |
| :---: | :---: |
| **Item** | **Description** |
| **Sampling of Data** | Sensor values must be retrieved and logged at an adequate frequency. 300Hz has been deemed sufficient. |
| **Emergency Shutdown** | The system must recognize extreme anomalies, and have a rapid shutdown response to ensure safety and prevent excessive damage to equipment. Exact specifications TBD, but involve a pressure threshold. |
| **Operation Distance** | The system must operate wirelessly from outside standoff distance, which is up to 1500 ft for Titan II hotfires. |
| **Valve Control** | System must be able to set valve states as close to instantaneously after receiving commands as possible. |
| **Ignition Safety** | Must be built with an ignition safety lock, designed to ring a loud buzzer and handle ignition only when physically armed. |

# **Hardware Overview**

The hardware of the setup relies on the LabJack T7 for analog signal processing and high-power distribution, and the Raspberry Pi for logging, control and networking. Figure 3 shows a top-down perspective on the box electronics, where the majority of the hardware in the system lies. An electronics box from Amazon is used for housing, with holes drilled in the sides for soldered connectors. All panel-mounted components on the bottom are secured using removable dual-lock.

**Figure 3:** Top-down view of box electronics

### *1\. LabJack T7*

The T7 is a DAQ designed by LabJack to handle analog inputs and digital outputs, and support addition of modular components like the power switcher and the terminal board. The T7 collects the sensor values from (3) the terminal board, with 16-bit ADC resolution and support for sample rates upwards of 100kHz. Data collected is streamed in real time to (2) the Raspberry Pi. In this application, a sample rate of 300Hz is used. The T7 also sets digital high/low on the (4) power switching pins to control high-power valve and ignition driver states. Details on how data is sent to the Pi via the T7’s “stream” setting are described in the software section. The T7 gets power and communication to the Pi via USB.  
[LabJack T7](https://labjack.com/products/labjack-t7?utm_source=google&utm_medium=paid&utm_campaign=1465765588&utm_content=75215610674&utm_term=labjack%20t7&gadid=448710079867&gad=1&gclid=Cj0KCQjwu-KiBhCsARIsAPztUF3leinszq8X2Wu5o8pybw-7rAArnPjKi0t3oCprj-O1JbRnY000UQ8aAtDWEALw_wcB)  
[LabJack T-series Documentation](https://cdn.docsie.io/document/workspace_u4AEu22YJT50zKF8J/doc_y40BsFy3xfhoq6DFQ/file_IBjtnvTpbmI27oYxn/25e05688-5e4d-5e52-feb6-b5842cb6244blabjack_t_series_datasheet_export_20210520.pdf)                                                                                                                                                                                                                                                                               

### *2\. Raspberry Pi*

A Raspberry Pi model 3 b is used for overall control of the electronics in the box, indefinitely running a Python program to handle operations. It retrieves data from (1) the T7 via its “stream” setting, and sends commands for valve actuation/deactuation via writing modbus register values through the LJM Python library. Details on interfacing between the Pi and the T7 are described further in the software section. The Pi is also responsible for networking, and is connected via ethernet cable (9) to CPE210 router which communicates with the operator via TCP over WiFi. SD card logging occurs on the Pi, where sensor values are written as they are retrieved. The Pi is powered, like everything else, from the 12V car battery through (8) the 12 to 5V step down converter. The Raspberry Pi is positioned beneath a fan for optional cooling, which has historically been necessary.

### *3\. Terminal Board*

The terminal board, or CB37, is a module of (1) the T7 used to extend the number of available analog input pins. It is connected to (6) the muxer via a 36-pin adapter, which allows operation on a range of pins different from the default, enabling a large number of both single-ended and differential inputs. Details on the wiring for each sensor are described in their respective sections. The terminal board uses screw-terminals, which are a convenient way to secure connections between signal-carrying wires and the device’s input pins. In this application the X3 channel is used, which is best described in the Muxer80 (6) product documentation. Table 4 details which sensors are wired to which analog input pins, both as the multiplexed system input pin and as is physically labeled on the terminal board’s top surface. Explanations for how each sensor signal is handled, and why load cells 1 and 2 are not handled as differential pairs, are in each sensor's respective section.

| Table 4: CB37 Sensor to Pin Mapping |  |  |
| :---: | :---: | :---: |
| **Sensor Name** | **System Input Pin** | **CB37 Physical Label** |
| Thermocouple 1 | AIN64 | FIO0 |
| Thermocouple 2 | AIN65 | FIO1 |
| Thermocouple 3 | AIN66 | FIO2 |
| Thermocouple 4 | AIN67 | FIO3 |
| Pressure Transducer 1 | AIN68 | FIO4 |
| Pressure Transducer 2 | AIN69 | FIO5 |
| Pressure Transducer 3 | AIN70 | FIO6 |
| Pressure Transducer 4 | AIN71 | FIO7 |
| Load Cell 1 (Externally amplified) | AIN48 | AIN0 |
| Load Cell 2 (Externally amplified) | AIN49 | AIN1 |
| Load Cell 3 (Negative) | AIN58 | AIN10 |
| Load Cell 3 (Positive) | AIN50 | AIN2 |
| Load Cell 4 (Negative) | AIN59 | AIN11 |
| Load Cell 4 (Positive) | AIN51 | AIN3 |
| Strain Gauge 1 (Negative) | AIN60 | AIN12 |
| Strain Gauge 1 (Positive) | AIN52 | AIN4 |
| Strain Gauge 2 (Negative) | AIN61 | AIN13 |
| Strain Gauge 2 (Positive) | AIN53 | AIN5 |

[LabJack Terminal Board](https://labjack.com/products/cb37-terminal-board)

### *4\. Power Switching Board*

The power switching board, or PS12DC, is a module of (1) the T7 used to interface between the digital output pins on the T7 and the high-power drivers used to actuate the valves. Since the T7 does not support 12V outputs, the PS12DC handles them instead. It has VS and GND pins taking in the positive and negative electrodes of the battery, as well as output pins for each driver. When the T7 sets a digital value on the device to high, the corresponding output pin on the PS12DC becomes shorted with the output of the battery, actuating the connected valve. The power switching board has an output pin for the small ignition relay, the VS/GND pins of which are only powered when the safety key switch is activated.  
[LabJack Power Switching Device](https://labjack.com/products/ps12dc-power-switching-board)

### *5\. Ignition Wiring*

The ignition wiring is fairly complicated, involving both batteries, two separate relays, a PS12DC pin output, a physical key switch, and a buzzer. The schematic is in figure 4:  
![][image2]  
**Figure 4:** Ignition wiring schematic

As can be seen, the buzzer sounds whenever the key switch is closed. If the key switch is closed and the IGN command pin is set, the small relay closes, activating the big relay and powering the igniters. If the safety key switch is not armed, the system will not work. The PS12DC is modeled here as a switch, which conveys its purpose but is a simplification. In reality, the PD12DC’s VS/GND pins (for the ign output) are given power only when the key is closed, at which point ignition is then controlled digitally via the **CIO3** output pin on (4) the PS12DC. Two relays are used instead of one to dedicate as much of the power draw as possible, including ignition and closing the big relay, to the ignition battery. The small relay cannot itself handle ignition power, which is around 600 watts, so instead controls the bigger one which can.  
[Small relay](https://www.amazon.com/ARTGEAR-Harness-Color-Labeled-Automotive-Motorcycle/dp/B078T8CMF6?th=1)  
[Big relay](https://www.amazon.com/Ximoon-Solenoid-Outboard-89-96158T-89-846070/dp/B07JRC7WJ2/ref=sr_1_3?crid=3LO6GP4OUPJYI&keywords=ximoon+12v+power+trim+solenoid+switch&qid=1673390498&sprefix=ximoon+12v+power+trim+solenoisd+swith,aps,86&sr=8-3)  
[Buzzer](https://www.amazon.com/Icstation-85dB-Active-Piezo-Electronic/dp/B01LAYWUDO/ref=sr_1_3?crid=W34UDG1ER5XJ&keywords=piezo%2Bbuzzer%2B12v&qid=1673391048&sprefix=piezo%2Bbuzzer%2B12v%2Caps%2C105&sr=8-3&th=1)

### *6\. Muxer*

The muxer80 is a LabJack module used to access a greater number of analog input pins than are normally available on a T7. It does this by multiplexing the default analog input pins between up to 7 additional pins, between 4 channels. In this application, the X3 channel is used, connected to (3) the terminal board. The muxer is best understood by reading its documentation on the company website.  
[LabJack Muxer80](https://labjack.com/products/mux80)

### *7\. Power Distribution*

A 12-position Anderson connector array is used to distribute power from the battery. Since everything except the Pi, which uses a 12 to 5V step down converter, is powered off 12 volts this makes connections much more manageable.   
[12-way Anderson Connector Array](https://www.amazon.com/dp/B07KSQ93XK/ref=sspa_dk_detail_0?psc=1&pd_rd_i=B07KSQ93XK&pd_rd_w=utoJ5&content-id=amzn1.sym.89ee1d2e-380f-4a05-89e5-d22eb0a17762&pf_rd_p=89ee1d2e-380f-4a05-89e5-d22eb0a17762&pf_rd_r=7PQXDYXC7FM16YW7XT99&pd_rd_wg=cG6Rl&pd_rd_r=602c94c9-7534-439b-aff5-a6d426dac99e&s=aht&sp_csd=d2lkZ2V0TmFtZT1zcF9kZXRhaWxfdGhlbWF0aWM&spLa=ZW5jcnlwdGVkUXVhbGlmaWVyPUExRThETVJVSUZZV05TJmVuY3J5cHRlZElkPUEwMzQyOTA4MjUxRjFUN0pHNzNRUyZlbmNyeXB0ZWRBZElkPUEwMDgxNzY2M0RVVE9TWVY1Vk1TTiZ3aWRnZXROYW1lPXNwX2RldGFpbF90aGVtYXRpYyZhY3Rpb249Y2xpY2tSZWRpcmVjdCZkb05vdExvZ0NsaWNrPXRydWU=)

### *8\. 12V to 5V Step Down Converter*

The Raspberry Pi requires 5V for operation, and thus uses a 12 to 5V step down converter to be able to use the car battery.  
[12 to 5V Step down Converter](https://www.amazon.com/Converter-Female-Power-Adapter-Module/dp/B0BCP6WPBD/ref=sr_1_27?crid=A3KNFVWYC1H5&keywords=12%2Bto%2B5%2Bvolt%2Bstep%2Bdown%2BUSB&qid=1683623815&s=electronics&sprefix=12%2Bto%2B5%2Bvolt%2Bstep%2Bdown%2Busb%2Celectronics%2C150&sr=1-27&th=1)

### *9\. Ethernet & Router Power*

Power is supplied to the CPE210 router using a portable power station via a power over ethernet adapter. The router uses an ethernet connection from the Raspberry Pi.  
[CPE210 Router](https://www.tp-link.com/us/business-networking/outdoor-radio/cpe210/#overview)

### *10\. Main Power & Ignition Safety*

Main power is connected from the battery using an external power connector to (7) the Anderson connector array. The key switch for ignition safety is also located here.

### *11\. Ignition Power Input & Output*

The ignition battery sits outside the box, and is connected via the “IGN\` In” connector. The igniters are at the end of the wire harness connected to “IGN Out”.

### *12\. Thermocouple XLR Connectors* 

The thermocouple probes themselves are connected to Adafruit TC breakout boards, which amplify the output signals and return single-ended voltages scaling linearly with temperature. The breakout boards require 5V, GND and an output connection. 3-pin XLR connectors are used, with the 5V and GND wires connecting to VS and GND pins on (3) the terminal board, and signal feeding into respective analog input pins.   
[Adafruit Thermocouple Breakout Board](https://www.adafruit.com/product/1778?gclid=CO7Mhaaj18gCFU6SfgodF94LTg)  
![][image3]  
**Figure 5:** Adafruit AD8495 amplifier breakout board

| Table 5: Thermocouple Wiring |  |  |  |
| ----- | :---- | :---- | :---- |
| Number (XLR Connector) | Function | Color | Gauge (AWG) |
| 1 | 5V | Red | 22 |
| 3 | Signal | White | 22 |
| 2 | Ground | Black | 22 |

### 

### *13\. Load Cell & Strain Gauge XLR Connectors*

There are two types of load cells used, “S-type” for Proxima and “pancake-type” for Titan II to measure force produced while firing. Their operational load ranges are different, but they function almost identically from an electronics standpoint. They both take 5V excitation voltage and GND, supplied from the VS and GND pins of (3) the terminal board, and give differential output pairs. Sensors giving differential output pairs (positive and negative signal outputs) is a noise reduction technique, used to remove the effects of ambient (common mode) factors, such as temperature, from the resultant signal. Differential output pairs must be fed into an instrumentation amplifier (inamp), which returns an amplified single-ended voltage.   
The T7 contains inamps onboard. Load cells 3 and 4 use them- their output signals are wired into 2 analog input pins each and the rest is handled through software. Load cells 1 and 2 however, are amplified externally using purchased InAmp modules. Amplification is done externally for 1 and 2 to give an option of much higher precision via a significantly higher amplifier gain. The T7 has the capability to provide a high gain, but greatly at the expense of system sample rate which is why it is not used.   
Strain gauges have differential output pairs and operate very similarly, and are intended to be handled internally by the T7. The specs for strain gauges have not yet been decided, so they have not been implemented yet.  
[Pancake Load Cell](https://sps.honeywell.com/us/en/products/advanced-sensing-technologies/industrial-sensing/industrial-test-and-measurement/load-cells/low-profile-load-cells/model-41-series)  
[S-type Load Cell](https://www.phidgets.com/?tier=3&catid=9&pcid=7&prodid=229)  
[LabJack External Instrumentation Amplifier](https://labjack.com/products/ljtick-inamp?utm_source=google&utm_medium=paid&utm_campaign=15647618047&utm_content=&utm_term=&gadid=&gad=1&gclid=CjwKCAjw3ueiBhBmEiwA4BhspISZpIs-w7B_s90-yisA_nSaIgmuI_CP59xtWtcODkBAc4YLj8KtThoCQ8UQAvD_BwE)  
![][image4]  
**Figure 6:** S-Type Load Cell used on Proxima  
![][image5]  
**Figure 7:** Axial Load Cell used on Titan II

| Table 6: Load Cell Wiring |  |  |  |
| ----- | :---- | :---- | :---- |
| Number (XLR Connector) | Function | Color | Gauge (AWG) |
| 2 | 5V | Red | 22 |
| 4 | Signal \+ | Green | 22 |
| 1 | Signal \- | White | 22 |
| 3 | Ground | Black | 22 |
| 5 | \- | \- | \- |

### 

### *11\. Pressure Transducer XLR Connectors*

The pressure transducers, measuring oxidizer pressure at various points throughout the ground systems setup, run on a current loop. A 12V excitation is supplied directly from the battery, and the transducers’ signal wire returns current ranging from 4mA to 20mA linearly based on what the pressure is. A ground reference is not needed. To retrieve a voltage from this, the current is passed through a shunt resistor of known value. For convenience, the LabJack Current Shunt module is used which takes in the current loop and returns a single-ended voltage.   
[Pressure Transducer](https://www.newark.com/omega/px119-1kgi/pressure-transducers-109-platform/dp/56AH7881)  
[LabJack Current Shunt](https://labjack.com/products/ljtick-currentshunt)  
![][image6]  
**Figure 8:** Pressure Transducer current shunt schematic

| Table 6: Pressure Transducer Wiring |  |  |  |
| ----- | :---- | :---- | :---- |
| Number (XLR Connector) | Function | Color | Gauge (AWG) |
| 1 | 12V | Red | 22 |
| 2 | Signal | Blue | 22 |
| 3 | \- | \- | \- |

### 

### *12\. Solenoid Valve Driver XLR Connectors*

The valves used in ground systems plumbing require 12V for actuation, which is provided by (4) the power switching board. VS and GND for the valve driver outputs are provided directly from the battery, and shorted with the leads of the valves when the corresponding digital value is set on (1) the T7. Each valve consumes between .75 and 1.8A at its peak during actuation.

| Table 7: Driver Wiring |  |  |  |
| ----- | :---- | :---- | :---- |
| Number (XLR Connector) | Function | Color | Gauge (AWG) |
| 1 | 12V | Red | 14 |
| 2 | Output \- | Black | 14 |
| 3 | \- | \- | \- |

### 

# **Driver Software Overview**

The Raspberry Pi is responsible for logging data, handling actuation/ignition commands from the user, sending data to the user, and monitoring safety conditions. The Pi is controlled by a program in Python, which runs on box bootup indefinitely. The code is well-documented with comments and docstrings, and can be found at [https://github.com/rice-eclipse/labjack](https://github.com/rice-eclipse/labjack).

### *1\. Program overview*

Figure 6 contains a block diagram detailing the control flow of the program. ![][image7]  
**Figure 9:** Driver software block diagram

The code is designed to run on startup, using a custom systemd call stored in the config folder of the Pi. It is set up to execute the program immediately after the network is configured, and to start the program 5 seconds after every time after the program stops, whether due to nominal shutdown or a crash. The program waits to begin sampling until an initial connection has been established. Once one has, a total of three threads execute to handle logging, data sending, and command handling concurrently.  It is important to note that this program is designed to run *headless*, a contrast from previous iterations, independent of an active SSH session. Only a shared WiFi connection is needed to control the engine, but no connection beyond the initial is needed to maintain data collection. Data collection runs independent of the status of the other two, including the socket status, ensuring reliable logging and emergency monitoring at all times. Data sending and command handling both depend on an active socket connection, and are designed to repair it if need be. If the thread attempting to send data notices the connection has been lost, it will go back into a listening state and accept from any machine that attempts to connect. This makes the system highly robust to issues while running, as if a networking issue arises the critical tasks will still be performed, the valve states will not be reset, and the connection can be restored at any time. 

### *2\. Networking*

The Pi is connected to a CPE210 router via Ethernet cable, and the user connects to the router via WiFi through the long range antennas connected with coaxial cables. That way, the dashboard and the Pi work on the same network. For communication, a TCP (transmission control protocol) socket is used to reliably send data between devices. The Pi functions as the socket server, and initially blocks on a .accept() call until the dashboard, as the client, attempts to connect. After this point, bytes can be sent back and forth using .send() and .recv() calls.   
When the connection is lost for whatever reason, the Pi continues to operate as the socket server, and can repair the connection via a .accept() setup in the same way as previously. 

### *3\. Concurrency and Thread-safety*

This program makes use of several elements of Python concurrency, meaning there are instances where multiple sections of the program run at the same time. In this case, the data retrieval/logging, dashboard sender, and command listener all run concurrently on separate “threads”. This raises two concerns, first that shared data resources must be managed in a special way to avoid conflicting access attempts, and second that there must be a safe way to shut down all three threads when the program tries to shutdown.   
The first issue is resolved using locks, which are simple python objects paired with each shared data structure. Only one thread can “acquire” the lock at a time (and ultimately release it), signaling that only that thread has the ability to read/write the data structure at that moment. This is similar to how a group of people in a meeting may pass around an object signifying whose turn it is to speak. Without this, there would be risk for multiple threads attempting to edit the same piece of memory, or send data through the socket, at the same time causing undefined behavior.  
The second issue is resolved using a global integer called “close,” which takes a value of 0 or 1\. Close, like every shared data structure, has an associated lock, and is set to 1 anytime a location in the program has signaled for shutdown. Most commonly, this will be when the command listener has received a reboot request from the dashboard, but it can also occur if an error or a KeyboardInterrupt populates and the program needs to shut down. Each thread routinely checks the value of “close,” and wraps up its tasks and finishes when it sees a 1\. Why not just terminate the program and forcibly kill the threads when it's time to shut down? Because the shutdown process involves closing the socket, closing the file writer, defaulting the valves, and other important overhead which must be handled safely to avoid unwanted or undefined behavior. 

### *4\. Sampling and Logging*

The stream setting of the T7 is used to collect data from each of the analog sensor inputs, at 300Hz. An in-depth explanation of how stream works can be found in the [T-series Documentation](https://cdn.docsie.io/document/workspace_u4AEu22YJT50zKF8J/doc_y40BsFy3xfhoq6DFQ/file_IBjtnvTpbmI27oYxn/25e05688-5e4d-5e52-feb6-b5842cb6244blabjack_t_series_datasheet_export_20210520.pdf). While the stream is active, the T7 populates a local memory buffer with the voltage values of each analog input specified during setup. Using the Python LJM library, the Pi accesses these values using an eStreamRead() call, which pops one value from the T7’s buffer. It can be set up for more samples to be acquired per call, but in this case one is used to optimize the response time of emergency shutdown. It must be ensured that the LJM buffer does not overflow, which will cause the system to crash. This issue is prevented by ensuring the buffer is empty after every single call, and in the case that it isn’t repeating the stream read call. Once the data has been retrieved by the Pi, it is checked for unsafe values. This is done by checking if 3 consecutive readings exceed a specified cutoff, and closing the respective valve if so. The values are then logged into a .csv file on the Pi, and the loop is continued. Note that emergency conditions are checked roughly 300 times a second, needing 3 in a row to activate- this means there is a roughly 10ms response time. Given that sensors sometimes produce erroneous values, this is a reasonable tradeoff between speed and preventing unwanted shutoffs. Exact implementation details are explained with comments in the code itself. The LJM offline user’s guide is an excellent resource for explaining each of the LabJack system calls that are used, as well as possible bugs that occur.   
[LJM Library Offline PDF](https://cdn.docsie.io/file/workspace_u4AEu22YJT50zKF8J/doc_VDWGWsJAhd453cYSI/boo_CV8MD3zVA3YnzoiBf/file_NVUSYgeT8sCvuAq2X/labjack-ljm-users-guide-export-20190731.pdf)

### *5\. Data to dashboard*

Every .5s, the thread dedicated to dashboard sending on the Pi sends the most recent snapshot of the sensors’ values via TCP over the WiFi connection. A snapshot, i.e. the exact most recent values recorded, are used instead of an average over the previous time window, to avoid arbitrarily manipulating the data and instead give the operator an exact sense of the most recent behavior. There is a shared array (with a lock of course) containing these values, which is written to by the logger thread and read from by the sender thread. JSON is used, with a ‘sensors’ field mapping to an array, in the order as in the config file, containing data and a ‘states’ field containing a 1 or 0 for each valve driver state. In the event of an invalid connection, the sender will wait for .5s for an incoming socket connection, and then repeat the loop. This way, if the connection is lost it will be regained about as soon as the dashboard attempts to reconnect. 

### *6\. Command from dashboard*

The Pi has a thread dedicated to command processing, which starts by listening on a recv() call for incoming bytes from the dashboard. Commands are received in JSON format, with the command field containing the desired action, and additional fields sent alongside to contain other necessary information, such as valve number and whether to actuate or deactuate. After the command is unpacked from bytes, the decoded action is carried out in hardware. This includes setting valves, ignition, and rebooting the program.

## 

# **Dashboard Overview**

The Dashboard is a JavaScript desktop application designed using the Electron Framework.  It interfaces with the LabJack system through the TCP connection. The dashboard acts as the client in the TCP socket connection and is responsible for logging the data sent by the Pi, displaying the sensor data graphically, and sending commands for valve actuation and ignition to the Pi. 

The dashboard consists of a main process responsible for handling the communication between the Pi and the dashboard and a renderer process responsible for handling the user interface (The graphical display of data and the buttons for the controller to send commands). The communication between these processes is handled using Electron’s Inter-Process Communication (IPC) channels.

### 

### *1\. Dashboard and Pi interface*

An interface module initiates a connection request to the Pi and handles the closing of the TCP connection. It parses the incoming JSON data from the Pi into a global object that can be accessed by other scripts in the main process. It also packages the commands sent by the controller into a JSON object that is then sent to the Pi.

### *2\. Data logging*

Two logger modules write the data into log files. One of the scripts handles the runtime information about the program including information about the data sent and received by the dashboard and any errors sent by the Pi, while the other logs all the sensor data.

### *3\. Inter-Process Communication*

Whenever data is received from the Pi, an event is triggered. A ‘main’ module (part of the main process) ‘listens’ for these events and sends the new data to the modules in the renderer process which updates the graphs and the console accordingly. The controller interacts with the application window using buttons. They can send commands to initiate or close the TCP connection and commands for valve actuation and ignition. When a button is clicked, triggering an event, the renderer process sends the command associated with the button to the ‘main’ script, which calls the required function in the interface module. The interface module packages the command into a JSON object and sends it to the Pi. 

[^1]:   Avionics & Software Division Lead 2022-2023, Electrical and Computer Engineering (‘24)

[^2]:   Chief Engineer/Vice President 2022-2023, Mechanical Engineering (‘24)

[^3]:   Chief Safety Officer 2023-2024, Computer Science & Mathematics (‘25)

[^4]:   Avionics Testing and Diagnostics Lead 2021-2023, Electrical Engineering and Computer Science (‘23)

[^5]:   Chief Engineer/Vice President 2021-2023, Mechanical Engineering (‘23)

[^6]:   Avionics & Software Division Lead 2023-2024, Electrical and Computer Engineering (‘25)

[^7]:  President 2023-2024, Computer Science & Mathematics (‘25)

[^8]:   Mission Control Lead 2024-2026, Electrical and Computer Engineering (‘26)

