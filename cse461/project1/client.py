from cse461.project1.consts import IP_ADDR
from cse461.project1.packet import Packet
import socket
import struct
import time
__all__ = ['Client']


class Client:
    pass


def main():
    p_secret = 0
    step = 1
    student_id = 592
    packet = Packet(b'Hello World', p_secret, step, student_id)

    print(f"Sending packet {packet} to {IP_ADDR}:{12235}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(packet.bytes, (IP_ADDR, 12235))

    data = sock.recv(1024)
    response_packet = Packet.from_raw(data)
    num, length, udp_port, secret_a = struct.unpack("!4I", response_packet.payload)
    print({udp_port})

    # Stage b
    p_secret = secret_a     # reassign secret
    length = length + 4
    packet_id = 0
    while packet_id < num:     # send num packets  Stage b1

        payload = struct.pack("!2I", packet_id, length)
        packet = Packet(payload, p_secret, step, student_id)
        sock.sendto(packet.bytes, (IP_ADDR, udp_port)) # maybe just udp_port

        time.sleep(0.5)  # retransmission interval??

        data = sock.recv(1024)
        response_packet = Packet.from_raw(data)
        acked_packet_id = struct.unpack("!1I", response_packet.payload)
        if acked_packet_id == packet_id:
            packet_id += 1

    # Step b2
    data = sock.recv(1024)
    response_packet = Packet.from_raw(data)
    tcp_port, secretB = struct.unpack("!2I", response_packet.payload)
    p_secret = secretB  # reassigned p_secret
    connected = False
    while not connected:
        try:
            sock.connect((IP_ADDR, tcp_port))
            connected = True
        except Exception as e:
            pass

    # do stage C

    sock.close()




if __name__ == '__main__':
    main()
