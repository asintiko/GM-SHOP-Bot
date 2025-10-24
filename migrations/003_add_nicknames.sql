-- Migration: Add nicknames support
-- Date: 2025-10-24
-- Description: Add nickname column to chat_members with uniqueness constraint per chat

-- Add nickname column
ALTER TABLE chat_members ADD COLUMN IF NOT EXISTS nickname VARCHAR(32);

-- Create unique index for nicknames per chat (case-insensitive)
CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_members_nickname_unique
ON chat_members (chat_id, LOWER(nickname))
WHERE nickname IS NOT NULL;

-- Create index for faster nickname lookups
CREATE INDEX IF NOT EXISTS idx_chat_members_nickname
ON chat_members (chat_id, nickname)
WHERE nickname IS NOT NULL;
