import numpy as np
from jupyter_server.base.handlers import JupyterHandler
from jupyter_server.utils import url_path_join
import tornado.web

# Global column registry: widget_id -> { path -> np.ndarray (float32) }
# Path is "colname" for single DataFrames, "dataname/colname" for DataGroups.
_registry = {}
_base_url = "/"


def register(widget_id, path, array):
    if widget_id not in _registry:
        _registry[widget_id] = {}
    _registry[widget_id][path] = array


def unregister(widget_id):
    _registry.pop(widget_id, None)


def get_base_url():
    return _base_url


class ColumnHandler(JupyterHandler):
    @tornado.web.authenticated
    def get(self, widget_id, col_path):
        widget_data = _registry.get(widget_id)
        if widget_data is None:
            self.set_status(404)
            return

        arr = widget_data.get(col_path)
        if arr is None:
            self.set_status(404)
            return

        data = arr.astype(np.float32).tobytes()
        total = len(data)

        range_header = self.request.headers.get("Range")
        if range_header:
            range_spec = range_header.replace("bytes=", "")
            start_str, end_str = range_spec.split("-")
            start = int(start_str)
            end = int(end_str) if end_str else total - 1
            end = min(end, total - 1)
            length = end - start + 1

            self.set_status(206)
            self.set_header("Content-Range", f"bytes {start}-{end}/{total}")
            self.set_header("Content-Length", str(length))
            self.set_header("Content-Type", "application/octet-stream")
            self.write(data[start:end + 1])
        else:
            self.set_header("Content-Type", "application/octet-stream")
            self.set_header("Content-Length", str(total))
            self.write(data)


def _load_jupyter_server_extension(server_app):
    global _base_url
    _base_url = server_app.base_url
    web_app = server_app.web_app
    web_app.add_handlers(
        ".*$",
        [(url_path_join(_base_url, r"/gladly/data/([^/]+)/(.+)"), ColumnHandler)],
    )
    server_app.log.info("gladly_jupyter: column data handler registered")


def _jupyter_server_extension_points():
    return [{"module": "gladly_jupyter.server_extension"}]
