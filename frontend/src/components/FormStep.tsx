import { useState, useMemo, type FormEvent } from "react";
import type { QuestionsConfig } from "@/types";
import { validateFormData } from "@/utils/validation";
import JsonPreviewModal from "@/components/JsonPreviewModal";

interface Props {
  questions: QuestionsConfig;
  formData: Record<string, any>;
  onChange: (name: string, value: any) => void;
  onSubmit: () => void;
}

export default function FormStep({ questions, formData, onChange, onSubmit }: Props) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  // ajv 实时校验
  const validation = useMemo(() => validateFormData(formData), [formData]);
  const { valid, errors: ajvErrors } = validation;

  // 将 ajv errors 映射到字段 → 错误消息
  const fieldErrors: Record<string, string> = {};
  for (const e of ajvErrors) {
    const fieldName = e.path.replace(/^\//, "") || e.path;
    if (fieldName && !fieldErrors[fieldName]) {
      fieldErrors[fieldName] = e.message;
    }
  }
  // 合并服务端 422 错误
  const displayErrors = { ...fieldErrors, ...serverErrors };

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (valid) {
      onSubmit();
    }
  }

  function addListItem(name: string) {
    const current = Array.isArray(formData[name]) ? formData[name] : ["", "", ""];
    onChange(name, [...current, ""]);
  }

  function updateListItem(name: string, index: number, value: string) {
    const current = [...(formData[name] || ["", "", ""])];
    current[index] = value;
    onChange(name, current);
  }

  function removeListItem(name: string, index: number) {
    const current = [...(formData[name] || ["", "", ""])];
    current.splice(index, 1);
    onChange(name, current);
  }

  function renderField(q: QuestionsConfig["base_questions"][number]) {
    const val = formData[q.id] ?? "";
    const error = displayErrors[q.id];

    const baseInputClass =
      "w-full rounded-lg border bg-white px-3 py-2 text-sm outline-none transition-colors " +
      (error
        ? "border-red-400 focus:border-red-500 focus:ring-1 focus:ring-red-200"
        : "border-gray-300 focus:border-primary-500 focus:ring-1 focus:ring-primary-200");

    let input: JSX.Element;

    switch (q.type) {
      case "text":
        input = (
          <input
            type="text"
            className={baseInputClass}
            value={val as string}
            onChange={(e) => onChange(q.id, e.target.value)}
            placeholder={`请输入${q.label}`}
          />
        );
        break;

      case "textarea":
        input = (
          <textarea
            className={baseInputClass + " min-h-[80px] resize-y"}
            value={val as string}
            onChange={(e) => onChange(q.id, e.target.value)}
            placeholder={`请输入${q.label}`}
            rows={3}
          />
        );
        break;

      case "select":
        input = (
          <select
            className={baseInputClass}
            value={val as string}
            onChange={(e) => onChange(q.id, e.target.value)}
          >
            <option value="">-- 请选择 --</option>
            {q.options?.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        );
        break;

      case "radio":
        input = (
          <div className="flex flex-wrap gap-3">
            {q.options?.map((opt) => (
              <label
                key={opt.value}
                className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm cursor-pointer transition-colors ${
                  val === opt.value
                    ? "border-primary-500 bg-primary-50 text-primary-700"
                    : "border-gray-300 bg-white hover:bg-gray-50"
                }`}
              >
                <input
                  type="radio"
                  name={q.id}
                  value={opt.value}
                  checked={val === opt.value}
                  onChange={(e) => onChange(q.id, e.target.value)}
                  className="sr-only"
                />
                {opt.label}
              </label>
            ))}
          </div>
        );
        break;

      case "list":
        {
          const items: string[] = Array.isArray(formData[q.id])
            ? formData[q.id]
            : ["", "", ""];
          input = (
            <div className="space-y-2">
              {items.map((item: string, idx: number) => (
                <div key={`${q.id}-${idx}`} className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 w-5 text-right">
                    {idx + 1}.
                  </span>
                  <input
                    type="text"
                    className={baseInputClass + " flex-1"}
                    value={item}
                    onChange={(e) => updateListItem(q.id, idx, e.target.value)}
                    placeholder={`功能 ${idx + 1}`}
                  />
                  {items.length > 3 && (
                    <button
                      type="button"
                      onClick={() => removeListItem(q.id, idx)}
                      className="shrink-0 text-gray-400 hover:text-red-500 transition-colors p-1"
                      aria-label="删除"
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={() => addListItem(q.id)}
                className="text-sm text-primary-600 hover:text-primary-700 font-medium"
              >
                + 添加功能
              </button>
            </div>
          );
        }
        break;

      default:
        input = <div className="text-sm text-gray-400">不支持的字段类型</div>;
    }

    return (
      <div key={q.id} className="space-y-1.5">
        {/* 标签 */}
        <label className="text-sm font-medium text-gray-700">
          {q.label}
          {q.required && <span className="text-red-500 ml-0.5">*</span>}
        </label>

        {/* 输入控件 */}
        {input}

        {/* 描述 */}
        {q.description && (
          <p className="text-xs text-gray-400">{q.description}</p>
        )}

        {/* 错误 */}
        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>
    );
  }

  const hasData = Object.values(formData).some(
    (v) => v !== "" && v !== undefined && !(Array.isArray(v) && v.length === 0)
  );

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl mx-auto py-8 px-4 space-y-8">
      {/* 步骤标题 */}
      <div>
        <h2 className="text-xl font-bold text-gray-900">步骤一：填写产品信息</h2>
        <p className="mt-1 text-sm text-gray-500">
          以下信息将帮助 AI 更准确地理解你的产品需求
        </p>
      </div>

      {/* 基础问题 */}
      <div className="space-y-5">
        {questions.base_questions.map(renderField)}
      </div>

      {/* 高级问题折叠区 */}
      <div className="border border-gray-200 rounded-xl overflow-hidden">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
        >
          <span className="text-sm font-medium text-gray-700">
            高级配置
            <span className="ml-1.5 text-xs text-gray-400 font-normal">（可选）</span>
          </span>
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${showAdvanced ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {showAdvanced && (
          <div className="px-4 py-5 space-y-5 bg-white">
            {questions.advanced_questions.map(renderField)}
          </div>
        )}
      </div>

      {/* 双按钮布局 */}
      <div className="space-y-3">
        {/* 预览 JSON 按钮 */}
        {hasData && (
          <button
            type="button"
            onClick={() => setShowPreview(true)}
            className="w-full rounded-xl border border-gray-300 bg-white hover:bg-gray-50 text-gray-700 font-medium py-3 px-6 transition-colors"
          >
            预览 JSON
          </button>
        )}

        {/* 提交按钮 */}
        <button
          type="submit"
          disabled={!valid}
          className={`w-full rounded-xl font-semibold py-3 px-6 transition-colors shadow-sm ${
            valid
              ? "bg-primary-500 hover:bg-primary-600 text-white"
              : "bg-gray-300 text-gray-500 cursor-not-allowed"
          }`}
        >
          提交并开始 AI 对话
        </button>
      </div>

      {/* JSON 预览 Modal */}
      {showPreview && (
        <JsonPreviewModal
          formData={formData}
          errors={ajvErrors}
          onClose={() => setShowPreview(false)}
        />
      )}
    </form>
  );
}
