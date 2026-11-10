# 项目结构与使用说明

项目采用一个代码仓库，API、任务进程、Web、数据库初始化和部署配置统一维护。

| 目录 | 职责 |
| --- | --- |
| `apps/api` | FastAPI、权限、审核、SSO、上传存储、ARQ 任务及 API 测试 |
| `apps/web` | Next.js 页面、Markdown/Tiptap 编辑器、后台管理及前端测试 |
| `docker` | 网关与镜像构建配置 |
| `docs` | 功能、企业登录、存储和部署说明 |
| `.env.example` | 配置模板；实际 `.env` 不进入版本控制 |

## 社区功能

- 首页轮播图、公告卡片、滚动加载；栏目页显示公告，帖子详情使用更宽的正文区域。
- Markdown / Tiptap 双模式编辑；富文本支持全屏、编辑/预览/分屏、表格、图片、视频和附件。
- 作者或超级管理员可以编辑已发布或被拒绝且未锁定的帖子；保存前进行审核，版本冲突返回 409，保留用户输入供重新处理。编辑不创建新帖子，也不重复触发自动回帖；保留已有的人工处理标记。媒体上传完成前，发帖、回复及保存修改均不可提交。
- 帖子分享支持复制链接和分享文案；HTTP 环境或剪贴板权限被拒绝时提供选择复制的回退方式。
- 上传大小可在后台配置到 500 MiB；保留分块上传、视频文件头验证、存储后端和字节范围下载。
- 登录标题、副标题和 SSO 按钮文案沿用后台配置；自动 SSO 默认关闭，可由超级管理员开启。
- SSO 失败回到登录页；`/login?local=1` 始终提供手动账号登录入口。自动跳转每个浏览器标签页最多尝试一次。
- 个人中心可编辑昵称、可编辑的员工字段及密码。员工信息未成功加载时禁止保存，避免把未读取的数据覆盖为空值。
- 审计日志支持每页 20 条、操作名称筛选和页码跳转；审计时间统一显示为北京时间，并保留秒数。

保留仓库原有的通用 SDK 页面、资讯、向量检索和奖励行为。本次整合不内置客户专用 HiAgent 配置、客户地址或 AppKey，也不加入栏目标签及其他本地额外改动。

## 本地启动

需要 Node.js 22.6+、Python 3.12、PostgreSQL 和 Redis。数据库和 Redis 应先按已有部署说明准备好；启动 API 会执行项目原有的初始化及幂等迁移。

在项目根目录创建虚拟环境、安装 API 依赖，并复制 `.env.example` 为 `.env`。配置数据库、Redis 和随机生成的 JWT/AES/MCP 密钥。开发时将 `PUBLIC_BASE_URL` 设置为浏览器实际使用的地址，例如 `http://localhost:3000`。

PowerShell 示例：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r apps/api/requirements.txt
Copy-Item .env.example .env
$env:PYTHONPATH = "$PWD/apps/api"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

在另一个终端进入 `apps/web`，运行 `npm ci`、`npm run dev`。需要审核和自动回帖时，在项目根目录以相同 `.env` 和 `PYTHONPATH` 运行 `.venv/Scripts/arq.exe app.tasks.worker.WorkerSettings`。Linux 使用 `.venv/bin` 中对应命令。容器部署继续使用根目录 Compose 配置与原有部署文档。

## SSO 的公开地址

`PUBLIC_BASE_URL` 是默认的公开访问地址。需要通过其他域名、协议或端口完成登录时，把完整且可信的来源加入 `PUBLIC_ALLOWED_ORIGINS`，用逗号分隔，例如 `https://community.example,http://localhost:3000`。

回调地址由同一个已验证的来源生成，并在授权请求、令牌交换和登录完成时保持一致。未列入配置的 Host 回退到 `PUBLIC_BASE_URL`，不会成为令牌重定向目标。反向代理必须覆盖 Host 和 X-Forwarded-Proto；项目内置 Nginx 使用 `$http_host` 保留端口。X-Forwarded-Host 不作为来源依据。身份提供方也需要登记对应的精确回调地址。

## 验证

在 `apps/api` 中运行：

```text
python -m unittest discover -s tests -v
python -m compileall -q app tests
```

代理回归需要本地 Nginx，可用 `NGINX_BINARY` 指定可执行文件；它只启动临时回环端口并在结束时关闭。未提供 Nginx 时，该用例会跳过。

数据库持久化测试需要独立的可丢弃 PostgreSQL，通过 `RUN_DATABASE_TESTS=1` 启用，不能指向生产数据库。

在 `apps/web` 中运行：

```text
npm ci
npm test
npx tsc --noEmit --incremental false
npm run build
npm audit
```

浏览器回归使用本地 Web 服务和模拟 API，不连接客户身份提供方、生产数据或模型服务。另起终端启动 `npm run dev -- --port 3063`，设置 `TEST_BASE_URL=http://127.0.0.1:3063` 后运行 `npm run test:browser`。Windows 默认使用已安装的 Edge；其他系统可安装 Playwright Chromium，并设置 `TEST_BROWSER=chromium`。

前端锁定 Next.js 15.5.29；以 npm override 将 Next.js 使用的 PostCSS 固定到 8.5.32。更新这两个版本后应重新执行完整构建、浏览器回归和依赖审计。
