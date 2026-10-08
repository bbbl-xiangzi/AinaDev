# 东方电气 IAM 独立适配服务

用户要求按 DECITC.BZ.0017A Word 文档实现可随社区部署的独立配置和适配服务。社区作为 OIDC 客户端，适配服务作为固定单客户端 OIDC 桥接端，东方电气 IAM 仍是唯一认证源。此版本不实现多企业入口、租户隔离或用户同步接口。

## 登录接口

- 下游提供 discovery、JWKS、authorize、token、userinfo；仅 authorization_code，RS256，PKCE S256，不提供动态客户端注册或 refresh token。
- 上游使用 `/idp/oauth2/authorize`、POST `/idp/oauth2/getToken`、GET `/idp/oauth2/getUserInfo`。按 Word 默认通过 query 传 Token 请求参数；可显式改为 form 以兼容客户现场。上游请求不跟随重定向，验证 HTTPS 证书；支持客户 CA 文件。
- 两套 client_id/secret 分开管理。IAM 回调指向适配服务 `/iam/callback`，社区回调仍指向社区 `/api/auth/sso/callback`。
- `spRoleList` 必须恰好包含一个非空字符串，否则拒绝。用户已确认严格规则。该值映射为 OIDC sub，不以邮箱替代、不下发管理员权限；默认不转发邮箱，避免现有社区按邮箱自动关联造成跨账号绑定。
- 仅输出必要字段的确定性映射，不转发全部 IAM 响应到社区或模型。ID Token 包含同一组最小化用户字段，以兼容社区当前发现端点后的回调行为。

## 安全与运行

- 精确登记一个社区回调地址；只允许 HTTPS（本地开发开关明确允许 HTTP）。禁止动态上游地址。
- state 和授权码随机生成、短期有效，在 Redis 原子消费；IAM state 额外绑定浏览器 HttpOnly/Secure/SameSite=Lax Cookie。
- 交换授权码需客户端密钥、原始 redirect_uri、PKCE verifier；验签信息为固定 issuer/client_id。返回带过期时间的 ID Token 与短期不透明访问令牌。
- 默认登录事务 600 秒、授权码 60 秒、令牌 300 秒。Redis 7 存储短期记录，不持久保存上游 access_token 或 refresh_token；私钥以文件挂载并保持稳定。
- 关闭访问日志，不记录 code、token、密钥或原始用户数据。错误响应使用固定说明。
- 提供 Dockerfile、独立 Compose、配置初始化命令及部署说明。配置/私钥不覆盖、不入库。社区仅放行管理员指定的 SSO 内网主机，保留其他出站防护。

## 社区接入

补齐 SSO 登录结果接收、必要的 OIDC issuer/audience 校验、显式内网主机允许名单，以及可选的浏览器全局退出跳转。需要上一修复 PR 的 Redis 和任务入队修复。

## 退出边界

适配服务提供应用发起的 `/logout`，浏览器跳转 Word 的 GLO，使用文档原拼写 `redirctToUrl`、`redirectToLogin=true`、`entityId`。社区先清理本地浏览器登录信息。

Word 未定义票据回收接口的 URL、参数和鉴权，也未定义完整应用退出回调载荷。不能宣称实现“门户发起的全局注销”和社区 JWT 即时撤销；这些必须在客户补充接口后完成联调。本次不暴露伪造的无鉴权会话清除接口。

## 验收

模拟完整 IAM 授权码流程并以适配服务真实私钥签发、公开 JWKS 验证 Token；覆盖空/多权限账号、错误 state/浏览器/PKCE/client/redirect、重放、过期、IAM 错误与超时。验证社区回调接收和退出辅助逻辑。实际客户联调与容器运行结果须独立说明，不能用模拟测试替代。
