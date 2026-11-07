from sqlalchemy import func, select, update

from app.models import Approval


async def decide_ticket(session, ticket_no: str, action: str, operator: str):
    """返回 (状态码, 数据)。200 成功 / 404 不存在 / 409 已处理。"""
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
