"""Local bridge for HTTP proxies that require username/password auth.

Chrome's current branded builds no longer accept an unpacked extension passed
with ``--load-extension``. This small loopback proxy lets Chrome use a normal
unauthenticated local proxy while the bridge adds the upstream
``Proxy-Authorization`` header and handles HTTPS CONNECT tunnelling.
"""

import base64
import select
import socket
import socketserver
import ssl
import threading


_HEADER_END = b"\r\n\r\n"
_MAX_HEADER_BYTES = 128 * 1024


def _read_until_headers(sock):
    data = bytearray()
    while _HEADER_END not in data and len(data) <= _MAX_HEADER_BYTES:
        chunk = sock.recv(8192)
        if not chunk:
            break
        data.extend(chunk)

    if _HEADER_END not in data:
        raise ConnectionError("incomplete or oversized proxy request headers")

    split_at = data.index(_HEADER_END) + len(_HEADER_END)
    return bytes(data[:split_at]), bytes(data[split_at:])


def _parse_header_block(block):
    lines = block.decode("iso-8859-1").split("\r\n")
    request_line = lines[0]
    headers = []
    for line in lines[1:]:
        if not line or ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers.append((name.strip(), value.strip()))
    return request_line, headers


def _header_value(headers, name):
    name = name.lower()
    for key, value in headers:
        if key.lower() == name:
            return value
    return None


def _split_host_port(target):
    if target.startswith("["):
        end = target.find("]")
        if end < 0 or end + 2 > len(target) or target[end + 1] != ":":
            raise ValueError(f"invalid CONNECT target: {target}")
        return target[1:end], int(target[end + 2:])

    host, port = target.rsplit(":", 1)
    return host, int(port)


class _BridgeRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client = self.request
        client.settimeout(self.server.io_timeout)
        try:
            head, buffered_body = _read_until_headers(client)
            request_line, headers = _parse_header_block(head)
            method, target, version = request_line.split(" ", 2)
            if method.upper() == "CONNECT":
                self._handle_connect(client, target)
            else:
                self._handle_http(client, method, target, version, headers, buffered_body)
        except (ConnectionError, OSError, ValueError, TimeoutError):
            return

    def _upstream_socket(self):
        bridge = self.server.bridge
        upstream = socket.create_connection(
            (bridge.upstream_host, bridge.upstream_port),
            timeout=self.server.io_timeout,
        )
        if bridge.upstream_scheme == "https":
            context = ssl.create_default_context()
            upstream = context.wrap_socket(upstream, server_hostname=bridge.upstream_host)
        upstream.settimeout(self.server.io_timeout)
        return upstream

    def _proxy_authorization(self):
        bridge = self.server.bridge
        raw = f"{bridge.username}:{bridge.password}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _handle_connect(self, client, target):
        upstream = self._upstream_socket()
        try:
            connect_request = (
                f"CONNECT {target} HTTP/1.1\r\n"
                f"Host: {target}\r\n"
                f"Proxy-Authorization: {self._proxy_authorization()}\r\n"
                "Proxy-Connection: Keep-Alive\r\n"
                "Connection: Keep-Alive\r\n\r\n"
            ).encode("iso-8859-1")
            upstream.sendall(connect_request)
            response_head, _ = _read_until_headers(upstream)
            status_line = response_head.decode("iso-8859-1", "replace").split("\r\n", 1)[0]
            status_code = int(status_line.split(" ", 2)[1])
            if status_code != 200:
                client.sendall(response_head)
                return

            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self._relay(client, upstream)
        finally:
            upstream.close()

    def _handle_http(self, client, method, target, version, headers, buffered_body):
        upstream = self._upstream_socket()
        try:
            content_length = int(_header_value(headers, "Content-Length") or 0)
            body = bytearray(buffered_body[:content_length])
            while len(body) < content_length:
                chunk = client.recv(min(8192, content_length - len(body)))
                if not chunk:
                    break
                body.extend(chunk)

            host = _header_value(headers, "Host")
            if not target.startswith(("http://", "https://")) and host:
                target = "http://" + host + target

            outgoing = [f"{method} {target} {version}"]
            for name, value in headers:
                lowered = name.lower()
                if lowered in {"proxy-authorization", "proxy-connection", "connection", "keep-alive"}:
                    continue
                outgoing.append(f"{name}: {value}")
            outgoing.append(f"Proxy-Authorization: {self._proxy_authorization()}")
            outgoing.append("Connection: close")
            request = ("\r\n".join(outgoing) + "\r\n\r\n").encode("iso-8859-1")
            upstream.sendall(request + bytes(body))
            self._relay(upstream, client)
        finally:
            upstream.close()

    @staticmethod
    def _relay(left, right):
        sockets = [left, right]
        while sockets:
            readable, _, _ = select.select(sockets, [], [], 60)
            if not readable:
                return
            for source in readable:
                data = source.recv(64 * 1024)
                if not data:
                    try:
                        sockets.remove(source)
                    except ValueError:
                        pass
                    continue
                destination = right if source is left else left
                destination.sendall(data)


class _ThreadingProxyServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class AuthenticatedProxyBridge:
    """A loopback proxy that forwards traffic through an authenticated proxy."""

    def __init__(self, proxy_config, io_timeout=60):
        self.upstream_scheme = proxy_config.get("scheme", "http")
        self.upstream_host = proxy_config["host"]
        self.upstream_port = proxy_config["port"]
        self.username = proxy_config.get("username") or ""
        self.password = proxy_config.get("password") or ""
        self.io_timeout = io_timeout
        self._server = _ThreadingProxyServer(("127.0.0.1", 0), _BridgeRequestHandler)
        self._server.bridge = self
        self._server.io_timeout = io_timeout
        self._thread = None

    @property
    def address(self):
        host, port = self._server.server_address
        return host, port

    def start(self):
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.2},
            name="socialfarm-proxy-bridge",
            daemon=True,
        )
        self._thread.start()
        return self

    def close(self):
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._server = None

