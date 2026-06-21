## Context

当前 `questions_config.json` 为自定义 DSL，定义 17 个表单字段（11 基础 + 6 高级）。前端 `FormStep.tsx` 按 `type` 分派渲染控件（text/textarea/select/radio/list），但校验逻辑为手写 `validate()` 函数。后端 `FormData` Pydantic 模型虽通过 `_build_form_data_model()` 动态构建，但 API 层 4 个 Request 模型均以 `form_data: dict[str, Any]` 接收，校验未生效。

改造目标：以标准 JSON Schema 为单一事实来源，驱动前后端校验、类型生成、预览面板。

## Goals / Non-Goals

**Goals:**
- `product_schema.json`（JSON Schema）替代 `questions_config.json`
- 前端 ajv 消费 Schema 做实时校验，替代手写 `validate()`
- 新增分步 JSON 预览 Modal（填表 → 按钮 → 弹出）
- API 层 `form_data` 从 `dict[str, Any]` → Pydantic `FormData` 强类型
- 从 JSON Schema 生成 TypeScript `FormData` 接口
- localStorage `form_data` 加 `schema_version` + 迁移
- Prompt 模板字段引用启动时校验

**Non-Goals:**
- 对话澄清交互改动
- Skill Engine 生成流程改动
- `ProjectState` 全量类型化
- CI 阻断式静态检查

## Decisions

### 1. Schema 文件位置：`backend/core/product_schema.json`

**选择**：放在 `backend/core/`，与现有 `questions_config.json` 同目录。

**理由**：
- 与现有 `field_registry.py` 加载路径一致，后端改动最小
- 前端通过 Vite `import` 直接读取 JSON 文件（Vite 支持 JSON 导入），无需额外 API
- 避免引入 `shared/` 目录打破现有两层结构

**备选**：`shared/schemas/` 共享目录 — 更规范但引入新目录层，对当前 2 人项目过度设计。

### 2. Schema 结构设计：JSON Schema + 自定义 UI 扩展

**选择**：标准 JSON Schema Draft-07，附加 `x-ui` 自定义属性承载 UI 元数据。

```json
{
  "$schema": "https://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "product_name": {
      "type": "string",
      "minLength": 1,
      "x-ui": {
        "label": "产品名称",
        "widget": "text",
        "description": "给产品起一个简洁有辨识度的名称",
        "question": "你的产品叫什么名字？",
        "group": "base",
        "required": true
      }
    },
    "mvp_features": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 3,
      "x-ui": {
        "label": "MVP 核心功能",
        "widget": "list",
        "description": "至少列出 3 条",
        "group": "base",
        "required": true
      }
    },
    "platform_type": {
      "type": "string",
      "enum": ["web", "mobile", "wechat_miniprogram", "desktop", "multi"],
      "x-ui": {
        "label": "目标平台",
        "widget": "select",
        "group": "base",
        "required": true
      }
    }
  },
  "required": ["product_name", "one_liner", "problem_statement", "target_users", "mvp_features", "platform_type", "needs_auth", "needs_database", "page_count"],
  "x-meta": {
    "schema_version": "1.0.0"
  }
}
```

**理由**：
- JSON Schema `type`、`enum`、`minLength`、`minItems` 直接用于 ajv/Pydantic 校验
- `x-ui` 承载 UI 渲染信息，前端按 `widget` 分派控件
- `x-meta.schema_version` 驱动 localStorage 迁移
- 向后兼容：`field_registry.py` 可同时支持旧 `questions_config.json` 和新 Schema（过渡期）

**备选**：纯 JSON Schema 不带 UI 扩展，另建 `questions_config.json` 管 UI → 两份文件需同步，违反单一事实来源原则。

### 3. 前端校验：ajv

**选择**：ajv（JSON Schema validator）。

**理由**：
- 原生 JSON Schema 支持，无需转换层
- 体积小（~120KB gzipped ~30KB），适合前端
- 支持自定义关键字（可扩展 `x-ui` 校验）
- 实时校验：onChange 触发 ajv.validate()，毫秒级

**备选**：zod — TypeScript 体验更好，但需 JSON Schema → zod schema 转换层，增加维护成本。

### 4. API 边界强类型：Pydantic FormData

**选择**：`form_data: FormData` 替换 4 处 `dict[str, Any]`。

**理由**：
- FastAPI 自动校验，不合法请求返回 422（含详细错误路径）
- 前端已做同源 ajv 校验，正常用户不会触发 422 — 只作最后防线
- `FormData` 模型从 `product_schema.json` 构建（替代 `_build_form_data_model` 手动逻辑）

**行为变化**：当前用户发缺失字段 → 后端接收继续（LLM 可能出怪结果）。改为严格模式后 → 422 明确拒绝。前端预览面板确保用户提交前已修正错误。

**备选**：保持 `dict` + 服务层手动校验 → 类型安全无保障，违反 Schema-First 原则。

### 5. JSON 预览 Modal：分步触发，与提交解耦

**选择**：表单底部双按钮：「预览 JSON」+「提交并开始 AI 对话」。预览 Modal 为纯展示窗口，不包含提交功能。

**Modal 内容**：
- 结构化 JSON：使用 `@monaco-editor/react` 加载 Monaco Editor（readOnly 模式，language="json"，minimap 关闭）
- 校验失败字段：通过 Monaco `editor.deltaDecorations()` 标注红色波浪线 + hover message 显示错误原因
- `_schema_version` 字段显示
- 仅「关闭」按钮，无「确认提交」

**提交流程**（独立路径）：
- 点击「提交并开始 AI 对话」→ ajv 校验 → 通过则调 `onSubmit` → 失败则在表单内显示错误

**理由**：预览与提交职责解耦 — 预览是查看工具，提交是流程推进。合并会增加用户困惑（Modal 里"确认提交"让用户以为必须预览才能提交）。

### 6. TypeScript 类型生成

**选择**：手动维护 `FormData` TypeScript 接口，以 `product_schema.json` 为参照。

**理由**：
- 17 个字段，结构稳定，手动接口维护成本极低
- 避免引入 `json-schema-to-typescript` 等构建时依赖
- 可后续自动化（P2），当前手动更快

**备选**：`json-schema-to-typescript` 自动生成 — 增加构建步骤，当前收益不抵成本。

### 7. localStorage 版本化

**选择**：`form_data` 中嵌入 `_schema_version: "1.0.0"` 字段。

加载逻辑：
```typescript
function migrateFormData(data: Record<string, any>): FormData {
  const version = data._schema_version || "0.0.0";
  if (version === "1.0.0") return data as FormData;
  // v0 → v1: 补全缺失的选填字段默认值
  return applyDefaults(data, productSchema);
}
```

**理由**：`_schema_version` 在 Schema 的 `x-meta` 中定义，前后端一致。迁移函数集中管理，后续 Schema 迭代只需加 case。

### 8. Prompt 模板字段校验

**选择**：后端启动时加载 Schema 获取合法字段集合，扫描 Jinja2 / Skill 模板中 `{{ field_name }}` 引用，对不存在的字段名发出 WARNING 日志。

**实现**：
```python
def validate_template_fields(template_text: str, schema_fields: set[str]) -> list[str]:
    """返回模板中引用的不存在字段名"""
    referenced = set(re.findall(r'\{\{\s*(\w+)\s*\}\}', template_text))
    return list(referenced - schema_fields - {"form_fields", "chat_log", "requirements_summary", "current_content", "prd_content", "api_content", "previous_content", "session_id", "doc_type"})
```

**理由**：启动时 warn 足够 — 无 CI Pipeline，阻断部署不现实。白名单排除非表单上下文变量（`form_fields`、`chat_log` 等）。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| **BREAKING**: API `form_data` 类型变更，旧前端发 `Record<string, any>` 可能被 FastAPI 422 拒绝 | 前端先部署，Schema 校验通过后才发请求；过渡期后端保留 manual fallback |
| `product_schema.json` 与旧 `questions_config.json` 双存过渡期数据不一致 | `field_registry.py` 优先读 Schema，降级读旧配置；过渡期后删除旧文件 |
| ajv 校验规则与后端 Pydantic 校验不完全一致 | 标准 JSON Schema 关键字（type/enum/minLength/minItems）双向一致；自定义规则写单元测试对齐 |
| Prompt 字段名拼写错误 | 启动时 warn 覆盖 Chat + Skill 模板，开发者修复后 warn 消失 |
| localStorage 旧数据迁移失败导致页面崩溃 | try-catch 包裹迁移逻辑，失败时用 Schema 默认值重建 |

## Open Questions

（已全部在探索阶段澄清，无遗留）
