# lark-cal-sync

使用 uv 和 Python 将飞书日历发布为 ICS 订阅，供小米等支持 URL 订阅的日历客户端读取。

服务每 30 分钟刷新一次，并持久化最后一次成功的快照。项目当前配置的日历源为 KK 假期。

## 本地运行

```sh
uv sync --locked
cp .env.example .env
uv run python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

已有 `.env` 时直接补齐配置。填写 `FEISHU_APP_ID`、`FEISHU_APP_SECRET` 和随机生成的 `FEED_TOKEN`。飞书应用需开通应用身份权限 `calendar:calendar:readonly`，并获得源日历的 `reader`、`writer` 或 `owner` 权限。

```sh
uv run lark-cal-sync sync
uv run lark-cal-sync serve
```

`sync` 执行一次刷新，失败返回非零退出码。`serve` 启动后台刷新与 HTTP 服务，默认监听 `127.0.0.1:8000`。

也支持通过 `uv run python -m lark_cal_sync` 运行。

订阅地址：`http://127.0.0.1:8000/<FEED_TOKEN>/holidays.ics`。

## 日历源与配置

通过 `.env` 中的 `FEISHU_CALENDARS` JSON 数组管理日历源，每项需要 `slug`、`name` 和 `calendar_id`。`slug` 唯一，由小写字母、数字和短横线组成。源配置变更后重启服务。

| 环境变量 | 默认值 | 作用 |
| --- | --- | --- |
| `SYNC_INTERVAL_SECONDS` | `1800` | 刷新间隔，至少 60 秒 |
| `SYNC_PAST_DAYS` | `30` | 历史同步天数 |
| `SYNC_FUTURE_DAYS` | `365` | 未来同步天数 |
| `CALENDAR_TIMEZONE` | `Asia/Shanghai` | 日期范围计算时区 |
| `FEISHU_CALENDARS` | 必填 | 日历源 JSON 数组 |
| `DATA_DIR` | `data` | 快照目录 |

服务按 30 天窗口读取展开的日程实例，包含重复日程和例外调整。ICS 使用稳定 UID，全天日程保持日期语义，定时日程使用 UTC 时间。每轮成功后整体替换快照，原日程的修改和取消随客户端重新读取生效。快照只包含配置范围内的日程。

接口故障、权限不足或日程标题缺失时保留该日历上次成功的数据。首次同步完成前返回 HTTP 503。各日历独立刷新。

`/healthz` 在所有日历刷新成功且快照未超过两倍刷新间隔时返回 HTTP 200，否则返回 HTTP 503。失败期间仍可读取已有快照。

## 项目结构

```text
src/lark_cal_sync/
  __main__.py      模块运行入口
  cli.py           命令行入口
  config.py        配置加载与校验
  feishu.py        飞书 API 客户端
  calendar.py      ICS 生成
  sync.py          定时同步与快照管理
  server.py        订阅接口与健康检查
```

部署使用 GitHub Actions、GHCR 和 Traefik，完整步骤见 [部署说明](docs/deployment.md)。
