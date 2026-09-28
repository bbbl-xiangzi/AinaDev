# AI 原生开发者社区（ai-native-community）

面向企业的 **AI 原生开发者社区**：发帖、回帖、知识库问答由 **LangGraph Agent 流水线** 自动运维（**发帖先经 AI 异步审核**，通过后才发布并触发 AI 回帖），并内置 **MCP 服务**，可接入豆包工作等智能体生态做每日运维。

- 前端：Next.js 15（App Router）+ TypeScript + Tailwind + ByteMD（Markdown 编辑器，完全本地化，无 CDN 依赖）
- 后端：FastAPI + SQLAlchemy(async) + LangGraph 流水线 + ARQ 定时任务
- 搜索：jieba 中文分词多词匹配（跨环境一致，不依赖数据库扩展）
- 向量检索：**Weaviate 独立向量库**（应用侧生成向量）/ pgvector / JSONB+余弦（自动降级）
- 部署：Docker Compose（4 容器），依赖云端 PostgreSQL / Redis /（可选）Weaviate

---

## 一、功能总览

| 模块 | 说明 |
|---|---|
| 社区论坛 | 多栏目、发帖/回帖/点赞/收藏/搜索/引用回复/置顶/精华/锁帖/问答已解决；编辑器为 ByteMD（工具栏直接插入图片/附件，完全本地化） |
| 发帖 AI 审核 | 发帖后**不直接发布**，进入「审核中」（仅作者可见）；AI 异步审核通过才公开，不通过转 `rejected` 由管理员处理（通过/删除）；审核提示词后台可配 |
| AI 原生运维 | 审核通过后才触发 AI 回帖流水线（**两次 AI 调用分开**）：路由 → RAG 检索 → 证据判定 → AI 生成回复 |
| 无证据不回复 | Judge 节点相似度低于栏目阈值（默认 0.7）绝不回帖，转人工或明确告知 |
| 全链路审计 | 每个 Agent 决策写入 `agent_runs`，后台可视化查看（含 prompt/响应/耗时/评分） |
| 知识库 RAG | 上传 PDF / DOCX / MD / TXT / URL 自动解析切片向量化，混合检索（向量+全文）；后台可下载原文档、查看切片 |
| 合规审查 | LLM 审查（提示词后台可配，默认预设覆盖政治敏感/违法/色情/暴力/人身攻击/粗口/消极/灌水/藏头诗等）+ 内置风险词表双保险；AI 异常保守转人工 |
| 人工审核 | 审核队列按类型分页签（AI 不通过/中危帖/AI 待审/举报），操作全部留痕 |
| 多角色账号 | human（普通用户）/ agent（AI 管理员，不可登录）/ system（系统账号） |
| 模型配置 | 后台可视化配置 OpenAI 兼容协议模型（通义/火山/DeepSeek/自建 vLLM），Key AES 加密存储 |
| 邀请码注册 | 管理员生成邀请码，新用户凭码注册，有效期可配 |
| 资讯与周报 | ARQ 定时任务：每日资讯抓取、每周运维周报、48h 无回复提醒、重复帖检测、僵尸帖归档 |
| 外部 Agent 回帖源 | 栏目可绑定第三方 Agent（Dify / HiAgent / OpenAI 兼容 / 自定义 HTTP 四种协议）自动回帖；外部回复同样过 AI 审核（违规+主题相关性），不通过进审核队列由管理员处理；调用失败**不回退内置 AI**，通知管理员人工回复并给出失败码/原因 |
| 栏目主题相关性 | 栏目级开关「主题相关性审核」：开启后发帖/评论与栏目主题不相关即不通过（作者可见不通过原因）；相关性判断内置 LLM 完成 |
| 楼主追问自动回复 | 栏目级开关「楼主评论自动回复」：楼主在帖子下追加评论时，内置 LLM 先判断是否为提问（闲聊如「谢谢/好的」不回复），是提问才自动回复（走外部回帖源或内置 AI 管理员） |
| 奖励体系 | 后台「奖励设置」可配置发帖/回帖/评论/点赞/阅读/每日登录等行为的 ⭐ 奖励值（支持 0.x 一位小数）；用户中心显示 ⭐ 余额与奖励明细，全部默认值已内置 |
| MCP Server | 15 个运维工具（合规审查/知识库/帖子/栏目/审核/资讯/周报/统计），HTTP Streamable 协议 |

---

## 二、系统架构

```
                        ┌─────────────────────────────────────────────┐
   浏览器 / 豆包工作     │  Docker Compose（单机 4 容器）               │
   (MCP 客户端)         │                                             │
        │               │  ┌─────────┐   /api/    ┌──────────────┐   │
        │  http(s)      │  │  nginx  │───────────▶│  api(FastAPI)│   │
        └───────────────┼─▶│  8090:80│   /mcp     │  :8000       │   │
                        │  │         │───────────▶│  ┌──────────┐│   │
                        │  └────┬────┘   /        │  │ MCP 服务 ││   │
                        │       │                │  └──────────┘│   │
                        │       │                └──────┬───────┘   │
                        │       │                       │ 事件      │
                        │  ┌────▼────┐              ┌───▼────────┐  │
                        │  │  web    │              │ worker(ARQ)│  │
                        │  │Next.js  │              │ :8000      │  │
                        │  │ :3000   │              └─────┬──────┘  │
                        │  └─────────┘                    │         │
                        └────────────────────────────────┼─────────┘
                                                         │
                          ┌──────────────────────────────┼──────────────┐
                          │ 外部依赖（云端，部署时提供）   ▼              │
                          │  ┌──────────────┐   ┌────────────────────┐  │
                          │  │ PostgreSQL   │   │ Redis（ARQ 队列/   │  │
                          │  │ (业务数据)    │   │  定时任务/缓存)     │  │
                          │  └──────────────┘   └────────────────────┘  │
                          │  ┌──────────────┐                           │
                          │  │ Weaviate     │ ← 向量库（可选，           │
                          │  │ (向量检索)    │   vector_backend=weaviate）│
                          │  └──────────────┘                           │
                          └─────────────────────────────────────────────┘
```

**向量检索后端**：`.env` 中 `VECTOR_BACKEND` 三选一（默认 `numpy` 自动降级，无需任何外部服务）：
- `weaviate`：接入独立 Weaviate 实例（应用侧生成向量后写入，`vectorizer=NONE`），适合知识库规模大、多服务共享的场景
- `pgvector`：PostgreSQL 扩展向量检索（需数据库已装 `vector` 扩展）
- `numpy`：向量存 JSONB，应用层余弦检索（零依赖，小规模开箱即用）

**容器清单**

| 容器 | 镜像 | 端口 | 职责 |
|---|---|---|---|
| `community-nginx` | nginx:1.27-alpine | **8090 → 80**（对外） | 反代 web / api / mcp / uploads |
| `community-api` | 本地构建 | 8000（内网） | FastAPI：REST API + MCP Server |
| `community-web` | 本地构建 | 3000（内网） | Next.js 生产构建 |
| `community-worker` | 本地构建 | - | ARQ 异步任务 + 定时任务（消费流水线事件） |

---

## 三、技术栈

- **后端**：Python 3.12+ · FastAPI · SQLAlchemy 2 (async) · psycopg · LangGraph · fastmcp · ARQ · pydantic v2 · jieba（中文分词搜索）· weaviate-client
- **前端**：Next.js 15 · React 19 · TypeScript · Tailwind CSS · ByteMD（编辑器，npm 本地打包，无 CDN 依赖）
- **数据**：PostgreSQL 14+（可选 pgvector）· Redis 6+ · （可选）Weaviate
- **LLM**：OpenAI 兼容协议（通义千问 DashScope / 火山方舟 / DeepSeek / OpenAI / 自建 vLLM / Ollama 均可）

---

## 四、部署前准备

1. **一台 Linux 服务器**（Ubuntu 22.04+ / Debian 12+ 推荐），已装 Docker 与 Docker Compose v2：

   ```bash
   docker --version          # 建议 24+
   docker compose version    # 建议 2.20+
   ```

2. **云端 PostgreSQL**：创建数据库与账号，记录连接串。

3. **云端 Redis**：创建实例，记录地址与密码（用于 ARQ 任务队列）。

4. **（可选）Weaviate 向量库**：如需独立向量检索，准备 Weaviate 实例（HTTP/gRPC 地址、集合名；向量由应用生成，`vectorizer` 保持 `none`）。不准备则用默认 JSONB 余弦检索，开箱即用。

5. **LLM API Key**：任选 OpenAI 兼容服务商（推荐通义千问 / 火山方舟）。部署后通过后台「模型配置」页配置，**不会写入代码或明文存储**。

6. **安全组放行端口**：对外访问端口（默认 **8090**）需在云安全组放行。若 80 端口空闲，可改为 80。

---

## 五、快速部署（生产）

### 第 1 步：获取代码

```bash
git clone https://github.com/stepll2026/AinaDev.git ai-native-community
cd ai-native-community
```

### 第 2 步：配置环境变量

```bash
cp .env.example .env
vim .env   # 按下方表格填写
```

**必填项**：

| 变量 | 说明 | 示例 |
|---|---|---|
| `PUBLIC_BASE_URL` | 公网访问地址（MCP 与通知链接使用） | `http://192.168.1.100:8090` |
| `DATABASE_URL` | PostgreSQL 异步连接串 | `postgresql+psycopg://user:pass@<db-host>:5432/community` |
| `REDIS_URL` | Redis 连接串 | `redis://:pass@<redis-host>:6379/0` |
| `JWT_SECRET` | 随机 32 字节 hex：`openssl rand -hex 32` | |
| `AES_KEY` | AES-256 密钥（32 字节 hex）：`openssl rand -hex 32`，用于加密模型 API Key | |
| `MCP_API_KEY` | MCP 访问令牌（豆包工作配置时填 Bearer） | |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | 初始超管（首次启动自动创建；未配置时自动生成随机密码并打印到日志） | |

**可选项**：`SITE_NAME`、`SITE_DESCRIPTION`、`INVITE_EXPIRE_DAYS`、`SMTP_*`（邮件通知）、`DEFAULT_LLM_*`（默认模型，首次启动写入库，之后后台可改）、`VECTOR_BACKEND`（`numpy`/`pgvector`/`weaviate`，默认 `numpy`）、`WEAVIATE_HOST`/`WEAVIATE_HTTP_PORT`/`WEAVIATE_GRPC_PORT`/`WEAVIATE_COLLECTION`（使用 Weaviate 时填写）。

### 第 3 步：启动

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

- 首次启动自动建表 + 写入默认栏目与种子数据
- 可选：初始化演示数据（3 个演示用户 + 3 篇知识库文档 + 10 篇帖子 + 互动），需先配置好模型 Key 与 AI 管理员：
  ```bash
  docker compose -f docker-compose.prod.yml exec api python seed_demo_data.py
  docker compose -f docker-compose.prod.yml exec api python seed_demo_data2.py
  ```
  > 脚本超管密码默认从环境变量 `ADMIN_PASSWORD` 读取（缺省仅限本地演示，生产勿用）。
- 若 80 端口被占用，编辑 `docker-compose.prod.yml`，把 `8090:80` 改成其他端口（如 `8080:80`），并同步修改 `.env` 的 `PUBLIC_BASE_URL`

### 第 4 步：验证

```bash
curl http://<服务器IP>:8090/api/health
# {"status":"ok","site":"AI 开发者社区","mcp_endpoint":"http://<IP>:8090/mcp"}
```

浏览器打开 `http://<服务器IP>:8090`，用 `ADMIN_EMAIL/ADMIN_PASSWORD` 登录（首次登录后建议立即修改密码）。

---

## 六、初始化配置（上线必做）

登录超管后，按顺序完成：

1. **「模型配置」菜单** → 点击「+ 新建模型配置」→ 选模板「通义千问 DashScope」→ 填入 API Key → 保存 → 点「测试连接」确认 `OK` → 设为默认。AI 审核、AI 回帖与知识库向量化均使用默认配置。
2. **「栏目」菜单** → 为各栏目配置 AI 管理员（persona 名称、系统提示词、所属模型、回帖阈值）→ 确认「自动回帖」开启；「绑定管理员」弹窗中搜索并勾选人工管理员。
3. **「知识库」菜单** → 选择栏目 → 上传产品文档 / FAQ / 运维手册（PDF、DOCX、MD、TXT）或添加网页 URL。等待状态变为 `ready`；列表可「下载」原文档、「切片」查看向量切片。
4. **「用户」菜单** → 生成邀请码分发给员工注册。
5. **「设置」菜单** → 核对站点名称、MCP 令牌、附件上传限制（允许格式、单文件大小）；按需编辑 **AI 内容审核提示词**（默认预设已覆盖常见违规类型）。
6. **「审核」菜单** → 处理 AI 审核不通过的帖子（可「通过并发布」或「删除」）与中危帖/举报。
7. **「奖励设置」菜单** → 核对默认奖励配置（发帖/回帖/评论/点赞/阅读/每日登录等 ⭐ 数值，支持一位小数）；用户中心「我的」页展示 ⭐ 余额与奖励明细。

> 知识库文档上传后自动切片向量化；更换 embedding 模型后请在知识库列表点「重建」重新向量化（Weaviate 后端会自动清空旧向量重写）。

---

## 七、AI 原生流水线

**发帖 = 两次独立的 AI 调用**：

```
【第一次：内容审核】（发帖后立即异步执行）
发帖 → pending_review（仅作者可见）
  → AI 审核（提示词后台可配，默认覆盖：政治敏感/违法/色情/暴力/人身攻击/粗口/消极/灌水/藏头诗等）
  → 通过(low)  → published（公开）
  → 不通过 / AI 异常 / 输出非法 → rejected（仅作者+管理员可见，管理员后台可「通过并发布」或「删除」）

【第二次：AI 回帖】（仅审核通过后触发）
published → ① Route 路由 → ② Retrieve RAG 检索 → ③ Judge 证据判定 → ④ Generate 生成回复 → ⑤ Postprocess 后处理
```

**第二次调用的流水线节点**（LangGraph 拓扑，worker 异步执行，全决策落 `agent_runs`）：

```
① Route 路由（栏目自动回帖开关 + AI 管理员是否存在 + 是否 @AI）
② Retrieve RAG 混合检索（仅本栏目知识库命名空间，向量 + 全文）
③ Judge 证据判定（top1 相似度 < 栏目阈值 0.7 → 无证据不回帖，通知补文档）
④ Generate 生成回复（硬约束：只使用证据回答，末尾 [1][2] 标注来源；证据不足只输出 NO_ANSWER）
⑤ Postprocess 后处理（LLM 自检置信度 < 0.6 → 转人工复核；自动打标签；重复帖检测；通知订阅者）
```

**外部 Agent 回帖源（栏目级）**：后台「外部 Agent」菜单创建第三方回帖源（Dify Chatflow / Dify Workflow / OpenAI 兼容 / 自定义 HTTP，可填 Key 与响应路径）→ 「栏目」编辑中绑定并开启「自动回帖」。新帖发布后自动调用外部 Agent 生成回复；回复先过 AI 审核（违规 + 主题相关性），通过则发布，不通过进审核队列并通知栏目管理员；调用失败不回退内置 AI，通知管理员人工回复（含失败码/原因）。**未绑定外部源的栏目仍走内置 AI 管理员流水线。**

**楼主追问自动回复（栏目级）**：开启「楼主评论自动回复」后，楼主在帖子下追加评论时先用内置 LLM 判断是否提问（闲聊不回复），是提问则自动回复（优先走栏目绑定的外部源，否则走内置 AI 管理员）。

**审核提示词配置**：后台「设置」页可编辑 AI 审核提示词（含默认预设，修改立即生效）；「审核」页按类型分页签处理队列（AI 审核不通过 / 中危帖 / AI 回复待审 / 用户举报）。

**阈值可配置**：栏目级 `reply_threshold`（回帖相似度阈值）、AI 管理员级 `self_review_threshold`（自检置信度），后台均可调整。

---

## 八、MCP 服务接入（豆包工作 / 任意 MCP 客户端）

1. 登录超管 → 「总览」菜单 → 复制 **MCP 接入信息**：URL 与 Authorization 令牌。
2. 在豆包工作中添加 MCP 服务器：
   - **URL**：`http://<服务器IP>:8090/mcp`（注意尾部 `/`）
   - **传输**：HTTP（Streamable）
   - **Headers**：`Authorization: Bearer <MCP_API_KEY>`
3. 连接成功后可调用 15 个工具：合规审查、知识库检索、帖子/栏目管理、审核处置、用户/邀请码、每日资讯、周报生成、系统统计等，实现每日自动化运维。

---

## 九、运维与升级

**常用命令**

```bash
docker compose -f docker-compose.prod.yml ps            # 状态
docker compose -f docker-compose.prod.yml logs -f api   # 后端日志
docker compose -f docker-compose.prod.yml logs -f worker # 任务日志
docker compose -f docker-compose.prod.yml restart api   # 重启
```

**升级**

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

**数据备份**：备份 PostgreSQL（`pg_dump`）与 Redis；上传文件在 `uploads` 卷（`docker volume ls` 查看 `ai-native-community_uploads`）。

---

## 十、常见问题

| 问题 | 处理 |
|---|---|
| 外网访问超时 | 云安全组放行对外端口（默认 8090） |
| 80 端口被占用 | 修改 compose 端口映射与 `PUBLIC_BASE_URL` |
| 发帖一直「审核中」 | ① 模型配置是否已填 Key 并设为默认（审核调用 LLM）② 查看 worker 日志与「Agent 执行记录」 |
| 帖子被误判审核不通过 | 后台「审核」菜单 → AI 不通过分页 → 「通过并发布」；或到「设置」菜单调整审核提示词 |
| AI 不回复 | ① 模型配置是否已填 Key 并设为默认 ② 栏目是否配置 AI 管理员并开启自动回帖 ③ 知识库是否有相关证据（检索阈值）④ 查看「Agent 执行记录」定位 |
| 搜索不到中文帖子 | 搜索基于 jieba 分词多词匹配，输入完整关键词；标题/正文包含所有分词才命中（`AND` 语义） |
| 知识库文档 failed | 查看错误信息；模型 Key 是否正确；文档是否可解析；换模型后记得「重建」 |
| 更换模型 | 后台「模型配置」新增/编辑并测试连接 → 设为默认 → 知识库「重建」索引 |
| 使用 Weaviate 后检索为空 | 确认 `.env` 的 `VECTOR_BACKEND=weaviate` 与 Weaviate 地址/集合名正确；上传文档后状态 `ready`；旧文档需点「重建」写入向量 |
| 修改 MCP 令牌 | 后台「设置」修改后，同步更新豆包工作中的配置 |

---

## 十一、本地开发

```bash
# 后端（Python 3.12+）
cd apps/api
python -m venv .venv && .venv\Scripts\activate   # Windows；Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 配置数据库 / Redis
python run.py          # http://localhost:8000

# 前端
cd apps/web
npm install
npm run dev            # http://localhost:3000

# 本地起数据库（可选）：docker compose up -d db redis
```

> Windows 注意：项目已内置 SelectorEventLoop 适配，解决 psycopg async 与 Proactor 的兼容问题。

---

## 十二、目录结构

```
├── apps/
│   ├── api/                    # FastAPI 后端
│   │   ├── app/
│   │   │   ├── api/            # REST 路由（auth/posts/categories/admin_*/uploads…）
│   │   │   ├── agent/          # LangGraph 流水线（runner + nodes）
│   │   │   ├── models/         # SQLAlchemy 模型（users/posts/categories/rag/agent/external/tickets/system）
│   │   │   ├── schemas/        # Pydantic 模型
│   │   │   ├── services/       # LLM/RAG/Weaviate/合规/审计/通知/运维/资讯/文档/后处理
│   │   │   ├── tasks/          # ARQ worker + 定时任务（含发帖审核 review_tasks）
│   │   │   └── mcp/            # MCP Server（15 工具）
│   │   ├── run.py              # 启动入口（含 Windows 事件循环适配）
│   │   └── requirements.txt
│   └── web/                    # Next.js 15 前端
│       ├── app/                # 页面路由（首页/发帖/帖子/栏目/搜索/个人/后台）
│       ├── components/         # 组件（ByteMD 编辑器、后台各管理面板、模态弹窗）
│       └── lib/                # API 客户端 / 鉴权
├── docker/
│   ├── nginx/nginx.conf        # 反代 /api /mcp /uploads
│   └── postgres/               # 本地开发数据库初始化
├── docker-compose.yml          # 本地开发（内置 db/redis）
├── docker-compose.prod.yml     # 生产（外部云端 PG/Redis）
├── .env.example                # 环境变量模板（脱敏）
└── README.md
```
