# gladly-jupyter

Jupyter widget for [Gladly](https://github.com/redhog/gladly) — GPU-accelerated plotting via WebGL, driven directly from Python.

Large columns (gigabytes) are streamed to the browser over HTTP from kernel memory rather than sent through the Jupyter comm, so there is no practical data-size limit. Gladly itself is loaded from CDN — no JavaScript build step is required.

## Requirements

- Python ≥ 3.8
- JupyterLab ≥ 4 or Jupyter Notebook ≥ 7
- A WebGL-capable browser

## Installation

```bash
pip install gladly-jupyter
# with optional Pint unit support:
pip install "gladly-jupyter[pint]"
```

From source:
```bash
pip install ./gladly_jupyter
```

## Quick example

```python
import gladly_jupyter as gl
import pandas as pd
import numpy as np

t  = np.linspace(0, 10, 100_000, dtype="float32")
df = pd.DataFrame({"time": t, "signal": np.sin(t)})

config = {
    "layers": [{"points": {"xData": "input.time", "yData": "input.signal"}}],
    "axes":   {
        "xaxis_bottom": {"label": "Time (s)"},
        "yaxis_left":   {"label": "Signal"},
    },
}

gl.Plot(config, df)
```

A single DataFrame is automatically wrapped and placed under the key `input`, so its columns are referenced as `"input.colname"` in the config. For a `DataGroup` you use the name you assigned each source: `"raw.colname"`.

## Multiple data sources in one plot

```python
config = {
    "layers": [
        {"points": {"xData": "raw.time",      "yData": "raw.signal"}},
        {"points": {"xData": "filtered.time", "yData": "filtered.signal"}},
    ],
}

gl.Plot(config, gl.DataGroup({"raw": df_raw, "filtered": df_filtered}))
```

## Linked axes across multiple plots

```python
p1 = gl.Plot({"layers": [{"points": {"xData": "input.time", "yData": "input.depth"}}]},
             gl.Data(df1, quantity_kinds={"time": "s"}))

p2 = gl.Plot({"layers": [{"points": {"xData": "input.time", "yData": "input.velocity"}}]},
             gl.Data(df2, quantity_kinds={"time": "s"}))

gl.PlotGroup({"depth": p1, "velocity": p2})   # time axes auto-linked
```

Manual axis linking (cross-plot, no PlotGroup required):

```python
link = gl.link_axes(p1.axis.xaxis_bottom, p2.axis.xaxis_bottom)
link.unlink()   # tear down later
```

## Registering quantity kinds and layer types

```python
# Register before creating plots — picked up at construction time
gl.register_axis_quantity_kind("frequency", label="Frequency (Hz)", scale="log")

gl.register_layer_type("myLayer", {
    "vertShader": "attribute vec2 a_position; void main() { ... }",
    "fragShader": "void main() { gl_FragColor = vec4(1.0); }",
    "schema":     gl.js("(data) => ({ type: 'object', properties: {} })"),
})
```

## Live config and schema

```python
config = plot.get_config()   # includes current zoom domains, blocks until JS responds
schema = plot.schema()       # JSON Schema for the config dict

# Async variants:
config = await plot.async_get_config()
schema = await plot.async_schema()
```

## Documentation

Full API reference in [`docs/`](docs/):

- [Data — Data, DataGroup, auto-wrapping](docs/Data.md)
- [Plot — constructor, update, config, schema](docs/Plot.md)
- [PlotGroup — multi-plot containers](docs/PlotGroup.md)
- [Axis linking — link_axes, Axis proxy](docs/Linking.md)
- [Registries — quantity kinds, layer types](docs/Registries.md)
- [Architecture — internals](docs/Architecture.md)
