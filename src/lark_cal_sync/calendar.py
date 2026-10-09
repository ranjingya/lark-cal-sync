"""ICS 日历格式生成。"""

import hashlib
from datetime import date, datetime, timezone

from icalendar import Calendar, Event


def event_time(value):
    """将飞书的全天日期或时间戳转换为 ICS 时间。"""
    if value.get("date"):
        return date.fromisoformat(value["date"])
    return datetime.fromtimestamp(int(value["timestamp"]), timezone.utc)


def render_calendar(source, events, now):
    """功能：生成 ICS。参数：source 为日历配置，events 为展开的实例，now 为生成时间。返回值：ICS 字节。"""
    calendar = Calendar()
    calendar.add("prodid", "-//lark-cal-sync//ZH")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("x-wr-calname", source["name"])
    calendar.add("name", source["name"])
    for item in sorted(events, key=lambda e: (str(event_time(e["start_time"])), e["event_id"])):
        event = Event()
        start = event_time(item["start_time"])
        end = event_time(item["end_time"])
        if type(start) is not type(end) or end <= start:
            raise ValueError("日程起止时间无效")
        identity = source["calendar_id"] + ":" + item["event_id"] + ":" + start.isoformat()
        event.add("uid", hashlib.sha256(identity.encode()).hexdigest() + "@lark-cal-sync")
        event.add("dtstamp", now)
        event.add("dtstart", start)
        # 飞书接口的全天结束日期与 ICS 一致，均为不包含的结束边界。
        event.add("dtend", end)
        event.add("summary", item["summary"])
        if item.get("description"):
            event.add("description", item["description"])
        location = item.get("location") or {}
        if location.get("name"):
            event.add("location", location["name"])
        event.add("transp", "TRANSPARENT" if item.get("free_busy_status") == "free" else "OPAQUE")
        event.add("status", "CONFIRMED")
        calendar.add_component(event)
    return calendar.to_ical()
