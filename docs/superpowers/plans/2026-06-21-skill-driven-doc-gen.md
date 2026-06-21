---
change: skill-driven-doc-gen
design-doc: docs/superpowers/specs/2026-06-21-skill-driven-doc-gen-design.md
base-ref: 621c4c14226bf9d5cfc1c8267dfbdd7605d514e2
---

# 实施计划：Skill-Driven Document Generation

## 概览

将 `document_service.py` 中硬编码的 Jinja2 prompt 模板 + Review→Rewrite 循环逻辑，重构为 skill 引擎驱动的声明式架构。新增 `backend/skill_engine/` 模块（models、parser、engine、loader）和 `backend/skills/` 目录（3 个 .md skill 文件）。API 端点签名不变，前端无感知。

## 依赖关系图

```
任务 1 (数据模型) ──→ 任务 2 (Parser) ──→ 任务 3 (Engine) ──→ 任务 6 (后端集成)
                    ↗                                       ↗
任务 4 (Loader) ────                                       |
                    ↘                                       |
任务 5 (Skill 文件) ───────────────────────────────────────┘
                                                              ↘
                                                         任务 7 (验证回归)
                                                              ↘
                                                         任务 8 (清理收尾)
                                                              ↘
                                                         任务 9 (P2 增强)
```

## 任务组

---

### 任务 1：Skill Engine 数据模型 (P0)

**目标**：定义 skill 引擎的核心 Pydantic 数据模型，作为 parser、engine、loader 的契约基础。

**涉及文件**：
- `backend/skill_engine/__init__.py`（新建）
- `backend/skill_engine/models.py`（新建）
- `backend/tests/test_skill_engine_models.py`（新建）

**关键实现要点**：
1. 创建 `backend/skill_engine/` 包目录和 `__init__.py`
2. `StepSchema`：`id` (str)、`type` (Literal["generate", "review", "rewrite"])、`prompt` (str)、`pass_condition` (str | None, 仅 review 步)
3. `SkillSchema`：`name` (str)、`description` (str)、`max_iterations` (int=3)、`steps` (list[StepSchema])
4. `SSEEvent`：`event` (Literal["chunk", "done", "error", "review_result"])、`content` (str="")、`passed` (bool | None=None)、`issues` (list[str] | None=None)
5. `SkillParseError` (Exception) — parser 解析失败
6. `SkillNotFoundError` (Exception) — loader 未找到 skill

**验收标准**：
- `SkillSchema(...)` 正常创建
- `StepSchema(type="invalid")` Pydantic 校验失败（Literal 约束）
- `SSEEvent(event="chunk", content="text")` 可序列化为 dict
- `SkillParseError("msg")` 可抛出和捕获

**依赖**：无

**工作量**：S（30 分钟）

---

### 任务 2：Skill Parser (P0)

**目标**：解析 `.md` skill 文件的 YAML frontmatter，渲染 Jinja2 模板变量，返回 `SkillSchema`。

**涉及文件**：
- `backend/skill_engine/parser.py`（新建）
- `backend/tests/test_skill_engine_parser.py`（新建）

**关键实现要点**：
1. `parse_skill_file(filepath: str) -> SkillSchema`
   - 用 `yaml.safe_load()` 解析 frontmatter（`---...---` 分隔）
   - body 内容暂不处理（skill 文件 body 用作文档说明）
2. Pydantic 校验 frontmatter → 非法 skill 抛 `SkillParseError`
3. `render_skill_prompt(step: StepSchema, context: dict) -> str`
   - 用 Jinja2 `Environment`（FileSystemLoader 指向项目根目录）渲染 `step.prompt`
   - 支持 `{{ form_data.product_name }}`、`{{ prd_content }}` 等嵌套变量
   - 支持 `{% include "docs/prd-template.md" %}` 等 Jinja2 标签
4. 注意：Jinja2 环境可复用 `llm_service.py` 中已有的 `_jinja_env`，但 parser 需要独立环境以便后续 hot-reload。建议 parser 内部创建独立 env

**验收标准**：
- 合法 skill 文件 → 返回 `SkillSchema`
- 缺 `name` 字段 → `SkillParseError`
- YAML 格式错误 → `SkillParseError`
- `render_skill_prompt()` 正确替换 `{{ form_data.product_name }}` 为实际值
- `render_skill_prompt()` 支持 `{% include %}` 标签（需确认模板文件路径）
- step.prompt 中包含 `{{ current_content }}`、`{{ review_result }}` 等运行时变量（由 engine 注入，parser 不处理）

**依赖**：任务 1

**工作量**：M（2 小时）

---

### 任务 3：Skill Engine 执行器 (P0)

**目标**：实现 `SkillEngine` 类，按 skill 定义的步骤序列执行 generate→review→rewrite 循环，流式 yield SSE 事件。

**涉及文件**：
- `backend/skill_engine/engine.py`（新建）
- `backend/tests/test_skill_engine_engine.py`（新建，mock LLM service）

**关键实现要点**：
1. `SkillEngine.__init__(self, llm_service)` — 注入 LLM 服务模块
2. `async execute(skill: SkillSchema, context: dict) -> AsyncGenerator[SSEEvent]`
3. 主循环逻辑：
   ```
   current_content = ""
   for round in range(max_iterations):
       for step in steps:
           prompt = render_skill_prompt(step, {**context, "current_content": current_content})
           if step.type == "generate":
               async for token in llm_service.stream_generate(prompt):
                   yield SSEEvent(event="chunk", content=token)
                   current_content += token
           elif step.type == "review":
               full = await _call_llm_once(prompt)
               yield SSEEvent(event="chunk", content=full)  # 前端需要看审核过程
               passed, issues = _parse_review_result(full, step.pass_condition)
               yield SSEEvent(event="review_result", passed=passed, issues=issues)
               if passed:
                   yield SSEEvent(event="done", content=current_content)
                   return
           elif step.type == "rewrite":
               current_content = ""
               async for token in llm_service.stream_generate(prompt):
                   yield SSEEvent(event="chunk", content=token)
                   current_content += token
   yield SSEEvent(event="done", content=current_content)
   ```
4. `_parse_review_result(text, pass_condition)` 实现：
   - 尝试 `json.loads()` 解析 `{"passed": bool, "issues": [...]}`
   - JSON 失败 → 降级为 `pass_condition in text` 关键词匹配（当前逻辑 `"审核通过" in text`）
   - issues 从 JSON 提取；降级模式为空列表
5. `_call_llm_once(prompt)` — 复用 `llm_service.get_llm()` 的 `ainvoke`（与当前 `document_service._call_llm_once` 相同）

**验收标准**：
- mock LLM 返回固定 token → 验证事件序列：chunk×N → done
- mock 审核不通过 → 触发 rewrite → 再 review → 通过 → done
- mock 审核始终不通过 → 达到 max_iterations → 强制 done
- 事件数 = generate token 数 + review token 数 + rewrite token 数 + review_result + done
- `_parse_review_result` JSON 解析优先，关键词降级

**依赖**：任务 1、任务 2

**工作量**：L（4 小时）

---

### 任务 4：Skill Loader 热加载 (P0)

**目标**：启动时扫描 `backend/skills/*.md` 目录，解析并缓存所有 skill，支持运行时热加载。

**涉及文件**：
- `backend/skill_engine/loader.py`（新建）
- `backend/tests/test_skill_engine_loader.py`（新建）

**关键实现要点**：
1. `SkillLoader.__init__(self, skills_dir: str)` — 传入 `backend/skills/` 路径
2. `load_all()` — 扫描 `skills_dir/*.md`，对每个文件调用 `parser.parse_skill_file()`
3. 缓存为 `dict[str, SkillSchema]`（key = `skill.name`）
4. `get(name: str) -> SkillSchema` — 返回 skill 或抛 `SkillNotFoundError`
5. `reload()` — 重新扫描目录，原子替换缓存引用（新 dict 替换旧 dict，无锁）
6. 启动时自动调用 `load_all()`（在 `SkillLoader.__init__` 中）

**验收标准**：
- 目录有 3 个 skill 文件 → 缓存 3 个 entry
- `get("prd-generate")` → 返回对应 `SkillSchema`
- `get("nonexistent")` → `SkillNotFoundError`
- `reload()` 后新文件被识别
- 空目录 → 空缓存，不抛异常

**依赖**：任务 1、任务 2

**工作量**：M（1.5 小时）

---

### 任务 5：Skill 文件编写 (P0)

**目标**：将 `backend/prompts/` 下的 5 个 Jinja2 模板（generate_prd/generate_api/generate_prompts + doc_review/doc_rewrite）合并为 3 个 skill 文件。

**涉及文件**：
- `backend/skills/`（新建目录）
- `backend/skills/prd-generate.md`（新建）
- `backend/skills/api-generate.md`（新建）
- `backend/skills/prompts-generate.md`（新建）

**关键实现要点**：
1. **`prd-generate.md`**：
   - generate step：从 `generate_prd.jinja2` 迁移，包含角色定义、表单数据、需求摘要、`{% include "docs/prd-template.md" %}`、续写逻辑
   - review step：从 `doc_review.jinja2` 迁移，`pass_condition: "审核通过"`，`{{ current_content }}` 变量待 engine 注入
   - rewrite step：从 `doc_rewrite.jinja2` 迁移，`{{ review_result }}` 变量待 engine 注入（engine 将 `_parse_review_result` 的 issues 串为文本传入）

2. **`api-generate.md`**：
   - generate step：从 `generate_api.jinja2` 迁移，`{{ prd_content }}` 变量
   - review step：同 doc_review 模板，侧重 API 完整性
   - rewrite step：同 doc_rewrite 模板

3. **`prompts-generate.md`**：
   - generate step：从 `generate_prompts.jinja2` 迁移，`{{ prd_content }}` + `{{ api_content }}` 变量
   - review step：同 doc_review 模板，侧重提示词覆盖
   - rewrite step：同 doc_rewrite 模板

4. 注意：skill 文件中 `{{ current_content }}`、`{{ review_result }}` 由 engine 在执行时注入 context；`{{ form_data }}`、`{{ requirements_summary }}`、`{{ prd_content }}`、`{{ api_content }}` 由前端传入 context

**验收标准**：
- 3 个 skill 文件均能被 parser 成功解析
- 解析后的 `SkillSchema.steps` 长度 = 3（generate/review/rewrite）
- 启动时 loader 扫描无报错
- 渲染后 prompt 内容与原模板等价

**依赖**：任务 2（parser 可用）

**工作量**：L（3 小时）

---

### 任务 6：后端集成 (P0)

**目标**：重构 `document_service.py`，废弃 `optimize_document_stream()`，将 `generate_document_stream()` 改为调用 skill engine。

**涉及文件**：
- `backend/services/document_service.py`（修改）
- `backend/api/documents.py`（修改）
- `backend/api/sse_utils.py`（修改）
- `backend/main.py`（修改）
- `backend/requirements.txt`（修改）

**关键实现要点**：

1. **`document_service.py` 重构**：
   - 删除 `_build_review_prompt()`、`_build_rewrite_prompt()`、`_has_issues()`、`_call_llm_once()` 方法
   - `generate_document_stream()` 改为：
     ```python
     from skill_engine import SkillLoader, SkillEngine
     # 全局变量在模块级别初始化
     _skill_loader = None
     
     def init_skill_engine(skills_dir: str):
         global _skill_loader
         _skill_loader = SkillLoader(skills_dir)
         _engine = SkillEngine()
     
     async def generate_document_stream(doc_type, form_data, requirements_summary, ...):
         skill = _skill_loader.get(f"{doc_type}-generate")
         context = { "form_data": ..., "requirements_summary": ..., ... }
         async for event in _engine.execute(skill, context):
             yield event
     ```
   - 保留 `_build_prompt_kwargs()` 用于构造 context（但不再 build prompt）

2. **`api/documents.py` 修改**：
   - `/optimize` 端点：仍保留但内部调用 `engine.execute(skill)` 处理 review→rewrite
   - 将 `document_service.generate_document_stream()` 返回的 `SSEEvent` 序列化为 JSON SSE
   - 优化端点需要处理新的 `review_result` 事件格式：`{"event": "review_result", "passed": true, "issues": []}`

3. **`api/sse_utils.py` 修改**：
   - `make_sse_stream()` 改为接受 `AsyncGenerator[SSEEvent]` 而非 `AsyncGenerator[str]`
   - 根据 SSEEvent.event 类型决定序列化格式：
     - `chunk` → `{"event": "chunk", "content": token}`
     - `review_result` → `{"event": "review_result", "passed": bool, "issues": [...]}`
     - `done` → `{"event": "done", "content": full_content}`
     - `error` → `{"event": "error", "content": msg}`

4. **`main.py` 修改**：
   - 应用启动时调用 `document_service.init_skill_engine("backend/skills")`
   - 放在路由挂载之后、`__main__` 之前

5. **`requirements.txt` 修改**：
   - 添加 `pyyaml>=6.0,<7.0`

6. **API 兼容性保证**：
   - `/stream` 端点输出事件格式与前端 `readStream` 兼容（chunk/done/error）
   - `/optimize` 端点多输出 `review_result` 事件，前端需处理（前端 PR 另议）
   - 响应头、状态码不变

**验收标准**：
- 启动后 `/health` 正常，无模块加载错误
- `POST /api/documents/prd/stream` 返回 SSE 流（mock LLM 可测试）
- `POST /api/documents/prd/optimize` 返回包含 review_result 事件的 SSE 流
- `requirements.txt` 包含 PyYAML
- 原有 `_has_issues` 测试删除或改为测试 `_parse_review_result`

**依赖**：任务 3、任务 4、任务 5

**工作量**：L（4 小时）

---

### 任务 7：验证与回归 (P1)

**目标**：确保 skill 驱动的新架构功能正确，输出质量不下降，SSE 事件格式前端可正常消费。

**涉及文件**：
- `backend/tests/` 下的新增测试文件

**关键实现要点**：

1. **集成测试**（`test_skill_integration.py`）：
   - 用 `mock_form_dict` fixture 分别测试三种文档的完整生成流程
   - mock `stream_generate()` 返回固定 token 序列
   - 验证：事件序列完整、done 事件有 content、review_result 有 passed
   
2. **输出质量对比**：
   - 分别在旧架构（git stash 回退）和新架构下，用相同 mock 数据生成文档
   - 手动对比两组输出，确认无明显质量差异
   - 如发现差异（模板变量渲染不一致），调整 skill 文件内容

3. **SSE 事件格式验证**：
   - `/stream`：前端 `readStream` 期望的 chunk/done/error 格式不变
   - `/optimize`：新增 review_result 事件，前端需更新 `readStream`（前端侧任务，此处只验证格式正确）

4. **热加载验证**：
   - 启动应用，加载 skill → 修改 skill 文件内容 → `loader.reload()` → 新请求使用新 prompt
   - 验证：修改后的 content 出现在输出中

5. **回归测试**：
   - 运行 `pytest backend/tests/` 确认所有现有测试通过
   - 特别注意 `test_services.py` 中的 `TestHasIssues` 和 `TestBuildPromptKwargs`
   - `TestHasIssues` 应迁移至 engine 的 `_parse_review_result` 测试

**验收标准**：
- 集成测试覆盖三种文档类型
- 输出质量与旧版对比无明显退化
- 热加载生效
- 全量 `pytest` 通过

**依赖**：任务 6

**工作量**：M（2 小时）

---

### 任务 8：清理与收尾 (P1)

**目标**：删除废弃的 Jinja2 模板文件，更新项目文档。

**涉及文件**：
- `backend/prompts/generate_prd.jinja2`（删除）
- `backend/prompts/generate_api.jinja2`（删除）
- `backend/prompts/generate_prompts.jinja2`（删除）
- `backend/prompts/doc_review.jinja2`（删除）
- `backend/prompts/doc_rewrite.jinja2`（删除）
- `AGENTS.md`（修改）

**注意**：以下文件保留不动：
- `backend/prompts/chat_system.jinja2`（对话用，不涉及）
- `backend/prompts/chat_summary.jinja2`（对话用，不涉及）
- `backend/prompts/chat-prompts.md`（对话用，不涉及）

**关键实现要点**：
1. 确认删除文件后，`backend/prompts/` 下只保留 chat 相关模板
2. `git rm` 5 个文件，确保版本控制删除
3. 更新 `AGENTS.md`：
   - 添加 `skill_engine/` 和 `skills/` 目录说明
   - 更新文档生成流程描述（从 Jinja2 模板 → skill 驱动）
   - 更新 API 端点说明（optimize 端点不再独立 review→rewrite）

**验收标准**：
- `backend/prompts/` 下不再有 generate_* 和 doc_* 模板
- 启动无 `FileNotFoundError`（无残留引用）
- `AGENTS.md` 反映新架构

**依赖**：任务 7（验证通过后清理）

**工作量**：S（30 分钟）

---

### 任务 9：可选增强 (P2)

**目标**：提供 skill 可见性和手动管理能力。

**涉及文件**：
- `backend/api/documents.py` 或 `backend/api/skills.py`（新建）
- `backend/skill_engine/loader.py`（增强）

**关键实现要点**：

1. **`GET /api/skills`**：
   - 返回已加载的 skill 列表：`[{"name": "prd-generate", "description": "...", "steps": 3}, ...]`
   - 从 loader 缓存读取

2. **`POST /api/skills/reload`**：
   - 调用 `loader.reload()`
   - 返回 `{"status": "ok", "skills": 3}`

3. **前端展示**（选做）：
   - 文档生成页面底部或侧边栏显示当前使用的 skill 名称
   - API 调用 `GET /api/skills` 获取列表

**验收标准**：
- API 返回正确的 skill 列表
- reload 后新 skill 生效
- 前端显示 skill 名称

**依赖**：任务 6

**工作量**：S（1 小时）

---

## 工作量汇总

| 任务 | 优先级 | 预估 | 依赖 |
|------|--------|------|------|
| 1. 数据模型 | P0 | 0.5h | - |
| 2. Parser | P0 | 2h | 1 |
| 3. Engine | P0 | 4h | 1, 2 |
| 4. Loader | P0 | 1.5h | 1, 2 |
| 5. Skill 文件 | P0 | 3h | 2 |
| 6. 后端集成 | P0 | 4h | 3, 4, 5 |
| 7. 验证回归 | P1 | 2h | 6 |
| 8. 清理收尾 | P1 | 0.5h | 7 |
| 9. 可选增强 | P2 | 1h | 6 |
| **合计** | | **18.5h** | |

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Jinja2 `{% include %}` 在 skill 文件中的路径解析 | 高 | parser 内建 FileSystemLoader 指向项目根，与现有 `llm_service.py` 一致 |
| `{{ review_result }}` 在 rewrite prompt 中的格式不明确 | 中 | engine 将 issues 列表序列化为易读文本传给 context |
| optimize 端点新增 `review_result` 事件，前端未处理 | 中 | 前端 `readStream` 需添加 `review_result` case，未处理时忽略即可（下个迭代修复） |
| skill 文件内容与旧模板`{% include %}` 路径不一致 | 中 | 集成测试中对比新旧输出 |

## 分支策略

- 在独立分支 `feat/skill-driven-doc-gen` 上开发
- 合并前需通过全量 `pytest`
- 避免 `main.py` 中大范围重构 — 只添加 loader 初始化和 import
