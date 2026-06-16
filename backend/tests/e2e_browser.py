"""浏览器 E2E 测试：表单填写 → 提交 → AI 对话页跳转

依赖：python + Puppeteer（通过 MCP Chrome 浏览器控制）
用法：见下方 main() 中的流程
注意：需要先启动 backend（:8000）和 frontend（:5173）
"""

import json
import time
import sys

# 测试配置
FRONTEND_URL = "http://localhost:5173"
BACKEND_URL = "http://localhost:8000"

# 测试填写的数据
TEST_DATA = {
    "product_name": "智能简历助手",
    "one_liner": "AI 驱动的简历优化和投递管理工具",
    "problem_statement": "求职者花大量时间修改简历但不知道什么内容对特定岗位有效",
    "target_users": "应届毕业生和 3-5 年经验的职场人士",
    "mvp_features": ["一键简历解析", "智能关键词匹配", "投递记录追踪"],
    "platform_type": "web",
    "needs_auth": "yes",
    "needs_database": "yes",
    "page_count": "4-10",
    "visual_style": "minimal",
    "competitors": "Zety",
}


def run_browser_test():
    """使用 Puppeteer MCP 工具完成 E2E 测试"""
    from mcp__puppeteer__puppeteer_navigate import puppeteer_navigate
    from mcp__puppeteer__puppeteer_fill import puppeteer_fill
    from mcp__puppeteer__puppeteer_click import puppeteer_click
    from mcp__puppeteer__puppeteer_screenshot import puppeteer_screenshot
    from mcp__puppeteer__puppeteer_evaluate import puppeteer_evaluate

    print("=" * 50)
    print("Phase 3: 浏览器 E2E 测试")
    print("=" * 50)

    # 1. 导航到前端首页
    print("\n[1/6] 导航到前端首页...")
    puppeteer_navigate(FRONTEND_URL)

    # 2. 等待表单加载，截图确认
    print("\n[2/6] 等待表单加载...")
    time.sleep(3)
    puppeteer_screenshot("e2e-01-form-loaded")

    # 3. 填写必填字段
    print("\n[3/6] 填写表单字段...")
    fields = [
        ("#product_name", TEST_DATA["product_name"]),
        ("#one_liner", TEST_DATA["one_liner"]),
        ("#problem_statement", TEST_DATA["problem_statement"]),
        ("#target_users", TEST_DATA["target_users"]),
        ("#platform_type", TEST_DATA["platform_type"]),
        ("#needs_auth", TEST_DATA["needs_auth"]),
        ("#needs_database", TEST_DATA["needs_database"]),
        ("#page_count", TEST_DATA["page_count"]),
    ]
    for selector, value in fields:
        try:
            puppeteer_fill(selector, value)
            print(f"  填写 {selector} = {value[:20]}...")
        except Exception as e:
            print(f"  ⚠️  {selector} 不可用: {e}")

    # 填写 MVP 功能列表（可能需要特殊处理）
    for i, feature in enumerate(TEST_DATA["mvp_features"]):
        try:
            puppeteer_fill(f"#mvp_features_{i}", feature)
            print(f"  MVP 功能{i+1}: {feature}")
        except Exception:
            # 尝试其他选择器
            try:
                puppeteer_fill(f"input[name='mvp_features[{i}]']", feature)
                print(f"  MVP 功能{i+1}: {feature}")
            except Exception as e:
                print(f"  ⚠️ MVP 功能{i+1} 写不进去: {e}")

    # 4. 截图确认填写
    print("\n[4/6] 填写完毕，截图确认...")
    puppeteer_screenshot("e2e-02-form-filled")

    # 5. 点击提交按钮
    print("\n[5/6] 提交表单...")
    try:
        puppeteer_click("button[type='submit']")
    except Exception:
        try:
            puppeteer_click("button:contains('提交')")
        except Exception as e:
            print(f"  ⚠️ 提交按钮点击失败: {e}")

    # 6. 等待跳转到 AI 对话页，截图验证
    print("\n[6/6] 等待跳转...")
    time.sleep(5)
    puppeteer_screenshot("e2e-03-ai-dialogue")

    # 验证：通过 JS 检查页面内容
    print("\n--- 页面内容验证 ---")
    result = puppeteer_evaluate("""
        () => ({
            bodyText: document.body.innerText.substring(0, 500),
            url: window.location.href,
            hasAiDialogue: document.body.innerText.includes('AI 对话澄清'),
            hasSessionId: document.body.innerText.includes('会话 ID：'),
            stepProgress: document.querySelectorAll('.step-label, .text-primary-700, .font-semibold'),
        })
    """)
    print(f"  URL: {result.get('url', 'N/A')}")
    print(f"  包含 'AI 对话澄清': {result.get('hasAiDialogue', False)}")
    print(f"  包含 '会话 ID：': {result.get('hasSessionId', False)}")

    # 提取 session_id
    session_id = None
    if result.get("hasSessionId"):
        html = puppeteer_evaluate("document.body.innerHTML")
        import re
        match = re.search(r'会话 ID：<code[^>]*>([^<]+)</code>', str(html))
        if match:
            session_id = match.group(1)
            print(f"  session_id: {session_id}")

    print("\n" + "=" * 50)
    print("E2E 测试完成")
    print("=" * 50)
    return session_id


def verify_sse_backend(session_id: str):
    """通过后端 API 验证 SSE 流（不依赖前端）
    
    注意：新 SSE 端点为 POST /start-stream 和 POST /continue-stream，
    改用 urllib.request 的 POST 请求。
    """
    import urllib.request
    import json

    print(f"\n--- SSE 流测试（session: {session_id}）---")
    try:
        # 新 SSE 端点是 POST /start-stream
        url = f"{BACKEND_URL}/api/sessions/{session_id}/start-stream"
        data = b""  # 无请求体
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            chunks = []
            for i, line in enumerate(resp):
                text = line.decode("utf-8").strip()
                if text.startswith("data: "):
                    chunks.append(text)
                if i >= 10:  # 只读前几个 chunk
                    break
            if chunks:
                print(f"  ✅ 收到 {len(chunks)} 个 SSE 数据块")
                for c in chunks[:3]:
                    print(f"     {c[:60]}...")
                return True
            else:
                print("  ❌ 未收到 SSE 数据")
                return False
    except Exception as e:
        print(f"  ❌ SSE 连接失败: {e}")
        return False


def verify_backend_session(session_id: str):
    """验证 session 已正确持久化"""
    import urllib.request
    import json

    try:
        url = f"{BACKEND_URL}/api/sessions/{session_id}"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
            print(f"  Current state: {data.get('current_state', 'N/A')}")
            print(f"  Chat messages: {len(data.get('chat_messages', []))}")
            return data
    except Exception as e:
        print(f"  ❌ Session 查询失败: {e}")
        return None


if __name__ == "__main__":
    # 仅作为参考设计，实际通过 MCP Puppeteer 工具执行
    # 在 executor 环境中，这一流程用 puppeteer_* MCP 工具逐步骤执行
    print("请通过 MCP puppeteer_* 工具逐步骤执行此测试。")

    # 也可以回退为 direct API 验证
    test_session = "test-e2e-do-not-use"
    verify_sse_backend(test_session)
