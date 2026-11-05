-- Prashi Tutorial – database schema (SQLite; written to port to PostgreSQL later)
-- Dates are stored as ISO text (YYYY-MM-DD or full ISO timestamp). Booleans are 0/1.
PRAGMA foreign_keys = ON;

-- ───────── Accounts ─────────
CREATE TABLE users (
  id            INTEGER PRIMARY KEY,
  role          TEXT NOT NULL CHECK (role IN ('admin','staff','student')),
  name          TEXT NOT NULL,
  email         TEXT UNIQUE,
  phone         TEXT,
  username      TEXT UNIQUE,                 -- students may log in with admission no.
  password_hash TEXT NOT NULL,               -- argon2id, never plain text
  must_change_password INTEGER NOT NULL DEFAULT 1,
  active        INTEGER NOT NULL DEFAULT 1,
  failed_logins INTEGER NOT NULL DEFAULT 0,
  locked_until  TEXT,
  last_login_at TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK (email IS NOT NULL OR username IS NOT NULL)
);

CREATE TABLE password_resets (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL,                  -- only the hash is stored
  expires_at TEXT NOT NULL,
  used_at    TEXT
);

-- ───────── Public content ─────────
CREATE TABLE faculty (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, subject TEXT, qualifications TEXT,
  experience TEXT, focus TEXT, bio TEXT, photo TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0, visible INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE courses (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  class_level TEXT, exam TEXT, course_type TEXT,          -- Classroom / Online / Weekend
  duration TEXT, fee_amount INTEGER,                      -- rupees; shown publicly only if show_fee = 1
  show_fee INTEGER NOT NULL DEFAULT 0,
  instalments INTEGER NOT NULL DEFAULT 1,
  subjects TEXT,                                          -- comma-separated
  highlights TEXT,                                        -- one per line
  description_html TEXT, schedule_text TEXT, image TEXT,
  faculty_id INTEGER REFERENCES faculty(id) ON DELETE SET NULL,
  sort_order INTEGER NOT NULL DEFAULT 0, visible INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE batches (
  id INTEGER PRIMARY KEY,
  course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  name TEXT NOT NULL, start_date TEXT, timing TEXT,
  seats_total INTEGER NOT NULL DEFAULT 25,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','full','closed')),
  visible INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE testimonials (
  id INTEGER PRIMARY KEY, student_name TEXT NOT NULL, exam TEXT, result_text TEXT,
  quote TEXT NOT NULL, rating INTEGER CHECK (rating BETWEEN 1 AND 5), photo TEXT,
  approved INTEGER NOT NULL DEFAULT 0, sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE results (                                    -- rank holders & yearly stats
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('rank','year_stat','improvement')),
  student_name TEXT, exam TEXT, rank_or_score TEXT, year INTEGER, value REAL, label TEXT,
  photo TEXT, approved INTEGER NOT NULL DEFAULT 0, sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE faqs (
  id INTEGER PRIMARY KEY, question TEXT NOT NULL, answer_html TEXT NOT NULL,
  course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,   -- NULL = site-wide FAQ
  sort_order INTEGER NOT NULL DEFAULT 0, visible INTEGER NOT NULL DEFAULT 1,
  publish_at TEXT, expires_at TEXT
);

CREATE TABLE notices (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, body_html TEXT NOT NULL,
  audience TEXT NOT NULL DEFAULT 'public' CHECK (audience IN ('public','students')),
  batch_id INTEGER REFERENCES batches(id) ON DELETE CASCADE,    -- optional: only that batch
  pinned INTEGER NOT NULL DEFAULT 0, publish_at TEXT, expires_at TEXT,
  visible INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE articles (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
  category TEXT, summary TEXT, cover_image TEXT, body_html TEXT,
  published INTEGER NOT NULL DEFAULT 0, publish_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT
);

CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT, help TEXT);   -- contact, social, hours, banner, map, whatsapp
CREATE TABLE holidays (id INTEGER PRIMARY KEY, label TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL);

-- ───────── Form builder & inbox ─────────
CREATE TABLE form_fields (
  id INTEGER PRIMARY KEY,
  form TEXT NOT NULL CHECK (form IN ('admission','enquiry','counselling','contact')),
  name TEXT NOT NULL,                       -- machine key, e.g. previous_school
  label TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('text','tel','email','textarea','select','date','number','checkbox')),
  options TEXT,                             -- one per line, for select
  required INTEGER NOT NULL DEFAULT 0,
  help_text TEXT, sort_order INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
  locked INTEGER NOT NULL DEFAULT 0,        -- core fields (name, phone) can't be deleted
  UNIQUE (form, name)
);

CREATE TABLE submissions (
  id INTEGER PRIMARY KEY, form TEXT NOT NULL,
  data_json TEXT NOT NULL,                  -- answers keyed by field name (validated server-side)
  status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','contacted','demo_booked','enrolled','closed')),
  assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
  consent_at TEXT NOT NULL,                 -- consent box is mandatory
  ip_hash TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE submission_notes (
  id INTEGER PRIMARY KEY, submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  author_id INTEGER REFERENCES users(id) ON DELETE SET NULL, note TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ───────── Students, fees, records ─────────
CREATE TABLE students (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  admission_no TEXT NOT NULL UNIQUE, class_level TEXT, school TEXT, dob TEXT,
  parent_name TEXT, parent_phone TEXT, parent_email TEXT,
  address TEXT, joined_on TEXT, notes_internal TEXT,
  photo TEXT                                 -- profile picture, kept in storage/private (the student edits it)
);

CREATE TABLE enrollments (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL REFERENCES students(user_id) ON DELETE CASCADE,
  batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
  fee_total INTEGER NOT NULL DEFAULT 0, discount INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','completed','dropped')),
  enrolled_on TEXT NOT NULL DEFAULT (date('now')),
  UNIQUE (student_id, batch_id)
);
-- Balance = fee_total - discount - SUM(payments.amount); calculated, never stored.
CREATE TABLE payments (
  id INTEGER PRIMARY KEY,
  enrollment_id INTEGER NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
  amount INTEGER NOT NULL CHECK (amount > 0), paid_on TEXT NOT NULL,
  mode TEXT, receipt_no TEXT, note TEXT, recorded_by INTEGER REFERENCES users(id)
);

CREATE TABLE records (                      -- study material, notes, papers, mock results, remarks
  id INTEGER PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('material','notes','test_paper','mock_result','remark')),
  title TEXT NOT NULL, body TEXT,
  file_path TEXT,                           -- under storage/private, served only via authorised route
  student_id INTEGER REFERENCES students(user_id) ON DELETE CASCADE,   -- one student, OR
  batch_id   INTEGER REFERENCES batches(id) ON DELETE CASCADE,         -- a whole batch
  score REAL, max_score REAL, record_date TEXT,
  visible_to_student INTEGER NOT NULL DEFAULT 0,   -- admin's per-record toggle
  released_at TEXT, created_by INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK (student_id IS NOT NULL OR batch_id IS NOT NULL)
);

CREATE TABLE attendance (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL REFERENCES students(user_id) ON DELETE CASCADE,
  batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
  day TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('present','absent','late','excused')),
  remark TEXT, UNIQUE (student_id, batch_id, day)
);

CREATE TABLE doubts (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL REFERENCES students(user_id) ON DELETE CASCADE,
  subject TEXT, message TEXT NOT NULL, reply TEXT, replied_by INTEGER REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','answered','closed')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')), replied_at TEXT
);

-- ───────── Safety & workflow ─────────
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  user_name TEXT, action TEXT NOT NULL,        -- create / update / delete / login / export …
  entity TEXT NOT NULL, entity_id TEXT, summary TEXT, ip TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE drafts (                           -- "preview before publishing"
  id INTEGER PRIMARY KEY, entity TEXT NOT NULL, entity_id INTEGER,
  data_json TEXT NOT NULL, author_id INTEGER REFERENCES users(id), created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_batches_course   ON batches(course_id);
CREATE INDEX idx_enroll_student   ON enrollments(student_id);
CREATE INDEX idx_records_student  ON records(student_id, visible_to_student);
CREATE INDEX idx_records_batch    ON records(batch_id, visible_to_student);
CREATE INDEX idx_attend_student   ON attendance(student_id, day);
CREATE INDEX idx_subm_status      ON submissions(form, status, created_at);
CREATE INDEX idx_audit_created    ON audit_log(created_at);
