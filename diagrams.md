# LMS – Diagrams 

Both diagrams are written in [Mermaid](https://mermaid.js.org/) so they render on GitHub,
GitLab, VS Code (Markdown preview), Notion, Obsidian, and on <https://mermaid.live>
(paste the code block there and click *Actions → PNG/SVG* to export an image for Word).

---

## 1. Entity Relationship (ER) Diagram

Three tables: `users`, `shipments`, `logs`.

* One **user** (customer) can place **many shipments**.
* One **user** (driver) can be assigned **many shipments**.
* One **shipment** has **many log entries** (the tracking timeline).
* One **user** can appear in **many logs** as the person who made the change.

```mermaid
erDiagram
    USERS ||--o{ SHIPMENTS : "places (customer_id)"
    USERS ||--o{ SHIPMENTS : "delivers (driver_id)"
    SHIPMENTS ||--o{ LOGS : "has events"
    USERS ||--o{ LOGS : "performed (updated_by)"

    USERS {
        INT          id PK "auto_increment unique user id"
        VARCHAR(120) name "display name"
        VARCHAR(160) email UK "login name, unique"
        VARCHAR(255) password_hash "hashed password"
        VARCHAR(20)  role "customer | warehouse | driver | admin"
        DATETIME     created_at "account creation time"
    }

    SHIPMENTS {
        INT          id PK "auto_increment unique shipment id"
        VARCHAR(30)  tracking_number UK "LMS + YYMMDD + 4 digits"
        INT          customer_id FK "users.id - who ordered"
        INT          driver_id FK "users.id - assigned rider (nullable)"
        VARCHAR(120) sender_name "sender display name"
        VARCHAR(255) sender_address "pickup address"
        VARCHAR(120) receiver_name "receiver display name"
        VARCHAR(40)  receiver_phone "receiver contact number"
        VARCHAR(255) receiver_address "delivery address"
        DOUBLE       weight_kg "parcel weight"
        TEXT         description "parcel contents"
        VARCHAR(40)  shelf_location "warehouse rack, e.g. A-12"
        VARCHAR(30)  status "Pending ... Delivered / Cancelled"
        DATETIME     created_at "order creation time"
        DATETIME     updated_at "last status change"
    }

    LOGS {
        INT          id PK "auto_increment unique log id"
        INT          shipment_id FK "shipments.id"
        VARCHAR(30)  status "status set at that moment"
        TEXT         note "free-text explanation"
        INT          updated_by FK "users.id - who did it (NULL if the user was deleted)"
        DATETIME     created_at "when it happened"
    }
```

### Cardinality in words

| Relationship | Type | Meaning |
| --- | --- | --- |
| `USERS` → `SHIPMENTS` (customer_id) | 1 : N | a customer owns many shipments; each shipment belongs to exactly one customer |
| `USERS` → `SHIPMENTS` (driver_id) | 1 : N (optional, `ON DELETE SET NULL`) | a driver can be assigned many shipments; a shipment has 0 or 1 driver |
| `SHIPMENTS` → `LOGS` | 1 : N | every status change adds one log row |
| `USERS` → `LOGS` (updated_by) | 1 : N | each log row records who made the change |

---

## 2. Use Case Diagram

Actors: **Customer**, **Warehouse Staff**, **Driver/Rider**, **Admin**.
The dashed arrows are `«include»` relationships (the status update always also
writes a timeline entry).

```mermaid
flowchart LR
    %% ---------- actors ----------
    CUSTOMER(("👤<br/>Customer"))
    WAREHOUSE(("👤<br/>Warehouse<br/>Staff"))
    DRIVER(("👤<br/>Driver /<br/>Rider"))
    ADMIN(("👤<br/>Admin"))

    %% ---------- system boundary ----------
    subgraph LMS["Logistics Management System (LMS)"]
        direction TB
        UC01(["Register account"])
        UC02(["Log in / Log out"])
        UC03(["Create shipment order"])
        UC04(["Cancel pending order"])
        UC05(["View own order history"])
        UC06(["Track parcel by<br/>tracking number"])
        UC07(["Log inbound parcel<br/>and assign shelf"])
        UC08(["Log outbound /<br/>dispatch parcel"])
        UC09(["Assign driver<br/>to shipment"])
        UC10(["View assigned<br/>delivery tasks"])
        UC11(["Update shipment status"])
        UC12(["View shipment<br/>timeline / logs"])
        UC13(["Manage user accounts<br/>create - change role - delete"])
        UC14(["View system statistics"])
    end

    %% ---------- customer ----------
    CUSTOMER --> UC01
    CUSTOMER --> UC02
    CUSTOMER --> UC03
    CUSTOMER --> UC04
    CUSTOMER --> UC05
    CUSTOMER --> UC06

    %% ---------- warehouse staff ----------
    WAREHOUSE --> UC02
    WAREHOUSE --> UC07
    WAREHOUSE --> UC08
    WAREHOUSE --> UC09
    WAREHOUSE --> UC06
    WAREHOUSE --> UC14

    %% ---------- driver ----------
    DRIVER --> UC02
    DRIVER --> UC10
    DRIVER --> UC11

    %% ---------- admin ----------
    ADMIN --> UC02
    ADMIN --> UC13
    ADMIN --> UC14
    ADMIN --> UC09
    ADMIN --> UC12

    %% ---------- include relationships ----------
    UC11 -.->|"«include»"| UC12
    UC06 -.->|"«include»"| UC12
    UC03 -.->|"«include»"| UC02
```

### Use case descriptions 

| ID | Use case | Primary actor | Pre-condition | Main flow |
| --- | --- | --- | --- | --- |
| UC01 | Register account | Customer | not logged in | fill name/email/password → account created with role `customer` → redirected to login |
| UC02 | Log in / Log out | all | – | submit credentials → session created with role → logged in user is routed to their role dashboard; logout clears the session |
| UC03 | Create shipment order | Customer | logged in | fill sender/receiver/weight → system generates a unique tracking number → status `Pending` → log entry created |
| UC04 | Cancel pending order | Customer | own order, status `Pending` | click Cancel → status `Cancelled` → log entry created |
| UC05 | View own order history | Customer | logged in | system returns only shipments where `customer_id` = own id |
| UC06 | Track parcel | any (public) | tracking number | enter tracking number → shipment + full timeline displayed |
| UC07 | Log inbound parcel & assign shelf | Warehouse | shipment `Pending` | type shelf (e.g. `A-12`) → status `Warehouse Received`, `shelf_location` saved |
| UC08 | Log outbound / dispatch | Warehouse | status `Warehouse Received` | click Dispatch → status `In Transit` |
| UC09 | Assign driver | Warehouse, Admin | shipment not finished | pick a driver from the dropdown → `driver_id` saved → log entry |
| UC10 | View assigned delivery tasks | Driver | logged in | system returns only shipments where `driver_id` = own id |
| UC11 | Update shipment status | Driver | own assignment, legal next status | choose next status (In Transit / Out for Delivery / Delivered) → status saved + log written |
| UC12 | View shipment timeline | staff, admin, tracking | shipment exists | all `logs` rows for the shipment shown in order |
| UC13 | Manage user accounts | Admin | logged in as admin | create account / change role / delete account (blocked if the user owns shipments) |
| UC14 | View system statistics | Admin, Warehouse | logged in | total orders, active shipments, delivered, cancelled, users, per-status and per-role counts |

---

## 3. Role / permission matrix 

| Capability | Customer | Warehouse | Driver | Admin |
| --- | :--: | :--: | :--: | :--: |
| Register (self sign-up) | ✅ | – | – | – |
| Create order | ✅ | – | – | ✅ (on behalf of a customer) |
| View own orders / tasks | ✅ | – | ✅ | – |
| View all shipments | – | ✅ | – | ✅ |
| Log inbound + shelf | – | ✅ | – | ✅ |
| Dispatch (In Transit) | – | ✅ | ✅ (own) | ✅ |
| Out for Delivery / Delivered | – | – | ✅ (own) | ✅ |
| Assign driver | – | ✅ | – | ✅ |
| Cancel order | ✅ (Pending only) | ✅ | – | ✅ |
| Public tracking | ✅ | ✅ | ✅ | ✅ |
| Manage users | – | – | – | ✅ |
| Dashboard statistics | – | ✅ | – | ✅ |

These rules live in one place in `app.py`:

* `ALLOWED_TRANSITIONS` – which status may follow which status
* `ROLE_STATUS_PERMISSIONS` – which role may set which status
* `@login_required("role")` – which role may call which route
