"""审计历史写入（append-only）。"""
from __future__ import annotations

import json
import sqlite3

from .utils import now_str


def _text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def log_audit(
    conn: sqlite3.Connection,
    obj_type: str,
    obj_id: int,
    field_name: str | None = None,
    old_value=None,
    new_value=None,
    op_source: str = "local",
    operator: str = "self",
) -> None:
    conn.execute(
        "INSERT INTO audit_history(obj_type, obj_id, field_name, old_value, new_value,"
        " op_time, op_source, operator) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            obj_type,
            obj_id,
            field_name,
            _text(old_value),
            _text(new_value),
            now_str(),
            op_source,
            operator,
        ),
    )


def log_field_changes(
    conn: sqlite3.Connection,
    obj_type: str,
    obj_id: int,
    old_row: dict,
    new_row: dict,
    fields: list[str],
    op_source: str = "local",
) -> None:
    for field in fields:
        old = old_row.get(field)
        new = new_row.get(field)
        if old != new:
            log_audit(conn, obj_type, obj_id, field, old, new, op_source=op_source)
