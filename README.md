# Dudu 公共健康监控

这是一个无 API key、无账号凭据的静态健康展示项目，监控固定站点 `dudu.loc.cc`、`panel.dudu.loc.cc` 与 `baidu.vvpp.cc`。`scripts/check_health.py` 使用 Python 3 标准库执行：

- DNS：系统 `getaddrinfo`，分别记录 A / AAAA 与解析器标识；
- TLS：默认信任库、SNI 与证书校验，记录 UTC 到期时间和剩余天数；
- HTTP 与 HTTPS：独立 GET 检查，10 秒超时，最多跟随 3 次重定向，分别记录可达性、状态码与异常。

每一项都单独保存 `ok`、`fail` 或 `unknown`；失败、超时、异常和未测量不会被伪装成成功。错误文本会限制长度并安全 JSON 序列化。

## 自动运行与 GitHub Pages

1. 将本目录放入一个 **public GitHub repository** 的默认分支。
2. 在仓库 Settings → Pages → **Build and deployment** → Source 选择 **GitHub Actions**，使 `index.html` 能公开访问。
3. `.github/workflows/health.yml` 在 `schedule`（`0 */6 * * *`）、`workflow_dispatch` 以及任意分支 `push` 时运行。工作流使用 `configure-pages`、`upload-pages-artifact` 与 `deploy-pages`，把刚生成的 `latest.json` 与静态页面直接部署到 Pages，不依赖推送 `GITHUB_TOKEN` 触发另一个 workflow。
4. 工作流的权限是 `contents: read`、`pages: write`、`id-token: write`，并使用 `github-pages` environment；项目不创建或保存任何用户 token、账号密钥或 API key。
5. GitHub 对公共仓库的 scheduled workflows 可能在仓库超过 60 天没有活动时自动禁用；需要维护者重新启用或产生仓库活动。定时任务本身也可能因 GitHub 调度延迟而晚于计划时间。该监控不保证 Yunamo、GitHub Actions、Pages 或域名服务持续保活。

首页的“刷新数据”只重新请求带缓存破坏参数的 `latest.json`，不会发起新检测。页面会显示最近检查 UTC 时间、来源和可能延迟；DNS、TLS、HTTP、HTTPS 各项没有记录时显示“未知/未测量”。

## 本地运行

```bash
python3 scripts/check_health.py
python3 -m http.server 8000
```

然后打开 `http://localhost:8000/`。脚本固定只检查上述三个域名，不读取账号、令牌或其他 secret。`latest.json` 是一次真实执行生成的初始记录，并标注执行来源。
