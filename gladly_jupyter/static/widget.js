const GLADLY_URL = 'https://redhog.github.io/gladly/dist/gladly.iife.min.js';

// Load once, cache the promise so concurrent widgets don't create multiple script tags.
let _gladlyPromise = null;

function loadGladly() {
  if (_gladlyPromise) return _gladlyPromise;
  _gladlyPromise = new Promise((resolve, reject) => {
    if (globalThis.Gladly) {
      resolve(globalThis.Gladly);
      return;
    }
    const script = document.createElement('script');
    script.src = GLADLY_URL;
    script.onload = () => resolve(globalThis.Gladly);
    script.onerror = () => reject(new Error(`gladly-jupyter: failed to load ${GLADLY_URL}`));
    document.head.appendChild(script);
  });
  return _gladlyPromise;
}

// ─── Data fetching ────────────────────────────────────────────────────────────

function kernelUrl(port, widgetId, path) {
  // Kernel HTTP server runs on a random port on the same host as the notebook.
  return `http://${window.location.hostname}:${port}/gladly/data/${encodeURIComponent(widgetId)}/${path}`;
}

async function fetchColumn(port, widgetId, path) {
  const url = kernelUrl(port, widgetId, path);
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`gladly-jupyter: fetch ${url} → ${resp.status}`);
  return new Float32Array(await resp.arrayBuffer());
}

async function buildRawData(port, widgetId, meta, isGroup) {
  if (isGroup) {
    const result = {};
    for (const [dataName, cols] of Object.entries(meta)) {
      const arrays = {}, quantityKinds = {}, domains = {};
      for (const [colName, info] of Object.entries(cols)) {
        arrays[colName] = await fetchColumn(port, widgetId, `${dataName}/${colName}`);
        quantityKinds[colName] = info.quantityKind;
        domains[colName] = [info.min, info.max];
      }
      result[dataName] = { data: arrays, quantity_kinds: quantityKinds, domains };
    }
    return result;
  } else {
    const arrays = {}, quantityKinds = {}, domains = {};
    for (const [colName, info] of Object.entries(meta)) {
      arrays[colName] = await fetchColumn(port, widgetId, colName);
      quantityKinds[colName] = info.quantityKind;
      domains[colName] = [info.min, info.max];
    }
    return { data: arrays, quantity_kinds: quantityKinds, domains };
  }
}

// ─── Quantity kind registration ───────────────────────────────────────────────

function registerQKsFromMeta(registerAxisQuantityKind, meta, isGroup) {
  const qks = new Set();
  if (isGroup) {
    for (const cols of Object.values(meta)) {
      for (const { quantityKind } of Object.values(cols)) qks.add(quantityKind);
    }
  } else {
    for (const { quantityKind } of Object.values(meta)) qks.add(quantityKind);
  }
  for (const qk of qks) {
    if (qk) registerAxisQuantityKind(qk, { label: qk, scale: 'linear' });
  }
}

// ─── DOM helpers ──────────────────────────────────────────────────────────────

function makePlotContainer(parent) {
  const div = document.createElement('div');
  div.style.cssText = 'width:100%;height:400px;position:relative;';
  parent.appendChild(div);
  return div;
}

// ─── Render ───────────────────────────────────────────────────────────────────

export async function render({ model, el }) {
  const { Plot: GladlyPlot, PlotGroup: GladlyPlotGroup, registerAxisQuantityKind } = await loadGladly();

  el.style.cssText = 'width:100%;display:block;';

  if (model.get('_widget_type') === 'plotgroup') {
    return await renderPlotGroup(model, el, GladlyPlot, GladlyPlotGroup, registerAxisQuantityKind);
  } else {
    return await renderPlot(model, el, GladlyPlot, registerAxisQuantityKind);
  }
}

async function renderPlot(model, el, GladlyPlot, registerAxisQuantityKind) {
  const widgetId = model.get('_widget_id');
  const port = model.get('_kernel_port');
  const meta = model.get('_meta');
  const isGroup = model.get('_is_group');
  const layers = model.get('layers');
  const axes = model.get('axes');

  registerQKsFromMeta(registerAxisQuantityKind, meta, isGroup);

  const container = makePlotContainer(el);
  const rawData = await buildRawData(port, widgetId, meta, isGroup);
  const plot = new GladlyPlot(container, {});
  await plot.update({ config: { layers, axes }, data: rawData });
}

async function renderPlotGroup(model, el, GladlyPlot, GladlyPlotGroup, registerAxisQuantityKind) {
  const plotConfigs = model.get('_plot_configs');
  const autoLink = model.get('_auto_link');

  const namedPlots = {};

  for (let i = 0; i < plotConfigs.length; i++) {
    const { widget_id, kernel_port, meta, is_group, layers, axes } = plotConfigs[i];

    registerQKsFromMeta(registerAxisQuantityKind, meta, is_group);

    const container = makePlotContainer(el);
    const rawData = await buildRawData(kernel_port, widget_id, meta, is_group);
    const plot = new GladlyPlot(container, {});
    await plot.update({ config: { layers, axes }, data: rawData });
    namedPlots[String(i)] = plot;
  }

  const group = new GladlyPlotGroup(namedPlots, { autoLink });
  return () => group.destroy();
}
