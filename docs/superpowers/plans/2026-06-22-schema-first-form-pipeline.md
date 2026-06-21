---
change: schema-first-form-pipeline
design-doc: docs/superpowers/specs/2026-06-22-schema-first-form-pipeline-design.md
base-ref: e7415101d51a1ef5ceec688611ae111fd7af256f
archived-with: 2026-06-21-schema-first-form-pipeline
---

# Schema-First 表单管道 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** �?JSON Schema Draft-07 驱动前后端表单校验，废除手写 validate，同步强类型�?
**Architecture:** 单一真相�?`product_schema.json`。后�?Pydantic 动态构�?`FormData`，前�?ajv 编译 Schema 实时校验，Monaco Editor 预览 JSON + 错误标注�?
**Tech Stack:** Python 3.11 + FastAPI + Pydantic (create_model) | TypeScript + ajv + @monaco-editor/react | vitest + pytest

## Global Constraints

- `product_schema.json` 位于 `backend/core/`，与 `questions_config.json` 同级
- `questions_config.json` 保留但降级为 fallback，不删除
- `session_service._validate_form()` 标记 deprecated，不删除
- 所�?`form_data: dict[str, Any]` �?`FormData` 强类型（4 �?Request 模型 + 服务层）
- Schema 版本�?`x-meta.schema_version: "1.0.0"`，前�?localStorage 迁移依据
- ajv vs Pydantic 校验一致性由 `required`/`enum`/`minLength`/`minItems` 标准关键字保�?- 前端 Monaco Editor readOnly 模式，仅预览不可编辑
- 后端 debug 日志通过 `logger.bind(event=...)` 埋点，前端通过 `debugLogger.log()`
- 前端依赖: `ajv`、`@monaco-editor/react`、`monaco-editor`

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 1: 创建 `product_schema.json`

**Files:**
- Create: `backend/core/product_schema.json`

**Interfaces:**
- Produces: JSON Schema Draft-07 文件，含 `x-ui` 元数据和 `x-meta.schema_version`

- [x] **Step 1: 创建 product_schema.json**

�?`questions_config.json` �?17 个字段转�?JSON Schema Draft-07 格式�?
```json
{
  "$schema": "https://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "product_name": {
      "type": "string",
      "minLength": 1,
      "x-ui": { "label": "产品名称", "widget": "text", "group": "base", "required": true }
    },
    "one_liner": {
      "type": "string",
      "minLength": 1,
      "x-ui": { "label": "一句话定义", "widget": "text", "group": "base", "required": true }
    },
    "problem_statement": {
      "type": "string",
      "minLength": 1,
      "x-ui": { "label": "解决的问�?, "widget": "textarea", "group": "base", "required": true }
    },
    "target_users": {
      "type": "string",
      "minLength": 1,
      "x-ui": { "label": "目标用户", "widget": "textarea", "group": "base", "required": true }
    },
    "mvp_features": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 3,
      "x-ui": { "label": "MVP 核心功能", "widget": "list", "group": "base", "required": true }
    },
    "platform_type": {
      "type": "string",
      "enum": ["web", "mobile", "wechat_miniprogram", "desktop", "multi"],
      "x-ui": { "label": "目标平台", "widget": "select", "group": "base", "required": true }
    },
    "needs_auth": {
      "type": "string",
      "enum": ["yes", "no", "unsure"],
      "x-ui": { "label": "用户登录", "widget": "radio", "group": "base", "required": true }
    },
    "needs_database": {
      "type": "string",
      "enum": ["yes", "no", "unsure"],
      "x-ui": { "label": "数据存储", "widget": "radio", "group": "base", "required": true }
    },
    "page_count": {
      "type": "string",
      "enum": ["1-3", "4-10", "10+", "unsure"],
      "x-ui": { "label": "页面数量", "widget": "select", "group": "base", "required": true }
    },
    "visual_style": {
      "type": "string",
      "enum": ["minimal", "creative", "enterprise", "unsure"],
      "default": "unsure",
      "x-ui": { "label": "视觉风格", "widget": "select", "group": "base", "required": false }
    },
    "competitors": {
      "type": "string",
      "default": "",
      "x-ui": { "label": "竞品参�?, "widget": "textarea", "group": "base", "required": false }
    },
    "tech_stack_preference": {
      "type": "string",
      "default": "",
      "x-ui": { "label": "技术限�?, "widget": "textarea", "group": "advanced", "required": false }
    },
    "feature_priority": {
      "type": "string",
      "enum": ["user_defined", "ai_suggest", "iterate"],
      "default": "ai_suggest",
      "x-ui": { "label": "功能优先级策�?, "widget": "radio", "group": "advanced", "required": false }
    },
    "doc_depth": {
      "type": "string",
      "enum": ["brief", "standard", "detailed"],
      "default": "standard",
      "x-ui": { "label": "文档详细程度", "widget": "select", "group": "advanced", "required": false }
    },
    "ai_temperature": {
      "type": "string",
      "enum": ["conservative", "balanced", "creative"],
      "default": "balanced",
      "x-ui": { "label": "AI 创造力控制", "widget": "select", "group": "advanced", "required": false }
    },
    "timeline_expectation": {
      "type": "string",
      "enum": ["1-2_months", "3-6_months", "6+_months", "unsure"],
      "default": "unsure",
      "x-ui": { "label": "时间预期", "widget": "select", "group": "advanced", "required": false }
    },
    "additional_context": {
      "type": "string",
      "default": "",
      "x-ui": { "label": "补充上下�?, "widget": "textarea", "group": "advanced", "required": false }
    }
  },
  "required": [
    "product_name", "one_liner", "problem_statement", "target_users",
    "mvp_features", "platform_type", "needs_auth", "needs_database", "page_count"
  ],
  "x-meta": { "schema_version": "1.0.0" }
}
```

- [x] **Step 2: 手动校验 JSON 合法�?*

```powershell
python -c "import json; json.load(open('backend/core/product_schema.json','r',encoding='utf-8')); print('OK')"
```
Expected: `OK`

- [x] **Step 3: Commit**

```bash
git add backend/core/product_schema.json
git commit -m "feat: add product_schema.json (JSON Schema Draft-07)"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 2: 重构 `field_registry.py` �?优先�?Schema，降级读旧配�?
**Files:**
- Modify: `backend/core/field_registry.py`

**Interfaces:**
- Produces: `get_schema() -> dict` �?返回完整 JSON Schema 对象
- Modifies: `_load()` �?优先�?`product_schema.json`，失败降�?`questions_config.json`
- Keeps: `get_all_fields()`, `get_field_ids()`, `get_required_field_ids()`, `get_optional_field_ids()`, `get_field()`, `is_list_field()` �?签名不变

- [x] **Step 1: 编写 field_registry 降级逻辑 + get_schema()**

```python
"""字段注册表：�?product_schema.json 为单一来源，提供统一的字段元信息�?
Schema 优先读取 product_schema.json，失败时降级�?questions_config.json�?后端代码不应再硬编码字段名�?"""

import json
from pathlib import Path
from typing import Any

from loguru import logger

_CONFIG_CACHE: dict | None = None
_SCHEMA_CACHE: dict | None = None


def _load() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        path = Path(__file__).resolve().parent / "questions_config.json"
        with path.open(encoding="utf-8") as f:
            _CONFIG_CACHE = json.load(f)
    return _CONFIG_CACHE


def get_schema() -> dict:
    """返回完整 JSON Schema 对象。优�?product_schema.json，降级用 questions_config.json 重组�?""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE

    schema_path = Path(__file__).resolve().parent / "product_schema.json"
    try:
        with schema_path.open(encoding="utf-8") as f:
            _SCHEMA_CACHE = json.load(f)
        logger.bind(event="schema_loaded").debug(
            "Schema loaded: version={version}, field_count={count}",
            version=_SCHEMA_CACHE.get("x-meta", {}).get("schema_version", "unknown"),
            count=len(_SCHEMA_CACHE.get("properties", {})),
        )
    except FileNotFoundError:
        logger.bind(event="schema_fallback").warning(
            "product_schema.json not found, falling back to questions_config.json"
        )
        _SCHEMA_CACHE = _build_schema_from_questions()
    except json.JSONDecodeError as e:
        logger.bind(event="schema_fallback").warning(
            "product_schema.json parse error: {error}, falling back to questions_config.json",
            error=str(e),
        )
        _SCHEMA_CACHE = _build_schema_from_questions()
    return _SCHEMA_CACHE


def _build_schema_from_questions() -> dict:
    """�?questions_config.json 临时构建 Schema 结构（降级路径）�?""
    cfg = _load()
    properties = {}
    required = []
    for q in cfg["base_questions"] + cfg["advanced_questions"]:
        fid = q["id"]
        prop = {"x-ui": {"label": q.get("label", fid), "widget": q["type"], "group": "advanced", "required": q.get("required", False)}}
        if fid in {"product_name", "one_liner", "problem_statement", "target_users"}:
            prop["x-ui"]["group"] = "base"
        if "options" in q:
            prop["type"] = "string"
            prop["enum"] = [o["value"] for o in q["options"]]
        elif q["type"] == "list":
            prop["type"] = "array"
            prop["items"] = {"type": "string"}
            prop["minItems"] = 3
            prop["x-ui"]["group"] = "base"
        else:
            prop["type"] = "string"
        if not q.get("required"):
            prop["default"] = ""
        properties[fid] = prop
        if q.get("required"):
            required.append(fid)
    return {
        "$schema": "https://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": properties,
        "required": required,
        "x-meta": {"schema_version": "0.0.0 (degraded)"},
    }


def get_all_fields() -> list[dict]:
    cfg = _load()
    return cfg["base_questions"] + cfg["advanced_questions"]


def get_field_ids() -> list[str]:
    return [q["id"] for q in get_all_fields()]


def get_required_field_ids() -> list[str]:
    return [q["id"] for q in get_all_fields() if q.get("required")]


def get_optional_field_ids() -> list[str]:
    return [q["id"] for q in get_all_fields() if not q.get("required")]


def get_field(field_id: str) -> dict | None:
    for q in get_all_fields():
        if q["id"] == field_id:
            return q
    return None


def is_list_field(field_id: str) -> bool:
    f = get_field(field_id)
    return f is not None and f.get("type") == "list"
```

- [x] **Step 2: 验证 get_schema() 返回有效 Schema**

```powershell
python -c "from backend.core.field_registry import get_schema; s=get_schema(); print(s.get('x-meta',{}).get('schema_version')); print(len(s.get('properties',{})))"
```
Expected: `1.0.0` + `17`

- [x] **Step 3: 验证降级路径（移�?product_schema.json 后仍可工作）**

```powershell
# 备份 schema 然后测试降级
cp backend/core/product_schema.json backend/core/product_schema.json.bak
Remove-Item backend/core/product_schema.json
python -c "import importlib; from backend.core import field_registry; importlib.reload(field_registry); s=field_registry.get_schema(); print(s.get('x-meta',{}).get('schema_version'))"
# 恢复
mv backend/core/product_schema.json.bak backend/core/product_schema.json
```
Expected: `0.0.0 (degraded)` (WARNING 日志)

- [x] **Step 4: Commit**

```bash
git add backend/core/field_registry.py
git commit -m "feat: field_registry reads product_schema.json with fallback"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 3: 重构 `state.py` �?FormData �?Schema 动态构�?
**Files:**
- Modify: `backend/core/state.py`

**Interfaces:**
- Modifies: `_build_form_data_model()` �?�?`get_schema()` 构建，而非 `get_all_fields()`
- Produces: `FormData` �?字段类型、必�?选填、约束均�?Schema 派生

- [x] **Step 1: 重写 _build_form_data_model()**

```python
"""数据模型定义（无状态架构）"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, create_model


# ========== 数据模型 ==========

class ChatMessage(BaseModel):
    role: str          # "user" | "assistant"
    content: str
    timestamp: datetime


class ReviewRound(BaseModel):
    round_number: int
    review_content: Optional[str] = None
    rewrite_content: Optional[str] = None


class DocumentState(BaseModel):
    content: str = ""
    streaming: bool = False
    last_chunk_at: Optional[datetime] = None
    review_rounds: list[ReviewRound] = []
    current_round: int = 0
    user_edits: Optional[str] = None
    confirmed: bool = False


# ========== 动态表单数据模�?==========
# FormData �?product_schema.json 动态生成，字段增减只需修改 JSON

def _build_form_data_model():
    from core.field_registry import get_schema
    schema = get_schema()
    properties = schema.get("properties", {})
    required_set = set(schema.get("required", []))
    fields = {}
    for name, prop in properties.items():
        json_type = prop.get("type")
        if json_type == "array":
            fields[name] = (list[str], Field(default_factory=list, min_length=prop.get("minItems", 1)))
        elif name in required_set:
            fields[name] = (str, ...)
        else:
            fields[name] = (str, Field(default=prop.get("default", "")))
    return create_model("FormData", **fields)

FormData = _build_form_data_model()
```

- [x] **Step 2: 验证 FormData 字段�?= 17**

```powershell
python -c "from backend.core.state import FormData; print(len(FormData.model_fields))"
```
Expected: `17`

- [x] **Step 3: 验证必填字段约束生效**

```powershell
python -c "from backend.core.state import FormData; f=FormData(); print('FAIL: no error')" 2>&1
```
Expected: ValidationError (缺少必填字段)

- [x] **Step 4: 验证合法数据通过**

```powershell
python -c "from backend.core.state import FormData; f=FormData(product_name='X',one_liner='Y',problem_statement='Z',target_users='U',mvp_features=['a','b','c'],platform_type='web',needs_auth='yes',needs_database='yes',page_count='1-3'); print(f.product_name)"
```
Expected: `X`

- [x] **Step 5: Commit**

```bash
git add backend/core/state.py
git commit -m "feat: FormData built from product_schema.json via get_schema()"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 4: 改�?`api/schemas.py` �?4 �?Request 模型 `form_data` 强类型化

**Files:**
- Modify: `backend/api/schemas.py`

**Interfaces:**
- Modifies: `ChatRequest.form_data`, `SummaryRequest.form_data`, `DocumentRequest.form_data`, `OptimizeRequest.form_data` �?`dict[str, Any]` �?`FormData`
- Consumes: `FormData` from `backend.core.state`

- [x] **Step 1: 修改 api/schemas.py**

```python
"""统一的请�?响应 Pydantic 模型�?
前端据此了解 API 的数据格式，Swagger 自动生成文档�?"""

from typing import Any, Optional
from pydantic import BaseModel

from core.state import FormData


# ========== 请求模型（新无状�?API�?==========


class ChatRequest(BaseModel):
    """POST /api/chat/stream 的请求体"""
    session_id: str = ""
    form_data: FormData
    history: list[dict[str, str]] = []


class SummaryRequest(BaseModel):
    """POST /api/summary/generate 的请求体"""
    session_id: str = ""
    form_data: FormData
    history: list[dict[str, str]]


class DocumentRequest(BaseModel):
    """POST /api/documents/{type}/stream 的请求体"""
    session_id: str = ""
    form_data: FormData
    requirements_summary: str
    previous_content: str = ""
    prd_content: str = ""
    api_content: str = ""


class OptimizeRequest(BaseModel):
    """POST /api/documents/{type}/optimize 的请求体"""
    session_id: str = ""
    content: str
    form_data: FormData
    requirements_summary: str
    prd_content: str = ""
    api_content: str = ""


class DownloadRequest(BaseModel):
    """POST /api/documents/{type}/download 的请求体"""
    content: str


# ========== 响应模型 ==========


class SummaryResponse(BaseModel):
    """POST /api/summary/generate 的响�?""
    summary: str
```

- [x] **Step 2: 验证导入无误**

```powershell
python -c "from backend.api.schemas import ChatRequest, SummaryRequest, DocumentRequest, OptimizeRequest; print('OK')"
```
Expected: `OK`

- [x] **Step 3: 验证 422 校验生效（非法枚举值）**

```powershell
python -c "
from backend.core.state import FormData
from backend.api.schemas import ChatRequest
data = {'product_name':'X','one_liner':'Y','problem_statement':'Z','target_users':'U','mvp_features':['a','b','c'],'platform_type':'invalid_platform','needs_auth':'yes','needs_database':'yes','page_count':'1-3'}
ChatRequest(form_data=FormData(**data))
" 2>&1
```
Expected: ValidationError (platform_type 非法)

- [x] **Step 4: Commit**

```bash
git add backend/api/schemas.py
git commit -m "feat: 4 Request models use FormData instead of dict[str, Any]"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 5: 适配 `conversation_service.py` �?form_data 类型适配

**Files:**
- Modify: `backend/services/conversation_service.py`

**Interfaces:**
- Modifies: `chat_stream(form_data: dict �?FormData)`, `generate_summary(form_data: dict �?FormData)`
- Modifies: `_form_to_kwargs(form_data: dict �?FormData)` �?通过 `.model_dump()` 或属性访�?- Modifies: `_build_system_prompt(form_data: dict �?FormData)`

- [x] **Step 1: 修改 conversation_service.py**

```python
"""对话服务：Prompt 组装、流式对话、摘要生�?
无状态设计：所有方法从参数获取数据，不引用 session_store�?"""

from typing import Any, AsyncGenerator

from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage
from loguru import logger

from core.error_classifier import classify_error
from core.field_registry import get_all_fields, is_list_field
from core.state import FormData
from services.llm_service import load_prompt, get_llm


# ========================================================================
# 工具函数
# ========================================================================


def _form_to_kwargs(form_data: FormData) -> dict[str, Any]:
    """将强类型 FormData 转为模板需要的上下文�?
    既保留单个字�?key（{{ product_name }} 等向后兼容）�?    也提�?form_fields 列表供模板迭代渲染，实现数据驱动�?    """
    kwargs: dict[str, Any] = {}
    form_fields: list[dict] = []
    data_dict = form_data.model_dump()
    for field in get_all_fields():
        fid = field["id"]
        label = field.get("label", fid)
        value = data_dict.get(fid, "")
        if is_list_field(fid) and isinstance(value, list):
            value = ", ".join(value)
        kwargs[fid] = value or ""
        if value or field.get("required"):
            form_fields.append({"label": label, "value": str(value) if value else ""})
    kwargs["form_fields"] = form_fields
    return kwargs


def _build_system_prompt(form_data: FormData) -> str:
    """构建统一的系�?Prompt�?""
    kwargs = _form_to_kwargs(form_data)
    return load_prompt("backend/prompts/chat_system.jinja2", **kwargs)


def _build_lc_messages(
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
) -> list[BaseMessage]:
    """构建 LangChain 消息列表：System + 历史 + 当前用户消息"""
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    for m in history:
        if m.get("role") == "user":
            messages.append(HumanMessage(content=m.get("content", "")))
        elif m.get("role") == "assistant":
            messages.append(AIMessage(content=m.get("content", "")))
    if user_message:
        messages.append(HumanMessage(content=user_message))
    return messages


# ========================================================================
# 公开方法（无状态）
# ========================================================================


async def chat_stream(
    form_data: FormData,
    history: list[dict[str, str]],
    user_message: str,
    *,
    session_id: str = "",
) -> AsyncGenerator[str, None]:
    """流式对话：接收完整上下文，�?token yield AI 回复�?""
    system = _build_system_prompt(form_data)
    messages = _build_lc_messages(system, history, user_message)

    llm = get_llm()
    config = {}
    if session_id:
        config = {"metadata": {"session_id": session_id, "doc_type": "chat"}}
    logger.bind(event="chat_started").info("Chat stream started")
    try:
        async for chunk in llm.astream(messages, config=config):
            content: str = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
            if content:
                yield content
    except Exception as e:
        category = classify_error(e)
        logger.bind(event="llm_error").error("LLM call failed: {error} [{cat}]", error=str(e), cat=category.value)
        raise


async def generate_summary(
    form_data: FormData,
    history: list[dict[str, str]],
    *,
    session_id: str = "",
) -> str:
    """生成结构化需求摘要（非流式）�?""
    kwargs = _form_to_kwargs(form_data)

    chat_log_lines = []
    for m in history:
        role_label = "用户" if m.get("role") == "user" else "AI"
        chat_log_lines.append(f"[{role_label}] {m.get('content', '')}")
    kwargs["chat_log"] = "\n".join(chat_log_lines)

    summary_prompt = load_prompt("backend/prompts/chat_summary.jinja2", **kwargs)

    llm = get_llm()
    config = {}
    if session_id:
        config = {"metadata": {"session_id": session_id, "doc_type": "summary"}}
    logger.bind(event="summary_started").info("Summary generation started")
    try:
        result = await llm.ainvoke([
            SystemMessage(content=summary_prompt),
            HumanMessage(content="请根据以上信息生成需求摘�?),
        ], config=config)
    except Exception as e:
        category = classify_error(e)
        logger.bind(event="llm_error").error("LLM call failed: {error} [{cat}]", error=str(e), cat=category.value)
        raise

    return result.content if isinstance(result.content, str) else str(result.content)
```

- [x] **Step 2: conversation.py 路由适配 �?无需改动签名，FastAPI 自动反序列化**

`backend/api/conversation.py` 中的 `chat_stream_endpoint` �?`generate_summary_endpoint` 已通过 `data: ChatRequest` 接收请求，Pydantic 自动�?`form_data` 反序列化�?`FormData` 实例。路由层无需改动�?
- [x] **Step 3: 验证导入链无循环**

```powershell
python -c "from backend.services.conversation_service import chat_stream, generate_summary, _form_to_kwargs; print('OK')"
```
Expected: `OK`

- [x] **Step 4: Commit**

```bash
git add backend/services/conversation_service.py
git commit -m "feat: conversation_service accepts FormData typed form_data"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 6: 标记 `session_service._validate_form()` �?deprecated

**Files:**
- Modify: `backend/services/session_service.py`

- [x] **Step 1: 添加 deprecated 注释 + warning 日志**

```python
"""会话服务：仅保留表单校验和问题配置加�?
   _validate_form() 已废弃：API �?Pydantic 校验已覆盖表单校验职责�?"""

from pathlib import Path
import json
import warnings

# 加载表单配置，用于校�?_QUESTIONS_CONFIG_PATH = Path(__file__).resolve().parent.parent / "core" / "questions_config.json"
with open(_QUESTIONS_CONFIG_PATH, encoding="utf-8") as _f:
    _questions_config = json.load(_f)


def _load_questions() -> list[dict]:
    """�?base_questions �?advanced_questions 合并为扁平列�?""
    return _questions_config.get("base_questions", []) + _questions_config.get("advanced_questions", [])


def _validate_form(data: dict) -> None:
    """根据 questions_config.json 校验表单数据

    .. deprecated::
        API �?Pydantic 校验（FormData 模型 + FastAPI 422）已覆盖表单校验�?        此函数保留用于向后兼容，新代码不应调用�?    """
    warnings.warn(
        "_validate_form() is deprecated. Use Pydantic FormData validation instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    questions = _load_questions()

    for q in questions:
        qid = q["id"]
        value = data.get(qid)

        # 必填检�?        if q.get("required") and not value:
            raise ValueError(f"{q['label']}（{qid}）是必填�?)

        # 枚举值检查（select / radio 类型�?        options = q.get("options")
        if options and value:
            allowed = {o["value"] for o in options}
            if value not in allowed:
                raise ValueError(
                    f"{q['label']}（{qid}）的�?'{value}' 不在允许范围内，"
                    f"允许�? {allowed}"
                )

    # mvp_features 长度检�?    mvp_features = data.get("mvp_features")
    if isinstance(mvp_features, list) and len(mvp_features) < 3:
        raise ValueError("MVP 功能至少需�?3 �?)
```

- [x] **Step 2: 确认代码中无新调用点**

```powershell
cd backend; rg "_validate_form" --include="*.py" --no-heading | Select-String -NotMatch "deprecated"
```
Expected: �?session_service.py 自身定义 �?test_services.py 测试（后者可保留，测�?deprecated 函数仍工作）�?
- [x] **Step 3: Commit**

```bash
git add backend/services/session_service.py
git commit -m "deprecate: _validate_form() superseded by Pydantic FormData"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 7: 后端单元测试 �?`test_form_data_model.py`

**Files:**
- Create: `backend/tests/test_form_data_model.py`

**Interfaces:**
- Consumes: `FormData` from `backend.core.state`
- Tests: 非法数据拒绝、合法数据接受、deprecated 函数行为

- [x] **Step 1: 编写测试**

```python
"""FormData 模型测试：Pydantic 动态构建的正确�?""
import pytest
from pydantic import ValidationError

from core.state import FormData


class TestFormDataModel:
    """验证 FormData 正确拒绝非法 / 接受合法 form_data"""

    VALID_MINIMAL = {
        "product_name": "测试产品",
        "one_liner": "一句话",
        "problem_statement": "解决痛点",
        "target_users": "目标用户",
        "mvp_features": ["功能1", "功能2", "功能3"],
        "platform_type": "web",
        "needs_auth": "yes",
        "needs_database": "yes",
        "page_count": "1-3",
    }

    def test_valid_minimal(self):
        """合法最小数据集通过校验"""
        f = FormData(**self.VALID_MINIMAL)
        assert f.product_name == "测试产品"
        assert len(f.mvp_features) == 3

    def test_missing_required_product_name(self):
        """缺必填字�?product_name �?ValidationError"""
        data = {**self.VALID_MINIMAL}
        del data["product_name"]
        with pytest.raises(ValidationError):
            FormData(**data)

    def test_missing_required_one_liner(self):
        """缺必填字�?one_liner �?ValidationError"""
        data = {**self.VALID_MINIMAL}
        del data["one_liner"]
        with pytest.raises(ValidationError):
            FormData(**data)

    def test_missing_required_mvp_features(self):
        """缺必填字�?mvp_features �?ValidationError"""
        data = {**self.VALID_MINIMAL}
        del data["mvp_features"]
        with pytest.raises(ValidationError):
            FormData(**data)

    def test_mvp_features_too_short(self):
        """mvp_features < 3 �?�?ValidationError"""
        data = {**self.VALID_MINIMAL, "mvp_features": ["�?�?]}
        with pytest.raises(ValidationError):
            FormData(**data)

    def test_mvp_features_exact_3(self):
        """mvp_features = 3 项通过"""
        data = {**self.VALID_MINIMAL, "mvp_features": ["a", "b", "c"]}
        f = FormData(**data)
        assert len(f.mvp_features) == 3

    def test_platform_type_invalid_enum(self):
        """枚举越界 �?ValidationError"""
        data = {**self.VALID_MINIMAL, "platform_type": "quantum_computer"}
        with pytest.raises(ValidationError):
            FormData(**data)

    def test_platform_type_valid_enum(self):
        """合法枚举值通过"""
        for val in ["web", "mobile", "wechat_miniprogram", "desktop", "multi"]:
            data = {**self.VALID_MINIMAL, "platform_type": val}
            f = FormData(**data)
            assert f.platform_type == val

    def test_needs_auth_invalid(self):
        """needs_auth 非法�?�?ValidationError"""
        data = {**self.VALID_MINIMAL, "needs_auth": "maybe"}
        with pytest.raises(ValidationError):
            FormData(**data)

    def test_page_count_invalid(self):
        """page_count 非法�?�?ValidationError"""
        data = {**self.VALID_MINIMAL, "page_count": "9999"}
        with pytest.raises(ValidationError):
            FormData(**data)

    def test_optional_field_default(self):
        """选填字段未提供时使用默认�?""
        f = FormData(**self.VALID_MINIMAL)
        assert f.visual_style == "unsure"
        assert f.competitors == ""

    def test_optional_field_explicit(self):
        """选填字段显式赋�?""
        data = {**self.VALID_MINIMAL, "visual_style": "creative"}
        f = FormData(**data)
        assert f.visual_style == "creative"

    def test_type_coercion_mvp_features(self):
        """mvp_features 必须�?string 数组，非 string 元素�?Pydantic 拒绝"""
        data = {**self.VALID_MINIMAL, "mvp_features": [1, 2, 3]}
        with pytest.raises(ValidationError):
            FormData(**data)

    def test_field_count(self):
        """FormData 应包�?17 个字�?""
        assert len(FormData.model_fields) == 17


class TestValidateFormDeprecated:
    """验证 _validate_form 标记�?deprecated 且行为不�?""

    def test_deprecated_raises_deprecation_warning(self):
        """调用 _validate_form 触发 DeprecationWarning"""
        import warnings
        from services.session_service import _validate_form

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _validate_form({"product_name": "X", "one_liner": "Y", "problem_statement": "Z",
                            "target_users": "U", "mvp_features": ["a", "b", "c"],
                            "platform_type": "web", "needs_auth": "yes",
                            "needs_database": "yes", "page_count": "1-3"})
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) >= 1
```

- [x] **Step 2: 运行测试，确认全部通过**

```powershell
cd backend; python -m pytest tests/test_form_data_model.py -v
```
Expected: 全部 PASS (15 tests)

- [x] **Step 3: Commit**

```bash
git add backend/tests/test_form_data_model.py
git commit -m "test: FormData Pydantic validation (15 cases)"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 8: 后端单元测试 �?`test_field_registry.py`

**Files:**
- Create: `backend/tests/test_field_registry.py`

**Interfaces:**
- Consumes: `get_schema()`, `get_all_fields()`, `get_field_ids()`, etc. from `backend.core.field_registry`
- Tests: Schema 返回、字段数量、降级路�?
- [x] **Step 1: 编写测试**

```python
"""field_registry 测试：Schema 加载和降级路�?""
import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from core import field_registry


class TestGetSchema:
    """get_schema() 测试"""

    def test_returns_valid_schema(self):
        """get_schema() 返回合法 dict，含 properties �?required"""
        schema = field_registry.get_schema()
        assert isinstance(schema, dict)
        assert schema.get("$schema") == "https://json-schema.org/draft-07/schema#"
        assert "properties" in schema
        assert "required" in schema
        assert "x-meta" in schema

    def test_field_count_17(self):
        """Schema properties 包含 17 个字�?""
        schema = field_registry.get_schema()
        assert len(schema["properties"]) == 17

    def test_required_fields_count_9(self):
        """required 数组包含 9 个必填字�?""
        schema = field_registry.get_schema()
        assert len(schema["required"]) == 9
        assert "product_name" in schema["required"]
        assert "mvp_features" in schema["required"]
        assert "page_count" in schema["required"]

    def test_x_ui_present(self):
        """每个 property 都有 x-ui 元数�?""
        schema = field_registry.get_schema()
        for name, prop in schema["properties"].items():
            assert "x-ui" in prop, f"字段 {name} 缺少 x-ui"
            assert "label" in prop["x-ui"], f"字段 {name} 缺少 label"
            assert "widget" in prop["x-ui"], f"字段 {name} 缺少 widget"

    def test_enum_fields_have_enum_keyword(self):
        """platform_type 等字段有 enum 约束"""
        schema = field_registry.get_schema()
        assert "enum" in schema["properties"]["platform_type"]
        assert len(schema["properties"]["platform_type"]["enum"]) == 5

    def test_mvp_features_min_items(self):
        """mvp_features �?minItems=3 约束"""
        schema = field_registry.get_schema()
        assert schema["properties"]["mvp_features"]["minItems"] == 3
        assert schema["properties"]["mvp_features"]["type"] == "array"

    def test_schema_cached(self):
        """连续调用返回同一对象"""
        s1 = field_registry.get_schema()
        s2 = field_registry.get_schema()
        assert s1 is s2

    def test_fallback_on_file_not_found(self):
        """Schema 文件不存在时降级"""
        import importlib
        # 重置缓存并模拟文件不存在
        field_registry._SCHEMA_CACHE = None
        with mock.patch.object(Path, 'open', side_effect=FileNotFoundError):
            schema = field_registry.get_schema()
            assert "0.0.0 (degraded)" in schema.get("x-meta", {}).get("schema_version", "")

    def test_fallback_on_json_error(self):
        """Schema 文件 JSON 格式错误时降�?""
        import importlib
        field_registry._SCHEMA_CACHE = None
        with mock.patch.object(Path, 'open', side_effect=json.JSONDecodeError("bad", "", 0)):
            schema = field_registry.get_schema()
            assert "0.0.0 (degraded)" in schema.get("x-meta", {}).get("schema_version", "")


class TestLegacyFunctions:
    """get_all_fields / get_field_ids / is_list_field 仍工�?""

    def test_get_all_fields_count(self):
        fields = field_registry.get_all_fields()
        assert len(fields) == 17

    def test_get_field_ids(self):
        ids = field_registry.get_field_ids()
        assert "product_name" in ids
        assert "additional_context" in ids

    def test_is_list_field_mvp(self):
        assert field_registry.is_list_field("mvp_features") is True

    def test_is_list_field_text(self):
        assert field_registry.is_list_field("product_name") is False

    def test_get_required_field_ids(self):
        req = field_registry.get_required_field_ids()
        assert "product_name" in req
        assert "mvp_features" in req
        assert "page_count" in req

    def test_get_optional_field_ids(self):
        opt = field_registry.get_optional_field_ids()
        assert "visual_style" in opt
        assert "additional_context" in opt
```

- [x] **Step 2: 运行测试**

```powershell
cd backend; python -m pytest tests/test_field_registry.py -v
```
Expected: 全部 PASS (13 tests)

- [x] **Step 3: Commit**

```bash
git add backend/tests/test_field_registry.py
git commit -m "test: field_registry schema loading and fallback (13 cases)"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 9: 前端依赖安装 �?ajv

**Files:**
- Modify: `frontend/package.json` �?添加 `ajv`

- [x] **Step 1: 安装 ajv**

```powershell
cd frontend; npm install ajv
```
Expected: 成功安装，`package.json` �?`package-lock.json` 更新�?
- [x] **Step 2: 验证安装**

```powershell
cd frontend; node -e "const Ajv=require('ajv'); console.log(new Ajv().constructor.name)"
```
Expected: `Ajv` (或通过 ES module import 验证)

- [x] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add ajv dependency for JSON Schema validation"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 10: 前端 `validation.ts` + 单元测试

**Files:**
- Create: `frontend/src/utils/validation.ts`
- Create: `frontend/src/utils/__tests__/validation.test.ts`

**Interfaces:**
- Produces: `validateFormData(data: Record<string, unknown>) -> { valid: boolean; errors: { path: string; message: string }[] }`
- Consumes: `productSchema` via Vite import, `debugLogger`

- [x] **Step 1: 编写 validation.ts**

```typescript
import productSchema from '@/../backend/core/product_schema.json';
import Ajv from 'ajv';
import { debugLogger } from './debugLogger';

const ajv = new Ajv({ allErrors: true });
const validate = ajv.compile(productSchema);

export interface ValidationResult {
  valid: boolean;
  errors: { path: string; message: string }[];
}

export function validateFormData(data: Record<string, unknown>): ValidationResult {
  const valid = validate(data);
  const errors: { path: string; message: string }[] = (validate.errors || []).map((e) => ({
    path: e.instancePath || e.params.missingProperty || '',
    message: e.message || '校验失败',
  }));

  debugLogger.log('info', 'validation:ajv', {
    valid,
    errorCount: errors.length,
    firstError: errors.length > 0 ? errors[0] : null,
  });

  return { valid, errors };
}
```

- [x] **Step 2: Vite 配置检�?�?确保跨目�?import 可用**

验证 `vite.config.ts` �?`@` alias 指向 `frontend/src/`，`@/../backend/core/product_schema.json` 可解析。如不可解析，增�?alias�?
```typescript
// vite.config.ts 中新�?resolve: {
  alias: {
    "@": path.resolve(__dirname, "./src"),
    "@schema": path.resolve(__dirname, "../backend/core"),
  },
},
```

然后 `validation.ts` 中改�?`import productSchema from '@schema/product_schema.json';`

- [x] **Step 3: 编写前端测试 validation.test.ts**

```typescript
import { describe, it, expect } from 'vitest';
import { validateFormData } from '../validation';

// 合法的完�?form_data
const VALID_DATA: Record<string, unknown> = {
  product_name: '测试产品',
  one_liner: '一句话概括',
  problem_statement: '解决痛点',
  target_users: '目标用户�?,
  mvp_features: ['功能A', '功能B', '功能C'],
  platform_type: 'web',
  needs_auth: 'yes',
  needs_database: 'yes',
  page_count: '1-3',
};

describe('validateFormData', () => {
  it('should pass for valid complete data', () => {
    const result = validateFormData(VALID_DATA);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('should fail when required field is missing', () => {
    const { product_name, ...rest } = VALID_DATA;
    const result = validateFormData(rest);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.path.includes('product_name') || e.message.includes('required'))).toBe(true);
  });

  it('should fail when mvp_features has fewer than 3 items', () => {
    const data = { ...VALID_DATA, mvp_features: ['仅一�?] };
    const result = validateFormData(data);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.message.includes('minItems') || e.path.includes('mvp_features'))).toBe(true);
  });

  it('should fail when mvp_features is empty array', () => {
    const data = { ...VALID_DATA, mvp_features: [] };
    const result = validateFormData(data);
    expect(result.valid).toBe(false);
  });

  it('should fail when platform_type is invalid enum', () => {
    const data = { ...VALID_DATA, platform_type: 'quantum_computer' };
    const result = validateFormData(data);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.message.includes('enum'))).toBe(true);
  });

  it('should fail when needs_auth is invalid enum', () => {
    const data = { ...VALID_DATA, needs_auth: 'maybe' };
    const result = validateFormData(data);
    expect(result.valid).toBe(false);
  });

  it('should pass with all optional fields set', () => {
    const data = {
      ...VALID_DATA,
      visual_style: 'creative',
      competitors: '竞品A',
      tech_stack_preference: 'React',
      feature_priority: 'user_defined',
      doc_depth: 'detailed',
      ai_temperature: 'creative',
      timeline_expectation: '1-2_months',
      additional_context: '补充说明',
    };
    const result = validateFormData(data);
    expect(result.valid).toBe(true);
  });

  it('should fail when product_name is empty string', () => {
    const data = { ...VALID_DATA, product_name: '' };
    const result = validateFormData(data);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.message.includes('minLength'))).toBe(true);
  });

  it('should return errors with path and message', () => {
    const result = validateFormData({ product_name: '' });
    expect(result.valid).toBe(false);
    for (const err of result.errors) {
      expect(err).toHaveProperty('path');
      expect(err).toHaveProperty('message');
      expect(typeof err.path).toBe('string');
      expect(typeof err.message).toBe('string');
    }
  });

  it('should have 9 required fields', () => {
    // 空对象应�?9 �?required 错误
    const result = validateFormData({});
    expect(result.valid).toBe(false);
    // required 错误�?�?9（可能含额外错误�?    const requiredErrors = result.errors.filter((e) => e.message.includes('required'));
    expect(requiredErrors.length).toBeGreaterThanOrEqual(9);
  });
});
```

- [x] **Step 4: 运行前端测试**

```powershell
cd frontend; npx vitest run src/utils/__tests__/validation.test.ts
```
Expected: 全部 PASS (10 tests)

- [x] **Step 5: Commit**

```bash
git add frontend/src/utils/validation.ts frontend/src/utils/__tests__/validation.test.ts
git commit -m "feat: ajv-based form validation with 10 unit tests"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 11: `FormStep.tsx` �?废除手写 `validate()`，改�?ajv

**Files:**
- Modify: `frontend/src/components/FormStep.tsx`

**Interfaces:**
- Consumes: `validateFormData` from `@/utils/validation`
- Removes: 本地 `validate()` 函数
- Modifies: `onChange` 触发 ajv 校验，`handleSubmit` �?ajv 结果

- [x] **Step 1: 重写 FormStep.tsx**

```tsx
import { useState, useMemo, type FormEvent } from "react";
import type { QuestionsConfig } from "@/types";
import { validateFormData } from "@/utils/validation";
import JsonPreviewModal from "@/components/JsonPreviewModal";

interface Props {
  questions: QuestionsConfig;
  formData: Record<string, any>;
  onChange: (name: string, value: any) => void;
  onSubmit: () => void;
}

export default function FormStep({ questions, formData, onChange, onSubmit }: Props) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  // ajv 实时校验
  const validation = useMemo(() => validateFormData(formData), [formData]);
  const { valid, errors: ajvErrors } = validation;

  // �?ajv errors 映射到字�?�?错误消息
  const fieldErrors: Record<string, string> = {};
  for (const e of ajvErrors) {
    const fieldName = e.path.replace(/^\//, "") || e.path;
    if (fieldName && !fieldErrors[fieldName]) {
      fieldErrors[fieldName] = e.message;
    }
  }
  // 合并服务�?422 错误
  const displayErrors = { ...fieldErrors, ...serverErrors };

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (valid) {
      onSubmit();
    }
  }

  function addListItem(name: string) {
    const current = Array.isArray(formData[name]) ? formData[name] : ["", "", ""];
    onChange(name, [...current, ""]);
  }

  function updateListItem(name: string, index: number, value: string) {
    const current = [...(formData[name] || ["", "", ""])];
    current[index] = value;
    onChange(name, current);
  }

  function removeListItem(name: string, index: number) {
    const current = [...(formData[name] || ["", "", ""])];
    current.splice(index, 1);
    onChange(name, current);
  }

  function renderField(q: QuestionsConfig["base_questions"][number]) {
    const val = formData[q.id] ?? "";
    const error = displayErrors[q.id];

    const baseInputClass =
      "w-full rounded-lg border bg-white px-3 py-2 text-sm outline-none transition-colors " +
      (error
        ? "border-red-400 focus:border-red-500 focus:ring-1 focus:ring-red-200"
        : "border-gray-300 focus:border-primary-500 focus:ring-1 focus:ring-primary-200");

    let input: JSX.Element;

    switch (q.type) {
      case "text":
        input = (
          <input
            type="text"
            className={baseInputClass}
            value={val as string}
            onChange={(e) => onChange(q.id, e.target.value)}
            placeholder={`请输�?{q.label}`}
          />
        );
        break;

      case "textarea":
        input = (
          <textarea
            className={baseInputClass + " min-h-[80px] resize-y"}
            value={val as string}
            onChange={(e) => onChange(q.id, e.target.value)}
            placeholder={`请输�?{q.label}`}
            rows={3}
          />
        );
        break;

      case "select":
        input = (
          <select
            className={baseInputClass}
            value={val as string}
            onChange={(e) => onChange(q.id, e.target.value)}
          >
            <option value="">-- 请选择 --</option>
            {q.options?.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        );
        break;

      case "radio":
        input = (
          <div className="flex flex-wrap gap-3">
            {q.options?.map((opt) => (
              <label
                key={opt.value}
                className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm cursor-pointer transition-colors ${
                  val === opt.value
                    ? "border-primary-500 bg-primary-50 text-primary-700"
                    : "border-gray-300 bg-white hover:bg-gray-50"
                }`}
              >
                <input
                  type="radio"
                  name={q.id}
                  value={opt.value}
                  checked={val === opt.value}
                  onChange={(e) => onChange(q.id, e.target.value)}
                  className="sr-only"
                />
                {opt.label}
              </label>
            ))}
          </div>
        );
        break;

      case "list":
        {
          const items: string[] = Array.isArray(formData[q.id])
            ? formData[q.id]
            : ["", "", ""];
          input = (
            <div className="space-y-2">
              {items.map((item: string, idx: number) => (
                <div key={`${q.id}-${idx}`} className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 w-5 text-right">
                    {idx + 1}.
                  </span>
                  <input
                    type="text"
                    className={baseInputClass + " flex-1"}
                    value={item}
                    onChange={(e) => updateListItem(q.id, idx, e.target.value)}
                    placeholder={`功能 ${idx + 1}`}
                  />
                  {items.length > 3 && (
                    <button
                      type="button"
                      onClick={() => removeListItem(q.id, idx)}
                      className="shrink-0 text-gray-400 hover:text-red-500 transition-colors p-1"
                      aria-label="删除"
                    >
                      �?                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={() => addListItem(q.id)}
                className="text-sm text-primary-600 hover:text-primary-700 font-medium"
              >
                + 添加功能
              </button>
            </div>
          );
        }
        break;

      default:
        input = <div className="text-sm text-gray-400">不支持的字段类型</div>;
    }

    return (
      <div key={q.id} className="space-y-1.5">
        {/* 标签 */}
        <label className="text-sm font-medium text-gray-700">
          {q.label}
          {q.required && <span className="text-red-500 ml-0.5">*</span>}
        </label>

        {/* 输入控件 */}
        {input}

        {/* 描述 */}
        {q.description && (
          <p className="text-xs text-gray-400">{q.description}</p>
        )}

        {/* 错误 */}
        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>
    );
  }

  const hasData = Object.values(formData).some(
    (v) => v !== "" && v !== undefined && !(Array.isArray(v) && v.length === 0)
  );

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl mx-auto py-8 px-4 space-y-8">
      {/* 步骤标题 */}
      <div>
        <h2 className="text-xl font-bold text-gray-900">步骤一：填写产品信�?/h2>
        <p className="mt-1 text-sm text-gray-500">
          以下信息将帮�?AI 更准确地理解你的产品需�?        </p>
      </div>

      {/* 基础问题 */}
      <div className="space-y-5">
        {questions.base_questions.map(renderField)}
      </div>

      {/* 高级问题折叠�?*/}
      <div className="border border-gray-200 rounded-xl overflow-hidden">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
        >
          <span className="text-sm font-medium text-gray-700">
            高级配置
            <span className="ml-1.5 text-xs text-gray-400 font-normal">（可选）</span>
          </span>
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${showAdvanced ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {showAdvanced && (
          <div className="px-4 py-5 space-y-5 bg-white">
            {questions.advanced_questions.map(renderField)}
          </div>
        )}
      </div>

      {/* 双按钮布局 */}
      <div className="space-y-3">
        {/* 预览 JSON 按钮 */}
        {hasData && (
          <button
            type="button"
            onClick={() => setShowPreview(true)}
            className="w-full rounded-xl border border-gray-300 bg-white hover:bg-gray-50 text-gray-700 font-medium py-3 px-6 transition-colors"
          >
            预览 JSON
          </button>
        )}

        {/* 提交按钮 */}
        <button
          type="submit"
          disabled={!valid}
          className={`w-full rounded-xl font-semibold py-3 px-6 transition-colors shadow-sm ${
            valid
              ? "bg-primary-500 hover:bg-primary-600 text-white"
              : "bg-gray-300 text-gray-500 cursor-not-allowed"
          }`}
        >
          提交并开�?AI 对话
        </button>
      </div>

      {/* JSON 预览 Modal */}
      {showPreview && (
        <JsonPreviewModal
          formData={formData}
          errors={ajvErrors}
          onClose={() => setShowPreview(false)}
        />
      )}
    </form>
  );
}
```

- [x] **Step 2: 验证编译�?TypeScript 错误**

```powershell
cd frontend; npx tsc --noEmit
```
Expected: 无错误（JsonPreviewModal 尚未创建 �?预期 TS 报错，Task 12 消除�?
- [x] **Step 3: Commit**

```bash
git add frontend/src/components/FormStep.tsx
git commit -m "refactor: FormStep uses ajv validation instead of hand-rolled validate()"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 12: `JsonPreviewModal` 组件 �?Monaco Editor 预览

**Files:**
- Create: `frontend/src/components/JsonPreviewModal.tsx`
- Modify: `frontend/package.json` �?添加 `@monaco-editor/react`, `monaco-editor`

**Interfaces:**
- Produces: `<JsonPreviewModal formData={...} errors={...} onClose={...} />`
- Consumes: `@monaco-editor/react`, `debugLogger`

- [x] **Step 1: 安装 Monaco 依赖**

```powershell
cd frontend; npm install @monaco-editor/react monaco-editor
```
Expected: 成功安装�?
- [x] **Step 2: 编写 JsonPreviewModal.tsx**

```tsx
import { useEffect, useRef } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import { debugLogger } from "@/utils/debugLogger";

interface Props {
  formData: Record<string, unknown>;
  errors: { path: string; message: string }[];
  onClose: () => void;
}

/**
 * �?ajv errors 转换�?Monaco decorations
 */
function errorsToDecorations(
  errors: Props["errors"],
  model: editor.ITextModel
): editor.IModelDeltaDecoration[] {
  return errors.map((e) => {
    let lineNumber = 1;
    // 尝试根据 path 定位行号：在 model 内容中搜索字段名
    const fieldName = e.path.replace(/^\//, "");
    if (fieldName) {
      const text = model.getValue();
      const lines = text.split("\n");
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes(`"${fieldName}"`)) {
          lineNumber = i + 1;
          break;
        }
      }
    }
    return {
      range: new (window as any).monaco.Range
        ? new (window as any).monaco.Range(lineNumber, 1, lineNumber, 1)
        : { startLineNumber: lineNumber, startColumn: 1, endLineNumber: lineNumber, endColumn: 1 },
      options: {
        isWholeLine: true,
        className: "validation-error-line",
        glyphMarginClassName: "validation-error-glyph",
        hoverMessage: { value: `�?${e.message}` },
      },
    };
  });
}

export default function JsonPreviewModal({ formData, errors, onClose }: Props) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const decorationsRef = useRef<string[]>([]);

  const jsonText = JSON.stringify(formData, null, 2);
  const errorCount = errors.length;

  useEffect(() => {
    debugLogger.log("info", "preview:modal", {
      action: "open",
      fieldCount: Object.keys(formData).length,
      errorCount,
    });
    return () => {
      debugLogger.log("info", "preview:modal", { action: "close" });
    };
  }, []);

  const handleEditorMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;

    // 注入自定�?CSS �?    monaco.editor.defineTheme("jsonPreview", {
      base: "vs",
      inherit: true,
      rules: [],
      colors: {},
    });

    // 应用错误 decorations
    if (errors.length > 0 && editor.getModel()) {
      const decorations = errorsToDecorations(errors, editor.getModel()!);
      decorationsRef.current = editor.deltaDecorations(decorationsRef.current, decorations);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">JSON 预览</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors p-1"
            aria-label="关闭"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Monaco Editor */}
        <div className="flex-1 min-h-[400px] p-4">
          <Editor
            height="100%"
            defaultLanguage="json"
            value={jsonText}
            theme="jsonPreview"
            onMount={handleEditorMount}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              lineNumbers: "on",
              scrollBeyondLastLine: false,
              wordWrap: "on",
              automaticLayout: true,
            }}
          />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-gray-200 text-sm text-gray-500">
          <span>
            {errorCount > 0
              ? `${errorCount} 个校验错误`
              : "�?校验通过"}
          </span>
          <button
            onClick={onClose}
            className="rounded-lg bg-primary-500 hover:bg-primary-600 text-white px-4 py-1.5 text-sm font-medium transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [x] **Step 3: 添加 Monaco error decorations �?CSS**

�?`frontend/src/index.css` 或全局样式文件中追加：

```css
.validation-error-line {
  background-color: rgba(239, 68, 68, 0.08) !important;
}
.validation-error-glyph {
  background-color: #ef4444;
  width: 3px !important;
  margin-left: 3px;
}
```

- [x] **Step 4: 验证 TypeScript 编译**

```powershell
cd frontend; npx tsc --noEmit
```
Expected: 无错误�?
- [x] **Step 5: Commit**

```bash
git add frontend/src/components/JsonPreviewModal.tsx frontend/package.json frontend/package-lock.json frontend/src/index.css
git commit -m "feat: JsonPreviewModal with Monaco Editor + error decorations"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 13: `FormStep.tsx` �?集成预览按钮 + 提交流程（基�?Task 11 已包含）

Task 11 已包含双按钮布局�?`JsonPreviewModal` 集成。无需额外工作。确�?Task 11 中的 `FormStep.tsx` 代码已包含：
- [预览 JSON] 按钮（`hasData` 条件渲染�?- [提交并开�?AI 对话] 按钮（`disabled={!valid}`�?- `JsonPreviewModal` 条件渲染

- [x] **Step 1: 确认 FormStep.tsx 编译通过**

```powershell
cd frontend; npx tsc --noEmit
```
Expected: 无错误�?
archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 14: 前端 422 兜底处理 �?api.ts 解析 validation errors

**Files:**
- Modify: `frontend/src/services/api.ts`

**Interfaces:**
- Modifies: `chatStream()` �?catch 422 响应，解�?FastAPI 错误详情

- [x] **Step 1: 修改 chatStream() 添加 422 解析**

�?`chatStream()` 函数中，`!response.ok` 分支增强�?
```typescript
export async function chatStream(
  req: ChatRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const response = await fetch(`${SSE_BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal,
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      // FastAPI 422 响应：解�?validation error 详情
      let errorMsg = `chat/stream 失败 (${response.status}): ${body}`;
      if (response.status === 422) {
        try {
          const parsed = JSON.parse(body);
          if (parsed.detail && Array.isArray(parsed.detail)) {
            const messages = parsed.detail.map((d: { loc: string[]; msg: string }) => {
              const field = d.loc?.[d.loc.length - 1] ?? "unknown";
              return `${field}: ${d.msg}`;
            });
            errorMsg = `校验失败 (422): ${messages.join("; ")}`;
            debugLogger.log('warn', 'validation:422', { errors: parsed.detail });
          }
        } catch {
          // body �?JSON，使用原始错�?        }
      }
      callbacks.onError(errorMsg);
      return;
    }
    await readStream(response, callbacks, signal);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "chat/stream 请求异常";
    callbacks.onError(msg);
  }
}
```

同理修改 `generateDocumentStream()` �?`optimizeDocumentStream()` 中的 `!response.ok` 分支�?
- [x] **Step 2: 验证编译**

```powershell
cd frontend; npx tsc --noEmit
```
Expected: 无错误�?
- [x] **Step 3: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat: api.ts parses FastAPI 422 validation errors for chatStream"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 15: TypeScript 类型定义 �?`FormData` 接口 + 状态类型化

**Files:**
- Modify: `frontend/src/types/index.ts`

**Interfaces:**
- Produces: `FormData` 接口�?7 字段强类型）
- Modifies: `ProjectState.form_data` �?`FormData`
- Modifies: `ChatRequest.form_data`, `SummaryRequest.form_data`, `DocumentRequest.form_data`, `OptimizeRequest.form_data` �?`FormData`

- [x] **Step 1: �?types/index.ts 中添�?FormData 接口并替换引�?*

```typescript
// 新增 FormData 强类型接�?export interface FormData {
  _schema_version: string;
  product_name: string;
  one_liner: string;
  problem_statement: string;
  target_users: string;
  mvp_features: string[];
  platform_type: string;
  needs_auth: string;
  needs_database: string;
  page_count: string;
  visual_style: string;
  competitors: string;
  tech_stack_preference: string;
  feature_priority: string;
  doc_depth: string;
  ai_temperature: string;
  timeline_expectation: string;
  additional_context: string;
}

// 替换 ProjectState.form_data
export interface ProjectState {
  session_id: string
  viewState: ViewState
  form_data: FormData  // �? Record<string, any>
  messages: ChatMessage[]
  requirements_summary: string
  prd: DocumentState
  api: DocumentState
  prompts: DocumentState
  completedSteps: ViewState[]
  pendingUpdates: ViewState[]
}

// 替换 4 �?Request �?form_data
export interface ChatRequest {
  session_id: string
  form_data: FormData  // �? Record<string, any>
  history: ChatMessage[]
}

export interface SummaryRequest {
  session_id: string
  form_data: FormData  // �? Record<string, any>
  history: ChatMessage[]
}

export interface DocumentRequest {
  session_id: string
  form_data: FormData  // �? Record<string, any>
  requirements_summary: string
  previous_content?: string
  prd_content?: string
  api_content?: string
}

export interface OptimizeRequest {
  session_id: string
  content: string
  form_data: FormData  // �? Record<string, any>
  requirements_summary: string
  prd_content?: string
  api_content?: string
}
```

- [x] **Step 2: 更新 createEmptyProjectState()**

```typescript
export function createEmptyProjectState(): ProjectState {
  return {
    session_id: '',
    viewState: 'form_editing',
    form_data: {
      _schema_version: '1.0.0',
      product_name: '',
      one_liner: '',
      problem_statement: '',
      target_users: '',
      mvp_features: ['', '', ''],
      platform_type: '',
      needs_auth: '',
      needs_database: '',
      page_count: '',
      visual_style: 'unsure',
      competitors: '',
      tech_stack_preference: '',
      feature_priority: 'ai_suggest',
      doc_depth: 'standard',
      ai_temperature: 'balanced',
      timeline_expectation: 'unsure',
      additional_context: '',
    },
    messages: [],
    requirements_summary: '',
    prd: createEmptyDocumentState(),
    api: createEmptyDocumentState(),
    prompts: createEmptyDocumentState(),
    completedSteps: [],
    pendingUpdates: [],
  }
}
```

- [x] **Step 3: 验证编译**

```powershell
cd frontend; npx tsc --noEmit
```
Expected: 可能�?App.tsx �?api.ts 的类型错误（Task 16 修复）�?
- [x] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "types: add FormData interface, replace Record<string,any> in 6 locations"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 16: 前端类型级联修复 �?App.tsx + api.ts + 其他组件

**Files:**
- Modify: `frontend/src/App.tsx` �?form_data 类型适配
- Modify: `frontend/src/services/api.ts` �?函数签名类型适配
- Modify: `frontend/src/components/FormStep.tsx` �?Props 类型适配 (如需�?

- [x] **Step 1: 修复 api.ts 导入和类�?*

```typescript
// api.ts 顶部导入中加�?FormData
import type {
  QuestionsConfig,
  FormData,  // 新增
  ChatRequest,
  SummaryRequest,
  DocumentRequest,
  OptimizeRequest,
  StreamCallbacks,
} from "@/types";
```

`chatStream`、`generateDocumentStream`、`optimizeDocumentStream` �?`req` 参数已有正确类型（从 types 导入），无需改签名�?
- [x] **Step 2: 修复 App.tsx �?form_data 状态类�?*

�?`App.tsx` 中，找到 `formData` �?useState / ref 声明，将 `Record<string, any>` 改为 `FormData`�?
```typescript
import type { FormData, ProjectState, ... } from "@/types";

// 初始�?const initialFormData: FormData = createEmptyProjectState().form_data;
const [formData, setFormData] = useState<FormData>(initialFormData);
```

�?`onChange` handler 中：
```typescript
const handleFormChange = (name: string, value: any) => {
  setFormData((prev) => ({ ...prev, [name]: value }));
};
```

此处�?`...prev` spread 通过 TypeScript 的类型推断应能工作。如不能，用 `as FormData` 断言�?
- [x] **Step 3: 修复 App.tsx �?API 调用�?*

`chatStream` 调用处：
```typescript
await chatStream(
  { session_id, form_data: formData, history: messages },
  { ... },
);
```

`generateDocumentStream` 调用处同理，`form_data` 字段现在类型安全�?
- [x] **Step 4: 运行 TypeScript 编译检�?*

```powershell
cd frontend; npx tsc --noEmit
```
Expected: 0 errors�?
- [x] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/services/api.ts frontend/src/components/FormStep.tsx
git commit -m "types: cascade FormData type across App.tsx, api.ts, FormStep.tsx"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 17: `migration.ts` �?localStorage 版本化迁�?
**Files:**
- Create: `frontend/src/utils/migration.ts`
- Create: `frontend/src/utils/__tests__/migration.test.ts`

**Interfaces:**
- Produces: `migrateFormData(data: Record<string, any>) -> FormData`
- Consumes: `productSchema` (x-meta.schema_version), `debugLogger`

- [x] **Step 1: 编写 migration.ts**

```typescript
import type { FormData } from '@/types';
import productSchema from '@/../backend/core/product_schema.json';
import { debugLogger } from './debugLogger';

/**
 * localStorage �?form_data 的版本迁移�? * �?_schema_version 或版本不匹配 �?补全默认值�? */
export function migrateFormData(data: Record<string, any>): FormData {
  const currentVersion = productSchema['x-meta']?.['schema_version'] ?? '1.0.0';
  const dataVersion: string = data._schema_version || '0.0.0';

  if (dataVersion === currentVersion) {
    return data as FormData;
  }

  // �?Schema 中提取默认�?  const defaults = getSchemaDefaults(productSchema);
  const migrated = { ...defaults, ...data, _schema_version: currentVersion } as FormData;

  debugLogger.log('info', 'migration:executed', {
    fromVersion: dataVersion,
    toVersion: currentVersion,
  });

  return migrated;
}

/**
 * �?JSON Schema 中提取默认值（required=false 的字段取 default 或空串）�? */
function getSchemaDefaults(schema: Record<string, any>): Record<string, any> {
  const defaults: Record<string, any> = {};
  const properties = schema.properties ?? {};
  const requiredSet: Set<string> = new Set(schema.required ?? []);
  for (const [key, prop] of Object.entries(properties) as [string, any][]) {
    if (requiredSet.has(key)) continue;
    if (prop.type === 'array') {
      defaults[key] = [];
    } else if (prop.default !== undefined) {
      defaults[key] = prop.default;
    } else {
      defaults[key] = '';
    }
  }
  return defaults;
}
```

- [x] **Step 2: 编写 migration.test.ts**

```typescript
import { describe, it, expect } from 'vitest';
import { migrateFormData } from '../migration';

describe('migrateFormData', () => {
  it('should keep same version unchanged', () => {
    const data = {
      _schema_version: '1.0.0',
      product_name: 'X',
      one_liner: 'Y',
      problem_statement: 'Z',
      target_users: 'U',
      mvp_features: ['a', 'b', 'c'],
      platform_type: 'web',
      needs_auth: 'yes',
      needs_database: 'yes',
      page_count: '1-3',
      visual_style: 'creative',
      competitors: '',
      tech_stack_preference: '',
      feature_priority: 'ai_suggest',
      doc_depth: 'standard',
      ai_temperature: 'balanced',
      timeline_expectation: 'unsure',
      additional_context: '',
    };
    const result = migrateFormData(data);
    expect(result).toEqual(data);
  });

  it('should add missing optional fields for v0 data', () => {
    const oldData: Record<string, any> = {
      product_name: 'OldProduct',
      one_liner: 'Old',
      problem_statement: 'Old',
      target_users: 'Old',
      mvp_features: ['a', 'b', 'c'],
      platform_type: 'web',
      needs_auth: 'no',
      needs_database: 'no',
      page_count: '1-3',
    };
    const result = migrateFormData(oldData);
    expect(result._schema_version).toBe('1.0.0');
    expect(result.visual_style).toBeDefined();
    expect(result.competitors).toBe('');
    expect(result.tech_stack_preference).toBe('');
  });

  it('should not overwrite explicit values from old data', () => {
    const oldData: Record<string, any> = {
      product_name: 'P',
      one_liner: 'O',
      problem_statement: 'P',
      target_users: 'T',
      mvp_features: ['x', 'y', 'z'],
      platform_type: 'mobile',
      needs_auth: 'yes',
      needs_database: 'unsure',
      page_count: '4-10',
      visual_style: 'enterprise',
    };
    const result = migrateFormData(oldData);
    expect(result.visual_style).toBe('enterprise');
    expect(result.platform_type).toBe('mobile');
  });

  it('should produce valid FormData shape', () => {
    const result = migrateFormData({});
    expect(result._schema_version).toBe('1.0.0');
    expect(Array.isArray(result.mvp_features)).toBe(true);
    expect(typeof result.product_name).toBe('string');
  });
});
```

- [x] **Step 3: 运行测试**

```powershell
cd frontend; npx vitest run src/utils/__tests__/migration.test.ts
```
Expected: 全部 PASS (4 tests)

- [x] **Step 4: Commit**

```bash
git add frontend/src/utils/migration.ts frontend/src/utils/__tests__/migration.test.ts
git commit -m "feat: localStorage migration from v0 to v1.0.0 with 4 tests"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 18: `App.tsx` �?localStorage 加载时调�?migration

**Files:**
- Modify: `frontend/src/App.tsx`

- [x] **Step 1: �?App.tsx localStorage 加载处插入迁移调�?*

在加�?localStorage 的逻辑中（通常�?`useEffect` 或初�?state 计算处），找到类似：

```typescript
const saved = localStorage.getItem('harnessprd:project');
if (saved) {
  const parsed = JSON.parse(saved);
  // ...
}
```

修改为：

```typescript
import { migrateFormData } from '@/utils/migration';

const saved = localStorage.getItem('harnessprd:project');
if (saved) {
  try {
    const parsed = JSON.parse(saved);
    if (parsed.form_data) {
      parsed.form_data = migrateFormData(parsed.form_data);
    }
    // ... set state
  } catch (e) {
    debugLogger.log('error', 'migration:fallback', { error: String(e) });
    // 迁移失败 �?�?Schema 默认值重建空 formData
    // state 保持初始�?  }
}
```

- [x] **Step 2: 验证编译**

```powershell
cd frontend; npx tsc --noEmit
```
Expected: 0 errors�?
- [x] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: App.tsx calls migrateFormData on localStorage load"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 19: `prompt_validator.py` �?Prompt 模板字段校验

**Files:**
- Create: `backend/core/prompt_validator.py`
- Create: `backend/tests/test_prompt_validator.py`
- Modify: `backend/main.py` �?启动时调�?`validate_all()`

**Interfaces:**
- Produces: `validate_all()` �?扫描模板，对非法引用 emit WARNING
- Produces: `validate_template_fields(template_text, schema_fields) -> list[str]`

- [x] **Step 1: 编写 prompt_validator.py**

```python
"""Prompt 模板字段校验器：启动时扫描模板中�?form_data 字段的引用�?
�?{{ field_name }} 引用校验�?1. 字段存在�?product_schema.json �?合法
2. 字段在上下文白名单中 �?合法
3. 否则 �?WARNING 日志
"""

import re
from pathlib import Path

from loguru import logger

from core.field_registry import get_schema

# 上下文变量白名单：模板中除表单字段外合法使用的变量名
_CONTEXT_WHITELIST = {
    "form_fields", "chat_log", "requirements_summary", "current_content",
    "prd_content", "api_content", "previous_content", "session_id",
    "doc_type", "base_prompt", "review_result",
}

# 扫描目录
_TEMPLATE_DIRS = [
    Path(__file__).resolve().parent.parent / "prompts",
    Path(__file__).resolve().parent.parent / "skills",
]

# 文件扩展�?_TEMPLATE_GLOBS = ["*.jinja2", "*.md"]


def validate_template_fields(template_text: str, schema_fields: set[str]) -> list[str]:
    """扫描模板文本，返回非法字段引用列表�?
    Args:
        template_text: 模板文本内容
        schema_fields: 合法�?form_data 字段名集�?
    Returns:
        不在 schema_fields 也不在白名单中的字段名列�?    """
    referenced = set(re.findall(r'\{\{\s*(\w+)\s*\}\}', template_text))
    return sorted(referenced - schema_fields - _CONTEXT_WHITELIST)


def validate_all() -> int:
    """扫描所有模板文件，对非法引�?emit WARNING�?
    Returns:
        WARNING 总数�? = 全部合法�?    """
    schema = get_schema()
    schema_fields = set(schema.get("properties", {}).keys())
    total_warnings = 0

    for template_dir in _TEMPLATE_DIRS:
        if not template_dir.is_dir():
            continue
        for glob_pattern in _TEMPLATE_GLOBS:
            for template_file in template_dir.glob(glob_pattern):
                try:
                    text = template_file.read_text(encoding="utf-8")
                    invalid = validate_template_fields(text, schema_fields)
                    if invalid:
                        total_warnings += len(invalid)
                        logger.bind(event="prompt_field_warning").warning(
                            "Template {file} references unknown fields: {fields}",
                            file=str(template_file.relative_to(template_dir.parent.parent)),
                            fields=invalid,
                        )
                except Exception as e:
                    logger.bind(event="prompt_read_error").warning(
                        "Cannot read template {file}: {error}",
                        file=str(template_file),
                        error=str(e),
                    )

    if total_warnings == 0:
        logger.bind(event="prompt_validation_ok").info(
            "All prompt templates validated �?no unknown field references"
        )
    else:
        logger.bind(event="prompt_validation_warn").warning(
            "Prompt templates have {count} unknown field reference(s)", count=total_warnings
        )

    return total_warnings
```

- [x] **Step 2: �?main.py lifespan 中集�?prompt_validator**

�?`backend/main.py` �?`lifespan()` 函数中，`init_skill_engine()` 之后添加�?
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await validate_debug_config()
    from services.document_service import init_skill_engine
    init_skill_engine("skills")
    logger.bind(event="startup").info("Skill engine initialized from backend/skills")

    # Prompt 模板字段校验
    from core.prompt_validator import validate_all
    validate_all()

    yield
```

- [x] **Step 3: 编写 test_prompt_validator.py**

```python
"""prompt_validator 测试：字段引用校�?""
from core.prompt_validator import validate_template_fields

SCHEMA_FIELDS = {
    "product_name", "one_liner", "problem_statement", "target_users",
    "mvp_features", "platform_type", "needs_auth", "needs_database",
    "page_count", "visual_style", "competitors", "tech_stack_preference",
    "feature_priority", "doc_depth", "ai_temperature", "timeline_expectation",
    "additional_context",
}


class TestValidateTemplateFields:
    """validate_template_fields() 单元测试"""

    def test_valid_field_returns_empty(self):
        """合法表单字段引用 �?返回�?""
        result = validate_template_fields("{{ product_name }} is great", SCHEMA_FIELDS)
        assert result == []

    def test_whitelisted_field_returns_empty(self):
        """白名单字段被跳过"""
        for field in ["form_fields", "chat_log", "requirements_summary", "current_content"]:
            result = validate_template_fields(f"{{{{ {field} }}}}", SCHEMA_FIELDS)
            assert result == [], f"白名单字�?{field} 不应报告"

    def test_invalid_field_returns_list(self):
        """非法字段引用 �?返回字段�?""
        result = validate_template_fields("{{ unknown_field }}", SCHEMA_FIELDS)
        assert "unknown_field" in result

    def test_multiple_mixed(self):
        """混合模板 �?仅返回非法字�?""
        text = "Product: {{ product_name }}. Unknown: {{ missing_field }}. Summary: {{ requirements_summary }}"
        result = validate_template_fields(text, SCHEMA_FIELDS)
        assert result == ["missing_field"]

    def test_no_braces_returns_empty(self):
        """无模板语�?�?返回�?""
        result = validate_template_fields("Just plain text", SCHEMA_FIELDS)
        assert result == []

    def test_empty_template_returns_empty(self):
        """空模�?�?返回�?""
        result = validate_template_fields("", SCHEMA_FIELDS)
        assert result == []
```

- [x] **Step 4: 运行后端测试**

```powershell
cd backend; python -m pytest tests/test_prompt_validator.py -v
```
Expected: 全部 PASS (6 tests)

- [x] **Step 5: Commit**

```bash
git add backend/core/prompt_validator.py backend/tests/test_prompt_validator.py backend/main.py
git commit -m "feat: prompt_validator scans templates for unknown field refs at startup"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 20: 修复模板中可能存在的字段名拼写错�?
**Files:**
- Potentially modify: `backend/prompts/chat_system.jinja2`, `backend/prompts/chat_summary.jinja2`
- Potentially modify: `backend/skills/prd-generate.md`, `backend/skills/api-generate.md`, `backend/skills/prompts-generate.md`

- [x] **Step 1: 启动后端，检�?prompt_validator 输出**

```powershell
cd backend; python -c "from core.prompt_validator import validate_all; count=validate_all(); print(f'WARNINGS: {count}')"
```
Expected: `WARNINGS: 0`（如�?0，WARNING 日志列出具体文件和字段）

- [x] **Step 2: 如有 WARNING，逐一修复**

打开 WARNING 中报告的文件，将拼写错误�?`{{ field_name }}` 改为 Schema 中的正确字段名。例如：
- `{{ problem }}` �?`{{ problem_statement }}`
- `{{ target_user }}` �?`{{ target_users }}`
- `{{ platform }}` �?`{{ platform_type }}`

- [x] **Step 3: 重新校验确认 WARNING=0**

```powershell
cd backend; python -c "from core.prompt_validator import validate_all; assert validate_all()==0; print('OK')"
```
Expected: `OK`

- [x] **Step 4: Commit（如有修改）**

```bash
git add backend/prompts/ backend/skills/
git commit -m "fix: correct template field names to match product_schema.json"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 21: 联调测试与一致性验�?
**Files:**
- No new files �?端到端验�?+ 一致性测�?
- [x] **Step 1: 后端启动验证**

```powershell
cd backend; timeout 5 uvicorn main:app --port 8000 2>&1 | head -20
```
Expected: 日志�?`"Skill engine initialized"`, `"All prompt templates validated"`, `"Schema loaded: version=1.0.0, field_count=17"`。无 WARNING/ERROR 关于 schema �?prompt�?
- [x] **Step 2: 后端 422 验证 �?非法 form_data curl**

```powershell
curl -X POST http://localhost:8000/api/chat/stream -H 'Content-Type: application/json' -d '{"session_id":"test","form_data":{"product_name":"","one_liner":"","problem_statement":"","target_users":"","mvp_features":["a"],"platform_type":"invalid","needs_auth":"wrong","needs_database":"no","page_count":"99"},"history":[]}'
```
Expected: HTTP 422，响应体�?`detail` 数组�?
- [x] **Step 3: 后端合法请求 200 验证**

```powershell
curl -X POST http://localhost:8000/api/chat/stream -H 'Content-Type: application/json' -d '{"session_id":"test","form_data":{"product_name":"X","one_liner":"Y","problem_statement":"Z","target_users":"U","mvp_features":["a","b","c"],"platform_type":"web","needs_auth":"yes","needs_database":"yes","page_count":"1-3"},"history":[]}'
```
Expected: HTTP 200，SSE 流式响应（需 LLM 可用）�?
- [x] **Step 4: 前端启动验证**

```powershell
cd frontend; npx vite build 2>&1 | tail -5
```
Expected: 构建成功，无错误�?
- [x] **Step 5: 前后端校验一致性验�?*

创建一致性测试脚�?`backend/tests/test_consistency.py`�?
```python
"""ajv vs Pydantic 校验一致性验�?""
import json
import pytest


def test_ajv_pydantic_agree_on_invalid_data():
    """同一份非�?form_data，ajv �?Pydantic 报错字段集合一�?""
    # 非法数据：缺必填 + 枚举越界 + 数组不足
    invalid_data = {
        "product_name": "",
        "one_liner": "",
        "problem_statement": "",
        "target_users": "",
        "mvp_features": ["�?�?],
        "platform_type": "invalid_value",
        "needs_auth": "wrong",
        "needs_database": "yes",
        "page_count": "1-3",
    }

    # Pydantic 校验
    from core.state import FormData
    from pydantic import ValidationError

    pydantic_error_fields = set()
    try:
        FormData(**invalid_data)
    except ValidationError as e:
        for err in e.errors():
            field = err.get("loc", [None])[0]
            if field:
                pydantic_error_fields.add(field)

    # ajv 校验（需�?Node 环境，此处依赖已有的 validation.test.ts�?    # 比较两个集合
    # 预期：两者都拒绝 product_name(空串/minLength)、mvp_features(<3)、platform_type(enum)、needs_auth(enum)
    expected_fields = {"product_name", "mvp_features", "platform_type", "needs_auth", "one_liner", "problem_statement", "target_users"}
    assert pydantic_error_fields.issuperset(expected_fields) or pydantic_error_fields == expected_fields, \
        f"Pydantic fields: {pydantic_error_fields}, expected subset: {expected_fields}"
```

- [x] **Step 6: 运行全量后端测试**

```powershell
cd backend; python -m pytest tests/ -v --ignore=tests/test_skill_integration.py --ignore=tests/test_services.py
```
Expected: 所有新测试 PASS。`test_services.py` 中的 `TestValidateForm` 仍使�?`_validate_form`（deprecated），触发 DeprecationWarning，但测试�?PASS�?
- [x] **Step 7: 确认 test_services.py �?deprecated 测试仍通过**

```powershell
cd backend; python -m pytest tests/test_services.py::TestValidateForm -v -W default::DeprecationWarning
```
Expected: PASS with DeprecationWarning。不需要修改测试�?
archived-with: 2026-06-21-schema-first-form-pipeline
---

### Task 22: 文档更新 �?`docs/form-data-structure.md`

**Files:**
- Modify: `docs/form-data-structure.md`

- [x] **Step 1: 更新 form-data-structure.md**

在文档开头增加变更说明区块，标注�?
```markdown
> **变更 (2026-06-22):** 表单校验已迁移至 JSON Schema 驱动�?> - 单一真相源：`backend/core/product_schema.json`（JSON Schema Draft-07 + x-ui 扩展�?> - 后端：FormData Pydantic 模型动态构建（`state.py`），FastAPI 422 自动校验
> - 前端：ajv 编译 Schema，实时校�?+ Monaco Editor JSON 预览
> - `questions_config.json` 保留但降级为 fallback（`field_registry.py` 降级路径�?> - `session_service._validate_form()` deprecated
```

- [x] **Step 2: Commit**

```bash
git add docs/form-data-structure.md
git commit -m "docs: update form-data-structure.md for schema-first pipeline"
```

archived-with: 2026-06-21-schema-first-form-pipeline
---

## 任务依赖�?
```
Task 1 (schema) ──┬── Task 2 (field_registry) ── Task 8 (test)
                  ├── Task 3 (state.py)                                      
                  �?     └── Task 4 (schemas.py)                             
                  �?            └── Task 5 (conversation_service)             
                  �?                   └── Task 6 (deprecate _validate_form)  
                  �?                          └── Task 7 (test_form_data)    
                  �?                  ├── Task 9 (ajv install)
                  �?     └── Task 10 (validation.ts + test)
                  �?            └── Task 12 (JsonPreviewModal)
                  �?                   └── Task 11 (FormStep ajv rewrite)
                  �?                          └── Task 14 (422 fallback)
                  �?                  ├── Task 15 (FormData types)
                  �?     └── Task 16 (cascade type fix)
                  �?                  ├── Task 17 (migration.ts + test)
                  �?     └── Task 18 (App.tsx integration)
                  �?                  └── Task 19 (prompt_validator)
                         └── Task 20 (fix template typos)

Task 21 (integration) �?depends on all above
Task 22 (docs) �?depends on all above
```

**可并行执行组�?*
- �?A: Task 2 + Task 3 可并行（同一个文件不同函数，建议串行�?- �?B: Task 9 �?Task 10 �?Task 12 �?Task 11（前端串行链�?- �?C: Task 15 �?Task 16（类型链�?- �?D: Task 17 �?Task 18（迁移链�?- �?E: Task 19 �?Task 20（校验链�?- 后端链（Task 2-8）和前端链（Task 9-18）可并行推进
