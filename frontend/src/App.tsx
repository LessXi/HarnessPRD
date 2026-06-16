import { useEffect, useState, useCallback } from "react";
import FormStep from "@/components/FormStep";
import { getQuestions, createSession } from "@/services/api";
import type { QuestionsConfig, ViewState } from "@/types";
import { STEPS, STEP_INDEX_MAP } from "@/types";

const DRAFT_KEY = "harnessprd:form-draft";

function loadDraft(): Record<string, any> {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveDraft(formData: Record<string, any>) {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(formData));
  } catch {
    // localStorage 不可用时静默失败
  }
}

// ===== 步骤进度条 =====

function StepProgress({ current }: { current: ViewState }) {
  const currentIdx = STEP_INDEX_MAP[current] ?? -1;

  return (
    <nav className="border-b border-gray-200 bg-white">
      <ol className="flex items-center max-w-3xl mx-auto px-4 py-3">
        {STEPS.map((step, idx) => {
          const stepState =
            idx === currentIdx
              ? "current"
              : idx < currentIdx
              ? "done"
              : "pending";

          return (
            <li key={step.id} className="flex items-center flex-1 last:flex-none">
              {/* 圆圈/对勾 */}
              <span
                className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-medium shrink-0 ${
                  stepState === "done"
                    ? "bg-primary-500 text-white"
                    : stepState === "current"
                    ? "bg-primary-100 text-primary-700 ring-2 ring-primary-300"
                    : "bg-gray-100 text-gray-400"
                }`}
              >
                {stepState === "done" ? (
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  idx + 1
                )}
              </span>

              {/* 标签 */}
              <span
                className={`ml-2 text-xs ${
                  stepState === "current"
                    ? "text-primary-700 font-semibold"
                    : stepState === "done"
                    ? "text-gray-700"
                    : "text-gray-400"
                }`}
              >
                {step.label}
              </span>

              {/* 连接线 */}
              {idx < STEPS.length - 1 && (
                <div
                  className={`flex-1 h-px mx-3 ${
                    idx < currentIdx ? "bg-primary-300" : "bg-gray-200"
                  }`}
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

// ===== 占位页 =====

function PlaceholderPage({ title, sessionId }: { title: string; sessionId?: string | null }) {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center space-y-2">
        <p className="text-lg font-medium text-gray-700">{title}</p>
        <p className="text-sm text-gray-400">功能开发中…</p>
        {sessionId && (
          <p className="text-xs text-gray-400 mt-1">
            会话 ID：<code className="bg-gray-100 px-1.5 py-0.5 rounded">{sessionId}</code>
          </p>
        )}
      </div>
    </div>
  );
}

// ===== 主组件 =====

export default function App() {
  const [questions, setQuestions] = useState<QuestionsConfig | null>(null);
  const [formData, setFormData] = useState<Record<string, any>>(loadDraft);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [viewState, setViewState] = useState<ViewState>("form_editing");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getQuestions()
      .then((q) => setQuestions(q))
      .catch((e) =>
        setError(e?.response?.data?.detail || e.message || "加载表单配置失败")
      )
      .finally(() => setLoading(false));
  }, []);

  const handleChange = useCallback((name: string, value: any) => {
    setFormData((prev) => {
      const next = { ...prev, [name]: value };
      saveDraft(next);
      return next;
    });
  }, []);

  const handleSubmit = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await createSession(formData);
      setSessionId(result.session_id);
      setViewState("ai_dialogue");
      localStorage.removeItem(DRAFT_KEY);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || "提交失败");
    } finally {
      setSubmitting(false);
    }
  }, [formData]);

  // ===== 加载中 =====
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex items-center gap-2 text-gray-500">
          <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          加载中...
        </div>
      </div>
    );
  }

  // ===== 加载失败 =====
  if (error && !questions) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-2">加载失败</p>
          <p className="text-sm text-gray-400">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 text-sm text-primary-600 hover:underline"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  if (!questions) return null;

  // ===== 根据 viewState 渲染内容 =====
  let content: JSX.Element;

  switch (viewState) {
    case "form_editing":
      content = (
        <FormStep
          questions={questions}
          formData={formData}
          onChange={handleChange}
          onSubmit={handleSubmit}
        />
      );
      break;

    case "ai_dialogue":
      content = <PlaceholderPage title="AI 对话澄清" sessionId={sessionId} />;
      break;

    case "generating_prd":
      content = <PlaceholderPage title="正在生成 PRD…" />;
      break;

    case "reviewing_prd":
      content = <PlaceholderPage title="PRD 审阅" />;
      break;

    case "generating_api":
      content = <PlaceholderPage title="正在生成接口文档…" />;
      break;

    case "reviewing_api":
      content = <PlaceholderPage title="接口文档审阅" />;
      break;

    case "generating_prompts":
      content = <PlaceholderPage title="正在生成提示词套件…" />;
      break;

    case "reviewing_prompts":
      content = <PlaceholderPage title="提示词套件审阅" />;
      break;

    case "completed":
      content = <PlaceholderPage title="全部完成 🎉" />;
      break;

    default:
      content = <PlaceholderPage title="未知状态" />;
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* 步骤进度条 */}
      <StepProgress current={viewState} />

      {/* 主体内容 */}
      <div className="flex-1">{content}</div>

      {/* 全局错误提示 */}
      {error && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg shadow">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-3 text-red-400 hover:text-red-600"
          >
            ✕
          </button>
        </div>
      )}

      {/* 提交中遮罩 */}
      {submitting && (
        <div className="fixed inset-0 bg-white/60 flex items-center justify-center z-50">
          <div className="flex items-center gap-2 text-primary-600 font-medium">
            <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            正在提交...
          </div>
        </div>
      )}
    </div>
  );
}
