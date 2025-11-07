-- ===== A) Utility Functions =====
USE inv_warehouse;
-- A.1 Get current on-hand quantity (NULL -> 0)
DROP FUNCTION IF EXISTS fn_stock_qty;
DELIMITER $$
CREATE FUNCTION fn_stock_qty(p_warehouse_id BIGINT UNSIGNED, p_item_id BIGINT UNSIGNED)
RETURNS INT
DETERMINISTIC
BEGIN
  DECLARE q INT;
  SELECT quantity INTO q
  FROM stock
  WHERE warehouse_id = p_warehouse_id AND item_id = p_item_id;
  RETURN IFNULL(q, 0);
END$$
DELIMITER ;

-- A.2 Calculate totals for a PO
DROP FUNCTION IF EXISTS fn_po_total;
DELIMITER $$
CREATE FUNCTION fn_po_total(p_po_id BIGINT UNSIGNED)
RETURNS DECIMAL(14,2)
DETERMINISTIC
BEGIN
  DECLARE tot DECIMAL(14,2);
  SELECT IFNULL(SUM(quantity * price),0.00) INTO tot
  FROM purchase_order_details
  WHERE po_id = p_po_id;
  RETURN tot;
END$$
DELIMITER ;

-- A.3 Calculate totals for a SO
DROP FUNCTION IF EXISTS fn_so_total;
DELIMITER $$
CREATE FUNCTION fn_so_total(p_so_id BIGINT UNSIGNED)
RETURNS DECIMAL(14,2)
DETERMINISTIC
BEGIN
  DECLARE tot DECIMAL(14,2);
  SELECT IFNULL(SUM(quantity * price),0.00) INTO tot
  FROM sales_order_details
  WHERE so_id = p_so_id;
  RETURN tot;
END$$
DELIMITER ;

-- ===== B) Triggers =====

-- B.1 Maintain stock rows automatically (UPSERT helper via trigger)
--    When a stock movement happens via our stored procedures,
--    we UPDATE stock.quantity; this AFTER UPDATE trigger checks thresholds.

DROP TRIGGER IF EXISTS trg_stock_after_update;
DELIMITER $$
CREATE TRIGGER trg_stock_after_update
AFTER UPDATE ON stock
FOR EACH ROW
BEGIN
  DECLARE v_reorder INT;
  -- read reorder level for the item
  SELECT reorder_level INTO v_reorder FROM item WHERE item_id = NEW.item_id;

  -- Open/ack alert if below threshold and no existing OPEN/ACK
  IF NEW.quantity < v_reorder THEN
    INSERT INTO reorder_alerts (warehouse_id, item_id, current_quantity, reorder_level, expected_quantity, status)
    SELECT NEW.warehouse_id, NEW.item_id, NEW.quantity, v_reorder, NULL, 'OPEN'
    FROM DUAL
    WHERE NOT EXISTS (
      SELECT 1 FROM reorder_alerts
      WHERE warehouse_id = NEW.warehouse_id AND item_id = NEW.item_id AND status IN ('OPEN','ACK')
    );
  ELSE
    -- Auto-resolve any open alert if stock restored
    UPDATE reorder_alerts
      SET status = 'RESOLVED'
    WHERE warehouse_id = NEW.warehouse_id
      AND item_id = NEW.item_id
      AND status IN ('OPEN','ACK');
  END IF;
END$$
DELIMITER ;

-- Keep purchase/sales header totals always correct when detail rows change
DROP TRIGGER IF EXISTS trg_pod_after_insupd;
DELIMITER $$
CREATE TRIGGER trg_pod_after_insupd
AFTER INSERT ON purchase_order_details
FOR EACH ROW
BEGIN
  UPDATE purchase_order SET total_amount = fn_po_total(NEW.po_id) WHERE po_id = NEW.po_id;
END$$
DELIMITER ;

DROP TRIGGER IF EXISTS trg_pod_after_update;
DELIMITER $$
CREATE TRIGGER trg_pod_after_update
AFTER UPDATE ON purchase_order_details
FOR EACH ROW
BEGIN
  UPDATE purchase_order SET total_amount = fn_po_total(NEW.po_id) WHERE po_id = NEW.po_id;
END$$
DELIMITER ;

DROP TRIGGER IF EXISTS trg_pod_after_delete;
DELIMITER $$
CREATE TRIGGER trg_pod_after_delete
AFTER DELETE ON purchase_order_details
FOR EACH ROW
BEGIN
  UPDATE purchase_order SET total_amount = fn_po_total(OLD.po_id) WHERE po_id = OLD.po_id;
END$$
DELIMITER ;

DROP TRIGGER IF EXISTS trg_sod_after_insupd;
DELIMITER $$
CREATE TRIGGER trg_sod_after_insupd
AFTER INSERT ON sales_order_details
FOR EACH ROW
BEGIN
  UPDATE sales_order SET total_amount = fn_so_total(NEW.so_id) WHERE so_id = NEW.so_id;
END$$
DELIMITER ;

DROP TRIGGER IF EXISTS trg_sod_after_update;
DELIMITER $$
CREATE TRIGGER trg_sod_after_update
AFTER UPDATE ON sales_order_details
FOR EACH ROW
BEGIN
  UPDATE sales_order SET total_amount = fn_so_total(NEW.so_id) WHERE so_id = NEW.so_id;
END$$
DELIMITER ;

DROP TRIGGER IF EXISTS trg_sod_after_delete;
DELIMITER $$
CREATE TRIGGER trg_sod_after_delete
AFTER DELETE ON sales_order_details
FOR EACH ROW
BEGIN
  UPDATE sales_order SET total_amount = fn_so_total(OLD.so_id) WHERE so_id = OLD.so_id;
END$$
DELIMITER ;

-- ===== C) Stored Procedures =====

-- C.1 Ensure a stock row exists (idempotent helper)
DROP PROCEDURE IF EXISTS sp_ensure_stock_row;
DELIMITER $$
CREATE PROCEDURE sp_ensure_stock_row(IN p_wh BIGINT UNSIGNED, IN p_item BIGINT UNSIGNED)
BEGIN
  INSERT INTO stock (warehouse_id, item_id, quantity)
  VALUES (p_wh, p_item, 0)
  ON DUPLICATE KEY UPDATE quantity = quantity;
END$$
DELIMITER ;

-- C.2 Receive a PO: add quantities to stock and log transactions
DROP PROCEDURE IF EXISTS sp_receive_po;
DELIMITER $$
CREATE PROCEDURE sp_receive_po(IN p_po_id BIGINT UNSIGNED, IN p_emp BIGINT UNSIGNED)
BEGIN
  DECLARE done INT DEFAULT 0;
  DECLARE v_wh BIGINT UNSIGNED;
  DECLARE v_item BIGINT UNSIGNED;
  DECLARE v_qty INT;
  DECLARE cur CURSOR FOR
    SELECT po.warehouse_id, pod.item_id, pod.quantity
    FROM purchase_order po
    JOIN purchase_order_details pod ON pod.po_id = po.po_id
    WHERE po.po_id = p_po_id;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

  -- verify header status
  IF (SELECT status FROM purchase_order WHERE po_id = p_po_id) IN ('CANCELLED','RECEIVED') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'PO cannot be received (already received or cancelled)';
  END IF;

  OPEN cur;
  read_loop: LOOP
    FETCH cur INTO v_wh, v_item, v_qty;
    IF done = 1 THEN LEAVE read_loop; END IF;

    CALL sp_ensure_stock_row(v_wh, v_item);
    UPDATE stock SET quantity = quantity + v_qty
      WHERE warehouse_id = v_wh AND item_id = v_item;

    INSERT INTO transaction_log(warehouse_id, item_id, change_type, delta_qty, ref_type, ref_id, emp_id)
    VALUES (v_wh, v_item, 'IN', v_qty, 'PO', p_po_id, p_emp);
  END LOOP;
  CLOSE cur;

  UPDATE purchase_order SET status = 'RECEIVED', total_amount = fn_po_total(p_po_id) WHERE po_id = p_po_id;
END$$
DELIMITER ;

-- C.3 Ship a SO: check availability, subtract stock, and log
DROP PROCEDURE IF EXISTS sp_ship_so;
DELIMITER $$
CREATE PROCEDURE sp_ship_so(IN p_so_id BIGINT UNSIGNED, IN p_emp BIGINT UNSIGNED)
BEGIN
  DECLARE done INT DEFAULT 0;
  DECLARE v_wh BIGINT UNSIGNED;
  DECLARE v_item BIGINT UNSIGNED;
  DECLARE v_qty INT;
  DECLARE cur CURSOR FOR
    SELECT so.warehouse_id, sod.item_id, sod.quantity
    FROM sales_order so
    JOIN sales_order_details sod ON sod.so_id = so.so_id
    WHERE so.so_id = p_so_id;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

  -- verify header status
  IF (SELECT status FROM sales_order WHERE so_id = p_so_id) IN ('CANCELLED','SHIPPED') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'SO cannot be shipped (already shipped or cancelled)';
  END IF;

  -- availability check
  IF EXISTS(
    SELECT 1
    FROM (
      SELECT sod.item_id, sod.quantity, fn_stock_qty(so.warehouse_id, sod.item_id) AS onhand
      FROM sales_order so
      JOIN sales_order_details sod ON sod.so_id = so.so_id
      WHERE so.so_id = p_so_id
    ) t
    WHERE t.onhand < t.quantity
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Insufficient stock to ship this SO';
  END IF;

  -- apply movements
  OPEN cur;
  read_loop: LOOP
    FETCH cur INTO v_wh, v_item, v_qty;
    IF done = 1 THEN LEAVE read_loop; END IF;

    CALL sp_ensure_stock_row(v_wh, v_item);
    UPDATE stock SET quantity = quantity - v_qty
      WHERE warehouse_id = v_wh AND item_id = v_item;

    INSERT INTO transaction_log(warehouse_id, item_id, change_type, delta_qty, ref_type, ref_id, emp_id)
    VALUES (v_wh, v_item, 'OUT', -v_qty, 'SO', p_so_id, p_emp);
  END LOOP;
  CLOSE cur;

  UPDATE sales_order SET status = 'SHIPPED', total_amount = fn_so_total(p_so_id) WHERE so_id = p_so_id;
END$$
DELIMITER ;

-- C.4 Manual adjustments (cycle count gains/losses)
DROP PROCEDURE IF EXISTS sp_adjust_stock;
DELIMITER $$
CREATE PROCEDURE sp_adjust_stock(
  IN p_wh BIGINT UNSIGNED,
  IN p_item BIGINT UNSIGNED,
  IN p_delta INT,
  IN p_emp BIGINT UNSIGNED,
  IN p_reason VARCHAR(255)
)
BEGIN
  CALL sp_ensure_stock_row(p_wh, p_item);
  UPDATE stock SET quantity = quantity + p_delta
  WHERE warehouse_id = p_wh AND item_id = p_item;

  INSERT INTO transaction_log(warehouse_id, item_id, change_type, delta_qty, ref_type, ref_id, emp_id)
  VALUES (p_wh, p_item, 'ADJUST', p_delta, 'MANUAL', NULL, p_emp);
END$$
DELIMITER ;

-- C.5 Convenience report procs
DROP PROCEDURE IF EXISTS sp_list_low_stock;
DELIMITER $$
CREATE PROCEDURE sp_list_low_stock(IN p_wh BIGINT UNSIGNED)
BEGIN
  SELECT s.warehouse_id, s.item_id, i.name AS item_name, s.quantity, i.reorder_level
  FROM stock s
  JOIN item i ON i.item_id = s.item_id
  WHERE s.warehouse_id = p_wh AND s.quantity < i.reorder_level
  ORDER BY (i.reorder_level - s.quantity) DESC;
END$$
DELIMITER ;


USE inv_warehouse;

-- ===== 1. Warehouse =====
INSERT INTO warehouse (name, address, city, state, zip, capacity)
VALUES
('Central Warehouse', '123 Main St', 'Bengaluru', 'KA', '560001', 100000),
('North Warehouse', '12 Industrial Rd', 'Delhi', 'DL', '110001', 80000),
('South Warehouse', '88 Ring Rd', 'Chennai', 'TN', '600001', 70000),
('East Warehouse', '45 MG Rd', 'Kolkata', 'WB', '700001', 60000);

-- ===== 2. Employee =====
INSERT INTO employee (name, role, contact, warehouse_id)
VALUES
('Rahul Mehta', 'manager', 'rahul@warehouse.com', 1),
('Ananya Sharma', 'staff', 'ananya@warehouse.com', 1),
('Vikram Rao', 'picker', 'vikram@warehouse.com', 2),
('Priya Iyer', 'staff', 'priya@warehouse.com', 3);

-- ===== 3. Item =====
INSERT INTO item (name, category, unit_of_measure, price, reorder_level)
VALUES
('Widget A', 'Widgets', 'pcs', 50.00, 20),
('Widget B', 'Widgets', 'pcs', 75.00, 30),
('Gear Box', 'Mechanical', 'pcs', 120.00, 15),
('Bearing Set', 'Mechanical', 'pcs', 40.00, 25);

-- ===== 4. Customer =====
INSERT INTO customer (name, email, phone, address)
VALUES
('Contoso Pvt Ltd', 'sales@contoso.com', '9998887771', 'Plot 12, Peenya, Bengaluru'),
('TechNova Inc', 'orders@technova.com', '8887776662', 'Sector 18, Gurugram'),
('Innova Parts', 'info@innova.com', '7776665553', 'Maraimalai Nagar, Chennai'),
('SmartSupply LLP', 'hello@smartsupply.com', '6665554444', 'Salt Lake, Kolkata');

-- ===== 5. Supplier =====
INSERT INTO supplier (name, email, phone, address)
VALUES
('Acme Supplies', 'contact@acme.com', '9123456789', 'No. 1 Industrial Estate, Bengaluru'),
('GearMax Corp', 'info@gearmax.com', '9876543210', 'Sector 5, Gurugram'),
('SteelTech Ltd', 'sales@steeltech.com', '8765432109', 'Tambaram, Chennai'),
('BearingWorks', 'support@bearingworks.com', '7654321098', 'Howrah, Kolkata');

-- ===== 6. Stock =====
INSERT INTO stock (warehouse_id, item_id, quantity)
VALUES
(1, 1, 100),
(1, 2, 50),
(2, 3, 80),
(3, 4, 40);

-- ===== 7. Transaction Log =====
INSERT INTO transaction_log (warehouse_id, item_id, change_type, delta_qty, ref_type, emp_id)
VALUES
(1, 1, 'IN', 100, 'PO', 1),
(1, 2, 'IN', 50, 'PO', 1),
(2, 3, 'IN', 80, 'PO', 3),
(3, 4, 'IN', 40, 'PO', 4);

-- ===== 8. Reorder Alerts =====
INSERT INTO reorder_alerts (warehouse_id, item_id, current_quantity, reorder_level, expected_quantity, status)
VALUES
(1, 1, 15, 20, 100, 'OPEN'),
(1, 2, 25, 30, 80, 'OPEN'),
(2, 3, 10, 15, 60, 'ACK'),
(3, 4, 5, 25, 100, 'OPEN');

-- ===== 9. Purchase Orders =====
INSERT INTO purchase_order (supplier_id, warehouse_id, po_date, status, total_amount)
VALUES
(1, 1, '2025-10-01', 'RECEIVED', 5000.00),
(2, 2, '2025-10-02', 'CREATED', 7000.00),
(3, 3, '2025-10-03', 'APPROVED', 8500.00),
(4, 4, '2025-10-04', 'CREATED', 6000.00);

-- ===== 10. Purchase Order Details =====
INSERT INTO purchase_order_details (po_id, item_id, quantity, price)
VALUES
(1, 1, 100, 50.00),
(1, 2, 50, 75.00),
(2, 3, 80, 120.00),
(3, 4, 40, 40.00);

-- ===== 11. Sales Orders =====
INSERT INTO sales_order (customer_id, warehouse_id, so_date, status, total_amount)
VALUES
(1, 1, '2025-10-05', 'SHIPPED', 4800.00),
(2, 2, '2025-10-06', 'CONFIRMED', 6500.00),
(3, 3, '2025-10-07', 'NEW', 3000.00),
(4, 4, '2025-10-08', 'CANCELLED', 1200.00);

-- ===== 12. Sales Order Details =====
INSERT INTO sales_order_details (so_id, item_id, quantity, price)
VALUES
(1, 1, 80, 60.00),
(1, 2, 20, 80.00),
(2, 3, 40, 130.00),
(3, 4, 20, 50.00);

SHOW TABLES;
SELECT * FROM customer;

-- Show all foreign keys in this database
SELECT 
    TABLE_NAME, 
    CONSTRAINT_NAME, 
    REFERENCED_TABLE_NAME, 
    UPDATE_RULE, 
    DELETE_RULE
FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = 'inv_warehouse';


-- Primary and Unique constraints
SELECT 
    TABLE_NAME, 
    CONSTRAINT_NAME, 
    CONSTRAINT_TYPE
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = 'inv_warehouse'
  AND CONSTRAINT_TYPE IN ('PRIMARY KEY','UNIQUE')
ORDER BY TABLE_NAME;


-- List all stored procedures in this database
SHOW PROCEDURE STATUS WHERE Db = 'inv_warehouse';

-- View source code of a specific procedure (example)
SHOW CREATE PROCEDURE sp_receive_po;

-- Or for all procedures:
SELECT ROUTINE_NAME, ROUTINE_DEFINITION
FROM INFORMATION_SCHEMA.ROUTINES
WHERE ROUTINE_SCHEMA = 'inv_warehouse' AND ROUTINE_TYPE = 'PROCEDURE';


-- List all functions
SHOW FUNCTION STATUS WHERE Db = 'inv_warehouse';

-- View function body
SHOW CREATE FUNCTION fn_stock_qty;

-- Or get all functions in one query
SELECT ROUTINE_NAME, ROUTINE_DEFINITION
FROM INFORMATION_SCHEMA.ROUTINES
WHERE ROUTINE_SCHEMA = 'inv_warehouse' AND ROUTINE_TYPE = 'FUNCTION';


-- Show all triggers
SHOW TRIGGERS FROM inv_warehouse;

-- View trigger definition
SHOW CREATE TRIGGER trg_stock_after_update;

-- Or use INFORMATION_SCHEMA for more detail
SELECT 
    TRIGGER_NAME,
    EVENT_MANIPULATION AS event,
    EVENT_OBJECT_TABLE AS table_name,
    ACTION_TIMING AS timing,
    ACTION_STATEMENT AS definition
FROM INFORMATION_SCHEMA.TRIGGERS
WHERE TRIGGER_SCHEMA = 'inv_warehouse'
ORDER BY EVENT_OBJECT_TABLE;
