import asyncio
import random
import time

import adafruit_connection_manager
import adafruit_requests
import adafruit_rfm9x
import adafruit_rgbled
import board
import busio
import microcontroller
import rtc
import storage
import supervisor
import usyslog
from adafruit_esp32spi import PWMOut, adafruit_esp32spi, adafruit_esp32spi_wifimanager
from APRS import APRS
from digitalio import DigitalInOut
from microcontroller import watchdog as w
from watchdog import WatchDogMode

import config

# software release (checks against OTA in GITHUB)
RELEASE = "1.0"

# stop autoreloading
supervisor.runtime.autoreload = False

# defaults
loraTimeout = 900
VERSION = "APRSiGate"


def _format_datetime(datetime):
    return "{:02}/{:02}/{} {:02}:{:02}:{:02}".format(
        datetime.tm_mon,
        datetime.tm_mday,
        datetime.tm_year,
        datetime.tm_hour,
        datetime.tm_min,
        datetime.tm_sec,
    )


def purple(data):
    stamp = "{}".format(_format_datetime(time.localtime()))
    return "\x1b[38;5;104m[" + str(stamp) + "] " + config.call + " " + data + "\x1b[0m"


def green(data):
    stamp = "{}".format(_format_datetime(time.localtime()))
    return (
        "\r\x1b[38;5;112m[" + str(stamp) + "] " + config.call + " " + data + "\x1b[0m"
    )


def blue(data):
    stamp = "{}".format(_format_datetime(time.localtime()))
    return "\x1b[38;5;14m[" + str(stamp) + "] " + config.call + " " + data + "\x1b[0m"


def yellow(data):
    return "\x1b[38;5;220m" + data + "\x1b[0m"


def red(data):
    stamp = "{}".format(_format_datetime(time.localtime()))
    return "\x1b[1;5;31m[" + str(stamp) + "] " + config.call + " " + data + "\x1b[0m"


def bgred(data):
    stamp = "{}".format(_format_datetime(time.localtime()))
    return "\x1b[41m[" + str(stamp) + "] " + config.call + data + "\x1b[0m"


# wait for console
time.sleep(2)

print("\x1b[1;5;31m -- " + f"{config.call} -=- {VERSION} {RELEASE}" + "\x1b[0m\n")

try:
    from secrets import secrets
except ImportError:
    print(red("WiFi secrets are kept in secrets.py, please add them there!"))
    raise

esp32_cs = DigitalInOut(board.GP17)
esp32_ready = DigitalInOut(board.GP14)
esp32_reset = DigitalInOut(board.GP13)

# Clock MOSI(TX) MISO(RX)
spi = busio.SPI(board.GP18, board.GP19, board.GP16)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
    print(yellow("ESP32 found and in idle mode"))
print(yellow("Firmware version: " + (esp.firmware_version)))
print(yellow("MAC addr: " + str([hex(i) for i in esp.MAC_address])))

RED_LED = PWMOut.PWMOut(esp, 25)
GREEN_LED = PWMOut.PWMOut(esp, 26)
BLUE_LED = PWMOut.PWMOut(esp, 27)
status_light = adafruit_rgbled.RGBLED(RED_LED, GREEN_LED, BLUE_LED)
esp.set_hostname(config.call + "-APRS-iGate")
wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)

## Connect to WiFi
print(yellow("Connecting to WiFi..."))
w.feed()
wifi.connect()
w.feed()
print(yellow("Connected!"))
apInfo = esp.ap_info

print(
    yellow(
        "Connected to: [" + str(apInfo.ssid, "utf-8") + "]\tRSSI:" + str(apInfo.rssi)
    )
)
w.feed()
print()

# Initialize a requests object with a socket and esp32spi interface
pool = adafruit_connection_manager.get_radio_socketpool(esp)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(esp)
requests = adafruit_requests.Session(pool, ssl_context)


# aprs auth packet
rawauthpacket = f"user {config.call} pass {config.passcode} vers {VERSION} {RELEASE}\n"

now = None
while now is None:
    try:
        now = time.localtime(esp.get_time()[0])
    except OSError:
        pass
rtc.RTC().datetime = now

# configure watchdog
w.timeout = 5
w.mode = WatchDogMode.RESET
w.feed()

if storage.getmount("/").readonly is False:
    try:
        UPDATE_URL = (
            "https://raw.githubusercontent.com/Guru-RF/LoRa433APRSiGate/main/ota"
        )
        response = requests.get(UPDATE_URL)

        if response.status_code == 200:
            OTARELEASE = response.content.decode("utf-8")
            if OTARELEASE != RELEASE:
                print(
                    yellow(
                        f"OTA update available old:{RELEASE} new:{OTARELEASE}, updating..."
                    )
                )

                # OTA update simplified
                UPDATE_URL = "https://raw.githubusercontent.com/Guru-RF/LoRa433APRSiGate/main/code.py"
                response = requests.get(UPDATE_URL)

                if response.status_code == 200:
                    print(yellow("OTA update available, downloading..."))
                    with open("ota.py", "wb") as f:
                        for chunk in response.iter_content(chunk_size=32):
                            f.write(chunk)
                            w.feed()
                    print(yellow("OTA update complete, restarting..."))
                    microcontroller.reset()
            else:
                print(yellow("no OTA update available"))
                print()
    except TimeoutError as error:
        print(yellow(f"OTA unavailable {error}"))
        print()

# usyslog
# until we cannot have multiple sockets open
# this can be used for debugging and reporting software updates
syslog = usyslog.UDPClient(
    pool,
    esp,
    hostname=config.call,
    host=config.syslogHost,
    port=config.syslogPort,
    process=VERSION + RELEASE,
)

if config.call == "":
    syslog.send("callsign missing!")
    print()
    print(red("callsign is empty, please set callsign in config.py"))
    while True:
        w.feed()
        time.sleep(1)

if config.passcode == "":
    syslog.send("callsign missing!")
    print()
    print(red("callsign is empty, please set passcode in config.py"))
    while True:
        w.feed()
        time.sleep(1)

syslog.send("Alive and kicking!")

# aprs
aprs = APRS()

# tx msg buffer
txmsgs = []

# configure tcp socket
s = pool.socket(type=pool.SOCK_STREAM)
s.settimeout(4)
socketaddr = pool.getaddrinfo(config.aprs_host, config.aprs_port)[0][4]


async def iGateAnnounce():
    # Periodically sends status packets and position packets to the APRS-IS server over TCP.
    # Handles reconnecting if the send fails.
    global w, s, rawauthpacket
    try:
        s.connect(socketaddr)
        s.settimeout(4)
        s.send(bytes(rawauthpacket, "utf-8"))
        w.feed()
    except Exception as error:
        print(bgred(f"init: An exception occurred: {error}"))
        print(
            purple(
                f"init: Connect to ARPS {config.aprs_host} {config.aprs_port} Failed ! Lost Packet ! Restarting System !"
            )
        )
        microcontroller.reset()
    while True:
        await asyncio.sleep(0)
        w.feed()
        temp = microcontroller.cpus[0].temperature
        freq = microcontroller.cpus[1].frequency / 1000000
        rawpacket = (
            f"{config.call}>APRFGI,TCPIP*:>Running on RP2040 t:{temp}C f:{freq}Mhz\n"
        )
        try:
            s.send(bytes(rawpacket, "utf-8"))
        except Exception as error:
            print(bgred(f"iGateStatus: An exception occurred: {error}"))
            print(
                purple(
                    f"iGateStatus: Reconnecting to ARPS {config.aprs_host} {config.aprs_port}"
                )
            )
            s.close()
            try:
                s.connect(socketaddr)
                w.feed()
                s.settimeout(4)
                s.send(bytes(rawauthpacket, "utf-8"))
                s.send(bytes(rawpacket, "utf-8"))
            except Exception as error:
                print(bgred(f"iGateStatus: An exception occurred: {error}"))
                syslog.send(f"iGateStatus: An exception occurred: {error}")
                print(
                    purple(
                        f"Connect to ARPS {config.aprs_host} {config.aprs_port} Failed ! Lost Packet ! Restarting system !"
                    )
                )
                microcontroller.reset()
        print(purple(f"iGateStatus: {rawpacket}"), end="")
        pos = aprs.makePosition(
            config.latitude, config.longitude, -1, -1, config.symbol
        )
        altitude = "/A={:06d}".format(int(config.altitude * 3.2808399))
        comment = VERSION + "." + RELEASE + " " + config.comment + altitude
        ts = aprs.makeTimestamp("z", now.tm_mday, now.tm_hour, now.tm_min, now.tm_sec)
        message = f"{config.call}>APRFGI,TCPIP*:@{ts}{pos}{comment}\n"
        try:
            w.feed()
            s.settimeout(4)
            s.send(bytes(message, "utf-8"))
        except Exception as error:
            print(bgred(f"iGateStatus: An exception occurred: {error}"))
            print(
                purple(
                    f"iGateStatus: Reconnecting to ARPS {config.aprs_host} {config.aprs_port}"
                )
            )
            s.close()
            try:
                s.connect(socketaddr)
                w.feed()
                s.settimeout(4)
                s.send(bytes(rawauthpacket, "utf-8"))
                s.send(bytes(message, "utf-8"))
            except Exception as error:
                print(bgred(f"iGateStatus: An exception occurred: {error}"))
                syslog.send(f"iGateStatus: An exception occurred: {error}")
                print(
                    purple(
                        f"iGateStatus: Connect to ARPS {config.aprs_host} {config.aprs_port} Failed ! Lost Packet ! Restarting system !"
                    )
                )
                microcontroller.reset()

        print(purple(f"iGatePossition: {message}"), end="")
        await asyncio.sleep(15 * 60)


async def tcpPost(packet):
    # Sends an APRS packet over TCP to the APRS-IS server.
    # Handles reconnecting if the send fails.
    global w, s, rawauthpacket
    w.feed()
    rawpacket = f"{packet}\n"
    try:
        await asyncio.sleep(0)
        s.settimeout(4)
        s.send(bytes(rawpacket, "utf-8"))
    except Exception as error:
        print(bgred(f"aprsTCPSend: An exception occurred: {error}"))
        print(
            purple(
                f"aprsTCPSend: Reconnecting to ARPS {config.aprs_host} {config.aprs_port}"
            )
        )
        s.close()
        try:
            s.connect(socketaddr)
            w.feed()
            s.settimeout(4)
            s.send(bytes(rawauthpacket, "utf-8"))
            s.send(bytes(rawpacket, "utf-8"))
        except Exception as error:
            print(bgred(f"aprsTCPSend: An exception occurred: {error}"))
            syslog.send(f"aprsTCPSend: An exception occurred: {error}")
            print(
                purple(
                    f"aprsTCPSend: Reconnecting to ARPS {config.aprs_host} {config.aprs_port} Failed ! Lost Packet ! Restarting system !"
                )
            )
            microcontroller.reset()
    print(blue(f"aprsTCPSend: {packet}"))
    await asyncio.sleep(0)


async def loraRunner(loop):
    await asyncio.sleep(5)
    global w, txmsgs
    # Continuously receives LoRa packets and forwards valid APRS packets
    # via WiFi. Configures LoRa radio, prints status messages, handles
    # exceptions, creates asyncio tasks to process packets.
    # LoRa APRS frequency
    RADIO_FREQ_MHZ = 433.775
    CS = DigitalInOut(board.GP21)
    RESET = DigitalInOut(board.GP20)
    spi = busio.SPI(board.GP10, MOSI=board.GP11, MISO=board.GP8)
    rfm9x = adafruit_rfm9x.RFM9x(
        spi, CS, RESET, RADIO_FREQ_MHZ, baudrate=1000000, agc=False, crc=True
    )
    rfm9x.tx_power = 5

    time.monotonic() - 900

    while True:
        await asyncio.sleep(0)
        # reboot weekly
        if time.monotonic() > 604800:
            microcontroller.reset()
        w.feed()
        timeout = int(loraTimeout) + random.randint(1, 9)
        print(
            purple(f"loraRunner: Waiting for lora APRS packet timeout:{timeout} ...\r"),
            end="",
        )
        # packet = rfm9x.receive(w, with_header=True, timeout=timeout)
        packet = await rfm9x.areceive(w, with_header=True, timeout=timeout)
        if packet is not None:
            if packet[:3] == (b"<\xff\x01"):
                try:
                    rawdata = bytes(packet[3:]).decode("utf-8")
                    print(
                        green(
                            f"loraRunner: RX: RSSI:{rfm9x.last_rssi} SNR:{rfm9x.last_snr} Data:{rawdata}"
                        )
                    )
                    #                    syslog.send(
                    #                        f"loraRunner: RX: RSSI:{rfm9x.last_rssi} SNR:{rfm9x.last_snr} Data:{rawdata}"
                    #                    )
                    wifi.pixel_status((100, 100, 0))
                    loop.create_task(tcpPost(rawdata))
                    await asyncio.sleep(0)
                    wifi.pixel_status((0, 100, 0))
                except Exception as error:
                    print(bgred(f"loraRunner: An exception occurred: {error}"))
                    syslog.send(f"loraRunner: An exception occurred: {error}")
                    print(purple("loraRunner: Lost Packet, unable to decode, skipping"))
                    continue


async def main():
    # Create asyncio tasks to run the LoRa receiver, APRS message feed,
    # and iGate announcement in parallel. Gather the tasks and wait for
    # them to complete wich will never happen ;)
    loop = asyncio.get_event_loop()
    loraR = asyncio.create_task(loraRunner(loop))
    loraA = asyncio.create_task(iGateAnnounce())
    await asyncio.gather(loraA, loraR)


asyncio.run(main())
