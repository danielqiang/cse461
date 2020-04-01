import socketserver
import threading
import random
import struct

from typing import Callable
from cse461.project1.packet import Packet
from cse461.project1.consts import IP_ADDR

__all__ = ['Server']


class HookedHandler(socketserver.BaseRequestHandler):
    def __init__(self, callback: Callable, *args, **kwargs):
        self.callback = callback
        super().__init__(*args, **kwargs)

    def handle(self):
        self.callback(self)


class Server:
    def __init__(self):
        self.secrets = {}
        self.tcp_servers = {}
        self.udp_servers = {}
        self.threads = set()

    def start(self):
        server = socketserver.ThreadingUDPServer(
            (IP_ADDR, 12235),
            self.handler_factory(callback=self.handle_stage_a)
        )
        self.udp_servers[12235] = server
        self.start_server(server)
        print("Started new UDP server on port 12235.")

    def start_server(self, server: socketserver.BaseServer):
        t = threading.Thread(target=server.serve_forever)
        t.start()
        self.threads.add(t)

    def stop(self):
        # UDP servers don't need to be closed.
        for tcp_server in self.tcp_servers.values():
            tcp_server.server_close()

    @staticmethod
    def handler_factory(callback):
        def handler(*args, **kwargs):
            return HookedHandler(callback, *args, **kwargs)

        return handler

    def handle_stage_a(self, handler: HookedHandler):
        data, sock = handler.request

        print(f"Received data {data}")
        try:
            packet = Packet.from_raw(data)
            assert packet.payload.lower() == b'hello world\0'
            assert packet.p_secret == 0
            assert packet.step == 1
        except ValueError as e:
            # Packet is malformed
            print(e)
            return
        except AssertionError:
            # Packet doesn't satisfy step a1
            return

        num_packets = random.randint(1, 10)
        # Guarantee that packet_len is a multiple of 4.
        packet_len = random.randint(1, 10) * 4
        secret_a = self.generate_secret()
        udp_port = self.random_port()

        # Listen to `udp_port`
        server = socketserver.ThreadingUDPServer(
            (IP_ADDR, udp_port),
            self.handler_factory(callback=self.handle_stage_b)
        )
        self.udp_servers[udp_port] = server
        self.start_server(server)
        print(f"Started new UDP server on port {udp_port}.")

        # Map secret for stage A to relevant data for stage B
        self.secrets[secret_a] = {
            "stage": "a",
            "num_packets": num_packets,
            # Number of packets that the server is still expecting to receive
            "remaining_packets": num_packets,
            "packet_len": packet_len
        }

        payload = struct.pack("!4I", num_packets, packet_len, udp_port, secret_a)
        response = Packet(
            payload=payload,
            p_secret=0,
            step=2,
            student_id=packet.student_id
        )
        sock.sendto(response.bytes, handler.client_address)

        print(f"STEP A2: Sent response {response}")

    def handle_stage_b(self, handler: HookedHandler):
        data, sock = handler.request

        print(f"Received data {data}")
        try:
            packet = Packet.from_raw(data)
            assert packet.step == 1
            assert packet.p_secret in self.secrets

            stage = self.secrets[packet.p_secret]["stage"]
            num_packets = self.secrets[packet.p_secret]["num_packets"]
            remaining_packets = self.secrets[packet.p_secret]["remaining_packets"]
            packet_len = self.secrets[packet.p_secret]['packet_len']

            assert stage == "a"
            assert len(packet.payload) == packet_len + 4

            packet_id = struct.unpack("!I", packet.payload[:4])[0]
            assert remaining_packets + packet_id == num_packets
        except (ValueError, AssertionError) as e:
            # Packet is malformed or does not satisfy stage b
            print(e)
            return

        if remaining_packets > 0:
            self.secrets[packet.p_secret]["remaining_packets"] -= 1
            ack = Packet(
                payload=packet.payload[:4],
                p_secret=packet.p_secret,
                step=2,
                student_id=packet.student_id
            )
            sock.sendto(ack.bytes, handler.client_address)

            print(f"Acknowledged packet with packet id {packet_id}")
        if self.secrets[packet.p_secret]["remaining_packets"] == 0:
            # Delete secret for part A; they shouldn't need it anymore.
            del self.secrets[packet.p_secret]

            tcp_port = self.random_port()
            server = socketserver.ThreadingTCPServer(
                (IP_ADDR, tcp_port),
                self.handler_factory(callback=self.handle_stage_c)
            )
            self.tcp_servers[tcp_port] = server
            self.start_server(server)

            secret_b = self.generate_secret()
            self.secrets[secret_b] = {"stage": "b"}

            payload = struct.pack("!2I", tcp_port, secret_b)
            response = Packet(
                payload=payload,
                p_secret=packet.p_secret,
                step=2,
                student_id=packet.student_id
            )
            sock.sendto(response.bytes, handler.client_address)

            print(f"STEP B2: Sent response {response}")

    def handle_step_c2(self, handler: HookedHandler):
        data, sock = handler.request

        print(f"Received data {data}")
        try:
            packet = Packet.from_raw(data)
            # assert packet.payload.lower() == b'hello world\0'
            # assert packet.p_secret == 0
            assert packet.step == 1
        except ValueError as e:
            # Packet is malformed
            print(e)
            return
        except AssertionError:
            # Packet doesn't satisfy step a1
            return

        num2 = random.randint(1, 10)
        len2 = random.randint(1, 40)
        secret_c = self.generate_secret()
        c = 'c'

        payload = struct.pack("!3Ib", num2, len2, secret_c, c)
        response = Packet(
            payload=payload,
            p_secret=packet.p_secret,
            step=2,
            student_id=packet.student_id
        )
        print(f"STEP A2: Sending response {response}")
        sock.sendto(response.bytes, handler.client_address)

    def handle_step_d(self, handler: HookedHandler):
        pass
    def generate_secret(self) -> int:
        """Generates a unique, cryptographically secure secret."""
        from secrets import randbits

        while True:
            secret = randbits(32)
            if secret not in self.secrets:
                return secret

    def random_port(self) -> int:
        """Returns a unique random port."""
        while True:
            port = random.randint(1024, 49151)
            if port not in self.udp_servers and port not in self.tcp_servers:
                return port

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()


def main():
    with Server() as server:
        server.start()


if __name__ == '__main__':
    main()
