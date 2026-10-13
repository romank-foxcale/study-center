-- Mentor core schema. The evidence table is the append-only source of truth;
-- node_state is derived from it and can be rebuilt at any time (`mentor rebuild-state`).

CREATE TABLE IF NOT EXISTS meta(
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS courses(
    id         INTEGER PRIMARY KEY,
    slug       TEXT UNIQUE NOT NULL,
    goal       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS nodes(
    course_id INTEGER NOT NULL,
    node_id   TEXT NOT NULL,
    title     TEXT NOT NULL,
    type      TEXT NOT NULL,
    tier      TEXT NOT NULL,
    bloom     TEXT NOT NULL,
    minutes   INTEGER NOT NULL,
    data      TEXT NOT NULL,          -- full node JSON from graph.yaml
    PRIMARY KEY(course_id, node_id)
);

CREATE TABLE IF NOT EXISTS edges(
    course_id INTEGER NOT NULL,
    src       TEXT NOT NULL,
    dst       TEXT NOT NULL,
    kind      TEXT NOT NULL,          -- prereq | encompasses
    weight    REAL
);
CREATE INDEX IF NOT EXISTS edges_course ON edges(course_id);

CREATE TABLE IF NOT EXISTS items(
    item_id           TEXT PRIMARY KEY,
    course_id         INTEGER NOT NULL,
    node_id           TEXT NOT NULL,
    form              TEXT NOT NULL,  -- mcq|short|numeric|explain|code|proof|error-spot|two-tier|cloze
    bloom             TEXT NOT NULL,
    prompt            TEXT NOT NULL,
    answer_key        TEXT NOT NULL,  -- json
    rubric            TEXT,           -- json
    misconception_map TEXT,           -- json: option -> misconception id
    purpose           TEXT NOT NULL DEFAULT 'practice',
    created_at        TEXT NOT NULL,
    retired           INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS items_node ON items(course_id, node_id);

CREATE TABLE IF NOT EXISTS evidence(
    id             INTEGER PRIMARY KEY,
    course_id      INTEGER NOT NULL,
    node_id        TEXT NOT NULL,
    item_id        TEXT,
    ts             TEXT NOT NULL,
    session_id     TEXT,
    kind           TEXT NOT NULL,     -- see learner.EVIDENCE_KINDS
    score          REAL,
    weight         REAL,              -- implicit credit weight / inferred value
    form           TEXT,
    bloom          TEXT,
    hinted         INTEGER NOT NULL DEFAULT 0,
    hint_level     INTEGER NOT NULL DEFAULT 0,
    idk            INTEGER NOT NULL DEFAULT 0,
    confidence     INTEGER,
    latency_s      REAL,
    misconceptions TEXT,              -- json list
    grader_version TEXT,
    rationale      TEXT,
    meta           TEXT,              -- json
    voided         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS evidence_node ON evidence(course_id, node_id, ts);

CREATE TABLE IF NOT EXISTS node_state(
    course_id            INTEGER NOT NULL,
    node_id              TEXT NOT NULL,
    state                TEXT NOT NULL,
    p_learned            REAL NOT NULL,
    indep_correct        INTEGER NOT NULL DEFAULT 0,
    forms_seen           TEXT NOT NULL DEFAULT '[]',
    bloom_reached        INTEGER NOT NULL DEFAULT 0,
    misconception_passed INTEGER NOT NULL DEFAULT 0,
    explain_passed       INTEGER NOT NULL DEFAULT 0,
    learned_at           TEXT,
    mastered_at          TEXT,
    last_retrieval       TEXT,
    fsrs_card            TEXT,
    due_at               TEXT,
    deferred_until       TEXT,
    check_flag           INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(course_id, node_id)
);

-- Learner model signals (pedagogy/PERSONALIZATION.md). Global on purpose: they describe the
-- person, not a course, so a new course starts already knowing them. Append-only like evidence;
-- the model is derived by replaying them (learner_model.build).
CREATE TABLE IF NOT EXISTS signals(
    id        INTEGER PRIMARY KEY,
    ts        TEXT NOT NULL,
    course_id INTEGER,
    node_id   TEXT,
    kind      TEXT NOT NULL,          -- fact | stated | reaction | outcome
    target    TEXT,                   -- what it is about, e.g. "game-camera analogy for rotation"
    dims      TEXT,                   -- json {dimension: value}, see learner_model.DIMENSIONS
    valence   REAL,                   -- -1 (did not help) .. 1 (helped)
    adjust    TEXT,                   -- json {pace|depth|length|rigor|challenge: -1|0|1}
    weight    REAL NOT NULL DEFAULT 1,
    note      TEXT,                   -- the learner's reason, quoted where possible
    voided    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS lessons(
    lesson_id  TEXT NOT NULL,
    course_id  INTEGER NOT NULL,
    node_id    TEXT NOT NULL,
    dir        TEXT NOT NULL,
    version    INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    PRIMARY KEY(course_id, lesson_id)
);
