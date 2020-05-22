__all__ = ['HTTPMessage', 'HTTPRequest', 'HTTPResponse']


class HTTPMessage:
    def __init__(self, headers: dict = None, **kwargs):
        _headers = (headers or {}).copy()
        _headers.update(kwargs)
        # Try to capitalize headers correctly. This fails
        # in some edge cases (i.e. x-xss-protection -> X-Xss-Protection
        # rather than X-XSS-Protection)
        self.headers = {k.title() if k.islower() else k: v
                        for k, v in _headers.items()}

    def _encode_headers(self) -> bytes:
        s = ""
        for k, v in self.headers.items():
            if isinstance(v, list):
                s += "\r\n".join(f"{k}: {item}" for item in v) + "\r\n"
            else:
                s += f"{k}: {v}\r\n"
        return (s + '\r\n').encode()

    @property
    def bytes(self) -> bytes:
        raise NotImplementedError

    @property
    def data(self) -> str:
        return self.bytes.decode()

    @classmethod
    def from_bytes(cls, data: bytes):
        raise NotImplementedError

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.bytes == other.bytes
        return False

    def __str__(self):
        return self.bytes.decode()


_http_methods = {'GET', 'HEAD', 'POST', 'PUT', 'DELETE',
                 'CONNECT', 'OPTIONS', 'TRACE'}


class HTTPRequest(HTTPMessage):
    def __init__(self, method: str, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if method.upper() not in _http_methods:
            raise ValueError(f"'{method}' is not a valid HTTP method")

        self.method = method.upper()

    @property
    def bytes(self) -> bytes:
        request_line = f'{self.method} / HTTP/1.0\r\n'.encode()
        return request_line + super()._encode_headers()

    @classmethod
    def from_bytes(cls, data: bytes):
        headers = {}
        lines = data.decode().split('\r\n')

        # Extract HTTP method from request line
        method = lines[0].split('/')[0].strip()
        if method not in _http_methods:
            raise ValueError(f'Invalid HTTP method: {method}')
        # Extract headers
        for line in lines[1:-2]:
            k, v = line.split(': ', maxsplit=1)
            headers[k] = v
        return cls(method, headers=headers)


_http_status_codes = {
    100: 'Continue',
    101: 'Switching Protocols',
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    307: 'Temporary Redirect',
    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Time-out',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request-URI Too Large',
    415: 'Unsupported Media Type',
    416: 'Requested range not satisfiable',
    417: 'Expectation Failed',
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Time-out',
    505: 'HTTP Version not supported'
}


class HTTPResponse(HTTPMessage):
    def __init__(self, status_code: int, body: str = '',
                 cookies: list = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if status_code not in _http_status_codes:
            raise ValueError(f'{status_code} is not a valid HTTP status code')

        self.status_code = status_code
        self.body = body

        if cookies:
            self.headers['Set-Cookie'] = cookies

    @property
    def bytes(self) -> bytes:
        status_line = (f'HTTP/1.0 {self.status_code} '
                       f'{_http_status_codes[self.status_code]}\r\n').encode()
        return status_line + super()._encode_headers() + self.body.encode()

    @classmethod
    def from_bytes(cls, data: bytes):
        headers = {}
        lines = data.decode().split('\r\n')
        # Extract HTTP status code from status line
        status_code = int(lines[0].split()[1])
        if status_code not in _http_status_codes:
            raise ValueError(f'{status_code} is not a valid HTTP status code')
        # The response body is at the end of an HTTP response
        body = lines[-1]
        # Extract headers
        for line in lines[1:-2]:
            k, v = line.split(': ', maxsplit=1)
            # There can be multiple Set-Cookie headers,
            # so store them in a list
            if k == 'Set-Cookie':
                if k not in headers:
                    headers[k] = []
                headers[k].append(v)
            else:
                headers[k] = v
        return cls(status_code, body, headers=headers)


def main():
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('www.google.com', 80))

    req = HTTPRequest('GET', host='www.google.com')
    # print(req.bytes)
    s.send(req.bytes)

    r = s.recv(4096)
    resp = HTTPResponse.from_bytes(r)
    print(resp)
    print(r.decode())

    print(resp.data == r.decode())


if __name__ == '__main__':
    main()
