import axios from "axios";
import type { QuestionsConfig } from "@/types";

const api = axios.create({
  baseURL: "/api",
});

interface RawQuestion {
  id: string;
  label: string;
  type: string;
  required?: boolean;
  description?: string;
  options?: { value: string; label: string }[];
}

interface RawQuestionsConfig {
  base_questions: RawQuestion[];
  advanced_questions: RawQuestion[];
}

function mapQuestion(q: RawQuestion) {
  return {
    name: q.id,
    label: q.label,
    type: q.type,
    required: q.required,
    description: q.description,
    options: q.options,
  };
}

export async function getQuestions(): Promise<QuestionsConfig> {
  const { data } = await api.get<RawQuestionsConfig>("/sessions/questions");
  return {
    base_questions: data.base_questions.map(mapQuestion),
    advanced_questions: data.advanced_questions.map(mapQuestion),
  };
}

export async function createSession(
  formData: Record<string, any>
): Promise<{ session_id: string; current_state: string }> {
  const { data } = await api.post("/sessions", formData);
  return data;
}
