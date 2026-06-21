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
