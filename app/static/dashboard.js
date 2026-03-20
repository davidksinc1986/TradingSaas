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

function reportMarkup(items = []) {
  return items.map((item) => `
    <article class="quantum-report-item fade-in-up">
      <strong>${item.title}</strong>
      <small>${item.body}</small>
    </article>
  `).join('');
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
    marketType.innerHTML = (PLATFORM_MARKET_TYPES[platform] || ['spot']).map((type) => `<option value="${type}">${type}</option>`).join('');
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
    runSelect.innerHTML = state.connectors.filter((c) => c.is_enabled).map((c) => `<option value="${c.id}">${c.label} · ${c.platform} · ${c.market_type}</option>`).join('');
  }
  if (panel) {
    panel.innerHTML = state.connectors.length ? reportMarkup(state.connectors.map((c) => ({
      title: `${c.label} · ${c.platform}`,
      body: `${c.mode} · ${c.market_type} · ${c.is_enabled ? 'activo' : 'inactivo'} · ${(c.symbols || []).length} símbolos`,
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
            <span>${connector.market_type}</span>
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
          <strong>${session.strategy_slug}</strong>
          <div class="connector-meta">
            <span>${session.connector_label}</span>
            <span>${session.platform}</span>
            <span>${session.market_type}</span>
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
    setStatus('connector-feedback', 'Conector guardado correctamente.', 'ok');
    await refreshDashboard();
  } catch (error) {
    setStatus('connector-feedback', parseApiError(error), 'error');
  }
}

function buildRunPayload(form) {
  const fd = new FormData(form);
  const connectorId = Number(fd.get('connector_id'));
  return {
    connector_ids: [connectorId],
    connector_id: connectorId,
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
  await refreshDashboard();
}

init().catch((error) => {
  setStatus('run-feedback', `Error cargando dashboard: ${parseApiError(error)}`, 'error');
});
