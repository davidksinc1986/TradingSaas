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

function renderUserList() {
  const wrap = document.getElementById('admin-users');
  const select = document.getElementById('selected-user');
  document.getElementById('admin-total-users').textContent = String(usersState.length);
  if (wrap) {
    wrap.innerHTML = usersState.map((user) => `
      <article class="connector-item fade-in-up">
        <div class="row-between">
          <div>
            <strong>${user.name}</strong>
            <div class="connector-meta">
              <span>${user.email}</span>
              <span>${user.is_admin ? 'Admin' : 'Usuario'}</span>
              <span>${user.is_active ? 'Activo' : 'Inactivo'}</span>
            </div>
          </div>
        </div>
      </article>
    `).join('');
  }
  if (select) {
    const previous = select.value;
    select.innerHTML = usersState.map((user) => `<option value="${user.id}">${user.name} · ${user.email}</option>`).join('');
    if (previous && usersState.some((user) => String(user.id) === previous)) select.value = previous;
  }
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
        <label>Top symbols<input name="top_symbols" value="${(policy.top_symbols || []).join(', ')}"></label>
        <label>Allowed symbols<input name="allowed_symbols" value="${(policy.allowed_symbols || []).join(', ')}"></label>
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
            top_symbols: String(fd.get('top_symbols') || '').split(',').map((x) => x.trim()).filter(Boolean),
            allowed_symbols: String(fd.get('allowed_symbols') || '').split(',').map((x) => x.trim()).filter(Boolean),
          }),
        });
        setFeedback(`Política ${form.dataset.platform} actualizada.`, 'ok');
      } catch (error) {
        setFeedback(parseApiError(error), 'error');
      }
    });
  });
}

async function refreshSelectedUserProfile() {
  const selectedId = document.getElementById('selected-user')?.value;
  const wrap = document.getElementById('selected-user-profile');
  if (!selectedId || !wrap) return;
  try {
    const profile = await api(`/api/admin/users/${selectedId}/profile`);
    document.getElementById('admin-selected-user-state').textContent = `${profile.user.name} · ${profile.user.email}`;
    wrap.innerHTML = `
      <article class="connector-item fade-in-up">
        <div class="row-between">
          <div>
            <strong>${profile.user.name}</strong>
            <div class="connector-meta">
              <span>${profile.user.email}</span>
              <span>${profile.user.is_admin ? 'Admin' : 'Usuario'}</span>
              <span>${profile.user.is_active ? 'Activo' : 'Inactivo'}</span>
            </div>
          </div>
        </div>
      </article>

      <form id="user-meta-form" class="connector-item fade-in-up form-grid">
        <strong>Estado de usuario</strong>
        <label>Activo
          <select name="is_active"><option value="true" ${profile.user.is_active ? 'selected' : ''}>Sí</option><option value="false" ${!profile.user.is_active ? 'selected' : ''}>No</option></select>
        </label>
        <label>Administrador
          <select name="is_admin"><option value="true" ${profile.user.is_admin ? 'selected' : ''}>Sí</option><option value="false" ${!profile.user.is_admin ? 'selected' : ''}>No</option></select>
        </label>
        <button class="btn btn-sm primary" type="submit">Guardar usuario</button>
      </form>

      <div class="connector-item fade-in-up">
        <strong>Conectores del usuario</strong>
        ${(profile.connectors || []).map((connector) => `
          <form class="connector-form form-grid" data-id="${connector.id}" style="margin-top:12px;">
            <label>Label<input name="label" value="${connector.label}"></label>
            <label>Modo<input name="mode" value="${connector.mode}"></label>
            <label>Mercado<input name="market_type" value="${connector.market_type}"></label>
            <label>Símbolos<input name="symbols" value="${(connector.symbols || []).join(', ')}"></label>
            <label>Allocation mode<input name="allocation_mode" value="${connector.allocation_mode || 'fixed'}"></label>
            <label>Allocation value<input name="allocation_value" type="number" step="0.01" value="${connector.allocation_value || 0}"></label>
            <button class="btn btn-sm" type="submit">Guardar conector</button>
          </form>
        `).join('') || '<small class="hint">Este usuario no tiene conectores.</small>'}
      </div>

      <div class="connector-item fade-in-up">
        <strong>Grants por plataforma</strong>
        ${(profile.policies || []).map((policy) => {
          const grant = (profile.grants || []).find((g) => g.platform === policy.platform) || { is_enabled: false, max_symbols: 0, max_daily_movements: 0, notes: '' };
          return `
            <form class="grant-form form-grid" data-platform="${policy.platform}" style="margin-top:12px;">
              <strong>${policy.display_name}</strong>
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

      <form id="strategy-control-form" class="connector-item fade-in-up form-grid">
        <strong>Estrategias permitidas</strong>
        <label>Gestionado por admin
          <select name="managed_by_admin"><option value="true" ${profile.strategy_control.managed_by_admin ? 'selected' : ''}>Sí</option><option value="false" ${!profile.strategy_control.managed_by_admin ? 'selected' : ''}>No</option></select>
        </label>
        <label>Estrategias
          <select name="allowed_strategies" multiple size="6">
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
              symbols: String(fd.get('symbols') || '').split(',').map((x) => x.trim()).filter(Boolean),
              config: {
                allocation_mode: fd.get('allocation_mode'),
                allocation_value: Number(fd.get('allocation_value') || 0),
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
  } catch (error) {
    wrap.innerHTML = `<div class="status-msg status-error">${parseApiError(error)}</div>`;
  }
}

async function refreshAdmin() {
  const [users, policies] = await Promise.all([
    api('/api/admin/users'),
    api('/api/admin/policies'),
  ]);
  usersState = Array.isArray(users) ? users : [];
  renderUserList();
  renderPolicies(Array.isArray(policies) ? policies : []);
  await refreshSelectedUserProfile();
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
  document.getElementById('selected-user')?.addEventListener('change', refreshSelectedUserProfile);
  await refreshAdmin();
}

init().catch((error) => setFeedback(parseApiError(error), 'error'));
