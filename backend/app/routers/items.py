"""事项、过程记录、关联、附件、全局时间线接口。"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile

from ..config import ATTACH_DIR
from ..db import get_db
from ..services import items as svc
from ..utils import loads

router = APIRouter(prefix="/api", tags=["items"])


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0] if exc.args else exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/items")
def list_items(
    q: str | None = None,
    category: str | None = None,
    source_type: str | None = None,
    status: str | None = None,
    handle_mode: str | None = None,
    due_from: str | None = None,
    due_to: str | None = None,
    receive_from: str | None = None,
    receive_to: str | None = None,
    finished_from: str | None = None,
    finished_to: str | None = None,
    pinned: bool = False,
    include_merged: bool = False,
    overdue: bool = False,
    instruction: bool = False,
    sort: str = "recent",
    page: int = 1,
    page_size: int = Query(20, le=200),
    conn: sqlite3.Connection = Depends(get_db),
):
    return svc.list_items(
        conn,
        {
            "q": q,
            "category": category,
            "source_type": source_type,
            "status": status,
            "handle_mode": handle_mode,
            "due_from": due_from,
            "due_to": due_to,
            "receive_from": receive_from,
            "receive_to": receive_to,
            "finished_from": finished_from,
            "finished_to": finished_to,
            "pinned": pinned,
            "include_merged": include_merged,
            "overdue": "1" if overdue else None,
            "instruction": "1" if instruction else None,
            "sort": sort,
            "page": page,
            "page_size": page_size,
        },
    )


@router.post("/items")
def create_item(body: dict = Body(...), conn: sqlite3.Connection = Depends(get_db)):
    result = _run(svc.create_item, conn, body)
    conn.commit()
    return result


@router.get("/items/{item_id}")
def get_item(item_id: int, conn: sqlite3.Connection = Depends(get_db)):
    detail = _run(svc.get_item_detail, conn, item_id)
    svc.touch_view(conn, item_id)
    return detail


@router.patch("/items/{item_id}")
def update_item(item_id: int, body: dict = Body(...), conn: sqlite3.Connection = Depends(get_db)):
    result = _run(svc.update_item, conn, item_id, body)
    conn.commit()
    return result


@router.post("/items/{item_id}/pin")
def pin_item(item_id: int, body: dict = Body(...), conn: sqlite3.Connection = Depends(get_db)):
    result = _run(svc.set_pin, conn, item_id, bool(body.get("pinned")))
    conn.commit()
    return result


@router.post("/items/{item_id}/view")
def view_item(item_id: int, conn: sqlite3.Connection = Depends(get_db)):
    _run(svc.touch_view, conn, item_id)
    conn.commit()
    return {"ok": True}


@router.post("/items/{item_id}/merge")
def merge_item(item_id: int, body: dict = Body(...), conn: sqlite3.Connection = Depends(get_db)):
    master_id = body.get("master_id")
    if not master_id:
        raise HTTPException(status_code=400, detail="请选择主事项")
    result = _run(svc.merge_items, conn, item_id, int(master_id), body.get("note"))
    conn.commit()
    return result


@router.get("/items/{item_id}/audit")
def item_audit(item_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return _run(svc.list_audit, conn, item_id)


@router.post("/items/{item_id}/records")
def create_record(item_id: int, body: dict = Body(...), conn: sqlite3.Connection = Depends(get_db)):
    result = _run(svc.create_record, conn, item_id, body)
    conn.commit()
    return result


@router.get("/items/{item_id}/records")
def list_records(item_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return _run(svc.list_records, conn, item_id)


@router.get("/relations")
def list_relations(item_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return _run(svc._relations, conn, item_id)


@router.post("/relations")
def add_relation(body: dict = Body(...), conn: sqlite3.Connection = Depends(get_db)):
    result = _run(svc.add_relation, conn, body)
    conn.commit()
    return result


@router.delete("/relations/{relation_id}")
def delete_relation(relation_id: int, conn: sqlite3.Connection = Depends(get_db)):
    _run(svc.delete_relation, conn, relation_id)
    conn.commit()
    return {"ok": True}


@router.post("/attachments")
async def upload_attachment(file: UploadFile = File(...)):
    raw_name = Path(file.filename or "file").name
    safe_name = raw_name.replace("\\", "_").replace("/", "_")
    stored = f"{uuid.uuid4().hex}_{safe_name}"
    ATTACH_DIR.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    (ATTACH_DIR / stored).write_bytes(content)
    return {
        "name": raw_name,
        "path": stored,
        "url": f"/files/{stored}",
        "size": len(content),
    }


@router.get("/timeline")
def global_timeline(
    types: str | None = None,
    start: str | None = None,
    end: str | None = None,
    item_id: int | None = None,
    limit: int = Query(200, le=500),
    conn: sqlite3.Connection = Depends(get_db),
):
    where = ["1 = 1"]
    params: list = []
    if types:
        values = [t for t in types.split(",") if t]
        where.append("pr.action_type IN (" + ",".join("?" for _ in values) + ")")
        params.extend(values)
    if start:
        where.append("pr.action_time >= ?")
        params.append(start + "T00:00")
    if end:
        where.append("pr.action_time <= ?")
        params.append(end + "T23:59")
    if item_id:
        where.append("pr.item_id = ?")
        params.append(item_id)
    rows = conn.execute(
        f"""
        SELECT pr.*, i.item_no, i.title AS item_title, i.status AS item_status,
               i.category AS item_category, i.pinned
        FROM process_records pr JOIN items i ON i.id = pr.item_id
        WHERE {' AND '.join(where)}
        ORDER BY pr.action_time DESC, pr.id DESC LIMIT ?
        """,
        params + [limit],
    ).fetchall()
    from ..status import ACTION_LABEL, STATUS_LABEL

    result = []
    for row in rows:
        d = dict(row)
        d["report_channels"] = loads(d.get("report_channels"), []) or []
        d["attachments"] = loads(d.get("attachments"), []) or []
        d["action_label"] = ACTION_LABEL.get(d["action_type"], d["action_type"])
        d["item_status_label"] = STATUS_LABEL.get(d["item_status"], d["item_status"])
        result.append(d)
    return result
