import socketserver
import threading
import logging
import secrets
import random
import struct

from typing import Callable
from cse461.project1.packet import Packet
from cse461.project1.consts import IP_ADDR
from cse461.project1.wrappers import synchronized

__all__ = ['Server']
logger = logging.getLogger(__name__)


class HookedHandler(socketserver.BaseRequestHandler):
    def __init__(self, callback: Callable, callback_args: tuple = (), *args, **kwargs):
        self.callback = callback
        self.callback_args = callback_args
        super().__init__(*args, **kwargs)

    def handle(self):
        self.callback(self, *self.callback_args)


# TODO: Add functionality where the server completely shuts down
#  after not receiving a response for 3 seconds.
class TimeoutThreadingUDPServer(socketserver.ThreadingUDPServer):
    timeout = 3


class TimeoutThreadingTCPServer(socketserver.ThreadingTCPServer):
    timeout = 3


class Server:
    # TODO: Add docstring
    def __init__(self):
        self.active_secrets = {}
        # Track expired secrets to ensure we don't give out
        # duplicate secrets after they expire
        self.expired_secrets = set()
        self.tcp_servers = {}
        self.udp_servers = {}
        self._rlock = threading.RLock()

        # Wrap handler callbacks with re-entrant resource locks
        self.handle_stage_a = synchronized(self.handle_stage_a, lock=self._rlock)
        self.handle_stage_b = synchronized(self.handle_stage_b, lock=self._rlock)
        self.handle_stage_c = synchronized(self.handle_stage_c, lock=self._rlock)
        self.handle_stage_d = synchronized(self.handle_stage_d, lock=self._rlock)

    def start(self, port=12235):
        server = TimeoutThreadingUDPServer(
            (IP_ADDR, port),
            self.handler_factory(callback=self.handle_stage_a)
        )
        self.udp_servers[port] = server
        self.start_server(server)
        logger.info(f"[Start] Started new UDP server at {IP_ADDR}:{port}.")

    def stop(self):
        logger.info(f"[Stop] Received stop request. Shutting down servers "
                    f"(count: {threading.active_count() - 1}) and cleaning up.")
        for tcp_server in self.tcp_servers.values():
            tcp_server.shutdown()
            tcp_server.server_close()
        for udp_server in self.udp_servers.values():
            udp_server.shutdown()
            udp_server.server_close()
        logger.info("[Stop] Successfully shut down all servers. Exiting.")

    @staticmethod
    def start_server(server: socketserver.BaseServer):
        threading.Thread(target=server.serve_forever,
                         kwargs={"poll_interval": 0.01}).start()

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
            logger.error(e)
            return

        if (packet.payload.lower() != b'hello world\0' or
                packet.p_secret != 0 or
                packet.step != 1):
            logger.error(f"[Stage A] Packet does not conform to protocol. "
                         f"Packet info: {repr(packet)}")
            return

        num_packets = random.randint(5, 10)
        # Guarantee that packet_len is a multiple of 4.
        packet_len = random.randint(1, 10) * 4
        secret_a = self.generate_secret()
        udp_port = self.random_port()

        server = TimeoutThreadingUDPServer(
            (IP_ADDR, udp_port),
            self.handler_factory(callback=self.handle_stage_b)
        )
        assert udp_port not in self.udp_servers
        self.udp_servers[udp_port] = server
        self.start_server(server)
        logger.info(f"[Stage A] Started new UDP server at {IP_ADDR}:{udp_port}.")

        # For stage B, don't acknowledge at least one packet
        ack_fails = set(random.sample(
            range(num_packets),
            k=random.randint(1, num_packets))
        )
        # Store relevant data for stage B
        self.active_secrets[secret_a] = {
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
            logger.error(e)
            return
        try:
            prev_stage = self.active_secrets[packet.p_secret]['prev_stage']
            num_packets = self.active_secrets[packet.p_secret]["num_packets"]
            remaining_packets = self.active_secrets[packet.p_secret]["remaining_packets"]
            ack_fails = self.active_secrets[packet.p_secret]["ack_fails"]
            packet_len = self.active_secrets[packet.p_secret]['packet_len']

            packet_id = struct.unpack("!I", packet.payload[:4])[0]
        except KeyError:
            logger.error(f"Unrecognized secret: {packet.p_secret}")
            return
        except struct.error:
            logger.error("Packet payload must be at least 4 bytes long")
            return
        assert prev_stage == "a"
        # Ensure that this packet is a valid packet for step b1
        if (packet.step != 1 or
                packet_len + 4 != len(packet.payload) or
                remaining_packets + packet_id != num_packets):
            logger.error(f"[Stage B] Packet does not conform to protocol. "
                         f"Packet info: {repr(packet)}")
            return

        if remaining_packets > 0:
            if packet_id in ack_fails:
                logger.info(f"[Stage B] Dropping packet with id {packet_id}")
                ack_fails.remove(packet_id)
            else:
                logger.info(f"[Stage B] Acknowledging packet with id {packet_id}")
                self.active_secrets[packet.p_secret]["remaining_packets"] -= 1
                ack = Packet(
                    payload=packet.payload[:4],
                    p_secret=packet.p_secret,
                    step=2,
                    student_id=packet.student_id
                )

                sock.sendto(ack.bytes, handler.client_address)

        if self.active_secrets[packet.p_secret]["remaining_packets"] == 0:
            secret_b = self.generate_secret()
            self.active_secrets[secret_b] = {'prev_stage': "b"}

            del self.active_secrets[packet.p_secret]
            self.expired_secrets.add(packet.p_secret)

            tcp_port = self.random_port()
            payload = struct.pack("!II", tcp_port, secret_b)
            response = Packet(
                payload=payload,
                p_secret=secret_b,
                step=2,
                student_id=packet.student_id
            )
            server = TimeoutThreadingTCPServer(
                (IP_ADDR, tcp_port),
                self.handler_factory(callback=self.handle_stage_c, callback_args=(response,))
            )
            assert tcp_port not in self.tcp_servers
            self.tcp_servers[tcp_port] = server
            self.start_server(server)

            logger.info(f"[Stage B] Started new TCP server at {IP_ADDR}:{tcp_port}.")
            logger.info(f"[Stage B] Sending packet {response} "
                        f"to {handler.client_address[0]}:{handler.client_address[1]}")
            sock.sendto(response.bytes, handler.client_address)

    def handle_stage_c(self, handler: HookedHandler, packet: Packet):
        assert self.active_secrets[packet.p_secret]["prev_stage"] == "b"

        sock = handler.request

        num2 = random.randint(1, 10)
        len2 = random.randint(1, 10) * 4
        secret_c = self.generate_secret()
        char = secrets.token_bytes(1)

        self.active_secrets[secret_c] = {
            "prev_stage": "c",
            "num2": num2,
            "len2": len2,
            "char": char
        }
        del self.active_secrets[packet.p_secret]
        self.expired_secrets.add(packet.p_secret)
        payload = struct.pack("!3I4s", num2, len2, secret_c, char)

        response = Packet(
            payload=payload,
            p_secret=packet.p_secret,
            step=2,
            student_id=packet.student_id
        )
        logger.info(f"[Stage C] Sending packet {response} "
                    f"to {handler.client_address[0]}:{handler.client_address[1]}")
        sock.sendall(response.bytes)
        self.handle_stage_d(handler)

    def handle_stage_d(self, handler: HookedHandler):
        sock = handler.request

        data = sock.recv(2048)
        logger.info(f"[Stage D] Received data {data} from "
                    f"{handler.client_address[0]}:{handler.client_address[1]}")

        payload_len, secret_c, step, student_id = struct.unpack("!IIHH", data[:12])
        try:
            prev_stage = self.active_secrets[secret_c]['prev_stage']
            num2 = self.active_secrets[secret_c]["num2"]
            len2 = self.active_secrets[secret_c]["len2"]
            char = self.active_secrets[secret_c]["char"]
        except KeyError:
            logger.error(f"Unrecognized secret: {secret_c}")
            return
        assert prev_stage == "c"

        for i in range(num2):
            start, end = i * (len2 + 12), (i + 1) * (len2 + 12)
            try:
                packet = Packet.from_raw(data[start:end])
            except ValueError as e:
                # Malformed packet
                logger.info(e)
                return
            if packet.payload != char * len2:
                logger.error(f"[Stage D] Packet does not conform to protocol. "
                             f"Packet info: {repr(packet)}")
                return
        del self.active_secrets[secret_c]
        self.expired_secrets.add(secret_c)

        payload = struct.pack("!I", self.generate_secret())
        response = Packet(
            payload=payload,
            p_secret=secret_c,
            step=2,
            student_id=student_id
        )
        logger.info(f"[Stage D] Sending packet {response} "
                    f"to {handler.client_address[0]}:{handler.client_address[1]}")
        sock.sendall(response.bytes)

    def generate_secret(self) -> int:
        """Returns a unique, cryptographically secure secret."""
        while True:
            secret = secrets.randbits(32)
            if secret not in self.active_secrets and secret not in self.expired_secrets:
                return secret

    def random_port(self) -> int:
        """Returns a unique random port."""
        while True:
            port = random.randint(1024, 49151)
            if port not in self.udp_servers and port not in self.tcp_servers:
                return port

    def run(self, port: int = 12235, seconds: float = None):
        """Convenience function target for testing. Runs this server for
        `seconds` seconds. If `seconds` is None, runs forever."""
        import time

        self.start(port)
        if seconds is None:
            while True: time.sleep(1000)
        else:
            time.sleep(seconds)
        self.stop()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()


def main():
    Server().run()


if __name__ == '__main__':
    main()
