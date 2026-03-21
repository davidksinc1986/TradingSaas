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

function setFeedback(message, kind = 'ok') {
  const node = document.getElementById('admin-feedback');
  if (!node) return;
  node.textContent = message || '';
  node.className = `status-msg ${message ? `status-${kind}` : ''}`.trim();
}

let usersState = [];
let selectedUserId = null;
let adminOverviewState = null;

function formatDate(value) {
  if (!value) return '-';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  const two = (number) => String(number).padStart(2, '0');
  return `${two(d.getDate())}/${two(d.getMonth() + 1)}/${String(d.getFullYear()).slice(-2)}, ${two(d.getHours())}:${two(d.getMinutes())}`;
}


function activitySummaryCard(title, value, tone = 'neutral') {
  return `
    <article class="activity-mini-card tone-${tone}">
      <small>${title}</small>
      <strong>${value}</strong>
    </article>
  `;
}

let currentAdminLogTab = 'activity';

function isSystemError(item) {
  const status = String(item.status || '').toLowerCase();
  const reason = String(item.reason || item.status_reason || '').toLowerCase();
  const errorMarkers = ['error', 'failed', 'skipped', 'insufficient', 'locked', 'timeout', 'invalid', 'rejected', 'danger'];
  return errorMarkers.some((m) => status.includes(m) || reason.includes(m));
}

function statusPillClass(kind) {
  const normalized = String(kind || '').toLowerCase();
  if (['error', 'failed', 'danger'].includes(normalized)) return 'pill-danger';
  if (['warning', 'skipped', 'paused'].includes(normalized)) return 'pill-warning';
  return 'pill-ok';
}

function displaySymbol(value) {
  const raw = String(value || '').trim().toUpperCase();
  if (!raw) return '-';
  return raw.replace('/USDT', '').replace('USDT', '').replace('/', '') || raw;
}

function renderAdminEvents() {
  const eventsWrap = document.getElementById('admin-recent-events');
  if (!eventsWrap) return;
  const overview = adminOverviewState || {};
  
  // Combine runs and trades for a unified log view if needed, or focus on 'events' (runs)
  const allEvents = (overview.events || []).map(e => ({...e, type: 'run'}));
  const trades = (overview.trade_logs || []).map(t => ({...t, type: 'trade', signal: t.side, reason: t.platform}));
  const unified = [...allEvents, ...trades].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const filtered = unified.filter((item) => {
    const isErr = isSystemError(item);
    return currentAdminLogTab === 'system' ? isErr : !isErr;
  });

  if (!filtered.length) {
    eventsWrap.innerHTML = `<small class="hint">No hay ${currentAdminLogTab === 'system' ? 'errores' : 'actividad'} reciente.</small>`;
    return;
  }

  const header = `
    <div class="log-header-compact">
      <div class="log-col-date">Fecha / Hora</div>
      <div class="log-col-connector">Conector</div>
      <div class="log-col-market">Mercado</div>
      <div class="log-col-symbol">Símbolo</div>
      <div class="log-col-action">Acción</div>
      <div class="log-col-status">Estado</div>
    </div>
  `;

  const rows = filtered.map((item) => {
    const detailId = `admin-log-detail-${item.id}-${item.type}`;
    const symbol = displaySymbol(item.symbol);
    const connector = item.connector_id ? `ID:${item.connector_id}` : '-';
    
    return `
      <div class="log-row-compact" data-log-toggle="${detailId}">
        <div class="log-col-date">${formatDate(item.created_at)}</div>
        <div class="log-col-connector">${escapeHtml(connector)}</div>
        <div class="log-col-market">${escapeHtml(item.market_type || '-')}</div>
        <div class="log-col-symbol"><strong>${escapeHtml(symbol)}</strong></div>
        <div class="log-col-action">${escapeHtml(item.signal || item.side || '-')}</div>
        <div class="log-col-status">
          <span class="pill tiny ${statusPillClass(item.status)}">${escapeHtml(item.status || '-')}</span>
        </div>
      </div>
      <section class="log-details-expanded hidden" id="${detailId}">
        <div class="log-detail-grid">
          <div>
            <strong>Razón / Info</strong>
            <p>${escapeHtml(item.reason || item.status_reason || 'Sin detalles adicionales.')}</p>
          </div>
          <div>
            <strong>Metadatos</strong>
            <pre>${escapeHtml(JSON.stringify(item, null, 2))}</pre>
          </div>
        </div>
      </section>
    `;
  }).join('');

  eventsWrap.innerHTML = header + rows;

  eventsWrap.querySelectorAll('.log-row-compact').forEach((row) => {
    row.addEventListener('click', () => {
      const targetId = row.dataset.logToggle;
      const target = document.getElementById(targetId);
      row.classList.toggle('is-expanded');
      target?.classList.toggle('hidden');
    });
  });
}

function renderAdminOverview() {
  const metricsWrap = document.getElementById('admin-overview-metrics');
  const platformWrap = document.getElementById('admin-platform-health');
  const overview = adminOverviewState || {};
  const metrics = overview.metrics || {};
  if (metricsWrap) {
    metricsWrap.innerHTML = [
      activitySummaryCard('Usuarios activos', `${Number(metrics.users_active || 0)}/${Number(metrics.users_total || 0)}`, 'ok'),
      activitySummaryCard('Conectores live', Number(metrics.connectors_live || 0), 'accent'),
      activitySummaryCard('Bots activos', `${Number(metrics.sessions_active || 0)}/${Number(metrics.sessions_total || 0)}`, 'accent'),
      activitySummaryCard('Sesiones con error', Number(metrics.sessions_with_errors || 0), metrics.sessions_with_errors ? 'danger' : 'ok'),
      activitySummaryCard('Errores recientes', Number(metrics.recent_run_errors || 0), metrics.recent_run_errors ? 'danger' : 'ok'),
      activitySummaryCard('Conectores habilitados', `${Number(metrics.connectors_enabled || 0)}/${Number(metrics.connectors_total || 0)}`, 'neutral'),
    ].join('');
  }
  if (platformWrap) {
    const platformCards = (overview.platforms || []).map((item) => `
      <article class="quantum-report-item">
        <strong>${item.platform.toUpperCase()}</strong>
        <small>Total ${item.total} · habilitados ${item.enabled} · live ${item.live}</small>
      </article>
    `).join('');
    const marketCards = (overview.markets || []).map((item) => `
      <article class="quantum-report-item">
        <strong>${String(item.market_type || '-').toUpperCase()}</strong>
        <small>Total ${item.total} · habilitados ${item.enabled} · live ${item.live}</small>
      </article>
    `).join('');
    const connectorCards = (overview.connectors || []).map((item) => `
      <article class="quantum-report-item">
        <strong>${item.label}</strong>
        <small>${item.platform} · ${item.market_type} · corridas ${item.runs || 0} · trades ${item.trades || 0}</small>
      </article>
    `).join('');
    platformWrap.innerHTML = [platformCards, marketCards, connectorCards].filter(Boolean).join('') || '<small class="hint">Sin plataformas registradas.</small>';
  }
  renderAdminEvents();
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function adminUserHeartbeat() {
  const userId = selectedUserId || Number(document.getElementById('selected-user')?.value || 0);
  if (!userId) return;
  try {
    const result = await api(`/api/admin/users/${userId}/heartbeat`);
    const checks = Array.isArray(result.checks) ? result.checks : [];
    document.getElementById('admin-command-feedback').textContent = checks.length
      ? checks.map((item) => `${item.label}: ${item.ok ? 'ok' : item.message}`).join(' | ')
      : 'Sin conectores activos para heartbeat.';
    document.getElementById('admin-command-feedback').className = `status-msg ${result.ok ? 'status-ok' : 'status-error'}`;
  } catch (error) {
    const node = document.getElementById('admin-command-feedback');
    node.textContent = parseApiError(error);
    node.className = 'status-msg status-error';
  }
}

async function adminKillSwitch() {
  const userId = selectedUserId || Number(document.getElementById('selected-user')?.value || 0);
  if (!userId) return;
  try {
    const result = await api(`/api/admin/users/${userId}/kill-switch`, { method: 'POST' });
    const node = document.getElementById('admin-command-feedback');
    node.textContent = `Kill switch ejecutado. Cerradas: ${(result.closed || []).length} · Fallidas: ${(result.failed || []).length}`;
    node.className = 'status-msg status-ok';
  } catch (error) {
    const node = document.getElementById('admin-command-feedback');
    node.textContent = parseApiError(error);
    node.className = 'status-msg status-error';
  }
}

function renderUserList() {
  const wrap = document.getElementById('admin-users');
  const select = document.getElementById('selected-user');
  document.getElementById('admin-total-users').textContent = String(usersState.length);

  if (select) {
    const fallbackId = selectedUserId && usersState.some((user) => user.id === selectedUserId)
      ? selectedUserId
      : (usersState[0]?.id || null);
    selectedUserId = fallbackId;
    select.innerHTML = usersState.map((user) => `<option value="${user.id}" ${user.id === fallbackId ? 'selected' : ''}>${user.name} · ${user.email}</option>`).join('');
  }

  if (!wrap) return;
  wrap.innerHTML = usersState.map((user) => `
    <button class="admin-user-item fade-in-up ${user.id === selectedUserId ? 'selected' : ''}" type="button" data-user-id="${user.id}">
      <strong>${user.name}</strong>
      <small>${user.email}</small>
      <div class="connector-meta">
        <span>${user.is_admin ? 'Admin' : 'Usuario'}</span>
        <span>${user.is_active ? 'Activo' : 'Inactivo'}</span>
        <span>${formatDate(user.created_at)}</span>
      </div>
    </button>
  `).join('');

  wrap.querySelectorAll('[data-user-id]').forEach((button) => {
    button.addEventListener('click', async () => {
      selectedUserId = Number(button.dataset.userId);
      renderUserList();
      if (select) select.value = String(selectedUserId);
      await refreshSelectedUserProfile();
    });
  });
}

function renderPolicies(policies) {
  const wrap = document.getElementById('admin-policies');
  if (!wrap) return;
  wrap.innerHTML = policies.map((policy) => `
    <form class="policy-form connector-item fade-in-up" data-platform="${policy.platform}">
      <div class="row-between">
        <strong>${policy.display_name}</strong>
        <span class="pill tiny ${policy.is_enabled_global ? 'pill-on' : 'pill-off'}">${policy.is_enabled_global ? 'Global activo' : 'Global bloqueado'}</span>
      </div>
      <div class="form-grid admin-form-grid" style="margin-top:12px;">
        <label>Global habilitado
          <select name="is_enabled_global">
            <option value="true" ${policy.is_enabled_global ? 'selected' : ''}>Sí</option>
            <option value="false" ${!policy.is_enabled_global ? 'selected' : ''}>No</option>
          </select>
        </label>
        <label>Permitir símbolos manuales
          <select name="allow_manual_symbols">
            <option value="true" ${policy.allow_manual_symbols ? 'selected' : ''}>Sí</option>
            <option value="false" ${!policy.allow_manual_symbols ? 'selected' : ''}>No</option>
          </select>
        </label>
        <button class="btn btn-sm primary" type="submit">Guardar política</button>
      </div>
    </form>
  `).join('');

  wrap.querySelectorAll('.policy-form').forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const fd = new FormData(form);
      try {
        await api(`/api/admin/policies/${form.dataset.platform}`, {
          method: 'PUT',
          body: JSON.stringify({
            platform: form.dataset.platform,
            is_enabled_global: fd.get('is_enabled_global') === 'true',
            allow_manual_symbols: fd.get('allow_manual_symbols') === 'true',
          }),
        });
        setFeedback(`Política ${form.dataset.platform} actualizada.`, 'ok');
      } catch (error) {
        setFeedback(parseApiError(error), 'error');
      }
    });
  });
}

function connectorFormMarkup(connector) {
  return `
    <form class="connector-form form-grid admin-compact-grid" data-id="${connector.id}" style="margin-top:12px;">
      <strong style="grid-column:1/-1;">${connector.label} · ${connector.platform}</strong>
      <label>Label<input name="label" value="${connector.label}"></label>
      <label>Modo
        <select name="mode">
          <option value="live" ${connector.mode === 'live' ? 'selected' : ''}>Live</option>
        </select>
      </label>
      <label>Mercado
        <select name="market_type">
          <option value="spot" ${connector.market_type === 'spot' ? 'selected' : ''}>Spot</option>
          <option value="futures" ${connector.market_type === 'futures' ? 'selected' : ''}>Futures</option>
          <option value="forex" ${connector.market_type === 'forex' ? 'selected' : ''}>Forex</option>
          <option value="cfd" ${connector.market_type === 'cfd' ? 'selected' : ''}>CFD</option>
          <option value="signals" ${connector.market_type === 'signals' ? 'selected' : ''}>Signals</option>
        </select>
      </label>
      <label>Estado
        <select name="is_enabled">
          <option value="true" ${connector.is_enabled ? 'selected' : ''}>Activo</option>
          <option value="false" ${!connector.is_enabled ? 'selected' : ''}>Inactivo</option>
        </select>
      </label>
      <label>Símbolos<input name="symbols" value="${(connector.symbols || []).join(', ')}"></label>
      <label>Recv window<input name="recv_window_ms" type="number" value="${connector.config?.recv_window_ms ?? ''}"></label>
      <label>Request timeout<input name="request_timeout_ms" type="number" value="${connector.config?.request_timeout_ms ?? ''}"></label>
      <label>Retries<input name="retry_attempts" type="number" value="${connector.config?.retry_attempts ?? ''}"></label>
      <label>Retry delay<input name="retry_delay_ms" type="number" value="${connector.config?.retry_delay_ms ?? ''}"></label>
      <label>Margin mode<input name="futures_margin_mode" value="${connector.config?.futures_margin_mode ?? ''}"></label>
      <label>Position mode<input name="futures_position_mode" value="${connector.config?.futures_position_mode ?? ''}"></label>
      <label>Leverage<input name="futures_leverage" type="number" value="${connector.config?.futures_leverage ?? ''}"></label>
      <label>Leverage profile<input name="leverage_profile" value="${connector.config?.leverage_profile ?? ''}"></label>
      <div class="row-wrap" style="grid-column:1/-1;">
        <button class="btn btn-sm" type="submit">Guardar conector</button>
        <button class="btn btn-sm" type="button" data-delete-connector="${connector.id}">Eliminar conector</button>
      </div>
    </form>
  `;
}

async function refreshSelectedUserProfile() {
  const selectedId = selectedUserId || Number(document.getElementById('selected-user')?.value || 0);
  const wrap = document.getElementById('selected-user-profile');
  if (!selectedId || !wrap) return;
  try {
    const profile = await api(`/api/admin/users/${selectedId}/profile`);
    selectedUserId = Number(selectedId);
    document.getElementById('admin-selected-user-state').textContent = `${profile.user.name} · ${profile.user.email}`;
    wrap.innerHTML = `
      <article class="connector-item fade-in-up">
        <div class="row-between">
          <div>
            <strong>${profile.user.name}</strong>
            <div class="connector-meta">
              <span>${profile.user.email}</span>
              <span>${profile.user.phone || 'Sin teléfono'}</span>
              <span>${profile.user.is_admin ? 'Admin' : 'Usuario'}</span>
              <span>${profile.user.is_active ? 'Activo' : 'Inactivo'}</span>
            </div>
          </div>
          ${!profile.user.is_root ? '<button class="btn btn-sm" type="button" id="delete-user-btn">Eliminar usuario</button>' : ''}
        </div>
      </article>

      <form id="user-meta-form" class="connector-item fade-in-up form-grid admin-compact-grid">
        <strong style="grid-column:1/-1;">Estado de usuario</strong>
        <label>Nombre<input name="name" value="${profile.user.name || ''}"></label>
        <label>Email<input name="email" type="email" value="${profile.user.email || ''}"></label>
        <label>Teléfono<input name="phone" value="${profile.user.phone || ''}"></label>
        <label>Activo
          <select name="is_active"><option value="true" ${profile.user.is_active ? 'selected' : ''}>Sí</option><option value="false" ${!profile.user.is_active ? 'selected' : ''}>No</option></select>
        </label>
        <label>Administrador
          <select name="is_admin"><option value="true" ${profile.user.is_admin ? 'selected' : ''}>Sí</option><option value="false" ${!profile.user.is_admin ? 'selected' : ''}>No</option></select>
        </label>
        <label class="checkbox"><input name="telegram_alerts_enabled" type="checkbox" ${profile.user.telegram_alerts_enabled ? 'checked' : ''}> Telegram habilitado</label>
        <label>Telegram bot key<input name="telegram_bot_key" value="${profile.user.telegram_bot_key || ''}"></label>
        <label>Telegram chat id<input name="telegram_chat_id" value="${profile.user.telegram_chat_id || ''}"></label>
        <button class="btn btn-sm primary" type="submit">Guardar usuario</button>
      </form>

      <div class="connector-item fade-in-up">
        <strong>Telegram y diagnóstico rápido</strong>
        <div class="admin-section-grid" style="margin-top:12px;">
          <article class="admin-mini-card">
            <strong>Telegram</strong>
            <small>${profile.telegram?.alerts_enabled ? 'Alertas activas' : 'Alertas inactivas'}</small>
            <small>Bot: ${profile.telegram?.bot_key || 'Sin configurar'}</small>
            <small>Chat: ${profile.telegram?.chat_id || 'Sin configurar'}</small>
          </article>
          <article class="admin-mini-card">
            <strong>Diagnóstico</strong>
            <small>Conectores: ${(profile.connectors || []).length}</small>
            <small>Sesiones: ${(profile.recent_sessions || []).length}</small>
            <small>Logs recientes: ${(profile.recent_runs || []).length}</small>
          </article>
        </div>
      </div>

      <div class="connector-item fade-in-up">
        <strong>Conectores del usuario</strong>
        ${(profile.connectors || []).map(connectorFormMarkup).join('') || '<small class="hint">Este usuario no tiene conectores.</small>'}
      </div>

      <div class="connector-item fade-in-up">
        <strong>Grants por plataforma</strong>
        ${(profile.policies || []).map((policy) => {
          const grant = (profile.grants || []).find((g) => g.platform === policy.platform) || { is_enabled: false, max_symbols: 0, max_daily_movements: 0, notes: '' };
          return `
            <form class="grant-form form-grid admin-compact-grid" data-platform="${policy.platform}" style="margin-top:12px;">
              <strong style="grid-column:1/-1;">${policy.display_name}</strong>
              <label>Habilitado
                <select name="is_enabled"><option value="true" ${grant.is_enabled ? 'selected' : ''}>Sí</option><option value="false" ${!grant.is_enabled ? 'selected' : ''}>No</option></select>
              </label>
              <label>Máx. símbolos<input name="max_symbols" type="number" value="${grant.max_symbols}"></label>
              <label>Máx. movimientos<input name="max_daily_movements" type="number" value="${grant.max_daily_movements}"></label>
              <label>Notas<input name="notes" value="${grant.notes || ''}"></label>
              <button class="btn btn-sm" type="submit">Guardar grant</button>
            </form>
          `;
        }).join('')}
      </div>

      <div class="connector-item fade-in-up">
        <strong>Errores, sesiones y reportes recientes</strong>
        <div class="admin-section-grid" style="margin-top:12px;">
          ${(profile.recent_sessions || []).map((session) => `
            <article class="admin-mini-card">
              <strong>${session.display_name || session.session_name || session.strategy_slug}</strong>
              <small>${session.connector_label} · ${session.market_type}</small>
              <small>${session.is_active ? 'Activa' : 'Pausada'} · ${session.last_status || '-'}</small>
              <small>${session.last_error || 'Sin error reportado'}</small>
            </article>
          `).join('') || '<small class="hint">Sin sesiones recientes.</small>'}
          ${(profile.recent_runs || []).map((run) => `
            <article class="admin-mini-card">
              <strong>${run.display_symbol || run.symbol}</strong>
              <small>${run.connector_label}</small>
              <small>${run.status}</small>
              <small>${run.reason}</small>
            </article>
          `).join('') || '<small class="hint">Sin logs recientes.</small>'}
        </div>
      </div>

      <form id="strategy-control-form" class="connector-item fade-in-up form-grid">
        <strong>Estrategias permitidas</strong>
        <label>Gestionado por admin
          <select name="managed_by_admin"><option value="true" ${profile.strategy_control.managed_by_admin ? 'selected' : ''}>Sí</option><option value="false" ${!profile.strategy_control.managed_by_admin ? 'selected' : ''}>No</option></select>
        </label>
        <label>Estrategias
          <select name="allowed_strategies" multiple size="8">
            ${(profile.strategy_control.all_strategies || []).map((slug) => `<option value="${slug}" ${(profile.strategy_control.allowed_strategies || []).includes(slug) ? 'selected' : ''}>${slug}</option>`).join('')}
          </select>
        </label>
        <button class="btn btn-sm primary" type="submit">Guardar estrategias</button>
      </form>
    `;

    wrap.querySelector('#user-meta-form')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const fd = new FormData(event.currentTarget);
      try {
        await api(`/api/admin/users/${selectedId}`, {
          method: 'PUT',
          body: JSON.stringify({
            name: fd.get('name'),
            email: fd.get('email'),
            phone: fd.get('phone'),
            is_active: fd.get('is_active') === 'true',
            is_admin: fd.get('is_admin') === 'true',
          }),
        });
        setFeedback('Usuario actualizado.', 'ok');
        await refreshAdmin();
      } catch (error) {
        setFeedback(parseApiError(error), 'error');
      }
    });

    wrap.querySelectorAll('.connector-form').forEach((form) => {
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const fd = new FormData(form);
        try {
          await api(`/api/connectors/${form.dataset.id}`, {
            method: 'PUT',
            body: JSON.stringify({
              label: fd.get('label'),
              mode: fd.get('mode'),
              market_type: fd.get('market_type'),
              is_enabled: fd.get('is_enabled') === 'true',
              symbols: String(fd.get('symbols') || '').split(',').map((x) => x.trim()).filter(Boolean),
              config: {
                recv_window_ms: fd.get('recv_window_ms') ? Number(fd.get('recv_window_ms')) : null,
                request_timeout_ms: fd.get('request_timeout_ms') ? Number(fd.get('request_timeout_ms')) : null,
                retry_attempts: fd.get('retry_attempts') ? Number(fd.get('retry_attempts')) : null,
                retry_delay_ms: fd.get('retry_delay_ms') ? Number(fd.get('retry_delay_ms')) : null,
                futures_margin_mode: fd.get('futures_margin_mode') || null,
                futures_position_mode: fd.get('futures_position_mode') || null,
                futures_leverage: fd.get('futures_leverage') ? Number(fd.get('futures_leverage')) : null,
                leverage_profile: fd.get('leverage_profile') || null,
              },
            }),
          });
          setFeedback('Conector actualizado.', 'ok');
          await refreshSelectedUserProfile();
        } catch (error) {
          setFeedback(parseApiError(error), 'error');
        }
      });
    });

    wrap.querySelectorAll('[data-delete-connector]').forEach((button) => {
      button.addEventListener('click', async () => {
        try {
          await api(`/api/connectors/${button.dataset.deleteConnector}`, { method: 'DELETE' });
          setFeedback('Conector eliminado.', 'ok');
          await refreshSelectedUserProfile();
        } catch (error) {
          setFeedback(parseApiError(error), 'error');
        }
      });
    });

    wrap.querySelectorAll('.grant-form').forEach((form) => {
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const fd = new FormData(form);
        try {
          await api('/api/admin/grants', {
            method: 'PUT',
            body: JSON.stringify({
              user_id: Number(selectedId),
              platform: form.dataset.platform,
              is_enabled: fd.get('is_enabled') === 'true',
              max_symbols: Number(fd.get('max_symbols') || 0),
              max_daily_movements: Number(fd.get('max_daily_movements') || 0),
              notes: fd.get('notes') || '',
            }),
          });
          setFeedback('Grant actualizado.', 'ok');
        } catch (error) {
          setFeedback(parseApiError(error), 'error');
        }
      });
    });

    wrap.querySelector('#strategy-control-form')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const fd = new FormData(form);
      const selected = Array.from(form.querySelector('select[name="allowed_strategies"]').selectedOptions).map((option) => option.value);
      try {
        await api(`/api/admin/users/${selectedId}/strategy-control`, {
          method: 'PUT',
          body: JSON.stringify({
            managed_by_admin: fd.get('managed_by_admin') === 'true',
            allowed_strategies: selected,
          }),
        });
        setFeedback('Control de estrategias actualizado.', 'ok');
      } catch (error) {
        setFeedback(parseApiError(error), 'error');
      }
    });

    wrap.querySelector('#delete-user-btn')?.addEventListener('click', async () => {
      try {
        await api(`/api/admin/users/${selectedId}`, { method: 'DELETE' });
        setFeedback('Usuario eliminado.', 'ok');
        selectedUserId = null;
        await refreshAdmin();
      } catch (error) {
        setFeedback(parseApiError(error), 'error');
      }
    });
  } catch (error) {
    wrap.innerHTML = `<div class="status-msg status-error">${parseApiError(error)}</div>`;
  }
}

async function loadAdminOverview() {
  try {
    return await api('/api/admin/overview');
  } catch (error) {
    const detail = parseApiError(error);
    if (!/not found/i.test(detail)) throw error;
    return api('/api/admin/overview/');
  }
}

async function refreshAdmin() {
  const settled = await Promise.allSettled([
    api('/api/admin/users'),
    api('/api/admin/policies'),
    loadAdminOverview(),
  ]);
  const labels = ['usuarios', 'políticas', 'overview'];
  const failures = [];
  const values = settled.map((result, index) => {
    if (result.status === 'fulfilled') return result.value;
    failures.push(`${labels[index]}: ${parseApiError(result.reason)}`);
    return null;
  });
  const [users, policies, overview] = values;
  usersState = Array.isArray(users) ? users : [];
  adminOverviewState = overview || adminOverviewState || {
    metrics: {
      users_total: usersState.length,
      users_active: usersState.filter((user) => user.is_active).length,
      connectors_total: 0,
      connectors_enabled: 0,
      connectors_live: 0,
      sessions_total: 0,
      sessions_active: 0,
      sessions_with_errors: 0,
      recent_run_errors: 0,
    },
    platforms: [],
    markets: [],
    connectors: [],
    events: [],
    trade_logs: [],
  };
  renderUserList();
  renderPolicies(Array.isArray(policies) ? policies : []);
  renderAdminOverview();
  if (usersState.length) {
    await refreshSelectedUserProfile();
  } else {
    document.getElementById('selected-user-profile').innerHTML = '<small class="hint">No hay usuarios disponibles.</small>';
  }
  if (failures.length) {
    setFeedback(`Panel cargado parcialmente: ${failures.join(' | ')}`, 'error');
  } else {
    setFeedback('Panel administrativo actualizado.', 'ok');
  }
}

async function createUser(event) {
  event.preventDefault();
  const fd = new FormData(event.currentTarget);
  try {
    await api('/api/admin/users', {
      method: 'POST',
      body: JSON.stringify({
        email: fd.get('email'),
        name: fd.get('name'),
        password: fd.get('password'),
      }),
    });
    event.currentTarget.reset();
    setFeedback('Usuario creado correctamente.', 'ok');
    await refreshAdmin();
  } catch (error) {
    setFeedback(parseApiError(error), 'error');
  }
}

async function init() {
  document.getElementById('create-user-form')?.addEventListener('submit', createUser);
  document.getElementById('admin-refresh-overview-btn')?.addEventListener('click', refreshAdmin);
  document.getElementById('admin-heartbeat-btn')?.addEventListener('click', adminUserHeartbeat);
  document.getElementById('admin-kill-switch-btn')?.addEventListener('click', adminKillSwitch);
  document.getElementById('selected-user')?.addEventListener('change', async (event) => {
    selectedUserId = Number(event.currentTarget.value || 0);
    renderUserList();
    await refreshSelectedUserProfile();
  });

  document.getElementById('admin-logs-tabs')?.addEventListener('click', (e) => {
    const pill = e.target.closest('.admin-log-tab-pill');
    if (!pill) return;
    currentAdminLogTab = pill.dataset.tab;
    document.querySelectorAll('#admin-logs-tabs .admin-log-tab-pill').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    renderAdminEvents();
  });

  await refreshAdmin();
}

init().catch((error) => setFeedback(parseApiError(error), 'error'));
