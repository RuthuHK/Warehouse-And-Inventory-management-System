# Warehouse-And-Inventory-management-System
(Streamlit + MySQL)

A practical, classroom-grade **Warehouse & Inventory Management System** built with **Streamlit** (Python) and **MySQL**.  
It demonstrates real DBMS concepts—**tables**, **joins**, **aggregates**, **nested queries**, **stored procedures/functions**, and **triggers**—all wired to a simple, friendly GUI.

> Works on Windows/Linux/macOS. All state is saved in MySQL (not in memory), so updates persist across app restarts.

---

##  Features

- **Authentication (SQL-only)**
  - Uses `sp_get_menu_for_user(username, password)` or fallback `fn_auth_role` for role lookup.
  - Roles: `admin`, `worker` (admin sees full suite; worker sees Stock + Reports).

- **Purchasing (Inbound)**
  - Create Purchase Orders → add items (unit price pulled from Item master) → **Receive PO**.
  - On receive: **Stock increases** and **transaction log** is written.
  - PO totals via `fn_po_total(po_id)` (function) with `SUM()` fallback.

- **Sales (Outbound)**
  - Create Sales Orders → add items (sales price editable) → **Ship SO**.
  - On ship: **Stock decreases** and **transaction log** is written.

- **Stock & Alerts**
  - Live stock per warehouse & per item (with UOM, reorder level, price).
  - **Low-stock** section uses a **nested subquery** variant.
  - **Trigger** on `stock` keeps `reorder_alerts` table consistent.

- **Adjustments & Returns**
  - Manual adjustments (IN/OUT) with logging.
  - Customer returns (IN) and supplier returns (OUT).

- **Employees**
  - Add/delete employees; Gmail validation example; role mapping UI→DB enum.

- **Reports**
  - Month-wise Purchases, Sales, and simple P&L (Totals via `SUM` aggregates).

---

##  Tech Stack

- **Frontend**: [Streamlit](https://streamlit.io/)  
- **Database**: MySQL 8.x  
- **Python**: 3.10+  
- **DBMS Concepts**: Tables, FKs, **JOINs**, **Aggregates**, **Nested queries**, **Stored procedures/functions**, **Triggers**

---


