"""全局配置：从环境变量 / .env 读取。"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 站点
    site_name: str = "AI 开发者社区"
    site_description: str = "企业 AI 原生开发者社区"
    public_base_url: str = "http://localhost"

    # 数据层
    database_url: str = "postgresql+psycopg://community:community@localhost:5432/community"
    redis_url: str = "redis://localhost:6379/0"

    # 安全
    # 环境：development / production。production 下若密钥仍为默认值将拒绝启动（防客户部署带病运行）
    app_env: str = "development"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 120  # 收紧：改密后旧 token 最长 2h 有效
    jwt_refresh_expire_days: int = 7
    aes_key: str = "change-me-32-bytes-hex-0123456789abcdef0123456789abcdef"
    mcp_api_key: str = "change-me-mcp-token"
    invite_expire_days: int = 7
    # 出站请求安全：拦截私网/回环/云元数据地址（防 SSRF）。客户若需抓内网 RSS/资讯源，设 false
    block_private_urls: bool = True

    # 默认模型（首次启动写入 model_configs）
    default_llm_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    default_llm_api_key: str = ""
    default_llm_chat_model: str = "doubao-seed-1-6-250615"
    default_embedding_model: str = "doubao-embedding-large"
    default_embedding_dim: int = 2048

    # RSSHub 自部署实例（容器网络内）
    rsshub_base_url: str = "http://rsshub:1200"

    # 邮件（可选）
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # 上传
    upload_dir: str = "./uploads"
    # 知识库文档隔离目录（不挂在 /uploads 静态目录下，下载走后台鉴权接口，避免内部资料公开）
    rag_docs_dir: str = "./data/rag_docs"

    # 检索后端自动适配：
    # vector_backend: numpy=JSONB+应用层余弦（Windows/无 pgvector 环境）| pgvector=SQL HNSW（生产 Linux/Docker）| weaviate=独立向量库
    # fulltext_mode: ilike=关键词模糊（Windows/无 zhparser）| zhparser=中文分词全文检索（生产 Linux/Docker）
    vector_backend: str = "numpy"
    fulltext_mode: str = "ilike"

    # Weaviate 独立向量库（vector_backend=weaviate 时生效；应用侧生成向量后传入，向量模式 NONE）
    # 默认值为占位符，生产/部署时通过 .env 注入真实连接信息（WEAVIATE_HOST 等）
    weaviate_host: str = "weaviate-host"
    weaviate_http_port: int = 8080
    weaviate_grpc_port: int = 50051
    weaviate_collection: str = "AinaDev"

    # 初始超管（可选，配置后首次启动自动创建；未配置则首个注册用户成为超管）
    admin_email: str = ""
    admin_password: str = ""
    admin_name: str = "管理员"

    # 运维任务
    news_fetch_cron: str = "0 8 * * *"      # 每日资讯抓取时间
    weekly_report_cron: str = "0 18 * * 5"  # 每周五 18:00 周报
    no_reply_check_cron: str = "0 */6 * * *"  # 每 6 小时检查 48h 未回复
    stale_archive_cron: str = "0 3 * * *"   # 每日 3:00 僵尸帖归档


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
