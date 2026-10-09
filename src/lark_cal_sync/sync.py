"""日历同步与快照管理。"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from icalendar import Calendar

from .calendar import render_calendar
from .feishu import FeishuClient

LOG = logging.getLogger(__name__)


class SyncService:
    """管理订阅快照、定时刷新与失败降级。"""

    def __init__(self, settings):
        self.settings = settings
        self.sources = settings.calendars
        self.feeds = {}
        self.last_success = {}
        self.errors = set()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        for source in self.sources:
            slug = source["slug"]
            path = settings.data_dir / (slug + ".ics")
            if path.exists():
                try:
                    payload = path.read_bytes()
                    Calendar.from_ical(payload)
                    self.feeds[slug] = payload
                    self.last_success[slug] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
                    LOG.info("加载订阅快照：%s", slug)
                except Exception:
                    LOG.warning("订阅快照无效：%s", slug)

    async def refresh(self, client):
        """功能：刷新所有日历。参数：client 为飞书客户端。返回值：全部日历是否刷新成功。"""
        now = datetime.now(timezone.utc)
        today = now.astimezone(ZoneInfo(self.settings.timezone_name)).replace(hour=0, minute=0, second=0, microsecond=0)
        start = today - timedelta(days=self.settings.past_days)
        end = today + timedelta(days=self.settings.future_days)
        LOG.info("开始刷新 %d 个日历", len(self.sources))
        for source in self.sources:
            slug = source["slug"]
            try:
                events = await client.events(source["calendar_id"], start, end)
                payload = render_calendar(source, events, now)
                path = self.settings.data_dir / (slug + ".ics")
                temporary = path.with_suffix(".tmp")
                temporary.write_bytes(payload)
                temporary.replace(path)
                self.feeds[slug] = payload
                self.last_success[slug] = now
                self.errors.discard(slug)
                LOG.info("日历刷新成功：%s，%d 条日程", slug, len(events))
            except Exception as exc:
                self.errors.add(slug)
                # 不记录异常正文，避免请求地址、密钥及日程内容进入日志。
                reason = str(exc) if isinstance(exc, (RuntimeError, ValueError)) else type(exc).__name__
                LOG.error("日历刷新失败：%s，%s；保留上次快照", slug, reason)
        LOG.info("刷新结束：成功 %d，失败 %d", len(self.sources) - len(self.errors), len(self.errors))
        return not self.errors

    async def run(self):
        """功能：启动时立即刷新并执行后续调度。参数：self 为同步服务。返回值：任务取消后结束。"""
        async with httpx.AsyncClient(timeout=30) as transport:
            client = FeishuClient(self.settings, transport)
            while True:
                await self.refresh(client)
                if not self.settings.sync_times:
                    LOG.info("使用间隔同步，等待 %d 秒", self.settings.interval)
                    await asyncio.sleep(self.settings.interval)
                    continue
                target = next_sync_time(datetime.now(timezone.utc), self.settings.sync_times, self.settings.timezone_name)
                LOG.info("下次同步时间：%s", target.isoformat())
                # 定期检查墙上时钟，使系统校时后仍按配置时刻触发。
                while True:
                    remaining = (target.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds()
                    if remaining <= 0:
                        break
                    await asyncio.sleep(min(remaining, 60))


def next_sync_time(now, sync_times, timezone_name):
    """功能：计算下一次每日同步时间。参数：now 为带时区的当前时间，sync_times 为每日时间列表，timezone_name 为调度时区。返回值：严格晚于当前时刻的带时区时间。"""
    if now.tzinfo is None or not sync_times:
        raise ValueError("需要带时区的当前时间与非空同步时间列表")
    zone = ZoneInfo(timezone_name)
    today = now.astimezone(zone).date()
    for offset in range(2):
        candidates = [datetime.combine(today + timedelta(days=offset), value, zone) for value in sync_times]
        future = [value for value in candidates if value.astimezone(timezone.utc) > now.astimezone(timezone.utc)]
        if future:
            return min(future, key=lambda value: value.astimezone(timezone.utc))
    raise ValueError("无法计算下一次同步时间")
