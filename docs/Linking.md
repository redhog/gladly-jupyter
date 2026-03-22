# Axis linking

Axes on different plots can be linked so that zooming or panning one automatically updates the other. Links live entirely in the browser — no Python round-trip occurs on zoom/pan.

---

## `plot.axis`

`plot.axis` is an accessor object. Attribute access on it returns a cached `Axis` proxy for the named Gladly axis.

```python
x = plot.axis.xaxis_bottom   # bottom x axis
x = plot.axis.xaxis_top      # top x axis
y = plot.axis.yaxis_left     # left y axis
y = plot.axis.yaxis_right    # right y axis
c = plot.axis.amplitude      # color or filter axis (use the quantity kind name)
```

The same object is returned on every access for a given name:

```python
plot.axis.xaxis_bottom is plot.axis.xaxis_bottom   # True
```

This identity stability is required for `link_axes` to store and track links correctly.

### Available spatial axis names

| Name | Position |
|---|---|
| `xaxis_bottom` | Bottom horizontal axis |
| `xaxis_top` | Top horizontal axis |
| `yaxis_left` | Left vertical axis |
| `yaxis_right` | Right vertical axis |

Color and filter axes use the quantity kind string as the axis name (e.g. `plot.axis.frequency`).

---

## `gl.link_axes(axis1, axis2)` → `Link`

Link two axes bidirectionally. Both must be `Axis` proxy objects obtained from `plot.axis.*`.

```python
link = gl.link_axes(plot1.axis.xaxis_bottom, plot2.axis.xaxis_bottom)
```

The two plots may be:
- In the same `PlotGroup`
- Displayed in different cells (independent widgets)
- Displayed in any order — linking is resolved as soon as both plots have rendered

Linking is established purely in JS via Gladly's `linkAxes()`. After the link is active, domain changes (zoom, pan) propagate directly between the two plot instances in the browser with no Python involvement.

### Multiple links

```python
link1 = gl.link_axes(p1.axis.xaxis_bottom, p2.axis.xaxis_bottom)
link2 = gl.link_axes(p2.axis.yaxis_left,   p3.axis.yaxis_left)
```

---

## `link.unlink()`

Tear down a previously created link.

```python
link = gl.link_axes(p1.axis.xaxis_bottom, p2.axis.xaxis_bottom)

# ... later:
link.unlink()
```

After `unlink()` is called, the `Link` object is spent and should not be used again.

---

## Render-order independence

Links are registered in the browser via a module-level plot registry keyed by widget ID. When `gl.link_axes(a, b)` is called in Python, link records are written to both plots' `_links` traits. In JS:

- If both plots have already rendered → link established immediately.
- If one has not rendered yet → the link is held as pending and resolved the moment the second plot registers itself.

You can call `gl.link_axes()` before or after `display()`, in any order.

---

## Relationship to PlotGroup auto-linking

`gl.link_axes()` and `PlotGroup(auto_link=True)` are independent mechanisms:

- `auto_link` links axes with matching quantity kinds automatically when a `PlotGroup` is created.
- `gl.link_axes()` links any two specific axes explicitly, regardless of quantity kind, and does not require a `PlotGroup`.

Both can be used together.

---

## `Axis` object

`Axis` objects are lightweight Python proxies. They carry:

| Attribute | Description |
|---|---|
| `axis._plot` | The owning `Plot` widget |
| `axis._name` | The Gladly axis ID string |
| `axis._links` | List of active `Link` objects involving this axis |

These are internal attributes; the public interface is `plot.axis.<name>` and `gl.link_axes()`.
