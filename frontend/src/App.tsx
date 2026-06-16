import { useEffect, useState, useCallback } from "react";
import FormStep from "@/components/FormStep";
import { getQuestions, createSession } from "@/services/api";
import type { QuestionsConfig } from "@/types";

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

export default function App() {
  const [questions, setQuestions] = useState<QuestionsConfig | null>(null);
  const [formData, setFormData] = useState<Record<string, any>>(loadDraft);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getQuestions()
      .then((q) => setQuestions(q))
      .catch((e) => setError(e?.response?.data?.detail || e.message || "加载表单配置失败"))
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
          <svg
            className="animate-spin h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12" cy="12" r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
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

  // ===== 提交成功 =====
  if (sessionId) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="text-4xl">🎉</div>
          <h2 className="text-xl font-bold text-gray-900">表单提交成功！</h2>
          <p className="text-sm text-gray-500">
            会话 ID：<code className="bg-gray-100 px-2 py-0.5 rounded text-xs">{sessionId}</code>
          </p>
          <p className="text-sm text-gray-400">即将进入 AI 对话澄清阶段（功能开发中）</p>
        </div>
      </div>
    );
  }

  // ===== 表单 =====
  if (!questions) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      <FormStep
        questions={questions}
        formData={formData}
        onChange={handleChange}
        onSubmit={handleSubmit}
      />

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
            <svg
              className="animate-spin h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12" cy="12" r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            正在提交...
          </div>
        </div>
      )}
    </div>
  );
}
