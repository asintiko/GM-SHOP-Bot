-- Migration: Add statistics columns
-- Date: 2025-10-24
-- Description: Add all-time message counter and other statistics columns

-- Add messages_all_time counter
ALTER TABLE chat_members ADD COLUMN IF NOT EXISTS messages_all_time INTEGER NOT NULL DEFAULT 0;

-- Add warnings/mutes/bans all-time counters (optional, can be calculated from sanctions table)
ALTER TABLE chat_members ADD COLUMN IF NOT EXISTS warnings_all_time INTEGER NOT NULL DEFAULT 0;
ALTER TABLE chat_members ADD COLUMN IF NOT EXISTS mutes_all_time INTEGER NOT NULL DEFAULT 0;
ALTER TABLE chat_members ADD COLUMN IF NOT EXISTS bans_all_time INTEGER NOT NULL DEFAULT 0;

-- Update last_message_at to TIMESTAMPTZ if not already
-- (already exists in schema, but making sure it's the right type)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='chat_members'
        AND column_name='last_message_at'
        AND data_type='timestamp with time zone'
    ) THEN
        ALTER TABLE chat_members ALTER COLUMN last_message_at TYPE TIMESTAMPTZ;
    END IF;
END $$;

-- Create index for faster statistics queries
CREATE INDEX IF NOT EXISTS idx_message_log_created_at ON message_log(chat_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sanctions_created_at ON sanctions(chat_id, target_user_id, type, created_at);
CREATE INDEX IF NOT EXISTS idx_karma_events_created_at ON karma_events(chat_id, to_user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_members_messages_week ON chat_members(chat_id, messages_week DESC);
