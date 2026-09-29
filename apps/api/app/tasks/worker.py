"""ARQ 任务定义与 worker 入口。"""
import logging

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.core.db import engine

logger = logging.getLogger(__name__)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _session() -> AsyncSession:
    return SessionLocal()


# ---------- 任务 ----------
async def review_post_task(ctx: dict, post_id: int) -> str:
    """发帖异步 AI 审核：通过→发布+触发 AI 回复；不通过→rejected。"""
    from app.tasks.review_tasks import review_post

    async with SessionLocal() as db:
        return await review_post(db, post_id)


async def run_pipeline_task(ctx: dict, post_id: int, content_type: str = "post") -> str:
    """发帖事件流水线（worker 执行，支持重试）。"""
    from app.agent.runner import trigger_pipeline

    async with SessionLocal() as db:
        return await trigger_pipeline(db, post_id, content_type)


async def parse_rag_document_task(ctx: dict, doc_id: int) -> None:
    """文档解析 + 切片 + embedding + 入库（后台任务）。"""
    from app.services.document_service import process_document

    async with SessionLocal() as db:
        await process_document(db, doc_id)


async def daily_news_task(ctx: dict) -> dict:
    from app.services.news_service import run_daily_news

    async with SessionLocal() as db:
        return await run_daily_news(db)


async def weekly_report_task(ctx: dict) -> int:
    from app.services.ops_service import send_weekly_reports

    async with SessionLocal() as db:
        return await send_weekly_reports(db)


async def no_reply_check_task(ctx: dict) -> int:
    from app.services.ops_service import check_no_reply_48h

    async with SessionLocal() as db:
        return await check_no_reply_48h(db)


async def stale_archive_task(ctx: dict) -> int:
    from app.services.ops_service import archive_stale_posts

    async with SessionLocal() as db:
        return await archive_stale_posts(db)


async def ai_admin_health_task(ctx: dict) -> int:
    from app.services.ops_service import check_ai_admin_health

    async with SessionLocal() as db:
        return await check_ai_admin_health(db)


async def extract_employee_task(ctx: dict, user_id: int, claims: dict) -> None:
    """SSO 首登后：LLM 按事实抽取员工扩展信息（失败静默，不影响登录）。"""
    from app.services.sso_service import extract_employee_with_llm

    async with SessionLocal() as db:
        await extract_employee_with_llm(db, user_id, claims)


async def startup(ctx: dict) -> None:
    logger.info("ARQ worker started")


async def shutdown(ctx: dict) -> None:
    logger.info("ARQ worker stopped")


FUNCTIONS = [
    review_post_task,
    run_pipeline_task,
    parse_rag_document_task,
    daily_news_task,
    weekly_report_task,
    no_reply_check_task,
    stale_archive_task,
    ai_admin_health_task,
    extract_employee_task,
]


def get_cron_jobs() -> list:
    """定时任务：资讯/周报/48h 提醒/归档/AI 管理员健康。

    arq 0.28 CronJob 签名：CronJob(name, coroutine, month, day, weekday, hour,
    minute, second, microsecond, run_at_startup, unique, job_id, timeout_s,
    keep_result_s, keep_result_forever, max_tries)。weekday: 0=周一 ... 6=周日。
    """
    from arq.worker import CronJob

    def cjob(name: str, func, *, weekday=None, hour=None, minute=0, run_at_startup=False) -> CronJob:
        return CronJob(
            name=name, coroutine=func,
            month=None, day=None, weekday=weekday, hour=hour, minute=minute,
            second=0, microsecond=0, run_at_startup=run_at_startup, unique=True,
            job_id=None, timeout_s=None, keep_result_s=None, keep_result_forever=None, max_tries=None,
        )

    return [
        cjob("daily_news", daily_news_task, hour=8),                 # 每日 08:00 抓取资讯
        cjob("weekly_report", weekly_report_task, weekday=0, hour=9),  # 每周一 09:00 周报
        cjob("no_reply_48h", no_reply_check_task, hour=None, minute=0),  # 每小时检查 48h 未回
        cjob("stale_archive", stale_archive_task, hour=3),           # 每日 03:00 僵尸帖归档
        cjob("ai_admin_health", ai_admin_health_task, hour=None, minute=0, run_at_startup=True),  # 每小时 AI 管理员健康
    ]


async def enqueue(name: str, *args) -> None:
    """入队任务。"""
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await redis.enqueue_job(name, *args)
    finally:
        await redis.close()


def main() -> None:
    import asyncio
    import sys

    # Windows: psycopg async 需要 SelectorEventLoop
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    from arq import Worker

    worker = Worker(
        functions=FUNCTIONS,
        cron_jobs=get_cron_jobs(),
        redis_settings=RedisSettings.from_dsn(settings.redis_url),
        on_startup=startup,
        on_shutdown=shutdown,
        max_tries=3,
        retry_jobs=True,
        job_timeout=600,
    )
    worker.run()


if __name__ == "__main__":
    main()
