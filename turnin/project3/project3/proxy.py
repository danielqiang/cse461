from .http import HTTPRequest, HTTPResponse
import threading
import socket
import logging

__all__ = ['Proxy']
logger = logging.getLogger(__name__)
CHUNK_SIZE = 4096
TIMEOUT = 10


class Proxy:
    def __init__(self, host='127.0.0.1', port=8888):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((host, port))
        self.socket.listen()
        logger.info(f'Proxy listening on {host}:{port}')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.socket.close()

    @staticmethod
    def recv_until(sock: socket.socket, sentinel: bytes = b'\0'):
        msg = b''
        try:
            while True:
                data = sock.recv(CHUNK_SIZE)
                if sentinel in data:
                    msg_end, extra = data.split(sentinel, 1)
                    msg += msg_end + sentinel
                    return msg, extra
                elif not data:
                    return msg, b''
                else:
                    msg += data
        except (ConnectionError, socket.timeout):
            return msg, b''

    @staticmethod
    def stream(sender: socket.socket, receiver: socket.socket):
        try:
            while True:
                data = sender.recv(CHUNK_SIZE)
                receiver.send(data)
                if not data:
                    break
        except OSError:
            pass

    def handle_request(self, client: socket.socket, remote: socket.socket,
                       req: HTTPRequest, extra: bytes):
        # Don't persist TCP connections
        if 'Connection' in req:
            req['Connection'] = 'close'
        if 'Proxy-Connection' in req:
            req['Proxy-Connection'] = 'close'
        # Make sure we're using HTTP 1.0
        req.http_version = '1.0'

        remote.sendall(req.bytes + extra)

        self.stream(client, remote)
        self.stream(remote, client)

        remote.close()

    def handle_connect(self, client: socket.socket, remote: socket.socket):
        t1 = threading.Thread(target=self.stream, args=(client, remote), daemon=True)
        t2 = threading.Thread(target=self.stream, args=(remote, client), daemon=True)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        remote.close()

    def handle_client(self, client: socket.socket):
        while True:
            headers, extra = self.recv_until(client, b'\r\n\r\n')
            if not headers:
                break
            try:
                req = HTTPRequest.from_bytes(headers)
                logger.info(f'>>> {req.request_line!r}')
            except ValueError:
                break

            try:
                remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                remote.connect((req['Host'], req.port))
            except socket.gaierror:
                resp = HTTPResponse(502)
                client.sendall(resp.bytes)
                client.close()
                return
            else:
                resp = HTTPResponse(200)
                client.sendall(resp.bytes)

            if req.method == 'CONNECT':
                self.handle_connect(client, remote)
            else:
                self.handle_request(client, remote, req, extra)

    def _run(self):
        while True:
            client, addr = self.socket.accept()
            threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()

    def run(self):
        try:
            t = threading.Thread(target=self._run, daemon=True)
            t.start()
            while True:
                pass
        except KeyboardInterrupt:
            logger.info("Received stop request. Exiting.")


def main():
    proxy = Proxy()
    proxy.run()


if __name__ == '__main__':
    main()
