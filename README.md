# Logistics Management System (LMS)

A clean, minimal, beginner-friendly **Flask + MySQL** prototype of a logistics/delivery
management system. Four roles (customer, warehouse staff, driver, admin), session-based
login, automatic tracking numbers, a status workflow with an audit log, and a small
JSON REST API consumed by vanilla JavaScript.

---

## 1. How to run

**Requirements:** Python 3.8+, a running MySQL 8 server.

```bash
pip install -r requirements.txt     # Flask + PyMySQL
python app.py
```

Then open <http://127.0.0.1:5000>.

### Database connection

All settings live in one place at the top of `app.py`:

```python
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "1234567890",   # <- your MySQL password
    "database": "GG",           # <- your database name
    "charset": "utf8mb4",
}
```

On start-up the app runs `CREATE DATABASE IF NOT EXISTS GG` and `CREATE TABLE IF NOT
EXISTS ...` for `users`, `shipments` and `logs`, so you never have to run SQL by hand.

**To reset everything**, stop the app and run:

```sql
DROP DATABASE GG;
```

…then start the app again — the tables and the five demo accounts are recreated.

**To inspect the data** while the app runs:

```bash
mysql -u root -p GG
> SELECT tracking_number, status, shelf_location FROM shipments;
> SELECT * FROM logs ORDER BY id DESC LIMIT 10;
```

### Demo accounts (seeded automatically)

| Role            | Email               | Password       |
| --------------- | ------------------- | -------------- |
| Admin           | `admin@lms.com`      | `admin123`     |
| Warehouse staff | `warehouse@lms.com`  | `warehouse123` |
| Driver          | `driver@lms.com`     | `driver123`    |
| Driver 2        | `driver2@lms.com`    | `driver123`    |
| Customer        | `customer@lms.com`   | `customer123`  |

Public sign-ups (`/register`) always create **customer** accounts; staff/driver/admin
accounts are created by an admin on the Admin page.

### Empty database

No shipments or logs are created automatically - **the database starts with only the five
accounts above**, so you can create orders yourself and screenshot your own test data.

---

## 2. File map

```
app.py                   # whole backend: DB schema, page routes, JSON API
MySQL database 'GG'      # tables users / shipments / logs (auto-created)
requirements.txt         # Python dependencies (Flask only)
diagrams.md              # ER diagram + use-case diagram + permission matrix (Mermaid)
templates/
  base.html              # shared layout: navbar, flash messages, scripts
  login.html  register.html
  customer.html          # create order + my orders
  warehouse.html         # receive / dispatch / assign driver
  driver.html            # my delivery tasks + status buttons
  admin.html             # statistics + user management
  track.html             # public tracking page
static/
  css/style.css          # all styling (colour palette lives in :root)
  js/common.js           # api(), toast(), escapeHtml(), statusBadge(), shortDate()
  js/customer.js  js/warehouse.js  js/driver.js  js/admin.js  js/track.js
```

### Try the full flow

1. Log in as **customer** → place an order → note the tracking number.
2. Log in as **warehouse** → type a shelf (e.g. `A-12`) → **Receive** → **Dispatch**, and **Assign** a driver.
3. Log in as **driver** → **Mark In Transit** → **Out for Delivery** → **Delivered**.
4. Open `/track/<tracking-number>` (no login needed) to see the whole timeline.
5. Log in as **admin** → see statistics, create a user, change a role.

---

## 3. Status workflow (state machine)

```
Pending → Warehouse Received → In Transit → Out for Delivery → Delivered
   ↘───────────────↘──────────────↘──────────────↘
                    Cancelled (customer may cancel only while Pending)
```

---

## 3b. Diagrams

See **[diagrams.md](diagrams.md)** for the Mermaid **ER diagram**, the **use case diagram**
(4 actors + 14 use cases) and a role/permission matrix. Paste the code blocks into
<https://mermaid.live> to export PNG/SVG images for Word.

---

## 4. REST API summary
| Method | Endpoint                          | Who              | Purpose                              |
| ------ | --------------------------------- | ---------------- | ------------------------------------ |
| GET    | `/api/me`                         | logged in        | who am I                             |
| GET    | `/api/meta`                       | anyone           | statuses, roles, transitions         |
| GET    | `/api/shipments`                  | logged in        | role-filtered list                   |
| POST   | `/api/shipments`                  | customer, admin  | create order (auto tracking number)  |
| GET    | `/api/shipments/<id>`             | owner/staff      | one shipment + timeline              |
| POST   | `/api/shipments/<id>/status`      | warehouse/driver/admin | change status (+ `note`, `shelf_location`) |
| POST   | `/api/shipments/<id>/assign`      | warehouse, admin | assign / unassign driver             |
| POST   | `/api/shipments/<id>/cancel`      | customer (own)   | cancel a Pending order               |
| GET    | `/api/track/<tracking_number>`    | **public**       | tracking page data                   |
| GET    | `/api/stats`                      | admin, warehouse | dashboard counters                   |
| GET    | `/api/users`                      | admin            | list accounts                        |
| POST   | `/api/users`                      | admin            | create account                       |
| POST   | `/api/users/<id>/role`            | admin            | change role                          |
| DELETE | `/api/users/<id>`                 | admin            | delete account                       |
| GET    | `/api/drivers`                    | warehouse, admin | driver dropdown                      |
| GET    | `/api/customers`                  | admin            | customer dropdown                    |

Every response looks like `{"success": true, ...}` or `{"success": false, "error": "..."}`.

---

## 5. Editing guide (how to extend the system)

### Add a new tracking status
* `app.py` → `STATUSES` list (add the name, e.g. `"Failed Attempt"`).
* `app.py` → `ALLOWED_TRANSITIONS` (say which statuses may lead to it and out of it).
* `app.py` → `ROLE_STATUS_PERMISSIONS` (which role is allowed to set it).
* `static/css/style.css` → add `.badge[data-status="Failed Attempt"] { ... }` for a colour.
* Nothing else: buttons, filters and timelines are generated from these lists.

### Add a new role (e.g. "supervisor")
1. `app.py` → add `"supervisor"` to `ROLES`.
2. `app.py` → add `"supervisor": [...]` to `ROLE_STATUS_PERMISSIONS` if they may change statuses.
3. `app.py` → `dashboard()` returns a template for the role:
   `if role == "supervisor": return render_template("supervisor.html")`.
4. Create `templates/supervisor.html` (copy an existing dashboard) and
   `static/js/supervisor.js` for its logic.
5. Protect API routes with `@login_required("supervisor")` where needed;
   update `api_list_shipments()` / `api_stats()` to include the role.
6. `templates/base.html` → add a nav link inside `{% if me.role == 'supervisor' %}`.

### Add a new shipment field (e.g. `delivery_fee`)
1. `app.py` → `SCHEMA`: add `delivery_fee DOUBLE` to `CREATE TABLE shipments`.
   (For an existing database run `ALTER TABLE shipments ADD COLUMN delivery_fee DOUBLE;`.)
2. `app.py` → `INSERT` in `api_create_shipment()`: add the column + one `?`,
   and read `data.get("delivery_fee", 0)`.
3. `templates/customer.html` → add an `<input name="delivery_fee">` in the order form.
4. `static/js/customer.js` / `warehouse.js` / `track.js` → show the value in the table/card.
5. `SHIPMENT_SELECT` already uses `s.*`, so the new column comes back automatically.

### Add a new page
1. `app.py`: create a route, e.g.
   ```python
   @app.route("/reports")
   @login_required("admin")
   def reports_page():
       return render_template("reports.html")
   ```
2. Create `templates/reports.html` with `{% extends "base.html" %}` and a
   `{% block content %}` / `{% block scripts %}`.
3. Add a nav link in `templates/base.html`.

### Where to change the look
* Colours/spacing: `:root` at the top of `static/css/style.css`.
* Status badge colours: `.badge[data-status="..."]` rules in `style.css`.
* Site name: `templates/base.html` (the `.brand` div).

### Where to change behaviour
* Workflow rules: `ALLOWED_TRANSITIONS` in `app.py`.
* Who can do what: `ROLE_STATUS_PERMISSIONS` + `@login_required(...)` on each route.
* Session lifetime / security: `app.secret_key` in `app.py` (change it, and keep it secret).
* Debug mode: last line of `app.py` (`app.run(debug=True)` → set `False` for a demo you host).

---

## 6. Notes for the report / viva

* **RBAC** is enforced in two places: the UI hides what you cannot do, and the API
  (`@login_required("role")`) blocks direct URL calls. Try opening `/dashboard` in a
  private window without logging in — you get bounced to `/login`.
* **Tracking number generation**: `make_tracking_number()` → `LMS` + `YYMMDD` + 4 random
  digits, with a uniqueness check against the `shipments` table.
* **Audit trail**: every status change inserts a row in `logs`, which is what the
  tracking timeline renders.
* Passwords are stored as **hashes** (`werkzeug.security.generate_password_hash`), never
  as plain text.
