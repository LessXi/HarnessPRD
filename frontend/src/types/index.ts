// ===== 表单配置 =====

export interface QuestionConfig {
  id: string
  label: string
  type: 'text' | 'textarea' | 'select' | 'radio' | 'list'
  required?: boolean
  description?: string
  options?: { value: string; label: string }[]
}

export interface QuestionsConfig {
  base_questions: QuestionConfig[]
  advanced_questions: QuestionConfig[]
}

// ===== 状态 & 步骤 =====

export type ViewState =
  | 'form_editing'
  | 'ai_dialogue'
  | 'generating_prd'
  | 'reviewing_prd'
  | 'generating_api'
  | 'reviewing_api'
  | 'generating_prompts'
  | 'reviewing_prompts'
  | 'completed'

export const STEPS = [
  { id: 'form_editing', label: '描述产品' },
  { id: 'ai_dialogue', label: 'AI 对话' },
  { id: 'reviewing_prd', label: 'PRD' },
  { id: 'reviewing_api', label: '接口文档' },
  { id: 'reviewing_prompts', label: '提示词' },
] as const

/** ViewState → 步骤索引（generating_* 合并到对应的 reviewing_* 步骤） */
export const STEP_INDEX_MAP: Record<ViewState, number> = {
  form_editing: 0,
  ai_dialogue: 1,
  generating_prd: 2,
  reviewing_prd: 2,
  generating_api: 3,
  reviewing_api: 3,
  generating_prompts: 4,
  reviewing_prompts: 4,
  completed: 4,
}

// ===== 对话消息 =====

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
}

// ===== 项目状态（前端 localStorage 持久化） =====

export interface DocumentState {
  content: string
  user_edits: string
  confirmed: boolean
}

export interface ProjectState {
  session_id: string
  viewState: ViewState
  form_data: Record<string, any>
  messages: ChatMessage[]
  requirements_summary: string
  prd: DocumentState
  api: DocumentState
  prompts: DocumentState
}

/** 创建空的 DocumentState */
export function createEmptyDocumentState(): DocumentState {
  return { content: '', user_edits: '', confirmed: false }
}

/** 创建空的 ProjectState */
export function createEmptyProjectState(): ProjectState {
  return {
    session_id: '',
    viewState: 'form_editing',
    form_data: {},
    messages: [],
    requirements_summary: '',
    prd: createEmptyDocumentState(),
    api: createEmptyDocumentState(),
    prompts: createEmptyDocumentState(),
  }
}

// ===== API 请求类型（与后端 Pydantic 模型对齐） =====

export interface ChatRequest {
  session_id: string
  form_data: Record<string, any>
  history: ChatMessage[]
}

export interface SummaryRequest {
  session_id: string
  form_data: Record<string, any>
  history: ChatMessage[]
}

export interface DocumentRequest {
  session_id: string
  form_data: Record<string, any>
  requirements_summary: string
  previous_content?: string
  prd_content?: string
  api_content?: string
}

export interface OptimizeRequest {
  session_id: string
  content: string
  form_data: Record<string, any>
  requirements_summary: string
  prd_content?: string
  api_content?: string
}

// ===== SSE 流式回调 =====

/** SSE 流式回调 */
export interface StreamCallbacks {
  onChunk: (text: string) => void
  onDone: (data?: Record<string, any>) => void
  onError: (error: string) => void
}
