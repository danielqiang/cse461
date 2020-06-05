import logging

__all__ = ['HTTPMessage', 'HTTPRequest', 'HTTPResponse',
           'HTTPGet', 'HTTPHead', 'HTTPPost', 'HTTPPut',
           'HTTPDelete', 'HTTPConnect', 'HTTPOptions',
           'HTTPTrace']
logger = logging.getLogger(__name__)
DEFAULT_CODEC = 'iso-8859-1'


class HTTPMessage:
    def __init__(self, headers: dict = None, http_type: str = 'HTTP',
                 http_version: str = '1.0', port: int = None, **kwargs):
        headers = (headers or {}).copy()
        headers.update(kwargs)
        # Try to capitalize headers correctly. This fails
        # in some edge cases (i.e. x-xss-protection -> X-Xss-Protection
        # rather than X-XSS-Protection)
        self.headers = {k.title() if k.islower() else k: v
                        for k, v in headers.items()}

        if http_type.upper() not in {'HTTP', 'HTTPS'}:
            raise ValueError("`http_type` must be either 'HTTP' or 'HTTPS'")

        self.http_type = http_type.upper()

        if http_version not in {'0.9', '1.0', '1.1', '2.0'}:
            raise ValueError("`http_version` must be '0.9', '1.0', '1.1' or '2.0'.")

        self.http_version = http_version

        if port is None:
            port = 80 if http_type == 'HTTP' else 443
        self.port = port

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
        """Override in subclass"""
        raise NotImplementedError

    @property
    def data(self) -> str:
        return self.bytes.decode(DEFAULT_CODEC)

    @classmethod
    def from_bytes(cls, data: bytes):
        """Override in subclass"""
        raise NotImplementedError

    def __eq__(self, other):
        if type(other) == self.__class__:
            return self.bytes == other.bytes
        return False

    def __str__(self):
        return self.data

    def __repr__(self):
        return repr(self.data)

    # Allow headers to be accessed/modified directly
    def __getitem__(self, item):
        return self.headers[item]

    def __setitem__(self, k, v):
        self.headers[k] = v

    def __contains__(self, item):
        return item in self.headers


_http_methods = {'GET', 'HEAD', 'POST', 'PUT', 'DELETE',
                 'CONNECT', 'OPTIONS', 'TRACE'}


class HTTPRequest(HTTPMessage):
    # Default HTTP method for this HTTPRequest. Override in subclass.
    _method = None

    def __init__(self, method: str = None, uri: str = '/', *args, **kwargs):
        super().__init__(*args, **kwargs)
        if method is None and self._method is None:
            raise ValueError('Either `method` or `HTTPRequest._method` must be provided.')
        # `method` overrides `HTTPRequest._method` if both are provided
        method = (method or self._method).upper()
        if method not in _http_methods:
            raise ValueError(f"'{method}' is not a valid HTTP method")

        self.method = method
        self.uri = uri

    @property
    def request_line(self) -> str:
        return f'{self.method} {self.uri} {self.http_type}/{self.http_version}\r\n'

    @property
    def bytes(self) -> bytes:
        return self.request_line.encode() + super()._encode_headers()

    @classmethod
    def from_bytes(cls, data: bytes):
        headers = {}

        if b'\r\n' in data:
            lines = data.decode(DEFAULT_CODEC).split('\r\n')
        else:
            # No carriage returns. Try splitting on newlines instead
            lines = data.decode(DEFAULT_CODEC).split('\n')

        try:
            method, uri, version = lines[0].split()
            if not version.startswith(('HTTP/', 'HTTPS/')):
                raise ValueError
            if not len(version.split('.')) == 2:
                raise ValueError
            http_type, http_version = version.split('/')
        except ValueError:
            logger.error(f"Malformed request line: {lines[0]!r}")
            raise
        if cls._method and cls._method != method:
            # Raise an error if the http method in the data does not match
            # the method specified by the class
            raise ValueError(f"{cls}._method == {cls._method} but the message "
                             f"is a {method} HTTP request")

        # Extract headers
        for line in lines[1:-1]:
            try:
                k, v = line.split(': ', maxsplit=1)
            except ValueError:
                # Malformed line
                continue
            headers[k] = v
        if 'Host' in headers and ':' in headers['Host']:
            # Port number is explicitly specified in URL; override it
            headers['Host'], port = headers['Host'].rsplit(':', maxsplit=1)
            port = int(port)
        else:
            port = None

        return cls(method, uri,
                   headers=headers,
                   http_type=http_type,
                   http_version=http_version,
                   port=port)


class HTTPGet(HTTPRequest):
    _method = 'GET'


class HTTPHead(HTTPRequest):
    _method = 'HEAD'


class HTTPPost(HTTPRequest):
    _method = 'POST'


class HTTPPut(HTTPRequest):
    _method = 'PUT'


class HTTPDelete(HTTPRequest):
    _method = 'DELETE'


class HTTPConnect(HTTPRequest):
    _method = 'CONNECT'


class HTTPOptions(HTTPRequest):
    _method = 'OPTIONS'


class HTTPTrace(HTTPRequest):
    _method = 'TRACE'


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
    def __init__(self, status_code: int, payload: str = '',
                 cookies: list = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if status_code not in _http_status_codes:
            raise ValueError(f'{status_code} is not a valid HTTP status code')

        self.status_code = status_code
        self.payload = payload

        # If the value of 'Set-Cookie' is a string, convert it to a list
        if 'Set-Cookie' in self.headers and isinstance(self.headers['Set-Cookie'], str):
            self.headers['Set-Cookie'] = [self.headers['Set-Cookie']]
        if cookies:
            if 'Set-Cookie' not in self.headers:
                self.headers['Set-Cookie'] = []
            self.headers['Set-Cookie'].extend(cookies)

    @property
    def status_line(self) -> str:
        return (f'{self.http_type}/{self.http_version} {self.status_code} '
                f'{_http_status_codes[self.status_code]}\r\n')

    @property
    def bytes(self) -> bytes:
        return self.status_line.encode() + super()._encode_headers() + self.payload.encode()

    @classmethod
    def from_bytes(cls, data: bytes):
        headers = {}
        if b'\r\n' in data:
            lines = data.decode(DEFAULT_CODEC).split('\r\n')
        else:
            # No carriage returns. Try splitting on newlines instead
            lines = data.decode(DEFAULT_CODEC).split('\n')
        # Extract HTTP status code from status line
        try:
            version, status_code, status_message = lines[0].split(maxsplit=2)
            http_type, http_version = version.split('/')
        except ValueError:
            logger.error(f"Malformed HTTP status line: {lines[0]!r}")
            raise
        # The response body is at the end of an HTTP response
        payload = lines[-1]
        # Extract headers
        for line in lines[1:-2]:
            try:
                k, v = line.split(': ', maxsplit=1)
            except ValueError:
                # Malformatted line
                continue
            # There can be multiple Set-Cookie headers,
            # so store them in a list
            if k == 'Set-Cookie':
                if k not in headers:
                    headers[k] = []
                headers[k].append(v)
            else:
                headers[k] = v
        return cls(int(status_code), payload,
                   headers=headers,
                   http_type=http_type.strip(),
                   http_version=http_version.strip())


def main():
    import socket

    url = 'www.bing.com'

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((url, 80))

    req = HTTPGet(host=url)
    print(f"Request: \n\n{req.data}\n\n")
    s.send(req.bytes)

    r = s.recv(16384)
    resp = HTTPResponse.from_bytes(r)
    print(f"Response: \n\n{resp}")


if __name__ == '__main__':
    main()
