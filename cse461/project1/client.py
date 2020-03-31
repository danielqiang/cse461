from cse461.project1.consts import IP_ADDR
from cse461.project1.packet import Packet
import socket

__all__ = ['Client']


class Client:
    pass


def main():
    p_secret = 0
    step = 1
    student_id = 592
    packet = Packet(b'Hello World\0', p_secret, step, student_id, payload_len=11)

    print(f"Sending packet {packet} to {IP_ADDR}:{12235}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(packet.bytes, (IP_ADDR, 12235))
    data = sock.recv(1024)
    print(f"Received {data}")


if __name__ == '__main__':
    main()
