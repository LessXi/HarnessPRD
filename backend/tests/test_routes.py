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

async def _fake_stream(*args, **kwargs):
    """模拟 LLM 流式返回 3 个 chunk"""
    for chunk in ["Hello", " World", "!"]:
        yield chunk


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

    @patch("api.conversation.chat_stream", side_effect=_fake_stream)
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
            "form_data": {"product_name": "TestApp"},
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

    @patch("api.documents.generate_document_stream", side_effect=_fake_stream)
    def test_prd_stream_returns_sse(self, mock_stream):
        """POST /api/documents/prd/stream 返回 SSE 流"""
        resp = client.post("/api/documents/prd/stream", json={
            "session_id": "test-001",
            "form_data": {"product_name": "TestApp"},
            "requirements_summary": "test summary",
        })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_invalid_doc_type_400(self):
        """不支持的文档类型返回 400"""
        resp = client.post("/api/documents/invalid/stream", json={
            "session_id": "test-001",
            "form_data": {},
            "requirements_summary": "test",
        })
        assert resp.status_code == 400

    @patch("api.documents.optimize_document_stream", side_effect=_fake_stream)
    def test_optimize_returns_sse(self, mock_stream):
        """POST /api/documents/prd/optimize 返回 SSE 流"""
        resp = client.post("/api/documents/prd/optimize", json={
            "session_id": "test-001",
            "content": "# Test",
            "form_data": {"product_name": "TestApp"},
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
