import type { FormData } from "@/types";
import { debugLogger } from "./debugLogger";

const CURRENT_SCHEMA_VERSION = "1.0.0";

const DEFAULTS: FormData = {
  _schema_version: CURRENT_SCHEMA_VERSION,
  product_name: "",
  one_liner: "",
  problem_statement: "",
  target_users: "",
  mvp_features: ["", "", ""],
  platform_type: "",
  needs_auth: "",
  needs_database: "",
  page_count: "",
  visual_style: "unsure",
  competitors: "",
  tech_stack_preference: "",
  feature_priority: "ai_suggest",
  doc_depth: "standard",
  ai_temperature: "balanced",
  timeline_expectation: "unsure",
  additional_context: "",
};

/**
 * 将旧的 Record<string, any> form_data 迁移为强类型 FormData。
 * 检测版本号，填充缺失字段默认值，确保 mvp_features 至少 3 项。
 *
 * @param data 从 localStorage 解析的原始 form_data
 * @returns 迁移后的 FormData
 */
export function migrateFormData(data: Record<string, any>): FormData {
  const fromVersion =
    typeof data?._schema_version === "string"
      ? data._schema_version
      : "0.0.0";

  // 过滤掉 null/undefined 值，避免覆盖默认值
  const cleaned = Object.fromEntries(
    Object.entries(data ?? {}).filter(
      ([, v]) => v !== null && v !== undefined,
    ),
  );
  // 用默认值打底，再用实际数据覆盖
  const result: FormData = {
    ...DEFAULTS,
    ...cleaned,
    _schema_version: CURRENT_SCHEMA_VERSION,
    // 保证 mvp_features 是合法数组（至少 3 项，每项为 string）
    mvp_features:
      Array.isArray(cleaned?.mvp_features) && cleaned.mvp_features.length >= 3
        ? cleaned.mvp_features.map(String)
        : [...DEFAULTS.mvp_features],
  };

  debugLogger.log("info", "migration:formData", {
    fromVersion,
    toVersion: CURRENT_SCHEMA_VERSION,
    inputFieldCount: Object.keys(data ?? {}).length,
    filledFields: Object.keys(result).length,
  });

  return result;
}
