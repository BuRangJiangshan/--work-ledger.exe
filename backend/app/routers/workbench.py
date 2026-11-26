"""今日工作台、统计、每日收尾接口。"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Body, Depends, HTTPException

from ..db import get_db
from ..services import dashboard as dash
from ..services import repeats
from ..services import stats as stats_svc
from ..services.settings import get_setting
from ..utils import dumps, now_str, today_str

router = APIRouter(prefix="/api", tags=["workbench"])


@router.get("/dashboard")
def get_dashboard(conn: sqlite3.Connection = Depends(get_db)):
    repeats.process_due_rules(conn)
    return dash.build_dashboard(conn)


@router.get("/stats")
def get_stats(
    start: str | None = None,
    end: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    return stats_svc.compute_stats(conn, start, end)


@router.get("/daily-close")
def get_daily_close(
    date: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    return dash.daily_summary(conn, date)


@router.post("/daily-close")
def submit_daily_close(
    body: dict = Body(...),
    conn: sqlite3.Connection = Depends(get_db),
):
    day = body.get("date") or today_str()
    status = body.get("status")
    if status not in ("done", "skipped"):
        raise HTTPException(status_code=400, detail="收尾状态必须是 done 或 skipped")
    existing = conn.execute(
        "SELECT * FROM daily_close_log WHERE log_date = ?", (day,)
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=409, detail=f"{day} 的收尾记录已存在，同一天不能重复提交"
        )
    summary = dash.daily_summary(conn, day)
    snapshot = {
        "counts": summary["counts"],
        "deviation": summary["deviation"],
        "finished": [
            {"id": i["id"], "item_no": i["item_no"], "title": i["title"]}
            for i in summary["finished"]
        ],
        "overdue": [
            {"id": i["id"], "item_no": i["item_no"], "title": i["title"]}
            for i in summary["overdue"]
        ],
    }
    remind_time = get_setting(conn, "close_remind_time", "17:30")
    try:
        conn.execute(
            "INSERT INTO daily_close_log(log_date, remind_time, status, skip_reason,"
            " summary_snapshot, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                day,
                remind_time,
                status,
                body.get("skip_reason"),
                dumps(snapshot) if status == "done" else None,
                now_str(),
            ),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409, detail=f"{day} 的收尾记录已存在，同一天不能重复提交"
        )
    row = conn.execute("SELECT * FROM daily_close_log WHERE log_date = ?", (day,)).fetchone()
    result = dict(row)
    result["summary_snapshot"] = summary if status == "done" else None
    conn.commit()
    return result
