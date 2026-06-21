# Brainstorm Summary

- Change: skill-driven-doc-gen
- Date: 2026-06-21

## 确认的技术方案

**Skill Engine 核心架构**：
- `models.py` — Pydantic 数据模型（SkillSchema、StepSchema、SSEEvent）
- `parser.py` — 解析 .md 文件（YAML frontmatter + Markdown body）→ SkillSchema，Jinja2 渲染模板变量
- `engine.py` — `async execute(skill, context) -> AsyncGenerator[SSEEvent]`，统一全流式执行
- `loader.py` — 目录扫描 + 内存缓存 + `reload()` 原子替换

**5 项关键决策**：
1. **全流式 AsyncGenerator**：generate/review/rewrite 三步骤统一流式，去掉 stream 配置字段，review 过程用户可见
2. **Jinja2 模板渲染**：复用现有 Jinja2 依赖，Engine FileSystemLoader 指向项目根，`{% include %}` 和 `{{ var }}` 照常工作
3. **混合审核判断**：JSON 结构化输出优先（`{"passed": bool, "issues": [...]}`），解析失败降级为关键词匹配
4. **简化 Skill 格式**：去掉 stream/criteria/version 字段，只保留 name/description/max_iterations/steps
5. **直接内嵌模板内容**：现有 Jinja2 模板内容复制粘贴到 skill prompt 字段，步骤间变量由 engine 自动注入

**已有模板迁移**：
- generate_prd/api/prompts.jinja2 → 各自 skill 的 generate step prompt
- doc_review.jinja2 → 三个 skill 共用 review step prompt
- doc_rewrite.jinja2 → 三个 skill 共用 rewrite step prompt
- Engine 自动注入步骤间变量：current_content、review_result、doc_type

## 关键取舍与风险

- 去掉步骤级流式控制 → 简化但失去灵活性（未来可重新加回）
- Jinja2 `{% include %}` 路径硬编码项目根 → 目录调整需同步
- 大 prompt 嵌入 YAML → skill 文件较长但自包含

## 测试策略

- 单元测试：parser（合法/非法 skill）、engine（mock LLM 验证事件序列和循环逻辑）、loader（扫描/缓存/热加载）
- 集成测试：三种文档全流程用 mock form_data 驱动，对比新旧输出质量

## Spec Patch

无（specs 已在 open 阶段充分覆盖，brainstorming 未发现需补充的验收场景）
