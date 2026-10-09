"""运行配置与日历源配置。"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """保存应用凭证、订阅密钥、刷新范围与文件路径。"""

    app_id: str
    app_secret: str
    feed_token: str
    calendars: list[dict]
    data_dir: Path
    interval: int
    past_days: int
    future_days: int
    timezone_name: str

    @classmethod
    def load(cls):
        """功能：加载环境配置。参数：cls 为配置类。返回值：校验后的配置对象。"""
        load_dotenv()
        required = ["FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEED_TOKEN", "FEISHU_CALENDARS"]
        missing = [key for key in required if not os.getenv(key)]
        if missing:
            raise ValueError("缺少配置：" + ", ".join(missing))
        token = os.environ["FEED_TOKEN"]
        if len(token) < 32 or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
            raise ValueError("FEED_TOKEN 必须为至少 32 位的字母、数字、下划线或短横线")
        settings = cls(
            os.environ["FEISHU_APP_ID"], os.environ["FEISHU_APP_SECRET"], token,
            load_calendars(os.environ["FEISHU_CALENDARS"]),
            Path(os.getenv("DATA_DIR", "data")),
            int(os.getenv("SYNC_INTERVAL_SECONDS", "1800")),
            int(os.getenv("SYNC_PAST_DAYS", "30")),
            int(os.getenv("SYNC_FUTURE_DAYS", "365")),
            os.getenv("CALENDAR_TIMEZONE", "Asia/Shanghai"),
        )
        if settings.interval < 60 or settings.past_days < 0 or settings.future_days < 1:
            raise ValueError("刷新间隔至少 60 秒，历史天数非负，未来天数至少 1 天")
        ZoneInfo(settings.timezone_name)
        return settings


def load_calendars(raw):
    """功能：读取日历源。参数：raw 为环境变量中的 JSON 字符串。返回值：日历配置列表。"""
    sources = json.loads(raw)
    if not isinstance(sources, list) or not sources:
        raise ValueError("日历配置必须为非空列表")
    slugs = set()
    for source in sources:
        slug = source.get("slug", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug) or slug in slugs:
            raise ValueError("日历 slug 必须唯一，且只包含小写字母、数字和短横线")
        if not source.get("calendar_id") or not source.get("name"):
            raise ValueError("每个日历需要 calendar_id 和 name")
        slugs.add(slug)
    return sources
