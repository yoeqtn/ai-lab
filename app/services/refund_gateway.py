"""退款网关（演示桩）。

真实项目里这里调支付网关，并用 transactional outbox / 重试任务保证最终一致。
"""
import logging

logger = logging.getLogger(__name__)


async def charge_refund(ticket_no: str) -> bool:
    """调用支付网关。返回 True 表示成功。"""
    logger.info("退款工单 %s 已批准，调用支付网关…", ticket_no)
    # TODO: 接入真实网关；失败时返回 False，由上层标记 refund_failed 并重试
    return True
