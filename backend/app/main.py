"""FastAPI 应用入口。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import ATTACH_DIR, FRONTEND_DIST, ensure_dirs
from .db import init_db
from .routers import items, reports, system, workbench


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="事项办理全程留痕工具",
    description="事事留痕、全程可溯、汇报自动生成",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (items, workbench, reports, system):
    app.include_router(module.router)

ensure_dirs()
app.mount("/files", StaticFiles(directory=str(ATTACH_DIR)), name="files")

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:

    @app.get("/")
    def root_info():
        return {
            "message": "后端已启动，前端尚未构建。开发模式请运行 frontend 下的 npm run dev。",
            "api_docs": "/docs",
        }
