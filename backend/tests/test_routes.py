"""测试 FastAPI 路由的冒烟测试（不调 LLM）"""

import json
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


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


class TestSessions:
    """会话路由"""

    def test_get_questions(self):
        """表单配置加载"""
        resp = client.get("/api/sessions/questions")
        assert resp.status_code == 200
        data = resp.json()
        assert "base_questions" in data
        assert "advanced_questions" in data
        assert len(data["base_questions"]) >= 11  # 至少 11 个必填

    def test_create_session(self):
        """创建 session"""
        payload = {
            "product_name": "测试产品",
            "one_liner": "一句话描述",
            "problem_statement": "痛点",
            "target_users": "用户",
            "mvp_features": ["功能1", "功能2", "功能3"],
            "platform_type": "web",
            "needs_auth": "yes",
            "needs_database": "yes",
            "page_count": "1-3",
        }
        resp = client.post("/api/sessions", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0
        assert data["current_state"] == "ai_dialogue"

    def test_list_sessions(self):
        """列表接口"""
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_sessions_with_data(self):
        """创建后列表非空"""
        # 先创建
        payload = {
            "product_name": "列表测试",
            "one_liner": "测试",
            "problem_statement": "测试",
            "target_users": "测试",
            "mvp_features": ["a", "b", "c"],
            "platform_type": "web",
            "needs_auth": "yes",
            "needs_database": "yes",
            "page_count": "1-3",
        }
        client.post("/api/sessions", json=payload)
        resp = client.get("/api/sessions")
        assert len(resp.json()) >= 1


class TestDialogues:
    """对话路由"""

    def _create_session(self) -> str:
        """辅助：创建 session 并返回 session_id"""
        payload = {
            "product_name": "对话测试",
            "one_liner": "测试",
            "problem_statement": "测试",
            "target_users": "测试",
            "mvp_features": ["a", "b", "c"],
            "platform_type": "web",
            "needs_auth": "yes",
            "needs_database": "yes",
            "page_count": "1-3",
        }
        resp = client.post("/api/sessions", json=payload)
        return resp.json()["session_id"]

    def test_get_messages_empty(self):
        """新 session 的消息列表为空"""
        sid = self._create_session()
        resp = client.get(f"/api/sessions/{sid}/messages")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_send_message(self):
        """发送用户消息"""
        sid = self._create_session()
        resp = client.post(f"/api/sessions/{sid}/messages", json={"content": "你好"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_get_messages_after_send(self):
        """发送后消息列表有内容"""
        sid = self._create_session()
        client.post(f"/api/sessions/{sid}/messages", json={"content": "你好"})
        resp = client.get(f"/api/sessions/{sid}/messages")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["role"] == "user"
        assert data[0]["content"] == "你好"

    def test_sse_stream_no_history(self):
        """无历史时 start-stream 返回 AI 问候"""
        sid = self._create_session()
        with client.stream("POST", f"/api/sessions/{sid}/start-stream") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            # 读取前 2 个数据块确认 SSE 格式正确
            for i, chunk in enumerate(response.iter_bytes()):
                if i >= 2:
                    break
                assert b"data:" in chunk

    def test_sse_stream_with_history(self):
        """有历史时 continue-stream 返回 AI 回复"""
        sid = self._create_session()
        client.post(f"/api/sessions/{sid}/messages", json={"content": "帮我分析一下"})
        with client.stream("POST", f"/api/sessions/{sid}/continue-stream", json={"content": "帮我分析一下"}) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            # 验证至少收到一个数据块
            for chunk in response.iter_bytes():
                assert b"data:" in chunk
                break


class TestDocuments:
    """文档生成路由（仅验证可达性）"""

    def _create_session(self) -> str:
        """创建 session（保持 AI_DIALOGUE 状态，PRD 生成需要）"""
        from services.session_service import create_session
        from core.state import FormData
        form = FormData(
            product_name="文档测试",
            one_liner="测试",
            problem_statement="测试",
            target_users="测试",
            mvp_features=["a", "b", "c"],
            platform_type="web",
            needs_auth="yes",
            needs_database="yes",
            page_count="1-3",
        )
        session = create_session(form)
        return session.session_id

    def test_generate_prd(self):
        """PRD 生成端点可达"""
        sid = self._create_session()
        resp = client.post(f"/api/sessions/{sid}/documents/prd/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "stream_url" in data
