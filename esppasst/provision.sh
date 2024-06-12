#!/bin/bash

DIR="/Volumes/RPI-RP2"
if [ -d "$DIR" ]; then
  echo "Installing passthrough firmwire to rp2040 in ${DIR}..."
  cp serial_passthrough.uf2 /Volumes/RPI-RP2
  echo "Sleeping 20 seconds for passthrough firmware to install"
  sleep 20
fi

esptool.py --port /dev/tty.usbmodem* --baud 115200 --before no_reset write_flash 0 NINA_W102-1.7.7.bin
