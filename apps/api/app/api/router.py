"""API 路由聚合。"""
from fastapi import APIRouter

from app.api.admin_categories import router as admin_categories
from app.api.admin_external_agents import router as admin_external_agents
from app.api.admin_models import router as admin_models
from app.api.admin_news import router as admin_news
from app.api.admin_rag import router as admin_rag
from app.api.admin_reviews import router as admin_reviews
from app.api.admin_sso import router as admin_sso
from app.api.admin_system import router as admin_system
from app.api.admin_tickets import router as admin_tickets
from app.api.admin_users import router as admin_users
from app.api.auth import router as auth
from app.api.auth_sso import router as auth_sso
from app.api.categories import router as categories
from app.api.me import router as me
from app.api.posts import router as posts
from app.api.uploads import router as uploads
from app.api.users import router as users
from app.api.banners import router as banners

from app.api.sdk_pages import router as sdk_pages

api_router = APIRouter()
api_router.include_router(banners)
api_router.include_router(sdk_pages)
for r in [auth, auth_sso, categories, posts, me, users, uploads, admin_categories, admin_external_agents, admin_models, admin_rag, admin_news, admin_reviews, admin_sso, admin_users, admin_system, admin_tickets]:
    api_router.include_router(r)
