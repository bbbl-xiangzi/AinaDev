import json
import unittest
from unittest.mock import patch
import httpx
from app.services import weaviate_service as store


class SearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_outage_preserves_keyword_fallback(self):
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503)), base_url="http://search")
        with patch.object(store, "_client", return_value=client):
            self.assertEqual(await store.search_vectors(1, [1, 0]), [])

    async def test_distance_and_category_are_requested(self):
        def handle(request):
            query = json.loads(request.content)["query"]
            self.assertIn("valueInt: 7", query)
            self.assertIn("_additional { distance }", query)
            return httpx.Response(200, json={"data": {"Get": {"AinaDev": [
                {"chunk_id": 3, "_additional": {"distance": 0.2}}]}}})
        client = httpx.AsyncClient(transport=httpx.MockTransport(handle), base_url="http://search")
        with patch.object(store, "_client", return_value=client):
            self.assertEqual(await store.search_vectors(7, [1, 0], 4), [(3, 0.8)])

    async def test_upsert_replaces_existing_object(self):
        methods = []
        def handle(request):
            methods.append(request.method)
            return httpx.Response(200, json={})
        client = httpx.AsyncClient(transport=httpx.MockTransport(handle), base_url="http://search")
        with patch.object(store, "_client", return_value=client):
            await store.upsert_chunk(1, 2, 3, 0, None, "text", "a.txt", [1, 0])
        self.assertEqual(methods, ["GET", "PUT"])

    async def test_write_failure_is_not_silently_successful(self):
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503)), base_url="http://search")
        with patch.object(store, "_client", return_value=client), self.assertRaises(httpx.HTTPStatusError):
            await store.upsert_chunk(1, 2, 3, 0, None, "text", "a.txt", [1, 0])
