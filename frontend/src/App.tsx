import { useEffect, useState, useCallback, useRef } from "react";
import JSZip from "jszip";
import FormStep from "@/components/FormStep";
import MessageList from "@/components/MessageList";
import ChatInput from "@/components/ChatInput";
import DocumentReview from "@/components/DocumentReview";
import CompletionPromptBar from "@/components/CompletionPromptBar";
import CompletionSummary from "@/components/CompletionSummary";
import PreviewModal from "@/components/PreviewModal";
import Sidebar, { PrimaryAction, SecondaryAction } from "@/components/Sidebar";
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
import { STEPS, STEP_INDEX_MAP, createEmptyProjectState, createEmptyDocumentState, isValidStateTransition } from "@/types";
import { debugLogger } from "@/utils/debugLogger";

const PROJECT_KEY = "harnessprd:project";

// ========================================================================
// localStorage 持久化
// ========================================================================

function loadProject(): ProjectState {
  try {
    const raw = localStorage.getItem(PROJECT_KEY);
    if (!raw) return createEmptyProjectState();
    const parsed = JSON.parse(raw);
    // 兼容旧数据：解构忽略 autoAdvance (已移除)，确保所有字段存在
    const { autoAdvance, ...cleanData } = parsed;
    return {
      ...createEmptyProjectState(),
      ...cleanData,
      prd: { ...createEmptyDocumentState(), ...cleanData.prd },
      api: { ...createEmptyDocumentState(), ...cleanData.api },
      prompts: { ...createEmptyDocumentState(), ...cleanData.prompts },
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
// 确认对话框
// ========================================================================

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

function ConfirmDialog({ isOpen, title, message, onConfirm, onCancel }: ConfirmDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/40" onClick={onCancel} />
      <div className="relative bg-white rounded-lg shadow-xl max-w-sm w-full mx-4 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
        <p className="text-sm text-gray-600 mb-6">{message}</p>
        <div className="flex justify-end gap-3">
          <button
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            onClick={onCancel}
          >
            取消
          </button>
          <button
            className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700"
            onClick={() => {
              onConfirm();
              onCancel();
            }}
          >
            确认
          </button>
        </div>
      </div>
    </div>
  );
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
  const [showCompletionPrompt, setShowCompletionPrompt] = useState(false);
  const [pendingNextDocType, setPendingNextDocType] = useState<"prd" | "api" | "prompts" | null>(null);
  const [previewModal, setPreviewModal] = useState<{ isOpen: boolean; docType: "prd" | "api" | "prompts" | null }>({
    isOpen: false,
    docType: null,
  });
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ isOpen: false, title: "", message: "", onConfirm: () => {} });

  // 用于在 streaming 中断时保留部分内容
  const streamingContentRef = useRef("");

  // 同步 ref
  useEffect(() => {
    streamingContentRef.current = streamingContent;
  }, [streamingContent]);

  // 初始化调试日志会话 ID（从已持久化的 project 中读取）
  useEffect(() => {
    if (project.session_id) {
      debugLogger.setSessionId(project.session_id);
    }
  }, []);

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
  const switchView = useCallback((newView: ViewState) => {
    updateProject((prev) => {
      debugLogger.log('info', 'state:transition', {
        from: prev.viewState,
        to: newView,
        trigger: 'user_action',
      });
      return { ...prev, viewState: newView };
    });
  }, [updateProject]);

  // ======================================================================
  // 表单提交
  // ======================================================================

  const handleSubmit = useCallback(async () => {
    setSubmitting(true);
    setError(null);

    const sessionId = crypto.randomUUID();
    debugLogger.setSessionId(sessionId);

    updateProject((prev) => ({
      ...prev,
      session_id: sessionId,
      viewState: "ai_dialogue",
      messages: [],
      completedSteps: [...new Set([...prev.completedSteps, "form_editing" as ViewState])],
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
        messages: [
          ...prev.messages,
          {
            role: "assistant",
            content: result.summary,
            timestamp: new Date().toISOString(),
          },
        ],
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

    // 创建新的 AbortController
    const controller = new AbortController();
    setAbortController(controller);

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
            // 重新生成完成，清除该步骤的待更新状态
            pendingUpdates: p.pendingUpdates.filter(s => s !== `reviewing_${docType}` as ViewState),
          }));
          return "";
        });
        setAbortController(null);
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
        setAbortController(null);
      },
    }, controller.signal);
  }, [project, switchView, updateProject]);

  // ======================================================================
  // 文档优化
  // ======================================================================

  const handleOptimizeDoc = useCallback((docType: "prd" | "api" | "prompts") => {
    const doc = project[docType];
    const contentToOptimize = doc.user_edits || doc.content;

    setStreamingContent("");
    setError(null);

    // 创建新的 AbortController
    const controller = new AbortController();
    setAbortController(controller);

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
        setAbortController(null);
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
        setAbortController(null);
      },
    }, controller.signal);
  }, [project, updateProject]);

  // ======================================================================
  // 取消生成
  // ======================================================================

  const handleCancel = useCallback(() => {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
      setError("已取消生成");
      setTimeout(() => setError(null), 2000);
    }
  }, [abortController]);

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
      completedSteps: [...new Set([...prev.completedSteps, `reviewing_${docType}` as ViewState])],
      // 清除该步骤的待更新状态（用户已确认，数据已一致）
      pendingUpdates: prev.pendingUpdates.filter(s => s !== `reviewing_${docType}` as ViewState),
    }));
    
    const nextDocType = nextDocTypeMap[docType];
    if (nextDocType) {
      if (project.autoAdvance) {
        // 自动推进：直接生成下一个文档
        setTimeout(() => handleGenerateDoc(nextDocType), 200);
      } else {
        // 手动推进：显示提示栏
        setPendingNextDocType(nextDocType);
        setShowCompletionPrompt(true);
      }
    }
  }, [updateProject, handleGenerateDoc, project.autoAdvance]);

  // ======================================================================
  // 提示栏回调
  // ======================================================================

  const handleContinue = useCallback(() => {
    if (pendingNextDocType) {
      setShowCompletionPrompt(false);
      handleGenerateDoc(pendingNextDocType);
      setPendingNextDocType(null);
    }
  }, [pendingNextDocType, handleGenerateDoc]);

  const handleSkip = useCallback(() => {
    // 跳过当前阶段，进入下一阶段
    if (pendingNextDocType) {
      const nextStateMap: Record<string, ViewState> = {
        prd: "generating_api",
        api: "generating_prompts",
        prompts: "completed",
      };
      const nextState = nextStateMap[pendingNextDocType];

      // 待更新步骤标签
      const DOC_LABEL: Record<string, string> = {
        prd: "PRD",
        api: "接口文档",
        prompts: "提示词套件",
      };
      const skipLabel = DOC_LABEL[pendingNextDocType] || pendingNextDocType;

      setConfirmDialog({
        isOpen: true,
        title: "确认跳过",
        message: `跳过${skipLabel}阶段，确定吗？`,
        onConfirm: () => {
          // 更新状态到下一个阶段
          if (nextState) {
            switchView(nextState);
          }
          setShowCompletionPrompt(false);
          setPendingNextDocType(null);
        },
      });
    }
  }, [pendingNextDocType, switchView]);

  const handleBack = useCallback(() => {
    // 返回上一个阶段
    setShowCompletionPrompt(false);
    setPendingNextDocType(null);
  }, []);

  // ======================================================================
  // 重置项目
  // ======================================================================

  const handleReset = useCallback(() => {
    setConfirmDialog({
      isOpen: true,
      title: "开始新项目",
      message: "将清空所有数据，确定吗？",
      onConfirm: () => {
        localStorage.removeItem(PROJECT_KEY);
        setProject(createEmptyProjectState());
        setStreamingContent("");
        setError(null);
      },
    });
  }, []);

  // ======================================================================
  // 文档预览、下载、复制
  // ======================================================================

  const handlePreview = useCallback((docType: "prd" | "api" | "prompts") => {
    setPreviewModal({ isOpen: true, docType });
  }, []);

  const handleDownload = useCallback((docType: "prd" | "api" | "prompts") => {
    const doc = project[docType];
    const content = doc.user_edits || doc.content;
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    // 文件名大写前缀，如 PRD_2026-06-21.md
    const prefixMap: Record<string, string> = { prd: "PRD", api: "API", prompts: "Prompts" };
    a.download = `${prefixMap[docType]}_${new Date().toISOString().split("T")[0]}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [project]);

  const handleCopy = useCallback((docType: "prd" | "api" | "prompts") => {
    // 显示复制成功提示
    setError("已复制到剪贴板");
    setTimeout(() => setError(null), 2000);
  }, []);

  const handleDownloadAll = useCallback(async () => {
    const zip = new JSZip();
    
    // 添加文档到 ZIP（spec 要求文件名：PRD.md、API.md、Prompts.md）
    zip.file("PRD.md", project.prd.user_edits || project.prd.content);
    zip.file("API.md", project.api.user_edits || project.api.content);
    zip.file("Prompts.md", project.prompts.user_edits || project.prompts.content);
    
    // 生成 ZIP 文件
    const content = await zip.generateAsync({ type: "blob" });
    
    // 下载 ZIP 文件
    const url = URL.createObjectURL(content);
    const a = document.createElement("a");
    a.href = url;
    a.download = `HarnessPRD_${new Date().toISOString().split("T")[0]}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [project]);

  // 逐个下载所有文档
  const handleDownloadAllSeparately = useCallback(() => {
    (["prd", "api", "prompts"] as const).forEach((docType, idx) => {
      setTimeout(() => handleDownload(docType), idx * 300);
    });
  }, [handleDownload]);

  // ======================================================================
  // 导航与回退（必须在 early return 之前定义，遵守 Hooks 规则）
  // ======================================================================

  const handleNavigate = useCallback((targetViewState: ViewState) => {
    if (!isValidStateTransition(project.viewState, targetViewState, project.completedSteps)) {
      setError(`无法从 ${project.viewState} 转换到 ${targetViewState}`);
      return;
    }

    // Bug #2 修复: 从表单页跳转时必须通过表单验证
    if (project.viewState === "form_editing") {
      const fd = project.form_data;
      const missing: string[] = [];
      if (!fd.product_name?.trim()) missing.push("产品名称");
      if (!fd.one_liner?.trim()) missing.push("一句话定义");
      if (!fd.problem_statement?.trim()) missing.push("解决的问题");
      if (!fd.target_users?.trim()) missing.push("目标用户");
      if (!Array.isArray(fd.mvp_features) || fd.mvp_features.length < 3 || fd.mvp_features.some((v: string) => !v?.trim())) {
        missing.push("MVP 核心功能（至少3项）");
      }
      if (!fd.platform) missing.push("目标平台");
      if (!fd.needs_auth) missing.push("用户登录");
      if (!fd.needs_database) missing.push("数据存储");
      if (!fd.page_count) missing.push("页面数量");

      if (missing.length > 0) {
        setError(`请先完整填写产品信息表单。未填写：${missing.join("、")}`);
        return;
      }
    }

    switchView(targetViewState);
  }, [project.viewState, project.completedSteps, project.form_data, switchView]);

  const handleRollback = useCallback((targetStep: ViewState) => {
    if (!project.completedSteps.includes(targetStep)) {
      setError(`步骤 ${targetStep} 尚未完成，无法回退`);
      return;
    }

    const currentIdx = STEP_INDEX_MAP[project.viewState];
    const targetIdx = STEP_INDEX_MAP[targetStep];
    if (targetIdx >= currentIdx) {
      setError(`无法回退到 ${targetStep}，它不在当前步骤之前`);
      return;
    }

    const targetLabel = STEPS[targetIdx]?.label || targetStep;
    const currentLabel = STEPS[currentIdx]?.label || project.viewState;
    // 列出所有受影响的后续步骤
    const affectedLabels: string[] = [];
    for (let i = targetIdx + 1; i <= currentIdx; i++) {
      const label = STEPS[i]?.label;
      if (label) affectedLabels.push(label);
    }
    const affectedText = affectedLabels.join("、");
    const confirmMessage = `返回${targetLabel}阶段将标记${affectedText}为待更新，确定吗？`;

    setConfirmDialog({
      isOpen: true,
      title: "确认回退",
      message: confirmMessage,
      onConfirm: () => {
        const pendingUpdates: ViewState[] = [];
        for (let i = targetIdx + 1; i <= currentIdx; i++) {
          const stepId = STEPS[i]?.id as ViewState;
          if (stepId && !pendingUpdates.includes(stepId)) {
            pendingUpdates.push(stepId);
          }
        }
        updateProject((prev) => ({
          ...prev,
          viewState: targetStep,
          pendingUpdates: [...new Set([...prev.pendingUpdates, ...pendingUpdates])],
        }));
      },
    });
  }, [project.viewState, project.completedSteps, updateProject]);

  const handleAutoAdvanceChange = useCallback((autoAdvance: boolean) => {
    updateProject(prev => ({ ...prev, autoAdvance }));
  }, [updateProject]);

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
        <CompletionSummary
          project={project}
          onPreview={handlePreview}
          onDownload={handleDownload}
          onCopy={handleCopy}
          onDownloadAll={handleDownloadAll}
          onDownloadAllSeparately={handleDownloadAllSeparately}
          onNewProject={handleReset}
        />
      );
      break;

    default:
      content = (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-gray-500">未知状态</p>
        </div>
      );
  }

  const DOC_TYPE_MAP: Record<string, "prd" | "api" | "prompts"> = {
    reviewing_prd: "prd",
    reviewing_api: "api",
    reviewing_prompts: "prompts",
  };

  const DOC_TYPE_LABEL: Record<string, string> = {
    prd: "PRD",
    api: "接口文档",
    prompts: "提示词",
  };

  const primaryActions: PrimaryAction[] = [];
  if (viewState === 'ai_dialogue') {
    if (project.messages.length > 0 && !chatLoading) {
      primaryActions.push({
        label: '生成 PRD',
        onClick: () => handleGenerateDoc('prd'),
        variant: 'primary',
      });
    }
  } else if (viewState === 'completed') {
    primaryActions.push({
      label: '开始新项目',
      onClick: handleReset,
      variant: 'primary',
    });
  } else if (DOC_TYPE_MAP[viewState]) {
    const docType = DOC_TYPE_MAP[viewState];
    primaryActions.push({
      label: docType === 'prompts' ? '完成' : `确认${DOC_TYPE_LABEL[docType]}`,
      onClick: () => handleConfirmDoc(docType),
      variant: 'primary',
    });
  }

  const secondaryActions: SecondaryAction[] = [];
  if (viewState === 'ai_dialogue') {
    if (project.messages.length > 0 && !chatLoading) {
      secondaryActions.push({
        label: '生成摘要',
        onClick: handleGenerateSummary,
      });
    }
  } else if (DOC_TYPE_MAP[viewState]) {
    const docType = DOC_TYPE_MAP[viewState];
    secondaryActions.push({
      label: 'AI 优化',
      onClick: () => handleOptimizeDoc(docType),
    });
    secondaryActions.push({
      label: '编辑',
      onClick: () => handleDocEdit(docType, project[docType].user_edits || project[docType].content),
    });
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* 移动端菜单按钮 */}
      <button
        className="md:hidden fixed top-4 left-4 z-50 p-2 bg-white rounded-lg shadow-md"
        onClick={() => setSidebarOpen(!sidebarOpen)}
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {/* 侧边栏 */}
      <div className={`fixed md:static inset-y-0 left-0 z-40 transform ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0 transition-transform duration-300 ease-in-out`}>
        <Sidebar
          current={viewState}
          project={project}
          onNavigate={handleNavigate}
          onRollback={handleRollback}
          primaryActions={primaryActions}
          secondaryActions={secondaryActions}
          onAutoAdvanceChange={handleAutoAdvanceChange}
        />
      </div>
      
      {/* 遮罩层 */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      
      {/* 内容区 */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1">{content}</div>
        {showCompletionPrompt && (
          <CompletionPromptBar
            currentViewState={viewState}
            onContinue={handleContinue}
            onSkip={handleSkip}
            onBack={handleBack}
            onCancel={() => {
              handleCancel();
              setShowCompletionPrompt(false);
              setPendingNextDocType(null);
            }}
            isGenerating={streamingContent !== ""}
          />
        )}
        {previewModal.isOpen && previewModal.docType && (
          <PreviewModal
            isOpen={previewModal.isOpen}
            onClose={() => setPreviewModal({ isOpen: false, docType: null })}
            title={previewModal.docType === "prd" ? "PRD 预览" : previewModal.docType === "api" ? "接口文档预览" : "提示词套件预览"}
            content={project[previewModal.docType]?.user_edits || project[previewModal.docType]?.content || ""}
          />
        )}
        <ConfirmDialog
          isOpen={confirmDialog.isOpen}
          title={confirmDialog.title}
          message={confirmDialog.message}
          onConfirm={confirmDialog.onConfirm}
          onCancel={() => setConfirmDialog((prev) => ({ ...prev, isOpen: false }))}
        />
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
    </div>
  );
}
