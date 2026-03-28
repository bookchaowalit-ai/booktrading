-- Rollback migration 005

DROP TRIGGER IF EXISTS update_sltp_updated_at ON stop_loss_take_profit;
DROP TABLE IF EXISTS stop_loss_take_profit;

DROP TABLE IF EXISTS notifications;

DROP TRIGGER IF EXISTS update_journal_updated_at ON journal_entries;
DROP TABLE IF EXISTS journal_entries;
