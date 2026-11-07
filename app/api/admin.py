"""管理端接口：退款审批列表与审批决定。"""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.db import SessionLocal
from app.crud import decide_ticket
from app.models import Approval
from app.services.refund_gateway import charge_refund

router = APIRouter(prefix="/admin", tags=["admin"])


class DecideIn(BaseModel):
    action: Literal["approved", "rejected"]     # 只收这两个词
    operator: str


@router.get("/approvals")
async def list_approvals(status: str = "pending"):
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Approval).where(Approval.status == status).order_by(Approval.created_at)
            )
        ).scalars().all()
    return [{"ticket_no": r.ticket_no, "order_id": r.order_id,
             "amount": r.amount, "reason": r.reason,
             "created_at": r.created_at} for r in rows]


@router.post("/approvals/{ticket_no}/decide")
async def decide(ticket_no: str, body: DecideIn):
    async with SessionLocal() as session:
        code, payload = await decide_ticket(session, ticket_no, body.action, body.operator)
    if code != 200:
        raise HTTPException(code, payload["detail"])

    # 状态已经提交，再去做外部动作
    if body.action == "approved":
        await charge_refund(payload["ticket_no"])
    return payload
