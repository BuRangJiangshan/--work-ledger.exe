PRAGMA foreign_keys = ON;

-- ================= 事项主表 =================
CREATE TABLE IF NOT EXISTS items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    item_no          TEXT    UNIQUE,               -- 事项编号（SX2026-0001）
    title            TEXT    NOT NULL,             -- 事项标题
    category         TEXT    NOT NULL,             -- 类别
    source_type      TEXT    NOT NULL,             -- 来源类型
    source_no        TEXT,                         -- 来源单号
    source_unit      TEXT,                         -- 来文来件单位
    receive_time     TEXT    NOT NULL,             -- 接收时间（ISO8601，分钟）
    receive_method   TEXT,                         -- 接收方式
    due_date         TEXT,                         -- 要求办结时间（延期批准后更新）
    original_due_date TEXT,                        -- 原始要求办结时间（统计口径用）
    due_type         TEXT    DEFAULT 'clear',      -- clear/convention/none
    estimated_days   REAL,                         -- 预计办理时长（自然日）
    status           TEXT    DEFAULT 'pending',    -- pending/in_process/review/assigned/finished/delayed/suspended
    handle_mode      TEXT    DEFAULT 'self',       -- self/assigned
    current_handler  TEXT,                         -- 当前承办人
    finish_time      TEXT,                         -- 办结时间（办结动作时间戳）
    finish_method    TEXT,                         -- 办结方式
    finish_summary   TEXT,                         -- 结果摘要
    actual_days      REAL,                         -- 实际用时（自然日）
    delay_reason     TEXT,                         -- 延期原因
    delay_applied_to TEXT,                         -- 向谁申请延期
    delay_approved   INTEGER,                      -- NULL未申请/0未批/1批准
    is_master        INTEGER DEFAULT 1,            -- 是否主事项
    merged_into      INTEGER REFERENCES items(id), -- 已合并至主事项
    pinned           INTEGER DEFAULT 0,            -- 置顶
    attachments      TEXT,                         -- JSON数组
    repeat_rule_id   INTEGER,                      -- 重复任务规则来源
    created_at       TEXT    NOT NULL,
    updated_at       TEXT    NOT NULL
);

-- ================= 过程记录表 =================
CREATE TABLE IF NOT EXISTS process_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         INTEGER NOT NULL REFERENCES items(id),
    action_type     TEXT    NOT NULL,
    action_time     TEXT    NOT NULL,
    report_channels TEXT,               -- JSON数组（多选）
    report_to       TEXT,
    target_person   TEXT,
    content         TEXT    NOT NULL,
    leader_opinion  TEXT,
    attachments     TEXT,               -- JSON数组
    origin_item_id  INTEGER,            -- 合并前原事项id
    created_at      TEXT    NOT NULL
);

-- ================= 事项关系表 =================
CREATE TABLE IF NOT EXISTS item_relations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    master_item_id   INTEGER NOT NULL REFERENCES items(id),
    related_item_id  INTEGER NOT NULL REFERENCES items(id),
    relation_type    TEXT    NOT NULL,   -- related/parent_child/duplicate
    created_time     TEXT    NOT NULL,
    created_method   TEXT,               -- manual/system_confirmed
    note             TEXT
);

-- ================= 审计历史（append-only） =================
CREATE TABLE IF NOT EXISTS audit_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    obj_type    TEXT    NOT NULL,
    obj_id      INTEGER NOT NULL,
    field_name  TEXT,
    old_value   TEXT,
    new_value   TEXT,
    op_time     TEXT    NOT NULL,
    op_source   TEXT,
    operator    TEXT    DEFAULT 'self'
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_history
BEGIN SELECT RAISE(ABORT, 'audit_history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_history
BEGIN SELECT RAISE(ABORT, 'audit_history is append-only'); END;

-- ================= 重复任务规则表 =================
CREATE TABLE IF NOT EXISTS repeat_rules (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL,
    item_template    TEXT    NOT NULL,
    trigger_type     TEXT    NOT NULL,   -- fixed/after_done
    schedule_expr    TEXT,
    after_done_days  INTEGER,
    backlog_strategy TEXT    DEFAULT 'keep_all',
    next_run_time    TEXT,
    enabled          INTEGER DEFAULT 1,
    created_at       TEXT    NOT NULL
);

-- ================= 每日收尾日志 =================
CREATE TABLE IF NOT EXISTS daily_close_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    log_date         TEXT    NOT NULL UNIQUE,
    remind_time      TEXT    NOT NULL,
    status           TEXT    NOT NULL,   -- done/skipped
    skip_reason      TEXT,
    summary_snapshot TEXT,
    created_at       TEXT    NOT NULL
);

-- ================= 汇报模板 =================
CREATE TABLE IF NOT EXISTS report_templates (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    source       TEXT    NOT NULL,   -- builtin/imported/custom
    file_path    TEXT,
    structure    TEXT,               -- JSON
    created_at   TEXT    NOT NULL
);

-- ================= 保存的过滤器 =================
CREATE TABLE IF NOT EXISTS saved_filters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    filter_json TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);

-- ================= 应用设置 =================
CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ================= 最近查看 =================
CREATE TABLE IF NOT EXISTS item_views (
    item_id   INTEGER PRIMARY KEY REFERENCES items(id),
    viewed_at TEXT NOT NULL
);

-- ================= 索引 =================
CREATE INDEX IF NOT EXISTS idx_items_status_due ON items(status, due_date);
CREATE INDEX IF NOT EXISTS idx_items_category     ON items(category, receive_time);
CREATE INDEX IF NOT EXISTS idx_proc_item_time     ON process_records(item_id, action_time);
CREATE INDEX IF NOT EXISTS idx_proc_action_time   ON process_records(action_type, action_time);
CREATE INDEX IF NOT EXISTS idx_audit_obj          ON audit_history(obj_type, obj_id, op_time);
