"""合规审查：LLM 审查（提示词后台可配置）+ 内置通用词表预检。"""
import json
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRun, SiteConfig
from app.services.llm import chat_with_json
from app.services.model_service import get_default_llm_config

# 内置通用风险词表（本地预检兜底，最终以 LLM 审查为准；可被站点配置 review_prompt 增强）
COMMON_BLOCK_WORDS = [
    "枪支", "爆炸物", "制毒", "贩毒", "博彩", "赌博平台", "代开发票", "刷单兼职",
]

# 默认审核提示词（后台「设置」页可修改，覆盖后立即生效）
DEFAULT_REVIEW_PROMPT = """你是企业内部开发者社区的内容安全审核员。请审核用户发布的帖子/回复，输出严格 JSON：
{"pass": true/false, "reason": "简要原因", "severity": "low|mid|high"}

以下内容一律判定为不通过（pass=false，severity 按危险程度给 mid 或 high）：
1. 政治敏感：攻击中国政府、中国共产党、领导人，或提及敏感政治事件、敏感人物（含谐音、影射、藏头诗、拆字等变体）。
2. 违法与高危：枪支、爆炸物、毒品、赌博、诈骗、黑客攻击教程、泄露国家秘密或企业机密。
3. 色情低俗：色情描写、色情链接、性暗示、招嫖。
4. 暴力恐怖：暴力威胁、恐吓、教唆伤害他人、恐怖主义言论。
5. 人身攻击与仇恨：辱骂、诅咒、歧视（性别/地域/民族/宗教/疾病）、贬低他人人格。
6. 粗口脏话：任何不文明用语，无论是否用谐音、缩写、拼音、emoji 变体。
7. 消极负面情绪宣泄：与工作无关的抱怨、消极怠工言论、影响团队氛围的负能量。
8. 与技术无关的闲聊灌水：拉家常、灌水、广告推广、刷屏、无关内容。
9. 其他企业内网不应出现的内容。

正常的技术讨论（含批评某产品/某 API 不好用、求助、经验分享）属于合规内容，不要误判。
只依据给定内容判断，不要联想扩展。"""


async def get_review_prompt(db: AsyncSession) -> str:
    """读取后台配置的审核提示词，未配置时用默认预设。"""
    row = await db.scalar(select(SiteConfig).where(SiteConfig.key == "review_prompt"))
    if row and row.value.strip():
        return row.value.strip()
    return DEFAULT_REVIEW_PROMPT


DEFAULT_RELEVANCE_PROMPT = """你是社区栏目的主题相关性审核员。栏目有明确的主题定位，你需要判断用户内容是否与栏目主题相关，输出严格 JSON：
{"relevant": true/false, "reason": "简要原因（50字内）"}

判断标准：
1. 内容与栏目主题直接相关、或属于该主题下的提问/讨论/求助/经验分享 → relevant=true。
2. 内容与栏目主题完全无关（如跨领域闲聊、与栏目定位无关的灌水）→ relevant=false。
3. 边界情况（沾边但主题偏移）→ relevant=false，reason 说明偏移在哪。
4. 只依据栏目主题定位和给定内容判断，不要联想扩展。"""


async def relevance_check(db: AsyncSession, category_name: str, category_desc: str | None, content: str, post_id: int | None, trace_id: str) -> dict:
    """栏目主题相关性判断（内置 LLM）。返回 {"pass": bool, "reason": str}。"""
    cfg = await get_default_llm_config(db)
    system_prompt = DEFAULT_RELEVANCE_PROMPT
    user_content = (
        f"栏目主题：{category_name}\n栏目定位：{category_desc or '（无描述）'}\n\n"
        f"待判断内容：\n{content[:3000]}"
    )
    start = time.time()
    raw = ""
    try:
        raw = await chat_with_json(cfg, system_prompt, user_content, max_tokens=500)
        result = json.loads(raw)
        if not isinstance(result, dict) or "relevant" not in result:
            raise ValueError("缺少 relevant 字段")
    except Exception as exc:
        # AI 异常/非法输出：保守策略按不相关处理，转人工复核
        result = {"relevant": False, "reason": f"AI 相关性判断未返回有效结果（{type(exc).__name__}），转人工复核"}
        raw = raw or f"<error:{type(exc).__name__}>"

    passed = bool(result.get("relevant", False))
    reason = str(result.get("reason", ""))[:200]
    db.add(
        AgentRun(
            trace_id=trace_id, trigger_type="compliance", post_id=post_id,
            node="relevance", prompt=system_prompt + "\n---\n" + user_content, response=raw,
            latency_ms=int((time.time() - start) * 1000),
            decision="pass" if passed else "reject", score=None,
        )
    )
    await db.commit()
    return {"pass": passed, "reason": reason}


DEFAULT_QUESTION_PROMPT = """你是社区 AI 助手的决策器。请判断帖子作者的这条追加评论是否是「需要回复的提问」，输出严格 JSON：
{"is_question": true/false, "reason": "简要原因（30字内）"}

判定标准：
1. 内容提出了具体问题、请求帮助、追问细节、寻求建议/方案 → is_question=true。
2. 纯寒暄/致谢/表态（如“谢谢”“好的”“哦”“收到”“哈哈”“顶”“收藏了”等）或没有信息诉求的闲聊 → is_question=false。
3. 不清楚是否提问时，倾向于 false（宁可不打扰）。
只依据评论内容判断。"""


async def is_question_check(db: AsyncSession, content: str, post_id: int | None, trace_id: str) -> dict:
    """判断楼主评论是否提问（内置 LLM）。返回 {"is_question": bool, "reason": str}。"""
    cfg = await get_default_llm_config(db)
    system_prompt = DEFAULT_QUESTION_PROMPT
    user_content = f"帖子作者的追加评论：\n{content[:1500]}"
    start = time.time()
    raw = ""
    try:
        raw = await chat_with_json(cfg, system_prompt, user_content, max_tokens=500)
        result = json.loads(raw)
        if not isinstance(result, dict) or "is_question" not in result:
            raise ValueError("缺少 is_question 字段")
    except Exception as exc:
        result = {"is_question": False, "reason": f"判断异常（{type(exc).__name__}），按非提问处理"}
        raw = raw or f"<error:{type(exc).__name__}>"

    is_question = bool(result.get("is_question", False))
    reason = str(result.get("reason", ""))[:100]
    db.add(
        AgentRun(
            trace_id=trace_id, trigger_type="judge", post_id=post_id,
            node="is_question", prompt=system_prompt + "\n---\n" + user_content, response=raw,
            latency_ms=int((time.time() - start) * 1000),
            decision="question" if is_question else "skip", score=None,
        )
    )
    await db.commit()
    return {"is_question": is_question, "reason": reason}


async def compliance_check(
    db: AsyncSession,
    content: str,
    post_id: int | None,
    trace_id: str,
) -> dict:
    """返回 {"pass": bool, "reason": str, "severity": str}。"""
    # 0) 本地词表预检（快速拦截，仍走 LLM 确认）
    hit_word = next((w for w in COMMON_BLOCK_WORDS if w in content), None)

    cfg = await get_default_llm_config(db)
    system_prompt = await get_review_prompt(db)
    user_content = f"待审查内容：\n{content[:4000]}\n\n本地预检命中词：{hit_word or '无'}"

    start = time.time()
    raw = ""
    try:
        raw = await chat_with_json(cfg, system_prompt, user_content)
        result = json.loads(raw)
        if not isinstance(result, dict) or "pass" not in result:
            raise ValueError("缺少 pass 字段")
    except Exception as exc:
        # AI 不返回 / 异常 / 输出非法 JSON / 缺字段：保守策略判定不通过，转人工复核
        result = {
            "pass": False,
            "reason": "AI 审核未返回有效结果（超时/异常/格式错误），已按不通过处理，转人工复核",
            "severity": "mid",
        }
        raw = raw or f"<error:{type(exc).__name__}>"

    # 预检命中高危词且 LLM 未识别时，提升为 mid（不误杀，转人工）
    if hit_word and result.get("pass", True):
        result = {"pass": False, "reason": f"命中敏感词「{hit_word}」，转人工复核", "severity": "mid"}

    db.add(
        AgentRun(
            trace_id=trace_id,
            trigger_type="compliance",
            post_id=post_id,
            node="guardrail",
            prompt=system_prompt + "\n---\n" + user_content,
            response=raw,
            latency_ms=int((time.time() - start) * 1000),
            decision=result.get("severity", "low"),
            score=None,
        )
    )
    await db.commit()
    return result
