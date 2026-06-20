import { useEffect, useState, useCallback, useRef } from "react";
import FormStep from "@/components/FormStep";
import MessageList from "@/components/MessageList";
import ChatInput from "@/components/ChatInput";
import DocumentReview from "@/components/DocumentReview";
import {
  getQuestions,
  chatStream,
  generateSummary,
  generateDocumentStream,
  optimizeDocumentStream,
} from "@/services/api";
import type {
  QuestionsConfig,
  ViewState,
  ChatMessage,
  ProjectState,
  DocumentState,
} from "@/types";
import { STEPS, STEP_INDEX_MAP, createEmptyProjectState, createEmptyDocumentState } from "@/types";

const PROJECT_KEY = "harnessprd:project";

// ========================================================================
// localStorage 持久化
// ========================================================================

function loadProject(): ProjectState {
  try {
    const raw = localStorage.getItem(PROJECT_KEY);
    if (!raw) return createEmptyProjectState();
    const parsed = JSON.parse(raw);
    // 兼容旧数据：确保所有字段存在
    return {
      ...createEmptyProjectState(),
      ...parsed,
      prd: { ...createEmptyDocumentState(), ...parsed.prd },
      api: { ...createEmptyDocumentState(), ...parsed.api },
      prompts: { ...createEmptyDocumentState(), ...parsed.prompts },
    };
  } catch {
    return createEmptyProjectState();
  }
}

function saveProject(state: ProjectState): void {
  try {
    localStorage.setItem(PROJECT_KEY, JSON.stringify(state));
  } catch {
    // localStorage 满或不可用
  }
}

// ========================================================================
// 步骤进度条
// ========================================================================

function StepProgress({ current }: { current: ViewState }) {
  const currentIdx = STEP_INDEX_MAP[current] ?? -1;
  return (
    <nav className="border-b border-gray-200 bg-white">
      <ol className="flex items-center max-w-3xl mx-auto px-4 py-3">
        {STEPS.map((step, idx) => {
          const stepState = idx === currentIdx ? "current" : idx < currentIdx ? "done" : "pending";
          return (
            <li key={step.id} className="flex items-center flex-1 last:flex-none">
              <span className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-medium shrink-0 ${
                stepState === "done" ? "bg-primary-500 text-white"
                : stepState === "current" ? "bg-primary-100 text-primary-700 ring-2 ring-primary-300"
                : "bg-gray-100 text-gray-400"
              }`}>
                {stepState === "done" ? (
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                ) : idx + 1}
              </span>
              <span className={`ml-2 text-xs ${
                stepState === "current" ? "text-primary-700 font-semibold"
                : stepState === "done" ? "text-gray-700" : "text-gray-400"
              }`}>{step.label}</span>
              {idx < STEPS.length - 1 && (
                <div className={`flex-1 h-px mx-3 ${idx < currentIdx ? "bg-primary-300" : "bg-gray-200"}`} />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

// ========================================================================
// 主组件
// ========================================================================

export default function App() {
  const [project, setProject] = useState<ProjectState>(loadProject);
  const [questions, setQuestions] = useState<QuestionsConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  // 用于在 streaming 中断时保留部分内容
  const streamingContentRef = useRef("");

  // 同步 ref
  useEffect(() => {
    streamingContentRef.current = streamingContent;
  }, [streamingContent]);

  // 加载表单配置
  useEffect(() => {
    getQuestions()
      .then(setQuestions)
      .catch((e) => setError(e?.response?.data?.detail || e.message || "加载表单配置失败"))
      .finally(() => setLoading(false));
  }, []);

  // 持久化 project 到 localStorage（每次变更时）
  const updateProject = useCallback((updater: (prev: ProjectState) => ProjectState) => {
    setProject((prev) => {
      const next = updater(prev);
      saveProject(next);
      return next;
    });
  }, []);

  // 切换 viewState 并持久化
  const switchView = useCallback((viewState: ViewState) => {
    updateProject((prev) => ({ ...prev, viewState }));
  }, [updateProject]);

  // ======================================================================
  // 表单提交
  // ======================================================================

  const handleSubmit = useCallback(async () => {
    setSubmitting(true);
    setError(null);

    const sessionId = crypto.randomUUID();

    updateProject((prev) => ({
      ...prev,
      session_id: sessionId,
      viewState: "ai_dialogue",
      messages: [],
    }));

    setChatLoading(true);
    setStreamingContent("");

    await chatStream(
      {
        session_id: sessionId,
        form_data: project.form_data,
        history: [],
      },
      {
        onChunk: (text) => setStreamingContent((prev) => prev + text),
        onDone: (data) => {
          setChatLoading(false);
          const assistantContent = data?.assistant_content ?? streamingContentRef.current;
          if (assistantContent) {
            const aiMsg: ChatMessage = {
              role: "assistant",
              content: assistantContent,
              timestamp: new Date().toISOString(),
            };
            updateProject((prev) => ({
              ...prev,
              messages: [...prev.messages, aiMsg],
            }));
          }
          setStreamingContent("");
        },
        onError: (err) => {
          setChatLoading(false);
          setError(err);
          setStreamingContent("");
        },
      },
    );

    setSubmitting(false);
  }, [project.form_data, updateProject]);

  // ======================================================================
  // 对话消息发送
  // ======================================================================

  const handleSendMessage = useCallback(async (content: string) => {
    if (chatLoading) return;

    const userMsg: ChatMessage = {
      role: "user",
      content,
      timestamp: new Date().toISOString(),
    };
    const updatedMessages = [...project.messages, userMsg];
    updateProject((prev) => ({ ...prev, messages: updatedMessages }));

    setChatLoading(true);
    setStreamingContent("");

    await chatStream(
      {
        session_id: project.session_id,
        form_data: project.form_data,
        history: updatedMessages,
      },
      {
        onChunk: (text) => setStreamingContent((prev) => prev + text),
        onDone: (data) => {
          setChatLoading(false);
          const assistantContent = data?.assistant_content ?? streamingContentRef.current;
          if (assistantContent) {
            const aiMsg: ChatMessage = {
              role: "assistant",
              content: assistantContent,
              timestamp: new Date().toISOString(),
            };
            updateProject((prev) => ({
              ...prev,
              messages: [...prev.messages, aiMsg],
            }));
          }
          setStreamingContent("");
        },
        onError: (err) => {
          setChatLoading(false);
          setError(err);
          setStreamingContent("");
        },
      },
    );
  }, [project.session_id, project.form_data, project.messages, chatLoading, updateProject]);

  // ======================================================================
  // 需求摘要生成
  // ======================================================================

  const handleGenerateSummary = useCallback(async () => {
    setChatLoading(true);
    setError(null);
    try {
      const result = await generateSummary({
        session_id: project.session_id,
        form_data: project.form_data,
        history: project.messages,
      });
      updateProject((prev) => ({
        ...prev,
        requirements_summary: result.summary,
      }));
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || "摘要生成失败");
    } finally {
      setChatLoading(false);
    }
  }, [project.session_id, project.form_data, project.messages, updateProject]);

  // ======================================================================
  // 文档生成（PRD / API / Prompts）
  // ======================================================================

  const handleGenerateDoc = useCallback((
    docType: "prd" | "api" | "prompts",
    previousContent?: string,
  ) => {
    const viewStateMap = {
      prd: "generating_prd" as ViewState,
      api: "generating_api" as ViewState,
      prompts: "generating_prompts" as ViewState,
    };

    switchView(viewStateMap[docType]);
    setStreamingContent("");
    setError(null);

    const req = {
      session_id: project.session_id,
      form_data: project.form_data,
      requirements_summary: project.requirements_summary,
      previous_content: previousContent || "",
      prd_content: docType === "api" || docType === "prompts" ? (project.prd.user_edits || project.prd.content) : "",
      api_content: docType === "prompts" ? (project.api.user_edits || project.api.content) : "",
    };

    generateDocumentStream(docType, req, {
      onChunk: (text) => setStreamingContent((prev) => prev + text),
      onDone: () => {
        setStreamingContent((prev) => {
          const fullContent = previousContent ? previousContent + prev : prev;
          const docState: DocumentState = {
            content: fullContent,
            user_edits: "",
            confirmed: false,
          };
          updateProject((p) => ({
            ...p,
            [docType]: docState,
            viewState: `reviewing_${docType}` as ViewState,
          }));
          return "";
        });
      },
      onError: (err) => {
        // 保存已接收的部分内容
        setStreamingContent((prev) => {
          if (prev) {
            const fullContent = previousContent ? previousContent + prev : prev;
            updateProject((p) => ({
              ...p,
              [docType]: {
                ...p[docType],
                content: fullContent,
              },
            }));
          }
          return "";
        });
        setError(`文档生成中断：${err}。可以点击"继续生成"从断点续写。`);
        switchView(`reviewing_${docType}`);
      },
    });
  }, [project, switchView, updateProject]);

  // ======================================================================
  // 文档优化
  // ======================================================================

  const handleOptimizeDoc = useCallback((docType: "prd" | "api" | "prompts") => {
    const doc = project[docType];
    const contentToOptimize = doc.user_edits || doc.content;

    setStreamingContent("");
    setError(null);

    optimizeDocumentStream(docType, {
      session_id: project.session_id,
      content: contentToOptimize,
      form_data: project.form_data,
      requirements_summary: project.requirements_summary,
      prd_content: docType === "api" || docType === "prompts" ? (project.prd.user_edits || project.prd.content) : "",
      api_content: docType === "prompts" ? (project.api.user_edits || project.api.content) : "",
    }, {
      onChunk: (text) => setStreamingContent((prev) => prev + text),
      onDone: () => {
        setStreamingContent((prev) => {
          if (prev) {
            updateProject((p) => ({
              ...p,
              [docType]: {
                ...p[docType],
                content: prev,
                user_edits: "",
              },
            }));
          }
          return "";
        });
      },
      onError: (err) => {
        setStreamingContent((prev) => {
          if (prev) {
            updateProject((p) => ({
              ...p,
              [docType]: {
                ...p[docType],
                content: prev,
                user_edits: "",
              },
            }));
          }
          return "";
        });
        setError(`文档优化中断：${err}`);
      },
    });
  }, [project, updateProject]);

  // ======================================================================
  // 文档编辑保存
  // ======================================================================

  const handleDocEdit = useCallback((docType: "prd" | "api" | "prompts", editedContent: string) => {
    updateProject((prev) => ({
      ...prev,
      [docType]: {
        ...prev[docType],
        user_edits: editedContent,
      },
    }));
  }, [updateProject]);

  // ======================================================================
  // 文档续写
  // ======================================================================

  const handleResumeDoc = useCallback((docType: "prd" | "api" | "prompts") => {
    const doc = project[docType];
    const currentContent = doc.user_edits || doc.content;
    handleGenerateDoc(docType, currentContent);
  }, [project, handleGenerateDoc]);

  // ======================================================================
  // 确认文档 → 进入下一阶段
  // ======================================================================

  const handleConfirmDoc = useCallback((docType: "prd" | "api" | "prompts") => {
    const nextStateMap: Record<string, ViewState> = {
      prd: "generating_api",
      api: "generating_prompts",
      prompts: "completed",
    };
    const nextDocTypeMap: Record<string, "prd" | "api" | "prompts" | null> = {
      prd: "api",
      api: "prompts",
      prompts: null,
    };
    updateProject((prev) => ({
      ...prev,
      [docType]: { ...prev[docType], confirmed: true },
      viewState: nextStateMap[docType],
    }));
    // 触发下一个文档的生成
    const nextDocType = nextDocTypeMap[docType];
    if (nextDocType) {
      // 使用 setTimeout 确保状态更新后再触发生成
      setTimeout(() => handleGenerateDoc(nextDocType), 200);
    }
  }, [updateProject, handleGenerateDoc]);

  // ======================================================================
  // 重置项目
  // ======================================================================

  const handleReset = useCallback(() => {
    localStorage.removeItem(PROJECT_KEY);
    setProject(createEmptyProjectState());
    setStreamingContent("");
    setError(null);
  }, []);

  // ======================================================================
  // Render
  // ======================================================================

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

  if (error && !questions) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-2">加载失败</p>
          <p className="text-sm text-gray-400">{error}</p>
          <button onClick={() => window.location.reload()} className="mt-4 text-sm text-primary-600 hover:underline">重试</button>
        </div>
      </div>
    );
  }

  if (!questions) return null;

  const { viewState, sessionId } = { viewState: project.viewState, sessionId: project.session_id };

  const handleFormChange = (name: string, value: any) => {
    updateProject((prev) => ({
      ...prev,
      form_data: { ...prev.form_data, [name]: value },
    }));
  };

  let content: JSX.Element;
  switch (viewState) {
    case "form_editing":
      content = (
        <FormStep
          questions={questions}
          formData={project.form_data}
          onChange={handleFormChange}
          onSubmit={handleSubmit}
        />
      );
      break;

    case "ai_dialogue":
      content = (
        <div className="flex-1 flex flex-col h-full">
          <div className="flex items-center justify-end px-4 py-2 border-b border-gray-100 bg-white shrink-0 gap-2">
            {project.messages.length > 0 && !chatLoading && (
              <>
                <button
                  onClick={handleGenerateSummary}
                  disabled={chatLoading}
                  className="text-xs px-3 py-1.5 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 font-medium transition-colors"
                >
                  生成摘要
                </button>
                <button
                  onClick={() => handleGenerateDoc("prd")}
                  className="text-xs px-3 py-1.5 rounded-lg bg-primary-500 text-white hover:bg-primary-600 font-medium transition-colors"
                >
                  生成 PRD
                </button>
              </>
            )}
          </div>
          <MessageList messages={project.messages} streamingText={streamingContent} />
          <ChatInput onSend={handleSendMessage} disabled={chatLoading} />
        </div>
      );
      break;

    case "generating_prd":
      content = <DocumentReview title="PRD" docType="prd" content={project.prd.content} streamingText={streamingContent || undefined} />;
      break;

    case "reviewing_prd":
      content = (
        <DocumentReview
          title="PRD"
          docType="prd"
          content={project.prd.user_edits || project.prd.content}
          streamingText={streamingContent || undefined}
          onOptimize={() => handleOptimizeDoc("prd")}
          onResume={() => handleResumeDoc("prd")}
          onEdit={(text) => handleDocEdit("prd", text)}
          onConfirm={() => handleConfirmDoc("prd")}
        />
      );
      break;

    case "generating_api":
      content = <DocumentReview title="接口文档" docType="api" content={project.api.content} streamingText={streamingContent || undefined} />;
      break;

    case "reviewing_api":
      content = (
        <DocumentReview
          title="接口文档"
          docType="api"
          content={project.api.user_edits || project.api.content}
          streamingText={streamingContent || undefined}
          onOptimize={() => handleOptimizeDoc("api")}
          onResume={() => handleResumeDoc("api")}
          onEdit={(text) => handleDocEdit("api", text)}
          onConfirm={() => handleConfirmDoc("api")}
        />
      );
      break;

    case "generating_prompts":
      content = <DocumentReview title="提示词套件" docType="prompts" content={project.prompts.content} streamingText={streamingContent || undefined} confirmLabel="完成" />;
      break;

    case "reviewing_prompts":
      content = (
        <DocumentReview
          title="提示词套件"
          docType="prompts"
          content={project.prompts.user_edits || project.prompts.content}
          streamingText={streamingContent || undefined}
          onOptimize={() => handleOptimizeDoc("prompts")}
          onResume={() => handleResumeDoc("prompts")}
          onEdit={(text) => handleDocEdit("prompts", text)}
          onConfirm={() => handleConfirmDoc("prompts")}
          confirmLabel="完成"
        />
      );
      break;

    case "completed":
      content = (
        <div className="flex-1 flex flex-col max-w-4xl mx-auto w-full">
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center space-y-3">
              <p className="text-3xl">🎉</p>
              <p className="text-lg font-medium text-gray-700">全部完成！</p>
              <p className="text-sm text-gray-400">PRD、接口文档、提示词套件已生成</p>
              <button onClick={handleReset} className="mt-2 text-sm text-primary-600 hover:underline">开始新项目</button>
            </div>
          </div>
        </div>
      );
      break;

    default:
      content = (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-gray-500">未知状态</p>
        </div>
      );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <StepProgress current={viewState} />
      <div className="flex-1">{content}</div>
      {error && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg shadow max-w-md">
          {error}
          <button onClick={() => setError(null)} className="ml-3 text-red-400 hover:text-red-600">✕</button>
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
