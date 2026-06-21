"""Tests for field_registry.py — schema-first with fallback to questions_config.json."""

import importlib
from pathlib import Path

import pytest

from core import field_registry as fr


# ── Schema loading ──────────────────────────────────────────────

class TestGetSchema:
    """get_schema() returns valid JSON Schema when product_schema.json exists."""

    def test_get_schema_returns_dict(self):
        s = fr.get_schema()
        assert isinstance(s, dict)
        assert "$schema" in s
        assert s["$schema"] == "https://json-schema.org/draft-07/schema#"

    def test_get_schema_has_18_properties(self):
        s = fr.get_schema()
        assert len(s["properties"]) == 18

    def test_get_schema_version_is_1_0_0(self):
        s = fr.get_schema()
        assert s["x-meta"]["schema_version"] == "1.0.0"


# ── Field IDs ───────────────────────────────────────────────────

class TestFieldIds:
    """get_field_ids() returns correct list from schema."""

    expected_ids = [
        "product_name", "one_liner", "problem_statement", "target_users",
        "mvp_features", "platform_type", "needs_auth", "needs_database",
        "page_count", "visual_style", "competitors",
        "tech_stack_preference", "feature_priority", "doc_depth",
        "ai_temperature", "timeline_expectation", "additional_context",
    ]

    def test_get_field_ids_returns_17(self):
        assert len(fr.get_field_ids()) == 17

    def test_get_field_ids_exact_order(self):
        assert fr.get_field_ids() == self.expected_ids

    def test_get_required_field_ids_returns_9(self):
        required = fr.get_required_field_ids()
        assert len(required) == 9

    def test_get_required_field_ids_exact(self):
        required = fr.get_required_field_ids()
        expected = [
            "product_name", "one_liner", "problem_statement", "target_users",
            "mvp_features", "platform_type", "needs_auth", "needs_database",
            "page_count",
        ]
        assert required == expected

    def test_get_optional_field_ids_returns_8(self):
        assert len(fr.get_optional_field_ids()) == 8

    def test_optional_ids_disjoint_from_required(self):
        optional = set(fr.get_optional_field_ids())
        required = set(fr.get_required_field_ids())
        assert optional.isdisjoint(required)
        assert len(optional) + len(required) == 17


# ── Field lookup ────────────────────────────────────────────────

class TestGetField:
    """get_field() and is_list_field() work correctly."""

    def test_get_field_returns_none_for_unknown(self):
        assert fr.get_field("nonexistent") is None

    def test_get_field_returns_dict_with_id(self):
        f = fr.get_field("product_name")
        assert isinstance(f, dict)
        assert f["id"] == "product_name"

    def test_get_field_returns_full_data(self):
        f = fr.get_field("platform_type")
        assert f["id"] == "platform_type"
        assert "label" in f
        assert "type" in f

    def test_is_list_field_true_for_mvp_features(self):
        assert fr.is_list_field("mvp_features") is True

    def test_is_list_field_false_for_text_field(self):
        assert fr.is_list_field("product_name") is False

    def test_is_list_field_false_for_select(self):
        assert fr.is_list_field("platform_type") is False

    def test_is_list_field_false_for_unknown(self):
        assert fr.is_list_field("nonexistent") is False


# ── Fallback when schema file missing ───────────────────────────

class TestFallback:
    """When product_schema.json is missing, fallback to questions_config.json."""

    @pytest.fixture
    def schema_missing(self):
        """Temporarily rename product_schema.json to trigger fallback."""
        schema_path = Path(__file__).resolve().parent.parent / "core" / "product_schema.json"
        bak_path = schema_path.with_suffix(".json.testbak")

        # Rename schema file to simulate missing
        schema_path.rename(bak_path)

        # Clear module caches so get_schema() re-reads from disk
        import core.field_registry as fr_mod
        fr_mod._CONFIG_CACHE = None
        fr_mod._SCHEMA_CACHE = None

        yield

        # Restore schema file
        bak_path.rename(schema_path)

        # Reload module to restore clean state
        importlib.reload(fr_mod)

    def test_fallback_returns_degraded_version(self, schema_missing):
        s = fr.get_schema()
        assert s["x-meta"]["schema_version"] == "0.0.0 (degraded)"

    def test_fallback_still_has_17_fields(self, schema_missing):
        assert len(fr.get_schema()["properties"]) == 17
        assert len(fr.get_field_ids()) == 17

    def test_fallback_field_ids_match(self, schema_missing):
        expected = [
            "product_name", "one_liner", "problem_statement", "target_users",
            "mvp_features", "platform_type", "needs_auth", "needs_database",
            "page_count", "visual_style", "competitors",
            "tech_stack_preference", "feature_priority", "doc_depth",
            "ai_temperature", "timeline_expectation", "additional_context",
        ]
        assert fr.get_field_ids() == expected

    def test_fallback_required_fields_count(self, schema_missing):
        assert len(fr.get_required_field_ids()) == 9

    def test_fallback_is_list_field(self, schema_missing):
        assert fr.is_list_field("mvp_features") is True
        assert fr.is_list_field("product_name") is False
