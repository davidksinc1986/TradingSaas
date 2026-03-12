async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function showFeedback(message, kind = "ok") {
  const el = document.getElementById("admin-feedback");
  if (!el) return;
  el.classList.remove("hidden", "status-ok", "status-error");
  el.classList.add(kind === "ok" ? "status-ok" : "status-error");
  el.textContent = message;
}

function symbolsToChips(symbols = []) {
  return symbols.map((symbol) => `<span class="chip chip-static">${symbol}</span>`).join("");
}

async function refreshAdmin() {
  const [users, policies, grants] = await Promise.all([
    api("/api/admin/users"),
    api("/api/admin/policies"),
    api("/api/admin/grants"),
  ]);

  document.getElementById("admin-users").innerHTML = users.map(u => `
    <div class="connector-item">
      <strong>${u.name}</strong>
      <div class="connector-meta"><span>${u.email}</span><span>ID: ${u.id}</span><span>Admin: ${u.is_admin ? "Sí" : "No"}</span><span>Activo: ${u.is_active ? "Sí" : "No"}</span></div>
      <div class="row-wrap">
        <button class="btn" onclick="toggleUser(${u.id}, ${!u.is_active}, null)">${u.is_active ? 'Desactivar' : 'Activar'}</button>
        <button class="btn" onclick="toggleUser(${u.id}, null, ${!u.is_admin})">${u.is_admin ? 'Quitar admin' : 'Hacer admin'}</button>
      </div>
    </div>
  `).join("");

  document.getElementById("admin-policies").innerHTML = policies.map(p => {
    const globalBadge = p.is_enabled_global ? "Global: Activado" : "Global: Desactivado";
    const manualBadge = p.allow_manual_symbols ? "Carga manual: Permitida" : "Carga manual: Bloqueada";
    return `
      <div class="connector-item">
        <div class="row-between">
          <strong>${p.display_name}</strong>
          <div class="row-wrap">
            <span class="pill tiny ${p.is_enabled_global ? "pill-on" : "pill-off"}">${globalBadge}</span>
            <span class="pill tiny ${p.allow_manual_symbols ? "pill-on" : "pill-off"}">${manualBadge}</span>
          </div>
        </div>
        <div class="row-wrap" style="margin-top:8px;">
          <button class="btn" onclick='togglePolicy(${JSON.stringify(p.platform)}, ${!p.is_enabled_global}, null)'>${p.is_enabled_global ? 'Desactivar acceso global' : 'Activar acceso global'}</button>
          <button class="btn" onclick='togglePolicy(${JSON.stringify(p.platform)}, null, ${!p.allow_manual_symbols})'>${p.allow_manual_symbols ? 'Bloquear símbolos manuales' : 'Permitir símbolos manuales'}</button>
        </div>
        <div class="symbol-block">
          <small class="hint"><strong>Símbolos sugeridos</strong></small>
          <div class="chip-wrap">${symbolsToChips(p.top_symbols || [])}</div>
        </div>
        <div class="symbol-block">
          <small class="hint"><strong>Símbolos permitidos por política</strong></small>
          <div class="chip-wrap">${symbolsToChips(p.allowed_symbols || [])}</div>
        </div>
      </div>
    `;
  }).join("");

  const grantsByUser = grants.reduce((acc, grant) => {
    if (!acc[grant.user_id]) acc[grant.user_id] = [];
    acc[grant.user_id].push(grant);
    return acc;
  }, {});

  document.getElementById("grant-output").innerHTML = Object.entries(grantsByUser).map(([userId, entries]) => `
    <div class="connector-item">
      <strong>Usuario ID ${userId}</strong>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Plataforma</th><th>Estado</th><th>Máx. símbolos</th><th>Máx. movimientos</th><th>Notas</th></tr>
          </thead>
          <tbody>
            ${entries.map(grant => `<tr><td>${grant.platform}</td><td>${grant.is_enabled ? "Habilitado" : "Deshabilitado"}</td><td>${grant.max_symbols}</td><td>${grant.max_daily_movements}</td><td>${grant.notes || "-"}</td></tr>`).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `).join("");
}

async function toggleUser(id, is_active, is_admin) {
  await api(`/api/admin/users/${id}`, { method: 'PUT', body: JSON.stringify({ is_active, is_admin }) });
  refreshAdmin();
}

async function togglePolicy(platform, is_enabled_global, allow_manual_symbols) {
  await api(`/api/admin/policies/${platform}`, { method: 'PUT', body: JSON.stringify({ platform, is_enabled_global, allow_manual_symbols }) });
  refreshAdmin();
}

document.getElementById('grant-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  await api('/api/admin/grants', {
    method: 'PUT',
    body: JSON.stringify({
      user_id: Number(fd.get('user_id')),
      platform: fd.get('platform'),
      is_enabled: fd.get('is_enabled') === 'true',
      max_symbols: Number(fd.get('max_symbols')),
      max_daily_movements: Number(fd.get('max_daily_movements')),
      notes: fd.get('notes'),
    })
  });
  showFeedback("Límites actualizados correctamente.");
  refreshAdmin();
});

document.getElementById('create-user-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    const fd = new FormData(e.target);
    const password = String(fd.get('password') || '');
    if (password.length < 6) {
      showFeedback("La contraseña debe tener al menos 6 caracteres.", "error");
      return;
    }

    await api('/api/admin/users', {
      method: 'POST',
      body: JSON.stringify({
        email: String(fd.get('email') || '').trim(),
        name: String(fd.get('name') || '').trim(),
        password,
      })
    });
    showFeedback("Usuario creado exitosamente.");
    e.target.reset();
    refreshAdmin();
  } catch (err) {
    showFeedback(`No se pudo crear el usuario: ${err.message}`, "error");
  }
});

refreshAdmin().catch(err => {
  const output = document.getElementById('grant-output');
  if (output) output.innerHTML = `<div class="status-msg status-error">${err.message}</div>`;
});
