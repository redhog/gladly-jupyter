"""
HTTP server running inside the kernel process.

Because the Jupyter kernel already runs a Tornado event loop, we can attach
a lightweight HTTP server to it. Column data is served directly from kernel
memory with no IPC, no temp files, and no involvement from the jupyter_server
process.
"""

import socket

import numpy as np
import tornado.web

# In-kernel column registry: widget_id -> { path -> np.ndarray (float32) }
_registry: dict = {}
_server_port: int | None = None


def register(widget_id: str, path: str, array: "np.ndarray") -> None:
    if widget_id not in _registry:
        _registry[widget_id] = {}
    _registry[widget_id][path] = np.asarray(array, dtype=np.float32)


def unregister(widget_id: str) -> None:
    _registry.pop(widget_id, None)


def get_port() -> int:
    """Start the kernel HTTP server if not already running and return its port."""
    global _server_port
    if _server_port is not None:
        return _server_port

    with socket.socket() as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    app = tornado.web.Application(
        [(r"/gladly/data/([^/]+)/(.+)", _ColumnHandler)],
    )
    app.listen(port)
    _server_port = port
    return port


class _ColumnHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        # CORS: notebook page (localhost:8888) and kernel server (localhost:{port})
        # are different origins, so we need to allow cross-origin fetches.
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Range, Content-Type")

    def options(self, *args, **kwargs):
        self.set_status(204)

    def get(self, widget_id, col_path):
        widget_data = _registry.get(widget_id)
        if widget_data is None:
            self.set_status(404)
            return

        arr = widget_data.get(col_path)
        if arr is None:
            self.set_status(404)
            return

        data = arr.tobytes()
        total = len(data)

        range_header = self.request.headers.get("Range")
        if range_header:
            range_spec = range_header.replace("bytes=", "")
            start_str, end_str = range_spec.split("-")
            start = int(start_str)
            end = int(end_str) if end_str else total - 1
            end = min(end, total - 1)

            self.set_status(206)
            self.set_header("Content-Range", f"bytes {start}-{end}/{total}")
            self.set_header("Content-Length", str(end - start + 1))
            self.set_header("Content-Type", "application/octet-stream")
            self.write(data[start : end + 1])
        else:
            self.set_header("Content-Type", "application/octet-stream")
            self.set_header("Content-Length", str(total))
            self.write(data)
