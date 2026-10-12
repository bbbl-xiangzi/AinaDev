"""Homepage banners stored independently from existing site settings."""
import re
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.deps import require_super_admin
from app.models import SiteConfig, Post, User, AuditLog

router = APIRouter(prefix='/api', tags=['banners'])
KEY = 'homepage_banners'


class Banner(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    image_url: str = Field(max_length=300)
    post_id: int = Field(gt=0)
    pinned: bool = False
    enabled: bool = True

    @field_validator('image_url')
    @classmethod
    def uploaded_image(cls, value):
        if not re.fullmatch(r'/uploads/\d{6}/\d{2}/[a-f0-9]{32}\.(png|jpg|jpeg|gif|webp)', value):
            raise ValueError('请选择已上传的 PNG/JPG/GIF/WebP 图片')
        return value


class BannerSettings(BaseModel):
    items: list[Banner] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def unique_ids(self):
        if len({i.id for i in self.items}) != len(self.items):
            raise ValueError('轮播图标识重复')
        return self


async def read_items(db):
    row = await db.get(SiteConfig, KEY)
    return BannerSettings.model_validate_json(row.value).items if row else []


async def related_posts(db, items):
    ids = {i.post_id for i in items}
    if not ids: return {}
    return {p.id:p for p in await db.scalars(select(Post).where(Post.id.in_(ids)))}


def visible_banners(items, posts):
    result=[]
    for item in sorted(items, key=lambda x: not x.pinned):
        p=posts.get(item.post_id)
        if item.enabled and p and p.status=='published' and p.deleted_at is None:
            result.append({**item.model_dump(), 'post_title':p.title})
    return result


@router.get('/banners')
async def public_banners(response: Response, db: AsyncSession=Depends(get_db)):
    response.headers['Cache-Control']='no-store'
    items=await read_items(db)
    return {'items':visible_banners(items,await related_posts(db,items))}


@router.get('/admin/banners/posts')
async def search_posts(q: str=Query('',max_length=100), admin: User=Depends(require_super_admin), db: AsyncSession=Depends(get_db)):
    stmt=select(Post).where(Post.status=='published',Post.deleted_at.is_(None))
    if q.strip():
        term=q.strip()
        title_match=Post.title.icontains(term,autoescape=True)
        stmt=stmt.where(or_(title_match,Post.id==int(term)) if term.isdigit() and len(term)<10 else title_match)
    posts=await db.scalars(stmt.order_by(Post.created_at.desc()).limit(30))
    return {'items':[{'id':p.id,'title':p.title} for p in posts]}


@router.get('/admin/banners')
async def get_settings(admin: User=Depends(require_super_admin), db: AsyncSession=Depends(get_db)):
    items=await read_items(db)
    posts=await related_posts(db,items)
    return {'items':[{**i.model_dump(),'post_title':posts[i.post_id].title if i.post_id in posts else '帖子已删除',
                      'post_available':i.post_id in posts and posts[i.post_id].status=='published' and posts[i.post_id].deleted_at is None} for i in items]}


@router.put('/admin/banners')
async def save_settings(body: BannerSettings, admin: User=Depends(require_super_admin), db: AsyncSession=Depends(get_db)):
    # Existing unavailable associations may be retained or taken down; new/reenabled ones must be public.
    existing={i.id:i for i in await read_items(db)}
    posts=await related_posts(db,body.items)
    for i in body.items:
        old=existing.get(i.id)
        if old and old.post_id==i.post_id and (old.enabled or not i.enabled):
            continue
        p=posts.get(i.post_id)
        if not p or p.deleted_at is not None or p.status!='published':
            raise HTTPException(400,'关联帖子不存在或未发布，请重新选择')
    value=body.model_dump_json()
    await db.execute(insert(SiteConfig).values(key=KEY,value=value).on_conflict_do_update(index_elements=[SiteConfig.key],set_={'value':value}))
    db.add(AuditLog(actor_type='user',actor_id=admin.id,action='homepage_banners_updated',target_type='site_config',detail={'count':len(body.items)}))
    await db.commit()
    return await get_settings(admin,db)
