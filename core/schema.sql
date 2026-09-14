CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  game TEXT NOT NULL,
  process TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT
);

CREATE TABLE IF NOT EXISTS samples (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sessions(id),
  ts TEXT NOT NULL,
  fps REAL,
  ping_ms REAL,
  loss_pct REAL,
  cpu_temp REAL,
  cpu_pct REAL,
  gpu_temp REAL,
  gpu_pct REAL,
  vram_used_mb REAL,
  ram_pct REAL,
  frame_ms REAL
);
CREATE INDEX IF NOT EXISTS idx_samples_session ON samples(session_id);
