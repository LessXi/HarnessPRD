---
comet_change: skill-driven-doc-gen
role: technical-design
canonical_spec: openspec
---

# Skill-Driven Document Generation — Technical Design

## 架构概览

```
backend/skill_engine/                    backend/skills/
├── models.py    Pydantic 数据模型       ├── prd-generate.md
├── parser.py    .md → SkillSchema       ├── api-generate.md
├── engine.py    AsyncGenerator 执行      └── prompts-generate.md
└── loader.py    目录扫描 + 热加载

         SkillEngine.execute(skill, context)
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
 generate        review          rewrite
 流式 yield      流式 yield       流式 yield
 chunk/done     chunk+review_    chunk/done
                result/done
```

## 核心组件

### 1. 数据模型 (`models.py`)

```python
from pydantic import BaseModel
from typing import Literal

class StepSchema(BaseModel):
    id: str
    type: Literal["generate", "review", "rewrite"]
    prompt: str
    pass_condition: str | None = None  # 仅 review 步

class SkillSchema(BaseModel):
    name: str
    description: str
    max_iterations: int = 3
    steps: list[StepSchema]
```

### 2. Parser (`parser.py`)

- 用 `yaml.safe_load()` 解析 YAML frontmatter
- 用 Pydantic 校验 → 非法 skill 抛 `SkillParseError`
- Jinja2 Environment（FileSystemLoader 指向项目根）渲染 `steps[*].prompt` 中的模板变量
- 支持 `{% include %}`、`{% if %}`、`{{ var }}` 全量 Jinja2 语法

### 3. Engine (`engine.py`)

```python
async def execute(skill: SkillSchema, context: dict) -> AsyncGenerator[SSEEvent]:
    current_content = ""
    for round_idx in range(skill.max_iterations):
        for step in skill.steps:
            prompt = render_template(step.prompt, {**context, "current_content": current_content})
            if step.type == "generate":
                async for token in llm.stream_generate(prompt):
                    yield SSEEvent(event="chunk", content=token)
                    current_content += token
            elif step.type == "review":
                full_text = ""
                async for token in llm.stream_generate(prompt):
                    yield SSEEvent(event="chunk", content=token)
                    full_text += token
                passed, issues = parse_review_result(full_text, step.pass_condition)
                yield SSEEvent(event="review_result", passed=passed, issues=issues)
                if passed:
                    yield SSEEvent(event="done", content=current_content)
                    return
            elif step.type == "rewrite":
                current_content = ""
                async for token in llm.stream_generate(prompt):
                    yield SSEEvent(event="chunk", content=token)
                    current_content += token
    # 达到迭代上限
    yield SSEEvent(event="done", content=current_content)
```

**审核判断 `parse_review_result()`**：
1. 尝试 `json.loads()` 解析 `{"passed": bool, "issues": [...]}`
2. JSON 解析失败 → 降级为 `pass_condition in full_text` 关键词匹配

### 4. Loader (`loader.py`)

- 启动时扫描 `backend/skills/*.md` → 解析 → 缓存在 `dict[str, SkillSchema]`
- `get(name)` → 返回缓存的 SkillSchema 或抛 `SkillNotFoundError`
- `reload()` → 重新扫描，原子替换缓存引用

## Skill 文件格式

```markdown
---
name: prd-generate
description: 生成 PRD 文档
max_iterations: 3
steps:
  - id: generate
    type: generate
    prompt: |
      # 角色定义
      你是一名资深产品文档工程师...
      {% include "docs/prd-template.md" %}
  - id: review
    type: review
    pass_condition: "审核通过"
    prompt: |
      # 角色定义
      你是一名资深技术文档审核专家...
      审核文档：{{ current_content }}
      以 JSON 格式返回：{"passed": true/false, "issues": [...]}
  - id: rewrite
    type: rewrite
    prompt: |
      # 角色定义
      你是一名资深技术文档工程师...
      原文档：{{ current_content }}
      审核意见：{{ review_result }}
      请修改后输出完整文档...
---

## 上下文变量
{{ form_data }} {{ requirements_summary }} {{ prd_content }} {{ api_content }}
{{ previous_content }} — 续写场景自动注入
```

## 集成方式

`document_service.py` 简化为：

```python
from skill_engine import SkillLoader, SkillEngine

loader = SkillLoader("backend/skills")
engine = SkillEngine(llm_service)

async def generate_document_stream(doc_type: str, context: dict):
    skill = loader.get(f"{doc_type}-generate")
    async for event in engine.execute(skill, context):
        yield sse_format(event)  # → JSON SSE
```

`optimize_document_stream()` 废弃 — review→rewrite 循环由 engine 内部处理。

## 回滚策略

Git revert。所有变更在独立分支，API 端点签名不变，前端无感知。

## 开放问题

1. Jinja2 FileSystemLoader 指向项目根目录 — 确认 `docs/prd-template.md` 等文件路径正确解析
2. 大 prompt（含 `{% include %}` 展开后）是否会超出 LLM context 限制 — 需实测
3. P2 增强（reload API、skill 列表 API）在 MVP 后评估
