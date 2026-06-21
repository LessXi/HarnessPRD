# Tasks: skill-driven-doc-gen

## 1. Skill Engine 数据模型 (P0)

- [x] 1.1 创建 `backend/skill_engine/__init__.py` 模块入口
- [x] 1.2 创建 `backend/skill_engine/models.py` — Pydantic 数据模型（SkillSchema、StepSchema、SSEEvent 等）
- [x] 1.3 编写数据模型单元测试（合法/非法 skill 解析验证）

## 2. Skill Parser (P0)

- [x] 2.1 创建 `backend/skill_engine/parser.py` — 解析 .md 文件，分离 YAML frontmatter 和 Markdown body
- [x] 2.2 实现 PyYAML 解析 + Pydantic 校验，非法 skill 抛出 SkillParseError
- [x] 2.3 实现 `{{ variable }}` 模板变量替换逻辑（支持嵌套路径如 `form_data.product_name`）
- [x] 2.4 编写 parser 单元测试（合法文件、缺字段、YAML 格式错误、模板替换）

## 3. Skill Engine 执行器 (P0)

- [x] 3.1 创建 `backend/skill_engine/engine.py` — `SkillEngine` 类，`async execute(skill, context) -> AsyncGenerator[SSEEvent]`
- [x] 3.2 实现 `generate` 步骤：流式调用 `llm_service.stream_generate()` → yield chunk 事件
- [x] 3.3 实现 `review` 步骤：非流式调用 `llm_service._call_llm_once()` → 判断 pass_condition → yield review_result 事件
- [x] 3.4 实现 `rewrite` 步骤：流式调用（输入原文 + 审核意见） → yield chunk 事件
- [x] 3.5 实现 review→rewrite 循环控制（max_iterations 上限，通过则跳出）
- [x] 3.6 编写 engine 单元测试（mock LLM service，验证事件序列和循环逻辑）

## 4. Skill Loader 热加载 (P0)

- [x] 4.1 创建 `backend/skill_engine/loader.py` — `SkillLoader` 类，启动时扫描目录
- [x] 4.2 实现内存缓存（key=skill name），`get(name)` 方法
- [x] 4.3 实现 `reload()` 方法 — 重新扫描目录，原子替换缓存
- [x] 4.4 编写 loader 单元测试（扫描、缓存、热加载、文件不存在）

## 5. Skill 文件编写 (P0)

- [x] 5.1 创建 `backend/skills/` 目录
- [x] 5.2 编写 `backend/skills/prd-generate.md` — 将 `generate_prd.jinja2` + `doc_review.jinja2` + `doc_rewrite.jinja2` 内容迁移为 skill 格式
- [x] 5.3 编写 `backend/skills/api-generate.md` — 将 `generate_api.jinja2` + 审核改写内容迁移
- [x] 5.4 编写 `backend/skills/prompts-generate.md` — 将 `generate_prompts.jinja2` + 审核改写内容迁移
- [x] 5.5 验证：启动时 loader 能成功解析全部 3 个 skill 文件

## 6. 后端集成 (P0)

- [x] 6.1 重构 `backend/services/document_service.py` — 移除 `_build_review_prompt()`、`_build_rewrite_prompt()`、`_has_issues()` 等硬编码方法
- [x] 6.2 `generate_document_stream()` 改为调用 `engine.execute(skill, context)`
- [x] 6.3 `optimize_document_stream()` 废弃（review→rewrite 由 skill engine 内部处理），保留端点但路由到 engine
- [x] 6.4 在 `backend/main.py` 或 `backend/api/documents.py` 中初始化 loader（应用启动时）
- [x] 6.5 确保 `requirements.txt` 包含 `PyYAML` 依赖

## 7. 验证与回归 (P1)

- [x] 7.1 编写集成测试：用 mock form_data 分别测试三种文档的完整生成流程
- [x] 7.2 对比新旧输出：skill 驱动的输出质量不低于原 Jinja2 模板输出
- [x] 7.3 验证 SSE 事件格式：chunk/done/error/review_result 事件格式正确，前端可正常消费
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
