-- Migration: Add setting to disable weekly top mentions
-- Allows users to opt-out of @mentions in weekly top announcements
-- Uses silent links instead

-- Add column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS disable_weekly_top_mention BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN users.disable_weekly_top_mention IS
  'If true, user will not be mentioned in weekly top (silent link instead)';

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_weekly_top_mention
  ON users(user_id) WHERE disable_weekly_top_mention = TRUE;
