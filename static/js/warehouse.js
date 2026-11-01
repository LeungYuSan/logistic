/* =====================================================================
   warehouse.js - logic for templates/warehouse.html
   What it does:
     1. loads every shipment and shows it in a table
     2. "Receive" -> status "Warehouse Received" + shelf location
     3. "Dispatch" -> status "In Transit"
     4. "Assign"  -> attaches a driver to the shipment
     5. simple client-side filtering by status / text search
   ===================================================================== */

let allShipments = [];      // last data we received (used by the filters)
let drivers = [];           // list of driver accounts (for the dropdown)

onReady(async () => {
  await Promise.all([loadDrivers(), loadStats()]);
  loadShipments();

  // re-filter the table whenever the filter inputs change
  document.getElementById("status-filter").addEventListener("change", renderTable);
  document.getElementById("search").addEventListener("input", renderTable);
});

/* ---------------------------------------------------------------------
   loadShipments() - GET /api/shipments and keep the result in memory
   --------------------------------------------------------------------- */
async function loadShipments() {
  try {
    const data = await api("/api/shipments");
    allShipments = data.shipments;
    renderTable();
  } catch (err) {
    document.getElementById("wh-body").innerHTML =
      `<tr><td colspan="8" class="empty">${escapeHtml(err.message)}</td></tr>`;
    toast(err.message, "error");
  }
}

/* ---------------------------------------------------------------------
   loadDrivers() - GET /api/drivers (for the "assign driver" dropdown)
   --------------------------------------------------------------------- */
async function loadDrivers() {
  try {
    const data = await api("/api/drivers");
    drivers = data.drivers;

    // Show them as a simple list under the table.
    const list = document.getElementById("driver-list");
    list.innerHTML = drivers.length
      ? drivers.map(d => `<span class="user-chip" style="margin:4px 6px 0 0">
            ${escapeHtml(d.name)} <span class="role">${escapeHtml(d.email)}</span></span>`).join("")
      : "No driver accounts yet. Create one in the Admin panel.";
  } catch (err) {
    /* not critical - the table still works without the dropdown */
  }
}

/* ---------------------------------------------------------------------
   loadStats() - GET /api/stats and draw the summary cards
   --------------------------------------------------------------------- */
async function loadStats() {
  try {
    const { stats } = await api("/api/stats");
    document.getElementById("wh-stats").innerHTML = `
      ${statCard("Total shipments", stats.total_shipments)}
      ${statCard("Active", stats.active_shipments)}
      ${statCard("Delivered", stats.delivered_shipments)}
      ${statCard("Waiting in warehouse", stats.per_status["Pending"] || 0)}
      ${statCard("Stored on shelves", stats.per_status["Warehouse Received"] || 0)}
    `;
  } catch (err) {
    /* stats are optional - ignore errors */
  }
}

/* small helper that returns one statistic card's HTML */
function statCard(label, value) {
  return `<div class="card stat-card">
      <div class="label">${escapeHtml(label)}</div>
      <div class="value">${value}</div>
    </div>`;
}

/* ---------------------------------------------------------------------
   renderTable() - draws the table from `allShipments`, applying filters
   --------------------------------------------------------------------- */
function renderTable() {
  const tbody = document.getElementById("wh-body");
  const statusFilter = document.getElementById("status-filter").value;
  const search = document.getElementById("search").value.trim().toLowerCase();

  // filter: by status dropdown AND by free-text search
  const rows = allShipments.filter((s) => {
    const matchesStatus = !statusFilter || s.status === statusFilter;
    const haystack = `${s.tracking_number} ${s.receiver_name} ${s.customer_name}`.toLowerCase();
    const matchesSearch = !search || haystack.includes(search);
    return matchesStatus && matchesSearch;
  });

  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty">No shipments match this filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map((s) => {
    // ---- build the action buttons that are valid for this status ----
    const actions = [];

    // Step 1: parcel arrives at the warehouse -> set shelf + "Warehouse Received"
    if (s.status === "Pending") {
      actions.push(`
        <div class="inline-form">
          <input id="shelf-${s.id}" placeholder="Shelf e.g. A-12" style="min-width:110px;">
          <button class="btn btn-sm" onclick="receiveShipment(${s.id})">Receive</button>
        </div>`);
    }

    // Step 2: parcel leaves the warehouse -> "In Transit"
    if (s.status === "Warehouse Received") {
      actions.push(`<button class="btn btn-sm" onclick="dispatchShipment(${s.id})">Dispatch</button>`);
    }

    // Step 3: assign a driver (possible until the parcel is finished)
    if (["Pending", "Warehouse Received", "In Transit", "Out for Delivery"].includes(s.status)) {
      const options = drivers
        .map(d => `<option value="${d.id}" ${d.id === s.driver_id ? "selected" : ""}>
                     ${escapeHtml(d.name)}</option>`)
        .join("");
      actions.push(`
        <div class="inline-form">
          <select id="drv-${s.id}">
            <option value="">— driver —</option>
            ${options}
          </select>
          <button class="btn btn-outline btn-sm" onclick="assignDriver(${s.id})">Assign</button>
        </div>`);
    }

    return `
      <tr>
        <td class="mono">${escapeHtml(s.tracking_number)}</td>
        <td>${escapeHtml(s.customer_name || "-")}</td>
        <td>
          ${escapeHtml(s.receiver_name)}<br>
          <span class="muted" style="font-size:12px">${escapeHtml(s.receiver_address)}</span>
        </td>
        <td>${s.weight_kg} kg</td>
        <td>${statusBadge(s.status)}</td>
        <td>${s.shelf_location ? `<span class="mono">${escapeHtml(s.shelf_location)}</span>` : '<span class="muted">-</span>'}</td>
        <td>${s.driver_name ? escapeHtml(s.driver_name) : '<span class="muted">-</span>'}</td>
        <td><div class="row-actions">${actions.join("") || '<span class="muted">-</span>'}</div></td>
      </tr>`;
  }).join("");
}

/* ---------------------------------------------------------------------
   receiveShipment(id) - log the parcel in and store the shelf location
   --------------------------------------------------------------------- */
async function receiveShipment(id) {
  const shelfEl = document.getElementById(`shelf-${id}`);
  const shelf = shelfEl.value.trim();

  if (!shelf) {
    toast("Please type a shelf location first (e.g. A-12).", "error");
    shelfEl.focus();
    return;
  }

  try {
    // One endpoint handles every status change: POST /api/shipments/<id>/status
    const data = await api(`/api/shipments/${id}/status`, {
      method: "POST",
      body: { status: "Warehouse Received", shelf_location: shelf, note: `Stored on shelf ${shelf}.` },
    });
    toast(data.message, "success");
    await Promise.all([loadShipments(), loadStats()]);
  } catch (err) {
    toast(err.message, "error");
  }
}

/* ---------------------------------------------------------------------
   dispatchShipment(id) - the parcel leaves the warehouse ("In Transit")
   --------------------------------------------------------------------- */
async function dispatchShipment(id) {
  try {
    const data = await api(`/api/shipments/${id}/status`, {
      method: "POST",
      body: { status: "In Transit", note: "Dispatched from the warehouse." },
    });
    toast(data.message, "success");
    await Promise.all([loadShipments(), loadStats()]);
  } catch (err) {
    toast(err.message, "error");
  }
}

/* ---------------------------------------------------------------------
   assignDriver(id) - POST /api/shipments/<id>/assign { driver_id }
   --------------------------------------------------------------------- */
async function assignDriver(id) {
  const select = document.getElementById(`drv-${id}`);
  const driverId = select.value || null;   // "" means unassign

  try {
    const data = await api(`/api/shipments/${id}/assign`, {
      method: "POST",
      body: { driver_id: driverId },
    });
    toast(data.message, "success");
    loadShipments();
  } catch (err) {
    toast(err.message, "error");
  }
}
