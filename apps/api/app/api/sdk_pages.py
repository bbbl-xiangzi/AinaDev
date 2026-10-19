"""Administrator-managed SDK pages; no customer defaults or server-side requests."""
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_super_admin
from app.models import SiteConfig, User

router = APIRouter(tags=["sdk-pages"])
CONFIG_KEY = "sdk_pages"


class SdkPage(BaseModel):
    slug: str = Field(pattern=r"^[a-z][a-z0-9-]{0,47}$")
    title: str = Field(min_length=1, max_length=60)
    enabled: bool = False
    provider: Literal["hiagent"] = "hiagent"
    base_url: str = Field(max_length=2048)
    sdk_url: str = Field(max_length=2048)
    app_key: str = Field(min_length=1, max_length=256)

    @field_validator("title", "app_key")
    @classmethod
    def nonempty(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("内容不能为空或包含控制字符")
        return value

    @field_validator("base_url", "sdk_url")
    @classmethod
    def https_url(cls, value):
        value = value.strip()
        p = urlsplit(value)
        if (p.scheme != "https" or not p.hostname or p.username is not None
                or p.password is not None or p.fragment or "\\" in value
                or any(c.isspace() or ord(c) < 32 for c in value)):
            raise ValueError("请输入不含凭据的 HTTPS 地址")
        _ = p.port
        return value

    @model_validator(mode="after")
    def base_origin(self):
        p = urlsplit(self.base_url)
        if p.path not in ("", "/") or p.query:
            raise ValueError("平台地址应为 HTTPS 站点根地址")
        self.base_url = self.base_url.rstrip("/")
        return self


class SdkPages(BaseModel):
    pages: list[SdkPage] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def unique_slugs(self):
        if len({p.slug for p in self.pages}) != len(self.pages):
            raise ValueError("页面标识不能重复")
        return self


async def read_pages(db):
    row = await db.get(SiteConfig, CONFIG_KEY)
    return SdkPages.model_validate_json(row.value) if row else SdkPages()


@router.get("/api/admin/sdk-pages", response_model=SdkPages)
async def admin_pages(admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return await read_pages(db)


@router.put("/api/admin/sdk-pages", response_model=SdkPages)
async def save_pages(body: SdkPages, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    row = await db.get(SiteConfig, CONFIG_KEY)
    if row:
        row.value = body.model_dump_json()
    else:
        db.add(SiteConfig(key=CONFIG_KEY, value=body.model_dump_json()))
    await db.commit()
    return body


@router.get("/api/sdk-pages")
async def navigation(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [{"slug": p.slug, "title": p.title} for p in (await read_pages(db)).pages if p.enabled]


@router.get("/api/sdk-pages/{slug}", response_model=SdkPage)
async def page(slug: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    for p in (await read_pages(db)).pages:
        if p.slug == slug and p.enabled:
            return p
    raise HTTPException(404, "页面不存在或已停用")
