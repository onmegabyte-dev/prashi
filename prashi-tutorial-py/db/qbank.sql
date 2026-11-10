-- ───────── Question bank ─────────
-- Safe to run on every start (IF NOT EXISTS). Questions are never tied to the person who uploaded them:
-- deleting a teacher/admin login (or a batch) only blanks the link; the name is kept as plain text.
CREATE TABLE IF NOT EXISTS qb_uploads (          -- one row per uploaded file
  id INTEGER PRIMARY KEY,
  batch_id INTEGER REFERENCES batches(id) ON DELETE SET NULL, batch_name TEXT,
  class_level TEXT NOT NULL, subject TEXT NOT NULL, chapter TEXT NOT NULL, q_type TEXT NOT NULL,
  file_name TEXT, file_kind TEXT,                 -- pdf / docx / txt
  question_count INTEGER NOT NULL DEFAULT 0, skipped_count INTEGER NOT NULL DEFAULT 0,
  uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL, uploaded_by_name TEXT, uploaded_by_role TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS qb_counters (         -- last qid handed out per group, so a deleted qid is never used again
  class_level TEXT NOT NULL COLLATE NOCASE, subject TEXT NOT NULL COLLATE NOCASE, chapter TEXT NOT NULL COLLATE NOCASE, q_type TEXT NOT NULL COLLATE NOCASE,
  last_qid INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (class_level, subject, chapter, q_type)
);

CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY,
  -- the grain: class + subject + chapter + question type + qid (qid counts up inside that group)
  class_level TEXT NOT NULL COLLATE NOCASE, subject TEXT NOT NULL COLLATE NOCASE, chapter TEXT NOT NULL COLLATE NOCASE, q_type TEXT NOT NULL COLLATE NOCASE,
  qid INTEGER NOT NULL,
  question_text TEXT NOT NULL, answer_text TEXT, text_key TEXT NOT NULL,      -- text_key = lower-case, single-spaced text, used to skip duplicates
  batch_id INTEGER REFERENCES batches(id) ON DELETE SET NULL, batch_name TEXT,
  upload_id INTEGER REFERENCES qb_uploads(id) ON DELETE SET NULL,
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL, created_by_name TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (class_level, subject, chapter, q_type, qid),
  UNIQUE (class_level, subject, chapter, q_type, text_key)
);
CREATE INDEX IF NOT EXISTS idx_questions_group ON questions(class_level, subject, chapter, q_type);
CREATE INDEX IF NOT EXISTS idx_questions_batch ON questions(batch_id);

-- A teacher publishes question types of a chapter to students: to all students of a class (batch_id NULL) or to the students of one batch.
-- Published students see those questions, with their answers, in the student portal (Class > Subject > Chapter > Question type).
CREATE TABLE IF NOT EXISTS chapter_access (
  id INTEGER PRIMARY KEY,
  class_level TEXT NOT NULL COLLATE NOCASE, subject TEXT NOT NULL COLLATE NOCASE, chapter TEXT NOT NULL COLLATE NOCASE, q_type TEXT NOT NULL COLLATE NOCASE,
  batch_id INTEGER REFERENCES batches(id) ON DELETE CASCADE,
  enabled_by INTEGER REFERENCES users(id) ON DELETE SET NULL, enabled_by_name TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_chapter_access_uq ON chapter_access(class_level, subject, chapter, q_type, COALESCE(batch_id, 0));
