# Architecture

## Overview

```
Python kernel                          Browser
─────────────────────────────────────────────────────────────────────
Plot.__init__()
  │  registers columns in kernel HTTP server
  │  serializes metadata + config as anywidget traits
  └──────────────────────────────────────────────────────► render()
                                                              │  loads Gladly from CDN
                                                              │  applies registrations
                                                              │  fetches columns from kernel HTTP server
                                                              │  calls plot.update({ config, data })
                                                              └──► WebGL rendering
```

---

## Data transport

Large datasets never pass through the Jupyter comm WebSocket. Instead:

1. At `Plot` construction, each column is registered in an in-process **Tornado HTTP server** running on a random port inside the kernel (`kernel_server.py`).
2. The port and a UUID widget ID are synced to the browser as anywidget traits.
3. The browser fetches each column as a raw `float32` binary payload via `fetch()`. HTTP `Range` headers are supported for partial reads.
4. The Tornado server serves from kernel memory (numpy arrays) with no disk I/O.

Because the browser connects directly to the kernel's HTTP server (not through the Jupyter server), data throughput is limited only by localhost networking — typically hundreds of MB/s.

### Column registration paths

| Data type | Kernel server path |
|---|---|
| Single `Data` | `/{col_name}` |
| `DataGroup` | `/{group_name}/{col_name}` |

The widget ID is part of the URL path so multiple plots never collide.

---

## Trait sync (Python ↔ JS)

anywidget keeps a set of traits synchronized via the Jupyter comm WebSocket. Only small, JSON-serializable values travel this path:

| Trait | Direction | Content |
|---|---|---|
| `config` | Python → JS | Plot configuration dict |
| `_meta` | Python → JS | Column metadata (length, min, max, quantityKind) |
| `_kernel_port` | Python → JS | Port for the kernel HTTP server |
| `_widget_id` | Python → JS | UUID for data URL paths |
| `_registrations` | Python → JS | JS code string for quantity-kind and layer-type registrations |
| `_links` | Python ↔ JS | Axis link records (added by `link_axes`, removed by `link.unlink()`) |

Trait changes trigger re-renders automatically. For example, `plot.update(config=new_config)` sets the `config` trait, which the JS side observes and passes to `plot.update({ config })`.

---

## Round-trip messages

`get_config()` and `schema()` use anywidget's custom message channel:

```
Python                                 JS
──────                                 ──
plot.send({'type': 'getConfig', ...})  ──►  model.on('msg:custom', ...)
                                               plot.getConfig()
plot.on_msg(handler)               ◄──  model.send({'type': 'configResponse', ...})
```

The Python side blocks on a `threading.Event` (sync variant) or an `asyncio.Future` (async variant) with a configurable timeout.

---

## Cross-widget axis linking

Axis links are managed by a **module-level plot registry** in `widget.js`:

```js
const _plotRegistry = {};       // widget_id → { plot, links, jsLinks }
const _establishedLinks = new Set();
```

When `gl.link_axes(p1.axis.xaxis_bottom, p2.axis.xaxis_bottom)` is called in Python:

1. A UUID link ID is generated.
2. Symmetric link records are appended to both plots' `_links` traits.
3. JS observes the `_links` trait change and calls `tryEstablishLink()`.
4. If the other plot is already in `_plotRegistry`, `Gladly.linkAxes()` is called immediately.
5. If not, the link is held pending. When the second plot renders and registers, it resolves all pending links from both sides.

`link.unlink()` removes the link records from both `_links` traits. JS observes the removal, retrieves the stored `jsLink` object, and calls `jsLink.unlink()`.

After a link is established, domain changes (zoom/pan) propagate directly between JS plot instances with no Python involvement.

---

## Gladly loading

Gladly is loaded once per page from CDN:

```
https://redhog.github.io/gladly/dist/gladly.iife.min.js
```

A module-level promise (`_gladlyPromise`) ensures only one `<script>` tag is injected regardless of how many widgets are on the page. The IIFE sets `globalThis.Gladly`.

---

## Cleanup

- `Plot.__del__()` calls `kernel_server.unregister(widget_id)` to free column memory.
- The anywidget cleanup function (returned from `render()`) removes trait observers, message handlers, unlinks all axes, and removes the plot from `_plotRegistry`.
- `PlotGroup` cleanup calls `group.destroy()` on the Gladly `PlotGroup` instance.
