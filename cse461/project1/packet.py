import struct
from typing import Optional

__all__ = ['Packet']


class Packet:
    def __init__(self,
                 payload: Optional[bytes],
                 p_secret: int,
                 step: int,
                 student_id: int,
                 payload_len: int = None):
        """
        Constructs a Packet. Packets are written in network order (big-endian)
        and are 4-byte aligned.

        :param payload: Payload to include in the constructed packet. If None,
                    returns an uninitialized Packet (all attributes are None).
        :param p_secret: Secret for previous stage of protocol (0 for stage a,
                    randomly generated for successive stages)
        :param step: Stage step of protocol (e.g. for step a1, `step` is 1)
        :param student_id: Last 3 digits of student id number.
        :param payload_len: Length of payload. If None, uses len(payload) as payload_len.
                    (Specify when using null-terminated strings)
        """
        if payload is None:
            self.bytes = None
            self.header = None
            self.payload = None
            self.payload_len = None
            self.p_secret = None
            self.step = None
            self.student_id = None
            return

        if payload_len is None:
            payload_len = len(payload)
        # Byte-align the payload.
        payload = struct.pack(f"{payload_len}s0I", payload)
        # Build the packet in network byte order
        _bytes = struct.pack(f"!IIHH{len(payload)}s",
                             payload_len,
                             p_secret,
                             step,
                             student_id,
                             payload)

        self.bytes = _bytes
        self.header = _bytes[:12]
        self.payload = payload
        self.payload_len = payload_len
        self.p_secret = p_secret
        self.step = step
        self.student_id = student_id

    def __str__(self):
        return str(self.bytes)

    def __repr__(self):
        # Dump all attributes in a pretty printed string
        attrs = ",\n\t".join(f"{k}={v}" for k, v in sorted(self.__dict__.items()))
        return f"Packet(\n\t{attrs}\n)"

    @staticmethod
    def from_raw(data: bytes):
        """
        Constructs a Packet directly from `data`.

        :param data: Raw data to directly construct a Packet with.
        :raises: ValueError if `data` cannot be interpreted as a valid Packet.
        :rtype: Packet
        """
        # Sanity checks
        if len(data) < 12:
            raise ValueError("`data` must have a 12-byte header.")
        if len(data) % 4 != 0:
            raise ValueError("`data` must be 4-byte aligned.")

        header = data[:12]
        payload = data[12:]
        payload_len, p_secret, step, student_id = struct.unpack("!IIHH", header)

        packet = Packet(None, 0, 0, 0)
        packet.bytes = data
        packet.header = header
        packet.payload = payload
        packet.p_secret = p_secret
        packet.step = step
        packet.student_id = student_id
        packet.payload_len = payload_len

        return packet
