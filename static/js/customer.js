/* =====================================================================
   customer.js - logic for templates/customer.html
   - loads the customer's own shipments into the table
   - sends the "create order" form to POST /api/shipments
   - allows cancelling an order that is still Pending
   ===================================================================== */

onReady(() => {
  loadOrders();                          // initial load of the table
  document.getElementById("order-form").addEventListener("submit", createOrder);
});

/* ---------------------------------------------------------------------
   loadOrders()
   Ask the backend for "the shipments I am allowed to see" and rebuild
   the table body. For a customer this is only their own orders.
   --------------------------------------------------------------------- */
async function loadOrders() {
  const tbody = document.getElementById("orders-body");

  try {
    const data = await api("/api/shipments");   // GET /api/shipments
    const shipments = data.shipments;

    // No orders yet -> show a friendly empty message.
    if (shipments.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="empty">
        No orders yet. Create your first shipment on the left.
      </td></tr>`;
      return;
    }

    // Build one <tr> per shipment. escapeHtml() keeps user text safe.
    tbody.innerHTML = shipments.map((s) => `
      <tr>
        <td class="mono"><a href="/track/${encodeURIComponent(s.tracking_number)}"
            target="_blank">${escapeHtml(s.tracking_number)}</a></td>
        <td>
          ${escapeHtml(s.receiver_name)}<br>
          <span class="muted" style="font-size:12px">${escapeHtml(s.receiver_address)}</span>
        </td>
        <td>${statusBadge(s.status)}</td>
        <td>${s.shelf_location ? escapeHtml(s.shelf_location) : '<span class="muted">-</span>'}</td>
        <td>${s.driver_name ? escapeHtml(s.driver_name) : '<span class="muted">not assigned</span>'}</td>
        <td class="muted" style="font-size:12.5px">${shortDate(s.created_at)}</td>
        <td>
          <div class="row-actions">
            <a class="btn btn-outline btn-sm" href="/track/${encodeURIComponent(s.tracking_number)}">Track</a>
            ${s.status === "Pending"
              ? `<button class="btn btn-danger btn-sm" onclick="cancelOrder(${s.id})">Cancel</button>`
              : ""}
          </div>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty">${escapeHtml(err.message)}</td></tr>`;
    toast(err.message, "error");
  }
}

/* ---------------------------------------------------------------------
   createOrder(event)
   Reads the form, converts it into a JSON object and POSTs it to the API.
   The backend generates the tracking number and returns it.
   --------------------------------------------------------------------- */
async function createOrder(event) {
  event.preventDefault();                       // stop the browser from reloading
  const form = event.target;
  const feedback = document.getElementById("order-feedback");

  // Convert the form fields into a plain JS object: { sender_name: "...", ... }
  const payload = Object.fromEntries(new FormData(form).entries());

  try {
    const data = await api("/api/shipments", { method: "POST", body: payload });
    toast(data.message, "success");
    feedback.textContent = `Tracking number: ${data.tracking_number}`;
    form.reset();                               // clear the inputs
    loadOrders();                               // refresh the table
  } catch (err) {
    toast(err.message, "error");
    feedback.textContent = "";
  }
}

/* ---------------------------------------------------------------------
   cancelOrder(id)
   Called by the "Cancel" button. Only works while the status is Pending.
   --------------------------------------------------------------------- */
async function cancelOrder(id) {
  if (!confirm("Cancel this order?")) return;
  try {
    const data = await api(`/api/shipments/${id}/cancel`, { method: "POST" });
    toast(data.message, "success");
    loadOrders();
  } catch (err) {
    toast(err.message, "error");
  }
}
