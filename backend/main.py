"""HarnessPRD — FastAPI 应用入口"""

import logging
import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from core.config import settings

# ---------- LangSmith 环境变量（必须在任何 langchain import 之前设置）----------
# LangChain 在首次 import 时读取 LANGCHAIN_TRACING_V2 环境变量，
# 因此必须在所有含 langchain 的模块（api.*, services.*）导入前完成设置。
if settings.langchain_tracing_v2:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

from api.sessions import router as sessions_router
from api.conversation import router as conversation_router
from api.documents import router as documents_router
from api.debug import router as debug_router
from api.skills import router as skills_router
from core.logging_config import InterceptHandler, setup_logging
from middleware.correlation import correlation_middleware
from middleware.request_logging import request_logging_middleware

# ---------- 启动校验 ----------

from contextlib import asynccontextmanager
from pathlib import Path


async def validate_debug_config() -> None:
    """启动时校验 Debug/可观测性配置（非阻塞，失败仅 WARNING）。"""
    # 1. LangSmith API 可达性检查
    if settings.langchain_tracing_v2 and settings.langchain_api_key:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get("https://api.smith.langchain.com")
                if resp.status_code < 500:
                    logger.bind(event="startup_check").info("LangSmith API reachable")
                else:
                    logger.bind(event="startup_check").warning(
                        "LangSmith API returned {status}", status=resp.status_code
                    )
        except Exception as e:
            logger.bind(event="startup_check").warning(
                "LangSmith API unreachable: {error}", error=str(e)
            )

    # 2. 日志目录可写检查
    log_dir = Path(__file__).resolve().parent / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        test_file = log_dir / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
    except Exception as e:
        logger.bind(event="startup_check").warning(
            "Log directory not writable: {error}", error=str(e)
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：校验 debug 配置 + 初始化 Skill Engine + 校验 Prompt 模板。"""
    await validate_debug_config()
    from services.document_service import init_skill_engine

    init_skill_engine("skills")
    logger.bind(event="startup").info("Skill engine initialized from backend/skills")

    # 校验 Prompt 模板中的变量引用
    from core.prompt_validator import validate_all

    validation_errors = validate_all()
    if validation_errors:
        for fp, errs in validation_errors.items():
            logger.bind(event="prompt_validation").warning(
                "Template validation found {count} issue(s) in {path}",
                count=len(errs),
                path=fp,
            )
            for e in errs:
                logger.bind(event="prompt_validation").warning("  -> {ref}", ref=e)
    else:
        logger.bind(event="prompt_validation").info(
            "Prompt template validation passed — all references valid"
        )
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-driven conversational requirements workbench",
    lifespan=lifespan,
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

# ---------- 异常处理器 ----------


@app.exception_handler(RequestValidationError)
async def validation_failed_handler(request: Request, exc: RequestValidationError):
    """记录请求体验证失败的详细信息。"""
    logger.bind(event="validation_failed").warning(
        "Validation failed: {errors}", errors=exc.errors()
    )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


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


# ---------- 直接运行时启动 ----------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
    )
