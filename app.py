"""
=====================================================================================
 Logistics Management System (LMS)  -  Flask + MySQL backend  (single file)
=====================================================================================

 HOW TO RUN
 ----------
   1. pip install flask pymysql
   2. Make sure MySQL is running (the database 'GG' is created automatically)
   3. python app.py
   4. Open http://127.0.0.1:5000

 DEMO ACCOUNTS (created automatically the first time you start the app)
 ----------------------------------------------------------------------
   Admin            admin@lms.com      / admin123
   Warehouse Staff  warehouse@lms.com  / warehouse123
   Driver           driver@lms.com     / driver123
   Driver 2         driver2@lms.com    / driver123
   Customer         customer@lms.com   / customer123

 FILE MAP (what lives where)
 ---------------------------
   app.py                  -> THIS file: database + all routes + API endpoints
   MySQL database 'GG'     -> tables users/shipments/logs (auto-created on first start)
   templates/*.html        -> HTML pages (Jinja2 templates)
   static/css/style.css    -> all styling
   static/js/*.js          -> frontend JavaScript (fetch calls to the API)
   README.md               -> setup + "editing guide" (how to extend the system)

 BIG PICTURE / ARCHITECTURE
 --------------------------
   Browser  --(fetch JSON)-->  Flask API routes (/api/...)  -->  MySQL (database 'GG')
   Browser  --(page load)-->   Flask page routes (/, /customer, ...) --> templates/*.html

   Every user must log in. The logged-in user is remembered in Flask's *session*
   (a signed cookie). Each protected page/API checks the session and the user's
   role before doing anything ("route guard" + RBAC = Role Based Access Control).
=====================================================================================
"""

import random
from functools import wraps
from datetime import datetime

import pymysql                      # MySQL driver (pip install pymysql)
from pymysql.cursors import DictCursor

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

# =====================================================================================
# 1. CONFIGURATION  (small "settings" section - easy to change)
# =====================================================================================

# ---------------------------------------------------------------------------
# MySQL connection settings - change these to match your own MySQL server.
# The database (and all three tables) are created automatically on first start,
# so you do not have to run any SQL by hand.
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": "127.0.0.1",        # where the MySQL server runs
    "port": 3306,               # default MySQL port
    "user": "root",             # MySQL user name
    "password": "1234567890",   # MySQL password  (change for a real deployment!)
    "database": "GG",           # database name
    "charset": "utf8mb4",       # full unicode support (emoji-safe)
}

# The 4 user roles used by the system (Role Based Access Control).
# Want a 5th role later? Add its name here AND handle it in the pages/API (see README).
ROLES = ["customer", "warehouse", "driver", "admin"]

# Every possible shipment status, in the normal order of the delivery lifecycle.
# Add / rename a status here and it appears everywhere in the UI automatically.
STATUSES = [
    "Pending",
    "Warehouse Received",
    "In Transit",
    "Out for Delivery",
    "Delivered",
    "Cancelled",
]

# Which status a shipment is allowed to move INTO, from its current status.
# This is the "workflow" / state machine. Edit this to change the business process.
ALLOWED_TRANSITIONS = {
    "Pending": ["Warehouse Received", "Cancelled"],
    "Warehouse Received": ["In Transit", "Cancelled"],
    "In Transit": ["Out for Delivery", "Cancelled"],
    "Out for Delivery": ["Delivered", "Cancelled"],
    "Delivered": [],          # final state - nothing may change any more
    "Cancelled": [],          # final state
}

# Which role is allowed to set which status (extra safety on top of the transitions).
ROLE_STATUS_PERMISSIONS = {
    "warehouse": ["Warehouse Received", "In Transit", "Cancelled"],
    "driver": ["In Transit", "Out for Delivery", "Delivered"],
    "admin": STATUSES,        # admin may do anything
    "customer": [],           # customers use the dedicated /cancel endpoint instead
}

app = Flask(__name__)
# The session cookie is signed with this key. Change it for any real deployment!
app.secret_key = "lms-demo-secret-key-change-me"


# =====================================================================================
# 2. DATABASE TABLES  (the schema, written as plain SQL so it is easy to read)
# =====================================================================================

SCHEMA = """
-- ---------------------------------------------------------------------------
-- users: every person who can log in (all 4 roles live in this one table)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            INT           NOT NULL AUTO_INCREMENT,   -- unique user id
    name          VARCHAR(120)  NOT NULL,                  -- display name, e.g. "Jane Doe"
    email         VARCHAR(160)  NOT NULL,                  -- used as the login name
    password_hash VARCHAR(255)  NOT NULL,                  -- hashed password (never plain text!)
    role          VARCHAR(20)   NOT NULL,                  -- customer | warehouse | driver | admin
    created_at    DATETIME      NOT NULL,                  -- when the account was created
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ---------------------------------------------------------------------------
-- shipments: one row = one parcel/order being delivered
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shipments (
    id               INT          NOT NULL AUTO_INCREMENT,
    tracking_number  VARCHAR(30)  NOT NULL,   -- shown to the customer, e.g. LMS2510314821
    customer_id      INT          NOT NULL,   -- who placed the order  -> users.id
    driver_id        INT          NULL,       -- assigned rider         -> users.id (NULL = none yet)
    sender_name      VARCHAR(120) NOT NULL,   -- who sends the parcel
    sender_address   VARCHAR(255) NOT NULL,   -- pickup address
    receiver_name    VARCHAR(120) NOT NULL,   -- who receives the parcel
    receiver_phone   VARCHAR(40)  NOT NULL,   -- contact number of the receiver
    receiver_address VARCHAR(255) NOT NULL,   -- delivery address
    weight_kg        DOUBLE       NOT NULL DEFAULT 1,
    description      TEXT         NULL,       -- what is inside the parcel
    shelf_location   VARCHAR(40)  NULL,       -- rack/shelf set by warehouse staff, e.g. "A-12"
    status           VARCHAR(30)  NOT NULL DEFAULT 'Pending',
    created_at       DATETIME     NOT NULL,
    updated_at       DATETIME     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_shipments_tracking (tracking_number),
    CONSTRAINT fk_shipments_customer FOREIGN KEY (customer_id) REFERENCES users (id),
    -- if a driver account is deleted, the shipment simply becomes unassigned
    CONSTRAINT fk_shipments_driver   FOREIGN KEY (driver_id)   REFERENCES users (id)
        ON DELETE SET NULL
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ---------------------------------------------------------------------------
-- logs: an audit trail / timeline. One row every time a shipment changes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS logs (
    id          INT          NOT NULL AUTO_INCREMENT,
    shipment_id INT          NOT NULL,   -- which shipment this event belongs to
    status      VARCHAR(30)  NOT NULL,   -- the status that was set at that moment
    note        TEXT         NULL,       -- free-text explanation
    updated_by  INT          NULL,       -- which user did it -> users.id
    created_at  DATETIME     NOT NULL,   -- when it happened
    PRIMARY KEY (id),
    CONSTRAINT fk_logs_shipment FOREIGN KEY (shipment_id) REFERENCES shipments (id),
    -- keep the history even if the staff account is deleted
    CONSTRAINT fk_logs_user     FOREIGN KEY (updated_by)  REFERENCES users (id)
        ON DELETE SET NULL
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
"""


# =====================================================================================
# 3. DATABASE HELPERS  (tiny functions so the routes stay readable)
# =====================================================================================

def get_connection(select_database=True):
    """Open a new connection to the MySQL server.

    select_database=False connects to the server WITHOUT choosing a database.
    We need that once, at start-up, to run "CREATE DATABASE IF NOT EXISTS GG".

    DictCursor makes every row a dictionary, so we can write row["name"]
    instead of row[0] - exactly like the SQLite version did.
    """
    settings = dict(DB_CONFIG)          # copy so we can drop a key safely
    if not select_database:
        settings.pop("database")
    return pymysql.connect(cursorclass=DictCursor, **settings)


def get_db():
    """Return the MySQL connection for the current request.

    Flask's `g` object stores data for the duration of one request, so we open
    exactly one connection per request and reuse it for the whole request.
    """
    if "db" not in g:
        g.db = get_connection()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """Close the database connection when the request finishes."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_db(sql, params=(), one=False):
    """Run a SELECT and return the rows (as loose dictionaries)."""
    cur = get_db().cursor()
    try:
        cur.execute(sql, params)
        rows = list(cur.fetchall())     # DictCursor -> list of dicts
    finally:
        cur.close()

    # MySQL hands DATETIME values back as Python datetime objects. The frontend
    # expects "YYYY-MM-DD HH:MM:SS" strings (like the SQLite version produced),
    # so we convert them here in one place.
    for row in rows:
        for key, value in row.items():
            if isinstance(value, datetime):
                row[key] = value.strftime("%Y-%m-%d %H:%M:%S")

    return (rows[0] if rows else None) if one else rows


def execute_db(sql, params=()):
    """Run an INSERT / UPDATE / DELETE, save it, and return the new row id."""
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(sql, params)
        db.commit()                     # MySQL needs an explicit commit
        last_id = cur.lastrowid         # id created by AUTO_INCREMENT
    finally:
        cur.close()
    return last_id


def now():
    """Current timestamp as a simple readable string (used in every table)."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    """Create the database + tables (if missing) and add the demo accounts once.

    Note: NO shipment/log demo data is inserted - the database starts empty,
    so you can create orders yourself while testing.
    """
    # --- step 1: create the database itself -----------------------------------
    server = get_connection(select_database=False)
    try:
        cur = server.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cur.close()
        server.commit()
    finally:
        server.close()

    # --- step 2: create the three tables --------------------------------------
    db = get_connection()
    try:
        cur = db.cursor()
        # The schema is one big string; MySQL executes one statement at a time,
        # so we split it on ";" and run each part.
        for statement in SCHEMA.split(";"):
            if statement.strip():
                cur.execute(statement)
        db.commit()

        # --- step 3: demo accounts (only when the users table is empty) -------
        cur.execute("SELECT COUNT(*) AS total FROM users")
        if cur.fetchone()["total"] == 0:
            demo_users = [
                ("System Admin", "admin@lms.com", "admin123", "admin"),
                ("Wendy Warehouse", "warehouse@lms.com", "warehouse123", "warehouse"),
                ("Danny Driver", "driver@lms.com", "driver123", "driver"),
                ("Rita Rider", "driver2@lms.com", "driver123", "driver"),
                ("Cathy Customer", "customer@lms.com", "customer123", "customer"),
            ]
            for name, email, password, role in demo_users:
                cur.execute(
                    "INSERT INTO users (name, email, password_hash, role, created_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (name, email, generate_password_hash(password), role, now()),
                )
            db.commit()
    finally:
        db.close()


# =====================================================================================
# 4. AUTH HELPERS  (session guard + role guard)
# =====================================================================================

def login_required(*allowed_roles):
    """Decorator that protects a route.

    Usage:
        @login_required()                  # any logged-in user
        @login_required("admin")           # only admins
        @login_required("warehouse", "admin")

    For API routes (/api/...) we return a JSON 401/403 error, so the JavaScript
    can show a friendly message. For normal pages we redirect the user away.
    """
    def decorator(view_function):
        @wraps(view_function)
        def wrapper(*args, **kwargs):
            # --- check 1: is anybody logged in? ---------------------------------
            if "user_id" not in session:
                if request.path.startswith("/api/"):
                    return jsonify({"success": False, "error": "Please log in first."}), 401
                flash("Please log in first.", "error")
                return redirect(url_for("login_page"))

            # --- check 2: does this role have permission? ----------------------
            if allowed_roles and session.get("role") not in allowed_roles:
                if request.path.startswith("/api/"):
                    return jsonify({"success": False, "error": "You do not have permission to do that."}), 403
                flash("You do not have permission to open that page.", "error")
                return redirect(url_for("dashboard"))
            return view_function(*args, **kwargs)
        return wrapper
    return decorator


def current_user():
    """Fetch the logged-in user row from the database (or None)."""
    if "user_id" not in session:
        return None
    return query_db("SELECT id, name, email, role FROM users WHERE id = %s",
                    (session["user_id"],), one=True)


@app.context_processor
def inject_globals():
    """Make `me`, `statuses` and `roles` available inside every template."""
    return {
        "me": current_user(),
        "statuses": STATUSES,
        "roles": ROLES,
    }


# =====================================================================================
# 5. SMALL UTILITIES
# =====================================================================================

def make_tracking_number():
    """Create a unique tracking number like LMS2510314821 (LMS + date + 4 digits)."""
    while True:
        candidate = "LMS" + datetime.now().strftime("%y%m%d") + str(random.randint(1000, 9999))
        exists = query_db("SELECT id FROM shipments WHERE tracking_number = %s",
                          (candidate,), one=True)
        if not exists:              # loop again if (very unlikely) already used
            return candidate


def add_log(shipment_id, status, note, user_id):
    """Write one entry to the logs table (the shipment timeline)."""
    execute_db(
        "INSERT INTO logs (shipment_id, status, note, updated_by, created_at) "
        "VALUES (%s, %s, %s, %s, %s)",
        (shipment_id, status, note, user_id, now()),
    )


def next_statuses(status):
    """Which statuses may follow the given one (used by the UI + validation)."""
    return ALLOWED_TRANSITIONS.get(status, [])


# =====================================================================================
# 6. PAGE ROUTES  (each one renders an HTML template)
# =====================================================================================

@app.route("/")
def index():
    """Home page: send the visitor to their own dashboard, or to the login page."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))


@app.route("/login", methods=["GET", "POST"])
def login_page():
    """Login form. On success we store the user id + role in the session."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = query_db("SELECT * FROM users WHERE email = %s", (email,), one=True)

        # check_password_hash compares the typed password with the stored hash
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Wrong email or password. Please try again.", "error")
            return render_template("login.html", email=email)

        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["name"] = user["name"]
        flash(f"Welcome back, {user['name']}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html", email="")


@app.route("/register", methods=["GET", "POST"])
def register_page():
    """Self-service sign-up. New accounts are ALWAYS 'customer' accounts."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html", name=name, email=email)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("register.html", name=name, email=email)

        if query_db("SELECT id FROM users WHERE email = %s", (email,), one=True):
            flash("That email is already registered. Try logging in.", "error")
            return render_template("register.html", name=name, email=email)

        execute_db(
            "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (%s, %s, %s, %s, %s)",
            (name, email, generate_password_hash(password), "customer", now()),
        )
        flash("Account created. You can log in now.", "success")
        return redirect(url_for("login_page"))

    return render_template("register.html", name="", email="")


@app.route("/logout")
def logout():
    """Forget the session - i.e. log the user out."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login_page"))


@app.route("/dashboard")
@login_required()
def dashboard():
    """A single URL that shows a different page for each role."""
    role = session.get("role")
    if role == "customer":
        return render_template("customer.html")
    if role == "warehouse":
        return render_template("warehouse.html")
    if role == "driver":
        return render_template("driver.html")
    if role == "admin":
        return render_template("admin.html")
    # Unknown role -> something is wrong, log out to be safe.
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/track")
@app.route("/track/<tracking_number>")
def track_page(tracking_number=None):
    """Public tracking page - anyone with a tracking number can use it."""
    return render_template("track.html", tracking_number=tracking_number or "")


# =====================================================================================
# 7. JSON API - AUTH / MISC
# =====================================================================================

@app.get("/api/me")
def api_me():
    """Tell the frontend who is logged in (used by common.js on page load)."""
    user = current_user()
    if user is None:
        return jsonify({"success": False, "error": "Not logged in."}), 401
    return jsonify({"success": True, "user": user})


@app.get("/api/meta")
def api_meta():
    """Handy lists for the frontend (statuses + allowed transitions)."""
    return jsonify({
        "success": True,
        "statuses": STATUSES,
        "roles": ROLES,
        "transitions": ALLOWED_TRANSITIONS,
        "role_status_permissions": ROLE_STATUS_PERMISSIONS,
    })


# =====================================================================================
# 8. JSON API - SHIPMENTS  (create / list / detail / update / assign / cancel)
# =====================================================================================

# The SELECT below is used in several places. It joins the shipments table with
# users twice so we can show the customer's name and the driver's name.
SHIPMENT_SELECT = """
SELECT s.*,
       c.name AS customer_name,
       c.email AS customer_email,
       d.name AS driver_name
FROM shipments s
LEFT JOIN users c ON c.id = s.customer_id
LEFT JOIN users d ON d.id = s.driver_id
"""


@app.get("/api/shipments")
@login_required()
def api_list_shipments():
    """Return the shipments the current user is allowed to see.

    customer  -> only their own shipments
    driver    -> only shipments assigned to them
    warehouse -> every shipment (they need to handle all parcels)
    admin     -> every shipment
    """
    role = session["role"]

    if role == "customer":
        rows = query_db(SHIPMENT_SELECT + " WHERE s.customer_id = %s ORDER BY s.id DESC",
                        (session["user_id"],))
    elif role == "driver":
        rows = query_db(SHIPMENT_SELECT + " WHERE s.driver_id = %s ORDER BY s.id DESC",
                        (session["user_id"],))
    else:
        rows = query_db(SHIPMENT_SELECT + " ORDER BY s.id DESC")

    # Add the allowed "next statuses" so the frontend knows which buttons to show.
    for row in rows:
        row["next_statuses"] = [st for st in next_statuses(row["status"])
                                if st in ROLE_STATUS_PERMISSIONS.get(role, [])]
    return jsonify({"success": True, "shipments": rows})


@app.get("/api/shipments/<int:shipment_id>")
@login_required()
def api_get_shipment(shipment_id):
    """One shipment + its full log timeline (used by the tracking page)."""
    shipment = query_db(SHIPMENT_SELECT + " WHERE s.id = %s", (shipment_id,), one=True)
    if shipment is None:
        return jsonify({"success": False, "error": "Shipment not found."}), 404

    # Customers may only open their own shipment.
    if session["role"] == "customer" and shipment["customer_id"] != session["user_id"]:
        return jsonify({"success": False, "error": "Not your shipment."}), 403

    shipment["logs"] = query_db(
        "SELECT l.*, u.name AS updated_by_name FROM logs l "
        "LEFT JOIN users u ON u.id = l.updated_by "
        "WHERE l.shipment_id = %s ORDER BY l.id ASC",
        (shipment_id,),
    )
    return jsonify({"success": True, "shipment": shipment})


@app.post("/api/shipments")
@login_required("customer", "admin")
def api_create_shipment():
    """Create a new order. The tracking number is generated automatically."""
    data = request.get_json(silent=True) or {}

    # --- simple validation ---------------------------------------------------
    required = ["sender_name", "sender_address", "receiver_name",
                "receiver_phone", "receiver_address"]
    for field in required:
        if not str(data.get(field, "")).strip():
            return jsonify({"success": False,
                            "error": f"Field '{field.replace('_', ' ')}' is required."}), 400

    try:
        weight = float(data.get("weight_kg", 1) or 1)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Weight must be a number."}), 400

    # Admins may order on behalf of a customer; everybody else orders for themselves.
    customer_id = session["user_id"]
    if session["role"] == "admin" and data.get("customer_id"):
        customer_id = int(data["customer_id"])

    tracking_number = make_tracking_number()
    timestamp = now()

    new_id = execute_db(
        "INSERT INTO shipments (tracking_number, customer_id, sender_name, sender_address, "
        "receiver_name, receiver_phone, receiver_address, weight_kg, description, status, "
        "created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pending', %s, %s)",
        (
            tracking_number,
            customer_id,
            data.get("sender_name", "").strip(),
            data.get("sender_address", "").strip(),
            data.get("receiver_name", "").strip(),
            data.get("receiver_phone", "").strip(),
            data.get("receiver_address", "").strip(),
            weight,
            data.get("description", "").strip(),
            timestamp,
            timestamp,
        ),
    )

    # First timeline entry.
    add_log(new_id, "Pending", "Order created by the customer.", session["user_id"])

    return jsonify({
        "success": True,
        "message": f"Order created. Tracking number: {tracking_number}",
        "tracking_number": tracking_number,
        "shipment_id": new_id,
    }), 201


@app.post("/api/shipments/<int:shipment_id>/status")
@login_required("warehouse", "driver", "admin")
def api_update_status(shipment_id):
    """Move a shipment to a new status and write a log entry.

    Request body (JSON):
        { "status": "In Transit", "note": "Loaded on truck", "shelf_location": "A-12" }
    """
    data = request.get_json(silent=True) or {}
    new_status = str(data.get("status", "")).strip()
    note = str(data.get("note", "")).strip()
    shelf_location = str(data.get("shelf_location", "")).strip()

    shipment = query_db("SELECT * FROM shipments WHERE id = %s", (shipment_id,), one=True)
    if shipment is None:
        return jsonify({"success": False, "error": "Shipment not found."}), 404

    role = session["role"]

    # 1) Does the role allow setting this status at all?
    if new_status not in ROLE_STATUS_PERMISSIONS.get(role, []):
        return jsonify({"success": False,
                        "error": f"The {role} role may not set the status '{new_status}'."}), 403

    # 2) Is the status a legal next step in the workflow?
    if new_status not in next_statuses(shipment["status"]):
        return jsonify({"success": False,
                        "error": f"Cannot go from '{shipment['status']}' to '{new_status}'."}), 400

    # 3) Drivers may only touch their own assignments.
    if role == "driver" and shipment["driver_id"] != session["user_id"]:
        return jsonify({"success": False, "error": "This shipment is not assigned to you."}), 403

    # 4) Optional shelf location (warehouse staff assign the rack on arrival).
    if shelf_location:
        execute_db("UPDATE shipments SET shelf_location = %s WHERE id = %s",
                   (shelf_location, shipment_id))

    # 5) Save the new status + updated_at timestamp.
    execute_db("UPDATE shipments SET status = %s, updated_at = %s WHERE id = %s",
               (new_status, now(), shipment_id))

    # 6) Timeline entry.
    default_note = f"Status changed to '{new_status}' by {role}."
    add_log(shipment_id, new_status, note or default_note, session["user_id"])

    return jsonify({"success": True,
                    "message": f"Status updated to '{new_status}'."})


@app.post("/api/shipments/<int:shipment_id>/assign")
@login_required("admin", "warehouse")
def api_assign_driver(shipment_id):
    """Assign (or unassign, by sending driver_id: null) a driver to a shipment."""
    data = request.get_json(silent=True) or {}
    driver_id = data.get("driver_id")

    shipment = query_db("SELECT * FROM shipments WHERE id = %s", (shipment_id,), one=True)
    if shipment is None:
        return jsonify({"success": False, "error": "Shipment not found."}), 404

    if driver_id in (None, "", 0, "0"):
        execute_db("UPDATE shipments SET driver_id = NULL, updated_at = %s WHERE id = %s",
                   (now(), shipment_id))
        add_log(shipment_id, shipment["status"], "Delivery task unassigned.", session["user_id"])
        return jsonify({"success": True, "message": "Driver unassigned."})

    driver = query_db("SELECT * FROM users WHERE id = %s AND role = 'driver'",
                      (int(driver_id),), one=True)
    if driver is None:
        return jsonify({"success": False, "error": "That driver does not exist."}), 400

    execute_db("UPDATE shipments SET driver_id = %s, updated_at = %s WHERE id = %s",
               (driver["id"], now(), shipment_id))
    add_log(shipment_id, shipment["status"], f"Assigned to driver {driver['name']}.",
            session["user_id"])

    return jsonify({"success": True, "message": f"Assigned to {driver['name']}."})


@app.post("/api/shipments/<int:shipment_id>/cancel")
@login_required("customer")
def api_cancel_shipment(shipment_id):
    """A customer may cancel their own order while it is still 'Pending'."""
    shipment = query_db("SELECT * FROM shipments WHERE id = %s", (shipment_id,), one=True)
    if shipment is None:
        return jsonify({"success": False, "error": "Shipment not found."}), 404

    if shipment["customer_id"] != session["user_id"]:
        return jsonify({"success": False, "error": "Not your shipment."}), 403

    if shipment["status"] != "Pending":
        return jsonify({"success": False,
                        "error": "Only orders that are still 'Pending' can be cancelled."}), 400

    execute_db("UPDATE shipments SET status = 'Cancelled', updated_at = %s WHERE id = %s",
               (now(), shipment_id))
    add_log(shipment_id, "Cancelled", "Cancelled by the customer.", session["user_id"])

    return jsonify({"success": True, "message": "Order cancelled."})


# =====================================================================================
# 9. JSON API - PUBLIC TRACKING
# =====================================================================================

@app.get("/api/track/<tracking_number>")
def api_track(tracking_number):
    """Public endpoint: look a shipment up by its tracking number + return timeline."""
    shipment = query_db(SHIPMENT_SELECT + " WHERE s.tracking_number = %s",
                        (tracking_number.strip(),), one=True)
    if shipment is None:
        return jsonify({"success": False, "error": "No shipment found with that tracking number."}), 404

    shipment["logs"] = query_db(
        "SELECT l.*, u.name AS updated_by_name FROM logs l "
        "LEFT JOIN users u ON u.id = l.updated_by "
        "WHERE l.shipment_id = %s ORDER BY l.id ASC",
        (shipment["id"],),
    )
    # Do not expose private customer details on a public page.
    shipment.pop("customer_email", None)
    return jsonify({"success": True, "shipment": shipment})


# =====================================================================================
# 10. JSON API - USERS (admin)  + DROPDOWN LISTS
# =====================================================================================

@app.get("/api/users")
@login_required("admin")
def api_list_users():
    """All accounts, newest first (admin only)."""
    users = query_db(
        "SELECT id, name, email, role, created_at FROM users ORDER BY id ASC"
    )
    return jsonify({"success": True, "users": users})


@app.post("/api/users")
@login_required("admin")
def api_create_user():
    """Admin creates an account with any role (e.g. a new driver)."""
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "customer")).strip()

    if not name or not email or len(password) < 6:
        return jsonify({"success": False,
                        "error": "Name, email and a password of 6+ characters are required."}), 400
    if role not in ROLES:
        return jsonify({"success": False, "error": "Unknown role."}), 400
    if query_db("SELECT id FROM users WHERE email = %s", (email,), one=True):
        return jsonify({"success": False, "error": "That email is already registered."}), 400

    execute_db(
        "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (%s, %s, %s, %s, %s)",
        (name, email, generate_password_hash(password), role, now()),
    )
    return jsonify({"success": True, "message": f"Account for {name} created."}), 201


@app.post("/api/users/<int:user_id>/role")
@login_required("admin")
def api_change_role(user_id):
    """Change somebody's role (e.g. promote a customer to warehouse staff)."""
    data = request.get_json(silent=True) or {}
    role = str(data.get("role", "")).strip()
    if role not in ROLES:
        return jsonify({"success": False, "error": "Unknown role."}), 400

    target = query_db("SELECT * FROM users WHERE id = %s", (user_id,), one=True)
    if target is None:
        return jsonify({"success": False, "error": "User not found."}), 404
    if target["id"] == session["user_id"]:
        return jsonify({"success": False, "error": "You cannot change your own role."}), 400

    execute_db("UPDATE users SET role = %s WHERE id = %s", (role, user_id))
    return jsonify({"success": True, "message": f"{target['name']} is now a {role}."})


@app.delete("/api/users/<int:user_id>")
@login_required("admin")
def api_delete_user(user_id):
    """Delete an account. Accounts that own shipments are protected."""
    target = query_db("SELECT * FROM users WHERE id = %s", (user_id,), one=True)
    if target is None:
        return jsonify({"success": False, "error": "User not found."}), 404
    if target["id"] == session["user_id"]:
        return jsonify({"success": False, "error": "You cannot delete your own account."}), 400

    owned = query_db("SELECT id FROM shipments WHERE customer_id = %s OR driver_id = %s LIMIT 1",
                     (user_id, user_id), one=True)
    if owned:
        return jsonify({"success": False,
                        "error": "This user is linked to shipments and cannot be deleted."}), 400

    execute_db("DELETE FROM users WHERE id = %s", (user_id,))
    return jsonify({"success": True, "message": f"{target['name']} deleted."})


@app.get("/api/drivers")
@login_required("admin", "warehouse")
def api_list_drivers():
    """Small list of drivers, used by the 'assign driver' dropdown."""
    drivers = query_db("SELECT id, name, email FROM users WHERE role = 'driver' ORDER BY name")
    return jsonify({"success": True, "drivers": drivers})


@app.get("/api/customers")
@login_required("admin")
def api_list_customers():
    """Small list of customers, used when an admin creates an order for someone."""
    customers = query_db("SELECT id, name, email FROM users WHERE role = 'customer' ORDER BY name")
    return jsonify({"success": True, "customers": customers})


# =====================================================================================
# 11. JSON API - DASHBOARD STATISTICS
# =====================================================================================

@app.get("/api/stats")
@login_required("admin", "warehouse")
def api_stats():
    """Counts used by the admin/warehouse dashboard cards."""
    total = query_db("SELECT COUNT(*) AS n FROM shipments", one=True)["n"]
    delivered = query_db("SELECT COUNT(*) AS n FROM shipments WHERE status = 'Delivered'",
                         one=True)["n"]
    cancelled = query_db("SELECT COUNT(*) AS n FROM shipments WHERE status = 'Cancelled'",
                         one=True)["n"]
    active = total - delivered - cancelled
    users_total = query_db("SELECT COUNT(*) AS n FROM users", one=True)["n"]

    # How many shipments are in each status (for the little bar chart).
    per_status = {status: 0 for status in STATUSES}
    for row in query_db("SELECT status, COUNT(*) AS n FROM shipments GROUP BY status"):
        per_status[row["status"]] = row["n"]

    # How many registered users per role.
    per_role = {role: 0 for role in ROLES}
    for row in query_db("SELECT role, COUNT(*) AS n FROM users GROUP BY role"):
        per_role[row["role"]] = row["n"]

    return jsonify({
        "success": True,
        "stats": {
            "total_shipments": total,
            "active_shipments": active,
            "delivered_shipments": delivered,
            "cancelled_shipments": cancelled,
            "total_users": users_total,
            "per_status": per_status,
            "per_role": per_role,
        },
    })


# =====================================================================================
# 12. STARTUP
# =====================================================================================

if __name__ == "__main__":
    init_db()          # create tables + demo users on first run
    # debug=True gives helpful error pages and auto-reload while you edit code.
    app.run(debug=True, host="127.0.0.1", port=5000)
