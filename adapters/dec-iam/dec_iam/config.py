from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEC_", env_file=".env", extra="ignore")

    issuer: str
    community_url: str
    iam_base_url: str
    iam_client_id: str = Field(min_length=1, max_length=200)
    iam_client_secret: SecretStr
    client_id: str = Field(default="community", pattern=r"^[A-Za-z0-9_-]{1,100}$")
    client_secret: SecretStr
    signing_key_file: Path = Path("/run/secrets/dec-signing.pem")
    redis_url: SecretStr = SecretStr("redis://dec-redis:6379/0")
    iam_token_parameters: Literal["query", "form"] = "query"
    iam_ca_file: Path | None = None
    allow_http: bool = False
    state_ttl: int = Field(default=600, ge=60, le=900)
    code_ttl: int = Field(default=60, ge=10, le=120)
    token_ttl: int = Field(default=300, ge=30, le=600)

    @model_validator(mode="after")
    def validate_configuration(self):
        for field in ("issuer", "community_url", "iam_base_url"):
            value = getattr(self, field).rstrip("/")
            url = urlsplit(value)
            if (url.scheme not in ({"https", "http"} if self.allow_http else {"https"})
                    or not url.hostname or url.username or url.password or url.query or url.fragment or url.path):
                raise ValueError(f"{field} must be an HTTPS origin without path, credentials, query or fragment")
            setattr(self, field, value)
        secret = self.client_secret.get_secret_value()
        if len(secret) < 32 or secret.lower().startswith(("change", "replace", "example")):
            raise ValueError("client_secret must be a generated random secret of at least 32 characters")
        if not self.iam_client_secret.get_secret_value().strip():
            raise ValueError("iam_client_secret is required")
        if secret == self.iam_client_secret.get_secret_value():
            raise ValueError("IAM and community must use different client secrets")
        return self

    @property
    def redirect_uri(self):
        return self.community_url + "/api/auth/sso/callback"

    @property
    def iam_callback_uri(self):
        return self.issuer + "/iam/callback"
