const PLATFORM_MARKET_TYPES = {
  mt5: ['forex', 'cfd'],
  ctrader: ['forex', 'cfd', 'spot', 'futures'],
  tradingview: ['signals'],
  binance: ['spot', 'futures'],
  bybit: ['spot', 'futures'],
  okx: ['spot', 'futures'],
};

const PLATFORM_FIELD_MAP = {
  mt5: [
    { key: 'login', label: 'Usuario MT5', target: 'secrets', required: true },
    { key: 'password', label: 'Contraseña MT5', target: 'secrets', required: true },
    { key: 'server', label: 'Servidor', target: 'secrets', required: true },
  ],
  ctrader: [
    { key: 'client_id', label: 'Client ID', target: 'secrets', required: true },
    { key: 'client_secret', label: 'Client Secret', target: 'secrets', required: true },
    { key: 'access_token', label: 'Access Token', target: 'secrets', required: true },
    { key: 'account_id', label: 'Account ID', target: 'secrets', required: true },
  ],
  tradingview: [
    { key: 'passphrase', label: 'Passphrase webhook', target: 'config', required: true },
  ],
  binance: [
    { key: 'api_key', label: 'API Key', target: 'secrets', required: true },
    { key: 'secret_key', label: 'Secret Key', target: 'secrets', required: true },
  ],
  bybit: [
    { key: 'api_key', label: 'API Key', target: 'secrets', required: true },
    { key: 'secret_key', label: 'Secret Key', target: 'secrets', required: true },
  ],
  okx: [
    { key: 'api_key', label: 'API Key', target: 'secrets', required: true },
    { key: 'secret_key', label: 'Secret Key', target: 'secrets', required: true },
    { key: 'passphrase', label: 'Passphrase', target: 'secrets', required: true },
  ],
};

const COMMON_CONNECTOR_CONFIG_FIELDS = [
  { key: 'recv_window_ms', label: 'Recv window (ms)', target: 'config', type: 'number', platforms: ['binance', 'bybit', 'okx'], hint: 'Ventana de recepción para APIs firmadas.' },
  { key: 'request_timeout_ms', label: 'Request timeout (ms)', target: 'config', type: 'number', platforms: ['binance', 'bybit', 'okx'], hint: 'Timeout total por request al exchange.' },
  { key: 'futures_margin_mode', label: 'Margin mode', target: 'config', type: 'select', options: ['isolated', 'cross'], platforms: ['binance', 'bybit', 'okx'], futuresOnly: true, hint: 'Modo de margen para futures.' },
  { key: 'futures_position_mode', label: 'Position mode', target: 'config', type: 'select', options: ['oneway', 'hedge'], platforms: ['binance', 'bybit', 'okx'], futuresOnly: true, hint: 'One-way o hedge según tu operativa.' },
  { key: 'futures_leverage', label: 'Leverage fijo', target: 'config', type: 'number', platforms: ['binance', 'bybit', 'okx'], futuresOnly: true, hint: 'Opcional; si lo dejas vacío usa leverage_profile.' },
  { key: 'leverage_profile', label: 'Leverage profile', target: 'config', type: 'select', options: ['none', 'conservative', 'balanced', 'aggressive'], platforms: ['binance', 'bybit', 'okx'], futuresOnly: true, hint: 'Perfil de apalancamiento usado por la lógica runtime.' },
  { key: 'retry_attempts', label: 'Retry attempts', target: 'config', type: 'number', platforms: ['binance', 'bybit', 'okx'], hint: 'Número de reintentos para timeouts/rechazos recuperables.' },
  { key: 'retry_delay_ms', label: 'Retry delay (ms)', target: 'config', type: 'number', platforms: ['binance', 'bybit', 'okx'], hint: 'Espera entre reintentos; 0 = inmediato.' },
];

const STRATEGIES = [
  { slug: 'ema_rsi', label: 'EMA RSI (Spot)', market_types: ['spot'] },
  { slug: 'mean_reversion_zscore', label: 'Mean Reversion Z-Score (Spot)', market_types: ['spot'] },
  { slug: 'ema_rsi_adx_stack', label: 'EMA RSI ADX Stack (Spot/Futures)', market_types: ['spot', 'futures'] },
  { slug: 'volatility_compression_breakout', label: 'Volatility Compression Breakout (Spot/Futures)', market_types: ['spot', 'futures'] },
  { slug: 'momentum_breakout', label: 'Momentum Breakout (Futures)', market_types: ['futures'] },
  { slug: 'macd_trend_pullback', label: 'MACD Trend Pullback (Futures)', market_types: ['futures'] },
  { slug: 'adx_trend_follow', label: 'ADX Trend Follow (Futures)', market_types: ['futures'] },
  { slug: 'supertrend_volatility', label: 'Supertrend Volatility (Futures)', market_types: ['futures'] },
  { slug: 'kalman_trend_filter', label: 'Kalman Trend Filter (Futures)', market_types: ['futures'] },
  { slug: 'atr_channel_breakout', label: 'ATR Channel Breakout (Futures)', market_types: ['futures'] },
  { slug: 'volatility_breakout', label: 'Volatility Breakout (Futures)', market_types: ['futures'] },
];

const FIELD_ADVISORY_CONFIG = {
  connector: {
    platform: {
      title: 'Plataforma',
      recommend: 'Elige el exchange/plataforma exacto que vas a conectar para cargar solo los campos compatibles.',
    },
    market_type: {
      title: 'Mercado',
      recommend: 'Spot opera inventario real; Futures habilita derivados, apalancamiento y posiciones en corto.',
    },
    symbols: {
      title: 'Símbolos base',
      recommend: 'Usa pares líquidos y consistentes con el mercado elegido. Ejemplo: BTC/USDT, ETH/USDT.',
    },
  },
  run: {
    connector_id: {
      title: 'Conector',
      recommend: 'Selecciona un conector activo antes de ejecutar o automatizar una estrategia.',
    },
    symbols: {
      title: 'Símbolos',
      recommend: 'Prioriza símbolos líquidos, evita duplicados y mantén una cesta manejable para no dispersar capital.',
    },
    timeframe: {
      title: 'Timeframe',
      recommend: '15m y 1h suelen ser buenos marcos base. 1m/3m exigen más control y más ruido de mercado.',
    },
    strategy_slug: {
      title: 'Estrategia',
      recommend: 'Asegúrate de que la estrategia sea compatible con el mercado del conector para evitar setups incoherentes.',
    },
    risk_per_trade_percent: {
      title: 'Riesgo por trade',
      recommend: 'Para trading serio, normalmente conviene mantenerse entre 0.25% y 2% por operación.',
    },
    min_ml_probability_percent: {
      title: 'Probabilidad mínima ML',
      recommend: 'Entre 55% y 75% suele equilibrar frecuencia y filtro. Valores extremos pueden bloquear demasiadas entradas.',
    },
    take_profit_value: {
      title: 'Take profit',
      recommend: 'El take profit debería compensar el riesgo asumido y mantener una relación beneficio/riesgo sana.',
    },
    stop_loss_value: {
      title: 'Stop loss',
      recommend: 'Nunca dejes una posición sin stop loss. En porcentaje, mantenerlo ajustado ayuda a limitar drawdown.',
    },
    trailing_stop_value: {
      title: 'Trailing stop',
      recommend: 'Úsalo como protección dinámica, idealmente más ajustado que el take profit y coherente con la volatilidad.',
    },
    trade_amount_mode: {
      title: 'Modo de sizing',
      recommend: 'Define aquí el sizing real de la estrategia. Ya no se hereda desde el conector para evitar configuraciones cruzadas.',
    },
    amount_per_trade: {
      title: 'Monto por trade',
      recommend: 'Debe ser suficiente para superar los mínimos del exchange. Si una estrategia antigua no tiene valor, se aplicará el mínimo notional del símbolo.',
    },
    amount_percentage: {
      title: '% por trade',
      recommend: 'Para robustez, evita porcentajes excesivos. Un rango moderado reduce sobreexposición y concentración.',
    },
    use_live_if_available: {
      title: 'Modo live',
      recommend: 'Actívalo solo cuando el conector, el sizing y los límites de riesgo ya estén validados.',
    },
  },
};

const DASHBOARD_TAB_STORAGE_KEY = 'trading-saas.dashboard.active-tab';

const state = {
  me: null,
  summary: null,
  connectors: [],
  connectorBalances: {},
  botSessions: [],
  executionLogs: [],
  executionLogFilters: {
    query: '',
    status: '',
    connector: '',
    marketType: '',
    startDate: '',
    endDate: '',
  },
  executionLogsMeta: {
    total: 0,
    limit: 25,
    offset: 0,
    hasMore: false,
  },
  heartbeat: null,
  activity: null,
  editingConnectorId: null,
  pendingActions: {
    runStrategy: false,
    activateBot: false,
    saveConnector: false,
  },
};

const REPORT_STATE_LABELS = {
  operativa_normal: 'Operativa normal',
  volatilidad_excesiva: 'Volatilidad excesiva',
  drawdown_reciente: 'Drawdown reciente',
  overtrading: 'Overtrading',
  mercado_lateral_ruidoso: 'Mercado lateral / ruidoso',
  baja_calidad_de_senal: 'Baja calidad de señal',
  riesgo_global_alto: 'Riesgo global alto',
  problemas_tecnicos: 'Problemas técnicos',
  eventos_extremos_de_mercado: 'Eventos extremos de mercado',
};

async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function parseApiError(error) {
  const raw = String(error?.message || 'Error inesperado').trim();
  try {
    const payload = JSON.parse(raw);
    if (payload?.detail) return Array.isArray(payload.detail) ? payload.detail.map((d) => d.msg || JSON.stringify(d)).join(' | ') : String(payload.detail);
  } catch (_err) {}
  return raw || 'Error inesperado';
}

function setStatus(id, message, kind = 'ok') {
  const node = document.getElementById(id);
  if (!node) return;
  node.textContent = message || '';
  node.className = `status-msg ${message ? `status-${kind}` : ''}`.trim();
}

function formatDate(value) {
  if (!value) return '-';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  const two = (number) => String(number).padStart(2, '0');
  return `${two(d.getDate())}/${two(d.getMonth() + 1)}/${String(d.getFullYear()).slice(-2)}, ${two(d.getHours())}:${two(d.getMinutes())}`;
}

function prettyLabel(value, fallback = '-') {
  const raw = String(value ?? '').trim();
  if (!raw || ['undefined', 'null'].includes(raw.toLowerCase())) return fallback;
  return raw;
}

function prettyMarketType(value, connectorId = null) {
  const connector = state.connectors.find((item) => item.id === Number(connectorId));
  const raw = String(value ?? connector?.market_type ?? '').trim().toLowerCase();
  const normalized = raw === 'future' ? 'futures' : raw;
  const labels = { spot: 'Spot', futures: 'Futures', forex: 'Forex', cfd: 'CFD', signals: 'Signals' };
  return labels[normalized] || prettyLabel(value ?? connector?.market_type, 'Spot');
}

function prettyPlatform(value) {
  const raw = String(value || '').trim().toLowerCase();
  const labels = { binance: 'Binance', bybit: 'Bybit', okx: 'OKX', mt5: 'MT5', ctrader: 'cTrader', tradingview: 'TradingView' };
  return labels[raw] || prettyLabel(value, '-');
}

function displaySymbol(value) {
  const raw = String(value || '').trim().toUpperCase();
  if (!raw) return '-';
  return raw.replace('/USDT', '').replace('USDT', '').replace('/', '') || raw;
}

function formatBalanceSnapshot(connectorId) {
  const balance = state.connectorBalances?.[connectorId];
  if (!balance) return 'Balance cargando…';
  if (!balance.ok) return `Balance no disponible${balance.error ? ` · ${balance.error}` : ''}`;
  const asset = prettyLabel(balance.quote_asset, 'USDT');
  const available = Number(balance.available_balance || 0).toFixed(2);
  const total = Number(balance.total_balance || 0).toFixed(2);
  return `Disponible ${available} ${asset} · Total ${total} ${asset}`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function svgLineChart(items = [], { color = '#f0b90b', fill = 'rgba(240,185,11,.12)' } = {}) {
  const normalized = Array.isArray(items) ? items : [];
  if (!normalized.length) return '<div class="chart-empty">Sin datos suficientes todavía.</div>';
  const values = normalized.map((item) => Number(item?.value || 0));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = 100;
  const height = 36;
  const points = normalized.map((item, index) => {
    const x = normalized.length === 1 ? width / 2 : (index / (normalized.length - 1)) * width;
    const y = height - (((Number(item?.value || 0) - min) / range) * (height - 4)) - 2;
    return `${x},${y}`;
  });
  const areaPoints = [`0,${height}`, ...points, `${width},${height}`].join(' ');
  return `
    <svg viewBox="0 0 ${width} ${height}" class="activity-chart" preserveAspectRatio="none" aria-hidden="true">
      <polygon points="${areaPoints}" fill="${fill}"></polygon>
      <polyline points="${points.join(' ')}" fill="none" stroke="${color}" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"></polyline>
    </svg>
  `;
}

function activitySummaryCard(title, value, tone = 'neutral') {
  return `
    <article class="activity-mini-card tone-${escapeHtml(tone)}">
      <small>${escapeHtml(title)}</small>
      <strong>${escapeHtml(value)}</strong>
    </article>
  `;
}

function formatTradeAmountMode(mode) {
  const normalized = String(mode || 'fixed_usd').toLowerCase();
  const labels = {
    inherit: 'Monto fijo automático',
    fixed_usd: 'Monto fijo',
    balance_percent: '% balance',
  };
  return labels[normalized] || prettyLabel(mode, 'Monto fijo');
}

function formatSessionCapital(session) {
  const configuredMode = String(session.configured_trade_amount_mode || session.trade_amount_mode || 'fixed_usd').toLowerCase();
  if (configuredMode === 'fixed_usd') {
    return `${Number(session.configured_amount_per_trade || session.capital_per_operation || 0).toFixed(2)} ${session.capital_currency || 'USDT'}`;
  }
  if (configuredMode === 'balance_percent') {
    return `${Number(session.configured_amount_percentage || session.capital_per_operation || 0).toFixed(2)}%`;
  }
  return `${Number(session.capital_per_operation || 0).toFixed(2)} ${session.capital_currency || 'USDT'}`;
}

function connectorSizingSummary(connector = {}) {
  return 'Se define dentro de la estrategia';
}

function statusPillClass(kind) {
  const normalized = String(kind || '').toLowerCase();
  const errorMarkers = ['error', 'failed', 'danger', 'rejected', 'invalid'];
  if (errorMarkers.some(m => normalized.includes(m))) return 'pill-danger';
  if (['warning', 'skipped', 'paused'].some(m => normalized.includes(m))) return 'pill-warning';
  return 'pill-ok';
}

function formatDecisionReason(reason) {
  const normalized = String(reason || '').trim();
  if (!normalized || normalized.toLowerCase() === 'ok') return 'operativa_normal';
  return normalized.replace(/^circuit_breaker:\s*/i, '').replaceAll('_', ' ');
}

function buildLogDetails(item) {
  const notes = item.notes || {};
  const decision = notes.decision_summary || {};
  const strategyConfig = notes.strategy_config || {};
  const scanner = notes.scanner || {};
  
  const rawDetails = Array.isArray(decision.reason_details) && decision.reason_details.length
    ? decision.reason_details
    : [item.status_reason || item.status_reason_code || item.status];
    
  const reasonDetails = rawDetails.map(d => {
    if (!d) return null;
    if (typeof d === 'object') return d.message || d.code || JSON.stringify(d);
    return formatDecisionReason(d);
  }).filter(Boolean);

  const highlights = [];
  if (strategyConfig.configured_symbol_count) highlights.push(`La estrategia tiene ${strategyConfig.configured_symbol_count} símbolo(s) configurados.`);
  if (scanner.selected_count) highlights.push(`En esta corrida se evaluaron ${scanner.selected_count} símbolo(s).`);
  if (strategyConfig.symbol_min_notional) highlights.push(`Monto mínimo detectado para ${item.display_symbol || item.symbol}: ${Number(strategyConfig.symbol_min_notional).toFixed(2)} USDT.`);
  if (decision.decision) highlights.push(`Decisión del motor: ${decision.decision}.`);
  if (notes.execution_error) highlights.push(`Error reportado por el exchange: ${notes.execution_error}`);
  if ((notes.execution_raw || {}).message) highlights.push(`Respuesta del exchange: ${notes.execution_raw.message}`);
  if (!highlights.length) highlights.push('Sin explicación adicional reportada.');
  
  return { summary: reasonDetails[0] || 'operativa normal', reasonDetails, highlights, raw: notes };
}

function percentFromStoredValue(value) {
  const numeric = Number(value || 0);
  return numeric > 1 ? numeric : numeric * 100;
}

function setButtonsBusy(buttons, isBusy, busyLabel = 'Guardando...') {
  (Array.isArray(buttons) ? buttons : [buttons]).filter(Boolean).forEach((button) => {
    if (!button.dataset.defaultLabel) button.dataset.defaultLabel = button.textContent.trim();
    button.disabled = isBusy;
    button.classList.toggle('is-loading', isBusy);
    button.textContent = isBusy ? busyLabel : button.dataset.defaultLabel;
  });
}

function connectorFieldDefinitions(platform, marketType = null) {
  const normalizedMarket = String(marketType || document.getElementById('connector-market-type')?.value || 'spot').toLowerCase();
  return [
    ...(PLATFORM_FIELD_MAP[platform] || []),
    ...COMMON_CONNECTOR_CONFIG_FIELDS.filter((field) => {
      if (field.platforms && !field.platforms.includes(platform)) return false;
      if (field.futuresOnly && normalizedMarket !== 'futures') return false;
      return true;
    }),
  ];
}

function configEntriesForDisplay(config = {}) {
  const orderedKeys = [
    'recv_window_ms',
    'request_timeout_ms',
    'futures_margin_mode',
    'futures_position_mode',
    'futures_leverage',
    'leverage_profile',
    'retry_attempts',
    'retry_delay_ms',
  ];
  return orderedKeys
    .filter((key) => config[key] !== undefined && config[key] !== null && config[key] !== '')
    .map((key) => ({
      key,
      label: key.replaceAll('_', ' '),
      value: typeof config[key] === 'boolean' ? (config[key] ? 'Sí' : 'No') : String(config[key]),
    }));
}

function reportMarkup(items = []) {
  return items.map((item) => `
    <article class="quantum-report-item fade-in-up">
      <strong>${item.title}</strong>
      <small>${item.body}</small>
    </article>
  `).join('');
}

function getConnectorById(connectorId) {
  return state.connectors.find((item) => item.id === Number(connectorId)) || null;
}

function activateTab(tabName) {
  const buttons = Array.from(document.querySelectorAll('#dashboard-tabs .tab-btn'));
  const normalized = String(tabName || 'profile');
  const fallback = buttons.find((button) => button.dataset.tab === normalized) || buttons[0];
  if (!fallback) return;
  buttons.forEach((btn) => btn.classList.toggle('active', btn === fallback));
  document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.toggle('active', panel.id === `tab-${fallback.dataset.tab}`));
  try {
    window.localStorage?.setItem(DASHBOARD_TAB_STORAGE_KEY, fallback.dataset.tab);
  } catch (_error) {}
}

function initTabs() {
  const buttons = Array.from(document.querySelectorAll('#dashboard-tabs .tab-btn'));
  buttons.forEach((button) => {
    button.addEventListener('click', () => activateTab(button.dataset.tab));
  });
  let savedTab = 'profile';
  try {
    savedTab = window.localStorage?.getItem(DASHBOARD_TAB_STORAGE_KEY) || savedTab;
  } catch (_error) {}
  activateTab(savedTab);
}

function normalizeMarketType(value) {
  const raw = String(value || 'spot').trim().toLowerCase();
  return raw === 'future' ? 'futures' : raw;
}

function syncRunStrategyAvailability(hasOptions) {
  const select = document.getElementById('strategy-select');
  const runButton = document.getElementById('run-strategy-btn');
  const activateButton = document.getElementById('activate-bot-btn');
  if (select) select.disabled = !hasOptions;
  if (runButton) runButton.disabled = !hasOptions;
  if (activateButton) activateButton.disabled = !hasOptions;
}

function renderStrategyOptions(marketType = null) {
  const select = document.getElementById('strategy-select');
  if (!select) return;

  const oldValue = select.value;
  const connectorId = document.getElementById('run-connector-select')?.value;
  const connector = getConnectorById(connectorId);
  
  if (!connector && !marketType) {
    select.innerHTML = '';
    select.value = '';
    syncRunStrategyAvailability(false);
    return;
  }

  const normalizedMarketType = normalizeMarketType(marketType || connector?.market_type);
  const filtered = STRATEGIES.filter((s) => s.market_types.includes(normalizedMarketType));
  
  select.innerHTML = filtered.map((s) => `<option value="${s.slug}">${s.label}</option>`).join('');

  if (filtered.some((s) => s.slug === oldValue)) {
    select.value = oldValue;
  } else if (filtered.length > 0) {
    select.value = filtered[0].slug;
    if (oldValue) {
        setStatus('run-feedback', 'La estrategia seleccionada se reinició por compatibilidad con el conector.', 'warning');
    }
  } else {
    select.value = '';
  }
  syncRunStrategyAvailability(filtered.length > 0);
}

function renderConnectorFields() {
  const platform = document.getElementById('connector-platform')?.value || 'binance';
  const marketType = document.getElementById('connector-market-type');
  const fieldsWrap = document.getElementById('connector-friendly-fields');
  const previousMarketType = marketType?.value || 'spot';
  const isEditing = Boolean(state.editingConnectorId);
  if (marketType) {
    const options = PLATFORM_MARKET_TYPES[platform] || ['spot'];
    marketType.innerHTML = options.map((type) => `<option value="${type}">${prettyMarketType(type)}</option>`).join('');
    marketType.value = options.includes(previousMarketType) ? previousMarketType : options[0];
  }
  if (fieldsWrap) {
    const selectedMarketType = marketType?.value || 'spot';
    fieldsWrap.innerHTML = connectorFieldDefinitions(platform, selectedMarketType).map((field) => {
      const name = `field_${field.target}_${field.key}`;
      const inputType = field.type || 'text';
      const isSecretField = field.target === 'secrets';
      const isRequired = Boolean(field.required && !(isEditing && isSecretField));
      if (inputType === 'select') {
        return `
          <label>${field.label}
            <select name="${name}" ${isRequired ? 'required' : ''}>
              <option value="">Auto / sin definir</option>
              ${(field.options || []).map((option) => `<option value="${option}">${prettyLabel(option, option)}</option>`).join('')}
            </select>
            ${field.hint ? `<small class="hint">${field.hint}</small>` : ''}
          </label>
        `;
      }
      if (inputType === 'checkbox') {
        return `
          <label class="checkbox">${field.label}
            <input type="checkbox" name="${name}" ${isRequired ? 'required' : ''}>
            <span class="hint">${field.hint || ''}</span>
          </label>
        `;
      }
      return `
        <label>${field.label}
          <input name="${name}" type="${inputType}" ${isRequired ? 'required' : ''} ${inputType === 'number' ? 'step="0.01"' : ''}>
          ${field.hint ? `<small class="hint">${field.hint}</small>` : ''}
        </label>
      `;
    }).join('');
  }
  const form = document.querySelector('#connector-form');
  if (form) delete form.dataset.advisoriesBound;
  bindFieldAdvisories('#connector-form', 'connector');
}

function readConnectorFriendlyFields(formEl, platform) {
  const fd = new FormData(formEl);
  const config = {};
  const secrets = {};
  const marketType = String(fd.get('market_type') || 'spot');
  connectorFieldDefinitions(platform, marketType).forEach((field) => {
    const rawValue = field.type === 'checkbox' ? fd.get(`field_${field.target}_${field.key}`) === 'on' : fd.get(`field_${field.target}_${field.key}`);
    if (field.type === 'checkbox') {
      if (field.target === 'secrets') secrets[field.key] = Boolean(rawValue);
      else config[field.key] = Boolean(rawValue);
      return;
    }
    const value = String(rawValue || '').trim();
    if (!value) return;
    const normalizedValue = field.type === 'number' ? Number(value) : value;
    if (field.target === 'secrets') secrets[field.key] = normalizedValue;
    else config[field.key] = normalizedValue;
  });
  return { config, secrets };
}

function resetConnectorForm() {
  const form = document.getElementById('connector-form');
  if (!form) return;
  state.editingConnectorId = null;
  form.reset();
  document.getElementById('connector-edit-id').value = '';
  document.getElementById('connector-form-title').textContent = 'Nuevo conector';
  document.getElementById('connector-form-mode-label').textContent = 'Creación';
  document.getElementById('connector-submit-btn').textContent = 'Guardar conector';
  document.getElementById('cancel-connector-edit-btn').classList.add('hidden');
  renderConnectorFields();
  bindFieldAdvisories('#connector-form', 'connector');
}

function populateConnectorForm(connectorId) {
  const connector = getConnectorById(connectorId);
  const form = document.getElementById('connector-form');
  if (!connector || !form) return;
  state.editingConnectorId = connector.id;
  document.getElementById('connector-edit-id').value = String(connector.id);
  form.querySelector('#connector-platform').value = connector.platform;
  renderConnectorFields();
  form.querySelector('#connector-market-type').value = connector.market_type || 'spot';
  renderConnectorFields();
  form.querySelector('#connector-label').value = connector.label || '';
  form.querySelector('#connector-mode').value = connector.mode || 'live';
  form.querySelector('#symbols-input').value = (connector.symbols || []).join(', ');
  connectorFieldDefinitions(connector.platform, connector.market_type).forEach((field) => {
    const input = form.querySelector(`[name="field_${field.target}_${field.key}"]`);
    if (!input) return;
    const value = field.target === 'secrets' ? '' : connector.config?.[field.key];
    if (field.type === 'checkbox') input.checked = Boolean(value);
    else input.value = value ?? '';
    if (field.target === 'secrets') input.placeholder = 'Deja vacío para conservar el valor actual';
  });
  document.getElementById('connector-form-title').textContent = `Editar conector · ${connector.label}`;
  document.getElementById('connector-form-mode-label').textContent = 'Edición';
  document.getElementById('connector-submit-btn').textContent = 'Guardar cambios';
  document.getElementById('cancel-connector-edit-btn').classList.remove('hidden');
  setStatus('connector-feedback', `Editando ${connector.label}. Puedes actualizar configuración, símbolos o credenciales.`, 'ok');
  form.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderProfile() {
  const user = state.me;
  if (!user) return;
  document.getElementById('profile-name').value = user.name || '';
  document.getElementById('profile-email').value = user.email || '';
  document.getElementById('profile-phone').value = user.phone || '';
  document.getElementById('profile-alert-language').value = user.alert_language || 'es';
  document.getElementById('profile-telegram-enabled').checked = Boolean(user.telegram_alerts_enabled);
  document.getElementById('profile-telegram-bot-key').value = user.telegram_bot_key || '';
  document.getElementById('profile-telegram-chat-id').value = user.telegram_chat_id || '';
  document.getElementById('profile-title').textContent = user.is_admin ? 'Cuenta administrativa' : 'Perfil de usuario';
  document.getElementById('user-config-state').textContent = `Perfil · ${user.name || user.email}`;
  document.getElementById('user-config-report').innerHTML = reportMarkup([
    { title: 'Alertas', body: user.telegram_alerts_enabled ? `Telegram activo · idioma ${String(user.alert_language || 'es').toUpperCase()}` : 'Telegram inactivo' },
    { title: 'Sizing', body: 'La asignación de capital se define por estrategia o por sesión automática. El conector ya no guarda sizing propio.' },
    { title: 'Canal admin', body: user.admin_alerts_enabled ? 'Canal administrativo de contingencias disponible' : 'Canal administrativo no configurado' },
    { title: 'Cobertura Telegram', body: 'Conexión, errores, mercado conectado, velas revisadas y tendencia de la corrida manual se notifican en el canal configurado.' },
  ]);
}

function renderConnectors() {
  const list = document.getElementById('connector-list');
  const panel = document.getElementById('connector-health-panel');
  const runSelect = document.getElementById('run-connector-select');
  if (runSelect) {
    const oldValue = runSelect.value;
    runSelect.innerHTML = state.connectors.filter((c) => c.is_enabled).map((c) => `<option value="${c.id}">${c.label} · ${prettyPlatform(c.platform)} · ${prettyMarketType(c.market_type, c.id)}</option>`).join('');
    if (oldValue && Array.from(runSelect.options).some(o => o.value === oldValue)) {
      runSelect.value = oldValue;
    }
    runSelect.dispatchEvent(new Event('change'));
  }
  if (panel) {
    panel.innerHTML = state.connectors.length ? reportMarkup(state.connectors.map((c) => ({
      title: `${c.label} · ${prettyPlatform(c.platform)}`,
      body: `${c.mode} · ${prettyMarketType(c.market_type, c.id)} · ${c.is_enabled ? 'activo' : 'inactivo'} · sizing ${connectorSizingSummary(c)} · ${(c.symbols || []).length} símbolos`,
    }))) : reportMarkup([{ title: 'Sin conectores', body: 'Crea al menos un conector para operar o automatizar.' }]);
  }
  if (!list) return;
  if (!state.connectors.length) {
    list.innerHTML = '<small class="hint">No hay conectores configurados todavía.</small>';
    return;
  }
  list.innerHTML = state.connectors.map((connector) => `
    <article class="connector-item fade-in-up ${state.editingConnectorId === connector.id ? 'is-editing' : ''}">
      <div class="row-between">
        <div>
          <strong>${connector.label}</strong>
          <div class="connector-meta">
            <span>${prettyPlatform(connector.platform)}</span>
            <span>${connector.mode}</span>
            <span>${prettyMarketType(connector.market_type, connector.id)}</span>
            <span>${(connector.symbols || []).length} símbolos</span>
          </div>
        </div>
        <span class="pill tiny ${connector.is_enabled ? 'pill-on' : 'pill-off'}">${connector.is_enabled ? 'Activo' : 'Inactivo'}</span>
      </div>
      <small class="hint">Símbolos: ${(connector.symbols || []).join(', ') || 'Sin símbolos configurados'}.</small>
      <small class="hint">Sizing: ${connectorSizingSummary(connector)}.</small>
      <small class="hint">Balance: ${formatBalanceSnapshot(connector.id)}.</small>
      <div class="chip-wrap">
        ${configEntriesForDisplay(connector.config || {}).map((entry) => `<span class="chip chip-static"><strong>${entry.label}:</strong> ${entry.value}</span>`).join('') || '<span class="chip chip-static">Sin parámetros visibles adicionales</span>'}
      </div>
      <div class="row-wrap" style="margin-top:12px;">
        <button class="btn btn-sm" type="button" data-action="edit" data-id="${connector.id}">Editar</button>
        <button class="btn btn-sm" type="button" data-action="test" data-id="${connector.id}">Test</button>
        <button class="btn btn-sm" type="button" data-action="toggle" data-id="${connector.id}" data-enabled="${connector.is_enabled}">${connector.is_enabled ? 'Desactivar' : 'Activar'}</button>
        <button class="btn btn-sm" type="button" data-action="delete" data-id="${connector.id}">Eliminar</button>
      </div>
    </article>
  `).join('');

  list.querySelectorAll('button[data-action]').forEach((button) => {
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.id);
      const action = button.dataset.action;
      try {
        if (action === 'edit') {
          populateConnectorForm(id);
        } else if (action === 'test') {
          const out = await api(`/api/connectors/${id}/test`, { method: 'POST' });
          setStatus('connector-feedback', out.message || 'Conector validado.', 'ok');
        } else if (action === 'toggle') {
          await api(`/api/connectors/${id}`, { method: 'PUT', body: JSON.stringify({ is_enabled: button.dataset.enabled !== 'true' }) });
          await refreshDashboard();
        } else if (action === 'delete') {
          await api(`/api/connectors/${id}`, { method: 'DELETE' });
          await refreshDashboard();
        }
      } catch (error) {
        setStatus('connector-feedback', parseApiError(error), 'error');
      }
    });
  });
}

function renderBotSessions() {
  const panel = document.getElementById('bot-sessions-panel');
  if (!panel) return;
  if (!state.botSessions.length) {
    panel.innerHTML = '<small class="hint">No hay bots activos todavía.</small>';
    return;
  }
  panel.innerHTML = state.botSessions.map((session) => `
    <article class="connector-item fade-in-up bot-session-card ${session.is_active ? 'is-active' : 'is-paused'}">
      <div class="row-between">
        <div>
          <strong>${prettyLabel(session.display_name || session.session_name || session.strategy_slug, 'strategy')}</strong>
          <div class="connector-meta">
            <span>${prettyLabel(session.session_name, 'Sin alias manual')}</span>
            <span>${prettyLabel(session.connector_label, 'Cuenta')}</span>
            <span>${prettyPlatform(session.platform)}</span>
            <span>${prettyMarketType(session.market_type, session.connector_id)}</span>
          </div>
        </div>
        <span class="pill tiny ${session.is_active ? 'pill-on' : 'pill-off'}">${session.is_active ? 'Activo' : 'Pausado'}</span>
      </div>
      <div class="bot-session-card-grid">
        <div class="bot-session-stat">
          <small>Timeframe</small>
          <strong>${prettyLabel(session.timeframe, '5m')}</strong>
        </div>
        <div class="bot-session-stat">
          <small>Riesgo</small>
          <strong>${percentFromStoredValue(session.risk_per_trade).toFixed(2)}%</strong>
        </div>
        <div class="bot-session-stat">
          <small>ML mínima</small>
          <strong>${percentFromStoredValue(session.min_ml_probability).toFixed(2)}%</strong>
        </div>
        <div class="bot-session-stat">
          <small>Modo sizing</small>
          <strong>${formatTradeAmountMode(session.configured_trade_amount_mode || 'fixed_usd')}</strong>
        </div>
        <div class="bot-session-stat">
          <small>Auto scan</small>
          <strong>${session.symbol_source_mode === 'dynamic' ? `Sí · Top ${Number(session.dynamic_symbol_limit || 10)}` : 'Manual'}</strong>
        </div>
        <div class="bot-session-stat bot-session-stat-wide">
          <small>Capital</small>
          <strong>${formatSessionCapital(session)}</strong>
        </div>
        <div class="bot-session-stat bot-session-stat-wide">
          <small>Símbolos</small>
          <strong>${(session.symbols || []).join(', ') || 'Sin símbolos'}</strong>
        </div>
      </div>
      <small class="hint">Próxima corrida: ${formatDate(session.next_run_at)} · Último estado: ${session.last_status || '-'}${session.last_error ? ` · ${session.last_error}` : ''}</small>
      <div class="row-wrap bot-session-actions">
        <button class="btn btn-sm" type="button" data-bot-action="edit" data-id="${session.id}">Editar</button>
        <button class="btn btn-sm" type="button" data-bot-action="copy" data-id="${session.id}">Duplicar</button>
        <button class="btn btn-sm" type="button" data-bot-action="delete" data-id="${session.id}">Eliminar</button>
      </div>
      <form class="bot-session-form form-grid hidden" data-session-id="${session.id}" style="margin-top:12px;">
        <label class="compact-field compact-field-wide">Nombre estrategia / sesión
          <input name="session_name" value="${session.session_name ?? ''}" placeholder="Momentum Binance principal">
        </label>
        <label class="compact-field">Estrategia
          <select name="strategy_slug">${STRATEGIES.filter(s => s.market_types.includes(normalizeMarketType(session.market_type))).map((s) => `<option value="${s.slug}" ${s.slug === session.strategy_slug ? 'selected' : ''}>${s.label}</option>`).join('')}</select>
        </label>
        <label class="compact-field">Timeframe<input name="timeframe" value="${session.timeframe || '15m'}"></label>
        <label class="compact-field compact-field-wide">Símbolos<input name="symbols" value="${(session.symbols || []).join(', ')}"></label>
        <label class="compact-field">Origen símbolos
          <select name="symbol_source_mode">
            <option value="manual" ${session.symbol_source_mode !== 'dynamic' ? 'selected' : ''}>Lista manual</option>
            <option value="dynamic" ${session.symbol_source_mode === 'dynamic' ? 'selected' : ''}>Auto scan</option>
          </select>
        </label>
        <label class="compact-field ${session.symbol_source_mode === 'dynamic' ? '' : 'hidden'}" data-session-dynamic-field="limit">Máx. símbolos auto scan
          <input name="dynamic_symbol_limit" type="number" min="1" max="50" step="1" value="${Number(session.dynamic_symbol_limit || 10)}">
        </label>
        <label class="compact-field">Riesgo por trade (%)<input name="risk_per_trade" type="number" min="0.1" max="100" step="0.1" value="${percentFromStoredValue(session.risk_per_trade)}"></label>
        <label class="compact-field">Prob. mínima ML (%)<input name="min_ml_probability" type="number" min="0" max="100" step="1" value="${percentFromStoredValue(session.min_ml_probability)}"></label>
        <label class="compact-field">Modo sizing
          <select name="trade_amount_mode">
            <option value="fixed_usd" ${(session.configured_trade_amount_mode || 'fixed_usd') === 'fixed_usd' ? 'selected' : ''}>Monto fijo</option>
            <option value="balance_percent" ${session.configured_trade_amount_mode === 'balance_percent' ? 'selected' : ''}>% balance</option>
          </select>
        </label>
        <label class="compact-field sizing-value-field ${(session.configured_trade_amount_mode || 'fixed_usd') === 'fixed_usd' ? '' : 'hidden'}" data-mode-field="fixed_usd">Monto por trade
          <input name="amount_per_trade" type="number" min="0.01" step="0.01" value="${session.configured_amount_per_trade ?? ''}">
        </label>
        <label class="compact-field sizing-value-field ${session.configured_trade_amount_mode === 'balance_percent' ? '' : 'hidden'}" data-mode-field="balance_percent">% por trade
          <input name="amount_percentage" type="number" min="0.1" max="100" step="0.1" value="${session.configured_amount_percentage ?? ''}">
        </label>
        <label class="compact-field">Ejecución
          <input value="Live" disabled>
        </label>
        <label class="compact-field">Estado
          <select name="is_active">
            <option value="true" ${session.is_active ? 'selected' : ''}>Activo</option>
            <option value="false" ${!session.is_active ? 'selected' : ''}>Pausado</option>
          </select>
        </label>
        <div class="row-wrap">
          <button class="btn btn-sm primary" type="submit">Guardar sesión</button>
          <button class="btn btn-sm" type="button" data-bot-action="cancel-edit" data-id="${session.id}">Cancelar</button>
        </div>
      </form>
    </article>
  `).join('');

  panel.querySelectorAll('.bot-session-form').forEach((form) => {
    const modeSelect = form.querySelector('[name="trade_amount_mode"]');
    const sourceModeSelect = form.querySelector('[name="symbol_source_mode"]');
    const syncSizingFields = () => {
      const currentMode = String(modeSelect?.value || 'fixed_usd');
      form.querySelectorAll('.sizing-value-field').forEach((field) => {
        const active = field.dataset.modeField === currentMode;
        field.classList.toggle('hidden', !active);
        const input = field.querySelector('input');
        if (input) {
          input.disabled = !active;
          if (!active) input.value = '';
        }
      });
    };
    modeSelect?.addEventListener('change', syncSizingFields);
    syncSizingFields();
    const syncSymbolSourceFields = () => {
      const dynamic = String(sourceModeSelect?.value || 'manual') === 'dynamic';
      form.querySelectorAll('[data-session-dynamic-field]').forEach((field) => {
        field.classList.toggle('hidden', !dynamic);
        const input = field.querySelector('input');
        if (input) input.disabled = !dynamic;
      });
    };
    sourceModeSelect?.addEventListener('change', syncSymbolSourceFields);
    syncSymbolSourceFields();

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const fd = new FormData(form);
      const id = Number(form.dataset.sessionId);
      const submitButton = form.querySelector('button[type="submit"]');
      try {
        setButtonsBusy(submitButton, true, 'Guardando...');
        await api(`/api/bot-sessions/${id}`, {
          method: 'PUT',
          body: JSON.stringify({
            session_name: String(fd.get('session_name') || '').trim() || null,
            strategy_slug: fd.get('strategy_slug'),
            timeframe: fd.get('timeframe'),
            symbols: String(fd.get('symbols') || '').split(',').map((item) => item.trim()).filter(Boolean),
            symbol_source_mode: fd.get('symbol_source_mode'),
            dynamic_symbol_limit: fd.get('symbol_source_mode') === 'dynamic' ? Number(fd.get('dynamic_symbol_limit') || 10) : null,
            risk_per_trade: Number(fd.get('risk_per_trade')),
            min_ml_probability: Number(fd.get('min_ml_probability')),
            trade_amount_mode: fd.get('trade_amount_mode'),
            amount_per_trade: fd.get('trade_amount_mode') === 'fixed_usd' ? Number(fd.get('amount_per_trade')) : null,
            amount_percentage: fd.get('trade_amount_mode') === 'balance_percent' ? Number(fd.get('amount_percentage')) : null,
            use_live_if_available: true,
            is_active: fd.get('is_active') === 'true',
          }),
        });
        setStatus('bot-session-feedback', 'Sesión automática actualizada.', 'ok');
        await refreshDashboard();
      } catch (error) {
        setStatus('bot-session-feedback', parseApiError(error), 'error');
      } finally {
        setButtonsBusy(submitButton, false);
      }
    });
  });

  panel.querySelectorAll('button[data-bot-action]').forEach((button) => {
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.id);
      const card = button.closest('.bot-session-card');
      const form = card?.querySelector('.bot-session-form');
      try {
        if (button.dataset.botAction === 'edit') {
          form?.classList.remove('hidden');
          button.classList.add('hidden');
          return;
        }
        if (button.dataset.botAction === 'cancel-edit') {
          form?.classList.add('hidden');
          card?.querySelector('[data-bot-action="edit"]')?.classList.remove('hidden');
          return;
        }
        setButtonsBusy(button, true, button.dataset.botAction === 'copy' ? 'Duplicando...' : 'Eliminando...');
        if (button.dataset.botAction === 'copy') {
          await api(`/api/bot-sessions/${id}/copy`, { method: 'POST', body: JSON.stringify({}) });
        } else {
          await api(`/api/bot-sessions/${id}`, { method: 'DELETE' });
        }
        await refreshDashboard();
      } catch (error) {
        setStatus('bot-session-feedback', parseApiError(error), 'error');
      } finally {
        if (!['edit', 'cancel-edit'].includes(button.dataset.botAction || '')) setButtonsBusy(button, false);
      }
    });
  });
}

function executionLogFilterOptions(key) {
  if (key === 'status') {
    return [
      { value: 'ok', label: 'Operativa normal' },
      { value: 'error', label: 'Error de ejecución' },
      { value: 'skipped', label: 'Omitido / Filtros' },
      { value: 'rejected', label: 'Rechazado' },
      { value: 'warning', label: 'Aviso' },
    ];
  }
  if (key === 'connector') {
    return (state.connectors || [])
      .filter((item) => item?.id)
      .map((item) => ({ value: String(item.id), label: prettyLabel(item.label, `Conector ${item.id}`) }))
      .sort((a, b) => a.label.localeCompare(b.label, 'es', { sensitivity: 'base' }));
  }
  if (key === 'marketType') {
    const values = Array.from(new Set((state.connectors || []).map((item) => normalizeMarketType(item.market_type)).filter(Boolean)));
    return values.sort((a, b) => a.localeCompare(b, 'es', { sensitivity: 'base' }));
  }
  return [];
}

function buildExecutionLogsQuery() {
  const filters = state.executionLogFilters || {};
  const meta = state.executionLogsMeta || {};
  const params = new URLSearchParams();
  params.set('limit', String(meta.limit || 25));
  params.set('offset', String(meta.offset || 0));
  if (filters.query) params.set('q', String(filters.query).trim());
  if (filters.status) params.set('status', String(filters.status).trim());
  if (filters.connector) params.set('connector', String(filters.connector).trim());
  if (filters.marketType) params.set('market_type', String(filters.marketType).trim());
  if (filters.startDate) params.set('start_date', String(filters.startDate).trim());
  if (filters.endDate) params.set('end_date', String(filters.endDate).trim());
  return params.toString();
}

async function refreshExecutionLogs({ resetOffset = false } = {}) {
  if (resetOffset) {
    state.executionLogsMeta = { ...(state.executionLogsMeta || {}), offset: 0 };
  }
  const payload = await api(`/api/execution-logs?${buildExecutionLogsQuery()}`);
  state.executionLogs = Array.isArray(payload?.items) ? payload.items : [];
  state.executionLogsMeta = {
    total: Number(payload?.total || 0),
    limit: Number(payload?.limit || state.executionLogsMeta?.limit || 25),
    offset: Number(payload?.offset || 0),
    hasMore: Boolean(payload?.has_more),
  };
}

function renderExecutionLogFilterBar() {
  const board = document.getElementById('execution-logs-board');
  if (!board) return null;
  let bar = document.getElementById('execution-log-filters');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'execution-log-filters';
    bar.className = 'row-wrap';
    bar.style.marginTop = '12px';
    bar.style.marginBottom = '8px';
    bar.innerHTML = `
      <input id="execution-log-filter-query" type="search" placeholder="Buscar símbolo, estado o razón" style="min-width:240px; border-radius:6px; border:1px solid rgba(255,255,255,0.1); padding:6px 10px; background:rgba(0,0,0,0.2); color:#fff; font-size:13px;">
      <select id="execution-log-filter-status" style="border-radius:6px; border:1px solid rgba(255,255,255,0.1); padding:6px 10px; background:rgba(0,0,0,0.2); color:#fff; font-size:13px;"><option value="">Estado</option></select>
      <button class="btn btn-sm" type="button" id="execution-log-filter-clear">Limpiar</button>
    `;
    board.parentNode?.insertBefore(bar, board);
  }
  if (bar.dataset.bound !== 'true') {
    let debounceHandle = null;
    const syncFiltersFromDom = (inputType) => {
      state.executionLogFilters = {
        query: document.getElementById('execution-log-filter-query')?.value || '',
        status: document.getElementById('execution-log-filter-status')?.value || '',
        connector: document.getElementById('execution-log-filter-connector')?.value || '',
        marketType: document.getElementById('execution-log-filter-market')?.value || '',
        startDate: document.getElementById('execution-log-filter-start-date')?.value || '',
        endDate: document.getElementById('execution-log-filter-end-date')?.value || '',
      };
      window.clearTimeout(debounceHandle);
      const runFetch = () => refreshExecutionLogs({ resetOffset: true }).then(() => renderExecutionLogs()).catch((error) => {
        setStatus('run-feedback', `No se pudieron filtrar los logs: ${parseApiError(error)}`, 'error');
      });
      if (inputType === 'input') {
        debounceHandle = window.setTimeout(runFetch, 250);
      } else {
        runFetch();
      }
    };
    bar.querySelectorAll('input, select').forEach((input) => {
      const eventName = input.tagName === 'INPUT' && input.type === 'search' ? 'input' : 'change';
      input.addEventListener(eventName, () => syncFiltersFromDom(eventName));
    });
    document.getElementById('execution-log-filter-clear')?.addEventListener('click', () => {
      state.executionLogFilters = { query: '', status: '', connector: '', marketType: '', startDate: '', endDate: '' };
      refreshExecutionLogs({ resetOffset: true }).then(() => renderExecutionLogs()).catch((error) => {
        setStatus('run-feedback', `No se pudieron reiniciar los filtros: ${parseApiError(error)}`, 'error');
      });
    });
    bar.dataset.bound = 'true';
  }

  const filters = state.executionLogFilters || {};
  const queryInput = document.getElementById('execution-log-filter-query');
  const statusSelect = document.getElementById('execution-log-filter-status');
  const connectorSelect = document.getElementById('execution-log-filter-connector');
  const marketSelect = document.getElementById('execution-log-filter-market');
  const startDateInput = document.getElementById('execution-log-filter-start-date');
  const endDateInput = document.getElementById('execution-log-filter-end-date');
  if (queryInput && queryInput.value !== filters.query) queryInput.value = filters.query || '';
  if (startDateInput && startDateInput.value !== (filters.startDate || '')) startDateInput.value = filters.startDate || '';
  if (endDateInput && endDateInput.value !== (filters.endDate || '')) endDateInput.value = filters.endDate || '';

  const applyOptions = (select, options, value, defaultLabel) => {
    if (!select) return;
    const currentValue = value || '';
    const normalizedOptions = options.map((option) => (typeof option === 'string' ? { value: option, label: option } : option));
    select.innerHTML = [`<option value="">${defaultLabel}</option>`, ...normalizedOptions.map((option) => `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`)].join('');
    select.value = normalizedOptions.some((option) => option.value === currentValue) ? currentValue : '';
  };

  applyOptions(statusSelect, executionLogFilterOptions('status'), filters.status, 'Estado');
  applyOptions(connectorSelect, executionLogFilterOptions('connector'), filters.connector, 'Conector');
  applyOptions(
    marketSelect,
    executionLogFilterOptions('marketType').map((value) => ({ value, label: prettyMarketType(value) })),
    filters.marketType,
    'Mercado',
  );
  state.executionLogFilters = {
    query: queryInput?.value || '',
    status: statusSelect?.value || '',
    connector: connectorSelect?.value || '',
    marketType: marketSelect?.value || '',
    startDate: startDateInput?.value || '',
    endDate: endDateInput?.value || '',
  };

  return bar;
}

function renderExecutionLogs() {
  const board = document.getElementById('execution-logs-board');
  if (!board) return;
  renderExecutionLogFilterBar();
  const logs = Array.isArray(state.executionLogs) ? state.executionLogs : [];
  const metaState = state.executionLogsMeta || {};
  const total = Number(metaState.total || 0);
  const offset = Number(metaState.offset || 0);
  const limit = Number(metaState.limit || 25);
  const filters = state.executionLogFilters || {};
  const hasActiveFilters = Boolean(filters.query || filters.status || filters.connector || filters.marketType || filters.startDate || filters.endDate);

  if (!logs.length && total === 0 && !hasActiveFilters) {
    board.innerHTML = '<div class="log-table-compact"><small class="hint" style="padding: 12px; display: block;">Sin logs todavía.</small></div>';
    const meta = document.getElementById('execution-logs-refresh-meta');
    if (meta) meta.textContent = `Mostrando 0 logs. Última actualización: ${new Date().toLocaleTimeString()}`;
    return;
  }
  if (!logs.length) {
    board.innerHTML = '<div class="log-table-compact"><small class="hint" style="padding: 12px; display: block;">Sin resultados.</small></div>';
    const meta = document.getElementById('execution-logs-refresh-meta');
    if (meta) meta.textContent = `Mostrando 0 de ${total} logs. Última actualización: ${new Date().toLocaleTimeString()}`;
    return;
  }

  const header = `
    <div class="log-header-compact">
      <div class="log-col-date">Fecha / Hora</div>
      <div class="log-col-connector">Conector</div>
      <div class="log-col-market">Mercado</div>
      <div class="log-col-symbol">Símbolo</div>
      <div class="log-col-action">Acción</div>
      <div class="log-col-status">Estado / Razón</div>
    </div>
  `;

  const rows = logs.map((item) => {
    const detail = buildLogDetails(item);
    const detailId = `log-detail-${item.id}`;
    const symbol = displaySymbol(item.display_symbol || item.symbol);
    const connector = prettyLabel(item.connector_label, `ID:${item.connector_id}`);
    const market = prettyMarketType(item.market_type, item.connector_id);
    const platform = prettyPlatform(item.platform);
    const states = Array.isArray(item.operational_states) && item.operational_states.length ? item.operational_states : ['operativa_normal'];

    return `
      <div class="log-row-compact" data-log-toggle="${detailId}">
        <div class="log-col-date">${formatDate(item.created_at)}</div>
        <div class="log-col-connector" title="${escapeHtml(platform)}">${escapeHtml(connector)}</div>
        <div class="log-col-market">${escapeHtml(market)}</div>
        <div class="log-col-symbol"><strong>${escapeHtml(symbol)}</strong></div>
        <div class="log-col-action">${escapeHtml(item.signal || '-')}</div>
        <div class="log-col-status">
          <span class="pill tiny ${statusPillClass(item.status)}">${escapeHtml(item.status || '-')}</span>
          <small style="display:block; margin-top:6px; font-size:11px; color:var(--muted); line-height:1.2; font-weight:500;">${escapeHtml(detail.summary || '')}</small>
        </div>
      </div>
      <section class="log-details-expanded hidden" id="${detailId}">
        <div class="chip-wrap" style="margin-top:0; margin-bottom:12px;">
          ${states.map((stateCode) => `<span class="chip chip-static tiny">${escapeHtml(REPORT_STATE_LABELS[stateCode] || prettyLabel(stateCode, stateCode))}</span>`).join('')}
        </div>
        <div class="log-detail-grid">
          <div>
            <strong>Razones</strong>
            <ul class="log-reason-list">
              ${detail.reasonDetails.map((reason) => `<li>${escapeHtml(reason)}</li>`).join('')}
            </ul>
          </div>
          <div>
            <strong>Highlights</strong>
            <ul class="log-reason-list">
              ${detail.highlights.map((row) => `<li>${escapeHtml(row)}</li>`).join('')}
            </ul>
          </div>
        </div>
        <div class="log-technical-block" style="margin-top:10px;">
          <strong>Detalle técnico</strong>
          <pre>${escapeHtml(JSON.stringify(detail.raw, null, 2))}</pre>
        </div>
      </section>
    `;
  }).join('');

  const pagination = `
    <div class="row-wrap" style="justify-content:space-between; align-items:center; margin-top:10px;">
      <small class="hint">Página ${Math.floor(offset / limit) + 1} · ${Math.min(offset + 1, total)}-${Math.min(offset + logs.length, total)} de ${total}</small>
      <div class="row-wrap">
        <button class="btn btn-sm" type="button" id="execution-logs-prev-page" ${offset <= 0 ? 'disabled' : ''}>Anterior</button>
        <button class="btn btn-sm" type="button" id="execution-logs-next-page" ${metaState.hasMore ? '' : 'disabled'}>Siguiente</button>
      </div>
    </div>
  `;

  board.innerHTML = `<div class="log-table-compact">${header}${rows}</div>${pagination}`;

  board.querySelectorAll('.log-row-compact').forEach((row) => {
    row.addEventListener('click', () => {
      const detailId = row.dataset.logToggle;
      const detail = document.getElementById(detailId);
      row.classList.toggle('is-expanded');
      detail?.classList.toggle('hidden');
    });
  });

  document.getElementById('execution-logs-prev-page')?.addEventListener('click', async () => {
    state.executionLogsMeta = { ...metaState, offset: Math.max(offset - limit, 0) };
    await refreshExecutionLogs();
    renderExecutionLogs();
  });
  document.getElementById('execution-logs-next-page')?.addEventListener('click', async () => {
    state.executionLogsMeta = { ...metaState, offset: offset + limit };
    await refreshExecutionLogs();
    renderExecutionLogs();
  });

  const meta = document.getElementById('execution-logs-refresh-meta');
  if (meta) meta.textContent = `Mostrando ${logs.length} de ${total} logs. Última actualización: ${new Date().toLocaleTimeString()}`;
}
function renderActivity() {
  const activity = state.activity || {};
  const summary = activity.summary || {};
  const equityWrap = document.getElementById('activity-equity-chart');
  const monthlyWrap = document.getElementById('activity-monthly-chart');
  const metricsWrap = document.getElementById('activity-performance-cards');
  if (equityWrap) equityWrap.innerHTML = svgLineChart(activity.equity_curve || [], { color: '#f0b90b', fill: 'rgba(240,185,11,.12)' });
  if (monthlyWrap) monthlyWrap.innerHTML = svgLineChart(activity.monthly_returns || [], { color: '#38bdf8', fill: 'rgba(56,189,248,.12)' });
  if (metricsWrap) {
    metricsWrap.innerHTML = [
      activitySummaryCard('Sharpe', Number(summary.sharpe_ratio || 0).toFixed(2), 'accent'),
      activitySummaryCard('Max DD', `${Number(summary.max_drawdown || 0).toFixed(2)}`, 'danger'),
      activitySummaryCard('Profit factor', Number(summary.profit_factor || 0).toFixed(2), 'ok'),
      activitySummaryCard('Win rate', `${Number(summary.win_rate || 0).toFixed(1)}%`, 'accent'),
      activitySummaryCard('Total trades', Number(summary.total_trades || 0), 'neutral'),
      activitySummaryCard('Avg win/loss', `${Number(summary.average_win || 0).toFixed(2)} / ${Number(summary.average_loss || 0).toFixed(2)}`, 'neutral'),
    ].join('');
  }
}

function renderSummary() {
  const summary = state.summary || {};
  const heartbeat = state.heartbeat || {};
  const heartbeatChecks = Array.isArray(heartbeat.checks) ? heartbeat.checks : [];
  const heartbeatHealth = heartbeatChecks.length ? Math.round((heartbeatChecks.filter((item) => item.ok).length / heartbeatChecks.length) * 100) : null;
  const currentSync = state.executionLogs[0]?.status_reason || state.executionLogs[0]?.status || 'Sin eventos';
  document.getElementById('stat-connectors').textContent = Number(summary.total_connectors || 0);
  document.getElementById('stat-enabled').textContent = Number(summary.enabled_connectors || 0);
  document.getElementById('stat-trades').textContent = Number(summary.total_trades || 0);
  document.getElementById('stat-pnl').textContent = Number(summary.realized_pnl || 0).toFixed(2);
  const riskHealth = Number(summary?.risk_summary?.health_score || 0);
  const healthScore = heartbeatHealth !== null ? Math.min(heartbeatHealth, riskHealth) : riskHealth;
  document.getElementById('quant-health-score').textContent = `${Math.round(healthScore)}%`;
  document.getElementById('quant-sync-status').textContent = formatDecisionReason(currentSync);
  document.getElementById('quant-live-connectors').textContent = state.connectors.filter((c) => c.mode === 'live' && c.is_enabled).length;
  document.getElementById('quant-last-heartbeat').textContent = formatDate(heartbeat.checked_at || state.executionLogs[0]?.created_at);
  document.getElementById('quant-status-strip').innerHTML = reportMarkup([
    { title: 'Riesgo abierto', body: `${Number(summary?.risk_summary?.estimated_open_risk || 0).toFixed(2)} USD estimados.` },
    { title: 'Drawdown', body: `${Number(summary?.risk_summary?.rolling_drawdown_pct || 0).toFixed(2)}%` },
    { title: 'Kill switch', body: summary?.risk_summary?.kill_switch_armed ? 'Armado' : 'Desarmado' },
    { title: 'Heartbeat', body: heartbeatChecks.length ? `${heartbeatChecks.filter((item) => item.ok).length}/${heartbeatChecks.length} conectores respondiendo.` : 'Sin heartbeat reciente.' },
  ]);
  document.getElementById('executive-report-panel').innerHTML = reportMarkup([
    { title: 'PNL realizado', body: `${Number(summary.realized_pnl || 0).toFixed(2)} USD con ${Number(summary.total_trades || 0)} trades.` },
    { title: 'Win/Loss', body: `${Number(summary.winning_trades || 0)} ganadas · ${Number(summary.losing_trades || 0)} perdidas.` },
    { title: 'Plataformas', body: Object.entries(summary.platforms || {}).map(([platform, count]) => `${platform}: ${count}`).join(' · ') || 'Sin actividad aún.' },
  ]);
}

async function refreshHeartbeat({ quiet = false } = {}) {
  try {
    state.heartbeat = await api('/api/heartbeat');
    renderSummary();
  } catch (error) {
    if (!quiet) {
      setStatus('activity-command-feedback', parseApiError(error), 'error');
    }
  }
}

async function refreshConnectorBalances() {
  const connectors = Array.isArray(state.connectors) ? state.connectors : [];
  if (!connectors.length) {
    state.connectorBalances = {};
    renderConnectors();
    return;
  }
  const settled = await Promise.allSettled(connectors.map((connector) => api(`/api/connectors/${connector.id}/balance`)));
  const nextBalances = {};
  settled.forEach((result, index) => {
    const connector = connectors[index];
    if (!connector) return;
    nextBalances[connector.id] = result.status === 'fulfilled'
      ? result.value
      : {
        connector_id: connector.id,
        connector_label: connector.label,
        ok: false,
        error: parseApiError(result.reason),
      };
  });
  state.connectorBalances = nextBalances;
  renderConnectors();
}

async function refreshDashboard() {
  const settled = await Promise.allSettled([
    api('/api/me'),
    api('/api/dashboard'),
    api('/api/connectors'),
    api('/api/bot-sessions'),
    refreshExecutionLogs().then(() => ({ items: state.executionLogs, meta: state.executionLogsMeta })),
    api('/api/activity/performance'),
  ]);
  const labels = ['perfil', 'dashboard', 'conectores', 'bots', 'logs', 'actividad'];
  const failures = [];
  const values = settled.map((result, index) => {
    if (result.status === 'fulfilled') return result.value;
    failures.push(`${labels[index]}: ${parseApiError(result.reason)}`);
    return null;
  });
  const [me, summary, connectors, botSessions, executionLogs, activity] = values;
  state.me = me || state.me;
  state.summary = summary || state.summary || {};
  state.connectors = Array.isArray(connectors) ? connectors : (state.connectors || []);
  state.botSessions = Array.isArray(botSessions) ? botSessions : (state.botSessions || []);
  if (executionLogs?.items) {
    state.executionLogs = executionLogs.items;
    state.executionLogsMeta = executionLogs.meta || state.executionLogsMeta;
  }
  state.activity = activity || state.activity || null;
  renderProfile();
  renderConnectors();
  renderBotSessions();
  renderExecutionLogs();
  renderSummary();
  renderActivity();
  refreshConnectorBalances().catch((error) => {
    setStatus('connector-feedback', `No se pudieron cargar balances: ${parseApiError(error)}`, 'error');
  });
  refreshHeartbeat({ quiet: true }).catch(() => {});
  if (failures.length) {
    setStatus('run-feedback', `Algunas secciones no pudieron actualizarse: ${failures.join(' | ')}`, 'error');
  }
}

function collectProfilePayload() {
  const form = document.getElementById('profile-form');
  const fd = new FormData(form);
  const botKey = String(fd.get('telegram_bot_key') || '').trim();
  return {
    name: fd.get('name'),
    phone: fd.get('phone'),
    alert_language: fd.get('alert_language'),
    telegram_alerts_enabled: fd.get('telegram_alerts_enabled') === 'on',
    telegram_bot_key: botKey,
    telegram_chat_id: fd.get('telegram_chat_id'),
  };
}

async function saveProfile(event) {
  event.preventDefault();
  try {
    await api('/api/me', { method: 'PUT', body: JSON.stringify(collectProfilePayload()) });
    setStatus('profile-feedback', 'Perfil actualizado correctamente.', 'ok');
    await refreshDashboard();
  } catch (error) {
    setStatus('profile-feedback', parseApiError(error), 'error');
  }
}

async function testTelegram() {
  try {
    await api('/api/me', { method: 'PUT', body: JSON.stringify(collectProfilePayload()) });
    const result = await api('/api/me/telegram/test', { method: 'POST' });
    setStatus('telegram-test-feedback', result.message || 'Prueba enviada.', 'ok');
  } catch (error) {
    setStatus('telegram-test-feedback', parseApiError(error), 'error');
  }
}


async function saveConnector(event) {
  event.preventDefault();
  if (state.pendingActions.saveConnector) return;
  const form = event.currentTarget;
  const fd = new FormData(form);
  const platform = String(fd.get('platform'));
  const label = String(fd.get('label') || '').trim();
  if (!label) {
    setStatus('connector-feedback', 'Debes indicar un nombre para el conector.', 'error');
    return;
  }
  const { config, secrets } = readConnectorFriendlyFields(form, platform);
  const marketType = String(fd.get('market_type') || 'spot');
  const isEditing = Boolean(state.editingConnectorId);
  const missingRequiredField = connectorFieldDefinitions(platform, marketType).find((field) => {
    if (!field.required) return false;
    const input = form.querySelector(`[name="field_${field.target}_${field.key}"]`);
    if (!input) return false;
    if (field.target === 'secrets' && isEditing) return false;
    if (input.type === 'checkbox') return !input.checked;
    return !String(input.value || '').trim();
  });
  if (missingRequiredField) {
    setStatus('connector-feedback', `Completa el campo obligatorio "${missingRequiredField.label}".`, 'error');
    return;
  }
  const submitButton = document.getElementById('connector-submit-btn');
  try {
    state.pendingActions.saveConnector = true;
    setButtonsBusy(submitButton, true, 'Guardando...');
    await api(isEditing ? `/api/connectors/${state.editingConnectorId}` : '/api/connectors', {
      method: isEditing ? 'PUT' : 'POST',
      body: JSON.stringify({
        platform,
        label: fd.get('label'),
        mode: fd.get('mode'),
        market_type: fd.get('market_type'),
        symbols: String(fd.get('symbols') || '').split(',').map((item) => item.trim()).filter(Boolean),
        config,
        ...(Object.keys(secrets).length ? { secrets } : {}),
      }),
    });
    resetConnectorForm();
    setStatus('connector-feedback', isEditing ? 'Conector actualizado correctamente.' : 'Conector guardado correctamente.', 'ok');
    await refreshDashboard();
  } catch (error) {
    setStatus('connector-feedback', parseApiError(error), 'error');
  } finally {
    state.pendingActions.saveConnector = false;
    setButtonsBusy(submitButton, false);
  }
}

function buildRunPayload(form) {
  const fd = new FormData(form);
  const connectorId = Number(fd.get('connector_id'));
  const connector = getConnectorById(connectorId);

  if (!connector) {
    throw new Error('Debes seleccionar un conector válido antes de continuar.');
  }
  
  const parseOptionalNumber = (value) => {
    const normalized = String(value ?? '').trim();
    if (!normalized) return null;
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const parseRequiredNumber = (value, label) => {
    const parsed = parseOptionalNumber(value);
    if (parsed === null) throw new Error(`Debes completar ${label}.`);
    return parsed;
  };

  const symbols = String(fd.get('symbols') || '').split(',').map((item) => item.trim()).filter(Boolean);
  if (!symbols.length) {
    throw new Error('Debes indicar al menos un símbolo.');
  }
  const tradeAmountMode = String(fd.get('trade_amount_mode') || 'fixed_usd');
  const amountPerTrade = parseOptionalNumber(fd.get('amount_per_trade'));
  const amountPercentage = parseOptionalNumber(fd.get('amount_percentage'));
  if (tradeAmountMode === 'fixed_usd' && (!amountPerTrade || amountPerTrade <= 0)) {
    throw new Error('Debes indicar un monto por trade válido.');
  }
  if (tradeAmountMode === 'balance_percent' && (!amountPercentage || amountPercentage <= 0)) {
    throw new Error('Debes indicar un porcentaje por trade válido.');
  }

  const strategySlug = fd.get('strategy_slug');
  const selectedMarketType = connector?.market_type || 'spot';

  return {
    connector_id: connectorId,
    platform: connector.platform,
    session_name: String(fd.get('session_name') || '').trim() || null,
    market_type: selectedMarketType,
    symbols,
    symbol_source_mode: fd.get('symbol_source_mode') || 'manual',
    dynamic_symbol_limit: Number(fd.get('dynamic_symbol_limit') || 10),
    timeframe: fd.get('timeframe'),
    strategy_slug: strategySlug,
    risk_per_trade: parseRequiredNumber(fd.get('risk_per_trade_percent'), 'el riesgo por trade'),
    min_ml_probability: parseRequiredNumber(fd.get('min_ml_probability_percent'), 'la probabilidad mínima ML'),
    take_profit_mode: fd.get('take_profit_mode'),
    take_profit_value: parseRequiredNumber(fd.get('take_profit_value'), 'el take profit'),
    stop_loss_mode: fd.get('stop_loss_mode'),
    stop_loss_value: parseRequiredNumber(fd.get('stop_loss_value'), 'el stop loss'),
    trailing_stop_mode: fd.get('trailing_stop_mode'),
    trailing_stop_value: parseRequiredNumber(fd.get('trailing_stop_value'), 'el trailing stop'),
    trade_amount_mode: tradeAmountMode,
    amount_per_trade: amountPerTrade,
    amount_percentage: amountPercentage,
    use_live_if_available: true,
    indicator_exit_enabled: false,
    indicator_exit_rule: 'macd_cross',
    leverage_profile: 'none',
    max_open_positions: 1,
    compound_growth_enabled: false,
    atr_volatility_filter_enabled: true,
  };
}

function buildManualRunPayload(form) {
  const payload = buildRunPayload(form);
  return {
    connector_ids: [payload.connector_id],
    market_type: payload.market_type,
    symbols: payload.symbols,
    symbol_source_mode: payload.symbol_source_mode,
    dynamic_symbol_limit: payload.dynamic_symbol_limit,
    timeframe: payload.timeframe,
    strategy_slug: payload.strategy_slug,
    risk_per_trade: payload.risk_per_trade,
    min_ml_probability: payload.min_ml_probability,
    take_profit_mode: payload.take_profit_mode,
    take_profit_value: payload.take_profit_value,
    stop_loss_mode: payload.stop_loss_mode,
    stop_loss_value: payload.stop_loss_value,
    trailing_stop_mode: payload.trailing_stop_mode,
    trailing_stop_value: payload.trailing_stop_value,
    trade_amount_mode: payload.trade_amount_mode,
    amount_per_trade: payload.amount_per_trade,
    amount_percentage: payload.amount_percentage,
    use_live_if_available: payload.use_live_if_available,
    indicator_exit_enabled: payload.indicator_exit_enabled,
    indicator_exit_rule: payload.indicator_exit_rule,
    leverage_profile: payload.leverage_profile,
    max_open_positions: payload.max_open_positions,
    compound_growth_enabled: payload.compound_growth_enabled,
    atr_volatility_filter_enabled: payload.atr_volatility_filter_enabled,
  };
}

function getPopoverElements() {
  return {
    popover: document.getElementById('field-advisory-popover'),
    title: document.getElementById('field-advisory-title'),
    body: document.getElementById('field-advisory-body'),
  };
}

function hideFieldPopover() {
  const { popover } = getPopoverElements();
  if (!popover) return;
  popover.classList.add('hidden');
}

function showFieldPopover(target, title, body) {
  const { popover, title: titleEl, body: bodyEl } = getPopoverElements();
  if (!popover || !titleEl || !bodyEl || !target || !body) return;
  titleEl.textContent = title || 'Sugerencia';
  bodyEl.textContent = body;
  popover.classList.remove('hidden');
  const rect = target.getBoundingClientRect();
  const popRect = popover.getBoundingClientRect();
  const left = Math.max(12, Math.min(window.innerWidth - popRect.width - 12, rect.left));
  const top = rect.bottom + 10 + popRect.height < window.innerHeight
    ? rect.bottom + 10
    : Math.max(12, rect.top - popRect.height - 10);
  popover.style.left = `${left}px`;
  popover.style.top = `${top}px`;
}

function getFieldMeta(formKind, input) {
  return FIELD_ADVISORY_CONFIG[formKind]?.[input?.name] || null;
}

function parseSymbols(rawValue) {
  return String(rawValue || '').split(',').map((item) => item.trim()).filter(Boolean);
}

function advisoryForField(formKind, input) {
  if (!input) return null;
  const meta = getFieldMeta(formKind, input);
  const raw = input.type === 'checkbox' ? input.checked : String(input.value || '').trim();
  const form = input.form;
  const severity = 'warning';

  if (formKind === 'connector') {
    if (input.name === 'symbols') {
      const symbols = parseSymbols(raw);
      const unique = new Set(symbols.map((item) => item.toUpperCase()));
      if (!symbols.length) return { severity, message: 'Agrega al menos un símbolo base para testear compatibilidad y defaults.' };
      if (unique.size !== symbols.length) return { severity: 'danger', message: 'Hay símbolos duplicados. Deja cada par una sola vez.' };
      if (symbols.length > 30) return { severity, message: 'Demasiados símbolos iniciales pueden volver más lenta la operación y el monitoreo.' };
    }
    return meta?.recommend ? { severity: 'ok', message: meta.recommend } : null;
  }

  if (formKind === 'run') {
    const fd = new FormData(form);
    const tpMode = String(fd.get('take_profit_mode') || 'percent');
    const slMode = String(fd.get('stop_loss_mode') || 'percent');
    const trailingMode = String(fd.get('trailing_stop_mode') || 'percent');
    const tpValue = Number(fd.get('take_profit_value') || 0);
    const slValue = Number(fd.get('stop_loss_value') || 0);
    const trailingValue = Number(fd.get('trailing_stop_value') || 0);
    const mode = String(fd.get('trade_amount_mode') || 'fixed_usd');
    const connector = getConnectorById(fd.get('connector_id'));

    if (input.name === 'connector_id') {
      if (!connector) return { severity: 'danger', message: 'Debes elegir un conector válido y activo.' };
      if (!connector.is_enabled) return { severity: 'danger', message: 'Ese conector está desactivado. Actívalo antes de operar.' };
      return meta?.recommend ? { severity: 'ok', message: `${meta.recommend} Conector actual: ${connector.label} · ${prettyMarketType(connector.market_type)}.` } : null;
    }

    if (input.name === 'symbols') {
      const symbols = parseSymbols(raw);
      const unique = new Set(symbols.map((item) => item.toUpperCase()));
      if (!symbols.length) return { severity: 'danger', message: 'Ingresa al menos un símbolo para ejecutar la estrategia.' };
      if (unique.size !== symbols.length) return { severity: 'danger', message: 'No conviene repetir símbolos en una misma corrida.' };
      if (symbols.length > 12) return { severity, message: 'Más de 12 símbolos con el mismo capital suele diluir demasiado el sizing por operación.' };
      return meta?.recommend ? { severity: 'ok', message: meta.recommend } : null;
    }

    if (input.name === 'timeframe') {
      const allowed = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d'];
      if (!allowed.includes(raw)) return { severity, message: 'Usa un timeframe estándar como 5m, 15m, 1h o 4h para evitar intervalos ambiguos.' };
      if (['1m', '3m'].includes(raw)) return { severity, message: 'Timeframes muy bajos aumentan ruido, comisiones y sensibilidad a latencia.' };
      return meta?.recommend ? { severity: 'ok', message: meta.recommend } : null;
    }

    if (input.name === 'strategy_slug') {
      const strategy = String(raw || '');
      const market = String(connector?.market_type || fd.get('market_type') || 'spot').toLowerCase();
      const futuresOnly = ['momentum_breakout', 'macd_trend_pullback', 'adx_trend_follow', 'supertrend_volatility', 'kalman_trend_filter', 'atr_channel_breakout', 'volatility_breakout'];
      const spotOnly = ['ema_rsi', 'mean_reversion_zscore'];
      if (market === 'spot' && futuresOnly.includes(strategy)) return { severity: 'danger', message: 'Esta estrategia está pensada para futures; en spot puede generar expectativas no realistas.' };
      if (market === 'futures' && spotOnly.includes(strategy)) return { severity, message: 'Esta estrategia fue diseñada para spot. Verifica que el comportamiento en futures tenga sentido.' };
      return meta?.recommend ? { severity: 'ok', message: meta.recommend } : null;
    }

    if (input.name === 'risk_per_trade_percent') {
      const value = Number(raw || 0);
      if (value <= 0) return { severity: 'danger', message: 'El riesgo por trade debe ser mayor a 0.' };
      if (value > 5) return { severity: 'danger', message: 'Más de 5% por trade es agresivo para una cuenta robusta y puede escalar drawdown muy rápido.' };
      if (value > 2) return { severity, message: 'Por encima de 2% por trade ya entras en un perfil de riesgo elevado.' };
      if (value < 0.25) return { severity: 'ok', message: 'Riesgo muy conservador: protege capital, pero puede volver insignificante el impacto del sistema.' };
      return meta?.recommend ? { severity: 'ok', message: meta.recommend } : null;
    }

    if (input.name === 'min_ml_probability_percent') {
      const value = Number(raw || 0);
      if (value < 50) return { severity, message: 'Un filtro ML por debajo de 50% suele dejar pasar demasiadas señales débiles.' };
      if (value > 90) return { severity, message: 'Un umbral tan alto puede bloquear casi todas las entradas y hacer que el bot opere muy poco.' };
      return meta?.recommend ? { severity: 'ok', message: meta.recommend } : null;
    }

    if (input.name === 'stop_loss_value') {
      if (slValue <= 0) return { severity: 'danger', message: 'Toda operación necesita stop loss positivo.' };
      if (slMode === 'percent' && slValue > 1.5) return { severity: 'danger', message: 'El backend ya restringe stop loss porcentual superior a 1.5% para evitar setups descontrolados.' };
      if (tpMode === slMode && tpValue > 0 && slValue >= tpValue) return { severity: 'danger', message: 'El stop loss no debería ser igual o mayor al take profit cuando comparten unidad.' };
      return meta?.recommend ? { severity: 'ok', message: meta.recommend } : null;
    }

    if (input.name === 'take_profit_value') {
      if (tpValue <= 0 && trailingValue <= 0) return { severity: 'danger', message: 'Define take profit o trailing stop; no dejes salidas abiertas sin criterio.' };
      if (tpMode === slMode && tpValue > 0 && slValue >= tpValue) return { severity: 'danger', message: 'El take profit debe dejar un espacio lógico por encima del stop loss.' };
      return meta?.recommend ? { severity: 'ok', message: meta.recommend } : null;
    }

    if (input.name === 'trailing_stop_value') {
      if (trailingValue <= 0) return { severity: 'ok', message: 'Puedes dejar trailing en 0 solo si el take profit está bien definido y la estrategia no requiere trailing.' };
      if (trailingMode === slMode && trailingValue >= slValue) return { severity, message: 'Un trailing mayor o igual al stop puede volver incoherente la protección dinámica.' };
      return meta?.recommend ? { severity: 'ok', message: meta.recommend } : null;
    }

    if (input.name === 'trade_amount_mode') {
      return meta?.recommend ? { severity: 'ok', message: meta.recommend } : null;
    }

    if (input.name === 'amount_per_trade') {
      const value = Number(raw || 0);
      if (mode === 'fixed_usd' && value <= 0) return { severity: 'danger', message: 'En modo monto fijo debes definir un capital por operación.' };
      if (mode === 'fixed_usd' && value > 0 && value < 10) return { severity, message: 'Montos muy bajos suelen chocar con mínimos de exchange, sobre todo en símbolos caros.' };
      return meta?.recommend ? { severity: 'ok', message: meta.recommend } : null;
    }

    if (input.name === 'amount_percentage') {
      const value = Number(raw || 0);
      if (mode === 'balance_percent' && value <= 0) return { severity: 'danger', message: 'En modo % de balance debes definir un porcentaje válido.' };
      if (mode === 'balance_percent' && value > 25) return { severity: 'danger', message: 'Más de 25% del balance por trade suele ser excesivo para una operación cuantitativa estable.' };
      if (mode === 'balance_percent' && value > 10) return { severity, message: 'Por encima de 10% por trade ya estás asumiendo una exposición importante.' };
      return meta?.recommend ? { severity: 'ok', message: meta.recommend } : null;
    }

  }

  return meta?.recommend ? { severity: 'ok', message: meta.recommend } : null;
}

function syncFieldHintState(formKind, input, { reveal = false } = {}) {
  if (!input) return;
  const label = input.closest('label');
  if (!label) return;
  const meta = getFieldMeta(formKind, input);
  if (!meta) return;
  const advisory = advisoryForField(formKind, input);
  label.classList.add('field-hint-enabled');
  label.classList.remove('field-hint-warning', 'field-hint-danger');
  if (advisory?.severity === 'warning') label.classList.add('field-hint-warning');
  if (advisory?.severity === 'danger') label.classList.add('field-hint-danger');
  if (reveal && advisory?.message) showFieldPopover(input, meta.title, advisory.message);
}

function appendAsteriskToLabel(label) {
  if (!label || label.querySelector('.field-asterisk')) return;
  const trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'field-advisory-trigger';
  trigger.textContent = '?';
  label.insertBefore(trigger, label.firstElementChild || null);
  const marker = document.createElement('span');
  marker.className = 'field-asterisk';
  marker.textContent = ' *';
  label.insertBefore(marker, label.firstElementChild || null);
}

function bindFieldAdvisories(formSelector, formKind) {
  const form = document.querySelector(formSelector);
  if (!form || form.dataset.advisoriesBound === 'true') return;
  form.dataset.advisoriesBound = 'true';
  const inputs = Array.from(form.querySelectorAll('input, select, textarea'));
  inputs.forEach((input) => {
    const meta = getFieldMeta(formKind, input);
    if (!meta) return;
    const label = input.closest('label');
    appendAsteriskToLabel(label);
    const trigger = label?.querySelector('.field-advisory-trigger');
    ['mouseenter', 'focus'].forEach((eventName) => {
      trigger?.addEventListener(eventName, () => {
        const advisory = advisoryForField(formKind, input);
        if (advisory?.message) showFieldPopover(trigger, meta.title, advisory.message);
      });
    });
    ['input', 'change'].forEach((eventName) => {
      input.addEventListener(eventName, () => syncFieldHintState(formKind, input, { reveal: true }));
    });
    input.addEventListener('blur', hideFieldPopover);
    syncFieldHintState(formKind, input);
  });
  form.addEventListener('mouseleave', hideFieldPopover);
}

async function runStrategy(event) {
  event.preventDefault();
  if (state.pendingActions.runStrategy) return;
  try {
    const form = event.currentTarget;
    const submitButton = document.getElementById('run-strategy-btn');
    state.pendingActions.runStrategy = true;
    setStatus('run-feedback', 'Ejecutando estrategia...', 'ok');
    setButtonsBusy([submitButton, document.getElementById('activate-bot-btn')], true, 'Procesando...');
    await api('/api/strategies/run', { method: 'POST', body: JSON.stringify(buildManualRunPayload(form)) });
    setStatus('run-feedback', 'Estrategia ejecutada correctamente.', 'ok');
    await refreshDashboard();
  } catch (error) {
    setStatus('run-feedback', parseApiError(error), 'error');
  } finally {
    state.pendingActions.runStrategy = false;
    setButtonsBusy([document.getElementById('run-strategy-btn'), document.getElementById('activate-bot-btn')], false);
  }
}

async function activateBotFromForm() {
  if (state.pendingActions.activateBot) return;
  try {
    const form = document.getElementById('run-form');
    if (!form) return;
    state.pendingActions.activateBot = true;
    setStatus('run-feedback', 'Creando estrategia automática...', 'ok');
    setButtonsBusy([document.getElementById('activate-bot-btn'), document.getElementById('run-strategy-btn')], true, 'Procesando...');
    const payload = buildRunPayload(form);
    const result = await api('/api/bot-sessions', { method: 'POST', body: JSON.stringify(payload) });
    const targetSessionId = Number(result?.session_id || 0);
    for (let attempt = 0; attempt < 4; attempt += 1) {
      await refreshDashboard();
      if (!targetSessionId || state.botSessions.some((item) => Number(item.id) === targetSessionId)) break;
      await new Promise((resolve) => window.setTimeout(resolve, 350));
    }
    setStatus('run-feedback', 'Bot 24/7 activado correctamente.', 'ok');
  } catch (error) {
    setStatus('run-feedback', parseApiError(error), 'error');
  } finally {
    state.pendingActions.activateBot = false;
    setButtonsBusy([document.getElementById('activate-bot-btn'), document.getElementById('run-strategy-btn')], false);
  }
}

function downloadExecutionLogs() {
  window.open('/api/execution-logs/download?limit=1000', '_blank');
}

async function runHeartbeatCheck() {
  try {
    setStatus('activity-command-feedback', 'Ejecutando heartbeat...', 'ok');
    await refreshHeartbeat();
    setStatus('activity-command-feedback', 'Heartbeat completado.', 'ok');
  } catch (error) {
    setStatus('activity-command-feedback', parseApiError(error), 'error');
  }
}

async function triggerKillSwitchFromDashboard() {
  try {
    setStatus('activity-command-feedback', 'Activando kill switch...', 'ok');
    await api('/api/risk/kill-switch', { method: 'POST', body: JSON.stringify({}) });
    setStatus('activity-command-feedback', 'Kill switch ejecutado.', 'ok');
    await refreshDashboard();
  } catch (error) {
    setStatus('activity-command-feedback', parseApiError(error), 'error');
  }
}

function startAutoRefresh() {
  window.setInterval(() => {
    refreshDashboard().catch((error) => {
      setStatus('activity-command-feedback', `Auto refresh falló: ${parseApiError(error)}`, 'error');
    });
  }, 120000);
}

async function init() {
  initTabs();
  resetConnectorForm();
  document.getElementById('run-connector-select')?.addEventListener('change', () => {
    const connectorId = document.getElementById('run-connector-select').value;
    const connector = getConnectorById(connectorId);
    renderStrategyOptions(connector?.market_type);
  });
  document.getElementById('connector-platform')?.addEventListener('change', renderConnectorFields);
  document.getElementById('connector-market-type')?.addEventListener('change', renderConnectorFields);
  document.getElementById('reset-connector-form-btn')?.addEventListener('click', resetConnectorForm);
  document.getElementById('cancel-connector-edit-btn')?.addEventListener('click', resetConnectorForm);
  document.getElementById('profile-form')?.addEventListener('submit', saveProfile);
  document.getElementById('test-telegram-btn')?.addEventListener('click', testTelegram);
  document.getElementById('connector-form')?.addEventListener('submit', saveConnector);
  document.getElementById('run-form')?.addEventListener('submit', runStrategy);
  document.getElementById('activate-bot-btn')?.addEventListener('click', activateBotFromForm);
  document.getElementById('refresh-connector-health-btn')?.addEventListener('click', refreshDashboard);
  document.getElementById('activity-refresh-btn')?.addEventListener('click', refreshDashboard);
  document.getElementById('activity-heartbeat-btn')?.addEventListener('click', runHeartbeatCheck);
  document.getElementById('activity-kill-switch-btn')?.addEventListener('click', triggerKillSwitchFromDashboard);
  document.getElementById('refresh-bot-sessions-btn')?.addEventListener('click', refreshDashboard);
  document.getElementById('refresh-execution-logs-btn')?.addEventListener('click', refreshDashboard);
  document.getElementById('download-execution-logs-btn')?.addEventListener('click', downloadExecutionLogs);
  document.getElementById('run-symbol-source-mode')?.addEventListener('change', (event) => {
    const dynamic = String(event.currentTarget?.value || 'manual') === 'dynamic';
    const wrap = document.getElementById('run-dynamic-limit-field');
    wrap?.classList.toggle('hidden', !dynamic);
  });
  document.getElementById('run-symbol-source-mode')?.dispatchEvent(new Event('change'));
  window.addEventListener('scroll', hideFieldPopover, { passive: true });
  window.addEventListener('resize', hideFieldPopover);
  bindFieldAdvisories('#connector-form', 'connector');
  bindFieldAdvisories('#run-form', 'run');
  document.getElementById('connector-form')?.setAttribute('novalidate', 'novalidate');
  document.getElementById('run-form')?.setAttribute('novalidate', 'novalidate');
  await refreshDashboard();
  startAutoRefresh();
}

init().catch((error) => {
  setStatus('run-feedback', `Error cargando dashboard: ${parseApiError(error)}`, 'error');
});
