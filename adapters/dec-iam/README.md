# 东方电气 IAM 配置器与独立适配服务

此目录提供一个独立部署的 IAM→OIDC 桥接服务，以及生成配置文件的本地命令。社区连接适配器的 OIDC 接口，适配器按 DECITC.BZ.0017A 的 B/S 授权码流程连接客户 IAM。使用此分支的社区代码，包含 SSO 回调接收、Redis/ARQ 修复和连接适配；只部署适配器而继续使用旧版社区代码，不能保证完成登录。

```text
浏览器 → 社区 → 适配器 /authorize → 客户 IAM /idp/oauth2/authorize
                                   ↑ IAM 回调 /iam/callback
                    适配器后端 → getToken → getUserInfo → 校验 spRoleList
浏览器 ← 社区回调 ← 适配器返回自己的授权码
社区后端 → 适配器 /token、/jwks、/userinfo → 社区本地登录
```

这不是 IAM 服务器替代品。客户账号、密码、认证策略仍由客户 IAM 管理；不使用文档中的密码模式，不接收用户 IAM 密码。本版本每个适配器对应一个 IAM 应用、一个社区实例，不提供多企业入口或账号同步 API。

## 部署前需要的资料

| 配置 | 提供方 | 示例用途 |
|---|---|---|
| IAM 实际 HTTPS 域名 | 客户 | `https://iam.customer.example`，需确认三个接口路径与文档一致 |
| IAM Client ID / Secret | 客户 | 仅适配器到 IAM 使用，测试和正式环境分开 |
| 适配器 HTTPS 域名及证书 | 部署方 | `https://sso-adapter.customer.example`，独立域名根路径 |
| 社区 HTTPS 域名 | 部署方 | `https://community.customer.example` |
| IAM 授权测试账号 | 客户 | 单权限、无权限、多权限、停用账号 |
| 内部 CA 公共证书链 | 客户 | 如果 IAM 或适配器使用内部 CA，需要导入相应容器信任 |

目前按用户确认的严格规则：`spRoleList` 必须恰好有一个非空字符串，该字符串作为应用账号主键和 OIDC `sub`。为空、多个值、类型错误均拒绝登录。部署前请让客户确认字段业务含义及主键是否会被重复分配；不要自行改为取数组第一项。

## 1 生成配置

需要 Python 3.12 和 Docker Compose **2.30 或以上**。较新 Compose 的 `env_file.format: raw` 用于原样传递包含 `$` 的 IAM 密钥。

在本目录执行（Linux）：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python configure.py \
  --issuer https://sso-adapter.customer.example \
  --community-url https://community.customer.example \
  --iam-base-url https://iam.customer.example \
  --iam-client-id 客户分配的应用ID
```

IAM 密钥通过不回显的交互输入。自动化部署可设置 `DEC_IAM_CLIENT_SECRET` 后加 `--no-input`，不要把密钥直接写进命令行参数。Windows 可以使用 `.venv\Scripts\python.exe` 执行同一脚本。

生成文件：

- `.env`：适配器配置，包括上下游两套不同的客户端凭据。
- `secrets/signing.pem`：3072 位 RSA 私钥，用于签发适配器自己的 ID Token。
- `community-sso.json`：社区 SSO 配置参考，包含适配器为社区生成的 Client Secret。

这些文件已被 Git 忽略，Docker 构建上下文也排除凭据。脚本拒绝覆盖现有文件；修改普通配置可编辑 `.env`，不要重新初始化来轮换私钥。Linux 上保持 `secrets/` 目录权限为 0700，配置文件为 0600；私钥单文件为 0644，以便单文件只读挂载后由容器非 root 用户读取，主机目录必须保持私有。Windows 请通过目录 ACL 限制读取。

初始化脚本只生成本地文件，不登录或修改现有社区。

## 2 客户 IAM 登记

请客户登记适配器回调：

```text
https://sso-adapter.customer.example/iam/callback
```

这是 IAM 回调地址。社区已有的 `/api/auth/sso/callback` 是适配器向社区的回调，不能把两个地址填反。

请客户为应用分配员工访问权限。邮箱不是登录前提；账号匹配不依赖邮箱。适配器暂不转发 `mail` 字段，避免社区现有按邮箱关联逻辑错误合并账号。

## 3 启动适配器及 TLS 网关

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8091/health
```

Compose 启动适配器与专用 Redis 7。适配器只绑定宿主机 `127.0.0.1:8091`，Redis 不映射主机端口，状态网络设为内部网络。适配器通过另一个网络访问 IAM。Redis 只保存短期状态和令牌，不持久化；重启会让正在进行的登录失效，用户重新登录即可。

参考 `nginx.example.conf`，将适配器域名的 HTTPS 流量转发到 `127.0.0.1:8091`。此示例用于宿主机网关；网关在容器中时，需接入适配器网络并把 upstream 改为 `adapter:8080`，不能使用容器自己的 127.0.0.1。

浏览器和社区后端容器都必须能通过相同域名访问适配器；适配器后端必须能访问 IAM 的 Token 和 UserInfo 接口，浏览器必须能访问 IAM 授权页。`DEC_ISSUER` 是浏览器访问的 HTTPS 地址，不要填 Docker 服务名或内部端口。

应用关闭访问日志；TLS 网关也应关闭包含查询参数的访问日志。IAM 文档要求 query 传 Token 请求参数，IAM 端网关也需做日志脱敏。若客户确认支持 form，可将 `.env` 中 `DEC_IAM_TOKEN_PARAMETERS=query` 改为 `form`，其他流程不变。

## 4 内部 CA

不关闭证书验证。如果 IAM 使用内部 CA，在本目录创建 `compose.override.yml`，例如：

```yaml
services:
  adapter:
    volumes:
      - ./customer-ca.pem:/run/customer-ca.pem:ro
    environment:
      DEC_IAM_CA_FILE: /run/customer-ca.pem
```

文件只应含 CA 公共证书，不需要 IAM 私钥。适配器域名使用内部 CA 时，也要在社区 API 容器挂载 CA 信任包，并设置 `SSL_CERT_FILE` 为该文件路径。修改挂载和环境后重建对应容器。

## 5 连接社区

先部署此分支的社区 API 与前端；前端和 API 必须一起升级。请保留管理员本地登录，以便配置错误时恢复。

如果适配器域名解析到客户内网地址，在**社区根目录** `.env` 添加：

```dotenv
SSO_ALLOWED_HOSTS=sso-adapter.customer.example
SSO_LOGOUT_URL=https://sso-adapter.customer.example/logout
```

`SSO_ALLOWED_HOSTS` 只放行精确匹配的 HTTPS SSO 主机，不支持通配符，不影响文档导入等功能的出站防护。无需设置 `BLOCK_PRIVATE_URLS=false`。

使用社区现有部署编排更新 API、worker、web。仓库 `docker-compose.prod.yml` 依赖客户已有 `back` 网络且没有宿主机端口映射，需保留或适配当前客户网关连接方式；不要盲目把本目录的 Compose 当成整个社区编排。

在社区后台「SSO 登录」填写 `community-sso.json` 对应字段：

| 社区字段 | 值 |
|---|---|
| Issuer | 适配器域名，必须填写并与 discovery 完全一致 |
| Client ID / Secret | **生成的社区凭据**，不是客户 IAM 凭据 |
| Authorization Endpoint | 适配器域名 + `/authorize` |
| Token Endpoint | 适配器域名 + `/token` |
| JWKS URI | 适配器域名 + `/jwks` |
| UserInfo Endpoint | 适配器域名 + `/userinfo` |
| Scopes | `openid profile` |
| 绑定规则 | `sub` |
| 首次登录自动开通 | 按项目约定，生成配置默认开启，仅限 IAM 已授权用户 |
| 员工信息 AI 抽取 | 关闭，使用确定性字段映射 |

填好后测试连接、保存并启用。端点探测中的 400/401/405 可以是未携带授权参数的正常拒绝，探测通过不代表客户凭据有效，必须再做一次实际登录。

从社区登录页点击企业登录按钮。前端为本次登录创建浏览器随机标记，回调匹配后才接受社区令牌，且使用 `/auth/me` 获取真实身份。请勿把 `/api/auth/sso/login` 当作可独立访问的门户入口；门户应链接社区登录页。

## 字段与接口范围

| IAM 字段 | 下游 OIDC 字段 |
|---|---|
| 唯一的 `spRoleList` 项 | `sub` |
| `displayName`，其次 `fullName` / `loginName` | `name` |
| `loginName` | `preferred_username` |
| `employeeNumber`，其次 `loginName` | `employee_no` |
| `orgNamePath` | `org_path` |

仅传上述字段。不转发 `otpKey`、身份证、生日等原始属性，不把 `spRoleList` 当作社区管理员角色，不产生客户不存在的数据。社区新用户仍为普通会员。

适配器提供 OIDC 授权码流程所需接口，使用 RS256、JWKS、PKCE S256、state、nonce、精确回调校验。仅支持登记的一个机密客户端、`client_secret_post`、GET UserInfo，不提供动态客户端注册或 refresh token；未进行 OpenID 认证，不能宣称完整 OIDC 产品认证。

## 退出及尚待客户补充的部分

用户从社区退出时，先清除该浏览器社区登录信息，再经适配器 `/logout` 跳转 IAM 全局退出。使用文档原拼写：

```text
/idp/profile/OAUTH2/Redirect/GLO
  ?redirctToUrl=https://社区域名/login
  &redirectToLogin=true
  &entityId=客户IAM应用ID
```

该流程**不等于完整单点注销**：Word 提到回收授权接口和 IAM 调用应用销毁会话，但未提供完整定义。本版本未实现 IAM 发起的应用会话清除、IAM 票据回收，以及已签发社区 JWT 的立即撤销；社区令牌仍遵循原有效期。适配器自己不保存 IAM Token，不创建持久 IAM 会话。客户要求完整 SLO 或即时离职停用时，必须补齐回收接口、回调鉴权和会话撤销方案后再上线验收。

账号/组织同步 `SchemaService`、`UserCreateService` 等不在此适配器范围内；首次登录自动开通不能替代生命周期同步。

## 验证和故障定位

```bash
curl https://sso-adapter.customer.example/.well-known/openid-configuration
curl https://sso-adapter.customer.example/jwks
docker compose logs --tail=100 adapter
```

| 现象 | 检查 |
|---|---|
| 社区提示内网地址被拦截 | API 容器 `SSO_ALLOWED_HOSTS` 和重建是否生效 |
| 用户从 IAM 回来后拒绝 | 浏览器 Cookie、回调域名、应用权限、`spRoleList` 是否恰好一个值 |
| Token 交换失败 | 两套 Client Secret 是否填反；IAM query/form 模式；回调是否完全一致 |
| 证书错误 | 适配器/社区的 CA 文件和域名，不关闭证书验证 |
| 返回社区仍未登录 | API 和 web 是否都升级；是否从社区按钮发起；浏览器 sessionStorage 是否可用 |
| 退出又自动登录 | IAM GLO 配置、客户全局会话策略及尚未完成的票据回收联调 |

本地测试（无需真实 IAM，Redis 使用内存仿真）：

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
```

测试包含真实社区 OIDC 验签实现与适配器 JWKS 的互通；其他网络边界用模拟数据。应分别记录容器运行、客户 CA/网络、真实 IAM 有/无权限账号、重复登录和 GLO 的现场验收结果，不能用本地模拟替代。

升级时备份 `.env`、`community-sso.json`、`secrets/signing.pem`，保留私钥后重建容器。更换私钥会改变 JWKS；需要安排变更窗口，不要在多实例间使用不同私钥。
