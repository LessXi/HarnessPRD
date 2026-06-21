# Tasks: skill-driven-doc-gen

## 1. Skill Engine 数据模型 (P0)

- [ ] 1.1 创建 `backend/skill_engine/__init__.py` 模块入口
- [ ] 1.2 创建 `backend/skill_engine/models.py` — Pydantic 数据模型（SkillSchema、StepSchema、SSEEvent 等）
- [ ] 1.3 编写数据模型单元测试（合法/非法 skill 解析验证）

## 2. Skill Parser (P0)

- [ ] 2.1 创建 `backend/skill_engine/parser.py` — 解析 .md 文件，分离 YAML frontmatter 和 Markdown body
- [ ] 2.2 实现 PyYAML 解析 + Pydantic 校验，非法 skill 抛出 SkillParseError
- [ ] 2.3 实现 `{{ variable }}` 模板变量替换逻辑（支持嵌套路径如 `form_data.product_name`）
- [ ] 2.4 编写 parser 单元测试（合法文件、缺字段、YAML 格式错误、模板替换）
- [ ] 2.5 **【Debug 集成】** parser 中导入 loguru logger，解析失败时 `logger.bind(event="skill_parse_error").warning(...)` 记录文件名和错误原因

## 3. Skill Engine 执行器 (P0)

- [ ] 3.1 创建 `backend/skill_engine/engine.py` — `SkillEngine` 类，`async execute(skill, context) -> AsyncGenerator[SSEEvent]`
- [ ] 3.2 实现 `generate` 步骤：流式调用 `llm_service.stream_generate()` → yield chunk 事件
- [ ] 3.3 实现 `review` 步骤：非流式调用 `llm_service._call_llm_once()` → 判断 pass_condition → yield review_result 事件
- [ ] 3.4 实现 `rewrite` 步骤：流式调用（输入原文 + 审核意见） → yield chunk 事件
- [ ] 3.5 实现 review→rewrite 循环控制（max_iterations 上限，通过则跳出）
- [ ] 3.6 编写 engine 单元测试（mock LLM service，验证事件序列和循环逻辑）
- [ ] 3.7 **【Debug 集成】** engine 中导入 loguru logger + `classify_error`：
  - `logger.bind(event="skill_execution_start").info(...)` 记录 skill 名称和 doc_type
  - 每个 step 执行前后 `logger.bind(event="skill_step_start"/"skill_step_complete").info(...)`
  - `context` dict 中提取 `session_id` 透传给 `llm_service.stream_generate(session_id=...)` 和 `_call_llm_once(session_id=...)`
  - LLM 调用异常用 `classify_error(e)` 分类后 `logger.bind(event="llm_error").error(...)` 记录

## 4. Skill Loader 热加载 (P0)

- [ ] 4.1 创建 `backend/skill_engine/loader.py` — `SkillLoader` 类，启动时扫描目录
- [ ] 4.2 实现内存缓存（key=skill name），`get(name)` 方法
- [ ] 4.3 实现 `reload()` 方法 — 重新扫描目录，原子替换缓存
- [ ] 4.4 编写 loader 单元测试（扫描、缓存、热加载、文件不存在）
- [ ] 4.5 **【Debug 集成】** loader 中导入 loguru logger：
  - 启动扫描时 `logger.bind(event="skill_loader_scan").info(...)` 记录扫描目录和 skill 数量
  - 热加载时 `logger.bind(event="skill_loader_reload").info(...)` 记录变更
  - 单个 skill 解析失败不阻塞整体，`logger.bind(event="skill_parse_error").warning(...)`

## 5. Skill 文件编写 (P0)

- [ ] 5.1 创建 `backend/skills/` 目录
- [ ] 5.2 编写 `backend/skills/prd-generate.md` — 将 `generate_prd.jinja2` + `doc_review.jinja2` + `doc_rewrite.jinja2` 内容迁移为 skill 格式
- [ ] 5.3 编写 `backend/skills/api-generate.md` — 将 `generate_api.jinja2` + 审核改写内容迁移
- [ ] 5.4 编写 `backend/skills/prompts-generate.md` — 将 `generate_prompts.jinja2` + 审核改写内容迁移
- [ ] 5.5 验证：启动时 loader 能成功解析全部 3 个 skill 文件

## 6. 后端集成 (P0)

- [ ] 6.1 重构 `backend/services/document_service.py` — 移除 `_build_review_prompt()`、`_build_rewrite_prompt()`、`_has_issues()` 等硬编码方法
- [ ] 6.2 `generate_document_stream()` 改为调用 `engine.execute(skill, context)`
- [ ] 6.3 `optimize_document_stream()` 废弃（review→rewrite 由 skill engine 内部处理），保留端点但路由到 engine
- [ ] 6.4 在 `backend/main.py` 或 `backend/api/documents.py` 中初始化 loader（应用启动时）
- [ ] 6.5 确保 `requirements.txt` 包含 `PyYAML` 依赖
- [ ] 6.6 **【Debug 集成】** 确保 `session_id` 从 request.state 提取后通过 `context` dict 透传到 engine → llm_service，维持 LangSmith trace 和 correlation_id 链路不断。`document_service.py` 重构后保留现有 debug 日志（`doc_generation_start`/`doc_generation_complete`/`doc_optimization_round`/`llm_error` 等 event）

## 7. 验证与回归 (P1)

- [ ] 7.1 编写集成测试：用 mock form_data 分别测试三种文档的完整生成流程
- [ ] 7.2 对比新旧输出：skill 驱动的输出质量不低于原 Jinja2 模板输出
- [ ] 7.3 验证 SSE 事件格式：chunk/done/error/review_result 事件格式正确，前端可正常消费
- [ ] 7.4 验证热加载：修改 skill 文件内容后 reload，新请求使用新 prompt

## 8. 清理与收尾 (P1)

- [ ] 8.1 删除 `backend/prompts/generate_prd.jinja2`
- [ ] 8.2 删除 `backend/prompts/generate_api.jinja2`
- [ ] 8.3 删除 `backend/prompts/generate_prompts.jinja2`
- [ ] 8.4 删除 `backend/prompts/doc_review.jinja2`
- [ ] 8.5 删除 `backend/prompts/doc_rewrite.jinja2`
- [ ] 8.6 更新 `AGENTS.md` — 反映新的 skill 引擎架构

## 9. 可选增强 (P2)

- [ ] 9.1 新增 `GET /api/skills` — 列出已加载的 skill 名称和版本
- [ ] 9.2 新增 `POST /api/skills/reload` — 手动触发热加载
- [ ] 9.3 前端在文档生成页面显示当前使用的 skill 名称（纯展示）
