import socketserver
import threading
import logging
import secrets
import random
import struct

from typing import Callable
from cse461.project1.packet import Packet
from cse461.project1.wrappers import synchronized
from cse461.project1.consts import *

__all__ = ['Server']
logger = logging.getLogger(__name__)


class HookedHandler(socketserver.BaseRequestHandler):
    def __init__(self, callback: Callable, callback_args: tuple = (), *args, **kwargs):
        self.callback = callback
        self.callback_args = callback_args
        super().__init__(*args, **kwargs)

    def handle(self):
        self.callback(self, *self.callback_args)


class ServerTimeout(Exception):
    """Exception indicating that a TimeoutThreadingServer timed out."""


class TimeoutThreadingServer(socketserver.ThreadingTCPServer):
    def __init__(self, *args,
                 timeout: float = None,
                 after_close: Callable = lambda: None,
                 **kwargs):
        self.timeout = timeout
        self.after_close = after_close
        super().__init__(*args, **kwargs)

    def serve_until_timeout(self):
        """Override in subclass."""


class TimeoutThreadingUDPServer(socketserver.ThreadingUDPServer, TimeoutThreadingServer):
    def handle_timeout(self):
        logger.info(f"UDP server at {self.server_address[0]}:{self.server_address[1]} "
                    f"timed out. Shutting down.")
        raise ServerTimeout

    def serve_until_timeout(self):
        # If the file descriptor is -1, the socket is closed.
        while self.fileno() != -1:
            try:
                self.handle_request()
            except ServerTimeout:
                self.server_close()
                self.after_close()
                return


class TimeoutThreadingTCPServer(TimeoutThreadingServer):
    def handle_timeout(self):
        logger.info(f"TCP server at {self.server_address[0]}:{self.server_address[1]} "
                    f"timed out. Shutting down.")

    def serve_until_timeout(self):
        # TCP only handles a single request
        self.handle_request()
        self.server_close()
        self.after_close()


class Server:
    """Multithreaded server implementation for protocol
    outlined in CSE 461 SPR 2020 Project 1 (Sockets API).

    Usage:
    >>> server = Server()
    >>> server.run()
    >>> # Run forever...

    Specify a server lifetime:
    >>> server = Server()
    >>> server.run(seconds=30)

    Timeouts for UDP/TCP servers started by this Server
    can be configured in consts.py.
    """
    def __init__(self):
        self.secrets = {}
        self.tcp_servers = {}
        self.udp_servers = {}
        self.rlock = threading.RLock()

        # Wrap handler callbacks with re-entrant resource locks
        self.handle_stage_a = synchronized(self.handle_stage_a, lock=self.rlock)
        self.handle_stage_b = synchronized(self.handle_stage_b, lock=self.rlock)
        self.handle_stage_c = synchronized(self.handle_stage_c, lock=self.rlock)
        self.handle_stage_d = synchronized(self.handle_stage_d, lock=self.rlock)
        self.start = synchronized(self.start, lock=self.rlock)
        self.stop = synchronized(self.stop, lock=self.rlock)
        self.generate_secret = synchronized(self.generate_secret, lock=self.rlock)
        self.random_port = synchronized(self.random_port, lock=self.rlock)

    def start(self, port=START_PORT):
        server = TimeoutThreadingUDPServer(
            (SERVER_ADDR, port),
            self.handler_factory(callback=self.handle_stage_a),
            after_close=synchronized(lambda: self.udp_servers.pop(port), lock=self.rlock)
        )
        self.udp_servers[port] = server
        self.start_server(server)
        logger.info(f"[Start] Started new UDP server at {SERVER_ADDR}:{port}.")

    def stop(self):
        logger.info(f"[Stop] Received stop request. Shutting down servers "
                    f"(count: {threading.active_count() - 1}) and cleaning up.")
        # Copy tcp/udp server lists so we don't run into data race issues
        # (after timeout, tcp/udp servers execute a callback that deletes
        # the server from self.tcp_servers or self.udp_servers respectively).
        # It is possible that some servers in the copied lists have already
        # been closed; however, server_close() being called twice on the
        # same server is ok because under the hood it calls socket.close(),
        # which just exits if the socket is already closed (no error is raised).
        for tcp_server in list(self.tcp_servers.values()):
            tcp_server.server_close()
        for udp_server in list(self.udp_servers.values()):
            udp_server.server_close()
        logger.info("[Stop] Successfully shut down all servers. Exiting.")

    @staticmethod
    def start_server(server: TimeoutThreadingServer):
        threading.Thread(target=server.serve_until_timeout).start()

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
                packet.step != 1 or
                packet.payload_len != 12):
            logger.error(f"[Stage A] Packet does not conform to protocol. "
                         f"Packet info: {packet!r}")
            return

        num_packets = random.randint(5, 10)
        # Guarantee that packet_len is a multiple of 4.
        packet_len = random.randint(1, 10) * 4
        secret_a = self.generate_secret()
        udp_port = self.random_port()

        server = TimeoutThreadingUDPServer(
            (SERVER_ADDR, udp_port),
            self.handler_factory(callback=self.handle_stage_b),
            timeout=TIMEOUT,
            after_close=synchronized(lambda: self.udp_servers.pop(udp_port), lock=self.rlock)
        )
        assert udp_port not in self.udp_servers
        self.udp_servers[udp_port] = server
        self.start_server(server)
        logger.info(f"[Stage A] Started new UDP server at {SERVER_ADDR}:{udp_port}.")

        # For stage B, don't acknowledge one packet
        # ack_fails = set()
        ack_fails = {random.choice(range(num_packets))}
        # ack_fails = set(random.sample(
        #     range(num_packets),
        #     k=random.randint(1, num_packets))
        # )
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
        # TODO: Fix issue where packet ids are not within 1 of the expected
        #  packet id

        if handler.server.fileno() == -1:
            client_ip, client_port = handler.client_address
            server_ip, server_port = handler.server.server_address
            logger.error(f"[Stage B] Received data from {client_ip}:{client_port} "
                         f"but the server at {server_ip}:{server_port} is already closed.")
            return

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
            prev_stage = self.secrets[packet.p_secret]['prev_stage']
            num_packets = self.secrets[packet.p_secret]["num_packets"]
            remaining_packets = self.secrets[packet.p_secret]["remaining_packets"]
            ack_fails = self.secrets[packet.p_secret]["ack_fails"]
            packet_len = self.secrets[packet.p_secret]['packet_len']

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
                packet_len + 4 != len(packet.payload)):
            logger.error(f"[Stage B] Packet does not conform to protocol. "
                         f"Packet info: {packet!r}\n"
                         f"packet.step: {packet.step}, expected: 1\n"
                         f"len(packet.payload): {len(packet.payload)}, "
                         f"expected: {packet_len + 4}\n"
                         f"packet_id: {packet_id}, expected: {num_packets - remaining_packets}, "
                         f"num_packets: {num_packets}, remaining_packets: {remaining_packets}")
            return

        if packet_id in ack_fails:
            logger.info(f"[Stage B] Dropping packet with id {packet_id}")
            ack_fails.remove(packet_id)
            return
        else:
            logger.info(f"[Stage B] Acknowledging packet with id {packet_id}")
            if num_packets - remaining_packets == packet_id:
                # Only decrement remaining_packets if this is not a resent packet
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

            tcp_port = self.random_port()
            payload = struct.pack("!II", tcp_port, secret_b)
            response = Packet(
                payload=payload,
                p_secret=secret_b,
                step=2,
                student_id=packet.student_id
            )
            server = TimeoutThreadingTCPServer(
                (SERVER_ADDR, tcp_port),
                self.handler_factory(callback=self.handle_stage_c, callback_args=(response,)),
                timeout=TIMEOUT,
                after_close=synchronized(lambda: self.tcp_servers.pop(tcp_port), lock=self.rlock)
            )
            assert tcp_port not in self.tcp_servers
            self.tcp_servers[tcp_port] = server
            self.start_server(server)

            logger.info(f"[Stage B] Started new TCP server at {SERVER_ADDR}:{tcp_port}.")
            logger.info(f"[Stage B] Sending packet {response} "
                        f"to {handler.client_address[0]}:{handler.client_address[1]}")
            sock.sendto(response.bytes, handler.client_address)

    def handle_stage_c(self, handler: HookedHandler, packet: Packet):
        assert self.secrets[packet.p_secret]["prev_stage"] == "b"

        sock = handler.request

        num2 = random.randint(1, 10)
        len2 = random.randint(1, 10) * 4
        secret_c = self.generate_secret()
        char = secrets.token_bytes(1)

        self.secrets[secret_c] = {
            "prev_stage": "c",
            "num2": num2,
            "len2": len2,
            "char": char
        }
        payload = struct.pack("!3I4s", num2, len2, secret_c, char * 4)

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
            prev_stage = self.secrets[secret_c]['prev_stage']
            num2 = self.secrets[secret_c]["num2"]
            len2 = self.secrets[secret_c]["len2"]
            char = self.secrets[secret_c]["char"]
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
                             f"Packet info: {packet!r}\n"
                             f"packet.payload: {packet.payload}, expected: {char * len2}")
                return

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
            if secret not in self.secrets:
                return secret

    def random_port(self) -> int:
        """Returns a unique random port."""
        while True:
            port = random.randint(1024, 49151)
            if port not in self.udp_servers and port not in self.tcp_servers:
                return port

    def run(self, seconds: float = None, port: int = START_PORT):
        """Convenience function target for testing. Runs this server for
        a maximum of `seconds` seconds. If `seconds` is None, runs until this
        server is not listening to any ports (all timed out or closed)."""
        import time

        start = time.time()
        self.start(port)

        while threading.active_count() > 1 and (
                seconds is None or time.time() < start + seconds):
            pass

        self.stop()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()


def main():
    Server().run(seconds=20)


if __name__ == '__main__':
    main()
