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

// ===== FormData 强类型（17 字段 + _schema_version） =====

export interface FormData {
  _schema_version: string;
  product_name: string;
  one_liner: string;
  problem_statement: string;
  target_users: string;
  mvp_features: string[];
  platform_type: string;
  needs_auth: string;
  needs_database: string;
  page_count: string;
  visual_style: string;
  competitors: string;
  tech_stack_preference: string;
  feature_priority: string;
  doc_depth: string;
  ai_temperature: string;
  timeline_expectation: string;
  additional_context: string;
}

export interface ProjectState {
  session_id: string
  viewState: ViewState
  form_data: FormData
  messages: ChatMessage[]
  requirements_summary: string
  prd: DocumentState
  api: DocumentState
  prompts: DocumentState
  completedSteps: ViewState[]  // 已完成步骤列表
  pendingUpdates: ViewState[]  // 待更新步骤列表
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
    form_data: {
      _schema_version: '1.0.0',
      product_name: '',
      one_liner: '',
      problem_statement: '',
      target_users: '',
      mvp_features: ['', '', ''],
      platform_type: '',
      needs_auth: '',
      needs_database: '',
      page_count: '',
      visual_style: 'unsure',
      competitors: '',
      tech_stack_preference: '',
      feature_priority: 'ai_suggest',
      doc_depth: 'standard',
      ai_temperature: 'balanced',
      timeline_expectation: 'unsure',
      additional_context: '',
    },
    messages: [],
    requirements_summary: '',
    prd: createEmptyDocumentState(),
    api: createEmptyDocumentState(),
    prompts: createEmptyDocumentState(),
    completedSteps: [],
    pendingUpdates: [],
  }
}

// ===== API 请求类型（与后端 Pydantic 模型对齐） =====

export interface ChatRequest {
  session_id: string
  form_data: FormData
  history: ChatMessage[]
}

export interface SummaryRequest {
  session_id: string
  form_data: FormData
  history: ChatMessage[]
}

export interface DocumentRequest {
  session_id: string
  form_data: FormData
  requirements_summary: string
  previous_content?: string
  prd_content?: string
  api_content?: string
}

export interface OptimizeRequest {
  session_id: string
  content: string
  form_data: FormData
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

// ===== 状态转换验证 =====

/** 合法的状态转换映射 */
const VALID_TRANSITIONS: Record<ViewState, ViewState[]> = {
  form_editing: ['ai_dialogue'],
  ai_dialogue: ['generating_prd', 'form_editing'], // 可以回退到表单编辑
  generating_prd: ['reviewing_prd', 'ai_dialogue'],
  reviewing_prd: ['generating_api', 'ai_dialogue'], // 可以回退到对话
  generating_api: ['reviewing_api', 'reviewing_prd'],
  reviewing_api: ['generating_prompts', 'reviewing_prd'], // 可以回退到PRD审阅
  generating_prompts: ['reviewing_prompts', 'reviewing_api'],
  reviewing_prompts: ['completed', 'reviewing_api'], // 可以回退到API审阅
  completed: ['form_editing'], // 可以开始新项目
}

/**
 * 验证状态转换是否合法
 * @param current 当前状态
 * @param target 目标状态
 * @param completedSteps 已完成步骤列表
 * @returns 是否合法
 */
export function isValidStateTransition(
  current: ViewState,
  target: ViewState,
  completedSteps: ViewState[]
): boolean {
  // 检查是否是合法的直接转换
  const validTargets = VALID_TRANSITIONS[current];
  if (validTargets.includes(target)) {
    return true;
  }
  
  // 如果目标状态在已完成步骤中，允许回退
  if (completedSteps.includes(target)) {
    // 但需要确保目标状态是当前状态的前序步骤
    const currentIdx = STEP_INDEX_MAP[current];
    const targetIdx = STEP_INDEX_MAP[target];
    return targetIdx < currentIdx;
  }
  
  return false;
}
