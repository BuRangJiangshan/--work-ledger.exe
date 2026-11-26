"""汇报中心接口：模板管理与汇报生成/导出。"""
from __future__ import annotations

import re
import sqlite3
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Response, UploadFile

from ..db import get_db
from ..services import reports as svc
from ..utils import today_str

router = APIRouter(prefix="/api", tags=["reports"])

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0] if exc.args else exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _docx_response(report: dict, filename: str) -> Response:
    buf = BytesIO()
    svc.render_docx(report, buf)
    safe = re.sub(r'[\\/:*?"<>|]', "_", filename)
    headers = {
        "Content-Disposition": (
            f"attachment; filename=report.docx; filename*=UTF-8''{quote(safe)}"
        )
    }
    return Response(content=buf.getvalue(), media_type=DOCX_MIME, headers=headers)


@router.get("/report-templates")
def list_templates(conn: sqlite3.Connection = Depends(get_db)):
    return svc.list_templates(conn)


@router.post("/report-templates")
def create_template(body: dict = Body(...), conn: sqlite3.Connection = Depends(get_db)):
    result = _run(svc.create_custom_template, conn, body.get("name"), body.get("headings") or [])
    conn.commit()
    return result


@router.post("/report-templates/import")
async def import_template(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    conn: sqlite3.Connection = Depends(get_db),
):
    content = await file.read()
    result = _run(svc.import_template, conn, file.filename or "template.docx", content, name)
    conn.commit()
    return result


@router.delete("/report-templates/{template_id}")
def delete_template(template_id: int, conn: sqlite3.Connection = Depends(get_db)):
    _run(svc.delete_template, conn, template_id)
    conn.commit()
    return {"ok": True}


@router.post("/reports/preview")
def preview_report(body: dict = Body(...), conn: sqlite3.Connection = Depends(get_db)):
    return _run(
        svc.build_report,
        conn,
        body.get("template_id"),
        body.get("start"),
        body.get("end"),
        body.get("organize") or "category",
    )


@router.post("/reports/export")
def export_report(body: dict = Body(...), conn: sqlite3.Connection = Depends(get_db)):
    report = _run(
        svc.build_report,
        conn,
        body.get("template_id"),
        body.get("start"),
        body.get("end"),
        body.get("organize") or "category",
    )
    filename = body.get("filename") or f"{report['title']}_{today_str()}.docx"
    return _docx_response(report, filename)


@router.get("/reports/items/{item_id}/preview")
def preview_item_report(item_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return _run(svc.build_item_report, conn, item_id)


@router.get("/reports/items/{item_id}/export")
def export_item_report(item_id: int, conn: sqlite3.Connection = Depends(get_db)):
    report = _run(svc.build_item_report, conn, item_id)
    return _docx_response(report, f"{report['title']}.docx")
