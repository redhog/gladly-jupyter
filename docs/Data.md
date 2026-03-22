# Data — Data, DataGroup, and auto-wrapping

## Column naming convention

Gladly organises all data in named groups. A single `Data` object is placed under the key `"input"` by Gladly's normalisation layer, so its columns are always referenced as `"input.colname"` in the plot config. A `DataGroup` uses the names you assign each source: `"myname.colname"`.

---

## `Data(data, *, quantity_kinds=None, domains=None)`

Wraps a single data source for use in a `Plot`.

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `data` | `pd.DataFrame` \| `dict[str, np.ndarray]` | The raw data. All columns/arrays are converted to `float32`. |
| `quantity_kinds` | `dict[str, str]` | Maps column name → quantity kind string. Overrides pint and column-name fallbacks. |
| `domains` | `dict[str, tuple[float, float]]` | Explicit `[min, max]` per column. Overrides auto-detection from the data. |

### Quantity kind resolution (priority order)

1. `quantity_kinds` dict
2. Pint unit from the column dtype (`pint-pandas` must be installed)
3. Column name

Quantity kinds drive axis auto-linking in `PlotGroup` and axis labelling.

### Examples

```python
import gladly_jupyter as gl
import pandas as pd
import numpy as np

# From a DataFrame
data = gl.Data(df)

# From a dict of numpy arrays
data = gl.Data({"x": np.linspace(0, 1, 1000), "y": np.random.randn(1000)})

# Explicit quantity kinds
data = gl.Data(df, quantity_kinds={"time": "s", "depth": "m"})

# Explicit domains (override auto-detection)
data = gl.Data(df, quantity_kinds={"x": "time"}, domains={"x": (0.0, 100.0)})
```

### With Pint units

When `pint-pandas` is installed, units attached to DataFrame columns are picked up automatically:

```python
import pint_pandas
df["time"]  = df["time"].astype("pint[s]")
df["depth"] = df["depth"].astype("pint[m]")

data = gl.Data(df)
# quantity kinds inferred as "s" and "m" — no extra config needed
```

---

## `DataGroup(frames)`

Wraps multiple named data sources for use in a single `Plot`.

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `frames` | `dict[str, Data \| pd.DataFrame]` | Named data sources. Plain DataFrames are auto-wrapped in `Data`. |

### Column references

Columns are referenced in the plot config as `"name.colname"`, where `name` is the key in `frames`.

### Examples

```python
# DataGroup from plain DataFrames (auto-wrapped)
data = gl.DataGroup({"raw": df_raw, "filtered": df_filtered})

# DataGroup mixing explicit Data and plain DataFrames
data = gl.DataGroup({
    "raw":      gl.Data(df_raw,      quantity_kinds={"time": "s"}),
    "filtered": gl.Data(df_filtered, quantity_kinds={"time": "s"}),
})
```

---

## Auto-wrapping

`Plot` and `PlotGroup` accept raw data in addition to explicit `Data` / `DataGroup` objects. The wrapping rules are:

| Python value | Wrapped as |
|---|---|
| `gl.Data(...)` | Used as-is |
| `gl.DataGroup(...)` | Used as-is |
| `pd.DataFrame` | `gl.Data(df)` |
| `dict` where values are `np.ndarray` | `gl.Data(dict)` |
| `dict` where values are `pd.DataFrame` or `Data` | `gl.DataGroup(dict)` |

```python
# All of these are equivalent:
gl.Plot(config, df)
gl.Plot(config, gl.Data(df))
gl.Plot(config, {"x": arr_x, "y": arr_y})   # dict of arrays → Data
gl.Plot(config, {"raw": df1, "proc": df2})   # dict of DataFrames → DataGroup
```
