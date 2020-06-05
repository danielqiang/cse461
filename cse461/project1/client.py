import socket
import struct
import logging

from cse461.project1.packet import Packet
from cse461.project1.consts import CLIENT_ADDR, START_PORT, STUDENT_ID

__all__ = ['Client']
logger = logging.getLogger(__name__)


class Client:
    """Client implementation for protocol outlined in CSE 461 SPR 2020
    Project 1 (Sockets API).

    Usage:
    >>> client = Client(student_id=123, ip_addr='localhost')
    >>> secrets = client.run()
    >>> # Do stuff with secrets
    >>> client.stop()

    Or as a context manager:
    >>> with Client(student_id=123, ip_addr='localhost') as client:
    ...     secrets = client.run()
    ...     # Do stuff with secrets

    Student ID and server IP address can be set in consts.py and will be
    automatically configured in Client:
    >>> with Client() as client:
    ...     client.run()
    ...     # Do stuff with secrets
    """

    def __init__(self, student_id: int = STUDENT_ID, ip_addr: str = CLIENT_ADDR):
        """
        Constructor. Creates a client that will run through the protocol once.

        :param student_id: Last 3 digits of student ID to include in all
                        packet headers sent from this client. Defaults to
                        consts.STUDENT_ID.
        :param ip_addr: IP Address to send all packets to. Defaults to
                        consts.CLIENT_ADDR.
        """
        self.step = 1
        self.secrets = {}
        self.student_id = student_id
        self.ip_addr = ip_addr
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Set in stage C, used in stage D
        self.tcp_port = None

    def stage_a(self, port: int = START_PORT) -> Packet:
        packet = Packet(
            payload=b'hello world\0',
            p_secret=0,
            step=self.step,
            student_id=self.student_id
        )
        logger.info(f"[Stage A] Sending packet {packet} to {self.ip_addr}:{port}")
        self.udp_socket.sendto(packet.bytes, (self.ip_addr, port))
        packet = Packet.from_raw(self.udp_socket.recv(1024))
        secret = struct.unpack("!I", packet.payload[-4:])[0]
        self.secrets['a'] = secret

        logger.info("[Stage A] Finished.")
        return packet

    def stage_b(self, response: Packet) -> Packet:
        num, length, udp_port, secret_a = struct.unpack("!4I", response.payload)
        # For stage b, unacknowledged packets should be re-sent
        # after 0.5 seconds.
        self.udp_socket.settimeout(0.5)

        for packet_id in range(num):
            while True:
                payload = struct.pack(f"!I{length}s", packet_id, b'\0' * length)
                packet = Packet(
                    payload=payload,
                    p_secret=secret_a,
                    step=self.step,
                    student_id=self.student_id
                )
                logger.info(f"[Stage B] Sending packet {packet} to {self.ip_addr}:{udp_port}")
                self.udp_socket.sendto(packet.bytes, (self.ip_addr, udp_port))
                try:
                    response_packet = Packet.from_raw(self.udp_socket.recv(1024))
                    ack = struct.unpack("!I", response_packet.payload)[0]

                    if ack == packet_id:
                        logger.info(f"[Stage B] Packet acknowledged (id: {packet_id})")
                        break
                    else:
                        logger.info(f"[Stage B] Packet (id: {packet_id}) not acknowledged: "
                                    f"expected payload {packet_id}, got {ack}. Retrying.")
                except socket.timeout:
                    logger.info(f"[Stage B] Packet dropped (id: {packet_id}). Retrying.")
        self.udp_socket.settimeout(None)
        packet = Packet.from_raw(self.udp_socket.recv(1024))
        secret = struct.unpack("!I", packet.payload[-4:])[0]
        self.secrets['b'] = secret

        logger.info("[Stage B] Finished.")
        return packet

    def stage_c(self, response: Packet) -> Packet:
        tcp_port, secret_b = struct.unpack("!II", response.payload)
        self.tcp_socket.connect((self.ip_addr, tcp_port))
        self.tcp_port = tcp_port

        logger.info(f"[Stage C] Connected to TCP socket at {self.ip_addr}:{tcp_port}")
        packet = Packet.from_raw(self.tcp_socket.recv(1024))

        secret = struct.unpack("!I", packet.payload[-4:])[0]
        self.secrets['c'] = secret

        logger.info("[Stage C] Finished.")
        return packet

    def stage_d(self, response: Packet):
        num2, len2, secret_c, char = struct.unpack("!3I4s", response.payload)
        packet = Packet(
            payload=bytes([char[0]]) * len2,
            p_secret=secret_c,
            step=self.step,
            student_id=self.student_id
        )

        logger.info(f"[Stage D] Sending {num2} packets with data {packet.bytes} "
                    f"to {self.ip_addr}:{self.tcp_port}")
        self.tcp_socket.sendall(packet.bytes * num2)

        packet = Packet.from_raw(self.tcp_socket.recv(1024))
        secret = struct.unpack("!I", packet.payload[-4:])[0]
        self.secrets['d'] = secret

        logger.info("[Stage D] Finished.")

    def start(self, port=START_PORT):
        logger.info(f"[Start] Starting protocol. Connecting to server at {self.ip_addr}.")
        resp = self.stage_a(port)
        resp = self.stage_b(resp)
        resp = self.stage_c(resp)
        self.stage_d(resp)

        logger.info(f"[Complete] Acquired secrets: {self.secrets}")
        return self.secrets

    def stop(self):
        self.udp_socket.close()
        self.tcp_socket.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()


def main():
    with Client(ip_addr='localhost') as client:
        client.start()


if __name__ == '__main__':
    main()
