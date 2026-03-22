# Registries

gladly-jupyter exposes Python wrappers for Gladly's module-level registries. Registrations accumulate in a module-level list and are applied in the browser before each `Plot` first renders.

**Register before creating plots.** Registrations are snapshotted at `Plot` construction time. Calls to `register_*` after a `Plot` has been constructed are not visible to that plot.

---

## `gl.register_axis_quantity_kind(name, **kwargs)`

Register a quantity kind in Gladly's `AxisQuantityKindRegistry`.

```python
gl.register_axis_quantity_kind(name, **kwargs)
```

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Quantity kind identifier (e.g. `"frequency"`, `"s"`, `"m/s"`). |
| `**kwargs` | any | Forwarded verbatim to `Gladly.registerAxisQuantityKind(name, kwargs)`. |

All kwargs are serialized to JSON and forwarded to the JS side without modification, so any property supported by the current or future Gladly version can be passed.

### Common kwargs

| kwarg | Type | Description |
|---|---|---|
| `label` | `str` | Human-readable axis label shown on the plot. |
| `scale` | `"linear"` \| `"log"` | Default scale type for this quantity kind. |

### Examples

```python
gl.register_axis_quantity_kind("frequency", label="Frequency (Hz)", scale="log")
gl.register_axis_quantity_kind("s",         label="Time (s)",        scale="linear")
gl.register_axis_quantity_kind("m",         label="Depth (m)")
gl.register_axis_quantity_kind("amplitude", label="Amplitude (dB)",  colorscale="viridis")
```

Registrations for the same name are **merged** (later calls add or overwrite individual keys).

---

## `gl.register_layer_type(name, args)`

Register a custom layer type in Gladly's `LayerTypeRegistry`.

```python
gl.register_layer_type(name, args)
```

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Layer type name used in the `"layers"` config array. |
| `args` | `dict` | Arguments to pass to `new Gladly.LayerType({...})`, serialized recursively. |

The `args` dict is serialized by `to_js_expr()` (see below) and inserted into a `new Gladly.LayerType({...})` constructor call. Registration is guarded so re-applying the same name (e.g. from multiple plots) is idempotent.

### Serialization of `args` values

| Python value | JS output |
|---|---|
| `str` | `` `string` `` (JS template literal) |
| `gl.js(str)` | `str` verbatim (raw JS expression) |
| `bool` | `true` / `false` |
| `int`, `float` | number literal |
| `None` | `null` |
| `dict` | `{ "key": value, ... }` recursively |
| `list` | `[value, ...]` recursively |

### `gl.js(expr)` — raw JS expression

Wraps a string so it is inserted into the generated JS as-is rather than as a template literal. Use this for function expressions, object literals, and any JS that is not a plain string value.

```python
gl.js("(data) => ({ type: 'object' })")   # function
gl.js("{ x: 1, y: 2 }")                  # object literal
gl.js("42 + offset")                      # expression
```

### Example — complete custom layer type

```python
gl.register_layer_type("myScatter", {
    # GLSL shader strings — plain Python strings become JS template literals
    "vertShader": """
        precision mediump float;
        attribute float a_x, a_y;
        uniform mat4 u_mvp;
        void main() {
            gl_Position = u_mvp * vec4(a_x, a_y, 0.0, 1.0);
            gl_PointSize = 3.0;
        }
    """,
    "fragShader": """
        precision mediump float;
        void main() { gl_FragColor = vec4(0.2, 0.6, 1.0, 1.0); }
    """,

    # Function expression — must use gl.js()
    "schema": gl.js("""
        (data) => ({
            type: "object",
            properties: {
                xData: { type: "string" },
                yData: { type: "string" },
            },
            required: ["xData", "yData"],
        })
    """),

    # Plain dict — serialized recursively
    "attributes": {
        "x": {"data": gl.js("params.xData")},
        "y": {"data": gl.js("params.yData")},
    },
})
```

For the full `LayerType` constructor API see the [Gladly extension docs](../../docs/extension-api/LayerTypes.md).

---

## `gl.js(expr)` — standalone helper

`gl.js` can also be used outside of `register_layer_type` wherever `to_js_expr()` is called — for example in nested `args` dicts.

```python
from gladly_jupyter import js

expr = js("(data) => data.columns()")
```

`gl.js` and `from gladly_jupyter import js` are equivalent.

---

## Execution context

In the browser, registered code runs as:

```js
// quantity kinds:
Gladly.registerAxisQuantityKind("frequency", {"label": "Frequency (Hz)", "scale": "log"});

// layer types (guarded against double-registration):
if (!Gladly.getRegisteredLayerTypes().includes("myScatter"))
    Gladly.registerLayerType("myScatter", new Gladly.LayerType({ vertShader: `...`, ... }));
```

The `Gladly` variable refers to the full Gladly module (all exports from `src/index.js`).
