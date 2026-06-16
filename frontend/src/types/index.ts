export interface QuestionConfig {
  name: string
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
