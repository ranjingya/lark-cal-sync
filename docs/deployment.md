# 部署与运维

服务通过 GHCR 镜像运行，Traefik 提供 HTTPS 入口。域名为 `lark-cal.skills.kktree.cn`，外部 Docker 网络为 `traefik-network`，入口为 `websecure`，证书解析器为 `myresolver`。服务在 Docker 网络中开放 8000 端口。

## 服务器准备

建议部署目录为 `/home/yatui/lark-cal-sync`：

```text
.env
docker-compose.yaml
```

- 手动维护：`.env`，填写飞书凭证、各日历的 ID、名称与订阅标识、随机订阅密钥和运行配置，文件权限设为 `600`。
- GitHub Actions 同步：`docker-compose.yaml`。
- 运行时保存：`calendar-data` 命名卷中的订阅快照。

服务器需安装 Docker Compose，并运行已连接 `traefik-network` 的 Traefik。域名 DNS 指向服务器，Traefik 配置 `websecure` 与 `myresolver`。域名、网络和证书解析器可通过 `.env.example` 中的变量调整。

## GitHub Actions 配置

将项目推送到 `ranjingya/lark-cal-sync`。在仓库 Settings → Secrets and variables → Actions 配置：

| 类型 | 名称 | 内容 |
| --- | --- | --- |
| Secret | `SSH_HOST` | 服务器地址 |
| Secret | `SSH_PORT` | SSH 端口 |
| Secret | `SSH_USER` | 具备 Docker 操作权限的部署用户 |
| Secret | `SSH_PRIVATE_KEY` | SSH 私钥 |
| Secret，可选 | `SSH_PRIVATE_KEY_PASSPHRASE` | 私钥口令 |
| Variable | `DEPLOY_DIR` | 服务器项目绝对路径 |

`GITHUB_TOKEN` 由 GitHub 自动提供，用于推送镜像及部署时登录 GHCR。SSH 凭证需要在当前仓库或对应组织范围内可用。

## 发布

推送 `v*` 标签后工作流构建镜像并部署，也支持在 Actions 页面手动运行 CD。

```sh
git tag v0.1.0
git push origin v0.1.0
```

镜像地址为 `ghcr.io/ranjingya/lark-cal-sync`，具有 `latest` 和版本标签；手动构建使用 `manual-<提交短 ID>` 标签。服务器拉取 `latest` 并更新服务。

部署完成表示容器启动命令执行成功；健康状态需要通过下列运维命令确认。

## 运维

在服务器部署目录执行：

```sh
docker compose ps
docker compose logs --tail=100 lark-cal-sync
docker compose pull lark-cal-sync
docker compose up -d --remove-orphans lark-cal-sync
```

HTTPS 健康检查地址：`https://lark-cal.skills.kktree.cn/healthz`。

订阅快照保存在命名卷中。服务每 30 分钟读取飞书，手机自身的拉取间隔也会影响更新延迟。

## 小米日历

在“添加 URL 订阅”中填写：

```text
https://lark-cal.skills.kktree.cn/<FEED_TOKEN>/holidays.ics
```

将 `<FEED_TOKEN>` 替换为服务器 `.env` 中的值。手机无需填写飞书应用凭证。

订阅密钥位于 URL 中，持有完整地址的人可读取日历。服务关闭访问日志；Traefik 的访问日志也应关闭或隐藏订阅路径。支持按路由关闭访问日志的 Traefik 版本可设置 `traefik.http.routers.lark-cal-sync.observability.accesslogs=false`。更换 `FEED_TOKEN` 并重建容器可撤销已有订阅地址。
