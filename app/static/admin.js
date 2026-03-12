async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
      <div class="connector-meta"><span>${u.email}</span><span>id: ${u.id}</span><span>admin: ${u.is_admin}</span><span>active: ${u.is_active}</span></div>
      <div class="row-wrap">
        <button class="btn" onclick="toggleUser(${u.id}, ${!u.is_active}, null)">${u.is_active ? 'Desactivar' : 'Activar'}</button>
        <button class="btn" onclick="toggleUser(${u.id}, null, ${!u.is_admin})">${u.is_admin ? 'Quitar admin' : 'Hacer admin'}</button>
      </div>
    </div>
  `).join("");

  document.getElementById("admin-policies").innerHTML = policies.map(p => `
    <div class="connector-item">
      <strong>${p.display_name}</strong>
      <div class="connector-meta"><span>${p.platform}</span><span>global: ${p.is_enabled_global}</span><span>manual: ${p.allow_manual_symbols}</span></div>
      <div class="row-wrap">
        <button class="btn" onclick='togglePolicy(${JSON.stringify(p.platform)}, ${!p.is_enabled_global}, null)'>${p.is_enabled_global ? 'Deshabilitar global' : 'Habilitar global'}</button>
        <button class="btn" onclick='togglePolicy(${JSON.stringify(p.platform)}, null, ${!p.allow_manual_symbols})'>Manual ${p.allow_manual_symbols ? 'OFF' : 'ON'}</button>
      </div>
      <small class="hint">Top 10: ${(p.top_symbols || []).join(", ")}</small>
      <small class="hint">Permitidos: ${(p.allowed_symbols || []).join(", ")}</small>
    </div>
  `).join("");

  document.getElementById("grant-output").textContent = JSON.stringify(grants, null, 2);
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
  refreshAdmin();
});

document.getElementById('create-user-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  await api('/api/admin/users', {
    method: 'POST',
    body: JSON.stringify({
      email: String(fd.get('email') || '').trim(),
      name: String(fd.get('name') || '').trim(),
      password: String(fd.get('password') || ''),
    })
  });
  e.target.reset();
  refreshAdmin();
});

refreshAdmin().catch(err => {
  document.getElementById('grant-output').textContent = err.message;
});
