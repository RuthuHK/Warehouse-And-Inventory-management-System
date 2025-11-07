CREATE DATABASE IF NOT EXISTS inv_warehouse
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE inv_warehouse;

-- 1. Warehouse
CREATE TABLE IF NOT EXISTS warehouse (
  warehouse_id  BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  name          VARCHAR(120) NOT NULL UNIQUE,
  address       VARCHAR(255),
  city          VARCHAR(80),
  state         VARCHAR(80),
  zip           VARCHAR(20),
  capacity      INT UNSIGNED DEFAULT 0,
  manager_id    BIGINT UNSIGNED NULL
) ENGINE=InnoDB;

-- 2. Employee
CREATE TABLE IF NOT EXISTS employee (
  emp_id        BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  name          VARCHAR(120) NOT NULL,
  role          ENUM('manager','staff','picker','packer','driver','admin') NOT NULL DEFAULT 'staff',
  contact       VARCHAR(120),
  warehouse_id  BIGINT UNSIGNED NULL,
  CONSTRAINT fk_emp_wh_fix
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(warehouse_id)
    ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- 3. Item
CREATE TABLE IF NOT EXISTS item (
  item_id         BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  name            VARCHAR(150) NOT NULL,
  category        VARCHAR(120),
  unit_of_measure VARCHAR(40) NOT NULL DEFAULT 'pcs',
  price           DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  reorder_level   INT UNSIGNED NOT NULL DEFAULT 0,
  UNIQUE KEY uq_item_name (name)
) ENGINE=InnoDB;

-- 4. Customer
CREATE TABLE IF NOT EXISTS customer (
  customer_id  BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  name         VARCHAR(150) NOT NULL,
  email        VARCHAR(150),
  phone        VARCHAR(40),
  address      VARCHAR(255),
  UNIQUE KEY uq_customer_email (email)
) ENGINE=InnoDB;

-- 5. Supplier
CREATE TABLE IF NOT EXISTS supplier (
  supplier_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  name        VARCHAR(150) NOT NULL,
  email       VARCHAR(150),
  phone       VARCHAR(40),
  address     VARCHAR(255),
  UNIQUE KEY uq_supplier_name (name)
) ENGINE=InnoDB;

-- 6. Stock
CREATE TABLE IF NOT EXISTS stock (
  stock_id      BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  warehouse_id  BIGINT UNSIGNED NOT NULL,
  item_id       BIGINT UNSIGNED NOT NULL,
  quantity      INT NOT NULL DEFAULT 0,
  last_updated  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_stock_wh FOREIGN KEY (warehouse_id)
    REFERENCES warehouse(warehouse_id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_stock_item FOREIGN KEY (item_id)
    REFERENCES item(item_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT ck_stock_nonneg CHECK (quantity >= 0),
  UNIQUE KEY uq_stock_wh_item (warehouse_id, item_id)
) ENGINE=InnoDB;

-- 7. Transaction Log
CREATE TABLE IF NOT EXISTS transaction_log (
  log_id        BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  warehouse_id  BIGINT UNSIGNED NOT NULL,
  item_id       BIGINT UNSIGNED NOT NULL,
  change_type   ENUM('IN','OUT','ADJUST') NOT NULL,
  delta_qty     INT NOT NULL,
  ref_type      ENUM('PO','SO','MANUAL') NOT NULL DEFAULT 'MANUAL',
  ref_id        BIGINT UNSIGNED NULL,
  emp_id        BIGINT UNSIGNED NULL,
  logged_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_tlog_wh   FOREIGN KEY (warehouse_id) REFERENCES warehouse(warehouse_id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_tlog_item FOREIGN KEY (item_id)     REFERENCES item(item_id)      ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_tlog_emp  FOREIGN KEY (emp_id)      REFERENCES employee(emp_id)   ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- 8. Reorder Alerts
CREATE TABLE IF NOT EXISTS reorder_alerts (
  alert_id         BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  warehouse_id     BIGINT UNSIGNED NOT NULL,
  item_id          BIGINT UNSIGNED NOT NULL,
  current_quantity INT NOT NULL,
  reorder_level    INT NOT NULL,
  expected_quantity INT NULL,
  alert_date       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status           ENUM('OPEN','ACK','RESOLVED') NOT NULL DEFAULT 'OPEN',
  CONSTRAINT fk_alert_wh   FOREIGN KEY (warehouse_id) REFERENCES warehouse(warehouse_id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_alert_item FOREIGN KEY (item_id)     REFERENCES item(item_id)      ON UPDATE CASCADE ON DELETE RESTRICT,
  UNIQUE KEY uq_alert_open (warehouse_id, item_id, status)
) ENGINE=InnoDB;

-- 9. Purchase Order
CREATE TABLE IF NOT EXISTS purchase_order (
  po_id        BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  supplier_id  BIGINT UNSIGNED NOT NULL,
  warehouse_id BIGINT UNSIGNED NOT NULL,
  po_date      DATE NOT NULL DEFAULT (CURRENT_DATE),
  status       ENUM('CREATED','APPROVED','RECEIVED','CANCELLED') NOT NULL DEFAULT 'CREATED',
  total_amount DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  CONSTRAINT fk_po_supplier FOREIGN KEY (supplier_id)  REFERENCES supplier(supplier_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_po_wh       FOREIGN KEY (warehouse_id) REFERENCES warehouse(warehouse_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS purchase_order_details (
  po_detail_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  po_id        BIGINT UNSIGNED NOT NULL,
  item_id      BIGINT UNSIGNED NOT NULL,
  quantity     INT UNSIGNED NOT NULL,
  price        DECIMAL(12,2) NOT NULL,
  CONSTRAINT fk_pod_po   FOREIGN KEY (po_id)   REFERENCES purchase_order(po_id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_pod_item FOREIGN KEY (item_id) REFERENCES item(item_id)         ON UPDATE CASCADE ON DELETE RESTRICT,
  UNIQUE KEY uq_pod_po_item (po_id, item_id),
  CONSTRAINT ck_pod_qty CHECK (quantity > 0),
  CONSTRAINT ck_pod_price CHECK (price >= 0)
) ENGINE=InnoDB;

-- 10. Sales Order
CREATE TABLE IF NOT EXISTS sales_order (
  so_id        BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  customer_id  BIGINT UNSIGNED NOT NULL,
  warehouse_id BIGINT UNSIGNED NOT NULL,
  so_date      DATE NOT NULL DEFAULT (CURRENT_DATE),
  status       ENUM('NEW','CONFIRMED','SHIPPED','CANCELLED') NOT NULL DEFAULT 'NEW',
  total_amount DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  CONSTRAINT fk_so_customer FOREIGN KEY (customer_id)  REFERENCES customer(customer_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_so_wh       FOREIGN KEY (warehouse_id) REFERENCES warehouse(warehouse_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sales_order_details (
  so_detail_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  so_id        BIGINT UNSIGNED NOT NULL,
  item_id      BIGINT UNSIGNED NOT NULL,
  quantity     INT UNSIGNED NOT NULL,
  price        DECIMAL(12,2) NOT NULL,
  CONSTRAINT fk_sod_so   FOREIGN KEY (so_id)   REFERENCES sales_order(so_id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_sod_item FOREIGN KEY (item_id) REFERENCES item(item_id)     ON UPDATE CASCADE ON DELETE RESTRICT,
  UNIQUE KEY uq_sod_so_item (so_id, item_id),
  CONSTRAINT ck_sod_qty CHECK (quantity > 0),
  CONSTRAINT ck_sod_price CHECK (price >= 0)
) ENGINE=InnoDB;

-- 11. Link manager_id back to employee
ALTER TABLE warehouse
  ADD CONSTRAINT fk_wh_manager
  FOREIGN KEY (manager_id) REFERENCES employee(emp_id)
  ON UPDATE CASCADE ON DELETE SET NULL;

-- Check if index exists
SHOW INDEX FROM stock WHERE Key_name = 'ix_stock_last_updated';

-- Then create only if not present
CREATE INDEX ix_stock_last_updated ON stock(last_updated);
CREATE INDEX ix_tlog_item_time ON transaction_log(item_id, logged_at);

ALTER TABLE employee
  ADD COLUMN monthly_salary DECIMAL(12,2) NOT NULL DEFAULT 0.00;
