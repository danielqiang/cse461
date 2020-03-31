from cse461.project1.consts import IP_ADDR
from cse461.project1.packet import Packet
import socketserver


class UDPHandler(socketserver.DatagramRequestHandler):
    def handle(self):
        data, sock = self.request

        packet = Packet.from_raw(data)
        print(f"Received packet {repr(packet)}")

        print(dir(sock))
        # sock.send(packet.bytes)


if __name__ == '__main__':
    PORT = 12235

    with socketserver.ThreadingUDPServer((IP_ADDR, PORT), UDPHandler) as server:
        print(f"Listening at {IP_ADDR}:{PORT}.")
        server.serve_forever()
