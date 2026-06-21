# 表单提交数据结构

> 版本 2.0 · 更新时间：2026-06-22

> **⚠️ `questions_config.json` 已降级为 fallback。** 真相源为 `backend/core/product_schema.json`（JSON Schema Draft-07）。后端通过 Pydantic `create_model()` 动态构建 `FormData` 模型，前端通过 ajv 编译 Schema 校验。手写 `validate()` 已废弃。

---

## 一、完整示例

```json
{
  "product_name": "HarnessPRD",
  "one_liner": "一个帮助产品经理自动生成PRD和接口文档的对话式工具",
  "problem_statement": "产品经理写文档花费大量时间，特别是PRD、接口文档和提示词套件，重复劳动多、质量不稳定",
  "target_users": "面向1-3年经验的产品经理，尤其是需要同时负责产品设计和AI提示词工程的人群",
  "mvp_features": [
    "用户填写产品信息表单",
    "AI扮演产品经理追问需求细节",
    "自动生成结构化PRD文档",
    "基于PRD生成接口文档",
    "基于PRD和接口文档生成提示词套件"
  ],
  "platform_type": "web",
  "needs_auth": "no",
  "needs_database": "no",
  "page_count": "4-10",
  "visual_style": "minimal",
  "competitors": "Notion AI、ChatPRD、文心一言",
  "tech_stack_preference": "想用Python后端 + React前端",
  "feature_priority": "ai_suggest",
  "doc_depth": "standard",
  "ai_temperature": "balanced",
  "timeline_expectation": "3-6_months",
  "additional_context": "单人开发，兼职，预算有限"
}
```

---

## 二、字段对照表

| 字段 | 类型 | 所属分组 | 必填 | 枚举值 |
|------|------|---------|------|--------|
| `product_name` | `string` | base | ✅ | — |
| `one_liner` | `string` | base | ✅ | — |
| `problem_statement` | `string` | base | ✅ | — |
| `target_users` | `string` | base | ✅ | — |
| `mvp_features` | `string[]` | base | ✅ | — |
| `platform_type` | `string` | base | ✅ | `web` / `mobile` / `wechat_miniprogram` / `desktop` / `multi` |
| `needs_auth` | `string` | base | ✅ | `yes` / `no` / `unsure` |
| `needs_database` | `string` | base | ✅ | `yes` / `no` / `unsure` |
| `page_count` | `string` | base | ✅ | `1-3` / `4-10` / `10+` / `unsure` |
| `visual_style` | `string` | base | ❌ | `minimal` / `creative` / `enterprise` / `unsure` |
| `competitors` | `string` | base | ❌ | — |
| `tech_stack_preference` | `string` | advanced | ❌ | — |
| `feature_priority` | `string` | advanced | ❌ | `user_defined` / `ai_suggest` / `iterate` |
| `doc_depth` | `string` | advanced | ❌ | `brief` / `standard` / `detailed` |
| `ai_temperature` | `string` | advanced | ❌ | `conservative` / `balanced` / `creative` |
| `timeline_expectation` | `string` | advanced | ❌ | `1-2_months` / `3-6_months` / `6+_months` / `unsure` |
| `additional_context` | `string` | advanced | ❌ | — |

---

## 三、类型规则

### string（单文本 / textarea / select / radio）

```json
"product_name": "HarnessPRD"
"platform_type": "web"
```

- 用户没填的选填字段 → 空字符串 `""`
- 后端接收后用 `if not value` 统一判空

### string[]（list / 动态功能列表）

```json
"mvp_features": [
  "用户填写产品信息表单",
  "AI扮演产品经理追问需求细节"
]
```

- 前端提交时已是 `string[]`，后端无需再解析
- 后端校验长度：`len(mvp_features) >= 3`

---

## 四、设计决策

### 1. 价值存储，不存标签

```json
// ✅ 存这个
"platform_type": "web"

// ❌ 不存这个
"platform_type": { "value": "web", "label": "Web 应用" }
```

前端提交时只发 `value`，后端校验时从 `questions_config.json` 读允许值列表。

### 2. 选填字段默认空字符串

```json
"competitors": ""
```

所有 `required: false` 的字段，用户没填时走空字符串，后端用 `not value` 判断。

### 3. `mvp_features` 专用数组类型

表单中有且只有 `mvp_features` 是数组，前端增删直接用数组操作，后端直接 `len()` 校验。

---

## 五、后端 Pydantic 模型（参考）

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class FormData(BaseModel):
    # base questions
    product_name: str = Field(..., min_length=1)
    one_liner: str = Field(..., min_length=1)
    problem_statement: str = Field(..., min_length=1)
    target_users: str = Field(..., min_length=1)
    mvp_features: list[str] = Field(..., min_length=3)

    platform_type: str = Field(...)
    needs_auth: str = Field(...)
    needs_database: str = Field(...)
    page_count: str = Field(...)

    # optional base
    visual_style: str = ""
    competitors: str = ""

    # advanced questions
    tech_stack_preference: str = ""
    feature_priority: str = ""
    doc_depth: str = ""
    ai_temperature: str = ""
    timeline_expectation: str = ""
    additional_context: str = ""

    @field_validator("mvp_features")
    @classmethod
    def check_mvp_count(cls, v: list[str]) -> list[str]:
        if len(v) < 3:
            raise ValueError("至少需要 3 个 MVP 功能")
        return v
```
