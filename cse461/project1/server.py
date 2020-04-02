import socketserver
import threading
import logging
import random
import struct

from typing import Callable
from cse461.project1.packet import Packet
from cse461.project1.consts import IP_ADDR

__all__ = ['Server']
logger = logging.getLogger(__name__)


class HookedHandler(socketserver.BaseRequestHandler):
    def __init__(self, callback: Callable, callback_args: tuple = (), *args, **kwargs):
        self.callback = callback
        self.callback_args = callback_args
        super().__init__(*args, **kwargs)

    def handle(self):
        self.callback(self, *self.callback_args)


class Server:
    # TODO: Possible issue where a client receives the same secret twice
    def __init__(self):
        self.secrets = {}
        self.tcp_servers = {}
        self.udp_servers = {}
        self.threads = set()
        self._lock = threading.Lock()

        # Unfortunately, we can't use standard decorator syntax to wrap instance methods
        self.handle_stage_a = self.synchronized(self.handle_stage_a, self._lock)
        self.handle_stage_b = self.synchronized(self.handle_stage_b, self._lock)
        self.handle_stage_c = self.synchronized(self.handle_stage_c, self._lock)
        self.handle_stage_d = self.synchronized(self.handle_stage_d, self._lock)

    @staticmethod
    def synchronized(method: Callable, lock: threading.Lock):
        """
        Method wrapper that acquires `lock` prior to executing `method` and
        releases it upon completion or if an exception occurs.
        """
        from functools import wraps

        @wraps(method)
        def wrapped(*args, **kwargs):
            with lock:
                return method(*args, **kwargs)

        return wrapped

    def start(self, port=12235):
        server = socketserver.ThreadingUDPServer(
            (IP_ADDR, port),
            self.handler_factory(callback=self.handle_stage_a)
        )
        self.udp_servers[port] = server
        self.start_server(server)
        logger.info(f"[Begin] Started new UDP server on port {port}.")

    def start_server(self, server: socketserver.BaseServer):
        # TODO: Add threading stop Event to effectively clean up threads
        t = threading.Thread(target=server.serve_forever)
        t.start()
        self.threads.add(t)

    def stop(self):
        # UDP servers don't need to be closed.
        for tcp_server in self.tcp_servers.values():
            tcp_server.server_close()

    @staticmethod
    def handler_factory(callback: Callable, callback_args: tuple = ()):
        def handler(*args, **kwargs):
            return HookedHandler(callback, callback_args, *args, **kwargs)

        return handler

    def handle_stage_a(self, handler: HookedHandler):
        data, sock = handler.request

        logger.info(f"[Stage A] Received packet {data} from "
                    f"{handler.client_address[0]}:{handler.client_address[1]}")
        try:
            packet = Packet.from_raw(data)
        except ValueError as e:
            # Packet is malformed
            logger.info(e)
            return

        if (packet.payload.lower() != b'hello world\0' or
                packet.p_secret != 0 or
                packet.step != 1):
            # Packet doesn't satisfy step a1
            return

        num_packets = random.randint(5, 10)
        # Guarantee that packet_len is a multiple of 4.
        packet_len = random.randint(1, 10) * 4
        secret_a = self.generate_secret()
        udp_port = self.random_port()

        server = socketserver.ThreadingUDPServer(
            (IP_ADDR, udp_port),
            self.handler_factory(callback=self.handle_stage_b)
        )
        self.udp_servers[udp_port] = server
        self.start_server(server)
        logger.info(f"[Stage A] Started new UDP server on port {udp_port}.")

        # For stage B, don't acknowledge at least one packet
        ack_fails = set(random.sample(
            range(num_packets),
            k=random.randint(1, min(4, num_packets)))
        )
        # Store relevant data for stage B
        self.secrets[secret_a] = {
            'prev_stage': "a",
            "num_packets": num_packets,
            # Number of packets that the server is still expecting to receive
            "remaining_packets": num_packets,
            # Packets that we should drop once
            "ack_fails": ack_fails,
            "packet_len": packet_len
        }

        payload = struct.pack("!4I", num_packets, packet_len, udp_port, secret_a)
        response = Packet(
            payload=payload,
            p_secret=0,
            step=2,
            student_id=packet.student_id
        )
        logger.info(f"[Stage A] Sending packet {response} "
                    f"to {handler.client_address[0]}:{handler.client_address[1]}")
        sock.sendto(response.bytes, handler.client_address)

    def handle_stage_b(self, handler: HookedHandler):
        data, sock = handler.request

        logger.info(f"[Stage B] Received packet {data} from "
                    f"{handler.client_address[0]}:{handler.client_address[1]}")
        try:
            packet = Packet.from_raw(data)
        except ValueError as e:
            # Malformed packet
            logger.info(e)
            return
        try:
            prev_stage = self.secrets[packet.p_secret]['prev_stage']
            num_packets = self.secrets[packet.p_secret]["num_packets"]
            remaining_packets = self.secrets[packet.p_secret]["remaining_packets"]
            ack_fails = self.secrets[packet.p_secret]["ack_fails"]
            packet_len = self.secrets[packet.p_secret]['packet_len']

            packet_id = struct.unpack("!I", packet.payload[:4])[0]
        except KeyError:
            logger.info(f"Unrecognized secret: {packet.p_secret}")
            return
        except struct.error:
            logger.info("Packet payload must be at least 4 bytes long")
            return
        # Ensure that this packet is a valid packet for step b1
        if (packet.step != 1 or
                prev_stage != "a" or
                packet_len + 4 != len(packet.payload) or
                remaining_packets + packet_id != num_packets):
            return

        if remaining_packets > 0:
            if packet_id in ack_fails:
                logger.info(f"[Stage B] Dropping packet with id {packet_id}")
                ack_fails.remove(packet_id)
            else:
                logger.info(f"[Stage B] Acknowledging packet with id {packet_id}")
                self.secrets[packet.p_secret]["remaining_packets"] -= 1
                ack = Packet(
                    payload=packet.payload[:4],
                    p_secret=packet.p_secret,
                    step=2,
                    student_id=packet.student_id
                )

                sock.sendto(ack.bytes, handler.client_address)

        if self.secrets[packet.p_secret]["remaining_packets"] == 0:
            secret_b = self.generate_secret()
            self.secrets[secret_b] = {'prev_stage': "b"}
            del self.secrets[packet.p_secret]

            tcp_port = self.random_port()
            payload = struct.pack("!II", tcp_port, secret_b)
            response = Packet(
                payload=payload,
                p_secret=secret_b,
                step=2,
                student_id=packet.student_id
            )
            server = socketserver.ThreadingTCPServer(
                (IP_ADDR, tcp_port),
                self.handler_factory(callback=self.handle_stage_c, callback_args=(response,))
            )
            self.tcp_servers[tcp_port] = server
            self.start_server(server)

            logger.info(f"[Stage B] Sending packet {response} "
                        f"to {handler.client_address[0]}:{handler.client_address[1]}")
            sock.sendto(response.bytes, handler.client_address)

    def handle_stage_c(self, handler: HookedHandler, packet: Packet):
        from secrets import token_bytes

        sock = handler.request

        num2 = random.randint(1, 10)
        len2 = random.randint(1, 40)
        secret_c = self.generate_secret()
        char = token_bytes(1)

        self.secrets[secret_c] = {
            "num2": num2,
            "len2": len2,
            "char": char
        }
        del self.secrets[packet.p_secret]
        payload = struct.pack("!3I4s", num2, len2, secret_c, char)

        response = Packet(
            payload=payload,
            p_secret=packet.p_secret,
            step=2,
            student_id=packet.student_id
        )
        logger.info(f"[Stage C] Sending packet {response} "
                    f"to {handler.client_address[0]}:{handler.client_address[1]}")
        sock.sendto(response.bytes, handler.client_address)

    def handle_stage_d(self, handler: HookedHandler):
        data, sock = handler.request
        logger.info((data, sock))

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
