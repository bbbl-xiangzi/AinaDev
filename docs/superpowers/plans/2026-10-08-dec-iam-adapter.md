# 东方电气 IAM 适配服务 Implementation Plan

> Execute inline with superpowers:executing-plans; review with a fresh reviewer before delivery.

**Goal:** 交付可配置、独立部署并能与社区连接的 IAM→OIDC 适配服务。

**Architecture:** `adapters/dec-iam/dec_iam` 包独立运行；Redis 存储短期事务，IAM HTTP 客户端隔离上游协议，OIDC 路由签发下游身份。社区只修改连接所必需的客户端行为。

**Tech Stack:** Python 3.12、FastAPI、httpx、PyJWT/cryptography、Redis 7；现有 Next.js 社区。

**Spec:** `docs/superpowers/specs/2026-10-08-dec-iam-adapter.md`

## Global Constraints

严格单值 spRoleList；仅 authorization_code + PKCE S256；RS256；state 600 秒、code 60 秒、token 300 秒；固定回调和 HTTPS；不记录敏感参数；不触碰线上配置。

## Review Focus

- 错误客户端或 callback 不得获得 IAM 跳转或 Token。
- 浏览器 Cookie 缺失、state/code 重放和过期必须拒绝。
- IAM 业务错误即使 HTTP 200 也拒绝；userinfo 非字典不得通过。
- 原始身份数据、query secret 不得进入日志或下游响应。
- 配置初始化重复执行不得覆盖现有私钥和凭据。

## Task 1 独立协议桥接

Files: `adapters/dec-iam/dec_iam/{config,iam,store,app}.py`，`tests/test_adapter.py`。
Interface: `create_app(settings, store=None, iam_transport=None)`；store 提供 put/get/pop/delete；IAM 返回标准化最小用户声明。

- [x] 写登录闭环与拒绝场景测试，运行确认缺少实现。
- [x] 实现固定客户端配置、上游调用、原子事务和 OIDC 路由。
- [x] 执行全部适配服务测试并检查错误信息不含敏感数据。

## Task 2 可部署配置器

Files: adapter Dockerfile、compose.yml、requirements、初始化脚本、README。

- [x] 写初始化生成及拒绝覆盖测试。
- [x] 实现交互式/非交互配置生成，生成独立 client secret 和 RSA 私钥、社区配置 JSON。
- [x] 编写 TLS 网关、CA、网络、社区配置、GLO 限制与联调清单，验证配置可加载。

## Task 3 社区连接

Files: API sso_service/config/auth_sso，web auth/sso helpers，相关测试。

- [x] 写 issuer/aud、私网允许名单、前端登录结果验证测试，观察失败。
- [x] 实现严格验证及内网精确允许名单，接收 fragment 后清除地址栏、向 /auth/me 验证再保存会话；提供仅 SSO 会话使用的可选退出跳转。
- [x] 全部测试、编译和前端类型检查；独立评审、修正，保留真实 IAM 与 Docker 未验证事项。

## 验证记录（2026-10-08）

- 适配器及配置器 20 项、社区 API 12 项、前端登录辅助逻辑 5 项测试通过。
- TypeScript 检查及 Next.js 生产构建通过。恢复了原项目缺失、导致构建失败的 Avatar/TimeAgo 导出，实现取自仓库历史。
- 独立评审的两个问题均补充失败回归测试后修复：已有密钥目录权限未收紧，以及完整显式端点仍被强制请求 Discovery。
- 未运行 Docker（本机无 Docker），未连接客户真实 IAM；模拟测试不能代替现场登录、CA/网络及 GLO 验收。
- 安装依赖时现有 Next.js 15.1.6 报安全警告；本次未升级框架，生产部署前需单独升级验证。
