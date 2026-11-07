"""对话相关接口：/agent、/agent/approve、/conversations。"""
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core import config as settings
from app.core.db import SessionLocal
from app.models import Conversation, Message

router = APIRouter(tags=["chat"])


# ============ 请求体 ============
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=settings.MAX_INPUT_CHARS)
    thread_id: str | None = None      # 不传 = 新开一个会话


class ApproveIn(BaseModel):
    thread_id: str
    decision: Literal["yes", "no"] = "yes"   # yes 批准 / no 拒绝


# ============ 两个小工具函数 ============
def conv_id_from_thread(thread_id: str | None) -> int | None:
    """thread_id 形如 conv-12，反解出 conversations.id。"""
    if not thread_id or not thread_id.startswith("conv-"):
        return None
    try:
        return int(thread_id[5:])
    except ValueError:
        return None


async def save_turn(conv_id: int, user_text: str, answer: str) -> None:
    """一轮问答落业务表，方便做会话列表、历史检索。"""
    async with SessionLocal() as s:
        s.add(Message(conversation_id=conv_id, role="user", content=user_text))
        s.add(Message(conversation_id=conv_id, role="assistant", content=answer))
        await s.commit()


# ============ 对话 ============
@router.post("/agent")
async def agent_chat(
    body: ChatIn,
    request: Request,
    user_id: int = Header(default=1, ge=1, alias="X-User-Id"),
    tenant_id: str = Header(default="demo", max_length=64, alias="X-Tenant-Id"),
):
    graph = request.app.state.graph       # 就是 lifespan 里挂上去的那张图

    # --- 事务一：只碰数据库，拿到 conv_id ---
    conv_id = conv_id_from_thread(body.thread_id)
    async with SessionLocal() as s:
        conv = None
        if conv_id:
            conv = await s.get(Conversation, conv_id)
            if conv is not None and conv.user_id != user_id:
                raise HTTPException(404, "会话不存在")
        if conv is None:                  # 没传、或者 id 不存在，就新建
            conv = Conversation(user_id=user_id, title=body.message[:30])
            s.add(conv)
        try:
            await s.flush()               # flush 之后 conv.id 才有值
            conv_id = conv.id
            await s.commit()
        except IntegrityError as e:
            await s.rollback()
            raise HTTPException(400, f"用户 {user_id} 不存在，请先创建用户") from e

    thread_id = f"conv-{conv_id}"         # thread_id 从业务 id 派生，两套系统天然对齐
    cfg = {"configurable": {"thread_id": thread_id, "tenant_id": tenant_id}}

    # --- 事务外调图：可能要好几秒，别占着数据库连接 ---
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=body.message)]}, cfg
    )

    # --- 被审批闸门拦住 ---
    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        await save_turn(conv_id, body.message, f"[待审批] {payload['message']}")
        return {"thread_id": thread_id, "status": "pending_approval",
                "approval": payload}

    answer = str(result["messages"][-1].content)
    await save_turn(conv_id, body.message, answer)
    return {"thread_id": thread_id, "status": "done", "answer": answer}


# ============ 审批 ============
@router.post("/agent/approve")
async def agent_approve(
    body: ApproveIn,
    request: Request,
    user_id: int = Header(default=1, ge=1, alias="X-User-Id"),
    tenant_id: str = Header(default="demo", max_length=64, alias="X-Tenant-Id"),
):
    graph = request.app.state.graph
    conv_id = conv_id_from_thread(body.thread_id)
    if conv_id is None:
        raise HTTPException(404, "会话不存在")
    async with SessionLocal() as s:
        conv = await s.get(Conversation, conv_id)
    if conv is None or conv.user_id != user_id:
        raise HTTPException(404, "会话不存在")

    cfg = {"configurable": {"thread_id": body.thread_id, "tenant_id": tenant_id}}
    st = await graph.aget_state(cfg)
    if not st.next:                       # 没有 pending 的节点，说明没有被拦住
        raise HTTPException(409, "该会话没有待审批的操作（可能已处理，或被新消息覆盖）")

    result = await graph.ainvoke(Command(resume=body.decision), cfg)
    answer = str(result["messages"][-1].content)
    await save_turn(conv_id, f"[审批] {body.decision}", answer)
    return {"thread_id": body.thread_id, "status": "done", "answer": answer}


# ============ 会话列表 ============
@router.get("/conversations")
async def list_conversations(
    user_id: int = Header(default=1, ge=1, alias="X-User-Id"),
):
    """列出当前用户的会话及消息数（查业务表，不依赖 LangGraph 内部表结构）。"""
    stmt = (
        select(
            Conversation.id,
            Conversation.title,
            Conversation.created_at,
            func.count(Message.id).label("messages"),
        )
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
        .group_by(Conversation.id)
        .order_by(Conversation.created_at.desc())
        .limit(50)
    )
    async with SessionLocal() as s:
        rows = (await s.execute(stmt)).all()
    return [
        {
            "thread_id": f"conv-{r.id}",
            "title": r.title,
            "messages": r.messages,
            "created_at": r.created_at,
        }
        for r in rows
    ]
