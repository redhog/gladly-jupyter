import uuid
import json
import threading
import asyncio
import pathlib

import anywidget
import traitlets
import numpy as np

from . import kernel_server
from .pint_support import get_quantity_kind, to_float32

_ESM_PATH = pathlib.Path(__file__).parent / "static" / "widget.js"


# ── JS expression helper ───────────────────────────────────────────────────────

class JsExpr:
    """Marks a string as a raw JS expression (not wrapped in template-literal backticks)."""
    def __init__(self, expr):
        self.expr = expr


def js(expr):
    """Wrap a string as a raw JS expression for use in register_layer_type."""
    return JsExpr(expr)


def to_js_expr(value):
    """Recursively serialize a Python value to a JS expression string."""
    if isinstance(value, JsExpr):
        return value.expr
    elif isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, (int, float)):
        return str(value)
    elif value is None:
        return 'null'
    elif isinstance(value, str):
        escaped = value.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
        return f'`{escaped}`'
    elif isinstance(value, dict):
        items = ', '.join(f'{json.dumps(k)}: {to_js_expr(v)}' for k, v in value.items())
        return '{' + items + '}'
    elif isinstance(value, (list, tuple)):
        return '[' + ', '.join(to_js_expr(v) for v in value) + ']'
    else:
        return json.dumps(value)


# ── Module-level registrations ─────────────────────────────────────────────────

_quantity_kind_registrations = []  # list of {'name': str, **kwargs}
_layer_type_registrations = []     # list of {'name': str, 'args': dict}


def register_axis_quantity_kind(name, **kwargs):
    """Register a quantity kind. kwargs are forwarded to Gladly.registerAxisQuantityKind."""
    _quantity_kind_registrations.append({'name': name, **kwargs})


def register_layer_type(name, args):
    """
    Register a custom layer type.

    args: dict mapping LayerType constructor argument names to Python values.
          str values become JS template literals; gl.js() values are raw JS expressions;
          dicts and lists are serialized recursively.
    """
    _layer_type_registrations.append({'name': name, 'args': args})


def _build_registrations_js():
    """Build JS code string for all module-level registrations."""
    lines = []
    for qk in _quantity_kind_registrations:
        name = qk['name']
        rest = {k: v for k, v in qk.items() if k != 'name'}
        lines.append(f'Gladly.registerAxisQuantityKind({json.dumps(name)}, {json.dumps(rest)});')
    for lt in _layer_type_registrations:
        name = lt['name']
        args_js = to_js_expr(lt['args'])
        guard = f'if (!Gladly.getRegisteredLayerTypes().includes({json.dumps(name)}))'
        lines.append(f'{guard} Gladly.registerLayerType({json.dumps(name)}, new Gladly.LayerType({args_js}));')
    return '\n'.join(lines)


# ── Data classes ───────────────────────────────────────────────────────────────

def _is_dataframe(obj):
    try:
        import pandas as pd
        return isinstance(obj, pd.DataFrame)
    except ImportError:
        return False


class Data:
    """Wraps a DataFrame or dict of numpy arrays, with optional quantity_kinds and domains."""

    def __init__(self, data, quantity_kinds=None, domains=None):
        self.data = data
        self.quantity_kinds = quantity_kinds or {}
        self.domains = domains or {}

    def _process(self):
        """Returns (columns, meta).

        columns: {col_name: np.ndarray float32}
        meta:    {col_name: {length, quantityKind, min, max}}
        """
        is_df = _is_dataframe(self.data)

        if is_df:
            raw_items = {str(col): self.data[col] for col in self.data.columns}
        elif isinstance(self.data, dict):
            raw_items = {str(k): v for k, v in self.data.items()}
        else:
            raise TypeError(f'Data expects a DataFrame or dict of arrays, got {type(self.data).__name__}')

        columns, meta = {}, {}
        for col_name, series_or_arr in raw_items.items():
            arr = to_float32(series_or_arr)

            if col_name in self.quantity_kinds:
                qk = self.quantity_kinds[col_name]
            elif is_df:
                qk = get_quantity_kind(self.data[col_name], col_name, {})
            else:
                qk = col_name

            domain = self.domains.get(col_name)
            columns[col_name] = arr
            meta[col_name] = {
                'length':       int(len(arr)),
                'quantityKind': qk,
                'min': float(domain[0]) if domain else (float(arr.min()) if len(arr) > 0 else 0.0),
                'max': float(domain[1]) if domain else (float(arr.max()) if len(arr) > 0 else 0.0),
            }
        return columns, meta


class DataGroup:
    """Wraps multiple named Data sources. Values may be Data instances or plain DataFrames."""

    def __init__(self, frames):
        self.frames = {
            name: (v if isinstance(v, Data) else Data(v))
            for name, v in frames.items()
        }


def _normalize_data(data):
    """Auto-wrap data into a Data or DataGroup."""
    if isinstance(data, (Data, DataGroup)):
        return data
    if _is_dataframe(data):
        return Data(data)
    if isinstance(data, dict):
        # dict whose values are DataFrames or Data → DataGroup
        if data and all(_is_dataframe(v) or isinstance(v, Data) for v in data.values()):
            return DataGroup(data)
        # dict of numpy arrays → single Data
        return Data(data)
    raise TypeError(f'Cannot auto-wrap data of type {type(data).__name__}')


# ── Axis proxy ─────────────────────────────────────────────────────────────────

class Axis:
    """Python proxy for a single Gladly axis. Stores active Link objects."""

    def __init__(self, plot, name):
        self._plot = plot
        self._name = name
        self._links = []


class AxisAccessor:
    """Attribute-access proxy: plot.axis.xaxis_bottom → cached Axis(plot, 'xaxis_bottom')."""

    def __init__(self, plot):
        self._plot = plot
        self._cache = {}

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        if name not in self._cache:
            self._cache[name] = Axis(self._plot, name)
        return self._cache[name]


# ── Link ───────────────────────────────────────────────────────────────────────

class Link:
    """Represents a live axis link. Call unlink() to tear it down."""

    def __init__(self, axis1, axis2, link_id):
        self._axis1 = axis1
        self._axis2 = axis2
        self._id = link_id

    def unlink(self):
        self._axis1._plot._remove_link(self._id)
        self._axis2._plot._remove_link(self._id)
        self._axis1._links = [l for l in self._axis1._links if l is not self]
        self._axis2._links = [l for l in self._axis2._links if l is not self]


def link_axes(axis1, axis2):
    """Link two axes across any two Plot widgets. Returns a Link with .unlink()."""
    link_id = str(uuid.uuid4())
    link = Link(axis1, axis2, link_id)
    axis1._links.append(link)
    axis2._links.append(link)
    axis1._plot._add_link(link_id, axis1._name, axis2._plot._widget_id, axis2._name)
    axis2._plot._add_link(link_id, axis2._name, axis1._plot._widget_id, axis1._name)
    return link


# ── Plot widget ────────────────────────────────────────────────────────────────

class Plot(anywidget.AnyWidget):
    _esm = _ESM_PATH

    _widget_type    = traitlets.Unicode('plot').tag(sync=True)
    _widget_id      = traitlets.Unicode('').tag(sync=True)
    _kernel_port    = traitlets.Int(0).tag(sync=True)
    _meta           = traitlets.Dict({}).tag(sync=True)
    _is_group       = traitlets.Bool(False).tag(sync=True)
    _registrations  = traitlets.Unicode('').tag(sync=True)
    _links          = traitlets.List([]).tag(sync=True)
    config          = traitlets.Dict({}).tag(sync=True)

    def __init__(self, config, data, **kwargs):
        super().__init__(**kwargs)
        self._widget_id     = str(uuid.uuid4())
        self._kernel_port   = kernel_server.get_port()
        self._registrations = _build_registrations_js()
        self.config         = config
        self._axis_accessor = AxisAccessor(self)
        self._load_data(_normalize_data(data))

    @property
    def axis(self):
        return self._axis_accessor

    def _load_data(self, data):
        wid = self._widget_id
        if isinstance(data, DataGroup):
            self._is_group = True
            meta = {}
            for name, d in data.frames.items():
                columns, df_meta = d._process()
                meta[name] = df_meta
                for col_name, arr in columns.items():
                    kernel_server.register(wid, f'{name}/{col_name}', arr)
            self._meta = meta
        else:
            self._is_group = False
            columns, meta = data._process()
            for col_name, arr in columns.items():
                kernel_server.register(wid, col_name, arr)
            self._meta = meta

    def update(self, config=None, data=None):
        """Mirror of JS plot.update({ config, data })."""
        if config is not None:
            self.config = config
        if data is not None:
            kernel_server.unregister(self._widget_id)
            self._load_data(_normalize_data(data))

    def _add_link(self, link_id, my_axis, other_widget_id, other_axis):
        self._links = self._links + [{
            'id':        link_id,
            'myAxis':    my_axis,
            'otherId':   other_widget_id,
            'otherAxis': other_axis,
        }]

    def _remove_link(self, link_id):
        self._links = [l for l in self._links if l['id'] != link_id]

    # ── Round-trip helpers ─────────────────────────────────────────────────────

    def _roundtrip(self, msg_type, response_type, timeout=5.0):
        event = threading.Event()
        result = {}
        request_id = str(uuid.uuid4())

        def on_response(widget, content, buffers):
            if content.get('type') == response_type and content.get('requestId') == request_id:
                result['data'] = content['result']
                event.set()

        self.on_msg(on_response)
        self.send({'type': msg_type, 'requestId': request_id})
        event.wait(timeout=timeout)
        self.on_msg(on_response, remove=True)
        return result.get('data')

    async def _async_roundtrip(self, msg_type, response_type, timeout=5.0):
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        request_id = str(uuid.uuid4())

        def on_response(widget, content, buffers):
            if content.get('type') == response_type and content.get('requestId') == request_id:
                if not future.done():
                    loop.call_soon_threadsafe(future.set_result, content['result'])

        self.on_msg(on_response)
        self.send({'type': msg_type, 'requestId': request_id})
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self.on_msg(on_response, remove=True)

    def get_config(self, timeout=5.0):
        """Return the current plot config including live axis domains. Blocks until JS responds."""
        return self._roundtrip('getConfig', 'configResponse', timeout)

    def schema(self, timeout=5.0):
        """Return the JSON Schema for the plot config. Blocks until JS responds."""
        return self._roundtrip('getSchema', 'schemaResponse', timeout)

    async def async_get_config(self, timeout=5.0):
        return await self._async_roundtrip('getConfig', 'configResponse', timeout)

    async def async_schema(self, timeout=5.0):
        return await self._async_roundtrip('getSchema', 'schemaResponse', timeout)

    def __del__(self):
        kernel_server.unregister(self._widget_id)


# ── PlotGroup widget ───────────────────────────────────────────────────────────

class PlotGroup(anywidget.AnyWidget):
    _esm = _ESM_PATH

    _widget_type  = traitlets.Unicode('plotgroup').tag(sync=True)
    _plot_configs = traitlets.List([]).tag(sync=True)
    _auto_link    = traitlets.Bool(True).tag(sync=True)

    def __init__(self, plots, auto_link=True, **kwargs):
        """
        plots: dict of {name: Plot}
        """
        super().__init__(**kwargs)
        self._auto_link = auto_link
        self._plot_configs = [
            {
                'name':         name,
                'widget_id':    p._widget_id,
                'kernel_port':  p._kernel_port,
                'meta':         p._meta,
                'is_group':     p._is_group,
                'config':       p.config,
                'registrations': p._registrations,
            }
            for name, p in plots.items()
        ]
