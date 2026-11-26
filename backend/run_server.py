"""本地启动入口：启动 FastAPI 并自动打开浏览器。"""
from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import uvicorn  # noqa: E402

from app.config import FRONTEND_DIST  # noqa: E402

HOST = "127.0.0.1"
PORT = 8765


def open_browser() -> None:
    webbrowser.open(f"http://{HOST}:{PORT}")


if __name__ == "__main__":
    if FRONTEND_DIST.exists():
        threading.Timer(1.5, open_browser).start()
    else:
        print("提示：未找到 frontend/dist，请先在 frontend 目录执行 npm run build。")
    print(f"服务地址：http://{HOST}:{PORT}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="info")
