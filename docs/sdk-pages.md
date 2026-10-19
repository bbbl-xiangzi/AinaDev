# SDK 页面

超级管理员在「管理 → SDK 页面」添加页面，设置页面名称、唯一标识、平台 HTTPS 根地址、SDK 脚本 HTTPS 地址、浏览器端 AppKey 和启停状态。保存后，登录用户刷新社区即可看到导航入口 `/sdk/<slug>`。支持最多 20 个页面；停用的入口不可直接访问。新安装默认无页面，不包含任何客户地址或应用标识。

当前适配器为 **HiAgent Web SDK**：脚本需提供 `HiagentWebSDK.WebClient`，初始化参数为 `baseUrl`、`appKey`、`hideSidebar`、`variables`。脚本地址通常为平台的 `/resources/product/llm/public/sdk/embedFull.js`。其他 SDK 的构造方法和协议不同，需要新增适配器，不能只替换 URL。

SDK 从用户浏览器加载，用户网络必须能访问配置的两个地址。SDK 在不授予 `allow-same-origin` 的 sandbox iframe 中执行，不能读取社区的 DOM、Cookie 或 localStorage。供应商必须允许隔离来源的跨域请求；依赖同源存储、特定 Origin 或第三方登录 Cookie 的 SDK 可能不兼容，可使用页面上的「打开平台」入口。接入前应在实际网络和浏览器完成供应商端测试。

AppKey 会提供给已登录用户的浏览器，不是服务端秘密；不要填写模型 API Key、OAuth ClientSecret 等。普通用户不能读取管理接口或修改配置，导航列表也不返回 SDK 配置。管理员只应填写可信 SDK；页面内容和对话由第三方服务处理。

配置存于既有 `SiteConfig` 的 `sdk_pages` 项，无数据库迁移。此通用功能不自动迁移客户私有的 `hiagent_sdk` 项，管理员需重新配置。此功能也不配置论坛的自动回帖 Agent。
