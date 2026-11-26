"""应用设置读写。"""
from __future__ import annotations

import sqlite3

from ..status import DEFAULT_SETTINGS
from ..utils import dumps, loads


def get_setting(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default if default is not None else DEFAULT_SETTINGS.get(key)
    return loads(row["value"], default)


def get_all_settings(conn: sqlite3.Connection) -> dict:
    result = dict(DEFAULT_SETTINGS)
    for row in conn.execute("SELECT key, value FROM app_settings"):
        result[row["key"]] = loads(row["value"], row["value"])
    return result


def set_settings(conn: sqlite3.Connection, values: dict) -> dict:
    for key, value in values.items():
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, dumps(value)),
        )
    return get_all_settings(conn)
