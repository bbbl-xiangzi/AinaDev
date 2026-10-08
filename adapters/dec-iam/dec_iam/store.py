import hashlib
import json


class Store:
    """Redis 7 short-lived records; never use separate GET/DELETE for one-time values."""

    def __init__(self, redis):
        self.redis = redis

    def key(self, kind, token):
        return f"dec-iam:{kind}:{hashlib.sha256(token.encode()).hexdigest()}"

    async def put(self, kind, token, record, ttl):
        await self.redis.set(self.key(kind, token), json.dumps(record, ensure_ascii=False), ex=ttl)

    async def get(self, kind, token):
        value = await self.redis.get(self.key(kind, token))
        return json.loads(value) if value else None

    async def pop(self, kind, token):
        value = await self.redis.getdel(self.key(kind, token))
        return json.loads(value) if value else None
