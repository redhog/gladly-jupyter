import pathlib
import uuid

import anywidget
import traitlets

from . import server_extension
from .pint_support import get_quantity_kind, to_float32

_ESM_PATH = pathlib.Path(__file__).parent / "static" / "widget.js"


class DataGroup:
    """Wraps multiple named DataFrames for use in a Plot."""

    def __init__(self, frames, quantity_kinds=None):
        """
        Args:
            frames: dict of {name: pd.DataFrame}
            quantity_kinds: optional nested dict {name: {col_name: quantity_kind_str}}
        """
        self.frames = frames
        self.quantity_kinds = quantity_kinds or {}


def _process_df(df, quantity_kinds=None):
    """
    Serialize a DataFrame for the widget.

    Returns:
        columns: {col_name: np.ndarray (float32)}  — for registration
        meta:    {col_name: {length, quantityKind, min, max}}  — for the traitlet
    """
    columns = {}
    meta = {}
    for col_name in df.columns:
        arr = to_float32(df[col_name])
        qk = get_quantity_kind(df[col_name], str(col_name), quantity_kinds)
        columns[str(col_name)] = arr
        meta[str(col_name)] = {
            "length": int(len(arr)),
            "quantityKind": qk,
            "min": float(arr.min()) if len(arr) > 0 else 0.0,
            "max": float(arr.max()) if len(arr) > 0 else 0.0,
        }
    return columns, meta


class Plot(anywidget.AnyWidget):
    _esm = _ESM_PATH

    _widget_type = traitlets.Unicode("plot").tag(sync=True)
    _widget_id = traitlets.Unicode("").tag(sync=True)
    _server_base_url = traitlets.Unicode("/").tag(sync=True)
    _meta = traitlets.Dict({}).tag(sync=True)
    _is_group = traitlets.Bool(False).tag(sync=True)
    layers = traitlets.List([]).tag(sync=True)
    axes = traitlets.Dict({}).tag(sync=True)

    def __init__(self, data, layers=None, axes=None, quantity_kinds=None, **kwargs):
        super().__init__(**kwargs)
        self._widget_id = str(uuid.uuid4())
        self._server_base_url = server_extension.get_base_url()
        self.layers = layers or []
        self.axes = axes or {}
        self._load_data(data, quantity_kinds)

    def _load_data(self, data, quantity_kinds=None):
        wid = self._widget_id

        if isinstance(data, DataGroup):
            self._is_group = True
            meta = {}
            for name, df in data.frames.items():
                # Merge: DataGroup-level quantity_kinds win over top-level
                qk = {**(quantity_kinds or {}).get(name, {}), **data.quantity_kinds.get(name, {})}
                columns, df_meta = _process_df(df, qk or None)
                meta[name] = df_meta
                for col_name, arr in columns.items():
                    server_extension.register(wid, f"{name}/{col_name}", arr)
            self._meta = meta
        else:
            self._is_group = False
            columns, meta = _process_df(data, quantity_kinds)
            for col_name, arr in columns.items():
                server_extension.register(wid, col_name, arr)
            self._meta = meta

    def __del__(self):
        server_extension.unregister(self._widget_id)


class PlotGroup(anywidget.AnyWidget):
    _esm = _ESM_PATH

    _widget_type = traitlets.Unicode("plotgroup").tag(sync=True)
    _server_base_url = traitlets.Unicode("/").tag(sync=True)
    _plot_configs = traitlets.List([]).tag(sync=True)
    _auto_link = traitlets.Bool(True).tag(sync=True)

    def __init__(self, plots, auto_link=True, **kwargs):
        super().__init__(**kwargs)
        self._server_base_url = server_extension.get_base_url()
        self._auto_link = auto_link
        self._plot_configs = [
            {
                "widget_id": p._widget_id,
                "meta": p._meta,
                "is_group": p._is_group,
                "layers": p.layers,
                "axes": p.axes,
            }
            for p in plots
        ]
