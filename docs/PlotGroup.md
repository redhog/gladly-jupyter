# PlotGroup

`gl.PlotGroup` renders multiple `Plot` widgets stacked vertically in a single Jupyter cell and optionally links their axes automatically.

---

## Constructor

```python
group = gl.PlotGroup(plots, auto_link=True)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `plots` | `dict[str, Plot]` | — | Named plots to render. Order is preserved. |
| `auto_link` | `bool` | `True` | Automatically link axes that share the same quantity kind across plots. |

### Example

```python
p1 = gl.Plot(
    {"layers": [{"points": {"xData": "input.time", "yData": "input.depth"}}]},
    gl.Data(df1, quantity_kinds={"time": "s", "depth": "m"}),
)
p2 = gl.Plot(
    {"layers": [{"points": {"xData": "input.time", "yData": "input.velocity"}}]},
    gl.Data(df2, quantity_kinds={"time": "s", "velocity": "m/s"}),
)

# Both plots share quantity kind "s" on their x-axis → automatically linked
gl.PlotGroup({"depth": p1, "velocity": p2})
```

---

## Auto-linking

When `auto_link=True` (the default), Gladly's `PlotGroup` class scans all plots for axes that share the same quantity kind and links them bidirectionally. Zooming or panning one plot's linked axis updates all others.

Quantity kinds come from the `Data` objects passed to each `Plot` (explicit `quantity_kinds`, pint units, or column-name fallback).

### Disabling auto-link

```python
gl.PlotGroup({"a": p1, "b": p2}, auto_link=False)
```

Use this when you want to control linking explicitly with `gl.link_axes()`. See [Linking](Linking.md).

---

## Notes

- `PlotGroup` takes a **dict** (not a list) so that each plot has a stable name. The insertion order determines the vertical rendering order.
- Individual `Plot` objects in a `PlotGroup` can still be displayed independently in other cells.
- Each plot's config and data are snapshotted at `PlotGroup` construction time. Subsequent calls to `p1.update(...)` do not propagate into an already-constructed `PlotGroup`.
- For dynamic updates to a group, reconstruct the `PlotGroup` with the updated plots.
