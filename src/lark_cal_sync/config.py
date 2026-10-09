"""运行配置与日历源配置。"""

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
        required = ["FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEED_TOKEN"]
        missing = [key for key in required if not os.getenv(key)]
        if missing:
            raise ValueError("缺少配置：" + ", ".join(missing))
        token = os.environ["FEED_TOKEN"]
        if len(token) < 32 or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
            raise ValueError("FEED_TOKEN 必须为至少 32 位的字母、数字、下划线或短横线")
        settings = cls(
            os.environ["FEISHU_APP_ID"], os.environ["FEISHU_APP_SECRET"], token,
            load_calendars(os.environ),
            Path(os.getenv("DATA_DIR", "data")),
            int(os.getenv("SYNC_INTERVAL_SECONDS", "3600")),
            int(os.getenv("SYNC_PAST_DAYS", "30")),
            int(os.getenv("SYNC_FUTURE_DAYS", "365")),
            os.getenv("CALENDAR_TIMEZONE", "Asia/Shanghai"),
        )
        if settings.interval < 60 or settings.past_days < 0 or settings.future_days < 1:
            raise ValueError("刷新间隔至少 60 秒，历史天数非负，未来天数至少 1 天")
        ZoneInfo(settings.timezone_name)
        return settings


def load_calendars(environment):
    """功能：加载编号日历配置。参数：environment 为环境变量映射。返回值：按编号排序且通过校验的日历列表。"""
    groups = {}
    for key, value in environment.items():
        match = re.fullmatch(r"FEISHU_CALENDAR_([1-9][0-9]*)_(ID|NAME|SLUG)", key)
        if match:
            number, field = match.groups()
            groups.setdefault(int(number), {})[field] = value.strip()
    if not groups:
        raise ValueError("请填写 FEISHU_CALENDAR_1_ID、FEISHU_CALENDAR_1_NAME 和 FEISHU_CALENDAR_1_SLUG")
    sources = []
    slugs = set()
    for number, fields in sorted(groups.items()):
        missing = [field for field in ["ID", "NAME", "SLUG"] if not fields.get(field)]
        if missing:
            raise ValueError("缺少配置：" + ", ".join(f"FEISHU_CALENDAR_{number}_{field}" for field in missing))
        slug = fields["SLUG"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug) or slug in slugs:
            raise ValueError("日历 SLUG 必须唯一，且只包含小写字母、数字和短横线")
        slugs.add(slug)
        sources.append({"calendar_id": fields["ID"], "name": fields["NAME"], "slug": slug})
    return sources
