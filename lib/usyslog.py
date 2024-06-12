"""
This syslog client can send UDP packets to a remote syslog server.
Timestamps are not supported for simplicity. For more information, see RFC 3164.
"""

import time

_MONTHNAMES = (
    None,
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


class SyslogClient:
    def __init__(self, process="rp2040[0]"):
        self._process = process

    def _format_datetime(self, datetime):
        return "{:3} {:2d} {:02d}:{:02d}:{:02d}".format(
            _MONTHNAMES[datetime.tm_mon],
            datetime.tm_mday,
            datetime.tm_hour,
            datetime.tm_min,
            datetime.tm_sec,
        )

    def log(self, message):
        """Log a message with the given severity."""
        data = "{} {} {}: {}".format(
            self._format_datetime(time.localtime()),
            self._hostname,
            self._process,
            message,
        )
        self._sock.send(data.encode())

    def send(self, message):
        self._sock.connect(self._socketaddr, conntype=self._esp.UDP_MODE)
        self.log(message)
        self._sock.close()


class UDPClient(SyslogClient):
    def __init__(
        self,
        pool,
        esp,
        hostname="unknown",
        host="127.0.0.1",
        port=514,
        process="rp2040[0]",
    ):
        super().__init__(process)

        self._esp = esp
        self._hostname = hostname
        self._sock = pool.socket(type=pool.SOCK_DGRAM)
        self._socketaddr = pool.getaddrinfo(host, port)[0][4]
        self._sock.settimeout(4)
