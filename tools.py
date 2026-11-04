"""工具集：模型可以调用的能力，一个函数就是一项能力。"""
from langchain_core.tools import tool
from sqlalchemy import select
# ↓↓↓ 这两个 import 按你项目的实际名字改 ↓↓↓
from db import SessionLocal          # 也可能叫 SessionLocal
from embedding import embed_texts       # 也可能叫 get_embedding
from models import Chunk

# 假的订单数据，先不建表。等 Day13 再换成真表。
_ORDERS = {
    "A12345": {"status": "已发货", "carrier": "顺丰", "city": "杭州", "eta": "11 月 6 日"},
    "B88888": {"status": "待付款", "carrier": None, "city": "上海", "eta": None},
}

@tool
async def search_docs(query: str) -> str:
    """在企业知识库中检索资料片段。

    什么时候必须用：用户询问公司政策、退换货规则、报销流程、
    员工制度、产品条款、合同细节等"知识库里可能有答案"的问题。
    什么时候不要用：打招呼、闲聊、问订单物流（那用 get_order_status）。

    参数 query：用户的原始问题，原样传入，不要改写、不要加引号。
    """
    vectors = await embed_texts([query])
    dist = Chunk.embedding.cosine_distance(vectors[0])

    async with SessionLocal() as session:
        rows = await session.execute(
            select(Chunk.content, dist.label("d")).order_by(dist).limit(3)
        )
        hits = rows.all()

    if not hits:
        return "知识库为空，没有检索到任何资料。"
    if hits[0].d > 0.55:
        return "知识库中没有与这个问题相关的内容。"
    return "\n\n".join(f"[片段{i + 1}] {h.content}" for i, h in enumerate(hits))

_TICKETS = {}      # 内存里凑合存，Day13 换成真表


@tool
def create_ticket(summary: str, contact: str) -> str:
    """为客户创建一张人工工单，转给人工客服跟进。

    什么时候必须用：用户明确要求"转人工""投诉""建个工单""找人处理"，
    或者问题查资料解决不了、用户明显不满意时。

    不要用的情况：能从知识库直接回答的问题，先回答，别急着转人工。

    参数 summary：一句话概括客户诉求，30 字以内。
    参数 contact：客户的手机号或邮箱，用于回访。用户没给就先问，不要编。
    """
    ticket_id = f"T{len(_TICKETS) + 1001}"
    _TICKETS[ticket_id] = {"summary": summary, "contact": contact}
    return f"已创建工单 {ticket_id}，24 小时内人工客服会联系 {contact}。"


@tool
def get_order_status(order_id: str) -> str:
    """查询订单的物流状态。

    什么时候必须用：用户提到具体订单号，或问"我的货到哪了""发货了吗"。
    参数 order_id：订单号，一个大写字母加 5 位数字，例如 A12345。
    如果用户没给订单号：先反问用户要订单号，不要编造。
    """
    info = _ORDERS.get(order_id.upper().strip())
    if info is None:
        return f"没有找到订单 {order_id}，请确认订单号是否正确。"
    if info["status"] == "待付款":
        return f"订单 {order_id} 尚未付款，付款后 24 小时内发货。"
    return (
        f"订单 {order_id} 已由{info['carrier']}发出，"
        f"当前在{info['city']}，预计 {info['eta']} 送达。"
    )

@tool
def refund(order_id: str, amount: int) -> str:
    """给客户办理退款。

    什么时候必须用：用户明确要求退款，并且已经说清订单号和金额。
    参数 order_id：订单号，如 A12345。
    参数 amount：退款金额，整数，单位元。

    风险：金额超过 1000 元会自动触发人工审批，不需要你在回复里询问。
    """
    return f"已为订单 {order_id} 退款 {amount} 元，预计 1-3 个工作日到账。"