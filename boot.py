# Configures board on boot:
# - Checks if config button is pressed
#   - If pressed, enables USB drive and console
#   - If not pressed, disables USB drive and enables console
# - Remounts filesystem as read-only
# - Install OTA updates after reboot
# - Sets USB drive name if enabled
import os

import board
import storage
import usb_cdc
from digitalio import DigitalInOut, Direction, Pull

# config button
btn = DigitalInOut(board.GP15)
btn.direction = Direction.INPUT
btn.pull = Pull.UP


def file_or_dir_exists(filename):
    try:
        os.stat(filename)
        return True
    except OSError:
        return False


# default disable usb drive
if btn.value is True:
    print("boot: button not pressed, disabling drive")
    storage.disable_usb_drive()
    storage.remount("/", readonly=False)

    usb_cdc.enable(console=True, data=False)
    if file_or_dir_exists("ota.py"):
        print("boot: installing new release")
        os.remove("code.py")
        os.rename("ota.py", "code.py")


else:
    print("boot: button pressed, enable console, enabling drive")

    usb_cdc.enable(console=True, data=False)

    new_name = "APRSGATE"
    storage.remount("/", readonly=False)
    m = storage.getmount("/")
    m.label = new_name
    storage.remount("/", readonly=True)
