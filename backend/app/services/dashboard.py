"""今日工作台与每日收尾数据。"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from ..status import STATUS_LABEL
from ..utils import loads, parse_date, today_str
from .items import serialize_item
from .settings import get_setting


def _unfinished(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM items WHERE merged_into IS NULL AND status != 'finished'"
        " ORDER BY (due_date IS NULL), due_date ASC, id DESC"
    ).fetchall()
    return [serialize_item(conn, r) for r in rows]


def build_dashboard(conn: sqlite3.Connection) -> dict:
    today = today_str()
    pinned = [
        serialize_item(conn, r)
        for r in conn.execute(
            "SELECT * FROM items WHERE merged_into IS NULL AND pinned = 1"
            " ORDER BY (due_date IS NULL), due_date ASC"
        ).fetchall()
    ]
    recent = [
        serialize_item(conn, r)
        for r in conn.execute(
            """
            SELECT i.* FROM item_views v JOIN items i ON i.id = v.item_id
            WHERE i.merged_into IS NULL
            ORDER BY v.viewed_at DESC LIMIT 5
            """
        ).fetchall()
    ]
    created_today = [
        serialize_item(conn, r)
        for r in conn.execute(
            "SELECT * FROM items WHERE merged_into IS NULL AND date(created_at) = ?"
            " ORDER BY id DESC",
            (today,),
        ).fetchall()
    ]

    unfinished = _unfinished(conn)
    buckets = {"red": [], "yellow": [], "green": [], "none": []}
    for item in unfinished:
        buckets[item["reminder"]].append(item)

    todo_report = [
        serialize_item(conn, r)
        for r in conn.execute(
            """
            SELECT * FROM items i
            WHERE i.merged_into IS NULL AND i.status IN ('pending', 'in_process', 'assigned', 'review')
              AND NOT EXISTS (SELECT 1 FROM process_records pr
                              WHERE pr.item_id = i.id AND pr.action_type = 'report')
            ORDER BY (i.due_date IS NULL), i.due_date ASC LIMIT 10
            """
        ).fetchall()
    ]
    urgent = [i for i in unfinished if i["remaining_days"] is not None and i["remaining_days"] <= 3]

    counts = conn.execute(
        """
        SELECT
          SUM(CASE WHEN action_type = 'report' THEN 1 ELSE 0 END) AS reports,
          SUM(CASE WHEN action_type = 'urge' THEN 1 ELSE 0 END) AS urges
        FROM process_records WHERE date(action_time) = ?
        """,
        (today,),
    ).fetchone()
    finished_today = conn.execute(
        "SELECT COUNT(*) AS c FROM items WHERE merged_into IS NULL"
        " AND status = 'finished' AND date(finish_time) = ?",
        (today,),
    ).fetchone()["c"]

    return {
        "date": today,
        "pinned": pinned,
        "recent": recent,
        "created_today": created_today,
        "red": buckets["red"],
        "yellow": buckets["yellow"],
        "green": buckets["green"],
        "no_due": buckets["none"],
        "todo_report": todo_report,
        "todo_urge": urgent,
        "counts": {
            "finished_today": finished_today,
            "reports_today": counts["reports"] or 0,
            "urges_today": counts["urges"] or 0,
            "open_total": len(unfinished),
            "overdue": sum(1 for i in unfinished if i["overdue"]),
        },
        "close_remind_time": get_setting(conn, "close_remind_time", "17:30"),
    }


def daily_summary(conn: sqlite3.Connection, day: str | None = None) -> dict:
    day = day or today_str()
    finished = [
        serialize_item(conn, r)
        for r in conn.execute(
            "SELECT * FROM items WHERE merged_into IS NULL AND status = 'finished'"
            " AND date(finish_time) = ? ORDER BY finish_time ASC",
            (day,),
        ).fetchall()
    ]
    created = [
        serialize_item(conn, r)
        for r in conn.execute(
            "SELECT * FROM items WHERE merged_into IS NULL AND date(created_at) = ?"
            " ORDER BY created_at ASC",
            (day,),
        ).fetchall()
    ]
    record_rows = conn.execute(
        """
        SELECT action_type, COUNT(*) AS c FROM process_records
        WHERE date(action_time) = ? GROUP BY action_type
        """,
        (day,),
    ).fetchall()
    counts = {r["action_type"]: r["c"] for r in record_rows}

    overdue = [
        serialize_item(conn, r)
        for r in conn.execute(
            """
            SELECT * FROM items WHERE merged_into IS NULL AND status != 'finished'
              AND due_date IS NOT NULL AND date(due_date) < ?
            ORDER BY due_date ASC
            """,
            (day,),
        ).fetchall()
    ]
    devs = [
        i["actual_days"] - i["estimated_days"]
        for i in finished
        if i.get("actual_days") is not None and i.get("estimated_days") is not None
    ]
    log = conn.execute("SELECT * FROM daily_close_log WHERE log_date = ?", (day,)).fetchone()
    if log:
        log = dict(log)
        log["summary_snapshot"] = loads(log.get("summary_snapshot"), {})

    return {
        "date": day,
        "finished": finished,
        "created": created,
        "overdue": overdue,
        "counts": {
            "finished": len(finished),
            "created": len(created),
            "urges": counts.get("urge", 0),
            "reports": counts.get("report", 0),
            "instructions": counts.get("instruction", 0),
            "overdue": len(overdue),
        },
        "deviation": {
            "count": len(devs),
            "avg": round(sum(devs) / len(devs), 1) if devs else None,
            "over_estimate": sum(1 for d in devs if d > 0),
        },
        "log": log,
    }
