# Nicla characterisation datatake
This repo contains the necessary files for setting up a rx/tx between Nicla ME Sense and a generic micro (such as a Raspberry).

## Requirements

### Nicla ME Sense
One needs to have" Arduino IDE" installed with the proper libraries (`Arduino.h`, `Arduino_BHY2.h`) for Nicla correct functioning to upload the sketch on a Nicla ME sense. Of course, in Arduino, one needs support for the Nicla board, that is installing in "Board Manager" `Arduino Mbed OS Nicla Boards`.

### Micro
The micro code runs on `python`. The libraries needed for the correct functioning of the system are:
- `bleak`
- `pynput`

## How to operate the system
Given the Nicla flashed with the `transmitter/transmitter.ino` code, the board will start looking for a BLE node to send data to.

The micro is the node that will accept data and log it in its internal memory. The code to operate the micro is `receiver/read_data.py`.

### Operation
The micro will first search for a device with an address specified in the `KNOWN_ADDRESSES` array at the beginning of the code. Please insert the address for the board in use.

Once found, the board will connect to the micro through BLE and will start notifying data. At any moment one can:
- `<ctrl>+c` to exit the data taking software.
- `<ctrl>+<alt>+n`, if the board is connected, to toggle notification.
- `<ctrl>+<alt>+p`, if the board is connected, to forcefully unpair the Nicla.

In the terminal, a logging is provided to monitor both sensor read and the status of the connection. If the connection is lost, the board will try to be reconnected automatically. A new file is generated for each connection in this version of the code.