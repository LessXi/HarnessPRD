# Proposal: skill-driven-doc-gen

## Why

当前 HarnessPRD 的文档生成流程（PRD、API、Prompts）硬编码在 `document_service.py` 中——生成 prompt、审核标准、改写逻辑、迭代轮次全部写死在代码里。每调整一个 prompt 或审核维度就要改代码、重启服务。三类文档（PRD/API/Prompts）共享相同的代码路径但无法独立演进。这导致：修改成本高、实验迭代慢、文档质量优化困难。

引入 **Skill 引擎**——将文档生成的 prompt 链式编排从代码中解耦为可热加载的 `.md` skill 文件（Claude skill 兼容格式），让文档生成流程可配置、可热更新、可独立演进。

## What Changes

- **新增** `backend/skill_engine/` 模块：Skill 解析器 + Prompt 链执行 pipeline + 热加载管理器
- **新增** `backend/skills/` 目录：存放 PRD/API/Prompts 的生成 skill 和审核改写 skill（`.md` 格式，YAML frontmatter + Markdown body）
- **重构** `backend/services/document_service.py`：移除硬编码的 prompt 构建和 Review→Rewrite 循环，改为调用 skill engine
- **保留** API 端点签名不变（`POST /api/documents/{type}/stream` 等），前端无需改动
- **保留** SSE 流式传输机制，skill engine 包装为流式输出

## Capabilities

### New Capabilities

- `skill-engine`: Skill 文件解析（YAML frontmatter + Markdown）、Prompt 链执行 pipeline、热加载管理器
- `doc-gen-skills`: PRD/API/Prompts 的 skill 文件定义（生成规则、审核维度、改写策略、迭代控制）

### Modified Capabilities

（无——现有 spec 如存在则无需修改，本 change 是架构改造，不改变功能行为）

## Impact

- **后端核心**: `backend/services/document_service.py` 大幅简化，委托给 skill engine
- **新增模块**: `backend/skill_engine/`（解析器、引擎、加载器）
- **新增资源**: `backend/skills/` 目录（skill 文件，后续可扩展）
- **依赖**: 引入 `PyYAML`（如未安装）用于解析 skill frontmatter
- **前端**: 无改动（API 端点签名不变）
- **LLM 调用**: 调用次数和 token 消耗基本不变（skill 文件内容替代了原硬编码 prompt）

## 非目标

- 不提供 skill 在线编辑器/管理 UI
- 不改变前端交互流程
- 不引入 DSPy、LangGraph 等新框架
- 不修改对话（chat）和摘要生成流程
