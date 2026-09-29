"""模型统一导出（供 Alembic autogenerate 与 create_all）。"""
from app.models.users import User, Invitation
from app.models.categories import Category, CategoryHumanAdmin, CategoryAiAdmin
from app.models.posts import Post, Reply
from app.models.rag import RagDocument, RagChunk
from app.models.agent import AgentRun, KnowledgeHit
from app.models.interactions import Report, Subscription, Follow, Notification, AuditLog
from app.models.system import ModelConfig, AiNewsSource, SiteConfig
from app.models.tickets import TicketConfig, UserTicket, TicketTransaction
from app.models.external import ExternalAgent
from app.models.sso import SsoConfig, EmployeeProfile

__all__ = [
    "User", "Invitation", "Category", "CategoryHumanAdmin", "CategoryAiAdmin",
    "Post", "Reply", "RagDocument", "RagChunk", "AgentRun", "KnowledgeHit",
    "Report", "Subscription", "Follow", "Notification", "AuditLog", "ModelConfig", "AiNewsSource", "SiteConfig",
    "TicketConfig", "UserTicket", "TicketTransaction", "ExternalAgent",
    "SsoConfig", "EmployeeProfile",
]
