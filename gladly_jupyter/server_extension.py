import pathlib
import shutil
import tempfile

import numpy as np
from jupyter_server.base.handlers import JupyterHandler
from jupyter_server.utils import url_path_join
import tornado.web

# Shared temp directory — both kernel and server processes can access this.
_TEMP_DIR = pathlib.Path(tempfile.gettempdir()) / "gladly_jupyter"
_base_url = "/"


def _col_file(widget_id: str, path: str) -> pathlib.Path:
    """Resolve the temp file path for a column. path may contain '/' for DataGroups."""
    return _TEMP_DIR / widget_id / (path + ".f32")


def register(widget_id: str, path: str, array: "np.ndarray") -> None:
    """Write a column to disk. Called from the kernel process."""
    dest = _col_file(widget_id, path)
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    dest.write_bytes(array.astype(np.float32).tobytes())


def unregister(widget_id: str) -> None:
    """Remove all column files for a widget. Called from the kernel process."""
    col_dir = _TEMP_DIR / widget_id
    if col_dir.exists():
        shutil.rmtree(col_dir)


def get_base_url() -> str:
    return _base_url


class ColumnHandler(JupyterHandler):
    @tornado.web.authenticated
    def get(self, widget_id, col_path):
        file_path = _col_file(widget_id, col_path)

        # Path traversal guard
        try:
            file_path.resolve().relative_to(_TEMP_DIR.resolve())
        except ValueError:
            self.set_status(400)
            return

        if not file_path.exists():
            self.set_status(404)
            return

        data = file_path.read_bytes()
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
            self.write(data[start : end + 1])
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
