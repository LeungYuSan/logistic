/* =====================================================================
   common.js - helper functions used by every page
   Loaded on ALL pages (see templates/base.html).
   ===================================================================== */

/* ---------------------------------------------------------------------
   api(url, options)
   Small wrapper around fetch() that talks to our Flask JSON API.
   - Automatically sends/receives JSON
   - Throws a normal JavaScript Error when the backend says success:false
   Example:
       const data = await api('/api/shipments');
       console.log(data.shipments);
   --------------------------------------------------------------------- */
async function api(url, options = {}) {
  const settings = {
    headers: { "Content-Type": "application/json" },
    ...options,
  };
  // Allow passing a plain object as the body - we convert it to JSON here.
  if (settings.body && typeof settings.body !== "string") {
    settings.body = JSON.stringify(settings.body);
  }

  const response = await fetch(url, settings);

  let data = {};
  try {
    data = await response.json();     // every API route returns JSON
  } catch (err) {
    /* ignore: e.g. an HTML error page was returned */
  }

  if (!response.ok || data.success === false) {
    throw new Error(data.error || `Request failed (HTTP ${response.status})`);
  }
  return data;
}

/* ---------------------------------------------------------------------
   toast(message, type)
   Small pop-up in the bottom-right corner. type: "success" | "error" | "info"
   --------------------------------------------------------------------- */
function toast(message, type = "info") {
  const box = document.getElementById("toast-box");
  if (!box) return;

  const el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = message;
  box.appendChild(el);

  // remove it automatically after 3.5 seconds
  setTimeout(() => el.remove(), 3500);
}

/* ---------------------------------------------------------------------
   escapeHtml(text)
   Escapes user-entered text before inserting it into the page with
   innerHTML. This prevents HTML/script injection (XSS).
   --------------------------------------------------------------------- */
function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/* ---------------------------------------------------------------------
   statusBadge(status)
   Returns a small coloured <span> for a shipment status.
   Colours are defined in static/css/style.css (.badge[data-status="..."]).
   --------------------------------------------------------------------- */
function statusBadge(status) {
  return `<span class="badge" data-status="${escapeHtml(status)}">${escapeHtml(status)}</span>`;
}

/* ---------------------------------------------------------------------
   shortDate(text) - "2025-10-31 19:48:00" -> "31 Oct 2025, 19:48"
   --------------------------------------------------------------------- */
function shortDate(text) {
  if (!text) return "-";
  const d = new Date(text.replace(" ", "T"));
  if (isNaN(d.getTime())) return text;
  return d.toLocaleString(undefined, {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

/* ---------------------------------------------------------------------
   onReady(callback)
   Runs the callback once the HTML page has finished loading.
   --------------------------------------------------------------------- */
function onReady(callback) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", callback);
  } else {
    callback();
  }
}
