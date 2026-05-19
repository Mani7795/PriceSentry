-- Phase 2: users, conversations, messages, citations
-- Runs after init.sql on first DB start.

-- ─────────────────────────────────────────────────────────────────────
-- USERS
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  user_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email            TEXT NOT NULL UNIQUE,
  password_hash    TEXT NOT NULL,
  full_name        TEXT,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  is_admin         BOOLEAN NOT NULL DEFAULT FALSE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_login_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users (LOWER(email));

-- ─────────────────────────────────────────────────────────────────────
-- REFRESH TOKENS  (one row per active session per user)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS refresh_tokens (
  token_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  token_hash       TEXT NOT NULL UNIQUE,   -- SHA-256 of the raw token; raw never stored
  issued_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at       TIMESTAMPTZ NOT NULL,
  revoked_at       TIMESTAMPTZ,
  user_agent       TEXT,
  ip_address       INET,
  replaced_by      UUID REFERENCES refresh_tokens(token_id)   -- rotation chain
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_active
  ON refresh_tokens (user_id) WHERE revoked_at IS NULL;

-- ─────────────────────────────────────────────────────────────────────
-- CONVERSATIONS
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
  conversation_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  title            TEXT NOT NULL DEFAULT 'New conversation',
  brand_filter     TEXT,                                  -- optional retrieval filter
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conversations_user_recent
  ON conversations (user_id, updated_at DESC);

-- ─────────────────────────────────────────────────────────────────────
-- MESSAGES
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
  message_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id  UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
  role             TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content          TEXT NOT NULL,
  model            TEXT,                                  -- which model produced it
  prompt_tokens    INTEGER,
  completion_tokens INTEGER,
  latency_ms       INTEGER,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_conv_time
  ON messages (conversation_id, created_at);

-- ─────────────────────────────────────────────────────────────────────
-- MESSAGE CITATIONS  (the reviews that grounded an assistant message)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS message_citations (
  citation_id      BIGSERIAL PRIMARY KEY,
  message_id       UUID NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
  review_id        UUID NOT NULL REFERENCES reviews(review_id),
  rank             INTEGER NOT NULL,
  similarity       REAL,
  snippet          TEXT,
  UNIQUE (message_id, review_id)
);
CREATE INDEX IF NOT EXISTS idx_citations_message ON message_citations (message_id);

-- ─────────────────────────────────────────────────────────────────────
-- FEEDBACK  (thumbs up/down per assistant message)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS message_feedback (
  feedback_id      BIGSERIAL PRIMARY KEY,
  message_id       UUID NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
  user_id          UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  rating           SMALLINT NOT NULL CHECK (rating IN (-1, 0, 1)),
  comment          TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (message_id, user_id)
);

-- ─────────────────────────────────────────────────────────────────────
-- AUDIT LOG  (lightweight: just append-only events)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
  audit_id         BIGSERIAL PRIMARY KEY,
  user_id          UUID REFERENCES users(user_id) ON DELETE SET NULL,
  event_type       TEXT NOT NULL,        -- 'login.success', 'login.failed', 'auth.refresh', ...
  ip_address       INET,
  user_agent       TEXT,
  metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_user_time ON audit_log (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_log (event_type, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────
-- updated_at triggers
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated ON users;
CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_conversations_updated ON conversations;
CREATE TRIGGER trg_conversations_updated BEFORE UPDATE ON conversations
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DO $$
BEGIN
  RAISE NOTICE 'Phase 2 schema initialized successfully.';
END $$;
