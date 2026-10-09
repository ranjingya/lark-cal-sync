"""订阅 HTTP 接口与健康检查。"""

import asyncio
import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Request, Response

from .sync import SyncService

LOG = logging.getLogger(__name__)


def create_app(settings):
    """功能：创建订阅 HTTP 服务。参数：settings 为运行配置。返回值：FastAPI 应用。"""
    service = SyncService(settings)

    @asynccontextmanager
    async def lifespan(app):
        """启动刷新任务并在停止时清理任务。"""
        task = asyncio.create_task(service.run())
        LOG.info("订阅服务已启动")
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            LOG.info("订阅服务已停止")

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service = service

    @app.get("/healthz")
    async def health():
        """返回订阅就绪状态，不返回密钥与日历内容。"""
        stale = any(datetime.now(timezone.utc) - updated > timedelta(seconds=settings.interval * 2) for updated in service.last_success.values())
        ready = len(service.feeds) == len(service.sources) and len(service.last_success) == len(service.sources) and not service.errors and not stale
        return Response(json.dumps({"status": "ok" if ready else "degraded", "feeds": len(service.feeds)}), status_code=200 if ready else 503, media_type="application/json")

    @app.get("/{token}/{slug}.ics")
    async def feed(token: str, slug: str, request: Request):
        """功能：提供订阅快照。参数：token 为订阅密钥，slug 为日历标识，request 为 HTTP 请求。返回值：ICS 或缓存响应。"""
        if not hmac.compare_digest(token.encode(), settings.feed_token.encode()):
            raise HTTPException(404)
        if slug not in {source["slug"] for source in service.sources}:
            raise HTTPException(404)
        if slug not in service.feeds:
            raise HTTPException(503, "日历正在初始化，请稍后重试", headers={"Retry-After": "60"})
        payload = service.feeds[slug]
        etag = '"' + hashlib.sha256(payload).hexdigest() + '"'
        headers = {"ETag": etag, "Cache-Control": "private, max-age=60", "Content-Disposition": f'inline; filename="{slug}.ics"'}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(payload, media_type="text/calendar; charset=utf-8", headers=headers)

    return app
