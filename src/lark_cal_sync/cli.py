"""命令行启动与单次同步入口。"""

import argparse
import asyncio
import logging

import httpx
import uvicorn

from .config import Settings
from .feishu import FeishuClient
from .server import create_app
from .sync import SyncService


def main():
    """功能：执行单次同步或启动服务。参数：无，命令行指定模式与监听地址。返回值：无，失败时非零退出。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description="飞书日历 ICS 订阅服务")
    parser.add_argument("command", choices=["serve", "sync"], nargs="?", default="serve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    settings = Settings.load()
    if args.command == "sync":
        async def once():
            """执行一次刷新并返回成功状态。"""
            async with httpx.AsyncClient(timeout=30) as transport:
                return await SyncService(settings).refresh(FeishuClient(settings, transport))
        raise SystemExit(0 if asyncio.run(once()) else 1)
    uvicorn.run(create_app(settings), host=args.host, port=args.port, access_log=False)
