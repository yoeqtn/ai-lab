"""工具集：模型可以调用的能力，一个函数就是一项能力。"""
import re
import uuid

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import config as settings
from app.core.db import SessionLocal
from app.models import Approval, Chunk, Document
from app.services.embedding import embed_texts

# 假的订单数据，先不建表。等真正接入订单系统时再换。
_ORDERS = {
    "A12345": {"status": "已发货", "carrier": "顺丰", "city": "杭州", "eta": "11 月 6 日"},
    "B88888": {"status": "待付款", "carrier": None, "city": "上海", "eta": None},
}

_ORDER_RE = re.compile(r"^[A-Za-z]\d{5}$")


@tool
async def search_docs(query: str, config: RunnableConfig) -> str:
    """在企业知识库中检索资料片段。

    什么时候必须用：用户询问公司政策、退换货规则、报销流程、
    员工制度、产品条款、合同细节等"知识库里可能有答案"的问题。
    什么时候不要用：打招呼、闲聊、问订单物流（那用 get_order_status）。

    参数 query：用户的原始问题，原样传入，不要改写、不要加引号。
    """
    tenant_id = config.get("configurable", {}).get("tenant_id", "demo")
    vectors = await embed_texts([query])
    dist = Chunk.embedding.cosine_distance(vectors[0])

    async with SessionLocal() as session:
        rows = await session.execute(
            select(Chunk.content, Document.filename, dist.label("d"))
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.tenant_id == tenant_id)   # 租户隔离：只查本租户文档
            .order_by(dist)
            .limit(5)
        )
        hits = rows.all()

    # 逐条过滤，而不是只看第一条：避免把明显不相关的片段塞给模型
    hits = [h for h in hits if h.d is not None and h.d <= settings.REJECT_DISTANCE][:3]
    if not hits:
        return "知识库中没有与这个问题相关的内容。"
    return "\n\n".join(
        f"[片段{i + 1} | 来源: {h.filename}] {h.content}"
        for i, h in enumerate(hits)
    )


_TICKETS: dict[str, dict] = {}      # 演示用：进程内存储，重启即丢


@tool
def create_ticket(summary: str, contact: str) -> str:
    """为客户创建一张人工工单，转给人工客服跟进。

    什么时候必须用：用户明确要求"转人工""投诉""建个工单""找人处理"，
    或者问题查资料解决不了、用户明显不满意时。

    不要用的情况：能从知识库直接回答的问题，先回答，别急着转人工。

    参数 summary：一句话概括客户诉求，30 字以内。
    参数 contact：客户的手机号或邮箱，用于回访。用户没给就先问，不要编。
    """
    ticket_id = "T" + uuid.uuid4().hex[:6].upper()
    _TICKETS[ticket_id] = {"summary": summary[:200], "contact": contact}
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
async def submit_refund(
    order_id: str, amount: int, reason: str, config: RunnableConfig
) -> str:
    """提交退款申请，进入人工审批。

    order_id 是订单号，形如 A12345；amount 是整数元；reason 写用户给出的原因。
    提交后不要承诺具体到账时间，只说"1 个工作日内出结果"。
    """
    order_id = (order_id or "").strip().upper()
    if not _ORDER_RE.match(order_id):
        return "订单号格式不正确，应为一个大写字母加 5 位数字，例如 A12345。"

    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return "退款金额必须是整数。"
    if amount <= 0:
        return "退款金额必须大于 0。"

    ticket_no = "AP-" + uuid.uuid4().hex[:8].upper()
    thread_id = config.get("configurable", {}).get("thread_id", "")
    async with SessionLocal() as session:
        session.add(Approval(
            ticket_no=ticket_no, order_id=order_id,
            amount=amount, reason=(reason or "用户未说明")[:200], thread_id=thread_id,
        ))
        try:
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            constraint = getattr(getattr(e.orig, "diag", None), "constraint_name", "")
            if constraint != "uq_approvals_pending_order":
                raise
            return "这个订单已经有一张待审批的退款单了，请等处理结果，不要重复提交。"
    return f"已提交，工单号 {ticket_no}，状态：待审批。1 个工作日内出结果。"


@tool
async def check_approval(ticket_no: str) -> str:
    """按工单号查询审批进度。ticket_no 形如 AP-1A2B3C4D。"""
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(Approval).where(Approval.ticket_no == ticket_no.upper())
            )
        ).scalar_one_or_none()
    if row is None:
        return f"没有找到工单 {ticket_no}，请确认单号。"
    return f"{row.ticket_no}：{row.status}，金额 {row.amount} 元。"


@tool
async def list_my_approvals(config: RunnableConfig) -> str:
    """列出本次对话提交过的所有退款工单及状态。

    用户问"我提交的退款怎么样了""还有哪些在等"且没给单号时使用。
    """
    tid = config.get("configurable", {}).get("thread_id", "")
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Approval).where(Approval.thread_id == tid)
                .order_by(Approval.created_at.desc()).limit(5)
            )
        ).scalars().all()
    if not rows:
        return "这个对话里还没有提交过退款申请。"
    return "\n".join(f"{r.ticket_no}：{r.status}，{r.amount} 元" for r in rows)
