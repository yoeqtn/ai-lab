"""审批闸门的纯逻辑测试（不需要数据库/模型）。"""
from langchain_core.messages import AIMessage
from langgraph.graph import END

from app.agent.graph import NEED_APPROVAL, TOOLS, needs_approval, route_after_review


def _call(name: str, **args) -> dict:
    return {"name": name, "args": args}


def test_all_approval_rules_match_registered_tools():
    """回归测试：规则键必须真的注册在 TOOLS 里，否则永远不会触发。"""
    registered = {t.name for t in TOOLS}
    assert set(NEED_APPROVAL) <= registered


def test_small_refund_does_not_need_approval():
    assert needs_approval(_call("submit_refund", order_id="A12345", amount=500)) is False


def test_large_refund_needs_approval():
    assert needs_approval(_call("submit_refund", order_id="A12345", amount=5000)) is True


def test_missing_or_invalid_amount_is_treated_as_risky():
    assert needs_approval(_call("submit_refund", order_id="A12345")) is True
    assert needs_approval(_call("submit_refund", order_id="A12345", amount="很多")) is True


def test_read_only_tools_do_not_need_approval():
    assert needs_approval(_call("search_docs", query="退货政策")) is False
    assert needs_approval(_call("get_order_status", order_id="A12345")) is False


def test_route_after_review_goes_to_tools_when_approved():
    msg = AIMessage(
        content="",
        tool_calls=[{"name": "submit_refund", "args": {"amount": 500}, "id": "call_1"}],
    )
    assert route_after_review({"messages": [msg]}) == "tools"


def test_route_after_review_ends_when_rejected():
    assert route_after_review({"messages": [AIMessage(content="操作已取消")]}) == END
