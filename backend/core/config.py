"""应用配置，基于 pydantic-settings 从 .env 读取。

工作方式：
1. 自动从 backend/.env 读取环境变量（如果该文件存在）
2. 也支持从系统环境变量读取（同名 key，优先级更高）
3. 字段的默认值在下方定义，.env 或系统环境变量会覆盖它们

使用示例：
    from core.config import settings
    settings.llm_provider  # → "openai"（来自 .env 或默认值）
"""

from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging


# .env 文件路径：始终相对于 backend/ 目录
_ENV_FILE = str(Path(__file__).resolve().parent.parent / ".env")


class Settings(BaseSettings):
    """全局配置类。

    每个字段对应一个 .env key（不区分大小写）。
    字段的默认值写在类型注解后面——当 .env 或系统环境变量都没有提供时使用。
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",          # .env 中未定义的 key 静默忽略
    )

    # ========== 应用基础 ==========
    app_name: str = "HarnessPRD"
    app_version: str = "1.0.0"
    debug: bool = True

    # ========== 服务端 ==========
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # ========== CORS 跨域 ==========
    # .env 中用逗号分隔多个来源
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        """将逗号分隔的字符串解析为列表"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ========== LLM 提供方 ==========
    # API key 和模型名必须从 .env 提供，代码中不设默认值
    llm_provider: str = "openai"  # openai | anthropic | deepseek | mimo

    openai_api_key: str = ""
    openai_model: str = ""

    anthropic_api_key: str = ""
    anthropic_model: str = ""

    deepseek_api_key: str = ""
    deepseek_model: str = ""

    mimo_api_key: str = ""
    mimo_model: str = ""
    mimo_base_url: str = ""

    # ========== 文档生成参数 ==========
    max_review_rounds: int = 3
    sse_timeout_seconds: int = 60

    # ========== Session ==========
    max_sessions: int = 100

    # ========== 可观测性 ==========
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "HarnessPRD"
    log_level: str = "INFO"
    prompt_log_max_length: int = 2000

    @field_validator("llm_provider")
    @classmethod
    def check_provider(cls, v: str) -> str:
        allowed = {"openai", "anthropic", "deepseek", "mimo"}
        if v not in allowed:
            raise ValueError(f"LLM_PROVIDER 必须是 {allowed} 之一，当前值: {v}")
        return v

    @field_validator("max_review_rounds")
    @classmethod
    def check_rounds(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError(f"MAX_REVIEW_ROUNDS 应在 1-10 之间，当前值: {v}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        v_upper = v.upper()
        if v_upper not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValueError(f"Invalid LOG_LEVEL: {v}. Must be DEBUG, INFO, WARNING, or ERROR")
        return v_upper

    @model_validator(mode="after")
    def check_langsmith_config(self) -> "Settings":
        if self.langchain_tracing_v2 and not self.langchain_api_key:
            logging.warning("LANGCHAIN_TRACING_V2=true but LANGCHAIN_API_KEY is not set")
        return self

    @model_validator(mode="after")
    def check_llm_config(self):
        """校验所选 provider 的 API key 是否已配置。缺失时只给 warning，不阻塞启动"""
        provider = self.llm_provider
        key_map = {
            "openai": ("openai_api_key", "OPENAI_API_KEY"),
            "anthropic": ("anthropic_api_key", "ANTHROPIC_API_KEY"),
            "deepseek": ("deepseek_api_key", "DEEPSEEK_API_KEY"),
            "mimo": ("mimo_api_key", "MIMO_API_KEY"),
        }
        field_name, env_key = key_map[provider]
        if not getattr(self, field_name):
            logging.warning(
                "LLM_PROVIDER 设为 %s，但 %s 未配置。LLM 调用将在运行时失败。"
                "请在 backend/.env 中设置 %s=你的密钥",
                provider, env_key, env_key,
            )
        return self


# ========== 全局单例 ==========
settings = Settings()

# ========== 启动提示 ==========
_ENV_PATH = Path(_ENV_FILE)
if not _ENV_PATH.exists():
    logging.warning(
        "未找到 %s，所有配置将使用默认值。"
        "如需自定义配置，请复制 backend/.env.example 为 backend/.env 并修改。",
        _ENV_PATH,
    )
