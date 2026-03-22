# Plot

`gl.Plot` is the main widget. It renders a single Gladly plot inside a Jupyter cell.

---

## Constructor

```python
plot = gl.Plot(config, data)
```

| Parameter | Type | Description |
|---|---|---|
| `config` | `dict` | Gladly plot configuration. Passed through to JS verbatim — any valid Gladly config works. |
| `data` | `Data \| DataGroup \| pd.DataFrame \| dict` | The data to plot. Auto-wrapped if not already a `Data` or `DataGroup`. |

The widget is displayed when the `Plot` object is returned from or assigned in a notebook cell (standard IPython / Jupyter display protocol).

### Config dict

The config dict is the same structure as Gladly's JS `plot.update({ config })` argument. All keys are optional:

```python
config = {
    # List of layers. Each item is a one-key dict: { layer_type_name: params }.
    "layers": [
        {"points":    {"xData": "input.x", "yData": "input.y"}},
        {"lines":     {"xData": "input.x", "yData": "input.y"}},
        {"bars":      {"xData": "input.x", "yData": "input.y"}},
        {"histogram": {"data":  "input.y", "bins": 100}},
        {"tile":      {"url":   "https://tile.openstreetmap.org/{z}/{x}/{y}.png"}},
    ],

    # Named transforms applied before layers.
    "transforms": [
        {"name": "h", "transform": {"HistogramData": {"input": "input.y", "bins": 50}}}
    ],

    # Axis configuration. Spatial axes: xaxis_bottom, xaxis_top, yaxis_left, yaxis_right.
    # Color/filter axes use the quantity kind name as the key.
    "axes": {
        "xaxis_bottom": {"label": "Time (s)", "min": 0.0, "max": 100.0, "scale": "linear"},
        "yaxis_left":   {"label": "Depth (m)", "scale": "log"},
        "amplitude":    {"colorscale": "viridis", "colorbar": "vertical"},
    },

    # Floating colorbar widgets.
    "colorbars": [
        {"xAxis": "frequency", "yAxis": "amplitude", "colorscale": "plasma"}
    ],
}
```

For the full list of layer types and their parameters, see the [Gladly layer type docs](../../docs/configuration/BuiltInLayerTypes.md).

### Column references

Columns are referenced in the config as `"groupname.colname"`:
- Single `Data` / DataFrame → group name is always `"input"` (e.g. `"input.time"`)
- `DataGroup` → use the name you gave each source (e.g. `"raw.time"`, `"filtered.time"`)

---

## `plot.update(config=None, data=None)`

Update the config and/or data after the plot has been created. Mirrors JS `plot.update({ config, data })`.

```python
# Update config only (e.g. change axis labels)
plot.update(config={"layers": [...], "axes": {...}})

# Update data only (re-streams all columns)
plot.update(data=new_df)

# Update both
plot.update(config=new_config, data=new_df)
```

Config updates are applied immediately via the anywidget trait sync. Data updates re-register all columns with the kernel HTTP server and update the column metadata.

---

## `plot.axis`

Attribute-access proxy that returns `Axis` proxy objects by name. Each name maps to a Gladly axis ID.

```python
# Spatial axes
x = plot.axis.xaxis_bottom
x = plot.axis.xaxis_top
y = plot.axis.yaxis_left
y = plot.axis.yaxis_right

# Color or filter axis (use the quantity kind name)
c = plot.axis.amplitude
```

The same `Axis` object is returned on every access (cached). This means identity is stable, which is required for `link_axes` to store links correctly.

See [Linking](Linking.md) for how to use axes.

---

## `plot.get_config(timeout=5.0)` → `dict`

Request the current plot configuration from the browser, including live axis domains (current zoom/pan state). Blocks the Python kernel until the JS responds or the timeout expires.

```python
config = plot.get_config()
print(config["axes"]["xaxis_bottom"])  # {'min': 3.2, 'max': 7.8, ...}
```

Returns `None` if the widget has not been displayed or the timeout expires.

---

## `plot.schema(timeout=5.0)` → `dict`

Request the JSON Schema for the plot configuration from the browser. The schema is data-dependent (it enumerates available column names as enum values for data attribute fields). Blocks until the JS responds.

```python
import json
schema = plot.schema()
print(json.dumps(schema, indent=2))
```

Returns `None` if the widget has not been displayed or the timeout expires.

---

## `await plot.async_get_config(timeout=5.0)` → `dict`

Async variant of `get_config()`. Use in async notebook cells (JupyterLab supports `await` at the top level):

```python
config = await plot.async_get_config()
```

---

## `await plot.async_schema(timeout=5.0)` → `dict`

Async variant of `schema()`.

```python
schema = await plot.async_schema()
```

---

## Traits (advanced)

The following anywidget traits are synced between Python and JavaScript. Direct access is rarely needed.

| Trait | Type | Description |
|---|---|---|
| `config` | `dict` | The current plot config. Setting this re-renders the plot. |
| `_widget_id` | `str` | UUID identifying this widget's data on the kernel HTTP server. |
| `_kernel_port` | `int` | Port of the kernel HTTP server. |
| `_meta` | `dict` | Column metadata (length, quantityKind, min, max) per column. |
| `_is_group` | `bool` | Whether the data is a DataGroup. |
| `_registrations` | `str` | JS code for module-level registrations, applied before rendering. |
| `_links` | `list` | Active axis link records used for cross-widget linking. |
