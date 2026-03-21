import {
  Plot as GladlyPlot,
  PlotGroup as GladlyPlotGroup,
  registerAxisQuantityKind,
} from 'https://redhog.github.io/gladly/dist/gladly.esm.js';

// ─── Data fetching ────────────────────────────────────────────────────────────

async function fetchColumn(baseUrl, widgetId, path) {
  const base = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
  const url = `${base}/gladly/data/${encodeURIComponent(widgetId)}/${path}`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`gladly-jupyter: fetch ${url} → ${resp.status}`);
  return new Float32Array(await resp.arrayBuffer());
}

/**
 * Fetch all columns for one plot's data and return a raw data object
 * suitable for passing directly to GladlyPlot.update({ data }).
 *
 * Single DataFrame meta:  { colName: { length, quantityKind, min, max } }
 * DataGroup meta:         { dataName: { colName: { ... } } }
 *
 * Output follows Gladly's columnar format:
 *   { data: { col: Float32Array }, quantity_kinds: { col: qk }, domains: { col: [min, max] } }
 * or for DataGroup:
 *   { dataName: { data: {...}, quantity_kinds: {...}, domains: {...} } }
 */
async function buildRawData(baseUrl, widgetId, meta, isGroup) {
  if (isGroup) {
    const result = {};
    for (const [dataName, cols] of Object.entries(meta)) {
      const arrays = {}, quantityKinds = {}, domains = {};
      for (const [colName, info] of Object.entries(cols)) {
        arrays[colName] = await fetchColumn(baseUrl, widgetId, `${dataName}/${colName}`);
        quantityKinds[colName] = info.quantityKind;
        domains[colName] = [info.min, info.max];
      }
      result[dataName] = { data: arrays, quantity_kinds: quantityKinds, domains };
    }
    return result;
  } else {
    const arrays = {}, quantityKinds = {}, domains = {};
    for (const [colName, info] of Object.entries(meta)) {
      arrays[colName] = await fetchColumn(baseUrl, widgetId, colName);
      quantityKinds[colName] = info.quantityKind;
      domains[colName] = [info.min, info.max];
    }
    return { data: arrays, quantity_kinds: quantityKinds, domains };
  }
}

// ─── Quantity kind registration ───────────────────────────────────────────────

/**
 * Register all quantity kinds from a meta object so Gladly knows about them.
 * Unregistered QKs already work (they default to label=name, scale=linear),
 * but explicit registration lets PlotGroup auto-link axes that share a QK.
 */
function registerQKsFromMeta(meta, isGroup) {
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
  el.style.cssText = 'width:100%;display:block;';

  const widgetType = model.get('_widget_type');

  if (widgetType === 'plotgroup') {
    return await renderPlotGroup(model, el);
  } else {
    return await renderPlot(model, el);
  }
}

async function renderPlot(model, el) {
  const widgetId = model.get('_widget_id');
  const meta = model.get('_meta');
  const isGroup = model.get('_is_group');
  const layers = model.get('layers');
  const axes = model.get('axes');
  const baseUrl = model.get('_server_base_url');

  registerQKsFromMeta(meta, isGroup);

  const container = makePlotContainer(el);
  const rawData = await buildRawData(baseUrl, widgetId, meta, isGroup);
  const plot = new GladlyPlot(container, {});
  await plot.update({ config: { layers, axes }, data: rawData });
}

async function renderPlotGroup(model, el) {
  const plotConfigs = model.get('_plot_configs');
  const autoLink = model.get('_auto_link');
  const baseUrl = model.get('_server_base_url');

  const namedPlots = {};

  for (let i = 0; i < plotConfigs.length; i++) {
    const { widget_id, meta, is_group, layers, axes } = plotConfigs[i];

    registerQKsFromMeta(meta, is_group);

    const container = makePlotContainer(el);
    const rawData = await buildRawData(baseUrl, widget_id, meta, is_group);
    const plot = new GladlyPlot(container, {});
    await plot.update({ config: { layers, axes }, data: rawData });
    namedPlots[String(i)] = plot;
  }

  const group = new GladlyPlotGroup(namedPlots, { autoLink });
  return () => group.destroy();
}
