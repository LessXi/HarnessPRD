"""LLM 服务：LLM 工厂 + Prompt 加载 + 流式调用"""

from pathlib import Path
from typing import AsyncGenerator, Optional

from jinja2 import Environment, FileSystemLoader, Template

from core.config import settings

# ---------- Jinja2 环境 ----------
_PROMPT_DIR = Path(__file__).resolve().parent.parent.parent  # 项目根目录
_jinja_env = Environment(
    loader=FileSystemLoader(str(_PROMPT_DIR)),
    autoescape=False,
)


def load_prompt(name: str, **kwargs) -> str:
    """加载 Jinja2 模板并渲染（路径相对项目根目录，如 prompts/generate_prd.jinja2）"""
    template: Template = _jinja_env.get_template(name)
    return template.render(**kwargs)


# ---------- LLM 工厂 ----------

def _build_llm():
    """根据 settings.llm_provider 构建 LangChain LLM 实例"""
    provider = settings.llm_provider
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            streaming=True,
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            streaming=True,
        )
    elif provider == "deepseek":
        from langchain_deepseek import ChatDeepSeek
        return ChatDeepSeek(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            streaming=True,
        )
    elif provider == "mimo":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.mimo_model,
            api_key=settings.mimo_api_key,
            base_url=settings.mimo_base_url,
            streaming=True,
        )
    else:
        raise ValueError(f"不支持的 LLM provider: {provider}")


def get_llm():
    """获取 LLM 实例（懒加载单例）"""
    if not hasattr(get_llm, "_instance"):
        get_llm._instance = _build_llm()  # type: ignore
    return get_llm._instance  # type: ignore


# ---------- 流式调用 ----------

async def stream_chat(system_prompt: str, user_message: str) -> AsyncGenerator[str, None]:
    """流式对话：按 token yield"""
    llm = get_llm()
    from langchain.schema import HumanMessage, SystemMessage
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]
    async for chunk in llm.astream(messages):
        content = chunk.content if hasattr(chunk, "content") else str(chunk)
        if content:
            yield content


async def stream_generate(system_prompt: str) -> AsyncGenerator[str, None]:
    """流式生成：按 token yield，不带 user message（仅 system prompt）"""
    llm = get_llm()
    from langchain.schema import SystemMessage
    messages = [SystemMessage(content=system_prompt)]
    async for chunk in llm.astream(messages):
        content = chunk.content if hasattr(chunk, "content") else str(chunk)
        if content:
            yield content
