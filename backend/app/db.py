"""数据库连接、初始化与备份。"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from .config import BACKUP_DIR, DB_PATH, SCHEMA_PATH, ensure_dirs
from .status import (
    BUILTIN_TEMPLATE_NAME,
    BUILTIN_TEMPLATE_STRUCTURE,
    DEFAULT_SETTINGS,
)
from .utils import dumps, now_str


def get_conn() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """FastAPI 依赖：每个请求一个连接，请求结束提交/回滚。"""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    ensure_dirs()
    conn = get_conn()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _seed(conn)
        conn.commit()
    finally:
        conn.close()


def _seed(conn: sqlite3.Connection) -> None:
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO app_settings(key, value) VALUES (?, ?)",
            (key, dumps(value)),
        )
    exists = conn.execute(
        "SELECT id FROM report_templates WHERE name = ? AND source = 'builtin'",
        (BUILTIN_TEMPLATE_NAME,),
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO report_templates(name, source, file_path, structure, created_at)"
            " VALUES (?, 'builtin', NULL, ?, ?)",
            (BUILTIN_TEMPLATE_NAME, dumps(BUILTIN_TEMPLATE_STRUCTURE), now_str()),
        )


def backup_now() -> str:
    """使用 SQLite 官方在线备份接口生成一致性备份。"""
    ensure_dirs()
    target = BACKUP_DIR / f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    src = get_conn()
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return str(target)
