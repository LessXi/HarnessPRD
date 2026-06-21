# Comet Design Handoff

- Change: skill-driven-doc-gen
- Phase: design
- Mode: compact
- Context hash: 394653e359e50103fe89b3f49af079ac40a9a34a7240eaa58a294d3ea710e73d

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/skill-driven-doc-gen/proposal.md

- Source: openspec/changes/skill-driven-doc-gen/proposal.md
- Lines: 1-42
- SHA256: 9cf978a65620b00788e4fa3e2bfa7b79c1856b24f6be76a13d10a1b58792c30c

```md
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
```

## openspec/changes/skill-driven-doc-gen/design.md

- Source: openspec/changes/skill-driven-doc-gen/design.md
- Lines: 1-210
- SHA256: 5901feee1b1cca8dfa38d8d1590ac3284eb6c71c1366689d91da572247df07d8

[TRUNCATED]

```md
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
```

Full source: openspec/changes/skill-driven-doc-gen/design.md

## openspec/changes/skill-driven-doc-gen/tasks.md

- Source: openspec/changes/skill-driven-doc-gen/tasks.md
- Lines: 1-68
- SHA256: c6412b906bc4c081bfcce855b0cf88483c8ef8acbcdc5027e776d117c918a3a5

```md
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

## 3. Skill Engine 执行器 (P0)

- [ ] 3.1 创建 `backend/skill_engine/engine.py` — `SkillEngine` 类，`async execute(skill, context) -> AsyncGenerator[SSEEvent]`
- [ ] 3.2 实现 `generate` 步骤：流式调用 `llm_service.stream_generate()` → yield chunk 事件
- [ ] 3.3 实现 `review` 步骤：非流式调用 `llm_service._call_llm_once()` → 判断 pass_condition → yield review_result 事件
- [ ] 3.4 实现 `rewrite` 步骤：流式调用（输入原文 + 审核意见） → yield chunk 事件
- [ ] 3.5 实现 review→rewrite 循环控制（max_iterations 上限，通过则跳出）
- [ ] 3.6 编写 engine 单元测试（mock LLM service，验证事件序列和循环逻辑）

## 4. Skill Loader 热加载 (P0)

- [ ] 4.1 创建 `backend/skill_engine/loader.py` — `SkillLoader` 类，启动时扫描目录
- [ ] 4.2 实现内存缓存（key=skill name），`get(name)` 方法
- [ ] 4.3 实现 `reload()` 方法 — 重新扫描目录，原子替换缓存
- [ ] 4.4 编写 loader 单元测试（扫描、缓存、热加载、文件不存在）

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
```

## openspec/changes/skill-driven-doc-gen/specs/doc-gen-skills/spec.md

- Source: openspec/changes/skill-driven-doc-gen/specs/doc-gen-skills/spec.md
- Lines: 1-78
- SHA256: 7a21929ee09cb1671bdeedecd31f3f08a523db5ca8e4dd4b7eef2bf3111a50c4

```md
# Spec: doc-gen-skills

文档生成 Skill 文件定义，覆盖 PRD、API 文档、提示词套件三种文档类型的生成、审核、改写流程。

## ADDED Requirements

### Requirement: PRD 生成 Skill

系统 SHALL 提供 `prd-generate.md` skill 文件，定义 PRD 文档的生成 prompt 和审核改写循环。

PRD 生成 prompt SHALL 基于需求摘要和表单数据，产出涵盖 10 个章节（产品概述、用户画像、功能需求、非功能需求、接口概览、数据模型、用户流程、边界条件、发布计划、附录）的 Markdown 文档。

审核维度 SHALL 包括：完整性（10 章是否齐全）、一致性（前后描述无矛盾）、清晰度（非技术人员可理解）、可执行性（研发可直接开工）。

#### Scenario: 生成 PRD 初稿

- **WHEN** 用户提交表单数据和需求摘要
- **THEN** 引擎加载 `prd-generate.md` → 执行 generate 步 → 流式输出 PRD Markdown，至少包含 10 个章节标题

#### Scenario: PRD 审核发现缺失章节

- **WHEN** 生成的 PRD 缺失 "发布计划" 章节
- **THEN** review 步指出缺失 → rewrite 步补全 → 再次 review 通过

### Requirement: 接口文档生成 Skill

系统 SHALL 提供 `api-generate.md` skill 文件，定义接口文档的生成 prompt 和审核改写循环。

接口文档生成 prompt SHALL 基于需求摘要和已确认的 PRD 内容（特别是 PRD 第 5 章接口概览和第 6 章数据模型），产出包含 5 章（概述、接口列表、请求/响应格式、错误码、认证方案）的 Markdown 文档。

#### Scenario: 生成接口文档

- **WHEN** 用户确认 PRD 后进入接口文档生成
- **THEN** 引擎加载 `api-generate.md`，context 包含 `prd_content` → 流式输出接口文档 Markdown

#### Scenario: 接口文档与 PRD 一致性审核

- **WHEN** review 步执行
- **THEN** 检查接口文档中的接口是否与 PRD 第 5 章一致，数据模型是否与 PRD 第 6 章一致

### Requirement: 提示词套件生成 Skill

系统 SHALL 提供 `prompts-generate.md` skill 文件，定义提示词套件的生成 prompt 和审核改写循环。

提示词套件生成 prompt SHALL 基于需求摘要、PRD 内容、接口文档内容，产出包含 5 类提示词（需求澄清、PRD 生成、接口文档生成、代码生成、测试用例生成）的 Markdown 文档。

#### Scenario: 生成提示词套件

- **WHEN** 用户确认接口文档后进入提示词套件生成
- **THEN** 引擎加载 `prompts-generate.md`，context 包含 `prd_content` 和 `api_content` → 流式输出提示词套件 Markdown

#### Scenario: 提示词一致性审核

- **WHEN** review 步执行
- **THEN** 检查各类提示词是否覆盖 PRD 中的核心功能点、是否与接口文档中的 API 一致

### Requirement: Skill 文件目录结构

系统后端 SHALL 按以下结构存放 skill 文件：

```
backend/skills/
├── prd-generate.md
├── api-generate.md
└── prompts-generate.md
```

所有 skill 文件 SHALL 为合法的 `.md` 文件，YAML frontmatter 与 Markdown body 之间用 `---` 分隔。

#### Scenario: 启动时扫描 skill 目录

- **WHEN** SkillLoader 初始化
- **THEN** 扫描 `backend/skills/` 下所有 `.md` 文件，按 `name` 字段建立索引

#### Scenario: 缺少 skill 文件

- **WHEN** 请求的文档类型对应的 skill 文件不存在于 `backend/skills/`
- **THEN** 引擎返回明确的错误信息，指示缺失的 skill 文件名
```

## openspec/changes/skill-driven-doc-gen/specs/skill-engine/spec.md

- Source: openspec/changes/skill-driven-doc-gen/specs/skill-engine/spec.md
- Lines: 1-102
- SHA256: d58de0519598cdc714bfb5e499347bfb123731e9344a2fe01374136154941802

[TRUNCATED]

```md
# Spec: skill-engine

Skill Engine 是文档生成后端的核心模块，负责解析 `.md` skill 文件并按声明的步骤链式执行 LLM 调用。

## ADDED Requirements

### Requirement: Skill 文件解析

系统 SHALL 解析符合 Claude skill 兼容格式的 `.md` 文件（YAML frontmatter + Markdown body），并输出 Pydantic 校验后的 SkillSchema 数据结构。

YAML frontmatter 必填字段：`name`、`description`、`steps`。`steps` 中每步必填 `id`、`type`（`generate` | `review` | `rewrite`）、`prompt`。可选字段：`version`、`max_iterations`。每步可选字段：`stream`（默认 true）、`criteria`（仅 review 步）、`pass_condition`（仅 review 步）。

#### Scenario: 解析有效的 skill 文件

- **WHEN** 引擎加载格式正确的 `.md` skill 文件
- **THEN** 返回 SkillSchema 对象，包含所有字段的解析结果

#### Scenario: 解析缺少必填字段的 skill 文件

- **WHEN** skill YAML frontmatter 缺少 `steps` 字段
- **THEN** 抛出 SkillParseError，包含文件路径和缺失字段名

#### Scenario: 解析无效 YAML frontmatter

- **WHEN** skill 文件的 YAML frontmatter 格式错误（如缩进不对）
- **THEN** 抛出 SkillParseError，包含文件路径和 YAML 解析错误详情

### Requirement: Prompt 链式执行

系统 SHALL 按 skill 文件中 `steps` 声明的顺序依次执行每步，每步调用 LLM 并产出对应事件。

步骤类型：
- `generate`: 流式调用 LLM → yield SSE `chunk` 事件（逐 token）
- `review`: 非流式调用 LLM → 检查输出是否含 `pass_condition` → yield `review_result` 事件（含审核意见和通过状态）
- `rewrite`: 流式调用 LLM（输入：原文 + 审核意见） → yield SSE `chunk` 事件

每步执行前，SHALL 将上下文变量（`form_data`、`requirements_summary`、`prd_content`、`api_content` 等）通过 `{{ variable_name }}` 语法替换到 `prompt` 中。

#### Scenario: 单步 generate 执行

- **WHEN** skill 仅包含一个 `generate` 步骤，`stream: true`
- **THEN** 引擎逐 token 流式输出 `chunk` 事件，最后输出 `done` 事件，生成的完整文档内容作为 `done` 事件的 payload

#### Scenario: review→rewrite 循环通过

- **WHEN** skill 包含 `review` + `rewrite` 步骤，review 输出含 "审核通过"（满足 `pass_condition`）
- **THEN** 引擎执行 review → 判断通过 → 跳过 rewrite → 输出 `done` 事件，含当前文档内容

#### Scenario: review→rewrite 循环 1 轮后通过

- **WHEN** skill 包含 review + rewrite，第一轮 review 输出不含 "审核通过"
- **THEN** 引擎执行 review → 判断不通过 → 执行 rewrite（流式输出 chunk） → 再执行 review → 通过 → 输出 `done`

#### Scenario: review→rewrite 循环达到 max_iterations 上限

- **WHEN** skill 设置 `max_iterations: 2`，review 连续 2 轮均未通过
- **THEN** 引擎在 2 轮后终止循环，输出最后 rewrite 的内容作为 `done` 事件 payload

#### Scenario: 模板变量替换

- **WHEN** skill prompt 中包含 `{{ form_data.product_name }}`
- **THEN** 引擎在调用 LLM 前将 `{{ form_data.product_name }}` 替换为实际值

### Requirement: 热加载

系统 SHALL 支持在运行时重新加载 skill 文件目录，新请求使用新版本 skill，活跃请求继续使用加载时的版本。

#### Scenario: 启动时加载所有 skill

- **WHEN** SkillLoader 初始化时指定 `backend/skills/` 目录
- **THEN** 扫描目录下所有 `.md` 文件，解析并缓存到内存（key 为 skill name）

#### Scenario: 热加载触发

- **WHEN** 调用 `loader.reload()` 或访问 reload API 端点
- **THEN** 重新扫描目录，解析新版 skill 文件，更新缓存；旧版本保留直到所有引用释放

#### Scenario: skill 文件不存在

- **WHEN** 请求的 skill name 在缓存中不存在
```

Full source: openspec/changes/skill-driven-doc-gen/specs/skill-engine/spec.md

