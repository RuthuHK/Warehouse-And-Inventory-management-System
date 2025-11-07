DELIMITER //

DROP FUNCTION IF EXISTS inv_warehouse.fn_po_total;
//

CREATE FUNCTION inv_warehouse.fn_po_total(p_po_id INT)
RETURNS DECIMAL(18,2)
DETERMINISTIC
READS SQL DATA
BEGIN
  DECLARE v_total DECIMAL(18,2) DEFAULT 0.00;
  SELECT IFNULL(SUM(quantity * price), 0.00) INTO v_total
  FROM purchase_order_details
  WHERE po_id = p_po_id;
  RETURN v_total;
END;
//
DELIMITER ;


USE inv_warehouse;

ALTER TABLE supplier
  ADD COLUMN contact VARCHAR(100) NULL AFTER name;


USE inv_warehouse;

-- 1) fill NULL contacts (safe-update-friendly)
UPDATE supplier
SET contact = ''
WHERE contact IS NULL
  AND supplier_id > 0;

-- 2) Now make it NOT NULL
ALTER TABLE supplier
  MODIFY contact VARCHAR(100) NOT NULL;





   -- to resolve the reorder level 
DROP TRIGGER IF EXISTS trg_stock_after_update;
DELIMITER $$
CREATE TRIGGER trg_stock_after_update
AFTER UPDATE ON stock
FOR EACH ROW
BEGIN
  DECLARE v_reorder INT;
  DECLARE v_wh INT;
  DECLARE v_item INT;
  DECLARE v_qty INT;
  DECLARE v_has_resolved INT DEFAULT 0;

  -- copy NEW.* into vars
  SET v_wh = NEW.warehouse_id;
  SET v_item = NEW.item_id;
  SET v_qty = NEW.quantity;

  -- get reorder level
  SELECT reorder_level INTO v_reorder
  FROM item
  WHERE item_id = v_item;

  IF v_qty < v_reorder THEN
    -- below threshold → make sure we have one OPEN
    INSERT INTO reorder_alerts
      (warehouse_id, item_id, current_quantity, reorder_level, expected_quantity, status)
    SELECT v_wh, v_item, v_qty, v_reorder, NULL, 'OPEN'
    FROM DUAL
    WHERE NOT EXISTS (
      SELECT 1
      FROM reorder_alerts
      WHERE warehouse_id = v_wh
        AND item_id = v_item
        AND status IN ('OPEN','ACK')
    );
  ELSE
    -- above threshold → first check if a RESOLVED already exists
    SELECT COUNT(*) INTO v_has_resolved
    FROM reorder_alerts
    WHERE warehouse_id = v_wh
      AND item_id = v_item
      AND status = 'RESOLVED';

    IF v_has_resolved > 0 THEN
      -- we already have (wh,item,'RESOLVED'), so just clean up extra OPEN/ACK
      DELETE FROM reorder_alerts
      WHERE warehouse_id = v_wh
        AND item_id = v_item
        AND status IN ('OPEN','ACK');
    ELSE
      -- no resolved yet → it's safe to turn latest OPEN/ACK into RESOLVED
      UPDATE reorder_alerts
      SET status = 'RESOLVED',
          current_quantity = v_qty
      WHERE warehouse_id = v_wh
        AND item_id = v_item
        AND status IN ('OPEN','ACK')
      ORDER BY alert_date DESC
      LIMIT 1;
    END IF;
  END IF;
END$$
DELIMITER ;
-- to clear the duplicated resolve status
DELETE FROM reorder_alerts
WHERE warehouse_id = 1
  AND item_id = 1
  AND status = 'RESOLVED'
LIMIT 1;

-- just testing
UPDATE stock
SET quantity = 100
WHERE warehouse_id = 1 AND item_id = 1;







USE inv_warehouse;

SELECT *FROM purchase_order
ORDER BY po_id DESC 
LIMIT 5;


-- After you add in UI (name + contact), re-run:
SELECT COUNT(*) AS after_cnt FROM supplier;

-- Quickly find the latest row
SELECT supplier_id, name, contact, email, phone, address
FROM supplier
ORDER BY supplier_id DESC
LIMIT 5;

 -- to check employees after updating
SELECT emp_id, name, role, contact, warehouse_id
FROM employee
ORDER BY emp_id DESC
LIMIT 10;




