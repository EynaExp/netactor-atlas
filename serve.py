#!/usr/bin/env python3
"""NetActor production server: static frontend + /api reverse proxy + WebSocket tunnel."""
import http.server
import socketserver
import urllib.request
import socket
import threading
import os

FRONTEND_DIR = "/home/none/projects/netactor/frontend/dist"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
LISTEN_PORT = 3000
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length"
}


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=FRONTEND_DIR, **kw)

    # ---------- WebSocket tunnel ----------
    def _is_websocket(self):
        return (self.headers.get("Upgrade", "").lower() == "websocket"
                and "upgrade" in self.headers.get("Connection", "").lower())

    def _tunnel_ws(self):
        """Raw TCP tunnel: client <-> backend for WebSocket connections."""
        client_sock = self.connection
        try:
            backend = socket.create_connection((BACKEND_HOST, BACKEND_PORT), timeout=10)
        except Exception:
            self.send_error(502, "Cannot reach backend for WS")
            return
        # Rebuild request line + headers for backend
        req = f"{self.command} {self.path} HTTP/1.1\r\n"
        for key, val in self.headers.items():
            if key.lower() not in HOP_HEADERS:
                req += f"{key}: {val}\r\n"
        # hop-by-hop headers are required for WS upgrade on the backend hop too
        req += "Upgrade: websocket\r\nConnection: Upgrade\r\n"
        # force Host to backend
        req += f"Host: {BACKEND_HOST}:{BACKEND_PORT}\r\n"
        req += "\r\n"
        backend.sendall(req.encode())

        client_sock.setblocking(True)
        backend.setblocking(True)

        def pump(src, dst):
            try:
                while True:
                    data = src.recv(65536)
                    if not data:
                        break
                    dst.sendall(data)
            except OSError:
                pass
            finally:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        t1 = threading.Thread(target=pump, args=(client_sock, backend), daemon=True)
        t1.start()
        # backend -> client handled inline in this handler thread
        try:
            while True:
                data = backend.recv(65536)
                if not data:
                    break
                client_sock.sendall(data)
        except OSError:
            pass
        t1.join(timeout=2)
        try:
            backend.close()
        except OSError:
            pass

    # ---------- HTTP ----------
    def _proxy(self, method):
        url = f"http://{BACKEND_HOST}:{BACKEND_PORT}{self.path}"
        body = None
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else None
        req = urllib.request.Request(url, data=body, method=method)
        for key, val in self.headers.items():
            if key.lower() not in HOP_HEADERS:
                req.add_header(key, val)
        if body is not None:
            req.add_header("Content-Type", self.headers.get("Content-Type", "application/json"))
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(502, str(e))

    def do_GET(self):
        if self._is_websocket():
            self._tunnel_ws()
        elif self.path.startswith("/api/"):
            self._proxy("GET")
        else:
            # SPA fallback: serve index.html for non-file routes
            if "." not in os.path.basename(self.path):
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy("POST")
        else:
            self.send_error(404)

    def do_PUT(self):
        if self.path.startswith("/api/"):
            self._proxy("PUT")
        else:
            self.send_error(404)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self._proxy("DELETE")
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def log_message(self, *a):
        pass


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    os.chdir(FRONTEND_DIR)
    server = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), ProxyHandler)
    print(f"NetActor web server on :{LISTEN_PORT} (api proxy + ws tunnel)", flush=True)
    server.serve_forever()
