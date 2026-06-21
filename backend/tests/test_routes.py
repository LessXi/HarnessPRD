"""测试 FastAPI 路由的冒烟测试

无状态架构下的路由测试：
  GET  /                         → root
  GET  /health                   → health check
  GET  /api/questions            → 表单配置
  POST /api/chat/stream          → SSE 对话（mock LLM）
  POST /api/summary/generate     → 需求摘要（mock LLM）
  POST /api/documents/{type}/stream   → SSE 文档生成（mock LLM）
  POST /api/documents/{type}/optimize → SSE 文档优化（mock LLM）
  POST /api/documents/{type}/download → 文档下载
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# ---------- Mock LLM helpers ----------

from skill_engine.models import SSEEvent


VALID_FORM_DATA = {
    "product_name": "TestApp",
    "one_liner": "Test one-liner",
    "problem_statement": "Test problem",
    "target_users": "Test users",
    "mvp_features": ["a", "b", "c"],
    "platform_type": "web",
    "needs_auth": "yes",
    "needs_database": "yes",
    "page_count": "1-3",
}


async def _fake_chat_stream(*args, **kwargs):
    """模拟对话流式返回 3 个字符串 chunk（conversation 端点使用）。"""
    for chunk in ["Hello", " World", "!"]:
        yield chunk


async def _fake_doc_stream(*args, **kwargs):
    """模拟文档流式返回 3 个 SSEEvent chunk + done（documents 端点使用）。"""
    for chunk in ["Hello", " World", "!"]:
        yield SSEEvent(event="chunk", content=chunk)
    yield SSEEvent(event="done", content="Hello World!")


# ---------- Tests ----------

class TestHealth:
    """基础健康检查"""

    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_root(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "app" in resp.json()


class TestQuestions:
    """表单配置路由"""

    def test_get_questions_new_path(self):
        """新路径 /api/questions 返回表单配置"""
        resp = client.get("/api/questions")
        assert resp.status_code == 200
        data = resp.json()
        assert "base_questions" in data
        assert "advanced_questions" in data
        assert len(data["base_questions"]) >= 11

    def test_old_path_404(self):
        """旧路径 /api/sessions/questions 返回 404"""
        resp = client.get("/api/sessions/questions")
        assert resp.status_code == 404


class TestChatStream:
    """对话 SSE 端点"""

    @patch("api.conversation.chat_stream", side_effect=_fake_chat_stream)
    def test_chat_stream_returns_sse(self, mock_stream):
        """POST /api/chat/stream 返回 SSE 流"""
        resp = client.post("/api/chat/stream", json={
            "session_id": "test-001",
            "form_data": {
                "product_name": "TestApp",
                "one_liner": "A test app",
                "problem_statement": "testing",
                "target_users": "developers",
                "mvp_features": ["f1", "f2", "f3"],
                "platform_type": "web",
                "needs_auth": "yes",
                "needs_database": "yes",
                "page_count": "1-3",
            },
            "history": [],
        })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        # 验证 SSE 事件格式
        lines = [l for l in resp.text.split("\n") if l.startswith("data: ")]
        assert len(lines) >= 1
        events = [json.loads(l[6:]) for l in lines]
        assert any(e.get("event") == "chunk" for e in events)
        assert any(e.get("event") == "done" for e in events)

    def test_chat_stream_rejects_empty_body(self):
        """缺少必填字段应返回 422"""
        resp = client.post("/api/chat/stream", json={})
        assert resp.status_code == 422


class TestSummaryGenerate:
    """需求摘要端点"""

    @patch("api.conversation.generate_summary", new_callable=AsyncMock, return_value="Mock summary")
    def test_summary_returns_json(self, mock_summary):
        """POST /api/summary/generate 返回 JSON"""
        resp = client.post("/api/summary/generate", json={
            "session_id": "test-001",
            "form_data": VALID_FORM_DATA,
            "history": [],
        })
        assert resp.status_code == 200
        assert resp.json()["summary"] == "Mock summary"

    def test_summary_rejects_empty_body(self):
        """缺少必填字段应返回 422"""
        resp = client.post("/api/summary/generate", json={})
        assert resp.status_code == 422


class TestDocuments:
    """文档生成端点"""

    @patch("api.documents.generate_document_stream", side_effect=_fake_doc_stream)
    def test_prd_stream_returns_sse(self, mock_stream):
        """POST /api/documents/prd/stream 返回 SSE 流"""
        resp = client.post("/api/documents/prd/stream", json={
            "session_id": "test-001",
            "form_data": VALID_FORM_DATA,
            "requirements_summary": "test summary",
        })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_invalid_doc_type_400(self):
        """不支持的文档类型返回 400"""
        resp = client.post("/api/documents/invalid/stream", json={
            "session_id": "test-001",
            "form_data": VALID_FORM_DATA,
            "requirements_summary": "test",
        })
        assert resp.status_code == 400

    @patch("api.documents.optimize_document_stream", side_effect=_fake_doc_stream)
    def test_optimize_returns_sse(self, mock_stream):
        """POST /api/documents/prd/optimize 返回 SSE 流"""
        resp = client.post("/api/documents/prd/optimize", json={
            "session_id": "test-001",
            "content": "# Test",
            "form_data": VALID_FORM_DATA,
            "requirements_summary": "test",
        })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_optimize_rejects_empty_body(self):
        """缺少必填字段应返回 422"""
        resp = client.post("/api/documents/prd/optimize", json={})
        assert resp.status_code == 422

    def test_download_returns_markdown(self):
        """POST /api/documents/prd/download 返回 .md 文件"""
        resp = client.post("/api/documents/prd/download", json={
            "content": "# Test PRD\n\n## Overview\nTest content.",
        })
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers.get("content-type", "")
        assert "attachment" in resp.headers.get("content-disposition", "")

    def test_download_rejects_empty_content(self):
        """空内容应返回 400"""
        resp = client.post("/api/documents/prd/download", json={"content": ""})
        assert resp.status_code == 400


class TestOldRoutesRemoved:
    """旧路由已删除"""

    def test_old_sessions_root_404(self):
        resp = client.get("/api/sessions")
        assert resp.status_code == 404

    def test_old_session_detail_404(self):
        resp = client.get("/api/sessions/test-001")
        assert resp.status_code == 404

    def test_old_session_start_404(self):
        resp = client.post("/api/sessions/test-001/start-stream")
        assert resp.status_code == 404


class TestDebug:
    """Debug API 端点冒烟测试"""

    def test_receive_logs(self):
        """POST /api/debug/log 接收批量日志"""
        resp = client.post("/api/debug/log", json={
            "logs": [
                {
                    "timestamp": 1718000000.0,
                    "level": "info",
                    "source": "frontend::ChatPage",
                    "data": {"action": "click", "target": "confirm-btn"},
                    "session_id": "test-debug-001",
                },
                {
                    "timestamp": 1718000001.0,
                    "level": "warn",
                    "source": "frontend::ApiService",
                    "data": {"retry_count": 2},
                    "session_id": "test-debug-001",
                },
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["received"] == 2

    def test_get_session_found(self):
        """GET /api/debug/session/{id} 返回 session 日志"""
        # 先写入一条日志
        client.post("/api/debug/log", json={
            "logs": [{
                "timestamp": 1718000000.0,
                "level": "info",
                "source": "test",
                "data": {"msg": "hello"},
                "session_id": "test-get-session",
            }],
        })
        resp = client.get("/api/debug/session/test-get-session")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "test-get-session"
        assert data["count"] >= 1
        assert "logs" in data
        assert "total_size_bytes" in data

    def test_get_session_not_found_404(self):
        """不存在的 session 返回 404"""
        resp = client.get("/api/debug/session/non-existent")
        assert resp.status_code == 404

    def test_set_log_level_valid(self):
        """POST /api/debug/log-level 切换合法级别"""
        resp = client.post("/api/debug/log-level", json={"level": "DEBUG"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] == "DEBUG"
        assert "previous" in data

        # 恢复
        client.post("/api/debug/log-level", json={"level": "INFO"})

    def test_set_log_level_invalid_400(self):
        """非法级别返回 400"""
        resp = client.post("/api/debug/log-level", json={"level": "TRACE"})
        assert resp.status_code == 400
        assert "Invalid" in resp.json()["detail"]


class MockSkill:
    """模拟 SkillSchema，供 skills API 测试用"""
    def __init__(self, name: str, description: str, steps_count: int):
        self.name = name
        self.description = description
        self.steps = [None] * steps_count


class MockSkillLoader:
    """模拟 SkillLoader，供 skills API 测试用"""
    def __init__(self, skills: dict | None = None):
        self._cache = skills or {}

    def list_skills(self) -> list[str]:
        return list(self._cache.keys())

    def get(self, name: str):
        return self._cache.get(name)

    def reload(self) -> None:
        pass


class TestSkillsApi:
    """Skill 管理 API 端点 — GET /api/skills & POST /api/skills/reload"""

    def test_list_skills_when_loader_none(self):
        """_skill_loader 为 None → 返回空列表"""
        with patch("services.document_service._skill_loader", None):
            resp = client.get("/api/skills")
        assert resp.status_code == 200
        assert resp.json() == {"skills": []}

    def test_list_skills_with_entries(self):
        """_skill_loader 有值 → 返回 skill 列表"""
        skills = {
            "prd-generate": MockSkill("prd-generate", "生成 PRD 文档", 3),
            "api-generate": MockSkill("api-generate", "生成 API 文档", 2),
        }
        loader = MockSkillLoader(skills)
        with patch("services.document_service._skill_loader", loader):
            resp = client.get("/api/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills" in data
        assert len(data["skills"]) == 2
        names = {s["name"] for s in data["skills"]}
        assert "prd-generate" in names
        assert "api-generate" in names
        # 验证字段结构
        entry = [s for s in data["skills"] if s["name"] == "prd-generate"][0]
        assert entry["description"] == "生成 PRD 文档"
        assert entry["steps"] == 3

    def test_reload_when_loader_none(self):
        """_skill_loader 为 None → reload 返回 error 状态"""
        with patch("services.document_service._skill_loader", None):
            resp = client.post("/api/skills/reload")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"

    def test_reload_with_loader(self):
        """reload 调用 loader.reload() 并返回 skill 数量"""
        skills = {
            "prd-generate": MockSkill("prd-generate", "生成 PRD 文档", 3),
        }
        loader = MockSkillLoader(skills)
        with patch("services.document_service._skill_loader", loader):
            resp = client.post("/api/skills/reload")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["skills"] == 1
