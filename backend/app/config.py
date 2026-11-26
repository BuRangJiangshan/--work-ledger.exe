"""应用配置与路径。"""
import os
import sys
from pathlib import Path


def _frozen_base() -> Path:
    """PyInstaller frozen 后，资源解压到 sys._MEIPASS。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


def _data_dir() -> Path:
    raw = os.environ.get("APP_DATA_DIR")
    if raw:
        return Path(raw).expanduser()
    # frozen 时，数据目录放到 exe 同级（用户可写）
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        return exe_dir / "data"
    return PROJECT_DIR / "data"


DATA_DIR = _data_dir()
DB_PATH = DATA_DIR / "app.db"
ATTACH_DIR = DATA_DIR / "attachments"
BACKUP_DIR = DATA_DIR / "backups"
UPLOAD_DIR = DATA_DIR / "uploads"

# frozen 时 schema.sql 会被打进 sys._MEIPASS/app/schema.sql
_FROZEN_BASE = _frozen_base()
SCHEMA_PATH = _FROZEN_BASE / "app" / "schema.sql"
if not SCHEMA_PATH.exists():
    # 开发时 fallback
    SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# frozen 时 frontend/dist 会被打进 sys._MEIPASS/frontend/dist
FRONTEND_DIST = _FROZEN_BASE / "frontend" / "dist"
if not FRONTEND_DIST.exists():
    # 开发时 fallback
    FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"


def ensure_dirs() -> None:
    for d in (DATA_DIR, ATTACH_DIR, BACKUP_DIR, UPLOAD_DIR):
        d.mkdir(parents=True, exist_ok=True)
