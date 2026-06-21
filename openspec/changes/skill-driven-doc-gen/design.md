# Design: skill-driven-doc-gen

## Context

当前 `document_service.py` 将文档生成 prompt、审核 prompt、改写 prompt、循环逻辑全部硬编码在 Python 代码中。修改任何 prompt 都需要改代码 + 重启服务。三类文档（PRD/API/Prompts）通过 `_build_prompt_kwargs()` 区分上下文，但共用同一套生成/审核/改写流程。

**约束**：
- 无数据库、无 Redis（无状态后端，每次请求携带完整上下文）
- SSE 流式传输（`sse-starlette`），前端通过 `fetch` + `ReadableStream` 消费
- API 端点签名不变（前端零改动）
- 纯 Python 自研，不引入 DSPy/LangGraph 等框架

## Goals / Non-Goals

**Goals:**
- 将文档生成 prompt 从代码中解耦为独立 `.md` skill 文件
- 支持 Prompt 链式编排：skill 声明步骤顺序，引擎依次执行
- 支持 skill 文件热加载（修改后新请求自动生效，无需重启）
- 保留 SSE 流式输出体验
- 审核→改写循环由 skill 文件声明（轮次上限、审核维度、改写策略）

**Non-Goals:**
- 不提供 skill 在线编辑器/管理 UI
- 不改变对话（chat）和摘要生成流程
- 不修改前端代码（API 端点签名不变）
- 不引入新的 LLM 框架依赖

## Decisions

### 1. Skill 文件格式：Claude skill 兼容 + 扩展

```
┌──────────────────────────────────────────────────┐
│ Skill 文件结构 (.md)                             │
├──────────────────────────────────────────────────┤
│ ---                                              │
│ name: prd-generate                               │
│ description: 生成 PRD 文档                        │
│ version: "1.0"                                   │
│ max_iterations: 3                                │
│ steps:                                           │
│   - id: generate                                 │
│     type: generate                               │
│     stream: true                                 │
│     prompt: |                                    │
│       # PRD 生成 Prompt                          │
│       你是一位资深产品经理...                       │
│   - id: review                                   │
│     type: review                                 │
│     stream: false                                │
│     criteria:                                    │
│       - 完整性：是否覆盖所有必要章节                │
│       - 一致性：前后描述是否矛盾                    │
│       - 清晰度：非技术人员能否理解                  │
│       - 可执行性：研发能否直接开工                  │
│     pass_condition: "审核通过"                    │
│     prompt: |                                    │
│       # 审核 Prompt                              │
│       请审核以下文档...                            │
│   - id: rewrite                                  │
│     type: rewrite                                │
│     stream: true                                 │
│     prompt: |                                    │
│       # 改写 Prompt                              │
│       根据审核意见修改...                          │
│ ---                                              │
│                                                  │
│ ## 上下文变量                                    │
│                                                  │
│ {{ form_data }} - 产品表单数据                    │
│ {{ requirements_summary }} - 需求摘要             │
│ {{ prd_content }} - PRD 文档内容                  │
│ {{ api_content }} - 接口文档内容                   │
│                                                  │
│ ## 注意事项                                      │
│ 保持中文输出，专业但不晦涩...                       │
└──────────────────────────────────────────────────┘
```

**选择理由**：
- YAML frontmatter 标准格式，与 Claude skill / OpenSpec 生态一致
- `steps` 数组定义链式执行顺序，支持 `generate`、`review`、`rewrite` 三种步骤类型
- `max_iterations` 控制 review→rewrite 最大循环轮次
- Markdown body 提供人类可读的上下文变量说明和注意事项

**替代方案**：
- 纯 YAML/JSON：结构性强但人类可读性差，不如 Markdown body 直观
- 沿用 Jinja2：需要模板引擎，不如 Markdown self-contained

### 2. Skill Engine 架构

```
backend/skill_engine/
├── __init__.py
├── parser.py        # SkillParser: 解析 .md → SkillSchema (Pydantic)
├── engine.py        # SkillEngine: 执行 skill → AsyncGenerator[SSEEvent]
├── loader.py        # SkillLoader: 目录扫描 + 热加载 + 缓存
└── models.py        # Pydantic 数据模型

数据流：
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────────┐
│ .md 文件  │────▶│ Parser   │────▶│ Engine   │────▶│ SSE Stream   │
│ (YAML+MD)│     │ → Schema │     │ → execute│     │ (chunk/done) │
└──────────┘     └──────────┘     └────┬─────┘     └──────────────┘
                                       │
                                ┌──────▼──────┐
                                │ LLM Service │
                                │ (stream/    │
                                │  non-stream)│
                                └─────────────┘
```

**Parser**：用 `PyYAML` 解析 frontmatter，Pydantic 校验 schema。
**Engine**：`async execute(skill, context) -> AsyncGenerator[SSEEvent]`，按 `steps` 顺序执行：
  - `generate`: 流式调用 LLM → 逐 token yield `chunk` 事件
  - `review`: 非流式调用 LLM → 检查 `pass_condition` → yield `review_result` 事件
  - `rewrite`: 流式调用 LLM（输入：原文 + 审核意见）→ yield `chunk` 事件
  - loop 控制：review 未通过 → 执行 rewrite → 回到 review，直到通过或达 `max_iterations`
**Loader**：启动时扫描 `backend/skills/`，构建 `{name: SkillSchema}` 内存缓存。热加载时重新扫描，旧 skill 等待活跃请求完成后释放。

### 3. 与现有代码的集成

```python
# document_service.py 重构后

from skill_engine import SkillLoader, SkillEngine

loader = SkillLoader("backend/skills")  # 启动时初始化
engine = SkillEngine(llm_service)

async def generate_document_stream(doc_type: str, context: dict):
    skill = loader.get(f"{doc_type}-generate")
    async for event in engine.execute(skill, context):
        yield event  # 直接透传 SSE 事件
```

**保留不变**：
- `backend/api/documents.py` — 端点定义不变
- `llm_service.py` — `stream_generate()` 和 `_call_llm_once()` 被 engine 调用
- `sse_utils.py` — SSE 包装器保留

**移除**：
- `document_service.py` 中的 `_build_review_prompt()`、`_build_rewrite_prompt()`、`_has_issues()`
- Jinja2 模板文件（`backend/prompts/generate_*.jinja2` 等）——内容迁移到 skill 文件的 `prompt` 字段

### 4. 热加载机制

```
┌──────────────────────────────────────────────────┐
│                SkillLoader                        │
├──────────────────────────────────────────────────┤
│                                                   │
│  启动时: 扫描 backend/skills/*.md → 内存缓存       │
│                                                   │
│  热加载触发:                                       │
│  ┌──────────────────────┐                        │
│  │ POST /api/skills/reload│  (新增，选做)          │
│  │ 或 文件监听 (watchdog) │                        │
│  └──────────┬───────────┘                        │
│             ▼                                      │
│  1. 解析新的 .md 文件 → SkillSchema v2             │
│  2. 缓存指向 v2 (新请求使用 v2)                    │
│  3. v1 引用计数归零 → 释放                         │
│                                                   │
│  GET /api/skills → 列出已加载 skill (选做)          │
└──────────────────────────────────────────────────┘
```

热加载 API (`/api/skills/reload`) 为 P2 锦上添花功能，MVP 可先不做——**重启服务即可**，因为后端无状态，重启不影响用户体验（前端有 localStorage 持久化）。

### 5. Skill 间的上下文传递

PRD → API → Prompts 存在依赖链。引擎通过 `context` dict 传入：

```python
context = {
    "form_data": {...},
    "requirements_summary": "...",
    "prd_content": "...",       # 生成 api/prompts 时注入
    "api_content": "...",       # 生成 prompts 时注入
}
```

Skill 文件通过 `{{ variable_name }}` 引用上下文变量，引擎在执行前做模板替换（简单 `str.replace`，不做 Jinja2 渲染以减少依赖）。

## Risks / Trade-offs

| 风险 | 影响 | 缓解 |
|------|------|------|
| Skill 格式解析错误 | 文档生成失败，前端收到 error 事件 | Pydantic 严格校验 + 启动时验证所有 skill 文件 + 解析失败时返回明确错误信息 |
| 审核判断不稳定 | review 时好时坏，用户困惑 | skill 文件提供明确的 4 维度审核清单 + `pass_condition` 关键词匹配 |
| 热加载期间并发请求 | 活跃请求可能读到被替换的 skill | 引用计数机制，旧 skill 等请求完成再释放 |
| LLM 调用次数增加 | 成本上升 | skill 文件声明 `max_iterations` 上限，review 非流式（单次调用），总调用量可控 |
| 现有 Jinja2 模板迁移遗漏 | 新 skill 文件 prompt 质量下降 | 逐模板比对迁移 + 用现有测试用例验证输出质量 |

## Migration Plan

1. **Phase 1 — Skill Engine 核心**：创建 `skill_engine/` 模块（parser + engine + loader + models）
2. **Phase 2 — Skill 文件编写**：将 5 个 Jinja2 模板内容迁移到 4 个 `.md` skill 文件
3. **Phase 3 — 集成**：重构 `document_service.py` 使用 engine，移除旧逻辑
4. **Phase 4 — 验证**：对比新旧输出，确保文档质量不下降
5. **Phase 5 — 清理**：删除 `backend/prompts/` 中的旧 Jinja2 模板

**回滚策略**：Git revert。所有变更在独立分支，不影响主分支。

## Open Questions

1. **模板替换语法**：用 `{{ var }}`（Mustache-style）还是 `$var`（shell-style）？建议 `{{ var }}`，用户熟悉。
2. **review 结果展示**：前端当前只显示最终改写结果，是否需要展示审核意见？建议作为 `review_result` SSE 事件透传，前端后续版本可选择性展示。
3. **Skill 版本管理**：skill 文件是否需要 `version` 字段和向后兼容？MVP 先不做，后续迭代考虑。
