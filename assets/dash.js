/* Minimal data runtime for the static dashboard: loads data/*.json,
   runs derived calculations, keeps filter state, and re-checks for
   fresh data every few minutes. No network calls beyond this site. */
(function () {
  'use strict';
  var DATASETS = ['deals', 'news', 'timeline', 'catalysts', 'kpis', 'capstats', 'capquarters',
    'capmkts', 'financings', 'market', 'bid', 'comps', 'distress'];
  var DEFAULT_PARAMS = { cat_state: 'MA', deal_state: null, deal_status: 'All', news_tag: 'All', fin_type: 'All' };
  var POLL_MS = 5 * 60 * 1000;

  var store = {};
  var calcs = {};
  var calcCache = {};
  var listeners = [];
  var meta = null;
  var version = 0;
  var params = Object.assign({}, DEFAULT_PARAMS);

  try {
    var saved = JSON.parse(localStorage.getItem('cx-params') || 'null');
    if (saved && typeof saved === 'object') Object.keys(DEFAULT_PARAMS).forEach(function (k) { if (k in saved) params[k] = saved[k]; });
  } catch (e) { /* storage unavailable */ }

  DATASETS.forEach(function (id) { store[id] = { status: 'loading', data: null }; });

  function notify() {
    version += 1;
    calcCache = {};
    listeners.forEach(function (cb) { try { cb(); } catch (e) { console.error(e); } });
  }

  function fetchJson(path) {
    return fetch(path + '?v=' + Date.now(), { cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error(path + ' ' + r.status);
      return r.json();
    });
  }

  function loadAll() {
    return Promise.all(DATASETS.map(function (id) {
      return fetchJson('data/' + id + '.json')
        .then(function (rows) { store[id] = { status: 'ok', data: Array.isArray(rows) ? rows : [] }; })
        .catch(function (err) { console.error(err); if (store[id].status !== 'ok') store[id] = { status: 'error', data: null }; });
    })).then(notify);
  }

  function poll() {
    fetchJson('data/meta.json').then(function (m) {
      var changed = !meta || m.updated !== meta.updated;
      meta = m;
      if (changed) loadAll();
      else notify();
    }).catch(function () {
      // meta missing: still load the data once; afterwards keep what is shown
      if (store.deals.status === 'loading') loadAll();
    });
  }

  function runCalc(name) {
    if (calcCache[name]) return calcCache[name];
    var def = calcs[name];
    var inputs = def.inputs.map(function (id) { return window.dash.data(id); });
    var out;
    if (inputs.every(function (r) { return r.status === 'ok'; })) {
      try { out = { status: 'ok', data: def.fn.apply(null, inputs.map(function (r) { return r.data; })) }; }
      catch (e) { console.error(e); out = { status: 'error', data: null }; }
    } else if (inputs.some(function (r) { return r.status === 'error'; })) out = { status: 'error', data: null };
    else out = { status: 'loading', data: null };
    calcCache[name] = out;
    return out;
  }

  window.dash = {
    colors: ['var(--cx-cat-1)', 'var(--cx-cat-2)', 'var(--cx-cat-3)', 'var(--cx-cat-4)', 'var(--cx-cat-5)'],
    data: function (id) {
      if (calcs[id]) return runCalc(id);
      return store[id] || { status: 'missing', data: null };
    },
    calc: function (name, def) { calcs[name] = def; },
    onData: function (cb) { listeners.push(cb); },
    params: function () { return Object.assign({}, params); },
    setParams: function (p) {
      Object.assign(params, p);
      try { localStorage.setItem('cx-params', JSON.stringify(params)); } catch (e) { /* ignore */ }
      notify();
    },
    setLink: function (id) { try { history.replaceState(null, '', '#' + id); } catch (e) { /* ignore */ } },
    meta: function () { return meta; },
  };

  document.addEventListener('DOMContentLoaded', function () {
    poll();
    setInterval(poll, POLL_MS);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) poll(); });
  });
})();
