import { describe, it, expect } from "vitest";
import { migrateFormData } from "../migration";

describe("migrateFormData", () => {
  it("fills defaults for empty object", () => {
    const result = migrateFormData({});
    expect(result._schema_version).toBe("1.0.0");
    expect(result.product_name).toBe("");
    expect(result.mvp_features).toEqual(["", "", ""]);
    expect(result.visual_style).toBe("unsure");
    expect(result.feature_priority).toBe("ai_suggest");
    expect(result.doc_depth).toBe("standard");
    expect(result.ai_temperature).toBe("balanced");
    expect(result.timeline_expectation).toBe("unsure");
  });

  it("preserves existing fields", () => {
    const result = migrateFormData({
      product_name: "MyApp",
      one_liner: "Best app ever",
      platform_type: "web",
    });
    expect(result.product_name).toBe("MyApp");
    expect(result.one_liner).toBe("Best app ever");
    expect(result.platform_type).toBe("web");
    expect(result.visual_style).toBe("unsure"); // default preserved
  });

  it("fixes mvp_features when too short", () => {
    const result = migrateFormData({ mvp_features: ["only"] });
    expect(result.mvp_features).toEqual(["", "", ""]);
  });

  it("fixes mvp_features when empty array", () => {
    const result = migrateFormData({ mvp_features: [] });
    expect(result.mvp_features).toEqual(["", "", ""]);
  });

  it("fixes mvp_features when not an array", () => {
    const result = migrateFormData({ mvp_features: "not-an-array" });
    expect(result.mvp_features).toEqual(["", "", ""]);
  });

  it("keeps valid mvp_features with 3+ items", () => {
    const features = ["登录", "注册", "首页"];
    const result = migrateFormData({ mvp_features: features });
    expect(result.mvp_features).toEqual(features);
  });

  it("keeps valid mvp_features with extra items", () => {
    const features = ["a", "b", "c", "d", "e"];
    const result = migrateFormData({ mvp_features: features });
    expect(result.mvp_features).toEqual(features);
  });

  it("coerces mvp_features items to strings", () => {
    const result = migrateFormData({ mvp_features: [1, 2, 3] as any });
    expect(result.mvp_features).toEqual(["1", "2", "3"]);
  });

  it("handles null/undefined values", () => {
    const result = migrateFormData({
      product_name: null,
      one_liner: undefined,
    } as any);
    expect(result.product_name).toBe("");
    expect(result.one_liner).toBe("");
  });

  it("handles null/undefined data argument", () => {
    const result = migrateFormData(null as any);
    expect(result._schema_version).toBe("1.0.0");
    expect(result.mvp_features).toEqual(["", "", ""]);
  });

  it("handles undefined data argument", () => {
    const result = migrateFormData(undefined as any);
    expect(result._schema_version).toBe("1.0.0");
    expect(result.product_name).toBe("");
    expect(result.mvp_features).toEqual(["", "", ""]);
  });

  it("overwrites version to 1.0.0", () => {
    const result = migrateFormData({ _schema_version: "0.5.0" });
    expect(result._schema_version).toBe("1.0.0");
  });

  it("returns all 18 keys (17 fields + _schema_version)", () => {
    const result = migrateFormData({});
    const keys = Object.keys(result).sort();
    expect(keys).toContain("_schema_version");
    expect(keys).toContain("product_name");
    expect(keys).toContain("additional_context");
    expect(keys).toContain("mvp_features");
    expect(keys.length).toBe(18);
  });

  it("fills optional fields with schema defaults", () => {
    const result = migrateFormData({});
    expect(result.competitors).toBe("");
    expect(result.tech_stack_preference).toBe("");
    expect(result.additional_context).toBe("");
  });
});
