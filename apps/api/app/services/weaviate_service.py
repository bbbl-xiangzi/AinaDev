"""Weaviate REST/GraphQL transport: all cross-host traffic uses HTTP(S)."""
import json
import logging
import re
import uuid

import httpx
from app.config import settings

logger = logging.getLogger(__name__)


def _client():
    scheme = "https" if settings.weaviate_secure else "http"
    headers = {"Authorization": f"Bearer {settings.weaviate_api_key}"} if settings.weaviate_api_key else {}
    return httpx.AsyncClient(base_url=f"{scheme}://{settings.weaviate_host}:{settings.weaviate_http_port}",
                             headers=headers, timeout=60, follow_redirects=False)


def _name():
    name = settings.weaviate_collection
    if not re.fullmatch(r"[A-Z][A-Za-z0-9_]*", name):
        raise ValueError("Invalid Weaviate collection name")
    return name


async def _ensure_collection(client):
    name = _name()
    response = await client.get(f"/v1/schema/{name}")
    if response.status_code != 404:
        response.raise_for_status()
        return
    props = [{"name": key, "dataType": ["int"]} for key in
             ("chunk_id", "document_id", "category_id", "chunk_index")]
    props += [{"name": key, "dataType": ["text"]} for key in ("title", "content", "filename")]
    response = await client.post("/v1/schema", json={
        "class": name, "vectorizer": "none", "properties": props,
        "vectorIndexConfig": {"distance": "cosine"},
    })
    if response.status_code in (409, 422):
        # API and worker may create the collection concurrently.
        response = await client.get(f"/v1/schema/{name}")
    response.raise_for_status()


async def upsert_chunk(chunk_id: int, document_id: int, category_id: int, chunk_index: int,
                       title, content: str, filename: str, vector: list[float]) -> None:
    obj_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ainadev-chunk-{chunk_id}"))
    props = {"chunk_id": int(chunk_id), "document_id": int(document_id),
             "category_id": int(category_id), "chunk_index": int(chunk_index),
             "title": title or "", "content": content[:20000], "filename": filename}
    body = {"class": _name(), "id": obj_uuid, "properties": props, "vector": vector}
    async with _client() as client:
        await _ensure_collection(client)
        response = await client.put(f"/v1/objects/{_name()}/{obj_uuid}", json=body)
        if response.status_code == 404:
            response = await client.post("/v1/objects", json=body)
        response.raise_for_status()


async def search_vectors(category_id: int, qvec: list[float], top: int = 20) -> list[tuple[int, float]]:
    try:
        return await _search_vectors(category_id, qvec, top)
    except (httpx.HTTPError, RuntimeError, KeyError, TypeError, ValueError):
        logger.warning("Weaviate search unavailable; using keyword retrieval")
        return []


async def _search_vectors(category_id: int, qvec: list[float], top: int) -> list[tuple[int, float]]:
    vector = json.dumps(qvec, allow_nan=False)
    query = ('{ Get { ' + _name() + '(nearVector: {vector: ' + vector + '}, '
             'where: {path: ["category_id"], operator: Equal, valueInt: ' + str(int(category_id)) + '}, '
             'limit: ' + str(max(1, min(int(top), 1000))) + ') { chunk_id _additional { distance } } } }')
    async with _client() as client:
        response = await client.post("/v1/graphql", json={"query": query})
        response.raise_for_status()
        data = response.json()
        if data.get("errors"):
            raise RuntimeError("Weaviate vector query failed")
        rows = data["data"]["Get"][_name()]
        return [(int(row["chunk_id"]), 1.0 - float(row["_additional"]["distance"])) for row in rows]


async def delete_document_chunks(document_id: int) -> None:
    async with _client() as client:
        # Batch deletion is capped server-side; repeat until no matches remain.
        while True:
            response = await client.request("DELETE", "/v1/batch/objects", json={
                "match": {"class": _name(), "where": {"path": ["document_id"],
                          "operator": "Equal", "valueInt": int(document_id)}},
                "output": "minimal", "dryRun": False,
            })
            if response.status_code == 404:
                return
            response.raise_for_status()
            results = response.json().get("results", {})
            if results.get("failed", 0):
                raise RuntimeError("Weaviate chunk deletion failed")
            matches = results.get("matches", 0)
            successful = results.get("successful", 0)
            if matches <= successful:
                return
            if not successful:
                raise RuntimeError("Weaviate chunk deletion made no progress")
