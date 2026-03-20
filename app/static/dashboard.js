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
    { key: 'login', label: 'Login MT5', target: 'secrets', required: true },
    { key: 'password', label: 'Password MT5', target: 'secrets', required: true },
    { key: 'server', label: 'Server', target: 'secrets', required: true },
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

const STRATEGIES = [
  'ema_rsi',
  'mean_reversion_zscore',
  'momentum_breakout',
  'ema_rsi_adx_stack',
  'volatility_compression_breakout',
  'macd_trend_pullback',
  'adx_trend_follow',
  'supertrend_volatility',
  'kalman_trend_filter',
  'atr_channel_breakout',
  'volatility_breakout',
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
      recommend: 'Heredar sirve para consistencia. Monto fijo aporta control; % de balance adapta el tamaño al capital.',
    },
    amount_per_trade: {
      title: 'Monto por trade',
      recommend: 'Debe ser suficiente para superar mínimos del exchange y no quedar rechazado por notional o qty mínima.',
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

const state = {
  me: null,
  summary: null,
  connectors: [],
  botSessions: [],
  executionLogs: [],
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
  return d.toLocaleString();
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

function initTabs() {
  const buttons = Array.from(document.querySelectorAll('#dashboard-tabs .tab-btn'));
  buttons.forEach((button) => {
    button.addEventListener('click', () => {
      buttons.forEach((btn) => btn.classList.toggle('active', btn === button));
      document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.toggle('active', panel.id === `tab-${button.dataset.tab}`));
    });
  });
}

function renderStrategyOptions() {
  const select = document.getElementById('strategy-select');
  if (!select) return;
  select.innerHTML = STRATEGIES.map((slug) => `<option value="${slug}">${slug}</option>`).join('');
}

function renderConnectorFields() {
  const platform = document.getElementById('connector-platform')?.value || 'binance';
  const marketType = document.getElementById('connector-market-type');
  const fieldsWrap = document.getElementById('connector-friendly-fields');
  if (marketType) {
    marketType.innerHTML = (PLATFORM_MARKET_TYPES[platform] || ['spot']).map((type) => `<option value="${type}">${prettyMarketType(type)}</option>`).join('');
  }
  if (fieldsWrap) {
    fieldsWrap.innerHTML = (PLATFORM_FIELD_MAP[platform] || []).map((field) => `
      <label>${field.label}
        <input name="field_${field.target}_${field.key}" ${field.required ? 'required' : ''}>
      </label>
    `).join('');
  }
}

function readConnectorFriendlyFields(formEl, platform) {
  const fd = new FormData(formEl);
  const config = {};
  const secrets = {};
  (PLATFORM_FIELD_MAP[platform] || []).forEach((field) => {
    const value = String(fd.get(`field_${field.target}_${field.key}`) || '').trim();
    if (!value) return;
    if (field.target === 'secrets') secrets[field.key] = value;
    else config[field.key] = value;
  });
  return { config, secrets };
}

function renderProfile() {
  const user = state.me;
  if (!user) return;
  document.getElementById('profile-name').value = user.name || '';
  document.getElementById('profile-email').value = user.email || '';
  document.getElementById('profile-phone').value = user.phone || '';
  document.getElementById('profile-alert-language').value = user.alert_language || 'es';
  document.getElementById('profile-telegram-enabled').checked = Boolean(user.telegram_alerts_enabled);
  document.getElementById('profile-telegram-bot-key').value = user.has_telegram_bot_key ? '••••••••' : '';
  document.getElementById('profile-telegram-chat-id').value = user.telegram_chat_id || '';
  document.getElementById('trade-amount-mode').value = user.trade_amount_mode || 'fixed_usd';
  document.getElementById('fixed-trade-amount-usd').value = Number(user.fixed_trade_amount_usd || 10);
  document.getElementById('trade-balance-percent').value = Number(user.trade_balance_percent || 10);
  document.getElementById('profile-title').textContent = user.is_admin ? 'Cuenta administrativa' : 'Perfil de usuario';
  document.getElementById('user-config-state').textContent = `Perfil · ${user.name || user.email}`;
  document.getElementById('user-config-report').innerHTML = reportMarkup([
    { title: 'Alertas', body: user.telegram_alerts_enabled ? `Telegram activo · idioma ${String(user.alert_language || 'es').toUpperCase()}` : 'Telegram inactivo' },
    { title: 'Sizing', body: user.trade_amount_mode === 'balance_percent' ? `${user.trade_balance_percent}% del balance por operación` : `${Number(user.fixed_trade_amount_usd || 0).toFixed(2)} USD por operación` },
    { title: 'Canal admin', body: user.admin_alerts_enabled ? 'Canal administrativo de contingencias disponible' : 'Canal administrativo no configurado' },
  ]);
}

function renderConnectors() {
  const list = document.getElementById('connector-list');
  const panel = document.getElementById('connector-health-panel');
  const runSelect = document.getElementById('run-connector-select');
  if (runSelect) {
    runSelect.innerHTML = state.connectors.filter((c) => c.is_enabled).map((c) => `<option value="${c.id}">${c.label} · ${c.platform} · ${prettyMarketType(c.market_type, c.id)}</option>`).join('');
  }
  if (panel) {
    panel.innerHTML = state.connectors.length ? reportMarkup(state.connectors.map((c) => ({
      title: `${c.label} · ${c.platform}`,
      body: `${c.mode} · ${prettyMarketType(c.market_type, c.id)} · ${c.is_enabled ? 'activo' : 'inactivo'} · ${(c.symbols || []).length} símbolos`,
    }))) : reportMarkup([{ title: 'Sin conectores', body: 'Crea al menos un conector para operar o automatizar.' }]);
  }
  if (!list) return;
  if (!state.connectors.length) {
    list.innerHTML = '<small class="hint">No hay conectores configurados todavía.</small>';
    return;
  }
  list.innerHTML = state.connectors.map((connector) => `
    <article class="connector-item fade-in-up">
      <div class="row-between">
        <div>
          <strong>${connector.label}</strong>
          <div class="connector-meta">
            <span>${connector.platform}</span>
            <span>${connector.mode}</span>
            <span>${prettyMarketType(connector.market_type, connector.id)}</span>
          </div>
        </div>
        <span class="pill tiny ${connector.is_enabled ? 'pill-on' : 'pill-off'}">${connector.is_enabled ? 'Activo' : 'Inactivo'}</span>
      </div>
      <small class="hint">Símbolos: ${(connector.symbols || []).join(', ') || 'Sin símbolos configurados'}.</small>
      <div class="row-wrap" style="margin-top:12px;">
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
        if (action === 'test') {
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
    <article class="connector-item fade-in-up">
      <div class="row-between">
        <div>
          <strong>${prettyLabel(session.strategy_slug, 'strategy')}</strong>
          <div class="connector-meta">
            <span>${prettyLabel(session.connector_label, 'Cuenta')}</span>
            <span>${prettyLabel(session.platform, '-')}</span>
            <span>${prettyMarketType(session.market_type, session.connector_id)}</span>
          </div>
        </div>
        <span class="pill tiny ${session.is_active ? 'pill-on' : 'pill-off'}">${session.is_active ? 'Activo' : 'Pausado'}</span>
      </div>
      <small class="hint">${(session.symbols || []).join(', ')} · ${session.timeframe} · Próxima corrida: ${formatDate(session.next_run_at)}.</small>
      <small class="hint">Sizing: ${session.trade_amount_mode || 'inherit'} · Capital ref: ${Number(session.capital_per_operation || 0).toFixed(2)} ${session.capital_currency || 'USDT'}.</small>
      <small class="hint">Estado: ${session.last_status || '-'}${session.last_error ? ` · ${session.last_error}` : ''}</small>
      <div class="row-wrap" style="margin-top:12px;">
        <button class="btn btn-sm" type="button" data-bot-action="toggle" data-id="${session.id}" data-enabled="${session.is_active}">${session.is_active ? 'Pausar' : 'Activar'}</button>
        <button class="btn btn-sm" type="button" data-bot-action="delete" data-id="${session.id}">Eliminar</button>
      </div>
    </article>
  `).join('');

  panel.querySelectorAll('button[data-bot-action]').forEach((button) => {
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.id);
      try {
        if (button.dataset.botAction === 'toggle') {
          await api(`/api/bot-sessions/${id}`, { method: 'PUT', body: JSON.stringify({ is_active: button.dataset.enabled !== 'true' }) });
        } else {
          await api(`/api/bot-sessions/${id}`, { method: 'DELETE' });
        }
        await refreshDashboard();
      } catch (error) {
        setStatus('run-feedback', parseApiError(error), 'error');
      }
    });
  });
}

function renderExecutionLogs() {
  const body = document.querySelector('#execution-logs-table tbody');
  if (!body) return;
  if (!state.executionLogs.length) {
    body.innerHTML = '<tr><td colspan="6"><small class="hint">Sin logs todavía.</small></td></tr>';
    return;
  }
  body.innerHTML = state.executionLogs.map((item) => `
    <tr>
      <td>${formatDate(item.created_at)}</td>
      <td>${item.symbol || '-'}</td>
      <td>${item.timeframe || '-'}</td>
      <td>${item.signal || '-'}</td>
      <td>${item.status || '-'}</td>
      <td>${Number(item.ml_probability || 0).toFixed(3)}</td>
    </tr>
  `).join('');
  const meta = document.getElementById('execution-logs-refresh-meta');
  if (meta) meta.textContent = `Mostrando ${state.executionLogs.length} logs. Última actualización: ${new Date().toLocaleTimeString()}`;
}

function renderSummary() {
  const summary = state.summary || {};
  document.getElementById('stat-connectors').textContent = Number(summary.total_connectors || 0);
  document.getElementById('stat-enabled').textContent = Number(summary.enabled_connectors || 0);
  document.getElementById('stat-trades').textContent = Number(summary.total_trades || 0);
  document.getElementById('stat-pnl').textContent = Number(summary.realized_pnl || 0).toFixed(2);
  document.getElementById('quant-health-score').textContent = `${Math.round(summary?.risk_summary?.health_score || 0)}%`;
  document.getElementById('quant-sync-status').textContent = (state.executionLogs[0]?.status || 'Sin eventos');
  document.getElementById('quant-live-connectors').textContent = state.connectors.filter((c) => c.mode === 'live' && c.is_enabled).length;
  document.getElementById('quant-last-heartbeat').textContent = formatDate(state.executionLogs[0]?.created_at);
  document.getElementById('quant-status-strip').innerHTML = reportMarkup([
    { title: 'Riesgo abierto', body: `${Number(summary?.risk_summary?.estimated_open_risk || 0).toFixed(2)} USD estimados.` },
    { title: 'Drawdown', body: `${Number(summary?.risk_summary?.rolling_drawdown_pct || 0).toFixed(2)}%` },
    { title: 'Kill switch', body: summary?.risk_summary?.kill_switch_armed ? 'Armado' : 'Desarmado' },
  ]);
  document.getElementById('executive-report-panel').innerHTML = reportMarkup([
    { title: 'PNL realizado', body: `${Number(summary.realized_pnl || 0).toFixed(2)} USD con ${Number(summary.total_trades || 0)} trades.` },
    { title: 'Win/Loss', body: `${Number(summary.winning_trades || 0)} ganadas · ${Number(summary.losing_trades || 0)} perdidas.` },
    { title: 'Plataformas', body: Object.entries(summary.platforms || {}).map(([platform, count]) => `${platform}: ${count}`).join(' · ') || 'Sin actividad aún.' },
  ]);
}

async function refreshDashboard() {
  const [me, summary, connectors, botSessions, executionLogs] = await Promise.all([
    api('/api/me'),
    api('/api/dashboard'),
    api('/api/connectors'),
    api('/api/bot-sessions'),
    api('/api/execution-logs?limit=25'),
  ]);
  state.me = me;
  state.summary = summary;
  state.connectors = Array.isArray(connectors) ? connectors : [];
  state.botSessions = Array.isArray(botSessions) ? botSessions : [];
  state.executionLogs = Array.isArray(executionLogs) ? executionLogs : [];
  renderProfile();
  renderConnectors();
  renderBotSessions();
  renderExecutionLogs();
  renderSummary();
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
    telegram_bot_key: botKey.startsWith('••••') ? undefined : botKey,
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

async function saveTradeAmountSettings(event) {
  event.preventDefault();
  const fd = new FormData(event.currentTarget);
  try {
    await api('/api/me', {
      method: 'PUT',
      body: JSON.stringify({
        trade_amount_mode: fd.get('trade_amount_mode'),
        fixed_trade_amount_usd: Number(fd.get('fixed_trade_amount_usd')),
        trade_balance_percent: Number(fd.get('trade_balance_percent')),
      }),
    });
    setStatus('profile-trade-amount-feedback', 'Configuración de sizing guardada.', 'ok');
    await refreshDashboard();
  } catch (error) {
    setStatus('profile-trade-amount-feedback', parseApiError(error), 'error');
  }
}

async function saveConnector(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const fd = new FormData(form);
  const platform = String(fd.get('platform'));
  const { config, secrets } = readConnectorFriendlyFields(form, platform);
  try {
    await api('/api/connectors', {
      method: 'POST',
      body: JSON.stringify({
        platform,
        label: fd.get('label'),
        mode: fd.get('mode'),
        market_type: fd.get('market_type'),
        symbols: String(fd.get('symbols') || '').split(',').map((item) => item.trim()).filter(Boolean),
        config,
        secrets,
      }),
    });
    form.reset();
    renderConnectorFields();
    bindFieldAdvisories('#connector-form', 'connector');
    setStatus('connector-feedback', 'Conector guardado correctamente.', 'ok');
    await refreshDashboard();
  } catch (error) {
    setStatus('connector-feedback', parseApiError(error), 'error');
  }
}

function buildRunPayload(form) {
  const fd = new FormData(form);
  const connectorId = Number(fd.get('connector_id'));
  const connector = getConnectorById(connectorId);
  return {
    connector_ids: [connectorId],
    connector_id: connectorId,
    market_type: connector?.market_type || 'spot',
    symbols: String(fd.get('symbols') || '').split(',').map((item) => item.trim()).filter(Boolean),
    timeframe: fd.get('timeframe'),
    strategy_slug: fd.get('strategy_slug'),
    risk_per_trade: Number(fd.get('risk_per_trade_percent')),
    min_ml_probability: Number(fd.get('min_ml_probability_percent')),
    take_profit_mode: fd.get('take_profit_mode'),
    take_profit_value: Number(fd.get('take_profit_value')),
    stop_loss_mode: fd.get('stop_loss_mode'),
    stop_loss_value: Number(fd.get('stop_loss_value')),
    trailing_stop_mode: fd.get('trailing_stop_mode'),
    trailing_stop_value: Number(fd.get('trailing_stop_value')),
    trade_amount_mode: fd.get('trade_amount_mode'),
    amount_per_trade: fd.get('amount_per_trade') ? Number(fd.get('amount_per_trade')) : null,
    amount_percentage: fd.get('amount_percentage') ? Number(fd.get('amount_percentage')) : null,
    use_live_if_available: fd.get('use_live_if_available') === 'on',
    indicator_exit_enabled: false,
    indicator_exit_rule: 'macd_cross',
    leverage_profile: 'none',
    max_open_positions: 1,
    compound_growth_enabled: false,
    atr_volatility_filter_enabled: true,
    symbol_source_mode: 'manual',
    dynamic_symbol_limit: 10,
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
    const mode = String(fd.get('trade_amount_mode') || 'inherit');
    const connector = getConnectorById(fd.get('connector_id'));

    if (input.name === 'connector_id') {
      if (!connector) return { severity: 'danger', message: 'Debes elegir un conector válido y activo.' };
      if (!connector.is_enabled) return { severity: 'danger', message: 'Ese conector está desactivado. Actívalo antes de operar.' };
      if (connector.mode !== 'live' && fd.get('use_live_if_available') === 'on') return { severity, message: 'El conector no está en modo live; aunque actives live, la orden no saldrá al exchange.' };
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
      if (raw === 'inherit' && !state.me) return { severity, message: 'Si vas a heredar sizing, primero asegúrate de tener el perfil de capital configurado.' };
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

    if (input.name === 'use_live_if_available') {
      if (input.checked && connector?.mode !== 'live') return { severity, message: 'Marcaste live, pero el conector actual no está en modo live.' };
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
    ['focus', 'mouseenter'].forEach((eventName) => {
      input.addEventListener(eventName, () => {
        const advisory = advisoryForField(formKind, input);
        if (advisory?.message) showFieldPopover(input, meta.title, advisory.message);
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
  try {
    await api('/api/strategies/run', { method: 'POST', body: JSON.stringify(buildRunPayload(event.currentTarget)) });
    setStatus('run-feedback', 'Estrategia ejecutada correctamente.', 'ok');
    await refreshDashboard();
  } catch (error) {
    setStatus('run-feedback', parseApiError(error), 'error');
  }
}

async function activateBotFromForm() {
  try {
    const form = document.getElementById('run-form');
    const payload = buildRunPayload(form);
    await api('/api/bot-sessions', { method: 'POST', body: JSON.stringify(payload) });
    setStatus('run-feedback', 'Bot 24/7 activado correctamente.', 'ok');
    await refreshDashboard();
  } catch (error) {
    setStatus('run-feedback', parseApiError(error), 'error');
  }
}

function downloadExecutionLogs() {
  window.open('/api/execution-logs/download?limit=1000', '_blank');
}

async function init() {
  initTabs();
  renderStrategyOptions();
  renderConnectorFields();
  document.getElementById('connector-platform')?.addEventListener('change', renderConnectorFields);
  document.getElementById('profile-form')?.addEventListener('submit', saveProfile);
  document.getElementById('test-telegram-btn')?.addEventListener('click', testTelegram);
  document.getElementById('profile-trade-amount-form')?.addEventListener('submit', saveTradeAmountSettings);
  document.getElementById('connector-form')?.addEventListener('submit', saveConnector);
  document.getElementById('run-form')?.addEventListener('submit', runStrategy);
  document.getElementById('activate-bot-btn')?.addEventListener('click', activateBotFromForm);
  document.getElementById('refresh-connector-health-btn')?.addEventListener('click', refreshDashboard);
  document.getElementById('refresh-bot-sessions-btn')?.addEventListener('click', refreshDashboard);
  document.getElementById('refresh-execution-logs-btn')?.addEventListener('click', refreshDashboard);
  document.getElementById('download-execution-logs-btn')?.addEventListener('click', downloadExecutionLogs);
  window.addEventListener('scroll', hideFieldPopover, { passive: true });
  window.addEventListener('resize', hideFieldPopover);
  bindFieldAdvisories('#connector-form', 'connector');
  bindFieldAdvisories('#run-form', 'run');
  await refreshDashboard();
}

init().catch((error) => {
  setStatus('run-feedback', `Error cargando dashboard: ${parseApiError(error)}`, 'error');
});
