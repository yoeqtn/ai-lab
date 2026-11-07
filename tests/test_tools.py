"""不依赖数据库/网络的基础工具测试。"""
from app.agent.tools import create_ticket, get_order_status


def test_order_status_known_order():
    result = get_order_status.invoke({"order_id": "A12345"})
    assert "顺丰" in result
    assert "杭州" in result


def test_order_status_unknown_order():
    result = get_order_status.invoke({"order_id": "Z00000"})
    assert "没有找到订单" in result


def test_create_ticket_returns_ticket_no():
    result = create_ticket.invoke({"summary": "要求转人工", "contact": "13800000000"})
    assert "已创建工单 T" in result
    assert "13800000000" in result
