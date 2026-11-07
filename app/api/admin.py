"""管理端接口：退款审批列表与审批决定。"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import require_api_key
from app.crud import decide_ticket, mark_refund_result
from app.models import Approval
from app.services.refund_gateway import charge_refund

logger = logging.getLogger(__name__)

# 管理端整体要求 X-API-Key（未配置 APP_API_TOKEN 时自动放行）
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_api_key)])


class DecideIn(BaseModel):
    action: Literal["approved", "rejected"]     # 只收这两个词
    operator: str = Field(min_length=1, max_length=32)


@router.get("/approvals")
async def list_approvals(status: Literal["pending", "approved", "rejected", "refunded"] = "pending"):
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

    # 状态已经提交，再去做外部动作。失败时把工单标成 refund_failed，留给重试任务。
    refund_status = "not_applicable"
    if body.action == "approved":
        try:
            ok = await charge_refund(payload["ticket_no"])
            refund_status = "refunded" if ok else "refund_failed"
        except Exception:
            logger.exception("退款网关调用失败 ticket_no=%s", payload["ticket_no"])
            refund_status = "refund_failed"
        async with SessionLocal() as session:
            await mark_refund_result(session, payload["ticket_no"], refund_status)

    return {**payload, "refund_status": refund_status}
