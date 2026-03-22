# gladly-jupyter

Jupyter widget for [Gladly](https://github.com/redhog/gladly) — GPU-accelerated plotting via WebGL.

Renders `Plot`, `DataGroup`, and `PlotGroup` directly from pandas DataFrames in Jupyter notebooks. Large columns (gigabytes) are streamed to the browser over HTTP rather than sent through the Jupyter comm, so there is no practical size limit.

Gladly itself is loaded from CDN — no JavaScript build step is required.

## Requirements

- Python ≥ 3.8
- JupyterLab ≥ 4 or Jupyter Notebook ≥ 7 (both use `jupyter_server` ≥ 2)
- A WebGL-capable browser

## Installation

### From PyPI

```bash
pip install gladly-jupyter
```

### From source

```bash
pip install ./gladly_jupyter   # from the repo root, where gladly_jupyter/ lives
```

Or, from inside the package directory:

```bash
cd gladly_jupyter
pip install .
```

### With optional Pint support

[pint](https://pint.readthedocs.io) and [pint-pandas](https://pint-pandas.readthedocs.io) allow quantity kinds to be inferred automatically from physical units attached to DataFrame columns:

```bash
pip install "gladly-jupyter[pint]"
# or from source:
pip install "./gladly_jupyter[pint]"
```

### Verifying the server extension

The server extension is enabled automatically when the package is installed — no manual enable step is needed. To confirm it is active:

```bash
jupyter server extension list
```

## Usage

### Column naming

Gladly always organises data in named groups. A single DataFrame is automatically placed in a group called `input`, so its columns are referenced as `"input.colname"` in layer specs. For a `DataGroup`, you use the name you gave each DataFrame: `"raw.colname"`.

### Single DataFrame

```python
import gladly_jupyter as gl
import pandas as pd
import numpy as np

t = np.linspace(0, 10, 100_000, dtype="float32")
df = pd.DataFrame({"time": t, "signal": np.sin(t)})

gl.Plot(
    df,
    layers=[{"points": {"xData": "input.time", "yData": "input.signal"}}],
    axes={
        "xaxis_bottom": {"label": "Time (s)"},
        "yaxis_left":   {"label": "Signal"},
    },
)
```

### Explicit quantity kinds

Quantity kinds drive axis auto-linking in `PlotGroup`. If not specified they fall back to the column name.

```python
gl.Plot(
    df,
    layers=[{"points": {"xData": "input.time", "yData": "input.voltage"}}],
    quantity_kinds={"time": "time", "voltage": "mV"},
)
```

### Pint-aware DataFrames

When `pint-pandas` is installed, units are picked up automatically — the unit string (`"s"`, `"mV"`, …) becomes the quantity kind:

```python
import pint_pandas
df["time"]    = df["time"].astype("pint[s]")
df["voltage"] = df["voltage"].astype("pint[mV]")

gl.Plot(df, layers=[{"points": {"xData": "input.time", "yData": "input.voltage"}}])
# quantity kinds inferred as "s" and "mV" — no extra config needed
```

### DataGroup — multiple DataFrames in one plot

Column names in layer specs use Gladly's dot notation (`"name.column"`):

```python
dg = gl.DataGroup({"raw": df_raw, "filtered": df_filtered})

gl.Plot(
    dg,
    layers=[
        {"points": {"xData": "raw.time",      "yData": "raw.signal"}},
        {"points": {"xData": "filtered.time", "yData": "filtered.signal"}},
    ],
)
```

Per-group quantity kinds:

```python
gl.DataGroup(
    {"raw": df_raw, "filtered": df_filtered},
    quantity_kinds={
        "raw":      {"time": "s", "signal": "mV"},
        "filtered": {"time": "s", "signal": "mV"},
    },
)
```

### PlotGroup — linked axes across multiple plots

Plots whose axes share the same quantity kind are automatically linked when `auto_link=True` (the default). With Pint columns, this happens without any extra configuration:

```python
p1 = gl.Plot(df1, layers=[{"points": {"xData": "input.time", "yData": "input.depth"}}])
p2 = gl.Plot(df2, layers=[{"points": {"xData": "input.time", "yData": "input.velocity"}}])

gl.PlotGroup([p1, p2])          # time axes linked automatically
```

Disable auto-linking to manage links manually:

```python
gl.PlotGroup([p1, p2], auto_link=False)
```

## How it works

- **Data transport**: columns are served as raw `float32` binary over HTTP from a Jupyter server extension (`/gladly/data/<widget-id>/<column-path>`), with `Range` header support. Data never passes through the Jupyter comm WebSocket.
- **Quantity kinds**: resolved per column as: explicit `quantity_kinds` dict → Pint unit string → column name. The same string is registered in Gladly's `AxisQuantityKindRegistry`, enabling `PlotGroup` axis auto-linking.
- **Rendering**: Gladly is loaded from `https://redhog.github.io/gladly/dist/gladly.esm.js`. No local JS build is needed.
