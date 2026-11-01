/* =====================================================================
   driver.js - logic for templates/driver.html
   Drivers only see shipments assigned to them (the backend enforces this).
   Each row offers the next allowed status as a button.
   ===================================================================== */

onReady(() => {
  loadTasks();
});

/* ---------------------------------------------------------------------
   loadTasks() - GET /api/shipments (already filtered to this driver)
   --------------------------------------------------------------------- */
async function loadTasks() {
  const tbody = document.getElementById("drv-body");

  try {
    const data = await api("/api/shipments");
    const tasks = data.shipments;

    /* ---- summary cards ---------------------------------------------- */
    const outForDelivery = tasks.filter(t => t.status === "Out for Delivery").length;
    const delivered = tasks.filter(t => t.status === "Delivered").length;
    const active = tasks.filter(t => !["Delivered", "Cancelled"].includes(t.status)).length;

    document.getElementById("drv-stats").innerHTML = `
      <div class="card stat-card"><div class="label">Assigned</div><div class="value">${tasks.length}</div></div>
      <div class="card stat-card"><div class="label">In progress</div><div class="value">${active}</div></div>
      <div class="card stat-card"><div class="label">Out for delivery</div><div class="value">${outForDelivery}</div></div>
      <div class="card stat-card"><div class="label">Delivered</div><div class="value">${delivered}</div></div>
    `;

    /* ---- table ------------------------------------------------------- */
    if (tasks.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty">
        Nothing assigned to you right now. Ask the warehouse to assign a shipment.
      </td></tr>`;
      return;
    }

    tbody.innerHTML = tasks.map((t) => {
      // `next_statuses` is calculated by the backend for this user's role.
      const buttons = t.next_statuses.map((st) => `
        <button class="btn btn-sm ${st === "Delivered" ? "btn-green" : "btn-outline"}"
                onclick="updateStatus(${t.id}, '${escapeHtml(st)}')">
          Mark ${escapeHtml(st)}
        </button>`).join(" ");

      return `
        <tr>
          <td class="mono">${escapeHtml(t.tracking_number)}</td>
          <td>${escapeHtml(t.receiver_name)}</td>
          <td><a href="tel:${escapeHtml(t.receiver_phone)}">${escapeHtml(t.receiver_phone)}</a></td>
          <td>${escapeHtml(t.receiver_address)}
              <div class="muted" style="font-size:12px">${escapeHtml(t.description || "")}</div></td>
          <td>${statusBadge(t.status)}</td>
          <td><div class="row-actions">${buttons || '<span class="muted">completed</span>'}</div></td>
        </tr>`;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty">${escapeHtml(err.message)}</td></tr>`;
    toast(err.message, "error");
  }
}

/* ---------------------------------------------------------------------
   updateStatus(shipmentId, newStatus)
   POST /api/shipments/<id>/status with an optional note.
   The backend checks that this driver owns the shipment and that the
   status change is a legal step in the workflow.
   --------------------------------------------------------------------- */
async function updateStatus(shipmentId, newStatus) {
  // Ask for an optional note (e.g. "Left with the receptionist").
  const note = prompt(`Add a note for "${newStatus}" (optional):`, "") || "";

  try {
    const data = await api(`/api/shipments/${shipmentId}/status`, {
      method: "POST",
      body: { status: newStatus, note: note },
    });
    toast(data.message, "success");
    loadTasks();
  } catch (err) {
    toast(err.message, "error");
  }
}
