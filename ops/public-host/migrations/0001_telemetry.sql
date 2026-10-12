CREATE TABLE IF NOT EXISTS usage_sessions (
  session_id TEXT PRIMARY KEY,
  game_pk INTEGER NOT NULL,
  utc_day TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  active_ms INTEGER NOT NULL,
  created_ms INTEGER NOT NULL,
  updated_ms INTEGER NOT NULL,
  expires_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_expiry ON usage_sessions(expires_ms);
CREATE INDEX IF NOT EXISTS sessions_day_game ON usage_sessions(utc_day, game_pk);
CREATE TABLE IF NOT EXISTS feedback (
  feedback_id TEXT PRIMARY KEY,
  game_pk INTEGER NOT NULL,
  utc_day TEXT NOT NULL,
  rating TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_ms INTEGER NOT NULL,
  expires_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS feedback_expiry ON feedback(expires_ms);
CREATE INDEX IF NOT EXISTS feedback_day_game ON feedback(utc_day, game_pk);
CREATE TABLE IF NOT EXISTS telemetry_budget (
  utc_day TEXT NOT NULL,
  kind TEXT NOT NULL,
  used INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (utc_day, kind)
);
