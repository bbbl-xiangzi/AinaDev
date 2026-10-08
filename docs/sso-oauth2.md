# OAuth2 / OIDC 企业登录配置

管理后台 → SSO 登录。本版本在项目内直接接入企业身份平台，无需独立 IAM 适配器。
仍为一套部署一条生效连接；多个企业登录入口和供应商隔离身份表需要另行扩展。

## 通用配置

- OIDC：填写 Issuer、Client ID/Secret；配置显式端点或自动发现。必须返回可验证的 ID Token，验证配置中的 Issuer、Audience、Nonce 和签名，使用 PKCE S256。
- OAuth2：填写授权地址和 Token 地址；用户信息可以单独请求或从 Token 响应读取。不要求 ID Token 或 JWKS。支持 Token GET/POST/PUT、Query/Form/JSON、请求参数或 HTTP Basic 客户端认证；用户信息支持 Bearer/Query/Form/JSON。
- 高级参数可以修改授权及 Token 请求参数名。回调仍需标准 `code` 和 `state` 参数。State 校验始终开启；OAuth2 PKCE 可根据身份平台支持情况启用。
- 用户信息路径支持点分隔的对象字段，例如 `data.user`。映射支持唯一标识、用户名、姓名、邮箱、手机；不执行自定义表达式。
- 退出地址填写完整 HTTPS URL，包括客户规定的固定参数。企业登录会话本地退出后浏览器跳转该地址。未实现身份平台主动通知注销、票据回收或社区 JWT 即时撤销。
- 用户默认普通会员，角色在社区用户管理中分配；不根据上游字段自动授予管理员权限。

唯一账号标识应长期稳定且唯一，与展示用户名不同。格式可选字符串或严格单值数组；空值、多值数组、非字符串会拒绝登录，不能随意取第一项。

“按唯一标识绑定”不再自动按同邮箱合并账号。同邮箱已存在但未绑定该身份时会拒绝，需管理员处理；按邮箱绑定仅适用于客户保证邮箱可信的情况。替换身份平台或更改主键映射前，应核对既有账号并安排迁移，避免相同标识代表不同用户。

OAuth2 仅把明确映射的用户字段传入账号开通与员工抽取，不保存完整 Token 响应、OTP 等未映射敏感字段。OIDC 保留原员工 claims 映射行为。

## 东方电气预设

点击“使用东方电气预设”只修改未保存表单，并关闭启用开关供复核。填写本应用 Client ID/Secret，不使用其他系统的凭据。

| 项目 | 文档预设 |
|---|---|
| 协议 | OAuth2 授权码 |
| 授权地址 | `https://iam.dongfang.com/idp/oauth2/authorize` |
| Token 地址 | `https://iam.dongfang.com/idp/oauth2/getToken` |
| Token 请求 | POST + Query，客户端凭据使用参数 |
| 用户信息 | GET + Query，参数 `access_token` |
| 用户信息地址 | `https://iam.dongfang.com/idp/oauth2/getUserInfo?client_id=本应用ID` |
| 唯一账号标识 | `spRoleList`，严格单值数组，按 Word 暂定 |
| 用户名 / 姓名 / 邮箱 | `loginName` / `displayName` / `mail` |
| PKCE / Scope | 文档未要求；预设关闭 / 留空 |

填写或修改 Client ID 后，核对用户信息地址的 `client_id` 查询参数。客户实际域名不同时修改三个接口地址。

其他平台截图以 `loginName` 为账号名，但这不能证明它就是唯一主键。现场用脱敏响应核实 `uid`、`loginName`、`spRoleList` 的含义及应用权限规则；确认前，空或多值 `spRoleList` 拒绝登录。

回调使用管理页显示的 `PUBLIC_BASE_URL/api/auth/sso/callback`。从社区登录按钮发起；直接访问后端登录 URL 会因缺少浏览器标记而拒绝。

退出地址由客户确认后填写。Word GLO 示例使用原拼写 `redirctToUrl`、`redirectToLogin=true`、`entityId=应用ID`，返回地址按客户白名单设置。

## 升级与网络

1. 升级 API 和 Web，设置正确 `PUBLIC_BASE_URL`。API 启动通过幂等 ALTER 添加 `sso_configs.oauth_options` JSON 列，原记录协议保留 OIDC。先备份数据库。
2. Redis 需 6.2 或更新版本（项目 Redis 7 满足），授权状态通过 GETDEL 原子消费。升级或配置更新前发出的登录请求可能失效，重新发起即可。
3. 身份服务接口强制 HTTPS，不允许 URL 用户名/密码或 fragment，不跟随重定向。内网域名通过 `SSO_ALLOWED_HOSTS=iam.customer.example` 精确放行；多个域名逗号分隔，不必关闭全局 SSRF 防护。
4. 客户 CA 通过运行环境信任库或 `SSL_CERT_FILE` 配置，不能关闭证书校验。浏览器及服务器均需能访问相应接口。
5. Query 可能把密钥放入 URL。应用屏蔽 httpx/httpcore 请求日志；代理、APM 和客户 IAM 日志也应避免记录完整敏感查询串。

“检查配置（不保存）”使用表单副本，不改变生效配置。OAuth2 只验证字段和出站地址策略，不携带凭据探测，也不证明账号或密钥可用；OIDC 额外探测发现端点及 JWKS。两者均需真实账号登录验收。

## 验收边界

本地模拟覆盖正常登录、权限/字段异常、重放、配置中途修改、浏览器主动登录标记、参数模式及密钥不回显。前端使用现有后台的颜色、边框和按钮，宽屏双列、窄屏单列。

Docker、数据库启动迁移、客户网络/CA 和真实 IAM 登录/GLO 尚需部署环境验收。现有 Next.js 15.1.6 的依赖安全警告不在此次框架升级范围内，生产上线前应单独处理。
