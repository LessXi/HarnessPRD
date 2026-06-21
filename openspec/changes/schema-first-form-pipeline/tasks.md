## 1. Schema 定义与后端适配（P0）

- [x] 1.1 创建 `product_schema.json`：将 `questions_config.json` 17 个字段转为 JSON Schema Draft-07 格式，添加 `x-ui` 元数据，定义 `x-meta.schema_version`
- [ ] 1.2 重构 `field_registry.py`：优先读取 `product_schema.json`，降级读 `questions_config.json`；新增 `get_schema()` 返回完整 Schema 对象；Schema 加载成功/失败时通过 logger.bind(event=...) 记录
- [ ] 1.3 重构 `state.py` `_build_form_data_model()`：从 `product_schema.json` 构建 `FormData` Pydantic 模型，支持 JSON Schema 约束（type/enum/minLength/minItems）
- [ ] 1.4 改造 `api/schemas.py` 4 个 Request 模型：`ChatRequest`、`SummaryRequest`、`DocumentRequest`、`OptimizeRequest` 的 `form_data` 字段从 `dict[str, Any]` → `FormData`；Pydantic 校验失败（422）时 logger.bind(event="validation_failed").warning() 记录详情
- [ ] 1.5 适配 `conversation_service.py`：`chat_stream()` 和 `generate_summary()` 的 `form_data` 参数类型适配 `FormData`；`_form_to_kwargs()` 改为接收强类型对象
- [ ] 1.6 标记 `session_service._validate_form()` 为 deprecated，验证 API 层 Pydantic 校验已覆盖其职责
- [ ] 1.7 后端单元测试 — `test_form_data_model.py`：验证 `FormData` 模型正确拒绝不合法 form_data（缺必填/枚举越界/数组不足），正确接受合法数据；验证 `_validate_form()` 已标记 deprecated 且不被调用
- [ ] 1.8 后端单元测试 — `test_field_registry.py`：验证 `get_schema()` 返回有效 dict；验证 Schema 不存在时降级读 `questions_config.json` + WARNING
- [ ] 1.9 后端单元测试 — `test_prompt_validator.py`：验证合法字段引用返回空列表；验证非法字段引用返回错误列表；验证白名单字段被跳过

## 2. 前端校验迁移（P0）

- [ ] 2.1 安装 ajv 依赖，配置全局 ajv 实例，加载 `product_schema.json`
- [ ] 2.2 创建 `src/utils/validation.ts`：封装 `validateFormData(data, schema)` 返回 `{ valid, errors }`，每个 error 含字段路径和消息；每次调用通过 `debugLogger.log()` 上报校验摘要（valid/errorCount/firstError）
- [ ] 2.3 重写 `FormStep.tsx` 校验逻辑：废除手写 `validate()`，改用 ajv 驱动，实时 onChange 校验，错误绑定到对应字段
- [ ] 2.4 `FormStep.tsx` 提交按钮 disabled 逻辑：存在 ajv 错误时按钮灰显
- [ ] 2.5 前端单元测试（P0）：验证校验函数对各类非法输入的拒绝行为（缺必填/枚举越界/数组不足/全合法）

## 3. JSON 预览 Modal（P0）

- [ ] 3.1 安装 `@monaco-editor/react` + `monaco-editor` 依赖；创建 `JsonPreviewModal` 组件：接收 `formData`、`schema`、`errors` props，以 Modal 弹出
- [ ] 3.2 JSON 语法高亮渲染：使用 `@monaco-editor/react` 加载 Monaco Editor（readOnly 模式），配置 JSON language、行号、minimap 关闭；通过 `editor.deltaDecorations()` 标注校验错误行（红色波浪线 + hover message）
- [ ] 3.3 校验错误映射：将 ajv `errors` 数组转换为 Monaco `IModelDeltaDecoration[]`（字段路径 → 行号定位 → 红色波浪线 className + hoverMessage）
- [ ] 3.4 `_schema_version` 显示：JSON 底部或 Modal footer 展示版本号
- [ ] 3.5 Modal 交互：仅「关闭」按钮和遮罩点击关闭，不包含提交功能（预览与提交解耦）；打开/关闭时通过 `debugLogger.log()` 上报事件（含 fieldCount、errorCount）
- [ ] 3.6 `FormStep.tsx` 集成：表单底部「预览 JSON」按钮（表单有数据时可见，点击打开 Modal）+ 独立「提交并开始 AI 对话」按钮
- [ ] 3.7 `FormStep.tsx` 提交流程：「提交并开始 AI 对话」按钮点击 → ajv 校验 → 通过则调 `onSubmit` → 失败则表单内显示错误
- [ ] 3.8 422 兜底处理：`api.ts` 流式调用中 catch 422，解析错误详情，set 入 error 状态传给 Modal

## 4. TypeScript 类型生成与状态类型化（P1）

- [ ] 4.1 定义 `FormData` TypeScript 接口：基于 `product_schema.json` 手动定义 17 个字段的强类型接口
- [ ] 4.2 替换 `types/index.ts` 中 `ProjectState.form_data`：`Record<string, any>` → `FormData`
- [ ] 4.3 替换 `types/index.ts` 中 `ChatRequest`、`SummaryRequest`、`DocumentRequest`、`OptimizeRequest` 的 `form_data` 类型
- [ ] 4.4 级联修复：所有引用 `form_data` 的组件和函数适配 `FormData` 类型（`App.tsx`、`api.ts`、`FormStep.tsx` 等）

## 5. localStorage 版本化迁移（P1）

- [ ] 5.1 `FormData` 接口中加 `_schema_version: string` 字段
- [ ] 5.2 创建 `src/utils/migration.ts`：`migrateFormData(data: Record<string, any>)` 函数，检测版本，补默认值；迁移执行和降级时通过 `debugLogger.log()` 上报
- [ ] 5.3 创建 `src/utils/__tests__/migration.test.ts`：验证无版本补默认、同版本不变、异常降级默认
- [ ] 5.4 `App.tsx` 或 `useProjectState` hook 中加载 localStorage 时调用 `migrateFormData`
- [ ] 5.5 迁移失败兜底：try-catch，失败时用 Schema 默认值重建空 formData

## 6. Prompt 模板字段校验（P1）

- [ ] 6.1 创建 `backend/core/prompt_validator.py`：加载 Schema 获取合法字段集合，扫描模板中 `{{ field_name }}` 引用
- [ ] 6.2 定义上下文变量白名单（`form_fields`、`chat_log`、`requirements_summary`、`current_content`、`prd_content`、`api_content`、`previous_content`、`session_id`、`doc_type`）
- [ ] 6.3 `main.py` 启动时调用 `prompt_validator.validate_all()`：遍历 `backend/prompts/*.jinja2` 和 `backend/skills/*.md`，对非法引用 emit WARNING
- [ ] 6.4 修复现有模板中可能存在的字段名拼写错误（如有）

## 7. 联调测试与清理（P0）

- [ ] 7.1 后端启动验证：`FormData` 正常加载，Prompt 校验 warn 为零
- [ ] 7.2 前端启动验证：ajv 加载 Schema 成功，表单渲染正常
- [ ] 7.3 E2E 正常流程（P1）：填写表单 → ajv 实时校验 → 预览 Modal（Monaco 渲染正确）→ 校验通过 → 提交 → 后端 200 → 进入对话
- [ ] 7.4 E2E 错误流程（P1）：缺必填字段 → 预览 Modal 红字 decoration → 提交按钮禁用；后端 422 场景模拟
- [ ] 7.5 E2E 旧数据兼容（P1）：注入无 `_schema_version` 的 localStorage 数据，刷新页面确认正常迁移
- [ ] 7.6 前后端校验一致性：同一份非法 form_data 分别经 ajv 和 Pydantic 校验，错误字段集合一致
- [ ] 7.7 更新 `docs/form-data-structure.md`：反映 Schema 变更，标注 `questions_config.json` deprecated
