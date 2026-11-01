/* =====================================================================
   admin.js - logic for templates/admin.html
   - shows system statistics
   - lists every user account
   - lets the admin create users, change roles and delete accounts
   ===================================================================== */

onReady(() => {
  loadStats();
  loadUsers();
  document.getElementById("user-form").addEventListener("submit", createUser);
});

/* ---------------------------------------------------------------------
   loadStats() - GET /api/stats -> cards + per-status breakdown
   --------------------------------------------------------------------- */
async function loadStats() {
  try {
    const { stats } = await api("/api/stats");
    const s = stats;

    document.getElementById("admin-stats").innerHTML = `
      <div class="card stat-card"><div class="label">Total orders</div><div class="value">${s.total_shipments}</div></div>
      <div class="card stat-card"><div class="label">Active shipments</div><div class="value">${s.active_shipments}</div></div>
      <div class="card stat-card"><div class="label">Delivered</div><div class="value">${s.delivered_shipments}</div></div>
      <div class="card stat-card"><div class="label">Cancelled</div><div class="value">${s.cancelled_shipments}</div></div>
      <div class="card stat-card"><div class="label">Users</div><div class="value">${s.total_users}</div></div>
    `;

    /* Simple horizontal bars for "shipments per status".
       The bar width = share of the total number of shipments. */
    const total = Math.max(s.total_shipments, 1);   // avoid divide-by-zero
    const rows = Object.entries(s.per_status).map(([status, count]) => {
      const width = Math.round((count / total) * 100);
      return `
        <div style="margin-bottom:10px">
          <div style="display:flex; justify-content:space-between; font-size:13px; margin-bottom:4px">
            <span>${escapeHtml(status)}</span><strong>${count}</strong>
          </div>
          <div style="height:8px; background:#eef1f7; border-radius:99px; overflow:hidden">
            <div style="height:100%; width:${width}%; background:#2f6fed; border-radius:99px"></div>
          </div>
        </div>`;
    }).join("");

    document.getElementById("status-breakdown").innerHTML = rows;

    /* Users per role, shown as small chips. */
    const roleChips = Object.entries(s.per_role)
      .map(([role, count]) => `<span class="user-chip" style="margin:4px 6px 0 0">
          ${escapeHtml(role)}: <strong>${count}</strong></span>`)
      .join("");
    document.getElementById("status-breakdown").innerHTML +=
      `<div class="spacer"></div><div style="font-size:13px" class="muted">Users per role</div>${roleChips}`;
  } catch (err) {
    toast(err.message, "error");
  }
}

/* ---------------------------------------------------------------------
   loadUsers() - GET /api/users -> the accounts table
   --------------------------------------------------------------------- */
async function loadUsers() {
  const tbody = document.getElementById("users-body");

  try {
    const data = await api("/api/users");

    tbody.innerHTML = data.users.map((u) => {
      // A dropdown to change the role + a delete button for each user.
      const roleOptions = ["customer", "warehouse", "driver", "admin"]
        .map(r => `<option value="${r}" ${r === u.role ? "selected" : ""}>${r}</option>`)
        .join("");

      return `
        <tr>
          <td class="muted">${u.id}</td>
          <td>${escapeHtml(u.name)}</td>
          <td>${escapeHtml(u.email)}</td>
          <td><span class="badge" data-status="In Transit" style="background:#eef2fd;color:#2f6fed">
              ${escapeHtml(u.role)}</span></td>
          <td class="muted" style="font-size:12.5px">${shortDate(u.created_at)}</td>
          <td>
            <div class="row-actions">
              <select id="role-${u.id}" style="padding:4px 6px; font-size:12.5px; width:auto">
                ${roleOptions}
              </select>
              <button class="btn btn-outline btn-sm" onclick="changeRole(${u.id})">Save role</button>
              <button class="btn btn-danger btn-sm" onclick="deleteUser(${u.id})">Delete</button>
            </div>
          </td>
        </tr>`;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty">${escapeHtml(err.message)}</td></tr>`;
    toast(err.message, "error");
  }
}

/* ---------------------------------------------------------------------
   createUser(event) - POST /api/users
   --------------------------------------------------------------------- */
async function createUser(event) {
  event.preventDefault();
  const form = event.target;
  const payload = Object.fromEntries(new FormData(form).entries());

  try {
    const data = await api("/api/users", { method: "POST", body: payload });
    toast(data.message, "success");
    form.reset();
    document.getElementById("u-password").value = "password123";
    // reload stats so the "users per role" chips update too
    Promise.all([loadUsers(), loadStats()]);
  } catch (err) {
    toast(err.message, "error");
  }
}

/* ---------------------------------------------------------------------
   changeRole(userId) - POST /api/users/<id>/role
   --------------------------------------------------------------------- */
async function changeRole(userId) {
  const role = document.getElementById(`role-${userId}`).value;
  try {
    const data = await api(`/api/users/${userId}/role`, {
      method: "POST",
      body: { role: role },
    });
    toast(data.message, "success");
    Promise.all([loadUsers(), loadStats()]);
  } catch (err) {
    toast(err.message, "error");
  }
}

/* ---------------------------------------------------------------------
   deleteUser(userId) - DELETE /api/users/<id>
   --------------------------------------------------------------------- */
async function deleteUser(userId) {
  if (!confirm("Delete this user account? This cannot be undone.")) return;
  try {
    const data = await api(`/api/users/${userId}`, { method: "DELETE" });
    toast(data.message, "success");
    Promise.all([loadUsers(), loadStats()]);
  } catch (err) {
    toast(err.message, "error");
  }
}
