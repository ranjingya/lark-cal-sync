"""飞书日历 API 客户端。"""

import json
import logging
from datetime import datetime, timedelta, timezone

API = "https://open.feishu.cn/open-apis"
LOG = logging.getLogger(__name__)


class FeishuClient:
    """以应用身份读取飞书日历，凭证只保存在内存。"""

    def __init__(self, settings, client):
        self.settings = settings
        self.client = client
        self.token = None
        self.expires = datetime.min.replace(tzinfo=timezone.utc)

    async def request(self, method, path, **kwargs):
        """功能：发送鉴权请求。参数：method 为方法，path 为接口路径，kwargs 为请求参数。返回值：接口数据。"""
        for attempt in range(2):
            if not self.token or datetime.now(timezone.utc) >= self.expires:
                LOG.info("开始加载飞书应用凭证")
                response = await self.client.post(API + "/auth/v3/tenant_access_token/internal", json={
                    "app_id": self.settings.app_id, "app_secret": self.settings.app_secret,
                })
                response.raise_for_status()
                payload = response.json()
                if payload.get("code") != 0:
                    raise RuntimeError(f"飞书认证失败，错误码 {payload.get('code')}")
                self.token = payload["tenant_access_token"]
                self.expires = datetime.now(timezone.utc) + timedelta(seconds=max(1, payload["expire"] - 60))
                LOG.info("飞书应用认证成功")
            response = await self.client.request(method, API + path, headers={"Authorization": "Bearer " + self.token}, **kwargs)
            payload = response.json()
            if payload.get("code") in {99991663, 99991668} and attempt == 0:
                LOG.warning("应用凭证过期，重新认证")
                self.token = None
                continue
            if payload.get("code") != 0:
                raise RuntimeError(f"飞书接口失败，错误码 {payload.get('code')}")
            response.raise_for_status()
            return payload.get("data", {})
        raise RuntimeError("飞书认证重试失败")

    async def events(self, calendar_id, start, end):
        """功能：读取展开后的日程实例。参数：calendar_id 为源日历 ID，start 和 end 为查询起止时间。返回值：实例列表。"""
        path = f"/calendar/v4/calendars/{calendar_id}"
        info = await self.request("GET", path)
        if info.get("role") not in {"reader", "writer", "owner"}:
            raise RuntimeError("目标日历缺少 reader 权限，无法读取完整日程")
        events = {}
        cursor = start
        while cursor < end:
            stop = min(cursor + timedelta(days=30), end)
            data = await self.request("GET", path + "/events/instance_view", params={
                "start_time": str(int(cursor.timestamp())), "end_time": str(int(stop.timestamp())),
            })
            for item in data.get("items", []):
                if item.get("status") == "cancelled":
                    continue
                if not item.get("summary"):
                    raise RuntimeError("日程标题为空，本轮保留已有订阅数据")
                identity = (item["event_id"], json.dumps(item["start_time"], sort_keys=True))
                events[identity] = item
            cursor = stop
        return list(events.values())
