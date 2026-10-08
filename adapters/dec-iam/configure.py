"""Generate deployment files locally; never transmit secrets or overwrite files."""
import argparse
import getpass
import json
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from dec_iam.config import Settings


def initialize(output: Path, *, issuer: str, community_url: str, iam_base_url: str,
               iam_client_id: str, iam_client_secret: str):
    values = dict(issuer=issuer, community_url=community_url, iam_base_url=iam_base_url,
                  iam_client_id=iam_client_id, iam_client_secret=iam_client_secret,
                  client_secret=secrets.token_urlsafe(48))
    if any("\n" in value or "\r" in value or "\x00" in value for value in values.values()):
        raise ValueError("Configuration values cannot contain newlines or NUL")
    cfg = Settings(_env_file=None, **values)
    files = [output / ".env", output / "secrets/signing.pem", output / "community-sso.json"]
    if any(path.exists() for path in files):
        raise FileExistsError("Configuration already exists; refusing to replace credentials or signing key")
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    output.mkdir(parents=True, exist_ok=True)
    (output / "secrets").mkdir(mode=0o700, exist_ok=True)
    # mkdir does not tighten permissions on an existing directory.
    # Fail before writing credentials if the host cannot protect this directory.
    (output / "secrets").chmod(0o700)
    env = {
        "DEC_ISSUER": cfg.issuer, "DEC_COMMUNITY_URL": cfg.community_url,
        "DEC_IAM_BASE_URL": cfg.iam_base_url, "DEC_IAM_CLIENT_ID": cfg.iam_client_id,
        "DEC_IAM_CLIENT_SECRET": cfg.iam_client_secret.get_secret_value(),
        "DEC_CLIENT_ID": cfg.client_id, "DEC_CLIENT_SECRET": cfg.client_secret.get_secret_value(),
        "DEC_SIGNING_KEY_FILE": "/run/secrets/dec-signing.pem",
        "DEC_REDIS_URL": "redis://dec-redis:6379/0", "DEC_IAM_TOKEN_PARAMETERS": "query",
    }
    community = {
        "enabled": True, "label": "东方电气统一身份登录", "protocol": "oidc", "issuer": cfg.issuer,
        "client_id": cfg.client_id, "client_secret": cfg.client_secret.get_secret_value(),
        "authorization_endpoint": cfg.issuer + "/authorize", "token_endpoint": cfg.issuer + "/token",
        "jwks_uri": cfg.issuer + "/jwks", "userinfo_endpoint": cfg.issuer + "/userinfo",
        "scopes": "openid profile", "bind_rule": "sub", "auto_provision": True,
        "extract_employee": False, "claim_sub": "sub", "claim_name": "name", "claim_email": "email",
    }
    contents = ["\n".join(f"{name}={value}" for name, value in env.items()) + "\n",
                key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()).decode(),
                json.dumps(community, indent=2, ensure_ascii=False) + "\n"]
    for path, content in zip(files, contents):
        # O_EXCL protects against accidental concurrent initialization.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    # Bind-mounted individual file is readable by the non-root container user;
    # host secrets directory remains 0700. Keep this directory private.
    files[1].chmod(0o644)
    return cfg


def main():
    parser = argparse.ArgumentParser(description="生成东方电气适配器配置；不会修改运行中的社区")
    parser.add_argument("--issuer", required=True, help="适配器外部 HTTPS 域名")
    parser.add_argument("--community-url", required=True)
    parser.add_argument("--iam-base-url", required=True)
    parser.add_argument("--iam-client-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("--no-input", action="store_true", help="从 DEC_IAM_CLIENT_SECRET 环境变量读取 IAM 密钥")
    args = parser.parse_args()
    secret = os.environ.get("DEC_IAM_CLIENT_SECRET")
    if not secret and not args.no_input:
        secret = getpass.getpass("IAM Client Secret（输入不回显）: ")
    if not secret:
        parser.exit(2, "缺少 IAM 密钥；请交互输入或设置 DEC_IAM_CLIENT_SECRET。\n")
    try:
        cfg = initialize(args.output_dir, issuer=args.issuer, community_url=args.community_url,
                         iam_base_url=args.iam_base_url, iam_client_id=args.iam_client_id, iam_client_secret=secret)
    except (ValueError, OSError):
        # Pydantic error repr may contain input values; do not print it.
        parser.exit(2, "初始化失败：检查 HTTPS 域名、必填参数、目录权限及是否已有配置；不会覆盖已有文件。\n")
    print("已生成 .env、secrets/signing.pem、community-sso.json；这些文件包含凭据，请勿提交 Git。")
    print("在 IAM 登记的回调地址：" + cfg.iam_callback_uri)
    print("社区环境变量 SSO_LOGOUT_URL=" + cfg.issuer + "/logout")
    print("若适配器解析为内网地址，在社区设置 SSO_ALLOWED_HOSTS 为适配器域名。")


if __name__ == "__main__":
    main()
