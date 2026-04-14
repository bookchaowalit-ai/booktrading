-- +migrate Down
ALTER TABLE orders DROP CONSTRAINT IF EXISTS fk_orders_user_id;
DROP TABLE IF EXISTS users;
