from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Approval


async def decide_ticket(
    session: AsyncSession, ticket_no: str, action: str, operator: str
) -> tuple[int, dict]:
    """返回 (状态码, 数据)。200 成功 / 404 不存在 / 409 已处理。

    用一条带条件的 UPDATE ... RETURNING 完成状态流转，避免"先查后改"的竞态。
    """
    stmt = (
        update(Approval)
        .where(Approval.ticket_no == ticket_no, Approval.status == "pending")
        .values(status=action, decided_at=func.now(), decided_by=operator)
        .returning(Approval.ticket_no, Approval.status, Approval.decided_by)
    )
    row = (await session.execute(stmt)).first()

    if row is not None:
        await session.commit()
        return 200, {"ticket_no": row[0], "status": row[1], "by": row[2]}

    # 没更新到：要么不存在，要么已经处理过，要分清
    await session.rollback()
    cur = (
        await session.execute(select(Approval).where(Approval.ticket_no == ticket_no))
    ).scalar_one_or_none()
    if cur is None:
        return 404, {"detail": f"工单 {ticket_no} 不存在"}
    return 409, {"detail": f"该工单已是 {cur.status}，由 {cur.decided_by} 处理"}


async def mark_refund_result(
    session: AsyncSession, ticket_no: str, status: str
) -> None:
    """记录支付网关的最终结果：approved -> refunded / refund_failed。

    只更新仍是 approved 的单子，避免重复回调把已完成状态覆盖掉。
    """
    await session.execute(
        update(Approval)
        .where(Approval.ticket_no == ticket_no, Approval.status == "approved")
        .values(status=status)
    )
    await session.commit()
