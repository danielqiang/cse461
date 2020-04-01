import socket
import struct
import logging

from cse461.project1.consts import IP_ADDR
from cse461.project1.packet import Packet

__all__ = ['Client']
logger = logging.getLogger(__name__)


class Client:
    def __init__(self, student_id: int):
        self.p_secret = 0
        self.step = 1
        self.student_id = student_id
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def stage_a(self, port: int) -> Packet:
        packet = Packet(
            payload=b'hello world\0',
            p_secret=self.p_secret,
            step=self.step,
            student_id=self.student_id,
            payload_len=11
        )
        logger.info(f"[Stage A] Sending packet {packet} to {IP_ADDR}:{port}")
        self.udp_socket.sendto(packet.bytes, (IP_ADDR, port))

        return Packet.from_raw(self.udp_socket.recv(1024))

    def stage_b(self, response: Packet) -> Packet:
        num, length, udp_port, secret_a = struct.unpack("!4I", response.payload)
        # For stage b, unacknowledged packets should be re-sent
        # after 0.5 seconds.
        self.udp_socket.settimeout(0.5)

        packet_id = 0
        while packet_id < 0:
            payload = struct.pack(f"!I{length}s", packet_id, b'\0' * length)
            packet = Packet(
                payload=payload,
                p_secret=secret_a,
                step=self.step,
                student_id=self.student_id
            )
            logger.info(f"[Stage B] Sending packet {packet} to {IP_ADDR}:{udp_port}")
            self.udp_socket.sendto(packet.bytes, (IP_ADDR, udp_port))

            try:
                response_packet = Packet.from_raw(self.udp_socket.recv(1024))
                ack = struct.unpack("!I", response_packet.payload)[0]

                if ack == packet_id:
                    logger.info(f"[Stage B] Packet acknowledged (id: {packet_id})")
                    packet_id += 1
                else:
                    logger.info(f"[Stage B] Packet (id: {packet_id}) not acknowledged: "
                                f"expected payload {packet_id}, got {ack}. Retrying.")
            except socket.timeout:
                logger.info(f"[Stage B] Packet dropped (id: {packet_id}). Retrying.")

        self.udp_socket.settimeout(None)
        return Packet.from_raw(self.udp_socket.recv(1024))

    def stage_c(self, response: Packet) -> Packet:
        tcp_port, secret_b = struct.unpack("!II", response.payload)
        self.tcp_socket.connect((IP_ADDR, tcp_port))

        return Packet.from_raw(self.tcp_socket.recv(1024))

    def stage_d(self, response: Packet) -> Packet:
        pass

    def start(self, port=12235):
        resp = self.stage_a(port)
        resp = self.stage_b(resp)
        resp = self.stage_c(resp)

        num2, len2, secret_c, c = struct.unpack("!3I4s", resp.payload)
        logger.debug((num2, len2, secret_c, c))

        resp = self.stage_d(resp)

    def stop(self):
        self.udp_socket.close()
        self.tcp_socket.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()


def main():
    with Client(student_id=592) as client:
        client.start()


if __name__ == '__main__':
    main()
