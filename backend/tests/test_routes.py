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

    def test_get_session(self):
        """获取单个 session"""
        # 先创建
        payload = {
            "product_name": "查询测试",
            "one_liner": "测试",
            "problem_statement": "测试",
            "target_users": "测试",
            "mvp_features": ["a", "b", "c"],
            "platform_type": "web",
            "needs_auth": "yes",
            "needs_database": "yes",
            "page_count": "1-3",
        }
        create_resp = client.post("/api/sessions", json=payload)
        sid = create_resp.json()["session_id"]

        resp = client.get(f"/api/sessions/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid
        assert data["current_state"] == "ai_dialogue"
        assert data["form_data"]["product_name"] == "查询测试"

    def test_get_session_404(self):
        """不存在的 session_id 返回 404"""
        resp = client.get("/api/sessions/nonexistent-id")
        assert resp.status_code == 404

    def test_create_session_missing_required(self):
        """缺少必填字段返回 422（Pydantic 校验）"""
        payload = {
            "product_name": "测试",
            # 缺少 one_liner、problem_statement 等
            "mvp_features": ["a", "b", "c"],
            "platform_type": "web",
            "needs_auth": "yes",
            "needs_database": "yes",
            "page_count": "1-3",
        }
        resp = client.post("/api/sessions", json=payload)
        assert resp.status_code == 422

    def test_create_session_mvp_too_few(self):
        """MVP 功能少于 3 条返回 422（Pydantic 校验）"""
        payload = {
            "product_name": "测试",
            "one_liner": "测试",
            "problem_statement": "测试",
            "target_users": "测试",
            "mvp_features": ["a", "b"],  # 只有 2 条
            "platform_type": "web",
            "needs_auth": "yes",
            "needs_database": "yes",
            "page_count": "1-3",
        }
        resp = client.post("/api/sessions", json=payload)
        assert resp.status_code == 422

    def test_create_session_invalid_enum(self):
        """select/radio 字段传入非法值返回 400"""
        payload = {
            "product_name": "测试",
            "one_liner": "测试",
            "problem_statement": "测试",
            "target_users": "测试",
            "mvp_features": ["a", "b", "c"],
            "platform_type": "INVALID_PLATFORM",  # 非法值
            "needs_auth": "yes",
            "needs_database": "yes",
            "page_count": "1-3",
        }
        resp = client.post("/api/sessions", json=payload)
        assert resp.status_code == 400


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

    # ===== 错误分支 =====

    def test_send_message_wrong_state(self):
        """非 AI_DIALOGUE 状态发送消息返回 400"""
        from core.state import session_store, StateEnum, SessionData
        from datetime import datetime, timezone
        import uuid
        # 直接创建一个状态为 FORM_EDITING 的 session
        session = SessionData(
            session_id=str(uuid.uuid4()),
            current_state=StateEnum.FORM_EDITING,
            created_at=datetime.now(timezone.utc),
        )
        session_store._sessions[session.session_id] = session
        resp = client.post(f"/api/sessions/{session.session_id}/messages", json={"content": "你好"})
        assert resp.status_code == 400

    def test_get_messages_404(self):
        """不存在的 session 获取消息返回 404"""
        resp = client.get("/api/sessions/nonexistent/messages")
        assert resp.status_code == 404

    def test_start_stream_with_history(self):
        """已有历史消息时调用 start-stream 返回 400"""
        sid = self._create_session()
        # 先发一条消息
        client.post(f"/api/sessions/{sid}/messages", json={"content": "你好"})
        resp = client.post(f"/api/sessions/{sid}/start-stream")
        assert resp.status_code == 400

    def test_start_stream_404(self):
        """不存在的 session 调用 start-stream 返回 404"""
        resp = client.post("/api/sessions/nonexistent/start-stream")
        assert resp.status_code == 404

    def test_continue_stream_without_history(self):
        """无历史消息时调用 continue-stream 返回 400"""
        sid = self._create_session()
        resp = client.post(f"/api/sessions/{sid}/continue-stream", json={"content": "你好"})
        assert resp.status_code == 400

    def test_continue_stream_404(self):
        """不存在的 session 调用 continue-stream 返回 404"""
        resp = client.post("/api/sessions/nonexistent/continue-stream", json={"content": "你好"})
        assert resp.status_code == 404


class TestSummary:
    """需求摘要路由"""

    def _create_session(self) -> str:
        """辅助：创建 session"""
        payload = {
            "product_name": "摘要测试",
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

    def test_summary_404(self):
        """不存在的 session 返回 404"""
        resp = client.post("/api/sessions/nonexistent/summary/generate")
        assert resp.status_code == 404

    def test_summary_confirm_no_summary(self):
        """未生成摘要时确认返回 400"""
        sid = self._create_session()
        resp = client.post(f"/api/sessions/{sid}/summary/confirm")
        assert resp.status_code == 400

    def test_summary_reject(self):
        """拒绝摘要返回 200"""
        sid = self._create_session()
        resp = client.post(f"/api/sessions/{sid}/summary/reject")
        assert resp.status_code == 200

    def test_summary_confirm(self):
        """生成摘要后确认成功 → 状态变为 generating_prd"""
        from core.state import session_store, ChatMessage
        sid = self._create_session()
        # 手动设置摘要（跳过 LLM 调用）
        session = session_store.get(sid)
        session.requirements_summary = "这是一个测试摘要"
        session_store.update(session)

        resp = client.post(f"/api/sessions/{sid}/summary/confirm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["next_state"] == "ai_dialogue"  # 确认后留在 ai_dialogue，生成 PRD 时才切状态


class TestSkip:
    """跳过对话路由"""

    def test_skip_dialogue(self):
        """跳过对话 → 状态变为 generating_prd"""
        payload = {
            "product_name": "跳过测试",
            "one_liner": "测试",
            "problem_statement": "测试",
            "target_users": "测试",
            "mvp_features": ["a", "b", "c"],
            "platform_type": "web",
            "needs_auth": "yes",
            "needs_database": "yes",
            "page_count": "1-3",
        }
        create_resp = client.post("/api/sessions", json=payload)
        sid = create_resp.json()["session_id"]

        resp = client.post(f"/api/sessions/{sid}/dialogues/skip")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["next_state"] == "generating_prd"

    def test_skip_dialogue_404(self):
        """不存在的 session 返回 404"""
        resp = client.post("/api/sessions/nonexistent/dialogues/skip")
        assert resp.status_code == 404


class TestDocuments:
    """文档生成路由全链路"""

    # ===== 辅助方法 =====

    def _create_prd_session(self) -> str:
        """创建 AI_DIALOGUE 状态的 session"""
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

    def _create_api_ready_session(self) -> str:
        """创建 REVIEWING_PRD 状态的 session（API 文档生成前需要）"""
        from core.state import session_store, StateEnum
        sid = self._create_prd_session()
        session = session_store.get(sid)
        session.current_state = StateEnum.REVIEWING_PRD
        session.prd.content = "测试 PRD 内容"
        session_store.update(session)
        return sid

    def _create_prompts_ready_session(self) -> str:
        """创建 REVIEWING_API 状态的 session（提示词生成前需要）"""
        from core.state import session_store, StateEnum
        sid = self._create_prd_session()
        session = session_store.get(sid)
        session.current_state = StateEnum.REVIEWING_API
        session.prd.content = "测试 PRD 内容"
        session.api.content = "测试 API 内容"
        session_store.update(session)
        return sid

    def _create_reviewing_prd_session(self) -> str:
        """创建 REVIEWING_PRD 状态的 session（PRD 确认需要）"""
        from core.state import session_store, StateEnum
        sid = self._create_prd_session()
        session = session_store.get(sid)
        session.current_state = StateEnum.REVIEWING_PRD
        session.prd.content = "测试 PRD 内容"
        session.prd.confirmed = False
        session_store.update(session)
        return sid

    # ===== 生成端点 =====

    def test_generate_prd(self):
        """PRD 生成端点可达"""
        sid = self._create_prd_session()
        resp = client.post(f"/api/sessions/{sid}/documents/prd/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "stream_url" in data

    def test_generate_prd_wrong_state(self):
        """非 AI_DIALOGUE 状态生成 PRD 返回 400"""
        from core.state import session_store, StateEnum
        sid = self._create_prd_session()
        session = session_store.get(sid)
        session.current_state = StateEnum.REVIEWING_PRD  # 错误状态
        session_store.update(session)
        resp = client.post(f"/api/sessions/{sid}/documents/prd/generate")
        assert resp.status_code == 400

    def test_generate_api(self):
        """API 文档生成端点可达（需在 REVIEWING_PRD 状态）"""
        sid = self._create_api_ready_session()
        resp = client.post(f"/api/sessions/{sid}/documents/api/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_generate_prompts(self):
        """提示词套件生成端点可达（需在 REVIEWING_API 状态）"""
        sid = self._create_prompts_ready_session()
        resp = client.post(f"/api/sessions/{sid}/documents/prompts/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_generate_wrong_doc_type(self):
        """不支持的文档类型返回 400"""
        sid = self._create_prd_session()
        resp = client.post(f"/api/sessions/{sid}/documents/invalid/generate")
        assert resp.status_code == 400

    def test_generate_session_404(self):
        """不存在的 session 返回 404"""
        resp = client.post("/api/sessions/nonexistent/documents/prd/generate")
        assert resp.status_code == 404

    # ===== 查询端点 =====

    def test_get_document(self):
        """获取文档内容"""
        sid = self._create_prd_session()
        from core.state import session_store
        session = session_store.get(sid)
        session.prd.content = "测试 PRD 内容"
        session_store.update(session)
        resp = client.get(f"/api/sessions/{sid}/documents/prd")
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "测试 PRD 内容"

    def test_get_document_wrong_type(self):
        """不支持的文档类型返回 400"""
        sid = self._create_prd_session()
        resp = client.get(f"/api/sessions/{sid}/documents/invalid")
        assert resp.status_code == 400

    def test_get_document_404(self):
        """不存在的 session 返回 404"""
        resp = client.get("/api/sessions/nonexistent/documents/prd")
        assert resp.status_code == 404

    # ===== 审核轮次 =====

    def test_get_review_rounds_empty(self):
        """新文档审核轮次为空列表"""
        sid = self._create_prd_session()
        resp = client.get(f"/api/sessions/{sid}/documents/prd/review-rounds")
        assert resp.status_code == 200
        assert resp.json() == []

    # ===== 编辑端点 =====

    def test_edit_content(self):
        """编辑文档内容"""
        sid = self._create_prd_session()
        resp = client.put(
            f"/api/sessions/{sid}/documents/prd/content",
            json={"content": "用户编辑的内容"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    # ===== 下载端点 =====

    def test_download(self):
        """下载文档为 .md 文件"""
        sid = self._create_prd_session()
        from core.state import session_store
        session = session_store.get(sid)
        session.prd.content = "# 测试 PRD"
        session_store.update(session)
        resp = client.get(f"/api/sessions/{sid}/documents/prd/download")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]
        assert 'attachment; filename="prd.md"' in resp.headers["content-disposition"]

    # ===== 确认端点 =====

    def test_confirm_document(self):
        """确认文档 → 状态转换"""
        sid = self._create_reviewing_prd_session()
        resp = client.post(f"/api/sessions/{sid}/documents/prd/confirm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["next_state"] == "generating_api"

    def test_confirm_document_wrong_state(self):
        """非 reviewing 状态确认文档返回 400"""
        sid = self._create_prd_session()  # AI_DIALOGUE 状态
        resp = client.post(f"/api/sessions/{sid}/documents/prd/confirm")
        assert resp.status_code == 400

    def test_confirm_document_404(self):
        """不存在的 session 返回 404"""
        resp = client.post("/api/sessions/nonexistent/documents/prd/confirm")
        assert resp.status_code == 404
