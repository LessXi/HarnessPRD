"""HarnessPRD — FastAPI 应用入口"""

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from api.sessions import router as sessions_router
from api.conversation import router as conversation_router
from api.documents import router as documents_router
from api.debug import router as debug_router
from api.skills import router as skills_router
from core.config import settings
from core.logging_config import InterceptHandler, setup_logging
from middleware.correlation import correlation_middleware
from middleware.request_logging import request_logging_middleware

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-driven conversational requirements workbench",
)

# ---------- 初始化 loguru 日志系统（替换默认 logging） ----------
setup_logging()
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
logger.bind(event="startup").info(
    "Logging initialized — level={level}", level=settings.log_level
)

# ---------- CORS（从 settings 读取） ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 请求链中间件（correlation → logging） ----------
app.middleware("http")(correlation_middleware)
app.middleware("http")(request_logging_middleware)

# ---------- 挂载路由 ----------
app.include_router(sessions_router)
app.include_router(conversation_router)
app.include_router(documents_router)
app.include_router(skills_router)
# Debug API 仅在开发/调试模式下可用（settings.debug 对应 uvicorn --reload）
if settings.debug:
    app.include_router(debug_router)


@app.get("/")
async def root():
    return {"app": settings.app_name, "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# ---------- 启动事件 ----------


@app.on_event("startup")
async def startup():
    """初始化共享资源。"""
    from services.document_service import init_skill_engine

    init_skill_engine("skills")
    logger.bind(event="startup").info("Skill engine initialized from backend/skills")


# ---------- 直接运行时启动 ----------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
    )
