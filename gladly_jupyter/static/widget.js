const GLADLY_URL = 'https://redhog.github.io/gladly/dist/gladly.iife.min.js';

let _gladlyPromise = null;

// Global registry for cross-widget axis linking.
// widget_id → { plot, links: [...], jsLinks: Map<linkId, jsLinkObj> }
const _plotRegistry = {};
const _establishedLinks = new Set();  // link IDs already linked in JS

function loadGladly() {
  if (_gladlyPromise) return _gladlyPromise;
  _gladlyPromise = new Promise((resolve, reject) => {
    if (globalThis.Gladly) { resolve(globalThis.Gladly); return; }
    const script = document.createElement('script');
    script.src = GLADLY_URL;
    script.onload = () => resolve(globalThis.Gladly);
    script.onerror = () => reject(new Error(`gladly-jupyter: failed to load ${GLADLY_URL}`));
    document.head.appendChild(script);
  });
  return _gladlyPromise;
}

// ── Data fetching ──────────────────────────────────────────────────────────────

function kernelUrl(port, widgetId, path) {
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

// ── Registrations ──────────────────────────────────────────────────────────────

function applyRegistrations(Gladly, registrationsJs) {
  if (!registrationsJs) return;
  try {
    new Function('Gladly', registrationsJs)(Gladly);
  } catch (e) {
    console.error('gladly-jupyter: error applying registrations:', e);
  }
}

function registerQKsFromMeta(Gladly, meta, isGroup) {
  const qks = new Set();
  if (isGroup) {
    for (const cols of Object.values(meta)) {
      for (const { quantityKind } of Object.values(cols)) qks.add(quantityKind);
    }
  } else {
    for (const { quantityKind } of Object.values(meta)) qks.add(quantityKind);
  }
  for (const qk of qks) {
    if (qk) Gladly.registerAxisQuantityKind(qk, { label: qk, scale: 'linear' });
  }
}

// ── Link management ────────────────────────────────────────────────────────────

function tryEstablishLink(myWidgetId, link, Gladly) {
  const { id, myAxis, otherId, otherAxis } = link;
  if (_establishedLinks.has(id)) return;

  const myEntry    = _plotRegistry[myWidgetId];
  const otherEntry = _plotRegistry[otherId];
  if (!myEntry || !otherEntry) return;

  try {
    const jsLink = Gladly.linkAxes(
      myEntry.plot._getAxis(myAxis),
      otherEntry.plot._getAxis(otherAxis)
    );
    _establishedLinks.add(id);
    myEntry.jsLinks.set(id, jsLink);
    otherEntry.jsLinks.set(id, jsLink);
  } catch (e) {
    console.warn(`gladly-jupyter: linkAxes failed (${myAxis} ↔ ${otherAxis}):`, e);
  }
}

function unestablishLink(linkId) {
  if (!_establishedLinks.has(linkId)) return;
  for (const entry of Object.values(_plotRegistry)) {
    const jsLink = entry.jsLinks.get(linkId);
    if (jsLink) { jsLink.unlink(); break; }
  }
  for (const entry of Object.values(_plotRegistry)) {
    entry.jsLinks.delete(linkId);
  }
  _establishedLinks.delete(linkId);
}

function registerPlot(widgetId, plot, links, Gladly) {
  const entry = { plot, links, jsLinks: new Map() };
  _plotRegistry[widgetId] = entry;

  // Resolve own links to already-registered plots.
  for (const link of links) {
    tryEstablishLink(widgetId, link, Gladly);
  }

  // Resolve other plots' pending links that point to this new plot.
  for (const [otherId, otherEntry] of Object.entries(_plotRegistry)) {
    if (otherId === widgetId) continue;
    for (const link of otherEntry.links) {
      if (link.otherId === widgetId) {
        tryEstablishLink(otherId, link, Gladly);
      }
    }
  }
}

// ── DOM helpers ────────────────────────────────────────────────────────────────

function makePlotContainer(parent) {
  const div = document.createElement('div');
  div.style.cssText = 'width:100%;height:400px;position:relative;';
  parent.appendChild(div);
  return div;
}

// ── Render ─────────────────────────────────────────────────────────────────────

export async function render({ model, el }) {
  const Gladly = await loadGladly();
  el.style.cssText = 'width:100%;display:block;';

  if (model.get('_widget_type') === 'plotgroup') {
    return renderPlotGroup(model, el, Gladly);
  } else {
    return renderPlot(model, el, Gladly);
  }
}

async function renderPlot(model, el, Gladly) {
  const widgetId = model.get('_widget_id');
  const port     = model.get('_kernel_port');
  const meta     = model.get('_meta');
  const isGroup  = model.get('_is_group');
  const config   = model.get('config');
  const links    = model.get('_links') || [];

  applyRegistrations(Gladly, model.get('_registrations'));
  registerQKsFromMeta(Gladly, meta, isGroup);

  const container = makePlotContainer(el);
  const rawData   = await buildRawData(port, widgetId, meta, isGroup);
  const plot      = new Gladly.Plot(container, {});
  await plot.update({ config, data: rawData });

  registerPlot(widgetId, plot, links, Gladly);

  // ── Observe config changes ────────────────────────────────────────────────
  const onConfigChange = () => {
    plot.update({ config: model.get('config') });
  };
  model.on('change:config', onConfigChange);

  // ── Observe link changes (for unlink()) ───────────────────────────────────
  const onLinksChange = () => {
    const newLinks  = model.get('_links') || [];
    const newIds    = new Set(newLinks.map(l => l.id));
    const entry     = _plotRegistry[widgetId];

    // Tear down removed links.
    for (const [id] of entry.jsLinks) {
      if (!newIds.has(id)) unestablishLink(id);
    }

    // Update stored links list and try to establish any new ones.
    entry.links = newLinks;
    for (const link of newLinks) tryEstablishLink(widgetId, link, Gladly);
  };
  model.on('change:_links', onLinksChange);

  // ── Handle round-trip messages (get_config / schema) ─────────────────────
  const onMsg = (msg) => {
    if (msg.type === 'getConfig') {
      model.send({ type: 'configResponse', requestId: msg.requestId, result: plot.getConfig() });
    } else if (msg.type === 'getSchema') {
      model.send({ type: 'schemaResponse', requestId: msg.requestId, result: Gladly.Plot.schema(rawData, plot.currentConfig) });
    }
  };
  model.on('msg:custom', onMsg);

  return () => {
    model.off('change:config', onConfigChange);
    model.off('change:_links', onLinksChange);
    model.off('msg:custom', onMsg);
    const entry = _plotRegistry[widgetId];
    if (entry) {
      for (const [id] of entry.jsLinks) unestablishLink(id);
    }
    delete _plotRegistry[widgetId];
  };
}

async function renderPlotGroup(model, el, Gladly) {
  const plotConfigs = model.get('_plot_configs');
  const autoLink    = model.get('_auto_link');
  const namedPlots  = {};

  for (const pc of plotConfigs) {
    const { name, widget_id, kernel_port, meta, is_group, config, registrations } = pc;

    applyRegistrations(Gladly, registrations);
    registerQKsFromMeta(Gladly, meta, is_group);

    const container = makePlotContainer(el);
    const rawData   = await buildRawData(kernel_port, widget_id, meta, is_group);
    const plot      = new Gladly.Plot(container, {});
    await plot.update({ config, data: rawData });
    namedPlots[name] = plot;
  }

  const group = new Gladly.PlotGroup(namedPlots, { autoLink });
  return () => group.destroy();
}
