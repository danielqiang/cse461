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
            self.handler_factory(callback=self.handle_step_a2)
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

    def handle_step_a2(self, handler: HookedHandler):
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
        packet_len = random.randint(1, 20)
        secret_a = self.generate_secret()
        port = self.random_port()

        # Listen to `port`
        server = socketserver.ThreadingUDPServer(
            (IP_ADDR, port),
            self.handler_factory(callback=self.handle_step_b2)
        )
        self.udp_servers[port] = server
        self.start_server(server)
        print(f"Started new UDP server on port {port}.")

        self.secrets[secret_a] = "a"  # This is a secret for stage A

        payload = struct.pack("!4I", num_packets, packet_len, port, secret_a)
        response = Packet(
            payload=payload,
            p_secret=0,
            step=2,
            student_id=packet.student_id
        )
        print(f"STEP A2: Sending response {response}")
        sock.sendto(response.bytes, handler.client_address)

    def handle_step_b2(self, handler: HookedHandler):
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
