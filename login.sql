-- inv_warehouse_auth_setup.sql
USE inv_warehouse;

-- ====================================================
-- 0) Safety backup of supplier (recommended)
-- ====================================================
DROP TABLE IF EXISTS supplier_bak;
CREATE TABLE supplier_bak LIKE supplier;
INSERT INTO supplier_bak SELECT * FROM supplier;

-- ====================================================
-- 1) Create app_user and role_menu tables
-- ====================================================
DROP TABLE IF EXISTS app_user;
CREATE TABLE app_user (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(100) NOT NULL UNIQUE,
  password_hash CHAR(64) NOT NULL,         -- SHA256 hex
  role ENUM('admin','worker') NOT NULL,
  emp_id INT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS role_menu;
CREATE TABLE role_menu (
  role ENUM('admin','worker') NOT NULL,
  menu_item VARCHAR(100) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  PRIMARY KEY(role, menu_item)
);

-- populate role_menu
INSERT INTO role_menu (role, menu_item, sort_order) VALUES
  ('admin','Stock',1),
  ('admin','Purchase',2),
  ('admin','Sales',3),
  ('admin','Adjust/Return',4),
  ('admin','Employees',5),
  ('admin','Reports',6),
  ('admin','Raw SQL (admin)',7),

  ('worker','Stock',1),
  ('worker','Reports',2);

-- ====================================================
-- 2) Add sample users (change passwords to secure ones)
-- ====================================================
DELETE FROM app_user WHERE username IN ('admin','worker1');
INSERT INTO app_user (username, password_hash, role)
VALUES
  ('admin', SHA2('AdminStrongPass123',256), 'admin'),
  ('worker1', SHA2('WorkerPass123',256), 'worker');

-- ====================================================
-- 3) Authentication function: fn_auth_role
--    returns 'admin' or 'worker' or NULL
-- ====================================================
DROP FUNCTION IF EXISTS fn_auth_role;
DELIMITER $$
CREATE FUNCTION fn_auth_role(p_username VARCHAR(100), p_password VARCHAR(255))
RETURNS VARCHAR(16)
DETERMINISTIC
READS SQL DATA
BEGIN
  DECLARE v_role VARCHAR(16);
  SELECT role INTO v_role
  FROM app_user
  WHERE username = p_username
    AND password_hash = SHA2(p_password,256)
  LIMIT 1;

  RETURN v_role; -- returns 'admin' or 'worker' or NULL if not found
END$$
DELIMITER ;

-- ====================================================
-- 4) Stored-proc: sp_get_menu_for_user
--    returns AUTH_FAILED row on bad credentials,
--    otherwise returns menu_item rows for the role
-- ====================================================
DROP PROCEDURE IF EXISTS sp_get_menu_for_user;
DELIMITER $$
CREATE PROCEDURE sp_get_menu_for_user(
  IN p_username VARCHAR(100),
  IN p_password VARCHAR(255)
)
BEGIN
  DECLARE v_role VARCHAR(16);

  SELECT fn_auth_role(p_username, p_password) INTO v_role;

  IF v_role IS NULL THEN
    SELECT 'AUTH_FAILED' AS status;
  ELSE
    SELECT menu_item
    FROM role_menu
    WHERE role = v_role
    ORDER BY sort_order;
  END IF;
END$$
DELIMITER ;

-- ====================================================
-- 5) Existing helper function: fn_po_total
--    (drop & recreate to ensure consistent definition)
-- ====================================================
DROP FUNCTION IF EXISTS fn_po_total;
DELIMITER $$
CREATE FUNCTION fn_po_total(p_po_id BIGINT UNSIGNED)
RETURNS DECIMAL(18,2)
DETERMINISTIC
READS SQL DATA
BEGIN
  DECLARE v_total DECIMAL(18,2) DEFAULT 0.00;
  SELECT IFNULL(SUM(quantity * price), 0.00) INTO v_total
  FROM purchase_order_details
  WHERE po_id = p_po_id;
  RETURN v_total;
END$$
DELIMITER ;

-- ====================================================
-- 6) supplier.contact column: add, populate, set NOT NULL
-- ====================================================
-- Add column if not exists (MySQL 8.0.19+ supports IF NOT EXISTS)
ALTER TABLE supplier
  ADD COLUMN IF NOT EXISTS contact VARCHAR(100) NULL AFTER name;

-- Populate contact for NULLs. Strategy: prefer phone, else email, else empty string.
UPDATE supplier
SET contact =
  CASE
    WHEN COALESCE(NULLIF(phone,''), NULLIF(email,'')) IS NOT NULL
    THEN COALESCE(NULLIF(phone,''), NULLIF(email,''))
    ELSE ''
  END
WHERE contact IS NULL;

-- Make contact NOT NULL with DEFAULT '' to be safe
ALTER TABLE supplier
  MODIFY contact VARCHAR(100) NOT NULL DEFAULT '';

-- ====================================================
-- 7) Optional: test queries (manual checks after running script)
-- ====================================================
-- SELECT fn_auth_role('admin','AdminStrongPass123') AS role_check;
-- CALL sp_get_menu_for_user('worker1','WorkerPass123');
-- SELECT fn_po_total(1) AS po1_total;