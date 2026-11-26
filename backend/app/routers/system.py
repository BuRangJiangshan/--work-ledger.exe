"""系统接口：元数据、设置、保存的过滤器、重复任务、数据导出与备份。"""
from __future__ import annotations

import csv
import io
import sqlite3
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, HTTPException, Response

from ..db import backup_now, get_db
from ..status import (
    ACTION_TYPES,
    CATEGORIES,
    DUE_TYPES,
    FINISH_METHODS,
    HANDLE_MODES,
    RECEIVE_METHODS,
    RELATION_TYPES,
    REPORT_CHANNELS,
    REPORT_GROUPS,
    SOURCE_TYPES,
    STATUSES,
)
from ..services import repeats as repeat_svc
from ..services.settings import get_all_settings, set_settings
from ..utils import dumps, loads, now_str, today_str

router = APIRouter(prefix="/api", tags=["system"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

STATUS_LABELS = {s["value"]: s["label"] for s in STATUSES}


@router.get("/health")
def health():
    return {"ok": True, "date": today_str()}


@router.get("/meta")
def meta(conn: sqlite3.Connection = Depends(get_db)):
    return {
        "statuses": STATUSES,
        "categories": CATEGORIES,
        "source_types": SOURCE_TYPES,
        "receive_methods": RECEIVE_METHODS,
        "due_types": DUE_TYPES,
        "report_channels": REPORT_CHANNELS,
        "finish_methods": FINISH_METHODS,
        "handle_modes": HANDLE_MODES,
        "relation_types": RELATION_TYPES,
        "action_types": ACTION_TYPES,
        "report_groups": [{"heading": h, "categories": c} for h, c in REPORT_GROUPS],
        "today": today_str(),
        "settings": get_all_settings(conn),
    }


@router.get("/settings")
def read_settings(conn: sqlite3.Connection = Depends(get_db)):
    return get_all_settings(conn)


@router.put("/settings")
def write_settings(body: dict = Body(...), conn: sqlite3.Connection = Depends(get_db)):
    result = set_settings(conn, body)
    conn.commit()
    return result


@router.get("/filters")
def list_filters(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT * FROM saved_filters ORDER BY id DESC").fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["filter_json"] = loads(d.get("filter_json"), {})
        result.append(d)
    return result


@router.post("/filters")
def create_filter(body: dict = Body(...), conn: sqlite3.Connection = Depends(get_db)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="过滤器名称不能为空")
    filter_json = body.get("filter_json") or {}
    cur = conn.execute(
        "INSERT INTO saved_filters(name, filter_json, created_at) VALUES (?, ?, ?)",
        (name, dumps(filter_json), now_str()),
    )
    row = conn.execute("SELECT * FROM saved_filters WHERE id = ?", (cur.lastrowid,)).fetchone()
    d = dict(row)
    d["filter_json"] = filter_json
    conn.commit()
    return d


@router.delete("/filters/{filter_id}")
def delete_filter(filter_id: int, conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT id FROM saved_filters WHERE id = ?", (filter_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="过滤器不存在")
    conn.execute("DELETE FROM saved_filters WHERE id = ?", (filter_id,))
    conn.commit()
    return {"ok": True}


@router.get("/repeats")
def list_repeats(conn: sqlite3.Connection = Depends(get_db)):
    return repeat_svc.list_rules(conn)


@router.post("/repeats")
def create_repeat(body: dict = Body(...), conn: sqlite3.Connection = Depends(get_db)):
    try:
        result = repeat_svc.create_rule(conn, body)
        conn.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/repeats/{rule_id}")
def update_repeat(rule_id: int, body: dict = Body(...), conn: sqlite3.Connection = Depends(get_db)):
    try:
        result = repeat_svc.update_rule(conn, rule_id, body)
        conn.commit()
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0] if exc.args else exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/repeats/{rule_id}")
def delete_repeat(rule_id: int, conn: sqlite3.Connection = Depends(get_db)):
    try:
        repeat_svc.delete_rule(conn, rule_id)
        conn.commit()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0] if exc.args else exc))
    return {"ok": True}


@router.post("/repeats/process")
def process_repeats(conn: sqlite3.Connection = Depends(get_db)):
    result = repeat_svc.process_due_rules(conn)
    conn.commit()
    return result


# ======================= 数据导出 =======================

JSON_TABLES = [
    "items",
    "process_records",
    "item_relations",
    "audit_history",
    "repeat_rules",
    "daily_close_log",
    "report_templates",
    "saved_filters",
    "app_settings",
    "item_views",
]

JSON_FIELDS = {
    "items": ("attachments",),
    "process_records": ("report_channels", "attachments"),
    "repeat_rules": ("item_template", "schedule_expr"),
    "daily_close_log": ("summary_snapshot",),
    "report_templates": ("structure",),
    "saved_filters": ("filter_json",),
    "app_settings": ("value",),
}


@router.get("/export/json")
def export_json(conn: sqlite3.Connection = Depends(get_db)):
    tables = {}
    for table in JSON_TABLES:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        data = []
        for row in rows:
            d = dict(row)
            for field in JSON_FIELDS.get(table, ()):
                d[field] = loads(d.get(field), d.get(field))
            data.append(d)
        tables[table] = data
    return {
        "app": "事项办理全程留痕工具",
        "exported_at": now_str(),
        "tables": tables,
    }


CSV_COLUMNS = [
    ("item_no", "事项编号"),
    ("title", "事项标题"),
    ("category", "类别"),
    ("source_type", "来源类型"),
    ("source_no", "来源单号"),
    ("source_unit", "来文来件单位"),
    ("receive_time", "接收时间"),
    ("receive_method", "接收方式"),
    ("due_date", "要求办结时间"),
    ("due_type", "时限性质"),
    ("estimated_days", "预计办理时长(自然日)"),
    ("status", "状态"),
    ("handle_mode", "办理模式"),
    ("current_handler", "当前承办人"),
    ("finish_time", "办结时间"),
    ("finish_method", "办结方式"),
    ("finish_summary", "结果摘要"),
    ("actual_days", "实际用时(自然日)"),
    ("delay_reason", "延期原因"),
    ("delay_applied_to", "向谁申请延期"),
    ("delay_approved", "延期是否批准"),
    ("pinned", "置顶"),
    ("merged_into", "合并去向ID"),
    ("created_at", "登记时间"),
]


def _csv_bytes(conn: sqlite3.Connection) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([label for _, label in CSV_COLUMNS])
    rows = conn.execute("SELECT * FROM items ORDER BY id").fetchall()
    for row in rows:
        d = dict(row)
        d["status"] = STATUS_LABELS.get(d["status"], d["status"])
        d["delay_approved"] = {1: "批准", 0: "未批准", None: ""}.get(d["delay_approved"], "")
        d["pinned"] = "是" if d["pinned"] else ""
        writer.writerow([d.get(key) if d.get(key) is not None else "" for key, _ in CSV_COLUMNS])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


@router.get("/export/csv")
def export_csv(conn: sqlite3.Connection = Depends(get_db)):
    filename = f"事项台账_{today_str()}.csv"
    return Response(
        content=_csv_bytes(conn),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=items.csv; filename*=UTF-8''{quote(filename)}"
        },
    )


@router.get("/export/xlsx")
def export_xlsx(conn: sqlite3.Connection = Depends(get_db)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "事项台账"
    header_fill = PatternFill("solid", fgColor="DDEBF7")
    header_font = Font(bold=True)
    ws.append([label for _, label in CSV_COLUMNS])
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
    for row in conn.execute("SELECT * FROM items ORDER BY id").fetchall():
        d = dict(row)
        d["status"] = STATUS_LABELS.get(d["status"], d["status"])
        d["delay_approved"] = {1: "批准", 0: "未批准", None: ""}.get(d["delay_approved"], "")
        d["pinned"] = "是" if d["pinned"] else ""
        ws.append([d.get(key) if d.get(key) is not None else "" for key, _ in CSV_COLUMNS])
    widths = [14, 30, 12, 16, 16, 20, 18, 12, 14, 12, 16, 12, 12, 14, 18, 12, 40, 14, 24, 16, 14, 8, 12, 18]
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.freeze_panes = "A2"

    ws2 = wb.create_sheet("过程记录")
    ws2.append(["事项编号", "事项标题", "动作类型", "动作时间", "汇报对象", "对象", "内容", "领导批示"])
    for cell in ws2[1]:
        cell.fill = header_fill
        cell.font = header_font
    rows = conn.execute(
        """
        SELECT i.item_no, i.title, pr.action_type, pr.action_time, pr.report_to,
               pr.target_person, pr.content, pr.leader_opinion
        FROM process_records pr JOIN items i ON i.id = pr.item_id
        ORDER BY pr.action_time DESC
        """
    ).fetchall()
    action_labels = {a["value"]: a["label"] for a in ACTION_TYPES}
    for row in rows:
        d = dict(row)
        d["action_type"] = action_labels.get(d["action_type"], d["action_type"])
        ws2.append(list(d.values()))
    for idx, width in enumerate([14, 30, 14, 18, 14, 14, 50, 40], start=1):
        ws2.column_dimensions[get_column_letter(idx)].width = width
    ws2.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    filename = f"事项台账_{today_str()}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type=XLSX_MIME,
        headers={
            "Content-Disposition": f"attachment; filename=items.xlsx; filename*=UTF-8''{quote(filename)}"
        },
    )


@router.post("/backup")
def create_backup():
    path = backup_now()
    return {"ok": True, "file": path, "created_at": now_str()}
