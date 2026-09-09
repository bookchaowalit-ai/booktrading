-- +migrate Down
ALTER TABLE orders ALTER COLUMN user_id SET DEFAULT 'default';
