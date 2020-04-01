import socket
import struct

from cse461.project1.consts import IP_ADDR
from cse461.project1.packet import Packet

__all__ = ['Client']


class Client:
    def __init__(self, student_id: int):
        self.p_secret = 0
        self.step = 1
        self.student_id = student_id
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def stage_a(self) -> Packet:
        packet = Packet(
            payload=b'hello world\0',
            p_secret=self.p_secret,
            step=self.step,
            student_id=self.student_id,
            payload_len=11
        )
        print(f"Sending packet {packet} to {IP_ADDR}:{12235}")
        self.udp_socket.sendto(packet.bytes, (IP_ADDR, 12235))

        return Packet.from_raw(self.udp_socket.recv(1024))

    def stage_b(self, response: Packet) -> Packet:
        num, length, udp_port, secret_a = struct.unpack("!4I", response.payload)

        for packet_id in range(num):  # send num packets  Stage b1
            payload = struct.pack(f"!I{length}s", packet_id, b'\0' * length)
            packet = Packet(
                payload=payload,
                p_secret=secret_a,
                step=self.step,
                student_id=self.student_id
            )
            self.udp_socket.sendto(packet.bytes, (IP_ADDR, udp_port))

            response_packet = Packet.from_raw(self.udp_socket.recv(1024))
            packet_id += 1

            acked_packet_id = struct.unpack("!I", response_packet.payload)[0]
            print(f"acked_packet_id: {acked_packet_id}")
        return Packet.from_raw(self.udp_socket.recv(1024))

    def stage_c(self, response: Packet) -> Packet:
        pass

    def stage_d(self, response: Packet) -> Packet:
        pass

    def start(self):
        resp = self.stage_a()
        resp = self.stage_b(resp)
        resp = self.stage_c(resp)
        resp = self.stage_d(resp)

    def stop(self):
        self.udp_socket.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()


def main():
    with Client(student_id=592) as client:
        client.start()


if __name__ == '__main__':
    main()
