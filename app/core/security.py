"""最小化接口鉴权。

管理端和上传接口属于高权限操作。设置 APP_API_TOKEN 后，调用方需要带
`X-API-Key` 请求头；不设置则视为本地开发模式，直接放行。

真正的生产系统应使用 OAuth2/JWT + RBAC，这里只是把危险接口先保护起来。
"""
import secrets

from fastapi import Header, HTTPException

from app.core import config


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    if not config.API_TOKEN:       # 未配置 = 开发模式
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, config.API_TOKEN):
        raise HTTPException(status_code=401, detail="缺少或错误的 X-API-Key")
