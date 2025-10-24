-- GM SHOP Bot - Initial Database Schema
-- Version: 1.0.0
-- Description: Initial schema with all core tables for bot functionality

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- CHATS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS chats (
  chat_id BIGINT PRIMARY KEY,
  title TEXT,
  settings JSONB NOT NULL DEFAULT '{}',  -- all toggles/threshold values
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chats_created_at ON chats(created_at);

-- =============================================================================
-- USERS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
  user_id BIGINT PRIMARY KEY,
  first_name TEXT,
  last_name TEXT,
  username TEXT,
  is_bot BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_username ON users(username) WHERE username IS NOT NULL;
CREATE INDEX idx_users_created_at ON users(created_at);

-- =============================================================================
-- CHAT MEMBERS TABLE (local statistics)
-- =============================================================================
CREATE TABLE IF NOT EXISTS chat_members (
  chat_id BIGINT,
  user_id BIGINT,
  joined_at TIMESTAMPTZ DEFAULT NOW(),
  karma INTEGER DEFAULT 0,
  messages_week INTEGER DEFAULT 0,
  replies_received_week INTEGER DEFAULT 0,
  reactions_received_week INTEGER DEFAULT 0,
  last_message_at TIMESTAMPTZ,
  PRIMARY KEY (chat_id, user_id),
  FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_members_karma ON chat_members(chat_id, karma DESC);
CREATE INDEX idx_chat_members_messages ON chat_members(chat_id, messages_week DESC);
CREATE INDEX idx_chat_members_joined ON chat_members(chat_id, joined_at);

-- =============================================================================
-- SANCTIONS/HISTORY TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS sanctions (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT,
  target_user_id BIGINT,
  moderator_id BIGINT,
  type TEXT CHECK (type IN ('warn','mute','ban','kick','unmute','unban','unwarn')),
  reason TEXT,
  duration_seconds INTEGER,   -- null for 'forever'
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ,
  is_active BOOLEAN DEFAULT TRUE,
  FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
  FOREIGN KEY (target_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (moderator_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_sanctions_chat_user ON sanctions(chat_id, target_user_id);
CREATE INDEX idx_sanctions_expires ON sanctions(expires_at) WHERE is_active = TRUE;
CREATE INDEX idx_sanctions_type ON sanctions(chat_id, type);
CREATE INDEX idx_sanctions_created ON sanctions(created_at);

-- =============================================================================
-- MESSAGE LOG TABLE (for antiflood "6 in a row")
-- =============================================================================
CREATE TABLE IF NOT EXISTS message_log (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT,
  user_id BIGINT,
  message_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_message_log_chat_time ON message_log(chat_id, created_at DESC);
CREATE INDEX idx_message_log_user_time ON message_log(chat_id, user_id, created_at DESC);

-- Auto-cleanup old messages (keep only last 7 days)
-- This will be handled by a scheduled job in the bot

-- =============================================================================
-- KARMA EVENTS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS karma_events (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT,
  from_user_id BIGINT,
  to_user_id BIGINT,
  delta SMALLINT CHECK (delta IN (-1, 1)),
  reason TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
  FOREIGN KEY (from_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (to_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_karma_events_chat_to_user ON karma_events(chat_id, to_user_id, created_at DESC);
CREATE INDEX idx_karma_events_from_to ON karma_events(chat_id, from_user_id, to_user_id, created_at DESC);

-- =============================================================================
-- GIVEAWAYS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS giveaways (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT,
  title TEXT NOT NULL,
  description TEXT,
  winners_count INTEGER DEFAULT 1,
  status TEXT CHECK (status IN ('scheduled','active','finished','cancelled')) DEFAULT 'scheduled',
  start_at TIMESTAMPTZ,
  end_at TIMESTAMPTZ,
  rules JSONB DEFAULT '{}',  -- requirements/filters
  created_by BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_giveaways_chat_status ON giveaways(chat_id, status);
CREATE INDEX idx_giveaways_end_at ON giveaways(end_at) WHERE status = 'active';

-- =============================================================================
-- GIVEAWAY ENTRIES TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS giveaway_entries (
  id BIGSERIAL PRIMARY KEY,
  giveaway_id BIGINT,
  user_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (giveaway_id, user_id),
  FOREIGN KEY (giveaway_id) REFERENCES giveaways(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_giveaway_entries_giveaway ON giveaway_entries(giveaway_id);

-- =============================================================================
-- GIVEAWAY WINNERS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS giveaway_winners (
  id BIGSERIAL PRIMARY KEY,
  giveaway_id BIGINT,
  user_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (giveaway_id) REFERENCES giveaways(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_giveaway_winners_giveaway ON giveaway_winners(giveaway_id);

-- =============================================================================
-- MARRIAGES TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS marriages (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT,
  user1 BIGINT,
  user2 BIGINT,
  married_at TIMESTAMPTZ DEFAULT NOW(),
  divorced_at TIMESTAMPTZ,
  FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
  FOREIGN KEY (user1) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (user2) REFERENCES users(user_id) ON DELETE CASCADE,
  CHECK (user1 < user2)  -- Ensure consistent ordering
);

CREATE UNIQUE INDEX idx_marriages_user1_active ON marriages(chat_id, user1) WHERE divorced_at IS NULL;
CREATE UNIQUE INDEX idx_marriages_user2_active ON marriages(chat_id, user2) WHERE divorced_at IS NULL;
CREATE INDEX idx_marriages_married_at ON marriages(chat_id, married_at);

-- =============================================================================
-- MARRIAGE PROPOSALS TABLE (for tracking pending proposals)
-- =============================================================================
CREATE TABLE IF NOT EXISTS marriage_proposals (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT,
  from_user_id BIGINT,
  to_user_id BIGINT,
  status TEXT CHECK (status IN ('pending','accepted','declined','expired')) DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ,
  FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
  FOREIGN KEY (from_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (to_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_marriage_proposals_to_user ON marriage_proposals(chat_id, to_user_id, status);
CREATE INDEX idx_marriage_proposals_expires ON marriage_proposals(expires_at) WHERE status = 'pending';

-- =============================================================================
-- STAFF TABLE (admin roles)
-- =============================================================================
CREATE TABLE IF NOT EXISTS staff (
  chat_id BIGINT,
  user_id BIGINT,
  role TEXT CHECK (role IN ('owner','admin','moderator')),
  added_by BIGINT,
  added_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (chat_id, user_id),
  FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (added_by) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_staff_role ON staff(chat_id, role);

-- =============================================================================
-- AUDIT LOG TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT,
  actor_id BIGINT,
  action TEXT NOT NULL,
  payload JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
  FOREIGN KEY (actor_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_audit_log_chat_time ON audit_log(chat_id, created_at DESC);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_actor ON audit_log(actor_id);

-- =============================================================================
-- WEEKLY TOPS TABLE (to store historical weekly top results)
-- =============================================================================
CREATE TABLE IF NOT EXISTS weekly_tops (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT,
  week_start TIMESTAMPTZ NOT NULL,
  week_end TIMESTAMPTZ NOT NULL,
  results JSONB NOT NULL,  -- stores top users with their scores
  created_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE
);

CREATE INDEX idx_weekly_tops_chat_week ON weekly_tops(chat_id, week_start DESC);

-- =============================================================================
-- FILTERS TABLE (for storing custom word/regex filters)
-- =============================================================================
CREATE TABLE IF NOT EXISTS filters (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT,
  filter_type TEXT CHECK (filter_type IN ('word','regex','link')) NOT NULL,
  pattern TEXT NOT NULL,
  action TEXT CHECK (action IN ('warn','mute','ban','delete')) DEFAULT 'delete',
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE
);

CREATE INDEX idx_filters_chat_type ON filters(chat_id, filter_type) WHERE is_active = TRUE;

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Update updated_at timestamp on chats
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_chats_updated_at BEFORE UPDATE ON chats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_giveaways_updated_at BEFORE UPDATE ON giveaways
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- DEFAULT DATA
-- =============================================================================

-- Insert default filter patterns (from Appendix A in the specification)
-- These can be customized later through the bot's admin panel

COMMENT ON TABLE chats IS 'Stores information about Telegram chats where the bot is active';
COMMENT ON TABLE users IS 'Stores information about all users the bot has encountered';
COMMENT ON TABLE chat_members IS 'Tracks user membership and statistics within specific chats';
COMMENT ON TABLE sanctions IS 'Records all moderation actions (bans, mutes, warns, etc.)';
COMMENT ON TABLE message_log IS 'Temporary log of recent messages for antiflood detection';
COMMENT ON TABLE karma_events IS 'Records all karma changes between users';
COMMENT ON TABLE giveaways IS 'Stores information about contests and giveaways';
COMMENT ON TABLE marriages IS 'Tracks user marriages within chats';
COMMENT ON TABLE staff IS 'Defines admin and moderator roles for chats';
COMMENT ON TABLE audit_log IS 'Comprehensive audit trail of all bot actions';

-- End of migration
