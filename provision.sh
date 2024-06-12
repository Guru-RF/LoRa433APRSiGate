#!/bin/bash

DIR="/Volumes/RPI-RP2"
if [ -d "$DIR" ]; then
  echo "Installing firmwire to rp2040 in ${DIR}..."
  cd /tmp
  wget https://downloads.circuitpython.org/bin/raspberry_pi_pico/en_US/adafruit-circuitpython-raspberry_pi_pico-en_US-9.0.4.uf2
  cp adafruit-circuitpython-raspberry_pi_pico-en_US-9.0.4.uf2 /Volumes/RPI-RP2
  rm adafruit-circuitpython-raspberry_pi_pico-en_US-9.0.4.uf2
  echo "Sleeping 20 seconds for firmware to install"
  cd -
  sleep 20
fi

DIR="/Volumes/CIRCUITPY"
if [ -d "$DIR" ]; then
  echo "Install software in ${DIR}..."
  cp -r lib /Volumes/CIRCUITPY
  cp boot.py /Volumes/CIRCUITPY
  echo "1" > /Volumes/CIRCUITPY/sequence
  cp config.py /Volumes/CIRCUITPY
  cp code.py /Volumes/CIRCUITPY
  cp secrets.py /Volumes/CIRCUITPY
  sync
  diskutil unmount /Volumes/CIRCUITPY
  echo "done"
fi

DIR="/Volumes/APRSGATE"
if [ -d "$DIR" ]; then
  echo "Updating software in ${DIR}..."
  cp -r lib /Volumes/APRSGATE
  cp boot.py /Volumes/APRSGATE
  cp code.py /Volumes/APRSGATE
  sync
  diskutil unmount /Volumes/APRSGATE
  echo "done"
fi
