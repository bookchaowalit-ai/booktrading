-- +migrate Up
-- The gRPC strategy has no authenticated user context.  The old default
-- value "default" violated the users foreign key because no such user exists.
ALTER TABLE orders ALTER COLUMN user_id DROP DEFAULT;
