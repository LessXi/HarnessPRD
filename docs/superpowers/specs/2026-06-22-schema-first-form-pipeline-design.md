---
comet_change: schema-first-form-pipeline
role: technical-design
canonical_spec: openspec
---

# Schema-First 表单管道设计

## 1. 架构概览

```
product_schema.json (JSON Schema Draft-07 + x-ui)
         │
    ┌────┴─────────────────────────────┐
    ▼                                  ▼
  后端 (Python/FastAPI)                前端 (React/TypeScript)
  ┌────────────────────┐              ┌─────────────────────────┐
  │ field_registry.py  │              │ Vite import schema       │
  │  ↓                 │              │  ↓                       │
  │ state.py           │              │ ajv instance             │
  │  ↓                 │              │  ↓                       │
  │ FormData (Pydantic)│              │ validation.ts            │
  │  ↓                 │              │  ↓                       │
  │ api/schemas.py     │              │ FormStep.tsx             │
  │ (4× Request 强类型) │              │  ├─ onChange → ajv      │
  │  ↓                 │              │  ├─ 实时错误显示         │
  │ FastAPI auto 422   │              │  ├─ [预览 JSON] 按钮     │
  │  ↓                 │              │  │   └→ JsonPreviewModal │
  │ conversation_      │              │  │      ├─ Monaco Editor │
  │   service.py       │              │  │      ├─ decorations   │
  │ document_service   │              │  │      └─ [关闭]       │
  │  ↓                 │              │  └─ [提交并开始 AI 对话]│
  │ prompt_validator   │              │      └→ onSubmit        │
  │  (启动时 warn)     │              │                          │
  │                    │              │ types/index.ts           │
  │ logger (loguru)    │              │  └─ FormData 接口        │
  │ · Schema 加载      │              │                          │
  │ · Pydantic 422     │              │ migration.ts             │
  │ · Prompt 字段 warn │              │  └─ localStorage 迁移    │
  └────────────────────┘              │                          │
                                      │ debugLogger              │
                                      │ · Schema 加载            │
                                      │ · ajv 校验               │
                                      │ · Modal 打开/关闭        │
                                      │ · 迁移执行               │
                                      │ · 422 捕获              │
                                      └─────────────────────────┘
```

## 2. Schema 设计

### 2.1 位置

`backend/core/product_schema.json` — 与现有 `questions_config.json` 同目录。前端通过 Vite `import` 直接消费，后端通过 `field_registry.py` 加载。

### 2.2 结构

标准 JSON Schema Draft-07，附加 `x-ui` 自定义属性：

```json
{
  "$schema": "https://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "product_name": {
      "type": "string",
      "minLength": 1,
      "x-ui": { "label": "产品名称", "widget": "text", "group": "base", "required": true }
    },
    "platform_type": {
      "type": "string",
      "enum": ["web", "mobile", "wechat_miniprogram", "desktop", "multi"],
      "x-ui": { "label": "目标平台", "widget": "select", "group": "base", "required": true }
    },
    "mvp_features": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 3,
      "x-ui": { "label": "MVP 核心功能", "widget": "list", "group": "base", "required": true }
    }
  },
  "required": ["product_name", "one_liner", "problem_statement", "target_users", "mvp_features", "platform_type", "needs_auth", "needs_database", "page_count"],
  "x-meta": { "schema_version": "1.0.0" }
}
```

- `type`, `enum`, `minLength`, `minItems` → ajv / Pydantic 共用约束
- `x-ui.widget` → 前端表单控件分派 (text/textarea/select/radio/list)
- `x-ui.group` → 前端分区渲染 (base/advanced)
- `x-meta.schema_version` → localStorage 版本迁移依据

### 2.3 降级策略

`field_registry.py` 加载逻辑：
1. 尝试读取 `product_schema.json` → 成功则用 Schema 驱动
2. 失败 (FileNotFoundError / JSONDecodeError) → 降级读 `questions_config.json` + WARNING 日志

## 3. 后端实现

### 3.1 FormData 模型 (state.py)

运行时从 JSON Schema 动态构建 Pydantic 模型：

```python
def _build_form_data_model():
    schema = get_schema()  # field_registry.get_schema()
    fields = {}
    for name, prop in schema["properties"].items():
        json_type = prop.get("type")
        if json_type == "array":
            fields[name] = (list[str], Field(..., min_length=prop.get("minItems", 1)))
        elif name in schema.get("required", []):
            fields[name] = (str, ...)
        else:
            fields[name] = (str, Field(default=""))
    return create_model("FormData", **fields)
```

### 3.2 API Schema 变更 (api/schemas.py)

```python
from core.state import FormData

class ChatRequest(BaseModel):
    session_id: str = ""
    form_data: FormData          # 曾: dict[str, Any]
    history: list[dict[str, str]] = []
# SummaryRequest, DocumentRequest, OptimizeRequest 同理
```

FastAPI 自动校验 → 非法请求返回 422，响应体含 `{ "detail": [{ "loc": [...], "msg": "..." }] }`。

### 3.3 服务适配 (conversation_service.py)

`_form_to_kwargs()` 从接收 `dict` 改为接收 `FormData` 对象。`chat_stream()` 和 `generate_summary()` 签名同步变更。

### 3.4 废弃手动校验 (session_service.py)

`_validate_form()` 标记为 deprecated。API 层 Pydantic 校验已覆盖其职责。

### 3.5 Prompt 字段校验 (prompt_validator.py)

启动时扫描模板：

```python
def validate_template_fields(template_text: str, schema_fields: set[str]) -> list[str]:
    referenced = set(re.findall(r'\{\{\s*(\w+)\s*\}\}', template_text))
    whitelist = {"form_fields", "chat_log", "requirements_summary", "current_content",
                 "prd_content", "api_content", "previous_content", "session_id",
                 "doc_type", "base_prompt", "review_result"}
    return list(referenced - schema_fields - whitelist)
```

`main.py` 启动时调用 `prompt_validator.validate_all()`，遍历 `backend/prompts/*.jinja2` 和 `backend/skills/*.md`。

### 3.6 后端 Debug 埋点

| 事件 | 级别 | 内容 |
|------|------|------|
| Schema 加载成功 | DEBUG | `schema_version`, `field_count` |
| Schema 加载失败 | WARNING | 错误原因，降级状态 |
| Pydantic 校验失败 (422) | WARNING | `event="validation_failed"`, 字段路径、值、约束 |

## 4. 前端实现

### 4.1 Schema 加载与 ajv 初始化 (validation.ts)

```typescript
import productSchema from '@/../backend/core/product_schema.json'; // Vite import
import Ajv from 'ajv';

const ajv = new Ajv({ allErrors: true });
const validate = ajv.compile(productSchema);

export function validateFormData(data: Record<string, unknown>): {
  valid: boolean;
  errors: { path: string; message: string }[];
} {
  const valid = validate(data);
  const errors = (validate.errors || []).map(e => ({
    path: e.instancePath || e.params.missingProperty || '',
    message: e.message || '校验失败',
  }));
  debugLogger.log('info', 'validation:ajv', { valid, errorCount: errors.length, firstError: errors[0] });
  return { valid, errors };
}
```

依赖：`ajv` (~120KB / ~30KB gzipped)。

### 4.2 FormStep 改造

**废弃**：手写 `validate()` 函数。

**新增**：
- `onChange` → `validateFormData(formData)` → 错误绑定到字段
- 提交按钮 `disabled={!valid}`
- 双按钮布局：[预览 JSON] [提交并开始 AI 对话]

### 4.3 JsonPreviewModal (新组件)

```tsx
interface Props {
  formData: FormData;
  schema: object;
  errors: { path: string; message: string }[];
  onClose: () => void;
}
```

**技术选型**：Monaco Editor (`@monaco-editor/react` + `monaco-editor`)，配置：
- `language="json"`, `readOnly`, `minimap: { enabled: false }`
- `lineNumbers: "on"`
- value = `JSON.stringify(formData, null, 2)`

**错误标注**：将 ajv errors 转换为 Monaco decorations：
```typescript
function errorsToDecorations(errors, model): IModelDeltaDecoration[] {
  return errors.map(e => {
    const lineNumber = locateLine(model, e.path); // 字段路径 → 行号
    return {
      range: new Range(lineNumber, 1, lineNumber, 1),
      options: {
        isWholeLine: true,
        className: 'validation-error-line',
        glyphMarginClassName: 'validation-error-glyph',
        hoverMessage: { value: e.message },
      },
    };
  });
}
```

依赖：`@monaco-editor/react` (~2MB bundled)。

### 4.4 TypeScript 类型 (types/index.ts)

```typescript
export interface FormData {
  _schema_version: string;
  product_name: string;
  one_liner: string;
  problem_statement: string;
  // ... 17 字段
  mvp_features: string[];
}
```

替换 `ProjectState.form_data`、`ChatRequest.form_data` 等 5 处 `Record<string, any>`。

### 4.5 localStorage 迁移 (migration.ts)

```typescript
export function migrateFormData(data: Record<string, any>): FormData {
  const version = data._schema_version || '0.0.0';
  if (version === '1.0.0') return data as FormData;
  // v0 → v1: 补全选填字段默认值
  const defaults = getSchemaDefaults(productSchema); // x-ui.required=false → ""
  const migrated = { ...defaults, ...data, _schema_version: '1.0.0' };
  debugLogger.log('info', 'migration:executed', { fromVersion: version, toVersion: '1.0.0' });
  return migrated;
}
```

`App.tsx` 加载 localStorage 时调用，外层 try-catch 兜底。

### 4.6 前端 Debug 埋点

| 事件 | 函数调用 |
|------|---------|
| Schema 加载 | `debugLogger.log('info', 'schema:loaded', { version, fieldCount })` |
| ajv 校验 | `debugLogger.log('info', 'validation:ajv', { valid, errorCount, firstError })` |
| Modal 打开/关闭 | `debugLogger.log('info', 'preview:modal', { action, fieldCount, errorCount })` |
| 迁移执行 | `debugLogger.log('info', 'migration:executed', { fromVersion, toVersion })` |
| 迁移降级 | `debugLogger.log('error', 'migration:fallback', { error })` |
| 422 捕获 | `debugLogger.log('warn', 'validation:422', { errors })` |

## 5. 数据流

```
用户输入 → FormStep.onChange
  → validateFormData(formData)
  → { valid, errors }
  → 实时渲染红色错误/清除
  → 提交按钮 disabled={!valid}

[预览 JSON] → JsonPreviewModal
  → Monaco Editor value={JSON.stringify(formData, null, 2)}
  → errorsToDecorations(errors) → 红色波浪线 + hover
  → [关闭]

[提交并开始 AI 对话] → validateFormData() 最终校验
  → 通过 → POST /api/chat/stream { form_data: FormData }
    → FastAPI Pydantic 校验
      → 通过 → SSE 流式 → viewState='ai_dialogue'
      → 失败 422 → debugLogger.log('warn') + 表单显示错误
  → 失败 → 表单内显示错误，按钮灰显
```

## 6. 依赖变更

| 依赖 | 平台 | 用途 | 体积 |
|------|------|------|------|
| `ajv` | 前端 | JSON Schema 校验 | ~30KB gzipped |
| `@monaco-editor/react` | 前端 | JSON 语法高亮预览 | ~2MB bundled |
| `monaco-editor` | 前端 | Monaco Editor 核心 | ~2MB (与上合计) |

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| BREAKING: `form_data: dict` → `FormData` | 前端先部署 ajv 校验，正常用户不触发 422；过渡期 `field_registry` 保留降级 |
| Schema 语法错误导致启动崩溃 | 降级到 `questions_config.json` + WARNING，不阻断启动 |
| ajv vs Pydantic 校验不一致 | 标准 JSON Schema 关键字双向一致；一致性测试 (7.6) 验证 |
| Monaco Editor 体积增大 | readOnly 模式轻量配置；后续可评估构建时 code splitting |
| localStorage 迁移失败 | try-catch 兜底，Schema 默认值重建空 formData |
| Prompt 字段拼写错误 | 启动时 warn 扫描 6 个模板文件，开发者修复后 warn 消失 |

## 8. 测试策略

| 层 | 工具 | 文件 | 优先级 |
|---|------|------|--------|
| 后端单元 | pytest | test_form_data_model.py | P0 |
| 后端单元 | pytest | test_field_registry.py | P0 |
| 后端单元 | pytest | test_prompt_validator.py | P0 |
| 前端单元 | vitest | validation.test.ts | P0 |
| 前端单元 | vitest | migration.test.ts | P0 |
| 一致性验证 | 手动 | ajv vs Pydantic 错误集合 | P0 |
| E2E | Playwright | 3 流程场景 | P1 |
