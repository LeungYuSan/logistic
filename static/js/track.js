/* =====================================================================
   track.js - logic for templates/track.html
   Looks up a tracking number with the PUBLIC endpoint GET /api/track/<no>
   and draws the status + timeline.
   ===================================================================== */

onReady(() => {
  document.getElementById("track-form").addEventListener("submit", handleSubmit);

  // If the URL already contains a tracking number (/track/LMS...) -> search now
  const preFilled = document.getElementById("tracking-input").value.trim();
  if (preFilled) trackShipment(preFilled);
});

function handleSubmit(event) {
  event.preventDefault();                                  // no page reload
  const value = document.getElementById("tracking-input").value.trim();
  if (!value) {
    toast("Please enter a tracking number.", "error");
    return;
  }
  trackShipment(value);
}

/* ---------------------------------------------------------------------
   trackShipment(trackingNumber)
   --------------------------------------------------------------------- */
async function trackShipment(trackingNumber) {
  const result = document.getElementById("track-result");
  result.innerHTML = `<div class="card muted">Searching…</div>`;

  try {
    const data = await api(`/api/track/${encodeURIComponent(trackingNumber)}`);
    renderShipment(data.shipment);
  } catch (err) {
    result.innerHTML = `<div class="card"><strong>Not found.</strong>
      <p class="muted" style="margin:6px 0 0">${escapeHtml(err.message)}</p></div>`;
    toast(err.message, "error");
  }
}

/* ---------------------------------------------------------------------
   renderShipment(shipment) - builds the result card + timeline
   --------------------------------------------------------------------- */
function renderShipment(s) {
  // The timeline: newest event at the top, so we copy the array and reverse it.
  const timeline = [...s.logs].reverse().map((log) => `
    <li>
      <div class="what">${escapeHtml(log.status)}</div>
      <div class="when">${shortDate(log.created_at)}
        ${log.updated_by_name ? "· by " + escapeHtml(log.updated_by_name) : ""}</div>
      ${log.note ? `<div class="note">${escapeHtml(log.note)}</div>` : ""}
    </li>`).join("");

  document.getElementById("track-result").innerHTML = `
    <div class="card">
      <h2 style="display:flex; justify-content:space-between; align-items:center; gap:10px">
        <span class="mono">${escapeHtml(s.tracking_number)}</span>
        ${statusBadge(s.status)}
      </h2>

      <div class="grid two" style="gap:14px">
        <div>
          <div class="muted" style="font-size:12px; text-transform:uppercase; letter-spacing:.5px">From</div>
          <div><strong>${escapeHtml(s.sender_name)}</strong></div>
          <div class="muted" style="font-size:13px">${escapeHtml(s.sender_address)}</div>
        </div>
        <div>
          <div class="muted" style="font-size:12px; text-transform:uppercase; letter-spacing:.5px">To</div>
          <div><strong>${escapeHtml(s.receiver_name)}</strong></div>
          <div class="muted" style="font-size:13px">${escapeHtml(s.receiver_address)}</div>
        </div>
      </div>

      <div class="spacer"></div>
      <div class="muted" style="font-size:13px">
        Weight: <strong>${s.weight_kg} kg</strong>
        ${s.description ? " · Contents: " + escapeHtml(s.description) : ""}
        ${s.shelf_location ? " · Shelf: " + escapeHtml(s.shelf_location) : ""}
        ${s.driver_name ? " · Driver: " + escapeHtml(s.driver_name) : ""}
      </div>

      <div class="spacer"></div>
      <h2 style="margin-top:18px">Journey</h2>
      ${timeline ? `<ul class="timeline">${timeline}</ul>` : '<p class="muted">No events yet.</p>'}
    </div>`;
}
