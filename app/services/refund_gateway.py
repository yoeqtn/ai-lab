async def charge_refund(ticket_no: str) -> None:
    """真实项目里这里调支付网关。今天只打印，绝不真退钱。"""
    print(f"[refund] 工单 {ticket_no} 已批准，调用支付网关…")
    # 成功后把状态推到 refunded（approved -> refunded）
    # 失败就停在 approved，等重试任务扫出来