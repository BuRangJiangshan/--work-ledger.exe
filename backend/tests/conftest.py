"""pytest 公共夹具：使用独立的临时数据目录。"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="workledger_test_"))
os.environ["APP_DATA_DIR"] = str(TEST_DATA_DIR)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    db_file = TEST_DATA_DIR / "app.db"
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(db_file) + suffix)
        if path.exists():
            path.unlink()
    init_db()
    with TestClient(app) as c:
        yield c


def make_item(client, **overrides):
    payload = {
        "title": "测试事项",
        "category": "综治工单",
        "source_type": "综治信息系统",
        "receive_time": "2026-11-20T09:30",
        "due_date": "2026-11-27",
        "estimated_days": 9,
    }
    payload.update(overrides)
    resp = client.post("/api/items", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()
