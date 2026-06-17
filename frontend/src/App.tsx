import { useEffect, useState, useCallback } from "react";
import FormStep from "@/components/FormStep";
import MessageList from "@/components/MessageList";
import ChatInput from "@/components/ChatInput";
import {
  getQuestions, createSession,
  startConversationStream, continueConversationStream,
  sendMessage, getMessages,
} from "@/services/api";
import type { QuestionsConfig, ViewState, ChatMessage } from "@/types";
import { STEPS, STEP_INDEX_MAP } from "@/types";

const DRAFT_KEY = "harnessprd:form-draft";
const CHAT_KEY = "harnessprd:chat-messages";
const SESSION_KEY = "harnessprd:session";

interface SessionInfo {
  sessionId: string;
  viewState: ViewState;
}

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

function loadMessages(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(CHAT_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveMessages(messages: ChatMessage[]) {
  try {
    localStorage.setItem(CHAT_KEY, JSON.stringify(messages));
  } catch {
    // localStorage 不可用时静默失败
  }
}

function loadSession(): SessionInfo | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSession(info: SessionInfo) {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(info));
  } catch {
    // 静默失败
  }
}

function clearSession() {
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(CHAT_KEY);
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

// ===== 占位页（尚未实现的步骤） =====

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
  // 尝试恢复会话（刷新后保持对话页）
  const savedSession = loadSession();

  const [questions, setQuestions] = useState<QuestionsConfig | null>(null);
  const [formData, setFormData] = useState<Record<string, any>>(loadDraft);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [viewState, setViewState] = useState<ViewState>(
    savedSession?.viewState ?? "form_editing"
  );
  const [sessionId, setSessionId] = useState<string | null>(
    savedSession?.sessionId ?? null
  );
  const [error, setError] = useState<string | null>(null);

  // 对话状态
  const [messages, setMessages] = useState<ChatMessage[]>(loadMessages);
  const [streamingContent, setStreamingContent] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  useEffect(() => {
    getQuestions()
      .then((q) => setQuestions(q))
      .catch((e) =>
        setError(e?.response?.data?.detail || e.message || "加载表单配置失败")
      )
      .finally(() => setLoading(false));
  }, []);

  // 刷新后验证 session 是否仍有效
  useEffect(() => {
    if (!savedSession) return;
    getMessages(savedSession.sessionId)
      .then((msgs) => {
        setMessages(msgs);
        saveMessages(msgs);
      })
      .catch(() => {
        // session 已失效 → 回到表单页
        clearSession();
        setSessionId(null);
        setViewState("form_editing");
        setMessages([]);
      });
  }, []); // 仅在挂载时执行一次

  const handleChange = useCallback((name: string, value: any) => {
    setFormData((prev) => {
      const next = { ...prev, [name]: value };
      saveDraft(next);
      return next;
    });
  }, []);

  // ===== 提交表单 → 创建 Session → 启动 SSE 问候 =====

  const handleSubmit = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await createSession(formData);
      setSessionId(result.session_id);
      setViewState("ai_dialogue");
      saveSession({ sessionId: result.session_id, viewState: "ai_dialogue" });
      localStorage.removeItem(DRAFT_KEY);

      // 清空历史消息，启动 AI 问候
      setMessages([]);
      setStreamingContent("");
      setChatLoading(true);

      startConversationStream(result.session_id, {
        onChunk: (text) => setStreamingContent((prev) => prev + text),
        onDone: () => {
          setChatLoading(false);
          // 刷新完整消息列表
          getMessages(result.session_id).then((msgs) => {
            setMessages(msgs);
            saveMessages(msgs);
          }).catch((e: unknown) => console.warn("getMessages (start) failed", e));
          setStreamingContent("");
        },
        onError: (err) => {
          setChatLoading(false);
          setError(err);
          setStreamingContent("");
        },
      });
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || "提交失败");
    } finally {
      setSubmitting(false);
    }
  }, [formData]);

  // ===== 发送消息 → 保存 → 接续 SSE 对话 =====

  const handleSendMessage = useCallback(async (content: string) => {
    if (!sessionId || chatLoading) return;

    const userMsg: ChatMessage = {
      role: "user",
      content,
      timestamp: new Date().toISOString(),
    };

    // 本地追加并持久化
    const updated = [...messages, userMsg];
    setMessages(updated);
    saveMessages(updated);

    // 保存到后端
    try {
      await sendMessage(sessionId, content);
    } catch {
      setError("发送失败");
      return;
    }

    // 启动 SSE 接收 AI 回复
    setChatLoading(true);
    setStreamingContent("");

    continueConversationStream(sessionId, content, {
      onChunk: (text) => setStreamingContent((prev) => prev + text),
      onDone: () => {
        setChatLoading(false);
        getMessages(sessionId).then((msgs) => {
          setMessages(msgs);
          saveMessages(msgs);
        }).catch((e: unknown) => console.warn("getMessages (continue) failed", e));
        setStreamingContent("");
      },
      onError: (err) => {
        setChatLoading(false);
        setError(err);
        setStreamingContent("");
      },
    });
  }, [sessionId, chatLoading, messages]);

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
      content = (
        <div className="flex-1 flex flex-col h-full">
          <MessageList messages={messages} streamingText={streamingContent} />
          <ChatInput onSend={handleSendMessage} disabled={chatLoading} />
        </div>
      );
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
      <StepProgress current={viewState} />

      <div className="flex-1">{content}</div>

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
